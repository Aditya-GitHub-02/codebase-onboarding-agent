import os

import pytest

pytestmark = pytest.mark.integration

OWNER, REPO = "octocat", "Hello-World"


@pytest.mark.skipif(
    not (os.environ.get("GROQ_API_KEY") and os.environ.get("GITHUB_TOKEN")),
    reason="requires real GROQ_API_KEY and GITHUB_TOKEN for a live integration run",
)
def test_full_graph_produces_final_brief():
    from src.graph import build_graph

    graph = build_graph()
    result = graph.invoke(
        {
            "repo_url": f"https://github.com/{OWNER}/{REPO}",
            "owner": OWNER,
            "repo": REPO,
            "metadata": {},
            "file_tree": [],
            "priority_files": [],
            "file_summaries": {},
            "draft_brief": "",
            "critic_feedback": "",
            "iterations": 0,
            "final_brief": "",
        }
    )
    assert result["final_brief"]
