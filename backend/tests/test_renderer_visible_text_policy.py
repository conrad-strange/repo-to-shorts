from pathlib import Path


def test_scene_templates_do_not_use_narration_as_visible_copy() -> None:
    scenes_dir = Path(__file__).resolve().parents[2] / "renderer" / "src" / "scenes"
    offenders = []
    for path in scenes_dir.glob("*.tsx"):
        if path.name == "SubtitleOverlay.tsx":
            continue
        text = path.read_text(encoding="utf-8")
        if "scene.narration" in text:
            offenders.append(path.name)

    assert offenders == []
