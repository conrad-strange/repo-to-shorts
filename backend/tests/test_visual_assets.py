import json
from pathlib import Path
from types import SimpleNamespace

from gva.config import Settings
from gva.core import visual_assets
from gva.core.visual_assets import extract_readme_evidence, prepare_visual_assets
from gva.models.repo import RepoFile, RepoSummary
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def test_extract_readme_evidence_finds_title_intro_and_highlights() -> None:
    summary = RepoSummary(
        source="demo",
        repo_name="demo",
        files=[
            RepoFile(
                path="README.md",
                role="readme",
                language="Markdown",
                excerpt=(
                    "# Demo\n\n"
                    "A local RAG demo.\n\n"
                    "## Quickstart\n\n"
                    "```bash\nstreamlit run app.py\n```\n\n"
                    "## Highlights\n\n"
                    "- Reads local papers and builds a searchable index.\n"
                ),
                size=160,
            )
        ],
        tree_overview="README.md",
    )

    evidence = extract_readme_evidence(summary)

    assert evidence.title == "Demo"
    assert evidence.intro == "A local RAG demo."
    assert evidence.highlights == ["Reads local papers and builds a searchable index."]


def test_extract_readme_evidence_cleans_html_and_generic_headings() -> None:
    summary = RepoSummary(
        source="demo",
        repo_name="repo-to-shorts",
        files=[
            RepoFile(
                path="README.md",
                role="readme",
                language="Markdown",
                excerpt=(
                    '<h1 align="center">Repo to Shorts</h1>\n\n'
                    '<p align="center">\n'
                    "  输入一个公开 GitHub 仓库，生成中文 9:16 项目讲解短视频。\n"
                    "</p>\n\n"
                    '<p align="center"><img alt="Python" src="badge.svg"></p>\n\n'
                    "## What It Does\n\n"
                    "Repo to Shorts 是一个面向开源开发者的 AI 视频生成工具。\n\n"
                    "## Features\n\n"
                    "<table>\n"
                    "<tr><td><strong>GitHub 输入</strong></td></tr>\n"
                    "<tr><td><strong>证据链</strong></td></tr>\n"
                    "</table>\n"
                ),
                size=420,
            )
        ],
        tree_overview="README.md",
    )

    evidence = extract_readme_evidence(summary)

    assert evidence.title == "Repo to Shorts"
    assert evidence.intro == "输入一个公开 GitHub 仓库，生成中文 9:16 项目讲解短视频。"
    assert "What It Does" not in evidence.sections
    assert "Features" not in evidence.sections
    assert "GitHub 输入" in evidence.highlights
    assert "证据链" in evidence.highlights


def test_prepare_visual_assets_annotates_storyboard_on_screenshot_success(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        screenshot_arg = next(item for item in command if str(item).startswith("--screenshot="))
        Path(str(screenshot_arg).split("=", 1)[1]).write_bytes(b"fake-png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
    monkeypatch.setattr(visual_assets, "_github_screenshot_quality_issue", lambda _path: None)
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("fake", encoding="utf-8")
    settings = Settings(chrome_exe=chrome)
    summary = RepoSummary(
        source="demo",
        repo_name="demo",
        files=[
            RepoFile(
                path="README.md",
                role="readme",
                language="Markdown",
                excerpt=(
                    "# Demo\n\n"
                    "A local RAG demo.\n\n"
                    "```bash\npython app.py\n```\n\n"
                    "- Answers questions with local retrieval evidence.\n"
                ),
                size=150,
            )
        ],
        tree_overview="README.md",
    )
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="看真实仓库。",
                visual=VisualSpec(layout="hook", headline="真实仓库"),
            ),
            Scene(
                id="scene-002",
                type="title",
                start=4,
                duration=6,
                narration="README 讲得很清楚。",
                visual=VisualSpec(layout="title", headline="项目价值"),
            ),
            Scene(
                id="scene-003",
                type="code",
                start=10,
                duration=5,
                narration="保留原本代码片段。",
                visual=VisualSpec(layout="code", headline="代码片段", code="original code"),
            ),
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url="https://github.com/example/demo",
        settings=settings,
    )

    assert enhanced.scenes[0].visual.layout == "github_hero"
    assert enhanced.scenes[0].visual.asset_path == "generated/assets/github-repo-home.png"
    assert enhanced.scenes[0].visual.repo_display_url == "example/demo"
    assert enhanced.scenes[1].visual.layout == "readme_focus"
    assert enhanced.scenes[1].visual.code is None
    assert all("python app.py" not in item for item in enhanced.scenes[1].visual.bullets)
    assert enhanced.scenes[2].visual.code == "original code"
    assert (tmp_path / "out" / "logs" / "visual-assets-manifest.json").exists()


def test_prepare_visual_assets_rejects_tiny_error_screenshot(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        screenshot_arg = next(item for item in command if str(item).startswith("--screenshot="))
        Path(str(screenshot_arg).split("=", 1)[1]).write_bytes(b"fake-png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("fake", encoding="utf-8")
    settings = Settings(chrome_exe=chrome)
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="hook",
                visual=VisualSpec(layout="hook", headline="hook"),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url="https://github.com/example/demo",
        settings=settings,
    )
    manifest = json.loads((tmp_path / "out" / "logs" / "visual-assets-manifest.json").read_text(encoding="utf-8"))

    assert manifest["github_screenshot"]["status"] == "failed"
    assert "error page or blank capture" in manifest["github_screenshot"]["reason"]
    assert enhanced.scenes[0].visual.layout == "hook"
    assert enhanced.scenes[0].visual.asset_path is None


def test_prepare_visual_assets_clears_stale_github_screenshot_asset(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        screenshot_arg = next(item for item in command if str(item).startswith("--screenshot="))
        Path(str(screenshot_arg).split("=", 1)[1]).write_bytes(b"fake-png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("fake", encoding="utf-8")
    settings = Settings(chrome_exe=chrome)
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=4,
                narration="hook",
                visual=VisualSpec(
                    layout="github_hero",
                    headline="hook",
                    asset_type="github_repo_home",
                    asset_path="generated/assets/github-repo-home.png",
                ),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url="https://github.com/example/demo",
        settings=settings,
    )

    assert enhanced.scenes[0].visual.layout == "github_hero"
    assert enhanced.scenes[0].visual.asset_type == "none"
    assert enhanced.scenes[0].visual.asset_path is None


def test_prepare_visual_assets_falls_back_when_chrome_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(visual_assets, "find_browser", lambda _settings: None)
    settings = Settings(chrome_exe=tmp_path / "missing.exe")
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="纯文字开场。",
                visual=VisualSpec(layout="hook", headline="纯文字"),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url="https://github.com/example/demo",
        settings=settings,
    )

    assert enhanced.scenes[0].visual.layout == "hook"


def test_prepare_visual_assets_rewrites_caption_that_repeats_narration(tmp_path) -> None:
    narration = "写了几千行代码，README 却没人看？试试 Repo to Shorts——输入一个 GitHub 链接，生成中文竖屏讲解视频。"
    settings = Settings()
    summary = RepoSummary(source="demo", repo_name="repo-to-shorts", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration=narration,
                visual=VisualSpec(
                    layout="hook",
                    headline="README 没人看？",
                    caption=narration,
                    bullets=["输入 GitHub 链接", "生成竖屏视频"],
                ),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url=None,
        settings=settings,
    )

    caption = enhanced.scenes[0].visual.caption
    assert caption == "仓库到短视频"
    assert caption not in narration
    assert len(caption) <= 14


def test_prepare_visual_assets_keeps_evidence_narration_with_env_example(tmp_path) -> None:
    settings = Settings()
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    narration = "它凭什么说真话？背后有个证据索引模块，把 README、.env.example、依赖文件等抽成事实列表。"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="evidence_grid",
                start=0,
                duration=8,
                narration=narration,
                visual=VisualSpec(
                    layout="evidence_grid",
                    headline="证据链：不说假话",
                    bullets=["README", ".env.example", "依赖文件"],
                ),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url=None,
        settings=settings,
    )

    assert enhanced.scenes[0].narration == narration


def test_prepare_visual_assets_assigns_motion_assets_by_layout(tmp_path) -> None:
    settings = Settings()
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="Hook",
                visual=VisualSpec(layout="hook", headline="Hook"),
            ),
            Scene(
                id="scene-002",
                type="flow",
                start=4,
                duration=12,
                narration="Workflow",
                visual=VisualSpec(
                    layout="flow",
                    headline="Workflow",
                    diagram_nodes=["Scan", "Index", "Render"],
                ),
            ),
            Scene(
                id="scene-003",
                type="code",
                start=16,
                duration=8,
                narration="Code",
                visual=VisualSpec(layout="code", headline="Code", code="print('ok')"),
            ),
            Scene(
                id="scene-004",
                type="cta",
                start=24,
                duration=4,
                narration="CTA",
                visual=VisualSpec(layout="cta", headline="CTA"),
            ),
            Scene(
                id="scene-005",
                type="result_media",
                start=28,
                duration=8,
                narration="Result",
                visual=VisualSpec(layout="result_media", headline="Result", media_type="image"),
            ),
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url=None,
        settings=settings,
    )
    manifest = json.loads((tmp_path / "out" / "logs" / "visual-assets-manifest.json").read_text(encoding="utf-8"))

    assert enhanced.scenes[0].visual.motion_asset == "repo_pulse"
    assert enhanced.scenes[1].visual.layout == "architecture_map"
    assert enhanced.scenes[1].visual.motion_asset == "data_flow"
    assert enhanced.scenes[2].visual.motion_asset == "code_scan"
    assert enhanced.scenes[3].visual.motion_asset == "spark_burst"
    assert enhanced.scenes[4].visual.motion_asset == "none"
    assert any(item.get("motion_asset") == "data_flow" for item in manifest["annotations"])


def test_prepare_visual_assets_preserves_existing_motion_asset(tmp_path) -> None:
    settings = Settings()
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="flow",
                start=0,
                duration=10,
                narration="Workflow",
                visual=VisualSpec(
                    layout="flow",
                    headline="Workflow",
                    diagram_nodes=["Scan", "Index", "Render"],
                    motion_asset="spark_burst",
                    motion_delay_ratio=0.72,
                ),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url=None,
        settings=settings,
    )

    assert enhanced.scenes[0].visual.motion_asset == "spark_burst"
    assert enhanced.scenes[0].visual.motion_delay_ratio == 0.72


def test_prepare_visual_assets_uses_cached_screenshot_when_refresh_fails(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="chrome failed")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
    monkeypatch.setattr(visual_assets, "_github_screenshot_quality_issue", lambda _path: None)
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("fake", encoding="utf-8")
    cached_public = tmp_path / "renderer" / "public" / "generated" / "assets" / "github-repo-home.png"
    cached_public.parent.mkdir(parents=True)
    cached_public.write_bytes(b"cached-png")
    settings = Settings(chrome_exe=chrome)
    summary = RepoSummary(source="demo", repo_name="demo", files=[], tree_overview="")
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="cached",
                visual=VisualSpec(layout="hook", headline="cached"),
            )
        ],
    )

    enhanced = prepare_visual_assets(
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        repo_summary=summary,
        storyboard=storyboard,
        repo_url="https://github.com/example/demo",
        settings=settings,
    )
    manifest = json.loads((tmp_path / "out" / "logs" / "visual-assets-manifest.json").read_text(encoding="utf-8"))

    assert manifest["github_screenshot"]["status"] == "cached"
    assert enhanced.scenes[0].visual.layout == "github_hero"
    assert enhanced.scenes[0].visual.asset_path == "generated/assets/github-repo-home.png"
