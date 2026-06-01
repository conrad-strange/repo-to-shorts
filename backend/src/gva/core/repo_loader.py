import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from git import Repo


def is_github_source(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com"


def clone_github_repo(source: str, cache_dir: Path) -> Path:
    parsed = urlparse(source)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Invalid GitHub repository URL: {source}")

    owner, repo_name = path_parts[0], path_parts[1].removesuffix(".git")
    target = cache_dir.resolve() / f"{owner}__{repo_name}"
    target.parent.mkdir(parents=True, exist_ok=True)

    if (target / ".git").exists():
        repo = Repo(target)
        try:
            sync_cached_repo_to_origin(repo)
        except Exception as exc:
            print(
                f"Warning: could not sync cached repo, using existing cache ({exc.__class__.__name__}).",
                file=sys.stderr,
            )
        return target

    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Cache target exists but is not a git repo: {target}")

    Repo.clone_from(source, target)
    return target


def sync_cached_repo_to_origin(repo: Repo) -> None:
    """Move a cached clone to the latest default remote branch.

    The repo cache is managed by this tool, so reusing an old working tree would
    be more surprising than resetting tracked files to the fetched remote state.
    """
    working_tree = Path(repo.working_tree_dir or ".").resolve()
    safe_config = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": working_tree.as_posix(),
    }
    with repo.git.custom_environment(**safe_config):
        fetch_result = subprocess.run(
            ["git", "fetch", "--prune", "origin"],
            cwd=working_tree,
            env={**os.environ, **safe_config},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if fetch_result.returncode != 0:
            raise RuntimeError("git fetch failed")
        default_ref = _resolve_origin_default_ref(repo)
        default_branch = default_ref.removeprefix("origin/")

        try:
            repo.git.checkout(default_branch)
        except Exception:
            repo.git.checkout("-B", default_branch, default_ref)
        repo.git.reset("--hard", default_ref)


def _resolve_origin_default_ref(repo: Repo) -> str:
    try:
        ref_path = repo.git.symbolic_ref("refs/remotes/origin/HEAD").strip()
        if ref_path.startswith("refs/remotes/"):
            return ref_path.removeprefix("refs/remotes/")
    except Exception:
        pass

    remote_heads = {ref.remote_head for ref in repo.remotes.origin.refs}
    if "main" in remote_heads:
        return "origin/main"
    if "master" in remote_heads:
        return "origin/master"
    for ref in repo.remotes.origin.refs:
        if ref.remote_head != "HEAD":
            return f"origin/{ref.remote_head}"
    raise ValueError("Could not resolve origin default branch.")


def resolve_project_path(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Project path does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Project path must be a directory: {resolved}")
    return resolved


def resolve_project_source(path: Path | None, repo: str | None, cache_dir: Path) -> Path:
    if path and repo:
        raise ValueError("Use either --path or --repo, not both.")
    if not path and not repo:
        raise ValueError("Please provide --path for a local project or --repo for a GitHub repository.")
    if repo:
        if not is_github_source(repo):
            raise ValueError("Only public GitHub repository URLs are supported for --repo in the MVP.")
        return clone_github_repo(repo, cache_dir)
    if path is None:
        raise ValueError("Missing project path.")
    return resolve_project_path(path)
