from __future__ import annotations

import json
import html
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from gva.config import Settings
from gva.core.render_bridge import find_browser
from gva.core.visible_text import clean_visible_text, clean_visible_text_list, compact_github_repo_handle
from gva.models.repo import RepoSummary
from gva.models.storyboard import MicroBeat, Scene, Storyboard


MIN_GITHUB_SCREENSHOT_BYTES = 40_000
LAYOUT_MOTION_ASSETS = {
    "hook": "repo_pulse",
    "github_hero": "repo_pulse",
    "architecture_map": "data_flow",
    "flow": "data_flow",
    "code": "code_scan",
    "readme_focus": "evidence_pulse",
    "evidence_grid": "evidence_pulse",
    "feature_spotlight": "evidence_pulse",
    "stack": "data_flow",
    "steps": "data_flow",
    "title": "evidence_pulse",
    "text": "evidence_pulse",
    "cta": "spark_burst",
}
LAYOUT_MOTION_DELAYS = {
    "hook": 0.5,
    "github_hero": 0.52,
    "cta": 0.46,
    "code": 0.62,
    "architecture_map": 0.6,
    "flow": 0.6,
}


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
    """Prepare repo-sourced assets and make scenes more video-friendly."""
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
    if public_screenshot_path is None:
        _clear_github_screenshot_asset(enhanced, manifest)

    readme = extract_readme_evidence(repo_summary)
    manifest["readme"] = {
        "title": readme.title,
        "intro": readme.intro,
        "highlights": readme.highlights[:3],
        "section_count": len(readme.sections),
    }

    _strengthen_hook_scene(enhanced, repo_summary, readme, repo_url, manifest)
    if public_screenshot_path:
        _annotate_github_hero(enhanced, public_screenshot_path, repo_url, manifest)
    if readme.title or readme.intro or readme.highlights or readme.sections:
        _annotate_readme_focus(enhanced, readme, manifest)
    _enrich_scene_layouts(enhanced, repo_summary, readme, manifest)
    _annotate_cta_repo_identity(enhanced, repo_url, manifest)
    _assign_motion_assets(enhanced, manifest)
    _compact_visual_language(enhanced)

    _write_manifest(output_dir, manifest)
    return enhanced


def extract_readme_evidence(repo_summary: RepoSummary) -> ReadmeEvidence:
    readme_file = next((file for file in repo_summary.files if file.role == "readme"), None)
    if readme_file is None:
        return ReadmeEvidence()

    lines = [line.rstrip() for line in readme_file.excerpt.splitlines()]
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
        html_heading = _extract_html_heading(stripped)
        if html_heading:
            level, heading = html_heading
            if level == 1 and not title:
                title = heading
            elif heading and not _looks_like_setup_text(heading) and not _is_generic_readme_heading(heading):
                sections.append(heading)
            continue

        if stripped.startswith("##"):
            section = _strip_markdown(stripped.lstrip("#").strip())
            if section and not _looks_like_setup_text(section) and not _is_generic_readme_heading(section):
                sections.append(section)
            continue

        if stripped.startswith("#") and not title:
            title = _strip_markdown(stripped.lstrip("#").strip())
            continue

        highlight = _extract_readme_highlight(stripped)
        if highlight and highlight not in highlights:
            highlights.append(highlight)

        if not intro and stripped and not stripped.startswith("#") and not stripped.startswith(("!", "[")):
            candidate = _strip_markdown(stripped)
            if (
                candidate
                and not _looks_like_setup_text(candidate)
                and not _looks_like_command(candidate)
                and not _is_generic_readme_heading(candidate)
            ):
                intro = candidate

    return ReadmeEvidence(title=title, intro=intro, highlights=highlights[:5], sections=sections[:8])


def _capture_github_repo_screenshot(
    repo_url: str,
    output_path: Path,
    public_path: Path,
    settings: Settings,
) -> dict:
    browser = find_browser(settings)
    if browser is None:
        return {"status": "failed", "reason": "BROWSER_EXE/CHROME_EXE is not configured, and Chrome/Edge was not found"}
    if not _is_github_url(repo_url):
        return {"status": "failed", "reason": "repo_url is not a GitHub URL"}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    command = [
        str(browser),
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
            "reason": (result.stderr or result.stdout or "Browser screenshot failed").strip()[:500],
        }

    quality_issue = _github_screenshot_quality_issue(output_path)
    if quality_issue:
        output_path.unlink(missing_ok=True)
        return {
            "status": "failed",
            "reason": quality_issue,
        }

    shutil.copyfile(output_path, public_path)
    return {
        "status": "ok",
        "output_path": str(output_path),
        "public_path": str(public_path),
        "public_src": "generated/assets/github-repo-home.png",
        "browser_path": str(browser),
    }


def _use_cached_github_screenshot(result: dict, output_path: Path, public_path: Path) -> dict:
    if public_path.exists():
        public_issue = _github_screenshot_quality_issue(public_path)
        if public_issue:
            result = {
                **result,
                "reason": f"{result.get('reason', 'screenshot refresh failed')}; cached public rejected: {public_issue}",
            }
        else:
            return {
                "status": "cached",
                "reason": result.get("reason", "screenshot refresh failed"),
                "output_path": str(output_path) if output_path.exists() else None,
                "public_path": str(public_path),
                "public_src": "generated/assets/github-repo-home.png",
            }
    if output_path.exists():
        output_issue = _github_screenshot_quality_issue(output_path)
        if output_issue:
            result = {
                **result,
                "reason": f"{result.get('reason', 'screenshot refresh failed')}; cached output rejected: {output_issue}",
            }
        else:
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


def _github_screenshot_quality_issue(path: Path) -> str | None:
    """Reject tiny Chrome screenshots that are usually timeout or blank error pages."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return f"screenshot stat failed: {exc}"
    if size < MIN_GITHUB_SCREENSHOT_BYTES:
        return f"screenshot looks like an error page or blank capture ({size} bytes)"
    width, height = _png_dimensions(path)
    if width is not None and height is not None and (width < 800 or height < 600):
        return f"screenshot dimensions are too small ({width}x{height})"
    return None


def _png_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as file:
            header = file.read(24)
    except OSError:
        return None, None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None, None
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def _clear_github_screenshot_asset(storyboard: Storyboard, manifest: dict) -> None:
    for scene in storyboard.scenes:
        visual = scene.visual
        if visual.asset_type != "github_repo_home" and visual.asset_path != "generated/assets/github-repo-home.png":
            continue
        visual.asset_type = "none"
        visual.asset_path = None
        manifest["annotations"].append({"scene_id": scene.id, "asset_type": "github_repo_home_rejected"})


def _strengthen_hook_scene(
    storyboard: Storyboard,
    repo_summary: RepoSummary,
    readme: ReadmeEvidence,
    repo_url: str | None,
    manifest: dict,
) -> None:
    if not storyboard.scenes:
        return
    scene = storyboard.scenes[0]
    text_blob = " ".join([readme.title or "", readme.intro or "", *readme.highlights]).lower()
    repo_handle = _repo_handle(repo_url) or repo_summary.repo_name

    if "rag" in text_blob and any(word in text_blob for word in ["paper", "research", "论文"]):
        scene.visual.headline = "论文太多？\nRAG 找答案"
        scene.narration = "几十篇论文看不完？这个本地 RAG 项目帮你定位相关段落，快速找到答案线索。"
        scene.visual.caption = "本地 RAG 论文问答"
        scene.visual.bullets = ["论文检索", "本地 RAG", "相关段落"]
        scene.visual.micro_beats = [
            MicroBeat(text="几十篇论文", kind="warning", start_ratio=0.0),
            MicroBeat(text="本地 RAG", kind="text", emphasis="RAG", start_ratio=0.32),
            MicroBeat(text="定位答案", kind="metric", start_ratio=0.62),
        ]
    elif "video" in text_blob or "remotion" in text_blob:
        scene.visual.headline = "项目没人看？\n先生成讲解视频"
        scene.narration = "GitHub 项目发布后没人理解？这个工具把代码仓库转成中文竖屏讲解视频。"
        scene.visual.caption = "仓库到短视频"
        scene.visual.bullets = ["读取仓库", "生成分镜", "渲染视频"]
        scene.visual.micro_beats = [
            MicroBeat(text="读取仓库", kind="text", start_ratio=0.0),
            MicroBeat(text="中文讲解", kind="text", start_ratio=0.32),
            MicroBeat(text="竖屏 MP4", kind="metric", start_ratio=0.62),
        ]
    elif len(_strip_markdown(scene.visual.headline)) > 24 or _looks_abstract_hook(scene.visual.headline):
        scene.visual.headline = f"{repo_handle}\n解决什么问题？"
        scene.visual.caption = "先看核心价值"
        scene.visual.bullets = [repo_summary.repo_name, *(repo_summary.detected_stack[:2])]

    manifest["annotations"].append({"scene_id": scene.id, "layout": "stronger_hook"})


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
        return compact_github_repo_handle(repo_url)
    return repo_url.removeprefix("https://").removeprefix("http://").rstrip("/")


def _repo_handle(repo_url: str | None) -> str | None:
    return compact_github_repo_handle(repo_url) or _display_repo_url(repo_url)


def _annotate_cta_repo_identity(storyboard: Storyboard, repo_url: str | None, manifest: dict) -> None:
    handle = _repo_handle(repo_url)
    if not handle:
        return
    scene = next(
        (item for item in reversed(storyboard.scenes) if item.visual.layout == "cta" or item.type == "cta"),
        None,
    )
    if scene is None:
        return
    scene.visual.layout = "cta"
    scene.visual.repo_url = repo_url
    scene.visual.repo_display_url = handle
    scene.visual.headline = handle
    scene.visual.bullets = ["查看代码", "阅读 README", "欢迎 Star"]
    scene.visual.caption = "开源项目"
    scene.visual.micro_beats = [
        MicroBeat(text=handle, kind="cta", emphasis="GitHub", start_ratio=0.0),
        MicroBeat(text="查看代码", kind="cta", start_ratio=0.28),
        MicroBeat(text="欢迎 Star", kind="cta", start_ratio=0.56),
    ]
    manifest["annotations"].append(
        {
            "scene_id": scene.id,
            "asset_type": "cta_repo_identity",
            "repo_display_url": handle,
        }
    )


def _assign_motion_assets(storyboard: Storyboard, manifest: dict) -> None:
    for scene in storyboard.scenes:
        visual = scene.visual
        if visual.motion_asset != "none" or visual.layout == "result_media":
            continue
        if scene.duration < 4 and visual.layout not in {"hook", "github_hero", "cta"}:
            continue
        asset = LAYOUT_MOTION_ASSETS.get(visual.layout)
        if not asset:
            continue
        visual.motion_asset = asset
        visual.motion_delay_ratio = LAYOUT_MOTION_DELAYS.get(visual.layout, 0.58)
        manifest["annotations"].append(
            {
                "scene_id": scene.id,
                "motion_asset": asset,
                "motion_delay_ratio": visual.motion_delay_ratio,
            }
        )


def _annotate_readme_focus(storyboard: Storyboard, readme: ReadmeEvidence, manifest: dict) -> None:
    scene = next((item for item in storyboard.scenes[1:] if item.visual.layout == "readme_focus"), None)
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
    scene.visual.headline = "README 证据"
    bullets = [item for item in [readme.title, _compact_readme_intro(readme.intro)] if item]
    bullets.extend(readme.highlights[: 3 - len(bullets)])
    if len(bullets) < 3:
        bullets.extend(readme.sections[: 3 - len(bullets)])
    if bullets:
        scene.visual.bullets = bullets[:3]
    scene.visual.code = None
    scene.visual.micro_beats = [
        MicroBeat(text=_short_phrase(text, 28), kind="text", start_ratio=index * 0.22)
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
            scene.visual.diagram_nodes = _enrich_flow_nodes(scene.visual.diagram_nodes)
            manifest["annotations"].append({"scene_id": scene.id, "layout": "architecture_map"})
            continue

        if scene.visual.layout in {"title", "text"} and len(scene.visual.bullets) >= 2:
            scene.visual.layout = "feature_spotlight"
            scene.type = "feature_spotlight"
            scene.visual.micro_beats = [
                MicroBeat(text=_short_phrase(text, 24), kind="text", start_ratio=index * 0.2)
                for index, text in enumerate(scene.visual.bullets[:3])
            ]
            manifest["annotations"].append({"scene_id": scene.id, "layout": "feature_spotlight"})
            continue

    if not any(scene.visual.layout == "evidence_grid" for scene in storyboard.scenes):
        target = next(
            (
                scene
                for scene in storyboard.scenes[1:-1]
                if scene.visual.layout in {"stack", "steps"} and scene.visual.asset_type == "none"
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
                MicroBeat(text=_short_phrase(text, 28), kind="text", start_ratio=index * 0.16)
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


def _compact_visual_language(storyboard: Storyboard) -> None:
    for scene in storyboard.scenes:
        scene.visual.headline = clean_visible_text(_short_headline(scene.visual.headline), limit=18) or _caption_fallback(scene) or "项目讲解"
        scene.visual.caption = clean_visible_text(_short_caption(scene), limit=14) if _short_caption(scene) else None
        scene.visual.bullets = clean_visible_text_list([_short_phrase(item, 24) for item in scene.visual.bullets[:3]], limit=24)
        scene.visual.diagram_nodes = clean_visible_text_list(scene.visual.diagram_nodes[:6], limit=42)
        cleaned_beats = []
        for beat in (scene.visual.micro_beats or [])[:4]:
            text = clean_visible_text(_short_phrase(_viewer_facing_beat_text(beat.text), 24), limit=24)
            if text:
                cleaned_beats.append(beat.model_copy(update={"text": text}))
        scene.visual.micro_beats = cleaned_beats
        if scene.visual.code:
            lines = [line[:80] for line in scene.visual.code.splitlines()[:8]]
            scene.visual.code = "\n".join(lines)


def _short_caption(scene: Scene) -> str | None:
    caption = _strip_markdown(scene.visual.caption or "")
    narration = _strip_markdown(scene.narration)
    if not caption:
        return None
    if _visual_text_repeats_narration(caption, narration) or len(caption) > 18:
        return _caption_fallback(scene)
    return _short_phrase(caption, 14)


def _visual_text_repeats_narration(text: str, narration: str) -> bool:
    cleaned = _normalize_for_overlap(text)
    spoken = _normalize_for_overlap(narration)
    if not cleaned or not spoken:
        return False
    return len(cleaned) >= 12 and (cleaned in spoken or spoken.startswith(cleaned))


def _caption_fallback(scene: Scene) -> str | None:
    layout = scene.visual.layout
    headline = _strip_markdown(scene.visual.headline)
    bullets = [_strip_markdown(item) for item in scene.visual.bullets if _strip_markdown(item)]
    joined = " ".join([headline, *bullets]).lower()
    if layout in {"hook", "github_hero"}:
        if "github" in joined and "视频" in joined:
            return "仓库到短视频"
        if "readme" in joined:
            return "README 变短片"
        return "先看核心价值"
    if layout == "readme_focus":
        return "README 证据"
    if layout in {"architecture_map", "flow"}:
        return "流程一眼看懂"
    if layout == "evidence_grid":
        return "证据先说话"
    if layout in {"feature_spotlight", "stack", "steps"}:
        return "核心亮点"
    if layout == "code":
        return "真实代码片段"
    if layout == "result_media":
        return "真实使用画面"
    if layout == "cta":
        return "查看 GitHub"
    if bullets:
        return _short_phrase(bullets[0], 14)
    return None


def _normalize_for_overlap(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)


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
        if _is_setup_narration(scene.narration):
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
                    fallback = "体验核心功能"
                visual.bullets = [fallback]
            if not visual.micro_beats:
                visual.micro_beats = [MicroBeat(text=visual.bullets[0][:28], kind="text", start_ratio=0.0)]


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


def _is_setup_narration(text: str) -> bool:
    cleaned = text.strip().removeprefix("$ ").strip()
    lowered = cleaned.lower()
    if not cleaned:
        return False
    if _looks_like_command(cleaned):
        return True
    if re.search(r"\b(?:pip|npm|pnpm|yarn|conda|docker)\s+(?:install|run|start|build|create|activate)\b", lowered):
        return True
    if re.search(r"\b(?:git\s+clone|streamlit\s+run)\b", lowered):
        return True
    starts_like_setup = cleaned.startswith(("先运行", "运行", "执行", "输入", "安装", "配置", "启动", "设置"))
    return starts_like_setup and _looks_like_setup_text(cleaned)


def _extract_readme_highlight(line: str) -> str | None:
    if not line or _looks_like_setup_text(line) or _looks_like_command(line):
        return None
    is_list_item = line.startswith(("- ", "* ", "+ "))
    is_table_label = bool(re.search(r"<td>\s*<strong>", line, re.I))
    if not is_list_item and not is_table_label:
        return None
    raw = line[2:].strip() if is_list_item else line
    cleaned = _strip_markdown(raw)
    if (
        not cleaned
        or _looks_like_setup_text(cleaned)
        or _looks_like_command(cleaned)
        or _is_generic_readme_heading(cleaned)
    ):
        return None
    if len(cleaned) < 2:
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
    text = html.unescape(text)
    text = re.sub(r"<img\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"</?(?:h[1-6]|p|div|span|table|thead|tbody|tr|td|th|strong|em|br|center)[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip("*_>|- ")[:160]


def _viewer_facing_beat_text(text: str) -> str:
    replacements = {
        "爆点开场": "真实仓库",
        "hook": "看点",
        "Hook": "看点",
    }
    cleaned = text.strip()
    return replacements.get(cleaned, cleaned)


def _extract_html_heading(text: str) -> tuple[int, str] | None:
    match = re.match(r"<h([1-6])\b[^>]*>(.*?)</h\1>", text.strip(), re.I | re.S)
    if not match:
        return None
    heading = _strip_markdown(match.group(2))
    return int(match.group(1)), heading


def _is_generic_readme_heading(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text.lower()).strip()
    normalized = re.sub(r"^\d+\s+", "", normalized)
    generic = {
        "what it does",
        "features",
        "quick start",
        "quickstart",
        "usage",
        "demo",
        "roadmap",
        "license",
        "examples",
        "installation",
        "requirements",
        "project structure",
        "python",
        "llm provider",
        "web ui",
        "cli",
        "output",
        "功能特点",
        "快速开始",
        "使用方式",
        "项目路线",
        "许可证",
    }
    return normalized in generic


def _compact_readme_intro(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if "retrieval-augmented generation" in lowered or "rag" in lowered:
        if "paper" in lowered or "research" in lowered or "论文" in lowered:
            return "本地 RAG 论文检索"
        return "本地 RAG 检索增强"
    return _short_phrase(_strip_markdown(text), 30)


def _enrich_flow_nodes(nodes: list[str]) -> list[str]:
    fallback_notes = ["输入", "处理", "索引", "检索", "输出"]
    enriched: list[str] = []
    for index, node in enumerate(nodes[:5]):
        if "：" in node or ":" in node or "\n" in node:
            enriched.append(node)
            continue
        note = fallback_notes[min(index, len(fallback_notes) - 1)]
        lowered = node.lower()
        if "pdf" in lowered or "文档" in node or "读取" in node:
            note = "PDF / Markdown"
        elif "分块" in node or "chunk" in lowered:
            note = "保留上下文"
        elif "faiss" in lowered or "向量" in node or "索引" in node:
            note = "向量索引"
        elif "bm25" in lowered or "检索" in node:
            note = "召回相关内容"
        elif "llm" in lowered or "答案" in node or "生成" in node:
            note = "答案 + 来源"
        enriched.append(f"{node}：{note}")
    return enriched


def _short_headline(text: str) -> str:
    stripped = _strip_markdown(text).strip()
    if "\n" in stripped:
        return "\n".join(_short_phrase(part, 14) for part in stripped.splitlines()[:2])
    return _short_phrase(stripped, 18)


def _short_phrase(text: str, limit: int) -> str:
    cleaned = _strip_markdown(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= limit:
        return cleaned
    separators = ["，", "。", "；", "、", ",", ";", " - ", " — ", " / "]
    for separator in separators:
        if separator in cleaned:
            candidate = cleaned.split(separator, 1)[0].strip()
            if 4 <= len(candidate) <= limit:
                return candidate
    return cleaned[:limit].rstrip() + "…"


def _looks_abstract_hook(text: str) -> bool:
    lowered = text.lower()
    abstract_words = ("关键信息", "快速了解", "项目介绍", "看懂项目", "效率工具")
    return any(word in lowered for word in abstract_words)
