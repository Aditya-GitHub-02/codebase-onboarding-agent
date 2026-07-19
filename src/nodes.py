from langchain_groq import ChatGroq

from src.config import GROQ_API_KEY, GROQ_MODEL
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
        "priority_files": select_priority_files(file_tree),
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
            "Summarize the purpose of this file in 2-3 sentences, for someone "
            f"onboarding to the codebase.\n\nFile: {path}\n\n{content[:6000]}"
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
        "You are writing an onboarding brief for a developer new to this codebase.\n\n"
        f"Repo description: {metadata.get('description')}\n"
        f"Primary language: {metadata.get('language')}\n"
        f"Stars: {metadata.get('stars')}\n\n"
        f"README:\n{(metadata.get('readme') or '')[:4000]}\n\n"
        f"File summaries:\n{summaries_text}\n\n"
        "Produce a structured markdown brief with exactly these sections: "
        "## Overview, ## Architecture, ## Key Modules, ## Entry Points, "
        "## Suggested First Tasks."
    )
    response = llm.invoke(prompt)
    return {**state, "draft_brief": response.content}


def critic_node(state: AgentState) -> AgentState:
    llm = _llm()
    file_tree_text = "\n".join(state["file_tree"])
    prompt = (
        "Review this onboarding brief against the full repo file tree. Are there any "
        "obviously important files (main entry point, core config, CI setup) that were "
        "missed? Respond with a JSON object: "
        '{"missing_files": ["path1", "path2"]} (empty list if none, at most 3 paths that '
        "actually appear in the file tree below).\n\n"
        f"Brief:\n{state['draft_brief']}\n\n"
        f"File tree:\n{file_tree_text}"
    )
    response = llm.invoke(prompt)

    missing: list[str] = []
    try:
        import json

        parsed = json.loads(response.content)
        missing = [
            path
            for path in parsed.get("missing_files", [])
            if path in state["file_tree"]
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
