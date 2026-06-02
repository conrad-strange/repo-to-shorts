from pathlib import Path

from gva.core.tts import _adjusted_scene_duration
from gva.models.tts import TimingAdjustmentLog, TtsManifest


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
    assert _adjusted_scene_duration(scene_index=4, original_duration=4.25, audio_duration=3.8, scene_layout="cta") == 3.95
