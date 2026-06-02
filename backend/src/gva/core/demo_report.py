from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from gva.config import Settings


def generate_demo_assets(output_dir: Path, settings: Settings, metadata: dict[str, Any]) -> dict[str, Any]:
    video_path = _resolve_video_path(output_dir)
    preview_dir = output_dir / "preview_frames"
    preview_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "video_path": str(video_path) if video_path.exists() else None,
        "preview_frames_dir": str(preview_dir),
        "frames": [],
        "preview_grid": None,
        "demo_report": str(output_dir / "demo_report.md"),
    }

    duration = _duration_from_metadata(output_dir, metadata)
    if video_path.exists() and settings.ffmpeg_exe and settings.ffmpeg_exe.exists() and duration:
        frame_paths = _extract_preview_frames(video_path, preview_dir, settings.ffmpeg_exe, duration)
        result["frames"] = [str(path) for path in frame_paths]
        grid_path = _create_preview_grid(preview_dir, settings.ffmpeg_exe)
        if grid_path:
            result["preview_grid"] = str(grid_path)

    _write_demo_report(output_dir, metadata, result)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (output_dir / "logs" / "demo-assets.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _extract_preview_frames(video_path: Path, preview_dir: Path, ffmpeg: Path, duration: float) -> list[Path]:
    times = _preview_times(duration)
    frames: list[Path] = []
    for index, seconds in enumerate(times, start=1):
        output = preview_dir / f"frame_{index:02d}.jpg"
        command = [
            str(ffmpeg),
            "-y",
            "-ss",
            f"{seconds:.2f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2:color=0x0D1117",
            "-q:v",
            "3",
            str(output),
        ]
        subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if output.exists() and output.stat().st_size > 0:
            frames.append(output)
    return frames


def _create_preview_grid(preview_dir: Path, ffmpeg: Path) -> Path | None:
    first_frame = preview_dir / "frame_%02d.jpg"
    if not (preview_dir / "frame_01.jpg").exists():
        return None
    output = preview_dir / "preview_grid.jpg"
    command = [
        str(ffmpeg),
        "-y",
        "-framerate",
        "1",
        "-i",
        str(first_frame),
        "-vf",
        "tile=3x2:margin=18:padding=12:color=0x0D1117,scale=900:-1",
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(output),
    ]
    subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return output if output.exists() and output.stat().st_size > 0 else None


def _write_demo_report(output_dir: Path, metadata: dict[str, Any], demo_assets: dict[str, Any]) -> None:
    lines = [
        "# Demo Report",
        "",
        f"- Input repo: `{metadata.get('repo_url') or metadata.get('project_path') or 'unknown'}`",
        f"- Run id: `{metadata.get('run_id', output_dir.name)}`",
        f"- Output video: `{metadata.get('video_path') or demo_assets.get('video_path') or 'not rendered'}`",
        f"- Verification passed: `{metadata.get('verification_passed', 'unknown')}`",
        f"- Evaluation score: `{metadata.get('evaluation_score', 'unknown')}`",
        "",
        "## Key Artifacts",
        "",
        "- `repo-summary.json`",
        "- `project-insight.json`",
        "- `video-script.json` and `script.md`",
        "- `storyboard.raw.json`, `storyboard.final.json`, `storyboard-timed.json`",
        "- `verification-report.md` and `evaluation-report.md`",
        "- `subtitles.srt` and `subtitles.vtt`",
        "- `preview_frames/preview_grid.jpg`",
        "",
    ]
    grid = demo_assets.get("preview_grid")
    if grid:
        grid_path = Path(grid)
        try:
            relative = grid_path.relative_to(output_dir).as_posix()
        except ValueError:
            relative = grid_path.as_posix()
        lines.extend(["## Preview", "", f"![Preview Grid]({relative})", ""])

    frames = demo_assets.get("frames") or []
    if frames:
        lines.extend(["## Preview Frames", ""])
        for frame in frames:
            frame_path = Path(frame)
            try:
                relative = frame_path.relative_to(output_dir).as_posix()
            except ValueError:
                relative = frame_path.as_posix()
            lines.append(f"- ![]({relative}) `{relative}`")
        lines.append("")

    (output_dir / "demo_report.md").write_text("\n".join(lines), encoding="utf-8")


def _preview_times(duration: float) -> list[float]:
    if duration <= 0:
        return []
    anchors = [2.0, duration * 0.22, duration * 0.4, duration * 0.6, duration * 0.78, max(0.5, duration - 2.0)]
    clean = sorted({round(min(max(value, 0.2), max(duration - 0.2, 0.2)), 2) for value in anchors})
    return clean[:6]


def _duration_from_metadata(output_dir: Path, metadata: dict[str, Any]) -> float | None:
    for key in ("voice_audio_duration_seconds", "timed_storyboard_duration_seconds"):
        value = metadata.get(key)
        if isinstance(value, (int, float)) and not math.isnan(value):
            return float(value)
    evaluation_path = output_dir / "evaluation-report.json"
    if evaluation_path.exists():
        try:
            payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
            duration = payload.get("metrics", {}).get("duration_seconds")
            if isinstance(duration, (int, float)):
                return float(duration)
        except Exception:
            return None
    return None


def _resolve_video_path(output_dir: Path) -> Path:
    return output_dir / "video.mp4"
