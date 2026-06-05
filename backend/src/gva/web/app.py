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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from git.exc import GitCommandError
from pydantic import BaseModel, Field

from gva.config import Settings
from gva.core.asyncio_windows import install_windows_connection_reset_filter
from gva.core.render_bridge import find_browser, find_ffmpeg
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
    user_brief: str | None = None
    out_dir: str | None = None
    video_mode: VideoMode = "short_30s"
    storytelling_mode: str = "experience_first"
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
    video_mode: VideoMode | None = None
    user_brief: str | None = None
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


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    install_windows_connection_reset_filter()
    yield


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Repo to Shorts API", version="0.1.0", lifespan=_lifespan)
    job_manager = JobManager(max_workers=int(os.getenv("GVA_WEB_MAX_JOBS", "1")))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler_zh(_request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "请求参数不完整，请检查 GitHub 链接和生成配置。"})

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        icon_path = (frontend_dist or _default_frontend_dist()) / "favicon.svg"
        if not icon_path.exists():
            icon_path = Settings().frontend_dir.resolve() / "public" / "favicon.svg"
        if not icon_path.exists():
            raise HTTPException(status_code=404, detail="favicon not found")
        return FileResponse(icon_path, media_type="image/svg+xml")

    @app.get("/api/system")
    def system_status() -> dict[str, Any]:
        settings = Settings()
        browser = find_browser(settings)
        return {
            "node": _node_status(settings),
            "tools": {
                "renderer_dir": str(settings.renderer_dir.resolve()),
                "frontend_dir": str(settings.frontend_dir.resolve()),
                "outputs_dir": str(settings.outputs_dir.resolve()),
                "ffmpeg_exe": _path_status(settings.ffmpeg_exe),
                "browser_exe": _path_status(browser),
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
                    "run_labels": _run_labels(path),
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

    @app.post("/api/projects/{project_id}/runs/{run_id}/assets/user-video")
    async def upload_user_video(
        project_id: str,
        run_id: str,
        request: Request,
        filename: str = "demo.mp4",
        start: float = 0.0,
        end: float = 6.0,
        clips: str | None = None,
    ) -> dict[str, Any]:
        run_dir = _run_dir(project_id, run_id)
        return await _save_user_video_asset(run_dir, request, filename, start, end, clips)

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
    settings.storytelling_mode = request.storytelling_mode or settings.storytelling_mode
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
        user_brief=request.user_brief,
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
    settings.video_mode = request.video_mode or metadata.get("video_mode", settings.video_mode)
    settings.render_strategy = metadata.get("render_strategy", settings.render_strategy)
    settings.storytelling_mode = metadata.get("storytelling_mode", settings.storytelling_mode)
    settings.render_profile = request.render_profile or metadata.get("render_profile", "preview")
    settings.brand_mode = request.brand_mode or metadata.get("brand_mode", settings.brand_mode)
    settings.bomb_circle = request.bomb_circle or metadata.get("bomb_circle", settings.bomb_circle)
    settings.bomb_again_count = request.bomb_again_count or metadata.get("bomb_again_count", settings.bomb_again_count)
    settings.tts_voice = request.tts_voice or metadata.get("tts_voice", settings.tts_voice)
    settings.remotion_concurrency = request.remotion_concurrency or metadata.get("remotion_concurrency")

    root_output_dir = Path(metadata.get("root_output_dir", _project_root(project_id))).resolve()
    new_run = allocate_run(root_output_dir, label_suffix=_video_mode_suffix(settings.video_mode))
    new_run_dir = new_run.run_dir
    _seed_rerender_run(source_run_dir, new_run_dir, request.storyboard)

    repo_url = metadata.get("repo_url")
    project_path = None if repo_url else Path(metadata["project_path"]) if metadata.get("project_path") else None
    user_brief = request.user_brief if request.user_brief is not None else metadata.get("user_brief")
    result = run_render_workflow(
        project_path=project_path,
        repo_url=repo_url,
        output_dir=root_output_dir,
        settings=settings,
        user_brief=user_brief,
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


async def _save_user_video_asset(
    run_dir: Path,
    request: Request,
    filename: str,
    start: float,
    end: float,
    clips: str | None = None,
) -> dict[str, Any]:
    clip_ranges = _parse_user_video_clips(clips, start, end)
    start = clip_ranges[0]["start"]
    end = clip_ranges[0]["end"]
    if start < 0:
        raise HTTPException(status_code=400, detail="视频开始时间不能小于 0 秒。")
    if end <= start:
        raise HTTPException(status_code=400, detail="视频结束时间必须大于开始时间。")
    duration = round(end - start, 3)
    if duration < 2:
        raise HTTPException(status_code=400, detail="展示片段至少保留 2 秒。")
    if duration > 12:
        raise HTTPException(status_code=400, detail="初版视频素材片段请控制在 12 秒以内。")

    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="请先选择一个视频文件。")
    if len(payload) > 120 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="视频文件太大，请上传 120MB 以内的录屏。")

    suffix = _safe_video_suffix(filename)
    digest = hashlib.sha1(payload).hexdigest()[:16]
    output_dir = run_dir / "assets" / "user"
    output_dir.mkdir(parents=True, exist_ok=True)
    source = output_dir / f"source-{digest}{suffix}"
    target = output_dir / f"result-video-{digest}.mp4"
    source.write_bytes(payload)
    if len(clip_ranges) == 1:
        _clip_user_video(source, target, start, duration)
    else:
        parts = []
        for index, clip in enumerate(clip_ranges, start=1):
            part = output_dir / f"result-video-{digest}-part-{index:02d}.mp4"
            _clip_user_video(source, part, clip["start"], clip["duration"])
            parts.append(part)
        _concat_user_video_parts(parts, target, output_dir / f"result-video-{digest}-concat.txt")

    public_target = Settings().renderer_dir.resolve() / "public" / "generated" / "assets" / "user" / target.name
    public_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, public_target)
    return {
        "asset_path": f"generated/assets/user/{target.name}",
        "run_asset_path": str(target),
        "bytes": target.stat().st_size,
        "start": clip_ranges[0]["start"],
        "end": clip_ranges[-1]["end"],
        "duration": round(sum(clip["duration"] for clip in clip_ranges), 3),
        "clips": clip_ranges,
    }


def _parse_user_video_clips(clips: str | None, start: float, end: float) -> list[dict[str, float]]:
    if clips:
        try:
            parsed = json.loads(clips)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="视频片段参数无法解析。") from exc
        if not isinstance(parsed, list):
            raise HTTPException(status_code=400, detail="视频片段参数必须是数组。")
        raw_clips = [item for item in parsed if isinstance(item, dict)]
    else:
        raw_clips = [{"start": start, "end": end}]

    if not raw_clips:
        raise HTTPException(status_code=400, detail="请至少选择一个视频片段。")
    if len(raw_clips) > 6:
        raise HTTPException(status_code=400, detail="初版最多拼接 6 个视频片段。")

    normalized = []
    for item in raw_clips:
        clip_start = _safe_float(item.get("start"))
        clip_end = _safe_float(item.get("end"))
        if clip_start < 0:
            raise HTTPException(status_code=400, detail="视频开始时间不能小于 0 秒。")
        if clip_end <= clip_start:
            raise HTTPException(status_code=400, detail="视频结束时间必须大于开始时间。")
        duration = round(clip_end - clip_start, 3)
        if duration < 2:
            raise HTTPException(status_code=400, detail="每个展示片段至少保留 2 秒。")
        if duration > 12:
            raise HTTPException(status_code=400, detail="每个视频素材片段请控制在 12 秒以内。")
        normalized.append({"start": round(clip_start, 3), "end": round(clip_end, 3), "duration": duration})

    total = sum(clip["duration"] for clip in normalized)
    if total > 24:
        raise HTTPException(status_code=400, detail="多片段拼接总时长请控制在 24 秒以内。")
    return normalized


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="视频片段时间必须是数字。") from None


def _clip_user_video(source: Path, target: Path, start: float, duration: float) -> None:
    ffmpeg = find_ffmpeg(Settings())
    command = [
        str(ffmpeg),
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-vf",
        "scale=960:-2",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-movflags",
        "+faststart",
        str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not target.exists():
        message = (completed.stderr or completed.stdout or "").strip().splitlines()[-1:] or ["FFmpeg failed."]
        raise HTTPException(status_code=502, detail=f"视频片段处理失败：{message[0]}")


def _concat_user_video_parts(parts: list[Path], target: Path, list_path: Path) -> None:
    if not parts:
        raise HTTPException(status_code=400, detail="没有可拼接的视频片段。")
    ffmpeg = find_ffmpeg(Settings())
    list_path.write_text(
        "\n".join(_concat_file_line(part) for part in parts),
        encoding="utf-8",
    )
    command = [
        str(ffmpeg),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not target.exists():
        message = (completed.stderr or completed.stdout or "").strip().splitlines()[-1:] or ["FFmpeg concat failed."]
        raise HTTPException(status_code=502, detail=f"视频片段拼接失败：{message[0]}")


def _concat_file_line(path: Path) -> str:
    escaped = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{escaped}'"


def _safe_video_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
        return suffix
    return ".mp4"


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
    normalized = source.rstrip("/").replace("\\", "/")
    match = re.match(r"^https://github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:[/?#].*)?$", normalized, re.I)
    if match:
        cleaned = f"{match.group(1)}-{match.group(2)}"
    else:
        cleaned = normalized.split("/")[-1] or "demo"
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
    storyboard = _storyboard_for_ui(run_dir)
    actual_run_id = run_dir.name
    return {
        "project_id": project_id,
        "run_id": actual_run_id,
        "run_label": _run_label(actual_run_id, metadata),
        "project_root": str(project_root),
        "run_dir": str(run_dir),
        "metadata": metadata,
        "repo_summary": _read_json(run_dir / "repo-summary.json"),
        "script_markdown": _read_text(run_dir / "script.md"),
        "storyboard": storyboard,
        "visible_text_manifest": _read_json(run_dir / "logs" / "visible-text-manifest.json"),
        "verification": _read_json(run_dir / "verification-report.json"),
        "evaluation": _read_json(run_dir / "evaluation-report.json"),
        "files": _artifact_urls(project_id, actual_run_id, run_dir),
    }


def _run_labels(project_root: Path) -> dict[str, str]:
    labels = {}
    for run_id in list_run_ids(project_root):
        metadata = _read_json(project_root / "runs" / run_id / "workflow-metadata.json") or {}
        labels[run_id] = _run_label(run_id, metadata)
    return labels


def _run_label(run_id: str, metadata: dict[str, Any]) -> str:
    if "+" in run_id:
        return run_id
    suffix = _video_mode_suffix(metadata.get("video_mode"))
    return f"{run_id}+{suffix}" if suffix else run_id


def _video_mode_suffix(video_mode: object) -> str | None:
    if video_mode == "short_30s":
        return "30s"
    if video_mode == "standard_60s":
        return "60s"
    if video_mode == "technical_90s":
        return "90s"
    return None


def _storyboard_for_ui(run_dir: Path) -> Any:
    base = _read_json(
        _first_existing(run_dir / "storyboard.edited.json", run_dir / "storyboard.final.json", run_dir / "storyboard.json")
    )
    timed = _read_json(run_dir / "storyboard-timed.json")
    if not isinstance(base, dict) or not isinstance(base.get("scenes"), list):
        return timed or base
    if not isinstance(timed, dict) or not isinstance(timed.get("scenes"), list):
        return base

    timed_by_id = {
        scene.get("id"): scene
        for scene in timed.get("scenes", [])
        if isinstance(scene, dict) and isinstance(scene.get("id"), str)
    }
    merged = json.loads(json.dumps(base))
    for scene in merged.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        timed_scene = timed_by_id.get(scene.get("id"))
        if not isinstance(timed_scene, dict):
            continue
        for key in ("start", "duration", "captions"):
            if key in timed_scene:
                scene[key] = timed_scene[key]
        timed_visual = timed_scene.get("visual")
        if isinstance(timed_visual, dict) and isinstance(timed_visual.get("visual_pages"), list):
            visual = scene.setdefault("visual", {})
            if isinstance(visual, dict):
                visual["visual_pages"] = timed_visual["visual_pages"]
    return merged


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
    exc_name = exc.__class__.__name__.lower()
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
    if "noaudioreceived" in exc_name or "no audio" in lowered or "edge tts" in lowered:
        return HTTPException(status_code=502, detail="Edge TTS 没有返回音频，系统已自动重试但仍失败。请稍后重试或换一个 TTS 音色。")
    if "websocket" in exc_name or "websocket" in lowered:
        return HTTPException(status_code=502, detail="Edge TTS 连接临时中断，系统已自动重试但仍失败。请稍后重试。")
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
    if index_html.exists() and not rebuild and not _frontend_source_newer_than(index_html, frontend_dir):
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


def _frontend_source_newer_than(index_html: Path, frontend_dir: Path) -> bool:
    if not index_html.exists():
        return True
    dist_mtime = index_html.stat().st_mtime_ns
    for path in _frontend_build_inputs(frontend_dir):
        if path.stat().st_mtime_ns > dist_mtime:
            return True
    return False


def _frontend_build_inputs(frontend_dir: Path) -> list[Path]:
    inputs: list[Path] = []
    for rel_path in [
        "index.html",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "tsconfig.node.json",
        "vite.config.ts",
        "scripts/build.cmd",
    ]:
        path = frontend_dir / rel_path
        if path.exists() and path.is_file():
            inputs.append(path)

    for rel_dir in ["src", "public"]:
        directory = frontend_dir / rel_dir
        if directory.exists() and directory.is_dir():
            inputs.extend(path for path in directory.rglob("*") if path.is_file())
    return inputs


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
