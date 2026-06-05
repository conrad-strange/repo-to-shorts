from __future__ import annotations

import re
import shutil
from pathlib import Path

from gva.models.evidence import RunInfo


def allocate_run(root_output_dir: Path, requested_run: str | None = None, label_suffix: str | None = None) -> RunInfo:
    root = root_output_dir.resolve()
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = requested_run or _next_run_id(runs_dir, label_suffix=label_suffix)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunInfo(run_id=run_id, run_dir=run_dir, root_output_dir=root)


def resolve_run_dir(root_output_dir: Path, run: str = "latest") -> Path:
    root = root_output_dir.resolve()
    if run == "latest":
        latest = _latest_run_id(root / "runs")
        if latest is None:
            return root
        return root / "runs" / latest
    candidate = root / "runs" / run
    if candidate.exists():
        return candidate
    prefixed = _run_dir_by_numeric_prefix(root / "runs", run)
    if prefixed is not None:
        return prefixed
    return root / run


def list_run_ids(root_output_dir: Path) -> list[str]:
    runs_dir = root_output_dir.resolve() / "runs"
    if not runs_dir.exists():
        return []
    return sorted((path.name for path in runs_dir.iterdir() if path.is_dir()), key=_run_sort_key)


def clean_old_runs(root_output_dir: Path, keep: int) -> list[Path]:
    run_ids = list_run_ids(root_output_dir)
    removable = run_ids[: max(0, len(run_ids) - keep)]
    removed: list[Path] = []
    for run_id in removable:
        path = root_output_dir.resolve() / "runs" / run_id
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
    return removed


def _next_run_id(runs_dir: Path, label_suffix: str | None = None) -> str:
    existing = [_run_number(path.name) for path in runs_dir.iterdir() if path.is_dir()]
    next_number = (max(number for number in existing if number is not None) + 1) if any(
        number is not None for number in existing
    ) else 1
    base = f"{next_number:04d}"
    suffix = _clean_label_suffix(label_suffix)
    return f"{base}+{suffix}" if suffix else base


def _latest_run_id(runs_dir: Path) -> str | None:
    if not runs_dir.exists():
        return None
    ids = [path.name for path in runs_dir.iterdir() if path.is_dir()]
    return sorted(ids, key=_run_sort_key)[-1] if ids else None


def _run_dir_by_numeric_prefix(runs_dir: Path, run: str) -> Path | None:
    if not runs_dir.exists() or not re.fullmatch(r"\d{4}", run):
        return None
    matches = [path for path in runs_dir.iterdir() if path.is_dir() and path.name.startswith(f"{run}+")]
    if len(matches) != 1:
        return None
    return matches[0]


def _run_sort_key(run_id: str) -> tuple[int, str]:
    number = _run_number(run_id)
    return (number if number is not None else 10**9, run_id)


def _run_number(run_id: str) -> int | None:
    match = re.match(r"^(\d{4})(?:\+.+)?$", run_id)
    if not match:
        return None
    return int(match.group(1))


def _clean_label_suffix(value: str | None) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", str(value or "").strip())
    return cleaned or None
