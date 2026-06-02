from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_generation_model
from gva.models.evidence import ClaimCheck, EvidenceIndex, VerificationReport
from gva.models.script import VideoScript
from gva.models.storyboard import MicroBeat, Storyboard


ALLOWED_BEAT_KINDS = {"text", "metric", "code", "flow", "warning", "cta"}


def repair_video_plan(
    output_dir: Path,
    script: VideoScript,
    storyboard: Storyboard,
    verification: VerificationReport,
    evidence_index: EvidenceIndex,
    settings: Settings,
) -> tuple[VideoScript, Storyboard, dict[str, Any]]:
    """Ask a lightweight generation model to downgrade unsupported claims.

    The repair step is intentionally narrow: it may rewrite narration and short
    visual copy, but it should not add scenes, change layouts, or introduce new
    project facts that are absent from the evidence index.
    """
    repairable_claims = _repairable_claims(verification)
    if not repairable_claims:
        report = {
            "attempted": False,
            "reason": "No high unsupported or medium weak claims to repair.",
            "changes": [],
        }
        _write_repair_report(output_dir, report)
        return script, storyboard, report

    client = build_openai_client(settings)
    model = get_generation_model(settings)
    messages = [
        {"role": "system", "content": _repair_prompt()},
        {
            "role": "user",
            "content": json.dumps(
                _repair_input(script, storyboard, verification, evidence_index),
                ensure_ascii=False,
            ),
        },
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.25,
        )
    except BadRequestError as exc:
        if "response_format" not in str(exc):
            raise
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.25)

    payload = loads_json_object(response.choices[0].message.content or "{}")
    repaired_script = script.model_copy(deep=True)
    repaired_storyboard = storyboard.model_copy(deep=True)
    changes = apply_repair_payload(repaired_script, repaired_storyboard, payload)

    report = {
        "attempted": True,
        "model": model,
        "repairable_claims": [claim.model_dump() for claim in repairable_claims],
        "changes": changes,
        "notes": _list_of_strings(payload.get("notes")),
    }
    _write_repair_report(output_dir, report)
    return repaired_script, repaired_storyboard, report


def apply_repair_payload(
    script: VideoScript,
    storyboard: Storyboard,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    for raw in payload.get("script_segments", []) or []:
        if not isinstance(raw, dict):
            continue
        index = _safe_int(raw.get("index"))
        narration = _clean_text(raw.get("narration"), limit=220)
        if index is None or not narration or not (1 <= index <= len(script.segments)):
            continue
        old = script.segments[index - 1].narration
        if old != narration:
            script.segments[index - 1].narration = narration
            changes.append({"target": f"script.segments[{index - 1}].narration", "old": old, "new": narration})

    if script.segments:
        script.full_text = "".join(segment.narration for segment in script.segments)

    scene_by_id = {scene.id: scene for scene in storyboard.scenes}
    for raw in payload.get("storyboard_scenes", []) or []:
        if not isinstance(raw, dict):
            continue
        scene_id = str(raw.get("id", "")).strip()
        scene = scene_by_id.get(scene_id)
        if scene is None:
            continue

        narration = _clean_text(raw.get("narration"), limit=240)
        if narration and scene.narration != narration:
            changes.append({"target": f"{scene.id}.narration", "old": scene.narration, "new": narration})
            scene.narration = narration

        visual = raw.get("visual")
        if not isinstance(visual, dict):
            continue
        headline = _clean_text(visual.get("headline"), limit=36)
        if headline and scene.visual.headline != headline:
            changes.append({"target": f"{scene.id}.visual.headline", "old": scene.visual.headline, "new": headline})
            scene.visual.headline = headline

        caption = _clean_text(visual.get("caption"), limit=42)
        if caption is not None and scene.visual.caption != caption:
            changes.append({"target": f"{scene.id}.visual.caption", "old": scene.visual.caption, "new": caption})
            scene.visual.caption = caption

        bullets = [_clean_text(item, limit=28) for item in _list_of_strings(visual.get("bullets"))]
        bullets = [item for item in bullets if item][:3]
        if bullets and scene.visual.bullets != bullets:
            changes.append({"target": f"{scene.id}.visual.bullets", "old": scene.visual.bullets, "new": bullets})
            scene.visual.bullets = bullets

        diagram_nodes = [_clean_text(item, limit=42) for item in _list_of_strings(visual.get("diagram_nodes"))]
        diagram_nodes = [item for item in diagram_nodes if item][:6]
        if diagram_nodes and scene.visual.diagram_nodes != diagram_nodes:
            changes.append(
                {"target": f"{scene.id}.visual.diagram_nodes", "old": scene.visual.diagram_nodes, "new": diagram_nodes}
            )
            scene.visual.diagram_nodes = diagram_nodes

        micro_beats = _micro_beats_from_payload(visual.get("micro_beats"))
        if micro_beats:
            changes.append(
                {
                    "target": f"{scene.id}.visual.micro_beats",
                    "old": [beat.model_dump() for beat in scene.visual.micro_beats],
                    "new": [beat.model_dump() for beat in micro_beats],
                }
            )
            scene.visual.micro_beats = micro_beats

    return changes


def render_repair_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Repair Report",
        "",
        f"- Attempted: `{report.get('attempted')}`",
        f"- Model: `{report.get('model', 'n/a')}`",
        f"- Change count: `{len(report.get('changes') or [])}`",
        "",
        "## Claims",
        "",
    ]
    claims = report.get("repairable_claims") or []
    if claims:
        for claim in claims:
            lines.append(f"- `{claim.get('id')}` {claim.get('status')} / {claim.get('severity')}: {claim.get('text')}")
            lines.append(f"  Reason: {claim.get('reason')}")
    else:
        lines.append("No repairable claims.")

    lines.extend(["", "## Changes", ""])
    changes = report.get("changes") or []
    if changes:
        for change in changes:
            lines.append(f"- `{change.get('target')}`")
            lines.append(f"  Old: {change.get('old')}")
            lines.append(f"  New: {change.get('new')}")
    else:
        lines.append("No changes returned.")

    notes = report.get("notes") or []
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def _repair_prompt() -> str:
    return (
        "You are the Repair Agent for a Chinese GitHub project explainer video. "
        "Your job is to rewrite only unsupported or weak claims so they become evidence-backed. "
        "Use only the supplied evidence excerpts. Do not add new project capabilities. "
        "Do not include install commands, API-key setup, or exaggerated marketing claims. "
        "Keep Chinese narration natural for a short vertical video. "
        "Keep visual text short: headline <= 12 Chinese chars when possible, bullets <= 8 Chinese chars. "
        "Do not add, remove, or reorder scenes. Preserve repo names, technical terms, and evidence refs. "
        "Return strict JSON with keys: script_segments, storyboard_scenes, notes. "
        "script_segments items: {index, narration}. "
        "storyboard_scenes items: {id, narration, visual:{headline, caption, bullets, diagram_nodes, micro_beats}}. "
        "micro_beats items may use kind text|metric|flow|warning|cta."
    )


def _repair_input(
    script: VideoScript,
    storyboard: Storyboard,
    verification: VerificationReport,
    evidence_index: EvidenceIndex,
) -> dict[str, Any]:
    repairable = _repairable_claims(verification)
    required_refs = {
        ref
        for claim in repairable
        for ref in claim.evidence_refs
        if isinstance(ref, str)
    }
    for scene in storyboard.scenes:
        required_refs.update(scene.evidence_refs)
    ordered_items = [item for item in evidence_index.items if item.id in required_refs]
    ordered_items.extend(item for item in evidence_index.items if item.id not in required_refs)
    evidence = [
        {
            "id": item.id,
            "source_path": item.source_path,
            "role": item.role,
            "excerpt": item.excerpt[:1600],
            "derived_facts": item.derived_facts,
        }
        for item in ordered_items[:24]
    ]
    return {
        "repairable_claims": [claim.model_dump() for claim in repairable],
        "evidence": evidence,
        "script": {
            "title": script.title,
            "segments": [
                {
                    "index": index,
                    "scene_hint": segment.scene_hint,
                    "narration": segment.narration,
                    "evidence_refs": segment.evidence_refs,
                }
                for index, segment in enumerate(script.segments, start=1)
            ],
        },
        "storyboard": {
            "title": storyboard.title,
            "scenes": [
                {
                    "id": scene.id,
                    "layout": scene.visual.layout,
                    "duration": scene.duration,
                    "narration": scene.narration,
                    "evidence_refs": scene.evidence_refs,
                    "visual": {
                        "headline": scene.visual.headline,
                        "caption": scene.visual.caption,
                        "bullets": scene.visual.bullets,
                        "diagram_nodes": scene.visual.diagram_nodes,
                        "micro_beats": [beat.model_dump() for beat in scene.visual.micro_beats],
                    },
                }
                for scene in storyboard.scenes
            ],
        },
    }


def _repairable_claims(verification: VerificationReport) -> list[ClaimCheck]:
    return [
        claim
        for claim in verification.claims
        if (claim.status == "unsupported" and claim.severity == "high")
        or (claim.status == "weak" and claim.severity in {"medium", "high"})
    ]


def _micro_beats_from_payload(value: object) -> list[MicroBeat]:
    raw_items = value if isinstance(value, list) else []
    beats: list[MicroBeat] = []
    for index, raw in enumerate(raw_items[:4]):
        if isinstance(raw, str):
            raw = {"text": raw}
        if not isinstance(raw, dict):
            continue
        text = _clean_text(raw.get("text"), limit=28)
        if not text:
            continue
        kind = str(raw.get("kind") or "text")
        if kind not in ALLOWED_BEAT_KINDS:
            kind = "text"
        start_ratio = raw.get("start_ratio", index * 0.18)
        try:
            start_ratio = min(max(float(start_ratio), 0.0), 0.86)
        except (TypeError, ValueError):
            start_ratio = index * 0.18
        beats.append(
            MicroBeat(
                text=text,
                kind=kind,  # type: ignore[arg-type]
                emphasis=_clean_text(raw.get("emphasis"), limit=18),
                start_ratio=start_ratio,
            )
        )
    return beats


def _clean_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\r", " ").strip()
    if not text:
        return None
    text = " ".join(part for part in text.split() if part)
    text = _normalize_terms(text)
    return text[:limit]


def _normalize_terms(text: str) -> str:
    return text.replace("READNE", "README").replace("Readne", "README").replace("readne", "README")


def _list_of_strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _safe_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _write_repair_report(output_dir: Path, report: dict[str, Any]) -> None:
    (output_dir / "repair-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "repair-report.md").write_text(render_repair_markdown(report), encoding="utf-8")
