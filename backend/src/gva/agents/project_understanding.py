import json
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_reasoning_model
from gva.models.insight import ProjectInsight
from gva.models.repo import RepoSummary


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "project_understanding.md"


def understand_project(repo: RepoSummary, settings: Settings) -> ProjectInsight:
    client = build_openai_client(settings)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": _build_repo_input(repo)},
    ]
    model = get_reasoning_model(settings)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except BadRequestError as exc:
        if "response_format" not in str(exc):
            raise
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
    content = response.choices[0].message.content or "{}"
    return ProjectInsight.model_validate(_sanitize_insight_payload(loads_json_object(content)))


def _sanitize_insight_payload(payload: dict) -> dict:
    architecture = payload.get("architecture")
    if architecture is not None and not isinstance(architecture, str):
        payload["architecture"] = json.dumps(architecture, ensure_ascii=False)

    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        payload["evidence"] = {
            str(key): [str(item) for item in value] if isinstance(value, list) else [str(value)]
            for key, value in evidence.items()
        }
    return payload


def _build_repo_input(repo: RepoSummary) -> str:
    files = [
        {
            "path": file.path,
            "role": file.role,
            "language": file.language,
            "excerpt": file.excerpt,
        }
        for file in repo.files
    ]
    return json.dumps(
        {
            "repo_name": repo.repo_name,
            "tree_overview": repo.tree_overview,
            "detected_stack": repo.detected_stack,
            "files": files,
        },
        ensure_ascii=False,
    )
