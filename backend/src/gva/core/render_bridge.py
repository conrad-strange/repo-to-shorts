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
    browser = find_browser(settings)
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
    if browser:
        command.extend(["--browser-executable", str(browser)])
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


def find_browser(settings: Settings) -> Path | None:
    """Find an optional Chromium-family browser for screenshots and Remotion."""
    candidates: list[Path] = []
    if settings.browser_exe:
        candidates.append(settings.browser_exe)
    if settings.chrome_exe:
        candidates.append(settings.chrome_exe)
    candidates.extend(_default_browser_candidates())
    for executable in ["chrome.exe", "msedge.exe", "chrome", "msedge", "google-chrome", "chromium"]:
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))
    candidates.extend(_registry_browser_candidates())

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


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


def _default_browser_candidates() -> list[Path]:
    if os.name != "nt":
        return []

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LocalAppData")
    candidates = [
        Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    if local_app_data:
        candidates.append(Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe")
        candidates.append(Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return candidates


def _registry_browser_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    candidates: list[Path] = []
    app_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
    ]
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    views = [0]
    for view in ["KEY_WOW64_64KEY", "KEY_WOW64_32KEY"]:
        if hasattr(winreg, view):
            views.append(getattr(winreg, view))

    for root in roots:
        for app_path in app_paths:
            for view in views:
                try:
                    with winreg.OpenKey(root, app_path, 0, winreg.KEY_READ | view) as key:
                        value, _ = winreg.QueryValueEx(key, "")
                except OSError:
                    continue
                if value:
                    candidates.append(Path(value))
    return candidates
