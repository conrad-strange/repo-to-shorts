from __future__ import annotations

import json
import shutil
from pathlib import Path

from gva.models.evidence import RunInfo


def allocate_run(root_output_dir: Path, requested_run: str | None = None) -> RunInfo:
    root = root_output_dir.resolve()
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = requested_run or _next_run_id(runs_dir)
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
    return candidate if candidate.exists() else root / run


def list_run_ids(root_output_dir: Path) -> list[str]:
    runs_dir = root_output_dir.resolve() / "runs"
    if not runs_dir.exists():
        return []
    return sorted(path.name for path in runs_dir.iterdir() if path.is_dir())


def publish_latest_video(run_dir: Path, root_output_dir: Path, video_path: Path) -> Path:
    latest_dir = root_output_dir / "videos" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_path = latest_dir / "video.mp4"
    shutil.copyfile(video_path, latest_path)
    manifest = {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "source_video": str(video_path),
        "latest_video": str(latest_path),
    }
    (latest_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest_path


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


def _next_run_id(runs_dir: Path) -> str:
    existing = [int(path.name) for path in runs_dir.iterdir() if path.is_dir() and path.name.isdigit()]
    return f"{(max(existing) + 1) if existing else 1:04d}"


def _latest_run_id(runs_dir: Path) -> str | None:
    if not runs_dir.exists():
        return None
    ids = [path.name for path in runs_dir.iterdir() if path.is_dir()]
    return sorted(ids)[-1] if ids else None
