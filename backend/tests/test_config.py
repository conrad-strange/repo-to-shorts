from pathlib import Path

from gva.config import Settings


def test_settings_default_r2s_tts_rate_is_fast() -> None:
    assert Settings(_env_file=None).tts_rate == "+32%"


def test_settings_treats_empty_optional_values_as_none(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "REMOTION_CONCURRENCY=",
                "NODE_EXE=",
                "NPM_CMD=",
                "FFMPEG_EXE=",
                "BROWSER_EXE=",
                "CHROME_EXE=",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_path)

    assert settings.remotion_concurrency is None
    assert settings.node_exe is None
    assert settings.npm_cmd is None
    assert settings.ffmpeg_exe is None
    assert settings.browser_exe is None
    assert settings.chrome_exe is None
