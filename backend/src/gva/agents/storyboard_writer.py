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
        {
            "role": "user",
            "content": json.dumps(
                {
                    "video_mode": settings.video_mode,
                    "mode_notes": _mode_notes(settings.video_mode),
                    "storytelling_mode": settings.storytelling_mode,
                    "storytelling_notes": _storytelling_notes(settings.storytelling_mode),
                    "video_script": script.model_dump(),
                },
                ensure_ascii=False,
            ),
        },
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
    payload = dict(payload) if isinstance(payload, dict) else {}
    if "scenes" not in payload and isinstance(payload.get("storyboard"), dict):
        payload = dict(payload["storyboard"])
    payload["aspect_ratio"] = "9:16"
    payload["fps"] = _safe_int(payload.get("fps"), 30)
    payload["width"] = _safe_int(payload.get("width"), 1080)
    payload["height"] = _safe_int(payload.get("height"), 1920)
    payload["title"] = _clean_string(payload.get("title"), fallback="项目讲解")

    scenes = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
    sanitized_scenes = []
    for index, scene in enumerate(scenes, start=1):
        scene = dict(scene) if isinstance(scene, dict) else {}
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id.strip():
            scene["id"] = f"scene-{index:03d}"
        scene["type"] = _clean_string(scene.get("type"), fallback="text")
        scene["start"] = _safe_float(_first_present(scene, "start", "startSec", "start_seconds"), 0.0)
        scene["duration"] = _safe_float(_first_present(scene, "duration", "durationSec", "duration_seconds"), 6.0)
        scene["narration"] = _clean_string(
            _first_present(scene, "narration", "voiceover", "script", "subtitle"),
            fallback="",
        )
        scene["evidence_keys"] = _string_list(_first_present(scene, "evidence_keys", "evidenceKeys"))
        scene["evidence_refs"] = _string_list(_first_present(scene, "evidence_refs", "evidenceRefs"))
        # Captions are generated after TTS timing. LLM-shaped captions often miss
        # source_scene_id/start/end and should not block storyboard validation.
        scene["captions"] = []

        visual = dict(scene.get("visual")) if isinstance(scene.get("visual"), dict) else {}
        visual["layout"] = _layout_from_values(_first_present(visual, "layout", "type") or scene.get("type"), scene.get("type"))
        visual["headline"] = _clean_string(
            _first_present(visual, "headline", "title") or _first_present(scene, "headline", "title"),
            fallback="",
        )
        visual["bullets"] = _string_list(_first_present(visual, "bullets", "items") or _first_present(scene, "bullets", "items"))
        visual["diagram_nodes"] = _string_list(
            _first_present(visual, "diagram_nodes", "diagramNodes", "nodes")
            or _first_present(scene, "diagram_nodes", "diagramNodes", "nodes")
        )
        visual["icons"] = _string_list(_first_present(visual, "icons", "icon"))
        visual["micro_beats"] = _sanitize_micro_beats(visual.get("micro_beats"), visual)
        visual["caption"] = _optional_string(_first_present(visual, "caption", "subtitle"))
        visual["code"] = _optional_multiline_string(_first_present(visual, "code", "codeSnippet") or scene.get("codeSnippet"))
        visual["accent_color"] = _accent_from_value(visual.get("accent_color"))
        visual["animation"] = _animation_from_value(_first_present(visual, "animation", "motion") or scene.get("animation"))
        visual["asset_type"] = _asset_type_from_value(_first_present(visual, "asset_type", "assetType"))
        visual["asset_path"] = _optional_string(_first_present(visual, "asset_path", "assetPath"))
        visual["focus_target"] = _focus_target_from_value(_first_present(visual, "focus_target", "focusTarget"))
        visual["repo_url"] = _optional_string(_first_present(visual, "repo_url", "repoUrl"))
        visual["repo_display_url"] = _optional_string(_first_present(visual, "repo_display_url", "repoDisplayUrl"))
        visual["evidence_refs"] = _string_list(_first_present(visual, "evidence_refs", "evidenceRefs"))
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


def _storytelling_notes(storytelling_mode: str) -> str:
    if storytelling_mode == "experience_first":
        return (
            "Default to a real-experience structure when possible: hook, repo/value card, user action or result, "
            "light technical proof, CTA. Visual text should be keywords only. If no user-provided demo media exists, "
            "fall back to README/code evidence cards instead of inventing an input/output demo."
        )
    return "Use the existing technical repo explainer storyboard structure."


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_string(item, fallback="") for item in value if _clean_string(item, fallback="")]
    cleaned = _clean_string(value, fallback="")
    return [cleaned] if cleaned else []


def _first_present(source: dict, *keys: str) -> object:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def _clean_string(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return fallback
    return _normalize_terms(str(value).replace("\r", " ").strip())


def _optional_string(value: object) -> str | None:
    cleaned = _clean_string(value, fallback="")
    return cleaned or None


def _optional_multiline_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        lines = [_clean_string(item, fallback="") for item in value]
        return "\n".join(line for line in lines if line) or None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return _optional_string(value)


def _safe_float(value: object, fallback: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _safe_int(value: object, fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _accent_from_value(value: object) -> str:
    text = _clean_string(value, fallback="")
    if len(text) == 7 and text.startswith("#"):
        try:
            red = int(text[1:3], 16)
            green = int(text[3:5], 16)
            blue = int(text[5:7], 16)
            return _normalize_accent(red, green, blue, text)
        except ValueError:
            pass
    return "#111827"


def _normalize_terms(text: str) -> str:
    return text.replace("READNE", "README").replace("Readne", "README").replace("readne", "README")


def _normalize_accent(red: int, green: int, blue: int, original: str) -> str:
    max_channel = max(red, green, blue)
    min_channel = min(red, green, blue)
    luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722
    is_neutral = max_channel - min_channel < 32
    is_warm = red > 210 and green < 165 and blue < 170
    is_purple = red > 130 and blue > 170 and green < 140
    if luminance < 105 or luminance > 235 or is_neutral or is_warm or is_purple:
        return "#58A6FF"
    return original


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
        elif not isinstance(item, dict):
            item = {"text": item}
        item = dict(item or {})
        text = _clean_string(item.get("text"), fallback="")
        if not text:
            continue
        kind = _clean_string(item.get("kind"), fallback="text")
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
                "emphasis": _optional_string(item.get("emphasis")),
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
        "result_media",
        "flow",
        "stack",
        "steps",
        "cta",
    }
    if isinstance(value, str) and value in allowed:
        return value
    return "text"


def _layout_from_values(layout: object, scene_type: object) -> str:
    if isinstance(layout, str):
        normalized = layout.strip().lower().replace("-", "_")
        aliases = {
            "repo": "github_hero",
            "repo_overview": "github_hero",
            "github": "github_hero",
            "github_repo": "github_hero",
            "readme": "readme_focus",
            "readme_card": "readme_focus",
            "feature": "feature_spotlight",
            "features": "feature_spotlight",
            "highlight": "feature_spotlight",
            "highlights": "feature_spotlight",
            "architecture": "architecture_map",
            "workflow": "architecture_map",
            "pipeline": "architecture_map",
            "evidence": "evidence_grid",
            "evidences": "evidence_grid",
            "terminal": "code",
            "usage": "code",
            "result": "result_media",
            "screenshot": "result_media",
            "media": "result_media",
            "outro": "cta",
            "ending": "cta",
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized in {
            "hook",
            "github_hero",
            "title",
            "text",
            "readme_focus",
            "feature_spotlight",
            "architecture_map",
            "evidence_grid",
            "code",
            "result_media",
            "flow",
            "stack",
            "steps",
            "cta",
        }:
            return normalized
    return _layout_from_type(scene_type)


def _animation_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "rise"
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "fade": "fade",
        "fade_in": "fade",
        "fade_out": "fade",
        "crossfade": "fade",
        "appear": "fade",
        "slide": "slide",
        "slide_up": "slide",
        "slide_down": "slide",
        "slide_in": "slide",
        "slide_left": "slide",
        "slide_right": "slide",
        "rise": "rise",
        "reveal": "rise",
        "stagger": "rise",
        "step_flow": "rise",
        "typewriter": "rise",
        "bounce": "rise",
        "pop": "rise",
        "spring": "rise",
        "zoom": "zoom",
        "zoom_in": "zoom",
        "zoom_out": "zoom",
        "none": "none",
        "static": "none",
    }
    return aliases.get(normalized, "rise")


def _asset_type_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "github": "github_repo_home",
        "github_repo": "github_repo_home",
        "repo_home": "github_repo_home",
        "repository": "github_repo_home",
        "readme": "readme_focus",
        "readme_card": "readme_focus",
        "none": "none",
        "": "none",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"github_repo_home", "readme_focus", "none"} else "none"


def _focus_target_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "repo": "repo_name",
        "repository": "repo_name",
        "repository_name": "repo_name",
        "repo_title": "repo_name",
        "readme": "readme_title",
        "title": "readme_title",
        "install": "install_command",
        "setup": "install_command",
        "section": "readme_section",
        "none": "none",
        "": "none",
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {"repo_name", "readme_title", "install_command", "readme_section", "none"}
    return normalized if normalized in allowed else "none"


def _mode_notes(video_mode: str) -> str:
    if video_mode == "short_30s":
        return "Use 4-5 scenes. Keep the first scene under 4s and skip deep code details."
    if video_mode == "technical_90s":
        return "Use 7-9 scenes. Add architecture/code detail only when evidence supports it."
    return "Use 5-7 scenes. Balance hook, repo overview, flow, highlights, and CTA."
