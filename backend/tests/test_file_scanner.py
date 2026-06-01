from pathlib import Path

from gva.agents.repo_reader import read_repo


def test_read_repo_selects_key_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nA useful project.", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")

    summary = read_repo(tmp_path)
    paths = [file.path for file in summary.files]

    assert "README.md" in paths
    assert "pyproject.toml" in paths
    assert "main.py" in paths
    assert "node_modules/ignored.js" not in paths
    assert "Python" in summary.detected_stack
