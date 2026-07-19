import os

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
