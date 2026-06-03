from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from gva.config import Settings
from gva.models.evaluation import EvaluationIssue, EvaluationReport
from gva.models.script import VideoScript
from gva.models.storyboard import Storyboard
from gva.models.tts import TimingAdjustmentLog, TtsManifest


def evaluate_output(output_dir: Path, settings: Settings) -> EvaluationReport:
    issues: list[EvaluationIssue] = []
    checked_files: list[Path] = []
    metrics: dict[str, Any] = {}

    video_path = _resolve_video_path(output_dir)
    required_files = {
        "repo-summary": output_dir / "repo-summary.json",
        "repo-evidence-index": output_dir / "repo-evidence-index.json",
        "project-insight": output_dir / "project-insight.json",
        "video-script": output_dir / "video-script.json",
        "storyboard": output_dir / "storyboard.json",
        "timed-storyboard": output_dir / "storyboard-timed.json",
        "verification-report": output_dir / "verification-report.json",
        "caption-cues": output_dir / "logs" / "caption-cues.json",
        "tts-manifest": output_dir / "logs" / "tts-manifest.json",
        "timing-adjustment": output_dir / "logs" / "timing-adjustment.json",
        "visual-assets-manifest": output_dir / "logs" / "visual-assets-manifest.json",
        "render-input": output_dir / "logs" / "render-input.json",
        "voice-audio": output_dir / "audio" / "voice.mp3",
        "video": video_path,
    }

    for label, path in required_files.items():
        checked_files.append(path)
        if not path.exists():
            severity = "high" if label in {"video", "timed-storyboard", "voice-audio"} else "medium"
            issues.append(
                EvaluationIssue(
                    severity=severity,
                    category="artifact",
                    message=f"Missing required artifact: {path}",
                    suggestion="Re-run the workflow step that produces this artifact.",
                )
            )

    script = _load_model(required_files["video-script"], VideoScript)
    storyboard = _load_model(required_files["storyboard"], Storyboard)
    timed_storyboard = _load_model(required_files["timed-storyboard"], Storyboard)
    tts_manifest = _load_model(required_files["tts-manifest"], TtsManifest)
    timing_log = _load_model(required_files["timing-adjustment"], TimingAdjustmentLog)
    visual_assets_manifest = _load_json(required_files["visual-assets-manifest"])

    if storyboard:
        _evaluate_storyboard(storyboard, "storyboard", issues, metrics)
    if timed_storyboard:
        _evaluate_storyboard(timed_storyboard, "timed_storyboard", issues, metrics)
    if script:
        metrics["script_segment_count"] = len(script.segments)
        metrics["script_duration_seconds"] = script.duration_seconds
        if len(script.full_text) < 120:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="script",
                    message="Script full_text is very short.",
                    suggestion="Regenerate or expand the script before rendering.",
                )
            )
    if tts_manifest:
        metrics["voice_audio_duration_seconds"] = tts_manifest.full_audio_duration_seconds
        metrics["tts_scene_count"] = len(tts_manifest.scenes)
        metrics["tts_rate"] = tts_manifest.rate
        if tts_manifest.rate in {"unknown", "+0%"}:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="tts",
                    message="TTS rate is not recorded as a mobile-short speedup.",
                    suggestion="Use TTS_RATE=+25% and regenerate TTS artifacts.",
                )
            )
    if timing_log:
        metrics["timing_original_duration_seconds"] = timing_log.original_total_duration_seconds
        metrics["timing_adjusted_duration_seconds"] = timing_log.adjusted_total_duration_seconds
        if timing_log.adjusted_total_duration_seconds > timing_log.original_total_duration_seconds * 1.6:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="timing",
                    message="TTS-adjusted duration is much longer than the original storyboard duration.",
                    suggestion="Consider generating a shorter script or allowing fewer visual beats.",
                )
            )
    if visual_assets_manifest:
        screenshot = visual_assets_manifest.get("github_screenshot", {})
        metrics["github_screenshot_status"] = screenshot.get("status", "unknown")
        metrics["visual_asset_annotation_count"] = len(visual_assets_manifest.get("annotations", []))
        if screenshot.get("status") == "failed":
            issues.append(
                EvaluationIssue(
                    severity="low",
                    category="visual",
                    message="GitHub screenshot asset was not generated.",
                    suggestion="Check BROWSER_EXE/CHROME_EXE or network access; the render should fall back to text scenes.",
                )
            )

    media_info = _probe_video(required_files["video"], settings)
    metrics["video_path"] = str(required_files["video"])
    metrics.update(media_info)
    _evaluate_media_info(media_info, issues)

    score = _score_from_issues(issues)
    report = EvaluationReport(
        passed=not any(issue.severity == "high" for issue in issues),
        score=score,
        issues=issues,
        metrics=metrics,
        checked_files=checked_files,
    )
    _write_reports(output_dir, report)
    return report


def render_evaluation_markdown(report: EvaluationReport) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"- Passed: {report.passed}",
        f"- Score: {report.score}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in sorted(report.metrics.items()):
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## Issues", ""])
    if not report.issues:
        lines.append("No issues found.")
    else:
        for issue in report.issues:
            lines.append(f"- [{issue.severity}] {issue.category}: {issue.message}")
            if issue.suggestion:
                lines.append(f"  Suggestion: {issue.suggestion}")

    lines.extend(["", "## Checked Files", ""])
    for path in report.checked_files:
        lines.append(f"- `{path}`")
    return "\n".join(lines)


def _evaluate_storyboard(
    storyboard: Storyboard,
    prefix: str,
    issues: list[EvaluationIssue],
    metrics: dict[str, Any],
) -> None:
    total_duration = round(sum(scene.duration for scene in storyboard.scenes), 2)
    metrics[f"{prefix}_scene_count"] = len(storyboard.scenes)
    metrics[f"{prefix}_duration_seconds"] = total_duration

    if not 5 <= len(storyboard.scenes) <= 9:
        issues.append(
            EvaluationIssue(
                severity="medium",
                category="storyboard",
                message=f"{prefix} has {len(storyboard.scenes)} scenes; expected 5-9 for MVP.",
            )
        )

    if storyboard.scenes:
        first = storyboard.scenes[0]
        metrics[f"{prefix}_first_scene_duration_seconds"] = first.duration
        if first.duration > 4:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="hook",
                    message=f"{prefix} first scene is {first.duration}s; mobile hook should be <= 4s.",
                    suggestion="Regenerate storyboard with a shorter hook scene.",
                )
            )

    if total_duration > 60:
        issues.append(
            EvaluationIssue(
                severity="medium",
                category="timing",
                message=f"{prefix} total duration is {total_duration}s; mobile-short target is <= 60s.",
                suggestion="Regenerate a shorter script/storyboard or increase TTS rate.",
            )
        )

    for scene in storyboard.scenes:
        if not scene.narration.strip():
            issues.append(
                EvaluationIssue(
                    severity="high",
                    category="storyboard",
                    message=f"{scene.id} narration is empty.",
                )
            )
        if not scene.visual.headline.strip():
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="visual",
                    message=f"{scene.id} visual headline is empty.",
                )
            )
        if len(scene.visual.bullets) > 3:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="visual",
                    message=f"{scene.id} has {len(scene.visual.bullets)} bullets; mobile layout may feel dense.",
                    suggestion="Keep each vertical scene to at most 3 bullet points.",
                )
            )
        _evaluate_visual_density(scene, issues)
        if scene.duration < 2.5:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="timing",
                    message=f"{scene.id} duration is too short: {scene.duration}s.",
                )
            )
        if scene.duration > 20:
            issues.append(
                EvaluationIssue(
                    severity="low",
                    category="timing",
                    message=f"{scene.id} duration is long: {scene.duration}s.",
                    suggestion="Consider splitting this scene if the pacing feels slow.",
                )
            )


def _evaluate_visual_density(scene, issues: list[EvaluationIssue]) -> None:
    visual_texts = [scene.visual.headline, scene.visual.caption or "", *scene.visual.bullets]
    if scene.visual.micro_beats:
        visual_texts.extend(beat.text for beat in scene.visual.micro_beats)

    for text in visual_texts:
        cleaned = _normalize_text(text)
        if not cleaned:
            continue
        if len(cleaned) > 42:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="visual",
                    message=f"{scene.id} visual text is long for mobile: {text[:48]}",
                    suggestion="Keep visual copy keyword-like; move full explanation to narration/subtitles.",
                )
            )
            break
        narration = _normalize_text(scene.narration)
        if len(cleaned) >= 14 and cleaned in narration:
            issues.append(
                EvaluationIssue(
                    severity="low",
                    category="visual",
                    message=f"{scene.id} visual text repeats narration.",
                    suggestion="Use shorter keywords on screen and let narration explain the sentence.",
                )
            )
            break

    if scene.visual.layout in {"stack", "feature_spotlight", "evidence_grid"}:
        item_count = len(scene.visual.micro_beats or []) or len(scene.visual.bullets)
        if item_count > 4:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="visual",
                    message=f"{scene.id} has {item_count} visual beats; expected at most 4.",
                    suggestion="Reduce chips/cards so the scene stays readable on mobile.",
                )
            )


def _normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?;；:：/|]+", "", text or "")


def _probe_video(video_path: Path, settings: Settings) -> dict[str, Any]:
    if not video_path.exists():
        return {"video_exists": False}

    metrics: dict[str, Any] = {
        "video_exists": True,
        "video_size_bytes": video_path.stat().st_size,
    }
    ffmpeg = settings.ffmpeg_exe
    if ffmpeg is None or not ffmpeg.exists():
        metrics["media_probe_available"] = False
        return metrics

    command = [str(ffmpeg), "-i", str(video_path), "-hide_banner"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    output = result.stderr + result.stdout
    metrics["media_probe_available"] = True
    metrics["has_audio"] = "Audio:" in output
    metrics["has_video"] = "Video:" in output
    metrics["video_resolution"] = _parse_video_resolution(output)
    metrics["is_9_16"] = _is_vertical_9_16(output, metrics["video_resolution"])
    metrics["duration_seconds"] = _parse_duration(output)
    metrics["media_probe_summary"] = _compact_media_summary(output)
    return metrics


def _evaluate_media_info(media_info: dict[str, Any], issues: list[EvaluationIssue]) -> None:
    if not media_info.get("video_exists"):
        issues.append(
            EvaluationIssue(
                severity="high",
                category="media",
                message="Rendered video does not exist.",
            )
        )
        return
    if media_info.get("video_size_bytes", 0) < 100_000:
        issues.append(
            EvaluationIssue(
                severity="high",
                category="media",
                message="Rendered video file is unexpectedly small.",
            )
        )
    if media_info.get("media_probe_available"):
        if not media_info.get("has_video"):
            issues.append(EvaluationIssue(severity="high", category="media", message="Video stream not detected."))
        if not media_info.get("has_audio"):
            issues.append(EvaluationIssue(severity="high", category="media", message="Audio stream not detected."))
        if not media_info.get("is_9_16"):
            issues.append(
                EvaluationIssue(
                    severity="high",
                    category="media",
                    message="Video is not detected as a 9:16 vertical render.",
                )
            )
        duration = media_info.get("duration_seconds")
        if isinstance(duration, float) and duration < 20:
            issues.append(
                EvaluationIssue(
                    severity="medium",
                    category="media",
                    message=f"Video duration is short: {duration}s.",
                )
            )


def _load_model(path: Path, model_class):
    if not path.exists():
        return None
    try:
        return model_class.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_duration(output: str) -> float | None:
    marker = "Duration:"
    if marker not in output:
        return None
    after = output.split(marker, 1)[1].strip()
    timestamp = after.split(",", 1)[0].strip()
    try:
        hours, minutes, seconds = timestamp.split(":")
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 2)
    except ValueError:
        return None


def _parse_video_resolution(output: str) -> str | None:
    video_line = next((line for line in output.splitlines() if "Video:" in line), "")
    match = re.search(r"(\d{3,5})x(\d{3,5})", video_line)
    return match.group(0) if match else None


def _is_vertical_9_16(output: str, resolution: str | None) -> bool:
    if "DAR 9:16" in output:
        return True
    if not resolution:
        return False
    width, height = (int(part) for part in resolution.split("x", 1))
    if height <= width:
        return False
    return abs((width / height) - (9 / 16)) < 0.02


def _compact_media_summary(output: str) -> list[str]:
    return [
        line.strip()
        for line in output.splitlines()
        if "Duration:" in line or "Video:" in line or "Audio:" in line
    ]


def _score_from_issues(issues: list[EvaluationIssue]) -> int:
    score = 100
    for issue in issues:
        if issue.severity == "high":
            score -= 25
        elif issue.severity == "medium":
            score -= 10
        else:
            score -= 3
    return max(0, score)


def _write_reports(output_dir: Path, report: EvaluationReport) -> None:
    json_path = output_dir / "evaluation-report.json"
    md_path = output_dir / "evaluation-report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_evaluation_markdown(report), encoding="utf-8")


def _resolve_video_path(output_dir: Path) -> Path:
    return output_dir / "video.mp4"
