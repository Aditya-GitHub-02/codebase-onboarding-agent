from src.config import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_PROVIDER,
    MAX_PRIORITY_FILES,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from src.state import AgentState
from src.tools import get_readme, get_repo_metadata, get_repo_tree, read_file_content

MAX_CRITIC_ITERATIONS = 2
MAX_CRITIC_ADDITIONS = 3

ALWAYS_INCLUDE_NAMES = {
    "readme.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "main.py",
    "app.py",
    "index.js",
    "index.ts",
}

BOOST_DIR_PREFIXES = ("src/", "app/")
BOOST_NAME_KEYWORDS = ("main", "core", "config")

DEPRIORITIZE_DIR_PARTS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "test",
    "tests",
    "__pycache__",
    ".git",
}
DEPRIORITIZE_NAME_SUFFIXES = (".lock", ".min.js", ".map")
DEPRIORITIZE_NAME_PREFIXES = ("test_",)
DEPRIORITIZE_NAME_KEYWORDS = ("test", "generated", "lock")

MAX_FILE_SIZE_HINT_BYTES = 200_000


def _path_parts(path: str) -> list[str]:
    return path.split("/")


def _is_deprioritized(path: str) -> bool:
    parts = _path_parts(path)
    dirs = {p.lower() for p in parts[:-1]}
    if dirs & DEPRIORITIZE_DIR_PARTS:
        return True
    name = parts[-1].lower()
    if name.startswith(DEPRIORITIZE_NAME_PREFIXES):
        return True
    if name.endswith(DEPRIORITIZE_NAME_SUFFIXES):
        return True
    if any(keyword in name for keyword in DEPRIORITIZE_NAME_KEYWORDS):
        return True
    return False


def _score(path: str) -> int:
    name = _path_parts(path)[-1].lower()
    if name in ALWAYS_INCLUDE_NAMES:
        return 100

    score = 0
    if path.startswith(BOOST_DIR_PREFIXES):
        score += 10
    if any(keyword in name for keyword in BOOST_NAME_KEYWORDS):
        score += 5
    # Shallower files are generally more architecturally significant.
    score -= len(_path_parts(path))
    return score


def select_priority_files(file_tree: list[str], max_files: int = 12) -> list[str]:
    candidates = [path for path in file_tree if not _is_deprioritized(path)]
    ranked = sorted(candidates, key=_score, reverse=True)
    return ranked[:max_files]


def _llm():
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL, google_api_key=GOOGLE_API_KEY, temperature=0.2
        )

    if LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2)

    from langchain_groq import ChatGroq

    return ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.2)


def explorer_node(state: AgentState) -> AgentState:
    owner, repo = state["owner"], state["repo"]
    metadata = get_repo_metadata(owner, repo)
    branch = metadata["default_branch"]
    file_tree = get_repo_tree(owner, repo, branch)
    metadata["readme"] = get_readme(owner, repo)

    return {
        **state,
        "metadata": metadata,
        "file_tree": file_tree,
        "priority_files": select_priority_files(file_tree, max_files=MAX_PRIORITY_FILES),
    }


def reader_node(state: AgentState) -> AgentState:
    owner, repo = state["owner"], state["repo"]
    branch = state["metadata"]["default_branch"]
    llm = _llm()
    summaries = dict(state.get("file_summaries", {}))

    for path in state["priority_files"]:
        if path in summaries:
            continue
        content = read_file_content(owner, repo, path, branch)
        if content is None:
            continue
        response = llm.invoke(
            "You are briefing a developer onboarding to this codebase. Summarize the "
            f"file `{path}` in 3-4 sentences, and be concrete, not generic:\n"
            "1. What this file actually does (its role, not a restatement of its name).\n"
            "2. Key functions/classes/exports it defines, or key config/dependencies it "
            "declares, if applicable.\n"
            "3. What other parts of the codebase it likely connects to (imports, "
            "config it feeds, APIs it exposes), inferred from the content.\n"
            "Skip generic filler like 'this file is important for the project.' If the "
            "file is trivial (e.g. a near-empty init file), say so in one short sentence "
            "instead of padding it.\n\n"
            f"Content:\n{content[:8000]}"
        )
        summaries[path] = response.content

    return {**state, "file_summaries": summaries}


def synthesizer_node(state: AgentState) -> AgentState:
    llm = _llm()
    metadata = state["metadata"]
    summaries_text = "\n\n".join(
        f"### {path}\n{summary}" for path, summary in state["file_summaries"].items()
    )
    prompt = (
        "You are a senior engineer writing an onboarding brief for another engineer who "
        "has never seen this codebase. Be specific and concrete — every claim should be "
        "traceable to something in the README or file summaries below, not a generic "
        "description that could apply to any repo. Cite file paths in backticks "
        "(e.g. `src/main.py`) whenever you reference a specific file.\n\n"
        f"Repo description: {metadata.get('description')}\n"
        f"Primary language: {metadata.get('language')}\n"
        f"Stars: {metadata.get('stars')}\n\n"
        f"README:\n{(metadata.get('readme') or '')[:6000]}\n\n"
        f"File summaries:\n{summaries_text}\n\n"
        "Produce a structured markdown brief with exactly these sections, in this order:\n\n"
        "## Overview — 2-4 sentences on what this project actually does and who it's for, "
        "grounded in the README and file summaries, not boilerplate.\n\n"
        "## Tech Stack & Dependencies — the concrete languages, frameworks, and key "
        "libraries in use, inferred from manifest files (package.json, "
        "pyproject.toml, requirements.txt, etc.) and file summaries. Name actual "
        "package/framework names where you can identify them, not just 'Python'.\n\n"
        "## Architecture — how the pieces fit together: what depends on what, "
        "the overall shape of the codebase (e.g. monorepo, single service, plugin "
        "system), citing specific directories/files as evidence.\n\n"
        "## Key Modules — a bulleted list of the most important files/directories, each "
        "with a one-line, specific explanation of its role (not 'this is important').\n\n"
        "## Entry Points — the concrete file(s) or command(s) to run/import to start "
        "using this project, if identifiable. If there isn't a runnable entry point "
        "(e.g. this is a library or content repo), say so explicitly instead of guessing.\n\n"
        "## Suggested First Tasks — 3-5 concrete, actionable tasks a new contributor "
        "could pick up this week, each referencing a specific file or module by path."
    )
    response = llm.invoke(prompt)
    return {**state, "draft_brief": response.content}


MAX_CRITIC_CANDIDATES = 60


def critic_node(state: AgentState) -> AgentState:
    llm = _llm()
    already_read = set(state["priority_files"])
    remaining = [path for path in state["file_tree"] if path not in already_read]
    candidates = sorted(remaining, key=_score, reverse=True)[:MAX_CRITIC_CANDIDATES]
    candidates_text = "\n".join(candidates)

    prompt = (
        "Review this onboarding brief. Below is a shortlist of files from the repo that "
        "were NOT read yet (the rest of the repo's files were already covered). Are any of "
        "these obviously important (main entry point, core config, CI setup) and worth "
        "adding? Respond with a JSON object: "
        '{"missing_files": ["path1", "path2"]} (empty list if none, at most 3 paths that '
        "actually appear in the shortlist below).\n\n"
        f"Brief:\n{state['draft_brief']}\n\n"
        f"Unread file shortlist ({len(remaining)} unread files total, showing top "
        f"{len(candidates)}):\n{candidates_text}"
    )
    response = llm.invoke(prompt)

    missing: list[str] = []
    try:
        import json

        parsed = json.loads(response.content)
        missing = [
            path
            for path in parsed.get("missing_files", [])
            if path in candidates
        ][:MAX_CRITIC_ADDITIONS]
    except (json.JSONDecodeError, AttributeError):
        missing = []

    iterations = state.get("iterations", 0) + 1
    new_state = {**state, "iterations": iterations, "critic_feedback": response.content}

    if missing and iterations < MAX_CRITIC_ITERATIONS:
        new_state["priority_files"] = list(state["priority_files"]) + missing
        return new_state

    new_state["final_brief"] = state["draft_brief"]
    return new_state


def should_continue(state: AgentState) -> str:
    if state.get("final_brief"):
        return "end"
    return "reader"
