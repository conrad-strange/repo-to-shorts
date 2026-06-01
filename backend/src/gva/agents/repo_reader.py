from pathlib import Path

from gva.core.file_scanner import build_tree_overview, detect_stack, scan_project
from gva.models.repo import RepoSummary


def read_repo(path: Path) -> RepoSummary:
    root = path.resolve()
    files = scan_project(root)
    return RepoSummary(
        source=str(root),
        repo_name=root.name,
        files=files,
        tree_overview=build_tree_overview(root),
        detected_stack=detect_stack(files),
    )
