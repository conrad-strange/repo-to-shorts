from pathlib import Path

from gva import cli
from gva.cli import _set_env_value


def test_set_env_value_updates_existing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_PROVIDER=deepseek\nNODE_EXE=\n", encoding="utf-8")

    _set_env_value(env_path, "NODE_EXE", r"C:\tools\node.exe")

    text = env_path.read_text(encoding="utf-8")
    assert "LLM_PROVIDER=deepseek" in text
    assert r"NODE_EXE=C:\tools\node.exe" in text


def test_set_env_value_appends_missing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_PROVIDER=deepseek\n", encoding="utf-8")

    _set_env_value(env_path, "DEEPSEEK_API_KEY", "test-key")

    assert "DEEPSEEK_API_KEY=test-key" in env_path.read_text(encoding="utf-8")


def test_find_powershell_uses_path(monkeypatch) -> None:
    expected = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

    def fake_which(name: str) -> str | None:
        return expected if name == "powershell.exe" else None

    monkeypatch.setattr(cli.shutil, "which", fake_which)

    assert cli._find_powershell_exe() == Path(expected)


def test_find_powershell_returns_none_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    monkeypatch.setattr(cli.Path, "exists", lambda _self: False)

    assert cli._find_powershell_exe() is None
