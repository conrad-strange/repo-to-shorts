from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from gva.config import Settings
from gva.models.storyboard import Storyboard


def prepare_remotion_public_assets(
    output_dir: Path,
    renderer_dir: Path,
    storyboard: Storyboard,
    audio_path: Path,
    settings: Settings,
) -> tuple[Path, Path]:
    public_dir = renderer_dir / "public" / "generated"
    public_dir.mkdir(parents=True, exist_ok=True)

    storyboard_public_path = public_dir / "storyboard.json"
    audio_public_path = public_dir / "voice.mp3"
    render_scale = _render_scale_for_profile(settings.render_profile)

    storyboard_public_path.write_text(
        storyboard.model_dump_json(indent=2),
        encoding="utf-8",
    )
    shutil.copyfile(audio_path, audio_public_path)

    manifest_path = output_dir / "logs" / "render-input.json"
    manifest_path.write_text(
        json.dumps(
            {
                "storyboard_public_path": str(storyboard_public_path),
                "audio_public_path": str(audio_public_path),
                "scene_count": len(storyboard.scenes),
                "duration_seconds": round(sum(scene.duration for scene in storyboard.scenes), 2),
                "render_profile": settings.render_profile,
                "render_width": round(storyboard.width * render_scale),
                "render_height": round(storyboard.height * render_scale),
                "render_fps": storyboard.fps,
                "render_scale": render_scale,
                "remotion_concurrency": settings.remotion_concurrency,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return storyboard_public_path, audio_public_path


def install_renderer_dependencies(settings: Settings) -> None:
    renderer_dir = settings.renderer_dir.resolve()
    node_modules = renderer_dir / "node_modules"
    if node_modules.exists():
        return
    npm = find_npm(settings)
    subprocess.run([str(npm), "install"], cwd=renderer_dir, check=True)


def render_video(output_dir: Path, settings: Settings) -> Path:
    renderer_dir = settings.renderer_dir.resolve()
    node = find_node(settings)
    ffmpeg = find_ffmpeg(settings)
    chrome = _optional_existing_path(settings.chrome_exe)
    remotion_cli = renderer_dir / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not remotion_cli.exists():
        raise FileNotFoundError(f"Remotion CLI does not exist: {remotion_cli}")
    timed_storyboard_path = output_dir / "storyboard-timed.json"
    if not timed_storyboard_path.exists():
        raise FileNotFoundError(f"Timed storyboard does not exist: {timed_storyboard_path}")
    storyboard = Storyboard.model_validate_json(timed_storyboard_path.read_text(encoding="utf-8"))
    render_scale = _render_scale_for_profile(settings.render_profile)
    video_path = output_dir / "video.mp4"
    full_env = os.environ.copy()
    full_env["REMOTION_FFMPEG_BINARY"] = str(ffmpeg)
    full_env["PATH"] = f"{ffmpeg.parent};{node.parent};{full_env.get('PATH', '')}"
    command = [
        str(node),
        str(remotion_cli),
        "render",
        "src/render-entry.tsx",
        "VerticalProjectVideo",
        str(video_path),
        "--props",
        json.dumps(
            {
                "storyboard": storyboard.model_dump(mode="json"),
                "audioSrc": "generated/voice.mp3",
            },
            ensure_ascii=False,
        ),
    ]
    if render_scale != 1:
        command.extend(["--scale", str(render_scale)])
    if chrome:
        command.extend(["--browser-executable", str(chrome)])
    if settings.remotion_concurrency and settings.remotion_concurrency > 0:
        command.extend(["--concurrency", str(settings.remotion_concurrency)])

    subprocess.run(
        command,
        cwd=renderer_dir,
        check=True,
        env=full_env,
    )
    return video_path


def find_node(settings: Settings) -> Path:
    return _find_tool(settings.node_exe, "NODE_EXE", "node-*-win-x64/node.exe", ["node.exe", "node"])


def find_npm(settings: Settings) -> Path:
    return _find_tool(settings.npm_cmd, "NPM_CMD", "node-*-win-x64/npm.cmd", ["npm.cmd", "npm"])


def find_ffmpeg(settings: Settings) -> Path:
    return _find_tool(settings.ffmpeg_exe, "FFMPEG_EXE", "**/ffmpeg.exe", ["ffmpeg.exe", "ffmpeg"])


def _storyboard_for_render(storyboard: Storyboard, render_profile: str) -> Storyboard:
    """Backward-compatible helper: preview scaling is handled by Remotion --scale."""
    return storyboard.model_copy(deep=True)


def _render_scale_for_profile(render_profile: str) -> float:
    """Keep the 1080x1920 composition intact and only scale the encoded output."""
    profile = (render_profile or "final").strip().lower()
    if profile == "preview":
        return 0.5
    if profile == "draft":
        return 0.5
    return 1


def _find_tool(configured: Path | None, name: str, tools_glob: str, path_names: list[str]) -> Path:
    candidates: list[Path] = []
    if configured:
        candidates.append(configured)
    candidates.extend(sorted(Path(".tools").glob(tools_glob), reverse=True))
    for executable in path_names:
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
    raise FileNotFoundError(
        f"{name} was not found. Set it in .env, run scripts/install-portable-tools.ps1, or install it on PATH."
    )


def _optional_existing_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = path.resolve()
    return resolved if resolved.exists() else None
