import re

import streamlit as st
from groq import RateLimitError as GroqRateLimitError

from src.graph import build_graph
from src.tools import RateLimitError, RepoNotFoundError

REPO_URL_PATTERN = re.compile(
    r"^(?:https?://)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"
)

st.set_page_config(page_title="Codebase Onboarding Agent", layout="wide")


def parse_repo_url(url: str) -> tuple[str, str]:
    match = REPO_URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(
            "That doesn't look like a GitHub repo URL. Expected something like "
            "https://github.com/owner/repo"
        )
    return match.group(1), match.group(2)


def trace_line_for(node_name: str, node_state: dict) -> str:
    if node_name == "explorer":
        return (
            f"**Explorer**: found {len(node_state.get('file_tree', []))} files, "
            f"selected {len(node_state.get('priority_files', []))} priority files"
        )
    if node_name == "reader":
        return f"**Reader**: summarized {len(node_state.get('file_summaries', {}))} files"
    if node_name == "synthesizer":
        return "**Synthesizer**: drafted the onboarding brief"
    if node_name == "critic":
        if node_state.get("final_brief"):
            return "**Critic**: brief approved, no gaps found"
        added = len(node_state.get("priority_files", [])) - len(
            node_state.get("file_summaries", {})
        )
        return f"**Critic**: found gaps, looping back to read {max(added, 1)} more file(s)"
    return f"**{node_name}**: completed"


if "trace" not in st.session_state:
    st.session_state.trace = []
if "final_brief" not in st.session_state:
    st.session_state.final_brief = ""
if "metadata" not in st.session_state:
    st.session_state.metadata = {}
if "error" not in st.session_state:
    st.session_state.error = ""

st.title("Codebase Onboarding Agent")
st.caption("Paste a public GitHub repo URL and get an AI-generated onboarding brief.")

repo_url = st.text_input("GitHub repo URL", placeholder="https://github.com/owner/repo")
analyze_clicked = st.button("Analyze Repository", type="primary")

with st.sidebar:
    st.header("About")
    st.markdown(
        "This agent reads only the ~12 most relevant files out of the full repo, "
        "using path-based heuristics, to keep analysis fast and cheap."
    )
    if st.session_state.metadata:
        st.subheader("Repo metadata")
        st.write(f"⭐ Stars: {st.session_state.metadata.get('stars', 'n/a')}")
        st.write(f"Language: {st.session_state.metadata.get('language', 'n/a')}")

if analyze_clicked:
    st.session_state.trace = []
    st.session_state.final_brief = ""
    st.session_state.metadata = {}
    st.session_state.error = ""

    try:
        owner, repo = parse_repo_url(repo_url)
    except ValueError as exc:
        st.session_state.error = str(exc)
    else:
        initial_state = {
            "repo_url": repo_url,
            "owner": owner,
            "repo": repo,
            "metadata": {},
            "file_tree": [],
            "priority_files": [],
            "file_summaries": {},
            "draft_brief": "",
            "critic_feedback": "",
            "iterations": 0,
            "final_brief": "",
        }

        trace_container = st.expander("Agent Trace", expanded=True)
        try:
            graph = build_graph()
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                for node_name, node_state in chunk.items():
                    line = trace_line_for(node_name, node_state)
                    st.session_state.trace.append(line)
                    trace_container.write(line)
                    if node_name == "explorer":
                        st.session_state.metadata = node_state.get("metadata", {})
                    if node_state.get("final_brief"):
                        st.session_state.final_brief = node_state["final_brief"]
        except RepoNotFoundError:
            st.session_state.error = (
                "Repo not found — check the URL, or the repo may be private."
            )
        except RateLimitError:
            st.session_state.error = (
                "GitHub API rate limit hit. Add a GITHUB_TOKEN to raise the limit, "
                "or try again later."
            )
        except GroqRateLimitError as exc:
            detail = str(exc)
            if "tokens per day" in detail or "TPD" in detail:
                st.session_state.error = (
                    "Groq's free-tier **daily** token quota is used up for now. It "
                    "resets on a rolling 24h window — try again later, or upgrade at "
                    "console.groq.com/settings/billing."
                )
            else:
                st.session_state.error = (
                    "Groq's free-tier **per-minute** token limit was hit (this repo has "
                    "a lot of files to summarize at once). Wait a minute and try again."
                )
        except Exception as exc:  # noqa: BLE001 - surface a clean message, not a traceback
            st.session_state.error = f"Something went wrong: {exc}"

if st.session_state.error:
    st.error(st.session_state.error)

if st.session_state.final_brief:
    st.markdown("## Onboarding Brief")
    st.markdown(st.session_state.final_brief)
