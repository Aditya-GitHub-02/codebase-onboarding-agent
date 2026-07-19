from src.nodes import select_priority_files

FAKE_TREE = [
    "README.md",
    "package.json",
    "src/main.py",
    "src/core/engine.py",
    "src/utils/helpers.py",
    "app/config.py",
    "node_modules/lodash/index.js",
    "vendor/some_lib/lib.py",
    "dist/bundle.min.js",
    "tests/test_engine.py",
    "test_helpers.py",
    "package-lock.json",
    "docs/architecture.md",
    "scripts/deploy.sh",
]


def test_always_includes_readme_and_manifest():
    result = select_priority_files(FAKE_TREE)
    assert "README.md" in result
    assert "package.json" in result


def test_filters_out_node_modules_vendor_dist():
    result = select_priority_files(FAKE_TREE)
    assert not any("node_modules" in path for path in result)
    assert not any("vendor" in path for path in result)
    assert not any("dist" in path for path in result)


def test_filters_out_test_files_and_lockfiles():
    result = select_priority_files(FAKE_TREE)
    assert "tests/test_engine.py" not in result
    assert "test_helpers.py" not in result
    assert "package-lock.json" not in result


def test_boosts_src_and_core_files():
    result = select_priority_files(FAKE_TREE)
    assert "src/main.py" in result
    assert "src/core/engine.py" in result


def test_caps_result_at_max_files():
    big_tree = [f"src/module_{i}.py" for i in range(50)]
    result = select_priority_files(big_tree, max_files=12)
    assert len(result) == 12
