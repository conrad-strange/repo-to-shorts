import json
from pathlib import Path

from openai import BadRequestError

from gva.config import Settings
from gva.core.json_utils import loads_json_object
from gva.core.llm_client import build_openai_client, get_generation_model
from gva.core.visible_text import clean_visible_text, clean_visible_text_list, compact_github_repo_handle
from gva.models.script import VideoScript
from gva.models.storyboard import Storyboard


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "storyboard_writer.md"


def write_storyboard(script: VideoScript, settings: Settings, user_brief: str | None = None) -> Storyboard:
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
                    "brand_mode": settings.brand_mode,
                    "brand_notes": _brand_notes(settings.brand_mode),
                    "storytelling_mode": settings.storytelling_mode,
                    "storytelling_notes": _storytelling_notes(settings.storytelling_mode),
                    "user_brief": user_brief or "",
                    "user_brief_rules": (
                        "Treat user_brief as a high-priority signal for scene emphasis, rhythm, visual priorities, and ordering. "
                        "If a requested emphasis is supported by the video_script or evidence, reflect it in at least one scene field "
                        "(headline, caption, bullets, micro_beats, or scene order). "
                        "Do not add unsupported facts, claims, features, commands, or demo behavior. "
                        "For setup/install/onboarding convenience requests, use short visual keywords like easy onboarding or clear entry points; "
                        "do not show specific install commands."
                    ),
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
        visual["headline"] = _clean_visible_string(
            _first_present(visual, "headline", "title") or _first_present(scene, "headline", "title"),
            fallback="",
            limit=36,
        )
        visual["bullets"] = _visible_string_list(
            _first_present(visual, "bullets", "items") or _first_present(scene, "bullets", "items"),
            limit=28,
        )
        visual["diagram_nodes"] = _visible_string_list(
            _first_present(visual, "diagram_nodes", "diagramNodes", "nodes")
            or _first_present(scene, "diagram_nodes", "diagramNodes", "nodes"),
            limit=42,
        )
        visual["icons"] = _string_list(_first_present(visual, "icons", "icon"))
        visual["micro_beats"] = _sanitize_micro_beats(visual.get("micro_beats"), visual)
        visual["caption"] = _optional_visible_string(_first_present(visual, "caption", "subtitle"), limit=42)
        visual["code"] = _optional_multiline_string(_first_present(visual, "code", "codeSnippet") or scene.get("codeSnippet"))
        visual["accent_color"] = _accent_from_value(visual.get("accent_color"))
        visual["animation"] = _animation_from_value(_first_present(visual, "animation", "motion") or scene.get("animation"))
        visual["asset_type"] = _asset_type_from_value(_first_present(visual, "asset_type", "assetType"))
        visual["asset_path"] = _optional_string(_first_present(visual, "asset_path", "assetPath"))
        visual["focus_target"] = _focus_target_from_value(_first_present(visual, "focus_target", "focusTarget"))
        visual["repo_url"] = _optional_string(_first_present(visual, "repo_url", "repoUrl"))
        visual["repo_display_url"] = _optional_repo_display(_first_present(visual, "repo_display_url", "repoDisplayUrl"))
        visual["evidence_refs"] = _string_list(_first_present(visual, "evidence_refs", "evidenceRefs"))
        visual["motion_asset"] = _motion_asset_from_value(
            _first_present(visual, "motion_asset", "motionAsset", "lottie_asset", "lottieAsset")
        )
        visual["motion_asset_kind"] = _motion_asset_kind_from_value(
            _first_present(visual, "motion_asset_kind", "motionAssetKind")
        )
        visual["motion_asset_path"] = _optional_string(
            _first_present(visual, "motion_asset_path", "motionAssetPath", "lottie_path", "lottiePath")
        )
        visual["motion_role"] = _motion_role_from_value(_first_present(visual, "motion_role", "motionRole"))
        visual["motion_delay_ratio"] = _safe_ratio(
            _first_present(visual, "motion_delay_ratio", "motionDelayRatio"),
            0.54,
            lower=0.0,
            upper=0.9,
        )
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


def _visible_string_list(value: object, limit: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return clean_visible_text_list(
            [str(item).strip() for item in value if not isinstance(item, (dict, list))],
            limit=limit,
        )
    if isinstance(value, (dict, list)):
        return []
    text = clean_visible_text(value, limit=limit)
    return [text] if text else []


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


def _clean_visible_string(value: object, fallback: str = "", limit: int | None = None) -> str:
    return clean_visible_text(value, limit=limit) or fallback


def _optional_string(value: object) -> str | None:
    cleaned = _clean_string(value, fallback="")
    return cleaned or None


def _optional_repo_display(value: object) -> str | None:
    cleaned = _optional_string(value)
    if not cleaned:
        return None
    return compact_github_repo_handle(cleaned) or cleaned


def _optional_visible_string(value: object, limit: int | None = None) -> str | None:
    return clean_visible_text(value, limit=limit)


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


def _safe_ratio(value: object, fallback: float, lower: float, upper: float) -> float:
    return min(max(_safe_float(value, fallback), lower), upper)


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
        text = clean_visible_text(item.get("text"), limit=28) or ""
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


def _motion_asset_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "flow": "data_flow",
        "pipeline": "data_flow",
        "architecture": "data_flow",
        "circuit": "data_flow",
        "terminal": "code_scan",
        "code": "code_scan",
        "scan": "code_scan",
        "readme": "evidence_pulse",
        "evidence": "evidence_pulse",
        "proof": "evidence_pulse",
        "github": "repo_pulse",
        "repo": "repo_pulse",
        "star": "spark_burst",
        "cta": "spark_burst",
        "none": "none",
        "": "none",
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {"data_flow", "code_scan", "evidence_pulse", "repo_pulse", "spark_burst", "none"}
    return normalized if normalized in allowed else "none"


def _motion_asset_kind_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    return normalized if normalized in {"svg", "lottie", "none"} else "none"


def _motion_role_from_value(value: object) -> str:
    if not isinstance(value, str):
        return "accent"
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "side": "side_illustration",
        "illustration": "side_illustration",
        "background": "hero_background",
        "hero": "hero_background",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"accent", "side_illustration", "hero_background"} else "accent"


def _mode_notes(video_mode: str) -> str:
    if video_mode == "short_30s":
        return (
            "Use 4-5 fast scenes. Match scene durations to narration; do not create long holds. "
            "Keep the first scene under 4s and skip deep code details."
        )
    if video_mode == "technical_90s":
        return (
            "Use 7-9 fast but information-rich scenes. The 90s length must come from richer voiceover and evidence-backed detail, "
            "not empty visual padding."
        )
    return (
        "Use 5-7 fast scenes. The 60s length must come from about 60s of voiceover, with only brief transition holds. "
        "Balance hook, repo overview, flow, highlights, and CTA."
    )


def _brand_notes(brand_mode: str) -> str:
    if str(brand_mode).strip().lower() in {"rb", "repo-to-bombs", "bomb", "bombs"}:
        return "Entertainment mode may use a more playful opener, but still keeps evidence-backed content."
    return (
        "R2S should feel like a polished developer short video: high-energy, tight cuts, strong hook, "
        "short visual keywords, and no slow PPT-like pauses."
    )
