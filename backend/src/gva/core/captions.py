from __future__ import annotations

import json
import re
from pathlib import Path

from gva.models.storyboard import CaptionCue, Storyboard


KEYWORD_RE = re.compile(r"(RAG|FAISS|DeepSeek|GitHub|README|API|FastAPI|LangGraph|Remotion|Python|TypeScript)", re.IGNORECASE)


def attach_caption_cues(storyboard: Storyboard, output_dir: Path) -> Storyboard:
    enhanced = storyboard.model_copy(deep=True)
    manifest: dict[str, list[dict]] = {"scenes": []}
    for scene in enhanced.scenes:
        cues = _scene_cues(scene_id=scene.id, narration=scene.narration, duration=scene.duration)
        scene.captions = cues
        manifest["scenes"].append(
            {
                "scene_id": scene.id,
                "duration": scene.duration,
                "cue_count": len(cues),
                "cues": [cue.model_dump() for cue in cues],
            }
        )

    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "caption-cues.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "subtitles.srt").write_text(_render_srt(enhanced), encoding="utf-8")
    (output_dir / "subtitles.vtt").write_text(_render_vtt(enhanced), encoding="utf-8")
    return enhanced


def _scene_cues(scene_id: str, narration: str, duration: float) -> list[CaptionCue]:
    parts = _split_narration(narration)
    if not parts:
        return []
    total_weight = sum(max(len(part), 6) for part in parts)
    cursor = 0.0
    cues: list[CaptionCue] = []
    for index, part in enumerate(parts):
        if index == len(parts) - 1:
            end = duration
        else:
            weight = max(len(part), 6) / total_weight
            end = min(duration, cursor + max(0.8, duration * weight))
        cues.append(
            CaptionCue(
                start=round(cursor, 2),
                end=round(max(end, cursor + 0.6), 2),
                text=part,
                keywords=_keywords(part),
                source_scene_id=scene_id,
            )
        )
        cursor = cues[-1].end
        if cursor >= duration:
            break
    if cues:
        cues[-1].end = round(duration, 2)
    return cues


def _split_narration(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    rough = [part for part in re.split(r"(?<=[。！？!?；;])", text) if part]
    parts: list[str] = []
    for item in rough:
        item = item.strip()
        if len(item) <= 26:
            parts.append(item)
            continue
        chunks = [chunk for chunk in re.split(r"(?<=[，,、])", item) if chunk]
        current = ""
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            if len(current) + len(chunk) <= 34:
                current += chunk
            else:
                if current:
                    parts.append(current)
                if len(chunk) > 34:
                    wrapped = _wrap_caption_text(chunk, max_length=34)
                    parts.extend(wrapped[:-1])
                    current = wrapped[-1] if wrapped else ""
                else:
                    current = chunk
        if current:
            parts.append(current)
    return parts[:8]


def _wrap_caption_text(text: str, max_length: int) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_+#./:-]*|\s+|.", text)
    lines: list[str] = []
    current = ""
    for token in tokens:
        if token.isspace():
            if current and not current.endswith(" "):
                current += " "
            continue
        if len((current + token).strip()) <= max_length:
            current += token
            continue
        if current.strip():
            lines.append(current.strip())
        current = token if len(token) <= max_length else token[:max_length]
    if current.strip():
        lines.append(current.strip())
    return lines


def _keywords(text: str) -> list[str]:
    found = []
    for match in KEYWORD_RE.finditer(text):
        value = match.group(0)
        canonical = "GitHub" if value.lower() == "github" else value
        found.append(canonical)
    return list(dict.fromkeys(found))


def _render_srt(storyboard: Storyboard) -> str:
    lines: list[str] = []
    index = 1
    for scene in storyboard.scenes:
        for cue in scene.captions:
            start = scene.start + cue.start
            end = scene.start + cue.end
            lines.extend(
                [
                    str(index),
                    f"{_srt_time(start)} --> {_srt_time(end)}",
                    cue.text,
                    "",
                ]
            )
            index += 1
    return "\n".join(lines)


def _render_vtt(storyboard: Storyboard) -> str:
    lines = ["WEBVTT", ""]
    for scene in storyboard.scenes:
        for cue in scene.captions:
            start = scene.start + cue.start
            end = scene.start + cue.end
            lines.extend([f"{_vtt_time(start)} --> {_vtt_time(end)}", cue.text, ""])
    return "\n".join(lines)


def _srt_time(seconds: float) -> str:
    hours, remainder = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int(round((secs - int(secs)) * 1000))
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d},{millis:03d}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")
