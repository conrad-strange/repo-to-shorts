from pathlib import Path

from gva.config import Settings
from gva.core import render_bridge
from gva.core.render_bridge import find_browser


def test_find_browser_prefers_browser_exe(tmp_path: Path, monkeypatch) -> None:
    browser = tmp_path / "preferred" / "msedge.exe"
    chrome = tmp_path / "chrome.exe"
    browser.parent.mkdir()
    browser.write_text("fake", encoding="utf-8")
    chrome.write_text("fake", encoding="utf-8")
    monkeypatch.setattr(render_bridge, "_default_browser_candidates", lambda: [])
    monkeypatch.setattr(render_bridge, "_registry_browser_candidates", lambda: [])
    monkeypatch.setattr(render_bridge.shutil, "which", lambda _name: None)

    settings = Settings(_env_file=None, browser_exe=browser, chrome_exe=chrome)

    assert find_browser(settings) == browser.resolve()


def test_find_browser_can_use_default_edge_candidate(tmp_path: Path, monkeypatch) -> None:
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_text("fake", encoding="utf-8")
    monkeypatch.setattr(render_bridge, "_default_browser_candidates", lambda: [edge])
    monkeypatch.setattr(render_bridge, "_registry_browser_candidates", lambda: [])
    monkeypatch.setattr(render_bridge.shutil, "which", lambda _name: None)

    assert find_browser(Settings(_env_file=None)) == edge.resolve()
