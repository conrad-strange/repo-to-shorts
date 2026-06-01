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
