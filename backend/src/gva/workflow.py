import json
import shutil
from pathlib import Path

from gva.agents.verifier import verify_video_plan
from gva.agents.evaluator import evaluate_output
from gva.agents.project_understanding import understand_project
from gva.agents.repo_reader import read_repo
from gva.agents.script_writer import render_script_markdown, write_script
from gva.agents.storyboard_writer import write_storyboard
from gva.config import Settings
from gva.core.llm_client import has_real_api_key
from gva.core.captions import attach_caption_cues
from gva.core.evidence import build_evidence_index, evidence_refs_for_keys, safe_fallback_refs
from gva.core.hyperframes import prepare_hyperframes_scene_assets
from gva.core.render_bridge import (
    install_renderer_dependencies,
    prepare_remotion_public_assets,
    render_video,
)
from gva.core.repo_loader import resolve_project_source
from gva.core.runs import allocate_run, publish_latest_video
from gva.core.tts import run_tts_timing
from gva.core.visual_assets import prepare_visual_assets
from gva.models.render import WorkflowResult


def run_render_workflow(
    project_path: Path | None,
    repo_url: str | None,
    output_dir: Path,
    settings: Settings,
    target_duration_seconds: int | None = None,
    dry_run: bool = True,
    force_insight: bool = False,
    force_script: bool = False,
    force_storyboard: bool = False,
    force_tts: bool = False,
    force_render: bool = False,
    allow_unverified: bool = False,
    run_id: str | None = None,
) -> WorkflowResult:
    """Placeholder workflow.

    The first real milestone will replace this with:
    repo scan -> project insight -> script -> storyboard -> verification.
    """
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
        "target_duration_seconds": target_duration_seconds,
        "dry_run": dry_run,
        "tts_provider": settings.tts_provider,
        "repo_summary_path": str(summary_path),
        "detected_stack": repo_summary.detected_stack,
        "selected_files": len(repo_summary.files),
    }
    has_llm_key = True
    if settings.llm_provider == "deepseek" and not has_real_api_key(settings.deepseek_api_key):
        metadata["next_step_requires"] = "DEEPSEEK_API_KEY for Project Understanding Agent"
        has_llm_key = False
    elif settings.llm_provider == "openai" and not has_real_api_key(settings.openai_api_key):
        metadata["next_step_requires"] = "OPENAI_API_KEY for Project Understanding Agent"
        has_llm_key = False

    if has_llm_key:
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

        script_path = output_dir / "video-script.json"
        script_md_path = output_dir / "script.md"
        if script_path.exists():
            from gva.models.script import VideoScript

            script = VideoScript.model_validate_json(script_path.read_text(encoding="utf-8"))
        else:
            script = write_script(insight, settings)
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
        if not script.segments or not any(segment.evidence_refs for segment in script.segments):
            _attach_script_evidence_refs(script, evidence_index)
            script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")

        storyboard_path = output_dir / "storyboard.json"
        if storyboard_path.exists():
            from gva.models.storyboard import Storyboard

            storyboard = Storyboard.model_validate_json(storyboard_path.read_text(encoding="utf-8"))
        else:
            storyboard = write_storyboard(script, settings)
            _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
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

        storyboard = prepare_visual_assets(
            output_dir=output_dir,
            renderer_dir=settings.renderer_dir.resolve(),
            repo_summary=repo_summary,
            storyboard=storyboard,
            repo_url=repo_url,
            settings=settings,
        )
        _attach_storyboard_evidence_refs(storyboard, script, evidence_index)
        storyboard_path.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        metadata["visual_assets_manifest_path"] = str(output_dir / "logs" / "visual-assets-manifest.json")

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
        if not verification.passed and not allow_unverified:
            metadata["next_step_requires"] = "Fix unsupported claims or pass --allow-unverified for debugging."
            metadata["next_step"] = "Verification"
            metadata_path = output_dir / "workflow-metadata.json"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return WorkflowResult(output_dir=output_dir, metadata=metadata)

        timed_storyboard_path = output_dir / "storyboard-timed.json"
        tts_manifest_path = output_dir / "logs" / "tts-manifest.json"
        timing_adjustment_path = output_dir / "logs" / "timing-adjustment.json"
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

        metadata["scene_enhancer"] = settings.scene_enhancer
        metadata["render_strategy"] = settings.render_strategy
        should_prepare_hyperframes = (
            settings.render_strategy.strip().lower() == "hyperframes-primary"
            and settings.scene_enhancer.lower() not in {"", "none", "off"}
        )
        if should_prepare_hyperframes:
            timed_storyboard = prepare_hyperframes_scene_assets(
                output_dir=output_dir,
                renderer_dir=settings.renderer_dir.resolve(),
                storyboard=timed_storyboard,
                render_strategy=settings.render_strategy,
            )
            timed_storyboard_path.write_text(
                timed_storyboard.model_dump_json(indent=2),
                encoding="utf-8",
            )
            metadata["hyperframes_manifest_path"] = str(output_dir / "logs" / "hyperframes-manifest.json")

        prepare_remotion_public_assets(
            output_dir=output_dir,
            renderer_dir=settings.renderer_dir.resolve(),
            storyboard=timed_storyboard,
            audio_path=tts_manifest.full_audio_path,
        )
        metadata["render_input_path"] = str(output_dir / "logs" / "render-input.json")

        if dry_run:
            metadata["next_step"] = "Remotion Render"
        else:
            install_renderer_dependencies(settings)
            video_path = render_video(output_dir=output_dir, settings=settings)
            metadata["video_path"] = str(video_path)
            latest_path = publish_latest_video(output_dir, root_output_dir, video_path)
            metadata["latest_video_path"] = str(latest_path)
            evaluation = evaluate_output(output_dir=output_dir, settings=settings)
            metadata["evaluation_report_path"] = str(output_dir / "evaluation-report.json")
            metadata["evaluation_score"] = evaluation.score
            metadata["evaluation_passed"] = evaluation.passed
            metadata["next_step"] = "Done"

    metadata_path = output_dir / "workflow-metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return WorkflowResult(output_dir=output_dir, metadata=metadata)


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
    if force_tts:
        force_render = True
        _delete_file(output_dir / "storyboard-timed.json")
        _delete_file(output_dir / "audio" / "voice.mp3")
        _delete_dir(output_dir / "audio" / "scenes")
        _delete_file(output_dir / "logs" / "tts-input.json")
        _delete_file(output_dir / "logs" / "tts-manifest.json")
        _delete_file(output_dir / "logs" / "timing-adjustment.json")
    if force_render:
        _delete_file(output_dir / "video.mp4")
        _delete_file(output_dir / "videos" / "latest" / "video.mp4")
        _delete_file(output_dir / "preview-5s.png")
        _delete_file(output_dir / "evaluation-report.json")
        _delete_file(output_dir / "evaluation-report.md")
        _delete_file(output_dir / "logs" / "render-input.json")
        _delete_file(output_dir / "logs" / "hyperframes-manifest.json")
        _delete_file(output_dir / "logs" / "visual-assets-manifest.json")
        _delete_dir(output_dir / "render-assets" / "hyperframes")


def _delete_file(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _delete_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
