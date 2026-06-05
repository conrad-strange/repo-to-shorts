from gva.agents.storyboard_writer import normalize_storyboard_timing, sanitize_storyboard_payload
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def test_normalize_storyboard_timing_sets_sequential_starts() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="s1",
                type="title",
                start=10,
                duration=1,
                narration="A",
                visual=VisualSpec(layout="title", headline="A"),
            ),
            Scene(
                id="s2",
                type="text",
                start=10,
                duration=3,
                narration="B",
                visual=VisualSpec(layout="text", headline="B"),
            ),
        ],
    )
    normalized = normalize_storyboard_timing(storyboard)
    assert normalized.scenes[0].start == 0
    assert normalized.scenes[0].duration == 2.5
    assert normalized.scenes[1].start == 2.5


def test_sanitize_storyboard_payload_fixes_common_llm_shapes() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": 1,
                    "type": "title",
                    "visual": {
                        "layout": "title",
                        "headline": "Demo",
                        "bullets": None,
                        "diagram_nodes": None,
                    },
                }
            ],
        }
    )
    assert payload["scenes"][0]["id"] == "scene-001"
    assert payload["scenes"][0]["visual"]["bullets"] == []
    assert payload["scenes"][0]["visual"]["diagram_nodes"] == []


def test_sanitize_storyboard_payload_adds_micro_beats_from_bullets() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "flow",
                    "visual": {
                        "layout": "flow",
                        "headline": "Flow",
                        "bullets": ["Read repo", "Write script"],
                    },
                }
            ],
        }
    )

    beats = payload["scenes"][0]["visual"]["micro_beats"]
    assert beats[0]["text"] == "Read repo"
    assert beats[1]["start_ratio"] > beats[0]["start_ratio"]


def test_sanitize_storyboard_payload_removes_visible_direction_text() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "github_hero",
                    "visual": {
                        "layout": "github_hero",
                        "headline": "镜头聚焦GitHub仓库",
                        "caption": "文字弹出",
                        "bullets": ["克隆仓库动画", "文件列表展示"],
                        "micro_beats": [
                            {"text": "镜头聚焦GitHub仓库", "kind": "text"},
                            {"text": "文字弹出", "kind": "text"},
                        ],
                    },
                }
            ],
        }
    )

    visual = payload["scenes"][0]["visual"]
    assert visual["headline"] == "GitHub 仓库"
    assert visual["caption"] is None
    assert visual["bullets"] == ["克隆仓库", "文件列表"]
    assert [beat["text"] for beat in visual["micro_beats"]] == ["GitHub 仓库"]


def test_sanitize_storyboard_payload_normalizes_animation_aliases() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "hook",
                    "visual": {"layout": "repo_overview", "headline": "Demo", "animation": "fade_in"},
                },
                {
                    "id": "scene-002",
                    "type": "flow",
                    "visual": {"layout": "workflow", "headline": "Flow", "animation": "step_flow"},
                },
                {
                    "id": "scene-003",
                    "type": "cta",
                    "visual": {"layout": "ending", "headline": "Star", "animation": "bounce"},
                },
            ],
        }
    )

    storyboard = Storyboard.model_validate(payload)
    assert storyboard.scenes[0].visual.layout == "github_hero"
    assert storyboard.scenes[0].visual.animation == "fade"
    assert storyboard.scenes[1].visual.layout == "architecture_map"
    assert storyboard.scenes[1].visual.animation == "rise"
    assert storyboard.scenes[2].visual.layout == "cta"
    assert storyboard.scenes[2].visual.animation == "rise"


def test_sanitize_storyboard_payload_drops_invalid_captions_and_enums() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": ["bad"],
            "aspect_ratio": "vertical",
            "fps": "30",
            "width": "1080",
            "height": "1920",
            "scenes": [
                {
                    "id": "",
                    "type": 123,
                    "start": "oops",
                    "duration": "7.5",
                    "narration": 456,
                    "captions": ["missing timing"],
                    "evidence_refs": [1, "readme"],
                    "visual": {
                        "layout": "readme",
                        "headline": 789,
                        "bullets": [1, "RAG"],
                        "diagram_nodes": [{"bad": "shape"}, "Load docs"],
                        "icons": "github",
                        "micro_beats": [1, {"text": "Beat", "kind": "sparkle", "emphasis": 2}],
                        "caption": 321,
                        "code": ["line 1", "line 2"],
                        "accent_color": "blue",
                        "animation": "typewriter",
                        "asset_type": "github_repo",
                        "focus_target": "repo_title",
                        "asset_path": 42,
                    },
                }
            ],
        }
    )

    storyboard = Storyboard.model_validate(payload)
    scene = storyboard.scenes[0]
    assert scene.id == "scene-001"
    assert scene.start == 0
    assert scene.duration == 7.5
    assert scene.captions == []
    assert scene.evidence_refs == ["1", "readme"]
    assert scene.visual.layout == "readme_focus"
    assert scene.visual.bullets == ["1", "RAG"]
    assert scene.visual.diagram_nodes == ["Load docs"]
    assert scene.visual.icons == ["github"]
    assert scene.visual.code == "line 1\nline 2"
    assert scene.visual.accent_color == "#111827"
    assert scene.visual.animation == "rise"
    assert scene.visual.asset_type == "github_repo_home"
    assert scene.visual.focus_target == "repo_name"
    assert scene.visual.micro_beats[0].text == "1"
    assert scene.visual.micro_beats[1].kind == "text"


def test_sanitize_storyboard_payload_normalizes_readme_typo_and_warm_accent() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "readme_focus",
                    "narration": "READNE 来自仓库证据。",
                    "visual": {
                        "layout": "readme_focus",
                        "headline": "READNE 证据",
                        "bullets": ["Readne 摘要"],
                        "accent_color": "#FF6B6B",
                    },
                }
            ],
        }
    )

    storyboard = Storyboard.model_validate(payload)
    scene = storyboard.scenes[0]
    assert scene.narration == "README 来自仓库证据。"
    assert scene.visual.headline == "README 证据"
    assert scene.visual.bullets == ["README 摘要"]
    assert scene.visual.accent_color == "#58A6FF"


def test_sanitize_storyboard_payload_accepts_camel_case_scene_fields() -> None:
    payload = sanitize_storyboard_payload(
        {
            "title": "Demo",
            "scenes": [
                {
                    "id": "scene-001",
                    "type": "repo_overview",
                    "title": "Repo card",
                    "durationSec": "4",
                    "voiceover": "这是旁白。",
                    "items": ["README", "core files"],
                    "visual": {
                        "assetType": "github_repo",
                        "assetPath": "assets/github.png",
                        "focusTarget": "repo_title",
                        "repoUrl": "https://github.com/conrad-strange/rag-demo",
                        "repoDisplayUrl": "github.com/conrad-strange/rag-demo",
                        "codeSnippet": ["python app.py"],
                    },
                }
            ],
        }
    )

    storyboard = Storyboard.model_validate(payload)
    scene = storyboard.scenes[0]
    assert scene.duration == 4
    assert scene.narration == "这是旁白。"
    assert scene.visual.layout == "github_hero"
    assert scene.visual.headline == "Repo card"
    assert scene.visual.bullets == ["README", "core files"]
    assert scene.visual.asset_type == "github_repo_home"
    assert scene.visual.focus_target == "repo_name"
    assert scene.visual.repo_display_url == "github.com/conrad-strange/rag-demo"


def test_sanitize_storyboard_payload_accepts_nested_storyboard() -> None:
    payload = sanitize_storyboard_payload(
        {
            "storyboard": {
                "title": "Nested",
                "scenes": [
                    {
                        "id": "scene-001",
                        "type": "cta",
                        "duration": 3,
                        "narration": "去 GitHub 看代码。",
                        "visual": {"layout": "ending", "headline": "conrad-strange/rag-demo"},
                    }
                ],
            }
        }
    )

    storyboard = Storyboard.model_validate(payload)
    assert storyboard.title == "Nested"
    assert storyboard.scenes[0].visual.layout == "cta"
