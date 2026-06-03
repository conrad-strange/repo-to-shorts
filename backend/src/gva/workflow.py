import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from gva.agents.verifier import verify_video_plan
from gva.agents.evaluator import evaluate_output
from gva.agents.project_understanding import understand_project
from gva.agents.repair_writer import repair_video_plan
from gva.agents.repo_reader import read_repo
from gva.agents.script_writer import render_script_markdown, write_script
from gva.agents.storyboard_writer import write_storyboard
from gva.config import Settings
from gva.core.llm_client import llm_settings_error
from gva.core.captions import attach_caption_cues
from gva.core.demo_report import generate_demo_assets
from gva.core.evidence import build_evidence_index, evidence_refs_for_keys, safe_fallback_refs
from gva.core.pacing import tighten_storyboard_for_video_mode
from gva.core.render_bridge import (
    install_renderer_dependencies,
    prepare_remotion_public_assets,
    render_video,
)
from gva.core.repo_loader import resolve_project_source
from gva.core.runs import allocate_run
from gva.core.tts import run_tts_timing
from gva.core.visual_assets import prepare_visual_assets
from gva.models.render import WorkflowResult
from gva.models.storyboard import MicroBeat

ProgressCallback = Callable[[dict[str, Any]], None]


def run_render_workflow(
    project_path: Path | None,
    repo_url: str | None,
    output_dir: Path,
    settings: Settings,
    user_brief: str | None = None,
    target_duration_seconds: int | None = None,
    dry_run: bool = True,
    force_insight: bool = False,
    force_script: bool = False,
    force_storyboard: bool = False,
    force_tts: bool = False,
    force_render: bool = False,
    allow_unverified: bool = False,
    run_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> WorkflowResult:
    """Placeholder workflow.

    The first real milestone will replace this with:
    repo scan -> project insight -> script -> storyboard -> verification.
    """
    _apply_brand_defaults(settings)
    user_brief = _normalize_user_brief(user_brief)
    _emit_progress(progress_callback, "repo", "读取 GitHub 仓库", 5)
    project_path = resolve_project_source(project_path, repo_url, settings.repo_cache_dir)
    root_output_dir = output_dir.resolve()
    run_info = allocate_run(root_output_dir, requested_run=run_id)
    output_dir = run_info.run_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    _apply_force_flags(
        output_dir=output_dir,
        force_insight=force_insight,
        force_script=force_script,
        force_storyboard=force_storyboard,
        force_tts=force_tts,
        force_render=force_render,
    )

    repo_summary = read_repo(project_path)
    _emit_progress(progress_callback, "repo", "仓库扫描完成", 16)
    summary_path = output_dir / "repo-summary.json"
    summary_path.write_text(
        repo_summary.model_dump_json(indent=2),
        encoding="utf-8",
    )

    metadata = {
        "project_path": str(project_path),
        "root_output_dir": str(root_output_dir),
        "run_id": run_info.run_id,
        "run_dir": str(output_dir),
        "repo_url": repo_url,
        "user_brief": user_brief,
        "target_duration_seconds": target_duration_seconds,
        "dry_run": dry_run,
        "tts_provider": settings.tts_provider,
        "tts_voice": settings.tts_voice,
        "tts_rate": settings.tts_rate,
        "video_mode": settings.video_mode,
        "storytelling_mode": settings.storytelling_mode,
        "render_profile": settings.render_profile,
        "brand_mode": settings.brand_mode,
        "bomb_circle": settings.bomb_circle,
        "bomb_again_count": settings.bomb_again_count,
        "rb_tts_voice": settings.rb_tts_voice,
        "rb_tts_rate": settings.rb_tts_rate,
        "rb_hook_duration_seconds": settings.rb_hook_duration_seconds,
        "remotion_concurrency": settings.remotion_concurrency,
        "repair_enabled": settings.repair_enabled,
        "repo_summary_path": str(summary_path),
        "detected_stack": repo_summary.detected_stack,
        "selected_files": len(repo_summary.files),
    }
    _write_user_intent(output_dir, user_brief, settings)
    llm_error = llm_settings_error(settings)
    has_llm_key = llm_error is None
    if llm_error:
        metadata["next_step_requires"] = f"{llm_error} Project Understanding Agent needs a configured LLM."

    if has_llm_key:
        _emit_progress(progress_callback, "evidence", "理解项目结构", 22)
        insight_path = output_dir / "project-insight.json"
        if insight_path.exists():
            from gva.models.insight import ProjectInsight

            insight = ProjectInsight.model_validate_json(insight_path.read_text(encoding="utf-8"))
        else:
            insight = understand_project(repo_summary, settings)
            insight_path.write_text(
                insight.model_dump_json(indent=2),
                encoding="utf-8",
            )
        metadata["project_insight_path"] = str(insight_path)
        metadata["project_name"] = insight.name
        evidence_index = build_evidence_index(repo_summary, output_dir, insight)
        metadata["repo_evidence_index_path"] = str(output_dir / "repo-evidence-index.json")
        _emit_progress(progress_callback, "evidence", "证据索引完成", 32)

        script_path = output_dir / "video-script.json"
        script_md_path = output_dir / "script.md"
        _emit_progress(progress_callback, "script", "生成中文讲稿", 40)
        if script_path.exists():
            from gva.models.script import VideoScript

            script = VideoScript.model_validate_json(script_path.read_text(encoding="utf-8"))
        else:
            script = write_script(insight, settings, user_brief=user_brief)
            _attach_script_evidence_refs(script, evidence_index)
            script_path.write_text(
                script.model_dump_json(indent=2),
                encoding="utf-8",
            )
            script_md_path.write_text(
                render_script_markdown(script),
                encoding="utf-8",
            )
        metadata["video_script_path"] = str(script_path)
        metadata["script_markdown_path"] = str(script_md_path)
        metadata["script_duration_seconds"] = script.duration_seconds
        _emit_progress(progress_callback, "script", "讲稿准备完成", 48)
        if not script.segments or not any(segment.evidence_refs for segment in script.segments):
            _attach_script_evidence_refs(script, evidence_index)
            script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        if _apply_bomb_mode_to_script(script, settings):
            script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
            script_md_path.write_text(render_script_markdown(script), encoding="utf-8")
            metadata["bomb_hook"] = _bomb_hook_text(settings)

        storyboard_path = output_dir / "storyboard.json"
        storyboard_raw_path = output_dir / "storyboard.raw.json"
        storyboard_final_path = output_dir / "storyboard.final.json"
        _emit_progress(progress_callback, "storyboard", "生成视频分镜", 54)
        if storyboard_path.exists():
            from gva.models.storyboard import Storyboard

            storyboard = Storyboard.model_validate_json(storyboard_path.read_text(encoding="utf-8"))
        else:
            storyboard = write_storyboard(script, settings, user_brief=user_brief)
            _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
            storyboard_raw_path.write_text(
                storyboard.model_dump_json(indent=2),
                encoding="utf-8",
            )
            storyboard_path.write_text(
                storyboard.model_dump_json(indent=2),
                encoding="utf-8",
            )
        if not any(scene.evidence_refs for scene in storyboard.scenes):
            _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
            storyboard_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        metadata["storyboard_path"] = str(storyboard_path)
        metadata["scene_count"] = len(storyboard.scenes)
        metadata["storyboard_duration_seconds"] = round(
            sum(scene.duration for scene in storyboard.scenes),
            2,
        )

        pacing_changed = False
        web_edited_storyboard = (output_dir / "logs" / "web-edited-storyboard.json").exists()
        _emit_progress(progress_callback, "storyboard", "准备 GitHub/README 视觉资产", 60)
        if _apply_bomb_mode_to_storyboard(storyboard, settings, repo_url):
            metadata["bomb_hook"] = _bomb_hook_text(settings)
            pacing_changed = True
        if web_edited_storyboard:
            _copy_existing_visual_assets_to_public(output_dir, settings.renderer_dir.resolve())
            metadata["web_edited_storyboard"] = True
        else:
            storyboard = prepare_visual_assets(
                output_dir=output_dir,
                renderer_dir=settings.renderer_dir.resolve(),
                repo_summary=repo_summary,
                storyboard=storyboard,
                repo_url=repo_url,
                settings=settings,
            )
            pacing_changed = tighten_storyboard_for_video_mode(storyboard, settings.video_mode, repo_url) or pacing_changed
        if _soften_risky_video_claims(storyboard):
            metadata["risky_claims_softened"] = True
            pacing_changed = True
        if _apply_bomb_mode_to_storyboard(storyboard, settings, repo_url):
            metadata["bomb_hook"] = _bomb_hook_text(settings)
            pacing_changed = True
        _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
        storyboard_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        storyboard_final_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        metadata["visual_assets_manifest_path"] = str(output_dir / "logs" / "visual-assets-manifest.json")
        metadata["storyboard_raw_path"] = str(storyboard_raw_path)
        metadata["storyboard_final_path"] = str(storyboard_final_path)

        _emit_progress(progress_callback, "verify", "校验内容可信度", 68)
        verification = verify_video_plan(
            output_dir=output_dir,
            script=script,
            storyboard=storyboard,
            evidence_index=evidence_index,
            settings=settings,
        )
        metadata["verification_report_path"] = str(output_dir / "verification-report.json")
        metadata["verification_passed"] = verification.passed
        metadata["verification_high_unsupported"] = verification.metrics.get("unsupported_high_count", 0)
        metadata["verification_policy"] = "advisory"

        if not verification.passed and settings.repair_enabled and not web_edited_storyboard:
            _emit_progress(progress_callback, "verify", "Repair Agent 正在修复未支持表述", 72)
            _preserve_file(output_dir / "verification-report.json", output_dir / "verification-report.before-repair.json")
            _preserve_file(output_dir / "verification-report.md", output_dir / "verification-report.before-repair.md")
            metadata["verification_before_repair_report_path"] = str(
                output_dir / "verification-report.before-repair.json"
            )
            metadata["repair_attempted"] = False
            for attempt in range(max(settings.repair_max_attempts, 0)):
                try:
                    script, storyboard, repair_report = repair_video_plan(
                        output_dir=output_dir,
                        script=script,
                        storyboard=storyboard,
                        verification=verification,
                        evidence_index=evidence_index,
                        settings=settings,
                    )
                except Exception as exc:
                    metadata["repair_error"] = f"{exc.__class__.__name__}: {str(exc)[:300]}"
                    break

                metadata["repair_attempted"] = True
                metadata["repair_attempts"] = attempt + 1
                metadata["repair_report_path"] = str(output_dir / "repair-report.json")
                _attach_script_evidence_refs(script, evidence_index)
                pacing_changed = tighten_storyboard_for_video_mode(storyboard, settings.video_mode, repo_url) or pacing_changed
                if _soften_risky_video_claims(storyboard):
                    metadata["risky_claims_softened_after_repair"] = True
                    pacing_changed = True
                if _apply_bomb_mode_to_script(script, settings):
                    metadata["bomb_hook"] = _bomb_hook_text(settings)
                if _apply_bomb_mode_to_storyboard(storyboard, settings, repo_url):
                    metadata["bomb_hook"] = _bomb_hook_text(settings)
                    pacing_changed = True
                _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
                script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
                script_md_path.write_text(render_script_markdown(script), encoding="utf-8")
                storyboard_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
                (output_dir / "storyboard.repaired.json").write_text(
                    storyboard.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                storyboard_final_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")

                verification = verify_video_plan(
                    output_dir=output_dir,
                    script=script,
                    storyboard=storyboard,
                    evidence_index=evidence_index,
                    settings=settings,
                )
                metadata["verification_passed"] = verification.passed
                metadata["verification_high_unsupported"] = verification.metrics.get("unsupported_high_count", 0)
                metadata["repair_change_count"] = len(repair_report.get("changes") or [])
                if verification.passed:
                    break
        elif not verification.passed and web_edited_storyboard:
            metadata["repair_skipped"] = "web_edited_storyboard"

        if pacing_changed:
            metadata["pacing_adjusted"] = True
            _delete_tts_artifacts(output_dir)
            _delete_render_artifacts(output_dir)

        if not verification.passed:
            metadata["verification_warning"] = "Verifier found advisory issues; rendering continues."
            _emit_progress(progress_callback, "verify", "校验有提示，继续生成视频", 76)

        timed_storyboard_path = output_dir / "storyboard-timed.json"
        tts_manifest_path = output_dir / "logs" / "tts-manifest.json"
        timing_adjustment_path = output_dir / "logs" / "timing-adjustment.json"
        _emit_progress(progress_callback, "tts", "生成配音和字幕", 80)
        if timed_storyboard_path.exists() and tts_manifest_path.exists() and timing_adjustment_path.exists():
            from gva.models.storyboard import Storyboard
            from gva.models.tts import TimingAdjustmentLog, TtsManifest

            timed_storyboard = Storyboard.model_validate_json(
                timed_storyboard_path.read_text(encoding="utf-8")
            )
            tts_manifest = TtsManifest.model_validate_json(
                tts_manifest_path.read_text(encoding="utf-8")
            )
            timing_log = TimingAdjustmentLog.model_validate_json(
                timing_adjustment_path.read_text(encoding="utf-8")
            )
        else:
            timed_storyboard, tts_manifest, timing_log = run_tts_timing(
                storyboard=storyboard,
                output_dir=output_dir,
                settings=settings,
            )
            timed_storyboard = attach_caption_cues(timed_storyboard, output_dir)
            timed_storyboard_path.write_text(timed_storyboard.model_dump_json(indent=2), encoding="utf-8")
        _emit_progress(progress_callback, "tts", "配音字幕完成", 86)
        metadata["timed_storyboard_path"] = str(timed_storyboard_path)
        metadata["tts_manifest_path"] = str(tts_manifest_path)
        metadata["timing_adjustment_path"] = str(timing_adjustment_path)
        metadata["voice_audio_path"] = str(tts_manifest.full_audio_path)
        metadata["voice_audio_duration_seconds"] = tts_manifest.full_audio_duration_seconds
        metadata["timed_storyboard_duration_seconds"] = timing_log.adjusted_total_duration_seconds

        if not any(scene.captions for scene in timed_storyboard.scenes):
            timed_storyboard = attach_caption_cues(timed_storyboard, output_dir)
            timed_storyboard_path.write_text(timed_storyboard.model_dump_json(indent=2), encoding="utf-8")
        metadata["caption_cues_path"] = str(output_dir / "logs" / "caption-cues.json")

        metadata["render_strategy"] = settings.render_strategy

        prepare_remotion_public_assets(
            output_dir=output_dir,
            renderer_dir=settings.renderer_dir.resolve(),
            storyboard=timed_storyboard,
            audio_path=tts_manifest.full_audio_path,
            settings=settings,
        )
        metadata["render_input_path"] = str(output_dir / "logs" / "render-input.json")

        if dry_run:
            metadata["next_step"] = "Remotion Render"
        else:
            _emit_progress(progress_callback, "render", "Remotion 渲染 MP4", 92)
            install_renderer_dependencies(settings)
            video_path = render_video(output_dir=output_dir, settings=settings)
            metadata["video_path"] = str(video_path)
            evaluation = evaluate_output(output_dir=output_dir, settings=settings)
            metadata["evaluation_report_path"] = str(output_dir / "evaluation-report.json")
            metadata["evaluation_score"] = evaluation.score
            metadata["evaluation_passed"] = evaluation.passed
            demo_assets = generate_demo_assets(output_dir=output_dir, settings=settings, metadata=metadata)
            metadata["demo_report_path"] = demo_assets.get("demo_report")
            metadata["preview_grid_path"] = demo_assets.get("preview_grid")
            metadata["next_step"] = "Done"
            _emit_progress(progress_callback, "render", "视频生成完成", 100)

    metadata_path = output_dir / "workflow-metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return WorkflowResult(output_dir=output_dir, metadata=metadata)


def _emit_progress(
    progress_callback: ProgressCallback | None,
    step: str,
    message: str,
    percent: float,
) -> None:
    if not progress_callback:
        return
    try:
        progress_callback({"step": step, "message": message, "percent": percent})
    except Exception:
        pass


def _copy_existing_visual_assets_to_public(output_dir: Path, renderer_dir: Path) -> None:
    source = output_dir / "assets"
    if not source.exists():
        return
    target = renderer_dir / "public" / "generated" / "assets"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


def _soften_risky_video_claims(storyboard) -> bool:
    changed = False
    for scene in storyboard.scenes:
        new_narration = _soften_risky_text(scene.narration)
        if new_narration != scene.narration:
            scene.narration = new_narration
            changed = True

        visual = scene.visual
        for attr in ["headline", "caption", "code"]:
            value = getattr(visual, attr, None)
            if not value:
                continue
            softened = _soften_risky_text(value)
            if softened != value:
                setattr(visual, attr, softened)
                changed = True

        softened_bullets = [_soften_risky_text(item) for item in visual.bullets]
        if softened_bullets != visual.bullets:
            visual.bullets = softened_bullets
            changed = True

        softened_nodes = [_soften_risky_text(item) for item in visual.diagram_nodes]
        if softened_nodes != visual.diagram_nodes:
            visual.diagram_nodes = softened_nodes
            changed = True

        softened_beats = []
        beats_changed = False
        for beat in visual.micro_beats:
            softened_text = _soften_risky_text(beat.text)
            if softened_text != beat.text:
                beat = beat.model_copy(update={"text": softened_text})
                beats_changed = True
            softened_beats.append(beat)
        if beats_changed:
            visual.micro_beats = softened_beats
            changed = True
    return changed


def _soften_risky_text(text: str) -> str:
    replacements = {
        "并给出可追溯来源": "并定位相关段落",
        "可追溯来源": "相关段落",
        "来源追踪": "相关段落",
        "快速定位答案": "定位相关答案线索",
        "无需任何云服务": "按项目配置接入模型服务",
        "无需云服务": "按项目配置接入模型服务",
        "无云服务": "按项目配置接入模型服务",
        "本地离线": "本地界面",
    }
    softened = text
    for old, new in replacements.items():
        softened = softened.replace(old, new)
    return softened


def _apply_bomb_mode_to_script(script, settings: Settings) -> bool:
    if not _is_bomb_mode(settings):
        return False
    hook = _bomb_hook_text(settings)
    changed = False
    if script.title != hook:
        script.title = hook
        changed = True
    if script.segments:
        first = script.segments[0]
        next_narration = _prepend_bomb_hook(first.narration, hook)
        if first.narration != next_narration:
            first.narration = next_narration
            changed = True
        if first.scene_hint != "bomb_hook":
            first.scene_hint = "bomb_hook"
            changed = True
    full_text = "\n".join(segment.narration.strip() for segment in script.segments if segment.narration.strip())
    if script.full_text != full_text:
        script.full_text = full_text
        changed = True
    return changed


def _apply_bomb_mode_to_storyboard(storyboard, settings: Settings, repo_url: str | None) -> bool:
    if not _is_bomb_mode(settings) or not storyboard.scenes:
        return False
    hook = _bomb_hook_text(settings)
    first = storyboard.scenes[0]
    changed = False
    if first.type != "bomb_hook":
        first.type = "bomb_hook"
        changed = True
    if first.visual.layout != "github_hero":
        first.visual.layout = "github_hero"
        changed = True
    if first.visual.headline != hook:
        first.visual.headline = hook
        changed = True
    next_narration = _prepend_bomb_hook(first.narration, hook)
    if first.narration != next_narration:
        first.narration = next_narration
        changed = True
    if first.visual.caption != "先别急着滑走，看证据":
        first.visual.caption = "先别急着滑走，看证据"
        changed = True
    if first.visual.accent_color != "#f85149":
        first.visual.accent_color = "#f85149"
        changed = True
    hook_duration = _bomb_hook_duration(settings)
    if abs(float(first.duration) - hook_duration) > 0.05:
        first.duration = hook_duration
        changed = True
    if first.visual.repo_url is None and repo_url:
        first.visual.repo_url = repo_url
        changed = True
    if first.visual.repo_display_url is None and repo_url:
        first.visual.repo_display_url = repo_url.replace("https://", "")
        changed = True
    bomb_beats = [
        MicroBeat(text="真实仓库", kind="warning", emphasis="evidence", start_ratio=0.08),
        MicroBeat(text="证据校验", kind="text", emphasis="evidence", start_ratio=0.34),
        MicroBeat(text="看完再 Star", kind="cta", emphasis="github", start_ratio=0.62),
    ]
    if [beat.text for beat in first.visual.micro_beats[:3]] != [beat.text for beat in bomb_beats]:
        first.visual.micro_beats = bomb_beats
        changed = True
    return changed


def _is_bomb_mode(settings: Settings) -> bool:
    return str(settings.brand_mode).strip().lower() in {"rb", "repo-to-bombs", "bomb", "bombs"}


def _apply_brand_defaults(settings: Settings) -> None:
    if not _is_bomb_mode(settings):
        return
    if not settings.tts_voice or settings.tts_voice == "zh-CN-XiaoxiaoNeural":
        settings.tts_voice = settings.rb_tts_voice
    if not settings.tts_rate or settings.tts_rate in {"+0%", "+25%"}:
        settings.tts_rate = settings.rb_tts_rate


def _normalize_user_brief(value: str | None) -> str:
    cleaned = re.sub(r"[<>{}\[\]|\\^`]", "", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:500]


def _write_user_intent(output_dir: Path, user_brief: str, settings: Settings) -> None:
    intent = {
        "raw_text": user_brief,
        "source": "web_user_brief" if user_brief else "default",
        "rules": [
            "User brief may adjust tone, pacing, focus, and scene emphasis.",
            "User brief is not evidence and must not introduce unsupported project facts.",
        ],
        "video_mode": settings.video_mode,
        "storytelling_mode": settings.storytelling_mode,
        "brand_mode": settings.brand_mode,
    }
    (output_dir / "user-intent.json").write_text(
        json.dumps(intent, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _bomb_hook_text(settings: Settings) -> str:
    circle = _clean_bomb_circle(settings.bomb_circle)
    again_count = max(1, min(8, int(settings.bomb_again_count or 1)))
    return f"{circle}今天{'又' * again_count}炸了！"


def _bomb_hook_duration(settings: Settings) -> float:
    try:
        duration = float(settings.rb_hook_duration_seconds)
    except (TypeError, ValueError):
        duration = 3.0
    return round(max(2.5, min(4.0, duration)), 2)


def _clean_bomb_circle(value: str | None) -> str:
    cleaned = "".join(ch for ch in (value or "").strip() if ch not in "<>{}[]|\\^`\"'，。；：")
    cleaned = cleaned.replace(" ", "")[:10]
    if not cleaned:
        cleaned = "科技圈"
    if not cleaned.endswith("圈"):
        cleaned = f"{cleaned}圈"
    return cleaned


def _prepend_bomb_hook(text: str, hook: str) -> str:
    cleaned = _strip_bomb_hook(text)
    return hook if not cleaned else f"{hook} {cleaned}"


def _strip_bomb_hook(text: str) -> str:
    return re.sub(r"^\s*[\w\u4e00-\u9fff]{1,12}圈今天又{1,8}炸了[!！]?\s*", "", text or "").strip()


def _attach_script_evidence_refs(script, evidence_index) -> None:
    fallback = safe_fallback_refs(evidence_index, limit=1)
    for segment in script.segments:
        refs = evidence_refs_for_keys(segment.evidence_keys, evidence_index)
        segment.evidence_refs = refs or fallback


def _attach_storyboard_evidence_refs(storyboard, script, evidence_index) -> None:
    fallback = safe_fallback_refs(evidence_index, limit=1)
    script_refs_by_index = [
        segment.evidence_refs or evidence_refs_for_keys(segment.evidence_keys, evidence_index)
        for segment in script.segments
    ]
    for index, scene in enumerate(storyboard.scenes):
        refs = evidence_refs_for_keys(scene.evidence_keys, evidence_index)
        if not refs and index < len(script_refs_by_index):
            refs = script_refs_by_index[index]
        scene.evidence_refs = refs or fallback
        scene.visual.evidence_refs = scene.evidence_refs


def _apply_force_flags(
    output_dir: Path,
    force_insight: bool,
    force_script: bool,
    force_storyboard: bool,
    force_tts: bool,
    force_render: bool,
) -> None:
    if force_insight:
        force_script = True
        _delete_file(output_dir / "project-insight.json")
    if force_script:
        force_storyboard = True
        _delete_file(output_dir / "video-script.json")
        _delete_file(output_dir / "script.md")
    if force_storyboard:
        force_tts = True
        _delete_file(output_dir / "storyboard.json")
        _delete_file(output_dir / "storyboard.raw.json")
        _delete_file(output_dir / "storyboard.final.json")
        _delete_file(output_dir / "storyboard.repaired.json")
        _delete_file(output_dir / "repair-report.json")
        _delete_file(output_dir / "repair-report.md")
        _delete_file(output_dir / "verification-report.before-repair.json")
        _delete_file(output_dir / "verification-report.before-repair.md")
    if force_tts:
        force_render = True
        _delete_tts_artifacts(output_dir)
    if force_render:
        _delete_render_artifacts(output_dir)


def _delete_tts_artifacts(output_dir: Path) -> None:
    _delete_file(output_dir / "storyboard-timed.json")
    _delete_file(output_dir / "subtitles.srt")
    _delete_file(output_dir / "subtitles.vtt")
    _delete_file(output_dir / "audio" / "voice.mp3")
    _delete_file(output_dir / "audio" / "voice-normalized.mp3")
    _delete_dir(output_dir / "audio" / "scenes")
    _delete_file(output_dir / "logs" / "tts-input.json")
    _delete_file(output_dir / "logs" / "tts-manifest.json")
    _delete_file(output_dir / "logs" / "timing-adjustment.json")
    _delete_file(output_dir / "logs" / "caption-cues.json")


def _delete_render_artifacts(output_dir: Path) -> None:
    _delete_file(output_dir / "video.mp4")
    _delete_dir(output_dir / "videos")
    _delete_file(output_dir / "preview-5s.png")
    _delete_file(output_dir / "evaluation-report.json")
    _delete_file(output_dir / "evaluation-report.md")
    _delete_file(output_dir / "demo_report.md")
    _delete_file(output_dir / "logs" / "render-input.json")
    _delete_file(output_dir / "logs" / "demo-assets.json")
    _delete_file(output_dir / "logs" / "visual-assets-manifest.json")
    _delete_dir(output_dir / "preview_frames")


def _delete_file(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _delete_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)


def _preserve_file(source: Path, target: Path) -> None:
    if source.exists() and not target.exists():
        shutil.copyfile(source, target)
