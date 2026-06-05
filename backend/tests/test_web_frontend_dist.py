import os
from pathlib import Path

from gva.web import app as web_app


def test_frontend_source_newer_than_dist_when_src_changes(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend"
    src_dir = frontend_dir / "src"
    dist_dir = frontend_dir / "dist"
    src_dir.mkdir(parents=True)
    dist_dir.mkdir()
    index_html = dist_dir / "index.html"
    app_tsx = src_dir / "App.tsx"
    index_html.write_text("<html></html>", encoding="utf-8")
    app_tsx.write_text("export const App = () => null;", encoding="utf-8")

    os.utime(index_html, ns=(1_000_000_000, 1_000_000_000))
    os.utime(app_tsx, ns=(2_000_000_000, 2_000_000_000))

    assert web_app._frontend_source_newer_than(index_html, frontend_dir)


def test_frontend_source_not_newer_than_fresh_dist(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend"
    src_dir = frontend_dir / "src"
    dist_dir = frontend_dir / "dist"
    src_dir.mkdir(parents=True)
    dist_dir.mkdir()
    index_html = dist_dir / "index.html"
    app_tsx = src_dir / "App.tsx"
    index_html.write_text("<html></html>", encoding="utf-8")
    app_tsx.write_text("export const App = () => null;", encoding="utf-8")

    os.utime(app_tsx, ns=(1_000_000_000, 1_000_000_000))
    os.utime(index_html, ns=(2_000_000_000, 2_000_000_000))

    assert not web_app._frontend_source_newer_than(index_html, frontend_dir)
