from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gva.core.visible_text import (
    clean_text_value,
    clean_visible_text,
    compact_visible_phrase,
    looks_like_spoken_sentence,
    normalize_visible_key,
    text_repeats_narration,
)
from gva.models.storyboard import Scene, Storyboard, VisualPage


VISIBLE_TEXT_MAX_LENGTH = 56
SAFE_HEADLINE_FALLBACK = "项目讲解"
SAFE_CAPTION_FALLBACKS = {
    "github_hero": "项目概览",
    "hook": "项目概览",
    "readme_focus": "README 证据",
    "architecture_map": "核心流程",
    "flow": "核心流程",
    "evidence_grid": "可信证据",
    "feature_spotlight": "核心亮点",
    "stack": "技术栈",
    "steps": "使用方式",
    "code": "代码片段",
    "result_media": "真实画面",
    "cta": "GitHub",
}

class VisibleTextPolicyError(ValueError):
    pass


def apply_visible_text_policy(storyboard: Storyboard, output_dir: Path | None = None) -> Storyboard:
    """Keep narration out of non-subtitle visible UI and write a render manifest."""
    for scene in storyboard.scenes:
        _sanitize_scene(scene)

    manifest = build_visible_text_manifest(storyboard)
    issues = _visible_text_issues(manifest)
    if output_dir is not None:
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "visible-text-manifest.json").write_text(
            json.dumps({"issues": issues, "scenes": manifest}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if issues:
        summary = "; ".join(issue["message"] for issue in issues[:3])
        raise VisibleTextPolicyError(f"Visible text policy failed: {summary}")
    return storyboard


def build_visible_text_manifest(storyboard: Storyboard) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for scene in storyboard.scenes:
        entries: list[dict[str, Any]] = []
        narration = normalize_visible_key(scene.narration)

        def add(
            source: str,
            text: str | None,
            editable: bool,
            allowed_from_narration: bool = False,
            allow_long: bool = False,
        ) -> None:
            cleaned = clean_text_value(text)
            if not cleaned:
                return
            entries.append(
                {
                    "source": source,
                    "text": cleaned,
                    "editable": editable,
                    "allowed_from_narration": allowed_from_narration,
                    "overlaps_narration": (
                        bool(narration)
                        and not allowed_from_narration
                        and text_repeats_narration(cleaned, scene.narration)
                    ),
                    "too_long": not allowed_from_narration and not allow_long and len(cleaned) > VISIBLE_TEXT_MAX_LENGTH,
                }
            )

        add("visual.headline", scene.visual.headline, True)
        add("visual.caption", scene.visual.caption, True)
        for index, item in enumerate(scene.visual.bullets):
            add(f"visual.bullets[{index}]", item, True)
        for index, item in enumerate(scene.visual.diagram_nodes):
            add(f"visual.diagram_nodes[{index}]", item, True)
        for index, beat in enumerate(scene.visual.micro_beats):
            add(f"visual.micro_beats[{index}].text", beat.text, True)
            add(f"visual.micro_beats[{index}].emphasis", beat.emphasis, True)
        for page_index, page in enumerate(scene.visual.visual_pages):
            add(f"visual.visual_pages[{page_index}].title", page.title, True)
            add(f"visual.visual_pages[{page_index}].caption", page.caption, True)
            for item_index, item in enumerate(page.items):
                add(f"visual.visual_pages[{page_index}].items[{item_index}]", item, True)
        if scene.visual.code:
            add("visual.code", scene.visual.code, True, allow_long=True)
        for index, cue in enumerate(scene.captions):
            add(f"captions[{index}].text", cue.text, False, allowed_from_narration=True)

        scenes.append(
            {
                "scene_id": scene.id,
                "layout": scene.visual.layout,
                "narration_length": len(scene.narration or ""),
                "entries": entries,
            }
        )
    return scenes


def _sanitize_scene(scene: Scene) -> None:
    visual = scene.visual
    visual.headline = _safe_visible_text(visual.headline, scene, limit=36, fallback=_layout_fallback(scene))
    visual.caption = _safe_visible_text(visual.caption, scene, limit=18, fallback=None)
    visual.bullets = _safe_visible_list(visual.bullets, scene, limit=28)
    visual.diagram_nodes = _safe_visible_list(visual.diagram_nodes, scene, limit=42)

    cleaned_beats = []
    for beat in visual.micro_beats:
        text = _safe_visible_text(beat.text, scene, limit=28, fallback=None)
        if not text:
            continue
        emphasis = _safe_visible_text(beat.emphasis, scene, limit=24, fallback=None)
        cleaned_beats.append(beat.model_copy(update={"text": text, "emphasis": emphasis}))
    visual.micro_beats = cleaned_beats

    cleaned_pages: list[VisualPage] = []
    for page in visual.visual_pages:
        title = _safe_visible_text(page.title, scene, limit=28, fallback=None)
        caption = _safe_visible_text(page.caption, scene, limit=24, fallback=None)
        items = _safe_visible_list(page.items, scene, limit=34)
        if not title and items:
            title = items[0]
        if title or caption or items:
            cleaned_pages.append(VisualPage(title=title or _layout_fallback(scene), caption=caption, items=items))
    visual.visual_pages = _dedupe_pages(cleaned_pages)

    if not visual.caption:
        visual.caption = SAFE_CAPTION_FALLBACKS.get(visual.layout, None)


def _safe_visible_list(values: list[str], scene: Scene, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe_visible_text(value, scene, limit=limit, fallback=None)
        if not text:
            continue
        key = normalize_visible_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _safe_visible_text(value: object, scene: Scene, limit: int, fallback: str | None) -> str | None:
    cleaned = clean_visible_text(value)
    if not cleaned:
        return fallback
    if text_repeats_narration(cleaned, scene.narration) or looks_like_spoken_sentence(cleaned):
        compact = compact_visible_phrase(cleaned)
        if compact and not text_repeats_narration(compact, scene.narration):
            return _truncate(compact, limit)
        return fallback
    return _truncate(cleaned, limit)


def _visible_text_issues(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for scene in manifest:
        for entry in scene["entries"]:
            if entry["allowed_from_narration"]:
                continue
            if entry["overlaps_narration"]:
                issues.append(
                    {
                        "scene_id": scene["scene_id"],
                        "source": entry["source"],
                        "message": f"{scene['scene_id']} {entry['source']} repeats narration",
                        "text": entry["text"],
                    }
                )
            elif entry["too_long"]:
                issues.append(
                    {
                        "scene_id": scene["scene_id"],
                        "source": entry["source"],
                        "message": f"{scene['scene_id']} {entry['source']} is too long for visible UI",
                        "text": entry["text"],
                    }
                )
    return issues


def _layout_fallback(scene: Scene) -> str:
    return SAFE_CAPTION_FALLBACKS.get(scene.visual.layout, SAFE_HEADLINE_FALLBACK)


def _dedupe_pages(pages: list[VisualPage]) -> list[VisualPage]:
    seen: set[str] = set()
    result: list[VisualPage] = []
    for page in pages:
        key = normalize_visible_key("|".join([page.title, page.caption or "", *page.items]))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(page)
    return result


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    for separator in ("，", "。", "；", "、", ",", ";", " - ", " / ", "：", ":"):
        if separator in text:
            candidate = text.split(separator, 1)[0].strip()
            if 3 <= len(candidate) <= limit:
                return candidate
    return text[:limit].rstrip()
