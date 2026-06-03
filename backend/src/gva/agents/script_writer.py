import json
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_generation_model
from gva.models.insight import ProjectInsight
from gva.models.script import VideoScript


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "script_writer.md"


def write_script(insight: ProjectInsight, settings: Settings, user_brief: str | None = None) -> VideoScript:
    client = build_openai_client(settings)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": _build_insight_input(insight, settings, user_brief)},
    ]
    model = get_generation_model(settings)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.55,
        )
    except BadRequestError as exc:
        if "response_format" not in str(exc):
            raise
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.55,
        )
    content = response.choices[0].message.content or "{}"
    return VideoScript.model_validate(loads_json_object(content))


def render_script_markdown(script: VideoScript) -> str:
    lines = [
        f"# {script.title}",
        "",
        f"- Language: {script.language}",
        f"- Estimated duration: {script.duration_seconds or 'auto'} seconds",
        "",
        "## Full Narration",
        "",
        script.full_text,
        "",
        "## Segments",
        "",
    ]
    for index, segment in enumerate(script.segments, start=1):
        lines.extend(
            [
                f"### {index}. {segment.scene_hint}",
                "",
                segment.narration,
                "",
                f"Evidence keys: {', '.join(segment.evidence_keys) if segment.evidence_keys else 'none'}",
                "",
            ]
        )
    return "\n".join(lines)


def _build_insight_input(insight: ProjectInsight, settings: Settings, user_brief: str | None = None) -> str:
    return json.dumps(
        {
            "video_mode": settings.video_mode,
            "mode_notes": _mode_notes(settings.video_mode),
            "storytelling_mode": settings.storytelling_mode,
            "storytelling_notes": _storytelling_notes(settings.storytelling_mode),
            "user_brief": user_brief or "",
            "user_brief_rules": (
                "Treat user_brief as a high-priority preference for tone, pacing, emphasis, and ordering. "
                "If a requested emphasis is supported by project_insight or evidence, reflect it in at least one segment. "
                "Do not treat it as evidence and do not add project capabilities that are absent from project_insight. "
                "For setup/install/onboarding convenience requests, use high-level wording like easy onboarding or clear entry points; "
                "do not invent commands or claim zero configuration unless evidence supports it."
            ),
            "project_insight": insight.model_dump(),
        },
        ensure_ascii=False,
    )


def _mode_notes(video_mode: str) -> str:
    if video_mode == "short_30s":
        return "Aim for 30-40 seconds: pain point, what it does, one core highlight, GitHub CTA."
    if video_mode == "technical_90s":
        return "Aim for 75-90 seconds: include architecture, usage, and one concise code or implementation detail scene."
    return "Aim for 45-60 seconds: hook, project value, core flow, highlights, usage/CTA."


def _storytelling_notes(storytelling_mode: str) -> str:
    if storytelling_mode == "experience_first":
        return (
            "Prefer a viewer-facing usage story: concrete pain point, what the user gives the project, "
            "what happens next, what result they get, then a small amount of technical credibility. "
            "If the repo has no obvious input/output demo, fall back to README/code evidence cards."
        )
    return "Use the existing technical repo explainer structure."
