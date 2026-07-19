import base64
from typing import Optional

import requests

from src.config import GITHUB_TOKEN

API_ROOT = "https://api.github.com"


class GitHubAPIError(Exception):
    pass


class RateLimitError(GitHubAPIError):
    pass


class RepoNotFoundError(GitHubAPIError):
    pass


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _get(url: str, params: Optional[dict] = None) -> requests.Response:
    response = requests.get(url, headers=_headers(), params=params, timeout=15)
    if response.status_code == 403:
        raise RateLimitError(
            f"GitHub API rate limit exceeded or access forbidden for {url}"
        )
    if response.status_code == 404:
        raise RepoNotFoundError(f"Resource not found: {url}")
    response.raise_for_status()
    return response


def get_repo_metadata(owner: str, repo: str) -> dict:
    data = _get(f"{API_ROOT}/repos/{owner}/{repo}").json()
    return {
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data.get("stargazers_count", 0),
        "default_branch": data.get("default_branch", "main"),
    }


def get_repo_tree(owner: str, repo: str, branch: str) -> list[str]:
    data = _get(
        f"{API_ROOT}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
    ).json()
    return [
        item["path"]
        for item in data.get("tree", [])
        if item.get("type") == "blob"
    ]


def read_file_content(owner: str, repo: str, path: str, branch: str) -> Optional[str]:
    data = _get(
        f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}",
        params={"ref": branch},
    ).json()
    if data.get("encoding") != "base64":
        return None
    raw = base64.b64decode(data["content"])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def get_readme(owner: str, repo: str) -> Optional[str]:
    try:
        data = _get(f"{API_ROOT}/repos/{owner}/{repo}/readme").json()
    except RepoNotFoundError:
        return None
    if data.get("encoding") != "base64":
        return None
    raw = base64.b64decode(data["content"])
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
