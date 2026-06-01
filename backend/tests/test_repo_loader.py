from pathlib import Path

import pytest
from git import Repo

from gva.core.repo_loader import is_github_source, resolve_project_source, sync_cached_repo_to_origin


def test_is_github_source_accepts_github_url() -> None:
    assert is_github_source("https://github.com/conrad-strange/rag-demo")
    assert not is_github_source("https://example.com/conrad-strange/rag-demo")


def test_resolve_project_source_requires_one_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_project_source(None, None, tmp_path)

    with pytest.raises(ValueError):
        resolve_project_source(tmp_path, "https://github.com/conrad-strange/rag-demo", tmp_path)


def test_sync_cached_repo_to_origin_resets_to_latest_remote(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    source_repo = Repo.init(source, initial_branch="main")
    with source_repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    readme = source / "README.md"
    readme.write_text("old", encoding="utf-8")
    source_repo.index.add(["README.md"])
    source_repo.index.commit("initial")

    remote = tmp_path / "remote.git"
    remote_repo = source_repo.clone(str(remote), bare=True)
    remote_repo.close()
    source_repo.create_remote("origin", str(remote))

    cached = tmp_path / "cached"
    cached_repo = Repo.clone_from(str(remote), cached)
    assert (cached / "README.md").read_text(encoding="utf-8") == "old"

    readme.write_text("new", encoding="utf-8")
    source_repo.index.add(["README.md"])
    source_repo.index.commit("update")
    source_repo.remotes.origin.push("main")

    sync_cached_repo_to_origin(cached_repo)

    assert (cached / "README.md").read_text(encoding="utf-8") == "new"
