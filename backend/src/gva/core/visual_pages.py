from __future__ import annotations

import json
import math
from pathlib import Path

from gva.core.visible_text import (
    clean_text_value,
    clean_visible_text,
    compact_visible_phrase,
    dedupe_visible_texts,
    looks_like_spoken_sentence,
    normalize_visible_key,
)
from gva.models.storyboard import Scene, Storyboard, VisualPage

STATIC_THRESHOLD_SECONDS = 1.5
PAGE_TRANSITION_SECONDS = 1.0
ITEM_REVEAL_GAP_SECONDS = 0.55
ITEM_REVEAL_DURATION_SECONDS = 0.45
MAX_ITEMS_PER_PAGE = 3
MIN_PAGE_SECONDS = 1.95
MIN_AUTO_PAGE_SCENE_SECONDS = 6.0


def apply_visual_pages(storyboard: Storyboard, output_dir: Path | None = None) -> Storyboard:
    """Attach scene-internal visual pages without changing narration or timing."""
    summaries: list[dict] = []
    for index, scene in enumerate(storyboard.scenes):
        existing_pages = scene.visual.visual_pages
        if existing_pages:
            scene.visual.visual_pages = _clean_pages(existing_pages)
            summaries.append(_scene_summary(scene, scene.visual.visual_pages, preserved=True))
            continue

        pages = build_visual_pages_for_scene(scene, scene_index=index)
        scene.visual.visual_pages = pages
        summaries.append(_scene_summary(scene, pages, preserved=False))

    if output_dir is not None:
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "visual-pages.json").write_text(
            json.dumps(
                {
                    "static_threshold_seconds": STATIC_THRESHOLD_SECONDS,
                    "page_transition_seconds": PAGE_TRANSITION_SECONDS,
                    "scenes": summaries,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return storyboard


def build_visual_pages_for_scene(scene: Scene, scene_index: int = 0) -> list[VisualPage]:
    duration = max(0.1, float(scene.duration or 0))
    if _is_edge_scene(scene_index, scene) or duration < MIN_AUTO_PAGE_SCENE_SECONDS:
        return []

    headline = _short_title(scene.visual.headline) or _short_title(scene.visual.caption) or "项目讲解"
    caption = _short_text(scene.visual.caption or "", 24) or None
    pool = _text_pool(scene)

    if not pool:
        pool = [text for text in [caption, headline] if text]
    if len(pool) <= MAX_ITEMS_PER_PAGE and duration < estimated_visual_page_seconds(len(pool)) + STATIC_THRESHOLD_SECONDS:
        return []

    target_seconds = estimated_visual_page_seconds(min(MAX_ITEMS_PER_PAGE, max(1, len(pool))))
    page_count = max(1, round(duration / target_seconds))
    page_count = min(page_count, _max_distinct_page_count(pool))
    if page_count <= 1:
        return []

    pages: list[VisualPage] = []
    for index in range(page_count):
        items = _page_items(pool, index, page_count)
        title = headline if index == 0 else _short_title(items[0] if items else headline)
        page_caption = caption if index == 0 else _short_text(items[1] if len(items) > 1 else caption or "", 24) or caption
        pages.append(VisualPage(title=title, caption=page_caption, items=items))
    return _clean_pages(pages)


def estimated_visual_page_seconds(item_count: int) -> float:
    count = max(1, min(MAX_ITEMS_PER_PAGE, item_count))
    last_reveal_end = ITEM_REVEAL_DURATION_SECONDS + ITEM_REVEAL_GAP_SECONDS * (count - 1)
    return max(MIN_PAGE_SECONDS, last_reveal_end + STATIC_THRESHOLD_SECONDS + PAGE_TRANSITION_SECONDS)


def _text_pool(scene: Scene) -> list[str]:
    visual = scene.visual
    values: list[str] = []
    if visual.layout in {"flow", "architecture_map"}:
        values.extend(visual.diagram_nodes)
    values.extend(_micro_beat_texts(scene))
    values.extend(visual.bullets)
    if visual.layout not in {"flow", "architecture_map"}:
        values.extend(visual.diagram_nodes)
    values.extend([visual.caption or "", visual.headline or ""])

    return _clean_pool(values)


def _micro_beat_texts(scene: Scene) -> list[str]:
    return [beat.text for beat in scene.visual.micro_beats if beat.text.strip()]


def _page_items(pool: list[str], page_index: int, page_count: int) -> list[str]:
    if not pool:
        return []
    if page_count <= 1:
        return pool[:MAX_ITEMS_PER_PAGE]
    start = math.floor(page_index * len(pool) / page_count)
    end = math.floor((page_index + 1) * len(pool) / page_count)
    items = pool[start:end]
    while len(items) < min(2, len(pool)):
        if start > 0:
            start -= 1
            items = [pool[start], *items]
        elif end < len(pool):
            items = [*items, pool[end]]
            end += 1
        else:
            break
    return dedupe_visible_texts(items)[:MAX_ITEMS_PER_PAGE]


def _short_title(text: str) -> str:
    return _short_text(text, 20)


def _short_text(text: str, limit: int) -> str:
    cleaned = clean_visible_text(clean_text_value(text)) or ""
    if len(cleaned) <= limit:
        return cleaned
    for separator in ["，", "。", "；", "、", ",", ";", " - ", " / ", "：", ":"]:
        if separator in cleaned:
            candidate = cleaned.split(separator, 1)[0].strip()
            if 4 <= len(candidate) <= limit:
                return candidate
    return cleaned[:limit].rstrip() + "..."


def _clean_pool(values: list[str]) -> list[str]:
    return dedupe_visible_texts(_short_visual_source(value) for value in values)


def _short_visual_source(value: str) -> str:
    text = _short_text(value, 28)
    if looks_like_spoken_sentence(text):
        return ""
    return text


def _max_distinct_page_count(pool: list[str]) -> int:
    if len(pool) <= MAX_ITEMS_PER_PAGE:
        return 1
    return max(1, math.ceil(len(pool) / 2))


def _clean_pages(pages: list[VisualPage]) -> list[VisualPage]:
    cleaned_pages: list[VisualPage] = []
    for page in pages:
        title = _compact_page_text(page.title, 24)
        caption = _compact_page_text(page.caption, 24)
        items = dedupe_visible_texts(_compact_page_text(item, 34) for item in page.items)
        if not title and items:
            title = items[0]
        if title or caption or items:
            cleaned_pages.append(VisualPage(title=title or "项目讲解", caption=caption, items=items))
    return _dedupe_pages(cleaned_pages)


def _compact_page_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    raw = clean_text_value(value)
    if looks_like_spoken_sentence(raw):
        compact = compact_visible_phrase(raw)
        if compact:
            return _short_text(compact, limit)
        return None
    text = _short_text(raw, limit)
    if text and not looks_like_spoken_sentence(text):
        return text
    compact = compact_visible_phrase(raw)
    if compact:
        return _short_text(compact, limit)
    return None


def _dedupe_pages(pages: list[VisualPage]) -> list[VisualPage]:
    seen: set[str] = set()
    result: list[VisualPage] = []
    for page in pages:
        normalized = normalize_visible_key("|".join([page.title, page.caption or "", *page.items]))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(page)
    return result


def _is_edge_scene(scene_index: int, scene: Scene) -> bool:
    return scene_index == 0 or scene.visual.layout == "cta" or scene.type == "cta"


def _scene_summary(scene: Scene, pages: list[VisualPage], preserved: bool) -> dict:
    page_seconds = round(float(scene.duration or 0) / max(1, len(pages)), 3)
    return {
        "scene_id": scene.id,
        "layout": scene.visual.layout,
        "duration": scene.duration,
        "page_count": len(pages),
        "page_seconds": page_seconds,
        "preserved": preserved,
        "titles": [page.title for page in pages],
    }
