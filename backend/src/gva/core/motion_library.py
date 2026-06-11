from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from gva.config import Settings
from gva.models.storyboard import Scene, Storyboard


@dataclass(frozen=True)
class MotionLibraryAsset:
    id: str
    filename: str
    kind: str
    role: str
    tags: tuple[str, ...]
    layouts: tuple[str, ...]
    source_url: str | None = None
    fallback_path: str | None = None
    license: str = "user-provided"
    attribution: str = "user-provided"


@dataclass
class MotionLibraryResult:
    id: str
    filename: str
    status: str
    path: str | None = None
    reason: str | None = None


MAX_LOTTIE_BYTES = 800_000


DEFAULT_COMPLEX_MOTION_ASSETS: tuple[MotionLibraryAsset, ...] = ()


def download_default_motion_assets(
    settings: Settings,
    renderer_dir: Path,
    *,
    force: bool = False,
    allow_network: bool = True,
) -> list[MotionLibraryResult]:
    if not DEFAULT_COMPLEX_MOTION_ASSETS:
        return []
    return [
        download_motion_asset(asset, settings=settings, renderer_dir=renderer_dir, force=force, allow_network=allow_network)
        for asset in DEFAULT_COMPLEX_MOTION_ASSETS
    ]


def download_motion_asset(
    asset: MotionLibraryAsset,
    settings: Settings,
    renderer_dir: Path,
    *,
    force: bool = False,
    allow_network: bool = True,
) -> MotionLibraryResult:
    cache_dir = motion_cache_dir(settings)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / asset.filename
    if target.exists() and not force:
        _upsert_manifest_record(settings, asset, target)
        return MotionLibraryResult(asset.id, asset.filename, "skipped", str(target), "same-name file already exists")

    if allow_network and asset.source_url:
        try:
            _download_file(asset.source_url, target)
            _validate_motion_file(target, asset.kind)
            _upsert_manifest_record(settings, asset, target)
            return MotionLibraryResult(asset.id, asset.filename, "downloaded", str(target), asset.source_url)
        except Exception as exc:
            if target.exists():
                target.unlink(missing_ok=True)
            network_error = f"{exc.__class__.__name__}: {str(exc)[:240]}"
        else:
            network_error = None
    else:
        network_error = "network disabled"

    fallback = _resolve_fallback_path(renderer_dir, asset.fallback_path)
    if fallback and fallback.exists():
        shutil.copyfile(fallback, target)
        _validate_motion_file(target, asset.kind)
        _upsert_manifest_record(settings, asset, target)
        return MotionLibraryResult(asset.id, asset.filename, "copied", str(target), f"local fallback used; {network_error}")

    return MotionLibraryResult(asset.id, asset.filename, "failed", None, network_error)


def import_motion_asset(
    source: Path,
    settings: Settings,
    *,
    name: str | None = None,
    role: str = "side_illustration",
    tags: Iterable[str] = (),
    layouts: Iterable[str] = (),
    source_url: str | None = None,
    license_name: str = "user-provided",
) -> list[MotionLibraryResult]:
    source = source.resolve()
    if source.suffix.lower() == ".zip":
        return _import_motion_zip(source, settings, role=role, tags=tags, layouts=layouts, source_url=source_url, license_name=license_name)
    return [_import_motion_json(source, settings, name=name, role=role, tags=tags, layouts=layouts, source_url=source_url, license_name=license_name)]


def attach_motion_library_assets(
    storyboard: Storyboard,
    output_dir: Path,
    renderer_dir: Path,
    settings: Settings,
) -> Storyboard:
    records = _read_manifest(settings)
    if not records:
        return storyboard

    generated_dir = renderer_dir / "public" / "generated" / "motion"
    generated_dir.mkdir(parents=True, exist_ok=True)
    logs: list[dict] = []

    for scene in storyboard.scenes:
        visual = scene.visual
        if visual.layout in {"result_media", "cta"} or visual.motion_asset_path:
            continue
        record = _best_record_for_scene(scene, records)
        if record is None:
            continue
        source = Path(record["path"])
        if not source.exists():
            continue
        public_name = _public_motion_filename(record)
        public_path = generated_dir / public_name
        if not public_path.exists():
            shutil.copyfile(source, public_path)
        visual.motion_asset_kind = record.get("kind", "lottie")
        visual.motion_asset_path = f"generated/motion/{public_name}"
        visual.motion_role = record.get("role", "side_illustration")
        visual.motion_delay_ratio = _delay_for_role(visual.motion_role, visual.layout)
        logs.append(
            {
                "scene_id": scene.id,
                "layout": visual.layout,
                "motion_asset_id": record.get("id"),
                "motion_asset_path": visual.motion_asset_path,
                "motion_role": visual.motion_role,
            }
        )

    if logs:
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "motion-assets.json").write_text(
            json.dumps({"assets": logs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return storyboard


def list_motion_assets(settings: Settings) -> list[dict]:
    return _read_manifest(settings)


def motion_cache_dir(settings: Settings) -> Path:
    return settings.motion_cache_dir.resolve()


def _download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=35) as response:
        target.write_bytes(response.read())


def _import_motion_zip(
    source: Path,
    settings: Settings,
    *,
    role: str,
    tags: Iterable[str],
    layouts: Iterable[str],
    source_url: str | None,
    license_name: str,
) -> list[MotionLibraryResult]:
    results: list[MotionLibraryResult] = []
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".json"):
                continue
            data = archive.read(info)
            filename = Path(info.filename).name
            cache_target = motion_cache_dir(settings) / _safe_filename(filename)
            if cache_target.exists():
                results.append(MotionLibraryResult(_id_from_name(filename), filename, "skipped", str(cache_target), "same-name file already exists"))
                continue
            cache_target.parent.mkdir(parents=True, exist_ok=True)
            cache_target.write_bytes(data)
            try:
                _validate_motion_file(cache_target, "lottie")
            except Exception as exc:
                cache_target.unlink(missing_ok=True)
                results.append(MotionLibraryResult(_id_from_name(filename), filename, "failed", None, str(exc)))
                continue
            asset = MotionLibraryAsset(
                id=_id_from_name(filename),
                filename=cache_target.name,
                kind="lottie",
                role=role,
                tags=tuple(tags),
                layouts=tuple(layouts),
                source_url=source_url or str(source),
                license=license_name,
                attribution="user-provided",
            )
            _upsert_manifest_record(settings, asset, cache_target)
            results.append(MotionLibraryResult(asset.id, asset.filename, "imported", str(cache_target)))
    return results


def _import_motion_json(
    source: Path,
    settings: Settings,
    *,
    name: str | None,
    role: str,
    tags: Iterable[str],
    layouts: Iterable[str],
    source_url: str | None,
    license_name: str,
) -> MotionLibraryResult:
    if not source.exists():
        return MotionLibraryResult(_id_from_name(name or source.name), name or source.name, "failed", None, "source does not exist")
    filename = _safe_filename(name or source.name)
    if not filename.lower().endswith(".json"):
        filename = f"{filename}.json"
    target = motion_cache_dir(settings) / filename
    if target.exists():
        return MotionLibraryResult(_id_from_name(filename), filename, "skipped", str(target), "same-name file already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    try:
        _validate_motion_file(target, "lottie")
    except Exception as exc:
        target.unlink(missing_ok=True)
        return MotionLibraryResult(_id_from_name(filename), filename, "failed", None, str(exc))
    asset = MotionLibraryAsset(
        id=_id_from_name(filename),
        filename=filename,
        kind="lottie",
        role=role,
        tags=tuple(tags),
        layouts=tuple(layouts),
        source_url=source_url or str(source),
        license=license_name,
        attribution="user-provided",
    )
    _upsert_manifest_record(settings, asset, target)
    return MotionLibraryResult(asset.id, asset.filename, "imported", str(target))


def _validate_motion_file(path: Path, kind: str) -> None:
    if kind == "svg":
        if not path.read_text(encoding="utf-8", errors="ignore").lstrip().startswith("<svg"):
            raise ValueError("SVG motion asset must start with <svg")
        return
    if kind != "lottie":
        raise ValueError(f"Unsupported motion asset kind: {kind}")
    if path.stat().st_size > MAX_LOTTIE_BYTES:
        raise ValueError(f"Lottie JSON is too large; keep complex motion assets under {MAX_LOTTIE_BYTES // 1000}KB")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = ("v", "fr", "w", "h", "layers")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"Not a valid Lottie JSON; missing: {', '.join(missing)}")
    if not isinstance(payload.get("layers"), list) or not payload["layers"]:
        raise ValueError("Lottie JSON must contain non-empty layers")
    background_issue = _lottie_background_issue(payload)
    if background_issue:
        raise ValueError(background_issue)


def _upsert_manifest_record(settings: Settings, asset: MotionLibraryAsset, path: Path) -> None:
    cache_dir = motion_cache_dir(settings)
    cache_dir.mkdir(parents=True, exist_ok=True)
    records = _read_manifest(settings)
    next_record = {
        **asdict(asset),
        "tags": list(asset.tags),
        "layouts": list(asset.layouts),
        "path": str(path),
        "sha256": _sha256(path),
    }
    records = [record for record in records if record.get("filename") != asset.filename and record.get("id") != asset.id]
    records.append(next_record)
    _manifest_path(settings).write_text(json.dumps({"assets": records}, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_manifest(settings: Settings) -> list[dict]:
    path = _manifest_path(settings)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [record for record in payload.get("assets", []) if isinstance(record, dict)]


def _manifest_path(settings: Settings) -> Path:
    return motion_cache_dir(settings) / "manifest.json"


def _best_record_for_scene(scene: Scene, records: list[dict]) -> dict | None:
    candidates = []
    for record in records:
        layouts = set(record.get("layouts") or [])
        tags = set(record.get("tags") or [])
        score = 0
        if scene.visual.layout in layouts:
            score += 10
        score += _tag_score(scene.visual.layout, tags)
        if record.get("kind") == "lottie":
            score += 2
        if record.get("role") == "side_illustration":
            score += 1
        if score > 0:
            candidates.append((score, record))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _tag_score(layout: str, tags: set[str]) -> int:
    wanted = {
        "github_hero": {"repo", "dashboard", "developer", "interface"},
        "hook": {"repo", "dashboard", "developer", "interface"},
        "architecture_map": {"data", "flow", "pipeline", "network"},
        "flow": {"data", "flow", "pipeline", "network"},
        "code": {"code", "developer", "implementation"},
        "readme_focus": {"readme", "search", "evidence", "signal"},
        "evidence_grid": {"readme", "search", "evidence", "signal"},
        "feature_spotlight": {"dashboard", "interface", "developer"},
        "stack": {"code", "developer", "implementation"},
        "steps": {"code", "developer", "implementation"},
        "title": {"dashboard", "interface", "developer"},
        "text": {"dashboard", "interface", "developer"},
    }.get(layout, set())
    return len(wanted & tags)


def _lottie_background_issue(payload: dict) -> str | None:
    width = _number(payload.get("w"))
    height = _number(payload.get("h"))
    if width <= 0 or height <= 0:
        return None
    for layer in payload.get("layers", []):
        if not isinstance(layer, dict) or _layer_opacity(layer) < 18:
            continue
        if _solid_layer_covers_canvas(layer, width, height):
            return "Rejected Lottie: contains an opaque solid layer that covers most of the canvas"
        if _shape_layer_has_large_rect(layer, width, height):
            return "Rejected Lottie: contains a large rectangle background that would show as a visible color block"
    return None


def _solid_layer_covers_canvas(layer: dict, width: float, height: float) -> bool:
    if layer.get("ty") != 1:
        return False
    layer_width = _number(layer.get("sw"))
    layer_height = _number(layer.get("sh"))
    return layer_width >= width * 0.74 and layer_height >= height * 0.74


def _shape_layer_has_large_rect(layer: dict, width: float, height: float) -> bool:
    if layer.get("ty") != 4:
        return False
    for shape in _iter_shapes(layer.get("shapes")):
        if not isinstance(shape, dict) or shape.get("ty") != "rc":
            continue
        rect_width, rect_height = _size_pair(shape.get("s"))
        if rect_width >= width * 0.74 and rect_height >= height * 0.74:
            return True
    return False


def _iter_shapes(shapes: object):
    if not isinstance(shapes, list):
        return
    for shape in shapes:
        yield shape
        if isinstance(shape, dict):
            nested = shape.get("it") or shape.get("shapes")
            if isinstance(nested, list):
                yield from _iter_shapes(nested)


def _layer_opacity(layer: dict) -> float:
    transform = layer.get("ks")
    if isinstance(transform, dict):
        return _animated_value(transform.get("o"), 100)
    return 100


def _animated_value(value: object, default: float) -> float:
    if isinstance(value, dict):
        return _animated_value(value.get("k"), default)
    if isinstance(value, list) and value:
        return _animated_value(value[0], default)
    return _number(value, default)


def _size_pair(value: object) -> tuple[float, float]:
    if isinstance(value, dict):
        return _size_pair(value.get("k"))
    if isinstance(value, list) and len(value) >= 2:
        return _number(value[0]), _number(value[1])
    return 0, 0


def _number(value: object, default: float = 0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _delay_for_role(role: str, layout: str) -> float:
    if role == "hero_background":
        return 0.18
    if layout in {"hook", "github_hero"}:
        return 0.34
    if layout == "cta":
        return 0.32
    return 0.46


def _public_motion_filename(record: dict) -> str:
    filename = _safe_filename(str(record.get("filename") or "motion.json"))
    digest = str(record.get("sha256") or "")[:10]
    if not digest:
        return filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".json"
    return f"{stem}-{digest}{suffix}"


def _resolve_fallback_path(renderer_dir: Path, fallback_path: str | None) -> Path | None:
    if not fallback_path:
        return None
    path = Path(fallback_path)
    if path.is_absolute():
        return path
    return renderer_dir / path


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value.strip())
    return cleaned.strip(".-") or "motion.json"


def _id_from_name(value: str) -> str:
    return Path(_safe_filename(value)).stem.replace(".", "-").lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
