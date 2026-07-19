from typing import TypedDict


class AgentState(TypedDict):
    repo_url: str
    owner: str
    repo: str
    metadata: dict
    file_tree: list[str]
    priority_files: list[str]
    file_summaries: dict[str, str]
    draft_brief: str
    critic_feedback: str
    iterations: int
    final_brief: str
