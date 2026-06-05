import json

import pytest

from gva.core.visual_pages import (
    PAGE_TRANSITION_SECONDS,
    STATIC_THRESHOLD_SECONDS,
    apply_visual_pages,
    estimated_visual_page_seconds,
)
from gva.models.storyboard import CaptionCue, Scene, Storyboard, VisualPage, VisualSpec


def test_long_scene_generates_multiple_visual_pages(tmp_path) -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-000",
                type="github_hero",
                start=0,
                duration=3,
                narration="Hook",
                visual=VisualSpec(layout="github_hero", headline="Hook"),
            ),
            Scene(
                id="scene-001",
                type="flow",
                start=3,
                duration=12,
                narration="先扫描仓库，再提取 README，然后生成分镜，最后渲染视频。",
                visual=VisualSpec(
                    layout="flow",
                    headline="工作流",
                    caption="分析到渲染",
                    diagram_nodes=["扫描仓库", "提取 README", "生成分镜"],
                ),
                captions=[
                    CaptionCue(start=0, end=2, text="先扫描仓库", source_scene_id="scene-001"),
                    CaptionCue(start=2, end=4, text="再提取 README", source_scene_id="scene-001"),
                    CaptionCue(start=4, end=6, text="然后生成分镜", source_scene_id="scene-001"),
                    CaptionCue(start=6, end=8, text="最后渲染视频", source_scene_id="scene-001"),
                ],
            )
        ],
    )

    apply_visual_pages(storyboard, output_dir=tmp_path)

    pages = storyboard.scenes[1].visual.visual_pages
    assert len(pages) >= 2
    assert storyboard.scenes[1].duration / len(pages) <= estimated_visual_page_seconds(3)
    assert (tmp_path / "logs" / "visual-pages.json").exists()
    manifest = json.loads((tmp_path / "logs" / "visual-pages.json").read_text(encoding="utf-8"))
    assert manifest["static_threshold_seconds"] == STATIC_THRESHOLD_SECONDS
    assert manifest["page_transition_seconds"] == PAGE_TRANSITION_SECONDS


def test_page_estimate_includes_transition_time() -> None:
    expected = 0.45 + 0.55 * 2 + STATIC_THRESHOLD_SECONDS + PAGE_TRANSITION_SECONDS
    assert estimated_visual_page_seconds(3) == pytest.approx(expected)


def test_opening_and_short_scenes_do_not_auto_page() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=3.8,
                narration="Hook",
                visual=VisualSpec(
                    layout="github_hero",
                    headline="做视频半天？",
                    micro_beats=[
                        {"text": "镜头聚焦GitHub仓库", "kind": "text", "start_ratio": 0.0},
                        {"text": "文字弹出", "kind": "text", "start_ratio": 0.18},
                    ],
                ),
            ),
            Scene(
                id="scene-002",
                type="architecture_map",
                start=3.8,
                duration=4.8,
                narration="短流程页",
                visual=VisualSpec(layout="architecture_map", headline="短流程", diagram_nodes=["提交 URL", "生成视频"]),
            ),
        ],
    )

    apply_visual_pages(storyboard)

    assert storyboard.scenes[0].visual.visual_pages == []
    assert storyboard.scenes[1].visual.visual_pages == []


def test_direction_words_are_removed_from_generated_pages() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=3,
                narration="Hook",
                visual=VisualSpec(layout="github_hero", headline="Hook"),
            ),
            Scene(
                id="scene-002",
                type="architecture_map",
                start=3,
                duration=9,
                narration="自动分析仓库，构建证据索引，再生成视频。",
                visual=VisualSpec(
                    layout="architecture_map",
                    headline="自动分析",
                    diagram_nodes=["镜头聚焦GitHub仓库", "克隆仓库动画", "文字弹出", "证据索引建成"],
                ),
            ),
        ],
    )

    apply_visual_pages(storyboard)

    visible = " ".join(
        " ".join([page.title, page.caption or "", *page.items])
        for page in storyboard.scenes[1].visual.visual_pages
    )
    assert "文字弹出" not in visible
    assert "镜头" not in visible
    assert "动画" not in visible
    assert "GitHub 仓库" in visible
    assert "克隆仓库" in visible


def test_existing_visual_pages_are_preserved() -> None:
    pages = [VisualPage(title="用户标题", caption="用户短句", items=["用户条目"])]
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="text",
                start=0,
                duration=9,
                narration="会生成很多自动分页。",
                visual=VisualSpec(layout="text", headline="原标题", visual_pages=pages),
            )
        ],
    )

    apply_visual_pages(storyboard)

    assert storyboard.scenes[0].visual.visual_pages == pages


def test_existing_visual_pages_are_cleaned_from_spoken_copy() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=12,
                narration="Demo",
                visual=VisualSpec(
                    layout="github_hero",
                    headline="Repo to Shorts",
                    visual_pages=[
                        VisualPage(
                            title="这个工具叫Repo to Shorts。",
                            caption="你只需要输入公开仓库的URL，它就会自动clone项目",
                            items=[
                                "这个工具叫Repo to Shorts。",
                                "你只需要输入公开仓库的URL，它就会自动clone项目",
                                "然后扫描Readme、配置文件、核心代码",
                            ],
                        )
                    ],
                ),
            )
        ],
    )

    apply_visual_pages(storyboard)

    visible = "\n".join(
        " ".join([page.title, page.caption or "", *page.items])
        for page in storyboard.scenes[0].visual.visual_pages
    )
    assert "这个工具叫" not in visible
    assert "你只需要" not in visible
    assert "它就会" not in visible
    assert "然后" not in visible
    assert "Repo to Shorts" in visible
    assert "输入 URL" in visible


def test_generated_pages_only_use_existing_visual_and_caption_text() -> None:
    allowed = {
        "核心流程",
        "可信亮点",
        "读取仓库",
        "分析 README",
        "生成中文讲稿",
        "渲染 9:16 视频",
    }
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="feature_spotlight",
                start=0,
                duration=7,
                narration="读取仓库，分析 README，生成中文讲稿，渲染 9:16 视频。",
                visual=VisualSpec(
                    layout="feature_spotlight",
                    headline="核心流程",
                    caption="可信亮点",
                    bullets=["读取仓库", "分析 README"],
                ),
                captions=[
                    CaptionCue(start=0, end=1.5, text="生成中文讲稿", source_scene_id="scene-001"),
                    CaptionCue(start=1.5, end=3, text="渲染 9:16 视频", source_scene_id="scene-001"),
                ],
            )
        ],
    )

    apply_visual_pages(storyboard)

    used = set()
    for page in storyboard.scenes[0].visual.visual_pages:
        used.add(page.title)
        if page.caption:
            used.add(page.caption)
        used.update(page.items)
    assert used <= allowed


def test_caption_narration_is_compacted_before_visible_pages() -> None:
    narration = "这个工具叫Repo to Shorts。你只需要输入公开仓库的URL，它就会自动clone项目，然后扫描Readme、配置文件、核心代码，构建成一个证据索引。"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-000",
                type="github_hero",
                start=0,
                duration=3,
                narration="Hook",
                visual=VisualSpec(layout="github_hero", headline="Hook"),
            ),
            Scene(
                id="scene-001",
                type="github_hero",
                start=3,
                duration=12,
                narration=narration,
                visual=VisualSpec(
                    layout="github_hero",
                    headline="Repo to Shorts",
                    caption="输入URL，自动扫描",
                    bullets=["Clone 仓库", "扫描 Readme/配置", "构建证据索引"],
                    micro_beats=[
                        {"text": "输入URL", "kind": "text", "start_ratio": 0.0},
                        {"text": "自动Clone", "kind": "text", "start_ratio": 0.18},
                        {"text": "扫描全项目", "kind": "text", "start_ratio": 0.36},
                        {"text": "构建证据索引", "kind": "text", "start_ratio": 0.54},
                    ],
                ),
                captions=[
                    CaptionCue(start=0, end=3, text="这个工具叫Repo to Shorts。", source_scene_id="scene-001"),
                    CaptionCue(start=3, end=7, text="你只需要输入公开仓库的URL，它就会自动clone项目。", source_scene_id="scene-001"),
                    CaptionCue(start=7, end=12, text="然后扫描Readme、配置文件、核心代码，构建成一个证据索引。", source_scene_id="scene-001"),
                ],
            )
        ],
    )

    apply_visual_pages(storyboard)

    pages = storyboard.scenes[1].visual.visual_pages
    assert 2 <= len(pages) <= 3
    page_signatures = {"|".join([page.title, page.caption or "", *page.items]) for page in pages}
    assert len(page_signatures) == len(pages)
    visible = "\n".join(page_signatures)
    assert "这个工具叫" not in visible
    assert "你只需要" not in visible
    assert "它就会" not in visible
    assert "然后" not in visible
    assert "输入URL" in visible
    assert "构建证据索引" in visible


def test_old_storyboard_without_visual_pages_validates() -> None:
    storyboard = Storyboard.model_validate(
        {
            "title": "Demo",
            "aspect_ratio": "9:16",
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "text",
                    "start": 0,
                    "duration": 3,
                    "narration": "Demo",
                    "visual": {"layout": "text", "headline": "Demo"},
                }
            ],
        }
    )

    assert storyboard.scenes[0].visual.visual_pages == []
