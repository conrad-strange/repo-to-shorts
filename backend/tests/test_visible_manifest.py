import json
from pathlib import Path

import pytest

from gva.config import Settings
from gva.core.render_bridge import prepare_remotion_public_assets
from gva.core.visible_manifest import VisibleTextPolicyError, apply_visible_text_policy
from gva.models.storyboard import CaptionCue, Scene, Storyboard, VisualPage, VisualSpec


def test_visible_policy_cleans_non_subtitle_spoken_copy(tmp_path: Path) -> None:
    narration = "这个工具叫Repo to Shorts。你只需要输入公开仓库的URL，它就会自动clone项目。"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=8,
                narration=narration,
                visual=VisualSpec(
                    layout="github_hero",
                    headline=narration,
                    caption=narration,
                    bullets=[narration, "文字弹出"],
                    micro_beats=[
                        {"text": narration, "kind": "text", "start_ratio": 0.0},
                    ],
                    visual_pages=[
                        VisualPage(title=narration, caption=narration, items=[narration]),
                    ],
                ),
                captions=[CaptionCue(start=0, end=8, text=narration, source_scene_id="scene-001")],
            )
        ],
    )

    apply_visible_text_policy(storyboard, output_dir=tmp_path)

    visible = " ".join(
        [
            storyboard.scenes[0].visual.headline,
            storyboard.scenes[0].visual.caption or "",
            *storyboard.scenes[0].visual.bullets,
            *(beat.text for beat in storyboard.scenes[0].visual.micro_beats),
            *(
                " ".join([page.title, page.caption or "", *page.items])
                for page in storyboard.scenes[0].visual.visual_pages
            ),
        ]
    )
    assert "这个工具叫" not in visible
    assert "你只需要" not in visible
    assert "它就会" not in visible
    assert storyboard.scenes[0].captions[0].text == narration

    manifest = json.loads((tmp_path / "logs" / "visible-text-manifest.json").read_text(encoding="utf-8"))
    assert manifest["issues"] == []
    caption_entries = [
        entry
        for scene in manifest["scenes"]
        for entry in scene["entries"]
        if entry["source"].startswith("captions[")
    ]
    assert caption_entries
    assert all(entry["allowed_from_narration"] for entry in caption_entries)


def test_visible_policy_fails_when_code_reuses_narration() -> None:
    narration = "这里展示项目中的一段关键代码或实际运行结果。"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="code",
                start=0,
                duration=5,
                narration=narration,
                visual=VisualSpec(layout="code", headline="代码", code=narration),
            )
        ],
    )

    with pytest.raises(VisibleTextPolicyError):
        apply_visible_text_policy(storyboard)


def test_visible_policy_compacts_github_urls_to_repo_handle() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=5,
                narration="项目地址看仓库名即可。",
                visual=VisualSpec(
                    layout="github_hero",
                    headline="https://github.com/conrad-strange/repo-to-shorts",
                    caption="github.com/conrad-strange/repo-to-shorts",
                    bullets=["查看 https://github.com/conrad-strange/repo-to-shorts/tree/main"],
                    visual_pages=[
                        VisualPage(
                            title="https://github.com/conrad-strange/repo-to-shorts.git",
                            caption="GitHub 仓库",
                            items=["github.com/conrad-strange/repo-to-shorts"],
                        )
                    ],
                ),
            )
        ],
    )

    apply_visible_text_policy(storyboard)

    visible = json.dumps(storyboard.model_dump(mode="json"), ensure_ascii=False)
    assert "https://github.com" not in visible
    assert "github.com/conrad-strange" not in visible
    assert "conrad-strange/repo-to-shorts" in visible


def test_render_bridge_writes_visible_text_manifest_and_clean_storyboard(tmp_path: Path) -> None:
    renderer_dir = tmp_path / "renderer"
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"fake audio")
    narration = "这个工具叫Repo to Shorts。你只需要输入公开仓库的URL，它就会自动clone项目。"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=8,
                narration=narration,
                visual=VisualSpec(layout="github_hero", headline=narration, caption=narration),
            )
        ],
    )

    prepare_remotion_public_assets(
        output_dir=tmp_path,
        renderer_dir=renderer_dir,
        storyboard=storyboard,
        audio_path=audio_path,
        settings=Settings(_env_file=None, renderer_dir=renderer_dir),
    )

    public_storyboard = json.loads((renderer_dir / "public" / "generated" / "storyboard.json").read_text(encoding="utf-8"))
    visible = json.dumps(public_storyboard["scenes"][0]["visual"], ensure_ascii=False)
    assert "你只需要" not in visible
    assert (tmp_path / "logs" / "visible-text-manifest.json").exists()
