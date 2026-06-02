from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts
from mutagen import File as MutagenFile

from gva.config import Settings
from gva.models.storyboard import Storyboard
from gva.models.tts import TimingAdjustmentLog, TtsManifest, TtsSceneAudio


def run_tts_timing(
    storyboard: Storyboard,
    output_dir: Path,
    settings: Settings,
) -> tuple[Storyboard, TtsManifest, TimingAdjustmentLog]:
    if settings.tts_provider != "edge":
        raise ValueError("Only edge TTS is implemented in the MVP.")

    logs_dir = output_dir / "logs"
    audio_dir = output_dir / "audio" / "scenes"
    logs_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    tts_input_path = logs_dir / "tts-input.json"
    tts_input_path.write_text(
        json.dumps(
            {
                "provider": settings.tts_provider,
                "voice": settings.tts_voice,
                "rate": settings.tts_rate,
                "scene_count": len(storyboard.scenes),
                "scenes": [
                    {
                        "scene_id": scene.id,
                        "narration": scene.narration,
                        "original_duration_seconds": scene.duration,
                    }
                    for scene in storyboard.scenes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    scene_audio_items: list[TtsSceneAudio] = []
    for index, scene in enumerate(storyboard.scenes, start=1):
        audio_path = audio_dir / f"{index:02d}-{scene.id}.mp3"
        _synthesize_edge_tts(scene.narration, audio_path, settings.tts_voice, settings.tts_rate)
        audio_duration = _audio_duration(audio_path)
        adjusted_duration = _adjusted_scene_duration(
            scene_index=index,
            original_duration=scene.duration,
            audio_duration=audio_duration,
            scene_layout=scene.visual.layout,
        )
        scene_audio_items.append(
            TtsSceneAudio(
                scene_id=scene.id,
                narration=scene.narration,
                audio_path=audio_path,
                duration_seconds=round(audio_duration, 2),
                original_scene_duration_seconds=scene.duration,
                adjusted_scene_duration_seconds=adjusted_duration,
            )
        )

    full_audio_path = output_dir / "audio" / "voice.mp3"
    _concat_mp3_bytes([item.audio_path for item in scene_audio_items], full_audio_path)
    normalized_audio_path = output_dir / "audio" / "voice-normalized.mp3"
    if _normalize_audio(full_audio_path, normalized_audio_path, settings.ffmpeg_exe):
        full_audio_path = normalized_audio_path
    full_audio_duration = _audio_duration(full_audio_path)

    timed_storyboard = storyboard.model_copy(deep=True)
    current = 0.0
    audio_by_scene = {item.scene_id: item for item in scene_audio_items}
    for scene in timed_storyboard.scenes:
        item = audio_by_scene[scene.id]
        scene.start = round(current, 2)
        scene.duration = item.adjusted_scene_duration_seconds
        current += scene.duration

    manifest = TtsManifest(
        voice=settings.tts_voice,
        rate=settings.tts_rate,
        full_audio_path=full_audio_path,
        full_audio_duration_seconds=round(full_audio_duration, 2),
        scenes=scene_audio_items,
    )
    manifest_path = logs_dir / "tts-manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )

    timed_storyboard_path = output_dir / "storyboard-timed.json"
    timed_storyboard_path.write_text(
        timed_storyboard.model_dump_json(indent=2),
        encoding="utf-8",
    )

    adjustment_log = TimingAdjustmentLog(
        storyboard_path=output_dir / "storyboard.json",
        timed_storyboard_path=timed_storyboard_path,
        tts_manifest_path=manifest_path,
        original_total_duration_seconds=round(sum(scene.duration for scene in storyboard.scenes), 2),
        adjusted_total_duration_seconds=round(sum(scene.duration for scene in timed_storyboard.scenes), 2),
        method="scene_audio_duration_plus_scene_padding_never_shorter_than_audio",
    )
    adjustment_path = logs_dir / "timing-adjustment.json"
    adjustment_path.write_text(
        adjustment_log.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return timed_storyboard, manifest, adjustment_log


def _adjusted_scene_duration(
    scene_index: int,
    original_duration: float,
    audio_duration: float,
    scene_layout: str | None = None,
) -> float:
    padding = 0.15 if scene_index == 1 or scene_layout == "cta" else 0.45
    adjusted = max(audio_duration + padding, 2.5)
    if scene_index == 1 and original_duration <= 4 and audio_duration + padding <= 4:
        adjusted = min(adjusted, 4.0)
    return round(adjusted, 2)


def _synthesize_edge_tts(text: str, output_path: Path, voice: str, rate: str) -> None:
    if output_path.exists():
        return

    async def synthesize() -> None:
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(str(output_path))

    asyncio.run(synthesize())


def _audio_duration(path: Path) -> float:
    audio = MutagenFile(path)
    if audio is None or audio.info is None:
        raise ValueError(f"Unable to read audio duration: {path}")
    return float(audio.info.length)


def _concat_mp3_bytes(parts: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output:
        for part in parts:
            output.write(part.read_bytes())


def _normalize_audio(input_path: Path, output_path: Path, ffmpeg: Path | None) -> bool:
    if ffmpeg is None or not ffmpeg.exists() or output_path.exists():
        return output_path.exists()
    command = [
        str(ffmpeg),
        "-y",
        "-i",
        str(input_path),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar",
        "48000",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
