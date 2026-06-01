from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from gva.config import Settings
from gva.models.repo import RepoSummary
from gva.models.storyboard import MicroBeat, Storyboard


@dataclass
class ReadmeEvidence:
    title: str | None = None
    intro: str | None = None
    highlights: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)


def prepare_visual_assets(
    output_dir: Path,
    renderer_dir: Path,
    repo_summary: RepoSummary,
    storyboard: Storyboard,
    repo_url: str | None,
    settings: Settings,
) -> Storyboard:
    """Prepare repo-sourced visual assets and annotate storyboard scenes."""
    output_assets = output_dir / "assets"
    public_assets = renderer_dir / "public" / "generated" / "assets"
    output_assets.mkdir(parents=True, exist_ok=True)
    public_assets.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "github_screenshot": {"status": "skipped", "reason": "repo_url not provided"},
        "readme": {},
        "annotations": [],
    }

    enhanced = storyboard.model_copy(deep=True)
    for scene in enhanced.scenes:
        scene.visual.enhanced_html = None
        scene.visual.enhanced_by = None
    _sanitize_setup_visuals(enhanced)

    public_screenshot_path = None
    if repo_url:
        screenshot_result = _capture_github_repo_screenshot(
            repo_url=repo_url,
            output_path=output_assets / "github-repo-home.png",
            public_path=public_assets / "github-repo-home.png",
            settings=settings,
        )
        if screenshot_result.get("status") != "ok":
            screenshot_result = _use_cached_github_screenshot(
                screenshot_result,
                output_assets / "github-repo-home.png",
                public_assets / "github-repo-home.png",
            )
        manifest["github_screenshot"] = screenshot_result
        if screenshot_result.get("status") in {"ok", "cached"}:
            public_screenshot_path = "generated/assets/github-repo-home.png"

    readme = extract_readme_evidence(repo_summary)
    manifest["readme"] = {
        "title": readme.title,
        "intro": readme.intro,
        "highlights": readme.highlights[:3],
        "section_count": len(readme.sections),
    }

    if public_screenshot_path:
        _annotate_github_hero(enhanced, public_screenshot_path, repo_url, manifest)
    if readme.title or readme.intro or readme.highlights or readme.sections:
        _annotate_readme_focus(enhanced, readme, manifest)
    _enrich_scene_layouts(enhanced, repo_summary, readme, manifest)
    _annotate_cta_repo_identity(enhanced, repo_url, manifest)

    _write_manifest(output_dir, manifest)
    return enhanced


def extract_readme_evidence(repo_summary: RepoSummary) -> ReadmeEvidence:
    readme_file = next((file for file in repo_summary.files if file.role == "readme"), None)
    if readme_file is None:
        return ReadmeEvidence()

    text = readme_file.excerpt
    lines = [line.rstrip() for line in text.splitlines()]
    title = None
    intro = None
    sections: list[str] = []
    highlights: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("#") and not title:
            title = stripped.lstrip("#").strip()
            continue
        if stripped.startswith("##"):
            section = stripped.lstrip("#").strip()
            if section and not _looks_like_setup_text(section):
                sections.append(section)
            continue

        highlight = _extract_readme_highlight(stripped)
        if highlight and highlight not in highlights:
            highlights.append(highlight)

        if not intro and stripped and not stripped.startswith("#") and not stripped.startswith("!") and not stripped.startswith("["):
            candidate = _strip_markdown(stripped)
            if candidate and not _looks_like_setup_text(candidate) and not _looks_like_command(candidate):
                intro = candidate

    return ReadmeEvidence(
        title=title,
        intro=intro,
        highlights=highlights[:5],
        sections=sections[:8],
    )


def _capture_github_repo_screenshot(
    repo_url: str,
    output_path: Path,
    public_path: Path,
    settings: Settings,
) -> dict:
    chrome = settings.chrome_exe
    if chrome is None or not chrome.exists():
        return {"status": "failed", "reason": "CHROME_EXE is not configured or does not exist"}
    if not _is_github_url(repo_url):
        return {"status": "failed", "reason": "repo_url is not a GitHub URL"}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    command = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-dev-shm-usage",
        "--hide-crash-restore-bubble",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=3000",
        "--window-size=1440,1400",
        f"--screenshot={output_path}",
        repo_url,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=45,
        )
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}

    if not output_path.exists() or output_path.stat().st_size == 0:
        return {
            "status": "failed",
            "reason": (result.stderr or result.stdout or "Chrome screenshot failed").strip()[:500],
        }

    shutil.copyfile(output_path, public_path)
    return {
        "status": "ok",
        "output_path": str(output_path),
        "public_path": str(public_path),
        "public_src": "generated/assets/github-repo-home.png",
    }


def _use_cached_github_screenshot(result: dict, output_path: Path, public_path: Path) -> dict:
    if public_path.exists():
        return {
            "status": "cached",
            "reason": result.get("reason", "screenshot refresh failed"),
            "output_path": str(output_path) if output_path.exists() else None,
            "public_path": str(public_path),
            "public_src": "generated/assets/github-repo-home.png",
        }
    if output_path.exists():
        public_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_path, public_path)
        return {
            "status": "cached",
            "reason": result.get("reason", "screenshot refresh failed"),
            "output_path": str(output_path),
            "public_path": str(public_path),
            "public_src": "generated/assets/github-repo-home.png",
        }
    return result


def _annotate_github_hero(
    storyboard: Storyboard,
    asset_path: str,
    repo_url: str | None,
    manifest: dict,
) -> None:
    if not storyboard.scenes:
        return
    scene = storyboard.scenes[0]
    if scene.visual.layout not in {"hook", "github_hero"}:
        return
    scene.visual.layout = "github_hero"
    scene.type = "github_hero"
    scene.visual.asset_type = "github_repo_home"
    scene.visual.asset_path = asset_path
    scene.visual.focus_target = "repo_name"
    scene.visual.repo_url = repo_url
    scene.visual.repo_display_url = _display_repo_url(repo_url)
    if not scene.visual.caption:
        scene.visual.caption = "真实 GitHub 仓库"
    manifest["annotations"].append(
        {
            "scene_id": scene.id,
            "asset_type": "github_repo_home",
            "repo_display_url": scene.visual.repo_display_url,
        }
    )


def _display_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    parsed = urlparse(repo_url)
    if parsed.netloc.lower() == "github.com":
        path = parsed.path.strip("/")
        return f"github.com/{path}" if path else "github.com"
    return repo_url.removeprefix("https://").removeprefix("http://").rstrip("/")


def _repo_handle(repo_url: str | None) -> str | None:
    display = _display_repo_url(repo_url)
    if not display:
        return None
    return display.removeprefix("github.com/").rstrip("/")


def _annotate_cta_repo_identity(storyboard: Storyboard, repo_url: str | None, manifest: dict) -> None:
    handle = _repo_handle(repo_url)
    if not handle:
        return
    scene = next((item for item in reversed(storyboard.scenes) if item.visual.layout == "cta"), None)
    if scene is None:
        return
    scene.visual.repo_url = repo_url
    scene.visual.repo_display_url = handle
    scene.visual.headline = handle
    scene.visual.bullets = ["GitHub 上查看项目", "README / Star / Clone"]
    scene.visual.caption = "GitHub 项目"
    scene.visual.micro_beats = [
        MicroBeat(text=handle, kind="cta", emphasis="GitHub", start_ratio=0.0),
        MicroBeat(text="README / Star / Clone", kind="cta", start_ratio=0.36),
    ]
    manifest["annotations"].append(
        {
            "scene_id": scene.id,
            "asset_type": "cta_repo_identity",
            "repo_display_url": handle,
        }
    )


def _annotate_readme_focus(storyboard: Storyboard, readme: ReadmeEvidence, manifest: dict) -> None:
    scene = next(
        (item for item in storyboard.scenes[1:] if item.visual.layout == "readme_focus"),
        None,
    )
    if scene is None:
        scene = next(
            (
                item
                for item in storyboard.scenes[1:]
                if item.visual.layout in {"title", "text", "steps"} and item.visual.asset_type == "none"
            ),
            None,
        )
    if scene is None:
        return

    scene.visual.layout = "readme_focus"
    scene.type = "readme_focus"
    scene.visual.asset_type = "readme_focus"
    scene.visual.focus_target = "readme_title" if readme.title else "readme_section"
    scene.visual.headline = "README 内容证据"
    bullets = [item for item in [readme.title, _compact_readme_intro(readme.intro)] if item]
    bullets.extend(readme.highlights[: 3 - len(bullets)])
    if len(bullets) < 3:
        bullets.extend(readme.sections[: 3 - len(bullets)])
    if bullets:
        scene.visual.bullets = bullets[:3]
    scene.visual.code = None
    scene.visual.micro_beats = [
        MicroBeat(text=text[:28], kind="text", start_ratio=index * 0.22)
        for index, text in enumerate(scene.visual.bullets[:3])
    ]
    manifest["annotations"].append({"scene_id": scene.id, "asset_type": "readme_focus"})


def _enrich_scene_layouts(
    storyboard: Storyboard,
    repo_summary: RepoSummary,
    readme: ReadmeEvidence,
    manifest: dict,
) -> None:
    for scene in storyboard.scenes[1:-1]:
        if scene.visual.layout == "flow" and len(scene.visual.diagram_nodes) >= 3:
            scene.visual.layout = "architecture_map"
            scene.type = "architecture_map"
            manifest["annotations"].append({"scene_id": scene.id, "layout": "architecture_map"})
            continue

        if scene.visual.layout in {"title", "text"} and len(scene.visual.bullets) >= 2:
            scene.visual.layout = "feature_spotlight"
            scene.type = "feature_spotlight"
            scene.visual.micro_beats = [
                MicroBeat(text=text[:42], kind="text", start_ratio=index * 0.2)
                for index, text in enumerate(scene.visual.bullets[:3])
            ]
            manifest["annotations"].append({"scene_id": scene.id, "layout": "feature_spotlight"})
            continue

    if not any(scene.visual.layout == "evidence_grid" for scene in storyboard.scenes):
        target = next(
            (
                scene
                for scene in storyboard.scenes[1:-1]
                if scene.visual.layout in {"stack", "steps", "feature_spotlight"} and scene.visual.asset_type == "none"
            ),
            None,
        )
        evidence_lines = _repo_evidence_lines(repo_summary, readme)
        if target and len(evidence_lines) >= 2:
            target.visual.layout = "evidence_grid"
            target.type = "evidence_grid"
            target.visual.headline = target.visual.headline or "Repo evidence"
            target.visual.bullets = evidence_lines[:3]
            target.visual.micro_beats = [
                MicroBeat(text=text[:36], kind="text", start_ratio=index * 0.16)
                for index, text in enumerate(evidence_lines[:3])
            ]
            manifest["annotations"].append({"scene_id": target.id, "layout": "evidence_grid"})


def _repo_evidence_lines(repo_summary: RepoSummary, readme: ReadmeEvidence) -> list[str]:
    lines: list[str] = []
    if readme.title:
        lines.append(readme.title)
    if readme.intro:
        lines.append(_compact_readme_intro(readme.intro) or readme.intro[:42])
    source_files = [file.path for file in repo_summary.files if file.role in {"entry", "source"}][:2]
    config_files = [file.path for file in repo_summary.files if file.role == "config"][:1]
    for path in [*source_files, *config_files]:
        lines.append(path)
    return [line for line in lines if line and not _is_setup_or_command(line)]


def _write_manifest(output_dir: Path, manifest: dict) -> None:
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "visual-assets-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sanitize_setup_visuals(storyboard: Storyboard) -> None:
    for scene in storyboard.scenes:
        visual = scene.visual
        if _is_setup_or_command(scene.narration):
            scene.narration = "打开项目后，可以体验它的核心功能。"
        if visual.focus_target == "install_command":
            visual.focus_target = "none"
        if visual.code and _is_setup_or_command(visual.code):
            visual.code = None

        visual.bullets = [item for item in visual.bullets if not _is_setup_or_command(item)]
        visual.micro_beats = [
            beat
            for beat in visual.micro_beats
            if not _is_setup_or_command(beat.text) and beat.kind != "code"
        ]

        if visual.layout == "readme_focus" and visual.code is None:
            visual.focus_target = "readme_section" if visual.focus_target == "none" else visual.focus_target
        if visual.layout == "code" and visual.code is None:
            visual.layout = "text"
            scene.type = "text"
            visual.focus_target = "none"
            if not visual.bullets:
                fallback = _strip_markdown(scene.narration)[:42]
                if _is_setup_or_command(fallback):
                    fallback = "打开项目后体验核心功能"
                visual.bullets = [fallback]
            if not visual.micro_beats:
                visual.micro_beats = [
                    MicroBeat(text=visual.bullets[0][:28], kind="text", start_ratio=0.0)
                ]


def _is_github_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com"


def _looks_like_command(line: str) -> bool:
    prefixes = (
        "$ ",
        "pip ",
        "python ",
        "streamlit ",
        "uvicorn ",
        "npm ",
        "pnpm ",
        "yarn ",
        "conda ",
        "docker ",
        "git clone",
    )
    return line.startswith(prefixes)


def _is_setup_or_command(text: str) -> bool:
    cleaned = text.strip().removeprefix("$ ").strip()
    return _looks_like_command(cleaned) or _looks_like_setup_text(cleaned)


def _extract_readme_highlight(line: str) -> str | None:
    if not line or _looks_like_setup_text(line) or _looks_like_command(line):
        return None
    if not line.startswith(("- ", "* ", "+ ")):
        return None
    cleaned = _strip_markdown(line[2:].strip())
    if not cleaned or _looks_like_setup_text(cleaned) or _looks_like_command(cleaned):
        return None
    if len(cleaned) < 8:
        return None
    return cleaned[:90]


def _looks_like_setup_text(text: str) -> bool:
    lowered = text.lower().strip()
    setup_keywords = (
        "install",
        "installation",
        "setup",
        "quickstart",
        "quick start",
        "requirements",
        "environment",
        "env",
        "conda",
        "pip ",
        "npm ",
        "pnpm ",
        "yarn ",
        "docker ",
        "venv",
        "配置环境",
        "环境安装",
        "安装",
        "命令",
        "运行命令",
        "启动命令",
    )
    return any(keyword in lowered for keyword in setup_keywords)


def _strip_markdown(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.strip("*_> ")
    return text[:160]


def _compact_readme_intro(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if "retrieval-augmented generation" in lowered or "rag" in lowered:
        if "paper" in lowered or "research" in lowered:
            return "本地 RAG 论文检索"
        return "本地 RAG 检索增强生成"
    return _strip_markdown(text)[:42]
