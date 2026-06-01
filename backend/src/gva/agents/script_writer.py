import json
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_generation_model
from gva.models.insight import ProjectInsight
from gva.models.script import VideoScript


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "script_writer.md"


def write_script(insight: ProjectInsight, settings: Settings) -> VideoScript:
    client = build_openai_client(settings)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": _build_insight_input(insight)},
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


def _build_insight_input(insight: ProjectInsight) -> str:
    return json.dumps(insight.model_dump(), ensure_ascii=False)
