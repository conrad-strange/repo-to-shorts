from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path

import edge_tts
from edge_tts.exceptions import NoAudioReceived, WebSocketError
from mutagen import File as MutagenFile

from gva.config import Settings
from gva.core.asyncio_windows import install_windows_connection_reset_filter
from gva.core.pacing import duration_range_for_video_mode
from gva.models.storyboard import Storyboard
from gva.models.tts import TimingAdjustmentLog, TtsManifest, TtsSceneAudio


MAX_MID_SCENE_SILENCE_SECONDS = 0.8
MAX_EDGE_SCENE_SILENCE_SECONDS = 0.35
EDGE_TTS_MAX_ATTEMPTS = 3
EDGE_TTS_RETRY_BASE_DELAY_SECONDS = 0.8


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

    durations_fitted = _fit_scene_audio_durations_for_video_mode(
        scene_audio_items=scene_audio_items,
        storyboard=storyboard,
        video_mode=settings.video_mode,
    )
    full_audio_path = output_dir / "audio" / "voice.mp3"
    _concat_scene_audio_with_padding(
        scene_audio_items=scene_audio_items,
        output_path=full_audio_path,
        ffmpeg=settings.ffmpeg_exe,
        audio_dir=audio_dir,
    )
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
        method=(
            "scene_audio_duration_plus_compact_transition_padding"
            if not durations_fitted
            else "scene_audio_duration_plus_bucket_padding"
        ),
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
    adjusted = max(original_duration, audio_duration + padding, 2.5)
    silence_cap = MAX_EDGE_SCENE_SILENCE_SECONDS if scene_index == 1 or scene_layout == "cta" else MAX_MID_SCENE_SILENCE_SECONDS
    adjusted = min(adjusted, max(audio_duration + silence_cap, audio_duration + padding, 2.5))
    if scene_index == 1 and original_duration <= 4 and audio_duration + padding <= 4:
        adjusted = min(adjusted, 4.0)
    return round(adjusted, 2)


def _fit_scene_audio_durations_for_video_mode(
    scene_audio_items: list[TtsSceneAudio],
    storyboard: Storyboard,
    video_mode: str,
) -> bool:
    if not scene_audio_items:
        return False

    minimum, maximum = duration_range_for_video_mode(video_mode)
    total = round(sum(item.adjusted_scene_duration_seconds for item in scene_audio_items), 2)
    changed = False

    if total < minimum:
        changed = _expand_scene_audio_items_to_minimum(scene_audio_items, storyboard, minimum) or changed
    elif total > maximum:
        changed = _shrink_scene_audio_items_to_maximum(scene_audio_items, maximum) or changed
    return changed


def _expand_scene_audio_items_to_minimum(
    scene_audio_items: list[TtsSceneAudio],
    storyboard: Storyboard,
    minimum: float,
) -> bool:
    deficit = minimum - round(sum(item.adjusted_scene_duration_seconds for item in scene_audio_items), 2)
    if deficit <= 0:
        return False

    candidates = _duration_expand_candidate_indexes(storyboard, len(scene_audio_items))
    if not candidates:
        return False

    share = deficit / len(candidates)
    for index in candidates:
        item = scene_audio_items[index]
        item.adjusted_scene_duration_seconds = round(item.adjusted_scene_duration_seconds + share, 2)
    _absorb_rounding_delta(scene_audio_items, minimum, candidates[-1])
    return True


def _shrink_scene_audio_items_to_maximum(scene_audio_items: list[TtsSceneAudio], maximum: float) -> bool:
    overflow = round(sum(item.adjusted_scene_duration_seconds for item in scene_audio_items), 2) - maximum
    if overflow <= 0:
        return False

    candidates = [
        (index, item)
        for index, item in enumerate(scene_audio_items)
        if item.adjusted_scene_duration_seconds > item.duration_seconds + 0.05
    ]
    remaining = overflow
    while candidates and remaining > 0.005:
        share = remaining / len(candidates)
        removed = 0.0
        next_candidates = []
        for index, item in candidates:
            floor = round(item.duration_seconds + 0.05, 2)
            room = max(0.0, item.adjusted_scene_duration_seconds - floor)
            reduction = min(share, room)
            if reduction > 0:
                item.adjusted_scene_duration_seconds = round(item.adjusted_scene_duration_seconds - reduction, 2)
                removed += reduction
            if room - reduction > 0.005:
                next_candidates.append((index, item))
        if removed <= 0.005:
            break
        remaining -= removed
        candidates = next_candidates
    return True


def _duration_expand_candidate_indexes(storyboard: Storyboard, item_count: int) -> list[int]:
    candidates = [
        index
        for index, scene in enumerate(storyboard.scenes[:item_count])
        if index > 0 and scene.visual.layout != "cta" and scene.type != "cta"
    ]
    if candidates:
        return candidates
    return [index for index in range(1, item_count)]


def _absorb_rounding_delta(scene_audio_items: list[TtsSceneAudio], minimum: float, index: int) -> None:
    total = round(sum(item.adjusted_scene_duration_seconds for item in scene_audio_items), 2)
    delta = round(minimum - total, 2)
    if abs(delta) <= 0.005:
        return
    scene_audio_items[index].adjusted_scene_duration_seconds = round(
        scene_audio_items[index].adjusted_scene_duration_seconds + delta,
        2,
    )


def _synthesize_edge_tts(text: str, output_path: Path, voice: str, rate: str) -> None:
    if output_path.exists() and output_path.stat().st_size > 512:
        return
    if output_path.exists():
        output_path.unlink()

    async def synthesize() -> None:
        install_windows_connection_reset_filter()
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(str(output_path))

    last_error: Exception | None = None
    for attempt in range(1, EDGE_TTS_MAX_ATTEMPTS + 1):
        try:
            asyncio.run(synthesize())
            if output_path.exists() and output_path.stat().st_size > 512:
                return
            raise NoAudioReceived("Edge TTS did not write an audio file.")
        except Exception as exc:
            last_error = exc
            if output_path.exists():
                output_path.unlink()
            if not _is_retryable_tts_error(exc) or attempt >= EDGE_TTS_MAX_ATTEMPTS:
                raise
            time.sleep(EDGE_TTS_RETRY_BASE_DELAY_SECONDS * attempt)

    if last_error is not None:
        raise last_error


def _is_retryable_tts_error(exc: Exception) -> bool:
    if isinstance(exc, (NoAudioReceived, WebSocketError, asyncio.TimeoutError, ConnectionResetError, OSError)):
        return True
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    return any(token in name or token in text for token in ("noaudio", "websocket", "timeout", "connection reset"))


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


def _concat_scene_audio_with_padding(
    scene_audio_items: list[TtsSceneAudio],
    output_path: Path,
    ffmpeg: Path | None,
    audio_dir: Path,
) -> None:
    parts: list[Path] = []
    for index, item in enumerate(scene_audio_items, start=1):
        parts.append(item.audio_path)
        silence_duration = item.adjusted_scene_duration_seconds - item.duration_seconds
        if silence_duration <= 0.05:
            continue
        silence_path = audio_dir / f"{index:02d}-{item.scene_id}-silence-{int(round(silence_duration * 1000))}ms.mp3"
        if _generate_silence_mp3(silence_path, silence_duration, ffmpeg):
            parts.append(silence_path)

    _concat_mp3_bytes(parts, output_path)


def _generate_silence_mp3(output_path: Path, duration: float, ffmpeg: Path | None) -> bool:
    if output_path.exists():
        return True
    if ffmpeg is None or not ffmpeg.exists() or duration <= 0:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=24000:cl=mono",
        "-t",
        f"{duration:.3f}",
        "-q:a",
        "9",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0


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
