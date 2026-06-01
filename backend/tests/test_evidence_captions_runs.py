from pathlib import Path

from gva.agents.verifier import verify_video_plan
from gva.config import Settings
from gva.core.captions import attach_caption_cues
from gva.core.evidence import build_evidence_index
from gva.core.runs import allocate_run, list_run_ids, publish_latest_video, resolve_run_dir
from gva.models.insight import ProjectInsight
from gva.models.repo import RepoFile, RepoSummary
from gva.models.script import ScriptSegment, VideoScript
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def _repo_summary() -> RepoSummary:
    return RepoSummary(
        source="demo",
        repo_name="demo",
        files=[
            RepoFile(
                path="README.md",
                language="Markdown",
                role="readme",
                excerpt="# Demo\nA small RAG demo for local document retrieval.\n\n## Install\npip install -r requirements.txt",
                size=90,
            ),
            RepoFile(
                path="app.py",
                language="Python",
                role="entry",
                excerpt="def main():\n    run_rag_demo()\n",
                size=40,
            ),
        ],
        tree_overview="README.md\napp.py",
        detected_stack=["Python"],
    )


def test_evidence_index_filters_setup_text(tmp_path: Path) -> None:
    index = build_evidence_index(
        _repo_summary(),
        tmp_path,
        ProjectInsight(
            name="Demo",
            one_liner="A RAG demo.",
            problem="Document retrieval.",
            architecture="README plus app entry.",
            evidence={"rag-demo": ["README.md describes a RAG demo."]},
        ),
    )

    assert (tmp_path / "repo-evidence-index.json").exists()
    readme_item = next(item for item in index.items if item.source_path == "README.md")
    assert "pip install" not in readme_item.excerpt
    assert any(item.id == "rag-demo" for item in index.items)


def test_caption_cues_stay_inside_scene_duration(tmp_path: Path) -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="text",
                start=0,
                duration=4.0,
                narration="这个 RAG 项目读取文档。然后用 FAISS 做检索。",
                visual=VisualSpec(layout="text", headline="RAG demo"),
            )
        ],
    )

    timed = attach_caption_cues(storyboard, tmp_path)

    assert timed.scenes[0].captions
    assert timed.scenes[0].captions[-1].end == 4.0
    assert (tmp_path / "logs" / "caption-cues.json").exists()


def test_verifier_blocks_install_commands(tmp_path: Path) -> None:
    index = build_evidence_index(_repo_summary(), tmp_path)
    ref = index.items[0].id
    script = VideoScript(
        title="Demo",
        segments=[
            ScriptSegment(
                scene_hint="setup",
                narration="先运行 pip install 安装依赖。",
                evidence_refs=[ref],
            )
        ],
        full_text="先运行 pip install 安装依赖。",
    )
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="text",
                start=0,
                duration=4,
                narration="先运行 pip install 安装依赖。",
                evidence_refs=[ref],
                visual=VisualSpec(layout="text", headline="安装", evidence_refs=[ref]),
            )
        ],
    )

    report = verify_video_plan(tmp_path, script, storyboard, index, Settings(), use_llm=False)

    assert not report.passed
    assert any(claim.severity == "high" for claim in report.claims)
    assert (tmp_path / "verification-report.json").exists()


def test_versioned_runs_and_latest_video(tmp_path: Path) -> None:
    first = allocate_run(tmp_path)
    second = allocate_run(tmp_path)
    video = second.run_dir / "videos" / "video.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"fake mp4")

    latest = publish_latest_video(second.run_dir, tmp_path, video)

    assert first.run_id == "0001"
    assert second.run_id == "0002"
    assert list_run_ids(tmp_path) == ["0001", "0002"]
    assert resolve_run_dir(tmp_path, "latest") == second.run_dir
    assert latest.exists()
