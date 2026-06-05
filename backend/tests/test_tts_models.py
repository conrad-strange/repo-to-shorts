from pathlib import Path

import pytest
from edge_tts.exceptions import NoAudioReceived

from gva.core import tts as tts_core
from gva.core.tts import _adjusted_scene_duration, _fit_scene_audio_durations_for_video_mode
from gva.models.storyboard import Scene, Storyboard, VisualSpec
from gva.models.tts import TimingAdjustmentLog, TtsManifest
from gva.models.tts import TtsSceneAudio


def test_tts_manifest_model_accepts_empty_scene_list() -> None:
    manifest = TtsManifest(
        voice="zh-CN-XiaoxiaoNeural",
        rate="+25%",
        full_audio_path=Path("voice.mp3"),
        full_audio_duration_seconds=1.2,
    )
    assert manifest.provider == "edge"
    assert manifest.rate == "+25%"


def test_timing_adjustment_log_model() -> None:
    log = TimingAdjustmentLog(
        storyboard_path=Path("storyboard.json"),
        timed_storyboard_path=Path("storyboard-timed.json"),
        tts_manifest_path=Path("tts-manifest.json"),
        original_total_duration_seconds=10,
        adjusted_total_duration_seconds=12,
        method="test",
    )
    assert log.adjusted_total_duration_seconds == 12


def test_timing_never_shorter_than_scene_audio() -> None:
    assert _adjusted_scene_duration(scene_index=1, original_duration=3.5, audio_duration=5.17) == 5.32
    assert _adjusted_scene_duration(scene_index=2, original_duration=5, audio_duration=5.17) == 5.62
    assert _adjusted_scene_duration(scene_index=4, original_duration=4.25, audio_duration=3.8, scene_layout="cta") == 4.15
    assert _adjusted_scene_duration(scene_index=2, original_duration=18, audio_duration=5.17) == 5.97


def test_timing_pads_technical_mode_without_extending_hook_or_cta() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=3.8,
                narration="Hook",
                visual=VisualSpec(layout="github_hero", headline="Hook"),
            ),
            Scene(
                id="scene-002",
                type="flow",
                start=3.8,
                duration=10,
                narration="Flow",
                visual=VisualSpec(layout="flow", headline="Flow"),
            ),
            Scene(
                id="scene-003",
                type="readme_focus",
                start=13.8,
                duration=10,
                narration="Readme",
                visual=VisualSpec(layout="readme_focus", headline="README"),
            ),
            Scene(
                id="scene-004",
                type="cta",
                start=23.8,
                duration=5,
                narration="CTA",
                visual=VisualSpec(layout="cta", headline="CTA"),
            ),
        ],
    )
    items = [
        _tts_item("scene-001", audio=3.2, adjusted=3.5),
        _tts_item("scene-002", audio=5.0, adjusted=5.8),
        _tts_item("scene-003", audio=5.0, adjusted=5.8),
        _tts_item("scene-004", audio=4.0, adjusted=4.35),
    ]

    changed = _fit_scene_audio_durations_for_video_mode(items, storyboard, "technical_90s")

    assert changed
    assert round(sum(item.adjusted_scene_duration_seconds for item in items), 2) == 90.0
    assert items[0].adjusted_scene_duration_seconds == 3.5
    assert items[-1].adjusted_scene_duration_seconds == 4.35
    assert items[1].adjusted_scene_duration_seconds > 30
    assert items[2].adjusted_scene_duration_seconds > 30


def test_edge_tts_retry_recovers_from_no_audio(tmp_path, monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeCommunicate:
        def __init__(self, **_kwargs):
            pass

        async def save(self, path: str) -> None:
            attempts["count"] += 1
            target = Path(path)
            if attempts["count"] < 3:
                target.write_bytes(b"partial")
                raise NoAudioReceived("no audio")
            target.write_bytes(b"x" * 600)

    monkeypatch.setattr(tts_core.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(tts_core.time, "sleep", lambda _seconds: None)

    output = tmp_path / "voice.mp3"
    tts_core._synthesize_edge_tts("你好", output, "zh-CN-XiaoxiaoNeural", "+32%")

    assert attempts["count"] == 3
    assert output.stat().st_size == 600


def test_edge_tts_retry_cleans_partial_file_after_final_failure(tmp_path, monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeCommunicate:
        def __init__(self, **_kwargs):
            pass

        async def save(self, path: str) -> None:
            attempts["count"] += 1
            Path(path).write_bytes(b"partial")
            raise NoAudioReceived("no audio")

    monkeypatch.setattr(tts_core.edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr(tts_core.time, "sleep", lambda _seconds: None)

    output = tmp_path / "voice.mp3"
    with pytest.raises(NoAudioReceived):
        tts_core._synthesize_edge_tts("你好", output, "zh-CN-XiaoxiaoNeural", "+32%")

    assert attempts["count"] == tts_core.EDGE_TTS_MAX_ATTEMPTS
    assert not output.exists()


def _tts_item(scene_id: str, audio: float, adjusted: float) -> TtsSceneAudio:
    return TtsSceneAudio(
        scene_id=scene_id,
        narration=scene_id,
        audio_path=Path(f"{scene_id}.mp3"),
        duration_seconds=audio,
        original_scene_duration_seconds=adjusted,
        adjusted_scene_duration_seconds=adjusted,
    )
