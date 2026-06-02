from gva.config import Settings
from gva.web import app as web_app


def test_save_user_image_asset_returns_renderer_path(tmp_path, monkeypatch) -> None:
    renderer_dir = tmp_path / "renderer"
    monkeypatch.setattr(web_app, "Settings", lambda: Settings(renderer_dir=renderer_dir))
    run_dir = tmp_path / "outputs" / "demo" / "runs" / "0001"
    data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    result = web_app._save_user_image_asset(
        run_dir,
        web_app.UserImageAssetRequest(filename="result.png", data_url=data_url),
    )

    assert result["asset_path"].startswith("generated/assets/user/result-")
    assert (run_dir / "assets" / "user").exists()
    assert (renderer_dir / "public" / "generated" / "assets" / "user").exists()
