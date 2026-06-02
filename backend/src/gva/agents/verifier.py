from __future__ import annotations

import json
import re
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_reasoning_model, has_real_api_key
from gva.models.evidence import ClaimCheck, EvidenceIndex, VerificationReport
from gva.models.script import VideoScript
from gva.models.storyboard import Storyboard


SETUP_RE = re.compile(
    r"(pip|npm|pnpm|yarn|conda|docker|git clone|api key|安装|环境|启动命令|运行命令)",
    re.IGNORECASE,
)
HYPE_RE = re.compile(r"(颠覆|史上最强|全自动企业级|无所不能|完全替代|零成本|最先进)")
AUDIENCE_RE = re.compile(r"(适合|面向|专门.*(研究者|学生|开发者|用户)|为.*(研究者|学生|开发者|用户).*设计)")


def verify_video_plan(
    output_dir: Path,
    script: VideoScript,
    storyboard: Storyboard,
    evidence_index: EvidenceIndex,
    settings: Settings,
    use_llm: bool = True,
) -> VerificationReport:
    claims = _deterministic_checks(script, storyboard, evidence_index)
    if use_llm and _has_key(settings):
        claims.extend(_llm_claim_checks(script, storyboard, evidence_index, settings))

    report = VerificationReport(
        passed=not any(claim.severity == "high" and claim.status == "unsupported" for claim in claims),
        claims=claims,
        metrics={
            "claim_count": len(claims),
            "unsupported_high_count": sum(
                1 for claim in claims if claim.status == "unsupported" and claim.severity == "high"
            ),
            "weak_count": sum(1 for claim in claims if claim.status == "weak"),
            "evidence_item_count": len(evidence_index.items),
        },
    )
    _write_report(output_dir, report)
    return report


def render_verification_markdown(report: VerificationReport) -> str:
    lines = [
        "# Verification Report",
        "",
        f"- Passed: {report.passed}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in sorted(report.metrics.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Claims", ""])
    if not report.claims:
        lines.append("No claims checked.")
    else:
        for claim in report.claims:
            refs = ", ".join(claim.evidence_refs) if claim.evidence_refs else "none"
            lines.append(f"- [{claim.severity}] {claim.status} `{claim.id}`: {claim.text}")
            lines.append(f"  Evidence: {refs}")
            lines.append(f"  Reason: {claim.reason}")
    return "\n".join(lines)


def _deterministic_checks(
    script: VideoScript,
    storyboard: Storyboard,
    evidence_index: EvidenceIndex,
) -> list[ClaimCheck]:
    claims: list[ClaimCheck] = []
    evidence_ids = {item.id for item in evidence_index.items}

    for index, segment in enumerate(script.segments, start=1):
        refs = [ref for ref in segment.evidence_refs if ref in evidence_ids]
        text = segment.narration.strip()
        claims.append(_check_text(f"script-{index:03d}", "script", text, refs))

    for index, scene in enumerate(storyboard.scenes, start=1):
        refs = [ref for ref in scene.evidence_refs if ref in evidence_ids]
        claims.append(_check_text(f"scene-{index:03d}", "storyboard", scene.narration.strip(), refs))
        visual_text = " / ".join([scene.visual.headline, *scene.visual.bullets])
        claims.append(_check_text(f"visual-{index:03d}", "visual", visual_text.strip(), refs or scene.visual.evidence_refs))

    return claims


def _check_text(claim_id: str, source: str, text: str, refs: list[str]) -> ClaimCheck:
    if not text:
        return ClaimCheck(
            id=claim_id,
            source=source,  # type: ignore[arg-type]
            text=text,
            evidence_refs=refs,
            status="unsupported",
            severity="high",
            reason="Empty text cannot be verified.",
        )
    if SETUP_RE.search(text):
        return ClaimCheck(
            id=claim_id,
            source=source,  # type: ignore[arg-type]
            text=text,
            evidence_refs=refs,
            status="unsupported",
            severity="high",
            reason="Setup or install commands should not appear in the MVP video.",
        )
    if HYPE_RE.search(text):
        return ClaimCheck(
            id=claim_id,
            source=source,  # type: ignore[arg-type]
            text=text,
            evidence_refs=refs,
            status="unsupported",
            severity="high",
            reason="The wording is over-claimed for a repo-based explainer.",
        )
    if not refs:
        return ClaimCheck(
            id=claim_id,
            source=source,  # type: ignore[arg-type]
            text=text,
            evidence_refs=[],
            status="weak",
            severity="medium",
            reason="No evidence reference is attached; this should be traceable before production use.",
        )
    return ClaimCheck(
        id=claim_id,
        source=source,  # type: ignore[arg-type]
        text=text,
        evidence_refs=refs,
        status="supported",
        severity="low",
        reason="The claim has at least one attached evidence reference and passed rule checks.",
    )


def _llm_claim_checks(
    script: VideoScript,
    storyboard: Storyboard,
    evidence_index: EvidenceIndex,
    settings: Settings,
) -> list[ClaimCheck]:
    claims_payload = [
        {
            "id": f"llm-scene-{index:03d}",
            "text": scene.narration,
            "evidence_refs": scene.evidence_refs,
        }
        for index, scene in enumerate(storyboard.scenes, start=1)
    ]
    required_refs = {
        ref
        for claim in claims_payload
        for ref in claim.get("evidence_refs", [])
        if isinstance(ref, str)
    }
    ordered_items = [
        item for item in evidence_index.items if item.id in required_refs
    ]
    ordered_items.extend(item for item in evidence_index.items if item.id not in required_refs)

    evidence_payload = [
        {
            "id": item.id,
            "source_path": item.source_path,
            "role": item.role,
            "excerpt": item.excerpt[:1600],
            "derived_facts": item.derived_facts,
        }
        for item in ordered_items[:28]
    ]
    prompt = (
        "You are a strict verifier for a Chinese GitHub project explainer video. "
        "Only mark a claim supported if it is directly supported by the evidence excerpts. "
        "Comedic opening hooks such as '科技圈今天又炸了' are stylistic packaging; "
        "do not treat them as unsupported high-risk claims unless they assert a concrete product capability. "
        "Simple calls to action such as viewing the repository, reading README, cloning, or starring "
        "are marketing CTAs and should not be marked high severity just because the repo did not ask for them. "
        "Return JSON with a `claims` array. Each item must contain id, status "
        "(supported|weak|unsupported), severity (low|medium|high), and reason. "
        "Unsupported factual project capabilities should be high severity."
    )
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(
                {"evidence": evidence_payload, "claims": claims_payload, "script_title": script.title},
                ensure_ascii=False,
            ),
        },
    ]
    client = build_openai_client(settings)
    model = get_reasoning_model(settings)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    except BadRequestError as exc:
        if "response_format" not in str(exc):
            raise
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.1)
    except Exception as exc:
        return [
            ClaimCheck(
                id="llm-verifier",
                source="storyboard",
                text="LLM verifier failed",
                evidence_refs=[],
                status="weak",
                severity="medium",
                reason=str(exc)[:300],
            )
        ]

    payload = loads_json_object(response.choices[0].message.content or "{}")
    checks: list[ClaimCheck] = []
    scene_by_id = {f"llm-scene-{index:03d}": scene for index, scene in enumerate(storyboard.scenes, start=1)}
    for raw in payload.get("claims", []):
        claim_id = str(raw.get("id", "llm-claim"))
        scene = scene_by_id.get(claim_id)
        text = scene.narration if scene else claim_id
        status = raw.get("status", "weak")
        severity = raw.get("severity", "medium")
        if status not in {"supported", "weak", "unsupported"}:
            status = "weak"
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        reason = str(raw.get("reason", ""))[:500]
        status, severity, reason = _soften_llm_verdict(
            text=text,
            evidence_refs=scene.evidence_refs if scene else [],
            status=status,
            severity=severity,
            reason=reason,
        )
        checks.append(
            ClaimCheck(
                id=claim_id,
                source="storyboard",
                text=text,
                evidence_refs=scene.evidence_refs if scene else [],
                status=status,
                severity=severity,
                reason=reason or "LLM verifier did not provide a reason.",
            )
        )
    return checks


def _soften_llm_verdict(
    text: str,
    evidence_refs: list[str],
    status: str,
    severity: str,
    reason: str,
) -> tuple[str, str, str]:
    if status == "unsupported" and severity == "high" and evidence_refs and AUDIENCE_RE.search(text):
        return (
            "weak",
            "medium",
            (reason + " Audience framing is treated as editable positioning, not a blocking capability claim.").strip(),
        )
    return status, severity, reason


def _has_key(settings: Settings) -> bool:
    if settings.llm_provider == "deepseek":
        return has_real_api_key(settings.deepseek_api_key)
    if settings.llm_provider == "openai":
        return has_real_api_key(settings.openai_api_key)
    return False


def _write_report(output_dir: Path, report: VerificationReport) -> None:
    (output_dir / "verification-report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "verification-report.md").write_text(render_verification_markdown(report), encoding="utf-8")
