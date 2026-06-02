from __future__ import annotations

import json
import hashlib
import base64
import binascii
import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from git.exc import GitCommandError
from pydantic import BaseModel, Field

from gva.config import Settings
from gva.core.runs import allocate_run, list_run_ids, resolve_run_dir
from gva.core.tts import _synthesize_edge_tts
from gva.models.storyboard import Storyboard
from gva.web.jobs import JobManager
from gva.workflow import run_render_workflow

VideoMode = Literal["short_30s", "standard_60s", "technical_90s"]
RenderProfile = Literal["draft", "preview", "final"]
BrandMode = Literal["rs", "rb"]


class WorkflowRequest(BaseModel):
    repo_url: str
    output_name: str | None = None
    out_dir: str | None = None
    video_mode: VideoMode = "short_30s"
    render_strategy: str = "remotion-primary"
    render_profile: RenderProfile = "preview"
    brand_mode: BrandMode = "rs"
    bomb_circle: str = "科技圈"
    bomb_again_count: int = Field(default=1, ge=1, le=8)
    tts_voice: str | None = None
    dry_run: bool = False
    auto_repair: bool = True
    allow_unverified: bool = False
    force_insight: bool = False
    force_script: bool = False
    force_storyboard: bool = False
    force_tts: bool = False
    force_render: bool = False
    remotion_concurrency: int | None = Field(default=None, ge=1, le=32)


class StoryboardUpdateRequest(BaseModel):
    storyboard: dict[str, Any]
    activate: bool = True


class RerenderRequest(BaseModel):
    render_profile: RenderProfile | None = None
    brand_mode: BrandMode | None = None
    bomb_circle: str | None = None
    bomb_again_count: int | None = Field(default=None, ge=1, le=8)
    tts_voice: str | None = None
    remotion_concurrency: int | None = Field(default=None, ge=1, le=32)
    allow_unverified: bool = False
    storyboard: dict[str, Any] | None = None


class RerenderJobRequest(RerenderRequest):
    project_id: str
    run_id: str


class TtsPreviewRequest(BaseModel):
    voice: str
    text: str = "今天来介绍一个 GitHub 项目。"
    rate: str | None = None


class UserImageAssetRequest(BaseModel):
    filename: str
    data_url: str


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Repo to Shorts API", version="0.1.0")
    job_manager = JobManager(max_workers=int(os.getenv("GVA_WEB_MAX_JOBS", "1")))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "请求参数不完整，请检查 GitHub 链接和生成配置。"})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler_zh(_request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "请求参数不完整，请检查 GitHub 链接和生成配置。"})

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/system")
    def system_status() -> dict[str, Any]:
        settings = Settings()
        return {
            "node": _node_status(settings),
            "tools": {
                "renderer_dir": str(settings.renderer_dir.resolve()),
                "frontend_dir": str(settings.frontend_dir.resolve()),
                "outputs_dir": str(settings.outputs_dir.resolve()),
                "ffmpeg_exe": _path_status(settings.ffmpeg_exe),
                "chrome_exe": _path_status(settings.chrome_exe),
            },
            "vite": {
                "required": "Node.js 20.19+ or 22.12+",
                "note": "Use the project portable Node when PATH points to an older or blocked Node.",
            },
        }

    @app.get("/api/projects")
    def projects() -> dict[str, Any]:
        settings = Settings()
        outputs_dir = settings.outputs_dir.resolve()
        outputs_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for path in sorted(outputs_dir.iterdir()):
            if not path.is_dir() or path.name == "generated":
                continue
            items.append(
                {
                    "id": path.name,
                    "path": str(path),
                    "runs": list_run_ids(path),
                }
            )
        return {"projects": items}

    @app.post("/api/tts/preview")
    def tts_preview(request: TtsPreviewRequest) -> dict[str, Any]:
        settings = Settings()
        voice = request.voice.strip() or settings.tts_voice
        text = request.text.strip() or "今天来介绍一个 GitHub 项目。"
        rate = request.rate or settings.tts_rate
        preview_dir = (settings.repo_cache_dir.resolve().parent / "tts-preview").resolve()
        preview_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:16]
        audio_path = preview_dir / f"{digest}.mp3"
        try:
            _synthesize_edge_tts(text, audio_path, voice, rate)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"TTS 试听生成失败：{exc.__class__.__name__}。") from exc
        return {
            "audio": f"/api/tts/preview/files/{audio_path.name}",
            "voice": voice,
            "text": text,
            "rate": rate,
        }

    @app.get("/api/tts/preview/files/{filename}")
    def tts_preview_file(filename: str) -> FileResponse:
        settings = Settings()
        preview_dir = (settings.repo_cache_dir.resolve().parent / "tts-preview").resolve()
        target = (preview_dir / filename).resolve()
        if not target.is_relative_to(preview_dir) or not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="试听音频不存在。")
        return FileResponse(target, media_type="audio/mpeg")

    @app.post("/api/projects")
    def create_project(request: WorkflowRequest) -> dict[str, Any]:
        try:
            return _run_workflow_payload(request)
        except Exception as exc:
            raise _workflow_http_error(exc) from exc

    @app.post("/api/jobs")
    def create_job(request: WorkflowRequest) -> dict[str, Any]:
        _validate_workflow_request(request)
        job = job_manager.create()

        def target() -> None:
            try:
                result = _run_workflow_payload(
                    request,
                    progress_callback=lambda event: job_manager.emit(job.id, "progress", **event),
                )
            except Exception as exc:
                http_error = _workflow_http_error(exc)
                job_manager.fail(job.id, str(http_error.detail), http_error.status_code)
                return
            job_manager.succeed(job.id, result)

        job_manager.start(job.id, target)
        snapshot = job_manager.snapshot(job.id)
        if not snapshot:
            raise HTTPException(status_code=500, detail="后台任务创建失败。")
        return snapshot

    @app.get("/api/jobs")
    def jobs() -> dict[str, Any]:
        return {"jobs": job_manager.list_snapshots()}

    @app.post("/api/jobs/rerender")
    def create_rerender_job(request: RerenderJobRequest) -> dict[str, Any]:
        job = job_manager.create()

        def target() -> None:
            try:
                result = _rerender_payload(
                    request.project_id,
                    request.run_id,
                    request,
                    progress_callback=lambda event: job_manager.emit(job.id, "progress", **event),
                )
            except Exception as exc:
                http_error = _workflow_http_error(exc)
                job_manager.fail(job.id, str(http_error.detail), http_error.status_code)
                return
            job_manager.succeed(job.id, result)

        job_manager.start(job.id, target)
        snapshot = job_manager.snapshot(job.id)
        if not snapshot:
            raise HTTPException(status_code=500, detail="后台任务创建失败。")
        return snapshot

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: str) -> dict[str, Any]:
        snapshot = job_manager.snapshot(job_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="任务不存在。")
        return snapshot

    @app.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str) -> StreamingResponse:
        if not job_manager.exists(job_id):
            raise HTTPException(status_code=404, detail="任务不存在。")
        return StreamingResponse(job_manager.event_stream(job_id), media_type="text/event-stream")

    @app.get("/api/projects/{project_id}/runs")
    def runs(project_id: str) -> dict[str, Any]:
        project_root = _project_root(project_id)
        return {"project_id": project_id, "runs": list_run_ids(project_root)}

    @app.get("/api/projects/{project_id}/runs/{run_id}")
    def run_detail(project_id: str, run_id: str) -> dict[str, Any]:
        project_root = _project_root(project_id)
        return _run_payload(project_id, run_id, project_root)

    @app.get("/api/projects/{project_id}/runs/{run_id}/storyboard")
    def get_storyboard(project_id: str, run_id: str) -> dict[str, Any]:
        run_dir = _run_dir(project_id, run_id)
        path = _first_existing(
            run_dir / "storyboard.edited.json",
            run_dir / "storyboard.final.json",
            run_dir / "storyboard.json",
            run_dir / "storyboard-timed.json",
        )
        if not path:
            raise HTTPException(status_code=404, detail="Storyboard not found.")
        return {"path": str(path), "storyboard": _read_json(path)}

    @app.put("/api/projects/{project_id}/runs/{run_id}/storyboard")
    def update_storyboard(project_id: str, run_id: str, request: StoryboardUpdateRequest) -> dict[str, Any]:
        run_dir = _run_dir(project_id, run_id)
        storyboard = Storyboard.model_validate(request.storyboard)
        edited_path = run_dir / "storyboard.edited.json"
        edited_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        if request.activate:
            (run_dir / "storyboard.json").write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
            (run_dir / "storyboard.final.json").write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        return {"saved": True, "path": str(edited_path), "activated": request.activate}

    @app.post("/api/projects/{project_id}/runs/{run_id}/assets/user-image")
    def upload_user_image(project_id: str, run_id: str, request: UserImageAssetRequest) -> dict[str, Any]:
        run_dir = _run_dir(project_id, run_id)
        return _save_user_image_asset(run_dir, request)

    @app.post("/api/projects/{project_id}/runs/{run_id}/rerender")
    def rerender(project_id: str, run_id: str, request: RerenderRequest) -> dict[str, Any]:
        return _rerender_payload(project_id, run_id, request)

    @app.get("/api/projects/{project_id}/runs/{run_id}/files/{artifact_path:path}")
    def run_file(project_id: str, run_id: str, artifact_path: str) -> FileResponse:
        run_dir = _run_dir(project_id, run_id)
        target = (run_dir / artifact_path).resolve()
        if not target.is_relative_to(run_dir.resolve()) or not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        return FileResponse(target)

    _mount_frontend(app, frontend_dist or _default_frontend_dist())
    return app


def _validate_workflow_request(request: WorkflowRequest) -> None:
    repo_error = _validate_repo_url(request.repo_url)
    if repo_error:
        raise HTTPException(status_code=400, detail=repo_error)
    output_error = _validate_output_name(request.output_name)
    if output_error:
        raise HTTPException(status_code=400, detail=output_error)


def _settings_from_request(request: WorkflowRequest) -> Settings:
    settings = Settings()
    settings.video_mode = request.video_mode
    settings.render_strategy = request.render_strategy
    settings.render_profile = request.render_profile
    settings.brand_mode = request.brand_mode
    settings.bomb_circle = request.bomb_circle
    settings.bomb_again_count = request.bomb_again_count
    if request.tts_voice:
        settings.tts_voice = request.tts_voice
    settings.repair_enabled = request.auto_repair
    settings.remotion_concurrency = request.remotion_concurrency
    return settings


def _run_workflow_payload(
    request: WorkflowRequest,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _validate_workflow_request(request)
    settings = _settings_from_request(request)
    root_output_dir = _resolve_output_root(request, settings)
    result = run_render_workflow(
        project_path=None,
        repo_url=request.repo_url,
        output_dir=root_output_dir,
        settings=settings,
        dry_run=request.dry_run,
        force_insight=request.force_insight,
        force_script=request.force_script,
        force_storyboard=request.force_storyboard,
        force_tts=request.force_tts,
        force_render=request.force_render,
        allow_unverified=request.allow_unverified,
        progress_callback=progress_callback,
    )
    project_id = root_output_dir.resolve().name
    run_id = str(result.metadata.get("run_id") or result.output_dir.name)
    return _run_payload(project_id, run_id, root_output_dir)


def _rerender_payload(
    project_id: str,
    run_id: str,
    request: RerenderRequest,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    source_run_dir = _run_dir(project_id, run_id)
    metadata = _read_json(source_run_dir / "workflow-metadata.json")
    if not metadata:
        raise HTTPException(status_code=400, detail="workflow-metadata.json is required to rerender.")

    settings = Settings()
    settings.video_mode = metadata.get("video_mode", settings.video_mode)
    settings.render_strategy = metadata.get("render_strategy", settings.render_strategy)
    settings.render_profile = request.render_profile or metadata.get("render_profile", "preview")
    settings.brand_mode = request.brand_mode or metadata.get("brand_mode", settings.brand_mode)
    settings.bomb_circle = request.bomb_circle or metadata.get("bomb_circle", settings.bomb_circle)
    settings.bomb_again_count = request.bomb_again_count or metadata.get("bomb_again_count", settings.bomb_again_count)
    settings.tts_voice = request.tts_voice or metadata.get("tts_voice", settings.tts_voice)
    settings.remotion_concurrency = request.remotion_concurrency or metadata.get("remotion_concurrency")

    root_output_dir = Path(metadata.get("root_output_dir", _project_root(project_id))).resolve()
    new_run = allocate_run(root_output_dir)
    new_run_dir = new_run.run_dir
    _seed_rerender_run(source_run_dir, new_run_dir, request.storyboard)

    repo_url = metadata.get("repo_url")
    project_path = None if repo_url else Path(metadata["project_path"]) if metadata.get("project_path") else None
    result = run_render_workflow(
        project_path=project_path,
        repo_url=repo_url,
        output_dir=root_output_dir,
        settings=settings,
        dry_run=False,
        force_tts=True,
        force_render=True,
        allow_unverified=request.allow_unverified,
        run_id=new_run.run_id,
        progress_callback=progress_callback,
    )
    _mark_edited_rerender(result.output_dir, source_run_id=run_id)
    return _run_payload(project_id, str(result.metadata.get("run_id") or new_run.run_id), root_output_dir)


def _seed_rerender_run(source_run_dir: Path, target_run_dir: Path, storyboard_payload: dict[str, Any] | None) -> None:
    target_run_dir.mkdir(parents=True, exist_ok=True)
    for name in ["project-insight.json", "video-script.json", "script.md"]:
        source = source_run_dir / name
        if source.exists():
            shutil.copyfile(source, target_run_dir / name)

    assets_dir = source_run_dir / "assets"
    if assets_dir.exists():
        shutil.copytree(assets_dir, target_run_dir / "assets", dirs_exist_ok=True)

    if storyboard_payload is not None:
        storyboard = Storyboard.model_validate(storyboard_payload)
    else:
        source_storyboard = _first_existing(
            source_run_dir / "storyboard.edited.json",
            source_run_dir / "storyboard.final.json",
            source_run_dir / "storyboard.json",
        )
        if source_storyboard is None:
            raise HTTPException(status_code=400, detail="Storyboard is required to rerender.")
        storyboard = Storyboard.model_validate_json(source_storyboard.read_text(encoding="utf-8"))

    serialized = storyboard.model_dump_json(indent=2)
    for name in ["storyboard.edited.json", "storyboard.json", "storyboard.final.json"]:
        (target_run_dir / name).write_text(serialized, encoding="utf-8")

    logs_dir = target_run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "web-edited-storyboard.json").write_text(
        json.dumps({"source_run_dir": str(source_run_dir), "preserve_user_edits": True}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _mark_edited_rerender(run_dir: Path, source_run_id: str) -> None:
    metadata_path = run_dir / "workflow-metadata.json"
    metadata = _read_json(metadata_path) or {}
    metadata["run_type"] = "edited_rerender"
    metadata["source_run_id"] = source_run_id
    metadata["storyboard_source"] = "web_editor"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_user_image_asset(run_dir: Path, request: UserImageAssetRequest) -> dict[str, Any]:
    match = re.match(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", request.data_url, re.IGNORECASE | re.DOTALL)
    if not match:
        raise HTTPException(status_code=400, detail="请上传 PNG、JPG 或 WebP 图片。")
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="图片数据无法解析。") from exc
    if len(payload) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片太大，请上传 8MB 以内的图片。")

    mime = match.group(1).lower().replace("jpg", "jpeg")
    digest = hashlib.sha1(payload).hexdigest()[:16]
    filename = f"result-{digest}.png"
    output_dir = run_dir / "assets" / "user"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    if not _write_resized_png(payload, target):
        suffix = ".jpg" if mime == "image/jpeg" else f".{mime.split('/')[-1]}"
        filename = f"result-{digest}{suffix}"
        target = output_dir / filename
        target.write_bytes(payload)

    public_target = Settings().renderer_dir.resolve() / "public" / "generated" / "assets" / "user" / filename
    public_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, public_target)
    return {
        "asset_path": f"generated/assets/user/{filename}",
        "run_asset_path": str(target),
        "bytes": target.stat().st_size,
    }


def _write_resized_png(payload: bytes, target: Path) -> bool:
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(payload)) as image:
            image = image.convert("RGB")
            image.thumbnail((1280, 1280))
            image.save(target, format="PNG", optimize=True)
            return True
    except Exception:
        return False


def _resolve_output_root(request: WorkflowRequest, settings: Settings) -> Path:
    if request.out_dir:
        return Path(request.out_dir).resolve()
    name = request.output_name.strip() if request.output_name else _slug_from_source(request.repo_url or "demo")
    return (settings.outputs_dir / name).resolve()


def _slug_from_source(source: str) -> str:
    cleaned = source.rstrip("/").replace("\\", "/").split("/")[-1] or "demo"
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", cleaned).strip("-") or "demo"


def _project_root(project_id: str) -> Path:
    safe_id = _slug_from_source(project_id)
    root = (Settings().outputs_dir / safe_id).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {safe_id}")
    return root


def _run_dir(project_id: str, run_id: str) -> Path:
    try:
        return resolve_run_dir(_project_root(project_id), run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _run_payload(project_id: str, run_id: str, project_root: Path) -> dict[str, Any]:
    run_dir = resolve_run_dir(project_root, run_id)
    metadata = _read_json(run_dir / "workflow-metadata.json") or {}
    storyboard = _read_json(
        _first_existing(run_dir / "storyboard.edited.json", run_dir / "storyboard.final.json", run_dir / "storyboard.json")
    )
    return {
        "project_id": project_id,
        "run_id": run_id,
        "project_root": str(project_root),
        "run_dir": str(run_dir),
        "metadata": metadata,
        "repo_summary": _read_json(run_dir / "repo-summary.json"),
        "script_markdown": _read_text(run_dir / "script.md"),
        "storyboard": storyboard,
        "verification": _read_json(run_dir / "verification-report.json"),
        "evaluation": _read_json(run_dir / "evaluation-report.json"),
        "files": _artifact_urls(project_id, run_id, run_dir),
    }


def _artifact_urls(project_id: str, run_id: str, run_dir: Path) -> dict[str, str | None]:
    candidates = {
        "video": run_dir / "video.mp4",
        "preview_grid": run_dir / "preview_frames" / "preview_grid.jpg",
        "script": run_dir / "script.md",
        "demo_report": run_dir / "demo_report.md",
        "subtitles_srt": run_dir / "subtitles.srt",
        "subtitles_vtt": run_dir / "subtitles.vtt",
    }
    return {
        name: f"/api/projects/{project_id}/runs/{run_id}/files/{path.relative_to(run_dir).as_posix()}"
        if path.exists()
        else None
        for name, path in candidates.items()
    }


def _read_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _first_existing(*paths: Path | None) -> Path | None:
    return next((path for path in paths if path and path.exists()), None)


def _node_status(settings: Settings) -> dict[str, Any]:
    candidates = []
    if settings.node_exe:
        candidates.append(settings.node_exe)
    candidates.extend(sorted(Path(".tools").glob("node-*-win-x64/node.exe")))
    candidates.append(Path("node"))

    results = []
    recommended = None
    for candidate in candidates:
        version, error = _run_version(candidate)
        ok = _node_version_ok_for_vite(version)
        if ok and recommended is None and candidate != Path("node"):
            recommended = str(candidate.resolve())
        results.append(
            {
                "path": str(candidate),
                "version": version,
                "ok_for_vite": ok,
                "error": error,
            }
        )
    return {
        "recommended_node_exe": recommended,
        "candidates": results,
    }


def _run_version(executable: Path) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            [str(executable), "-v"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return None, output or f"exit code {completed.returncode}"
    return output, None


def _node_version_ok_for_vite(version: str | None) -> bool:
    if not version:
        return False
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return False
    major, minor, _patch = (int(part) for part in match.groups())
    return major > 22 or (major == 22 and minor >= 12) or (major == 20 and minor >= 19)


def _path_status(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"configured": False, "exists": False, "path": None}
    resolved = path.resolve()
    return {"configured": True, "exists": resolved.exists(), "path": str(resolved)}


def _is_github_repo_url(url: str) -> bool:
    return _validate_repo_url(url) == ""


def _validate_repo_url(url: str | None) -> str:
    value = (url or "").strip()
    if not value:
        return "请输入 GitHub 仓库链接。"
    if re.search(r"\s", value):
        return "仓库链接不能包含空格。"
    if re.search(r"[<>{}\[\]|\\^`\"'，。；：]", value):
        return "仓库链接包含非法字符，请粘贴完整 GitHub URL。"
    if not value.lower().startswith("https://github.com/"):
        return "请输入以 https://github.com/ 开头的公开仓库链接。"
    if not re.match(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$", value, re.I):
        return "链接格式应为 https://github.com/owner/repo。"
    return ""


def _validate_output_name(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return "输出名不能为空。"
    if not re.match(r"^[A-Za-z0-9._-]+$", cleaned):
        return "输出名只能包含字母、数字、点、下划线和短横线。"
    return ""


def _workflow_http_error(exc: Exception) -> HTTPException:
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, GitCommandError):
        if any(token in lowered for token in ["repository not found", "not found", "authentication failed"]):
            return HTTPException(
                status_code=404,
                detail="没有找到这个公开 GitHub 仓库。请检查链接是否正确，或确认仓库不是私有仓库。",
            )
        return HTTPException(
            status_code=502,
            detail="访问 GitHub 仓库失败。请检查网络连接，稍后重试。",
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc) or "输入参数不合法。")
    if any(token in lowered for token in ["github", "git fetch", "git clone", "network", "timeout"]):
        return HTTPException(status_code=502, detail="访问 GitHub 或同步仓库失败。请检查网络连接后重试。")
    return HTTPException(status_code=500, detail=f"生成流程出现内部错误：{exc.__class__.__name__}。")


def _validate_repo_url(url: str | None) -> str:
    value = (url or "").strip()
    if not value:
        return "请输入 GitHub 仓库链接。"
    if re.search(r"\s", value):
        return "仓库链接不能包含空格。"
    if re.search(r"[<>{}\[\]|\\^`\"'，。；：]", value):
        return "仓库链接包含非法字符，请粘贴完整 GitHub URL。"
    if not value.lower().startswith("https://github.com/"):
        return "请输入以 https://github.com/ 开头的公开仓库链接。"
    if not re.match(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$", value, re.I):
        return "链接格式应为 https://github.com/owner/repo。"
    return ""


def _validate_output_name(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return "输出名不能为空。"
    if not re.match(r"^[A-Za-z0-9._-]+$", cleaned):
        return "输出名只能包含字母、数字、点、下划线和短横线。"
    return ""


def _workflow_http_error(exc: Exception) -> HTTPException:
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, GitCommandError):
        if any(token in lowered for token in ["repository not found", "not found", "authentication failed"]):
            return HTTPException(
                status_code=404,
                detail="没有找到这个公开 GitHub 仓库。请检查链接是否正确，或确认仓库不是私有仓库。",
            )
        return HTTPException(status_code=502, detail="访问 GitHub 仓库失败。请检查网络连接，稍后重试。")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc) or "输入参数不合法。")
    if any(token in lowered for token in ["github", "git fetch", "git clone", "network", "timeout"]):
        return HTTPException(status_code=502, detail="访问 GitHub 或同步仓库失败。请检查网络连接后重试。")
    return HTTPException(status_code=500, detail=f"生成流程出现内部错误：{exc.__class__.__name__}。")


def _default_frontend_dist() -> Path:
    return (Settings().frontend_dir / "dist").resolve()


def _mount_frontend(app: FastAPI, frontend_dist: Path) -> None:
    if (frontend_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


def ensure_frontend_dist(settings: Settings, rebuild: bool = False) -> Path:
    frontend_dir = settings.frontend_dir.resolve()
    dist_dir = frontend_dir / "dist"
    index_html = dist_dir / "index.html"
    if index_html.exists() and not rebuild:
        return dist_dir

    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"Frontend package.json does not exist: {package_json}")

    npm = _find_npm(settings)
    if not (frontend_dir / "node_modules").exists():
        subprocess.run([str(npm), "install"], cwd=frontend_dir, check=True)
    subprocess.run([str(npm), "run", "build"], cwd=frontend_dir, check=True)
    if not index_html.exists():
        raise FileNotFoundError(f"Frontend build did not create: {index_html}")
    return dist_dir


def _find_npm(settings: Settings) -> Path:
    candidates: list[Path] = []
    if settings.npm_cmd:
        candidates.append(settings.npm_cmd)
    candidates.extend(sorted(Path(".tools").glob("node-*-win-x64/npm.cmd"), reverse=True))
    for executable in ["npm.cmd", "npm"]:
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "NPM was not found. Set NPM_CMD, run scripts/install-portable-tools.ps1, or install Node.js on PATH."
    )


def main(
    host: str | None = None,
    port: int | None = None,
    rebuild_frontend: bool = False,
    open_browser: bool = True,
) -> None:
    import uvicorn

    settings = Settings()
    frontend_dist = ensure_frontend_dist(settings, rebuild=rebuild_frontend)
    app_instance = create_app(frontend_dist=frontend_dist)
    resolved_host = host or os.getenv("GVA_WEB_HOST", "127.0.0.1")
    resolved_port = port or int(os.getenv("GVA_WEB_PORT", "7860"))
    url = f"http://{resolved_host}:{resolved_port}"
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app_instance, host=resolved_host, port=resolved_port, reload=False)


app = create_app()


if __name__ == "__main__":
    main()
