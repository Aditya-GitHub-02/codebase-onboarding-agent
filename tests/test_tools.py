import base64
from unittest.mock import patch

import pytest

from src.tools import (
    RateLimitError,
    RepoNotFoundError,
    get_readme,
    get_repo_metadata,
    get_repo_tree,
    read_file_content,
)

OWNER, REPO, BRANCH = "octocat", "Hello-World", "master"


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@patch("src.tools.requests.get")
def test_get_repo_metadata(mock_get):
    mock_get.return_value = FakeResponse(
        200,
        {
            "description": "My first repository on GitHub!",
            "language": "C",
            "stargazers_count": 2800,
            "default_branch": "master",
        },
    )
    result = get_repo_metadata(OWNER, REPO)
    assert result == {
        "description": "My first repository on GitHub!",
        "language": "C",
        "stars": 2800,
        "default_branch": "master",
    }


@patch("src.tools.requests.get")
def test_get_repo_tree(mock_get):
    mock_get.return_value = FakeResponse(
        200,
        {
            "tree": [
                {"path": "README", "type": "blob"},
                {"path": "src", "type": "tree"},
                {"path": "src/main.c", "type": "blob"},
            ]
        },
    )
    result = get_repo_tree(OWNER, REPO, BRANCH)
    assert result == ["README", "src/main.c"]


@patch("src.tools.requests.get")
def test_read_file_content_decodes_base64(mock_get):
    encoded = base64.b64encode(b"hello world").decode()
    mock_get.return_value = FakeResponse(200, {"encoding": "base64", "content": encoded})
    result = read_file_content(OWNER, REPO, "README", BRANCH)
    assert result == "hello world"


@patch("src.tools.requests.get")
def test_read_file_content_binary_returns_none(mock_get):
    encoded = base64.b64encode(b"\xff\xfe\x00\x01").decode()
    mock_get.return_value = FakeResponse(200, {"encoding": "base64", "content": encoded})
    result = read_file_content(OWNER, REPO, "image.png", BRANCH)
    assert result is None


@patch("src.tools.requests.get")
def test_get_readme(mock_get):
    encoded = base64.b64encode(b"# Hello World").decode()
    mock_get.return_value = FakeResponse(200, {"encoding": "base64", "content": encoded})
    result = get_readme(OWNER, REPO)
    assert result == "# Hello World"


@patch("src.tools.requests.get")
def test_get_readme_missing_returns_none(mock_get):
    mock_get.return_value = FakeResponse(404, {})
    result = get_readme(OWNER, REPO)
    assert result is None


@patch("src.tools.requests.get")
def test_rate_limit_raises(mock_get):
    mock_get.return_value = FakeResponse(403, {})
    with pytest.raises(RateLimitError):
        get_repo_metadata(OWNER, REPO)


@patch("src.tools.requests.get")
def test_not_found_raises(mock_get):
    mock_get.return_value = FakeResponse(404, {})
    with pytest.raises(RepoNotFoundError):
        get_repo_metadata(OWNER, REPO)
