import json
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_generation_model
from gva.models.script import VideoScript
from gva.models.storyboard import Storyboard


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "storyboard_writer.md"


def write_storyboard(script: VideoScript, settings: Settings) -> Storyboard:
    client = build_openai_client(settings)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(script.model_dump(), ensure_ascii=False)},
    ]
    model = get_generation_model(settings)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.35,
        )
    except BadRequestError as exc:
        if "response_format" not in str(exc):
            raise
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.35,
        )
    content = response.choices[0].message.content or "{}"
    payload = sanitize_storyboard_payload(loads_json_object(content))
    return normalize_storyboard_timing(Storyboard.model_validate(payload))


def sanitize_storyboard_payload(payload: dict) -> dict:
    payload = dict(payload)
    payload.setdefault("aspect_ratio", "9:16")
    payload.setdefault("fps", 30)
    payload.setdefault("width", 1080)
    payload.setdefault("height", 1920)
    payload.setdefault("title", "项目讲解")

    scenes = payload.get("scenes") or []
    sanitized_scenes = []
    for index, scene in enumerate(scenes, start=1):
        scene = dict(scene or {})
        scene_id = scene.get("id")
        if not isinstance(scene_id, str):
            scene["id"] = f"scene-{index:03d}"
        scene.setdefault("type", "text")
        scene.setdefault("start", 0)
        scene.setdefault("duration", 6)
        scene.setdefault("narration", "")
        scene["evidence_keys"] = _list_or_empty(scene.get("evidence_keys"))
        scene["evidence_refs"] = _list_or_empty(scene.get("evidence_refs"))
        scene["captions"] = _list_or_empty(scene.get("captions"))

        visual = dict(scene.get("visual") or {})
        visual.setdefault("layout", _layout_from_type(scene.get("type")))
        visual.setdefault("headline", "")
        visual["bullets"] = _list_or_empty(visual.get("bullets"))
        visual["diagram_nodes"] = _list_or_empty(visual.get("diagram_nodes"))
        visual["icons"] = _list_or_empty(visual.get("icons"))
        visual["micro_beats"] = _sanitize_micro_beats(visual.get("micro_beats"), visual)
        visual.setdefault("caption", None)
        visual.setdefault("code", None)
        visual.setdefault("accent_color", "#111827")
        visual.setdefault("animation", "rise")
        visual.setdefault("asset_type", "none")
        visual.setdefault("asset_path", None)
        visual.setdefault("focus_target", "none")
        visual.setdefault("repo_url", None)
        visual.setdefault("repo_display_url", None)
        visual["evidence_refs"] = _list_or_empty(visual.get("evidence_refs"))
        scene["visual"] = visual
        sanitized_scenes.append(scene)

    payload["scenes"] = sanitized_scenes
    return payload


def normalize_storyboard_timing(storyboard: Storyboard) -> Storyboard:
    current = 0.0
    normalized = []
    for scene in storyboard.scenes:
        scene.start = round(current, 2)
        scene.duration = max(2.5, round(scene.duration, 2))
        current += scene.duration
        normalized.append(scene)
    storyboard.scenes = normalized
    return storyboard


def _list_or_empty(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _sanitize_micro_beats(value: object, visual: dict) -> list[dict]:
    allowed = {"text", "metric", "code", "flow", "warning", "cta"}
    raw_items = value if isinstance(value, list) else []
    if not raw_items:
        raw_items = [
            {"text": item, "kind": "text", "start_ratio": index * 0.18}
            for index, item in enumerate(visual.get("bullets", [])[:3])
        ]
        if visual.get("code"):
            raw_items.append({"text": visual["code"], "kind": "code", "start_ratio": 0.54})

    sanitized = []
    for index, item in enumerate(raw_items[:4]):
        if isinstance(item, str):
            item = {"text": item}
        item = dict(item or {})
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        kind = item.get("kind", "text")
        if kind not in allowed:
            kind = "text"
        try:
            start_ratio = float(item.get("start_ratio", index * 0.18))
        except (TypeError, ValueError):
            start_ratio = index * 0.18
        sanitized.append(
            {
                "text": text,
                "kind": kind,
                "emphasis": item.get("emphasis"),
                "start_ratio": min(max(start_ratio, 0.0), 0.86),
            }
        )
    return sanitized


def _layout_from_type(value: object) -> str:
    allowed = {
        "hook",
        "github_hero",
        "title",
        "text",
        "readme_focus",
        "feature_spotlight",
        "architecture_map",
        "evidence_grid",
        "code",
        "flow",
        "stack",
        "steps",
        "cta",
    }
    if isinstance(value, str) and value in allowed:
        return value
    return "text"
