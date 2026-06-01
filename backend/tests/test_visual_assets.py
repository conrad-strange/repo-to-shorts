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


def test_prepare_visual_assets_annotates_storyboard_on_screenshot_success(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        screenshot_arg = next(item for item in command if str(item).startswith("--screenshot="))
        Path(str(screenshot_arg).split("=", 1)[1]).write_bytes(b"fake-png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
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
    assert enhanced.scenes[0].visual.repo_display_url == "github.com/example/demo"
    assert enhanced.scenes[1].visual.layout == "readme_focus"
    assert enhanced.scenes[1].visual.code is None
    assert all("python app.py" not in item for item in enhanced.scenes[1].visual.bullets)
    assert enhanced.scenes[2].visual.code == "original code"
    assert (tmp_path / "out" / "logs" / "visual-assets-manifest.json").exists()


def test_prepare_visual_assets_falls_back_when_chrome_missing(tmp_path) -> None:
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


def test_prepare_visual_assets_uses_cached_screenshot_when_refresh_fails(tmp_path, monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="chrome failed")

    monkeypatch.setattr(visual_assets.subprocess, "run", fake_run)
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
