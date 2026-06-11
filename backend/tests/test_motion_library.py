import json
from pathlib import Path

from gva.config import Settings
from gva.core.motion_library import (
    MotionLibraryAsset,
    attach_motion_library_assets,
    download_motion_asset,
    import_motion_asset,
    list_motion_assets,
)
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def test_motion_download_skips_same_name_file(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    renderer_dir = tmp_path / "renderer"
    fallback = renderer_dir / "motion-fixtures" / "sample.json"
    _write_lottie(fallback)
    asset = MotionLibraryAsset(
        id="sample",
        filename="sample.json",
        kind="lottie",
        role="side_illustration",
        tags=("code",),
        layouts=("code",),
        fallback_path="motion-fixtures/sample.json",
    )

    first = download_motion_asset(asset, settings=settings, renderer_dir=renderer_dir, allow_network=False)
    second = download_motion_asset(asset, settings=settings, renderer_dir=renderer_dir, allow_network=False)

    assert first.status == "copied"
    assert second.status == "skipped"
    assert second.reason == "same-name file already exists"


def test_motion_import_json_and_attach_to_storyboard(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    source = tmp_path / "downloaded" / "developer-dashboard.json"
    _write_lottie(source)

    result = import_motion_asset(
        source,
        settings,
        role="side_illustration",
        tags=["code", "developer"],
        layouts=["code"],
        source_url="https://example.test/developer-dashboard",
        license_name="test-license",
    )[0]
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="code",
                start=0,
                duration=8,
                narration="Code",
                visual=VisualSpec(layout="code", headline="Code", code="print('ok')"),
            )
        ],
    )

    enhanced = attach_motion_library_assets(
        storyboard,
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        settings=settings,
    )

    visual = enhanced.scenes[0].visual
    assert result.status == "imported"
    assert visual.motion_asset_kind == "lottie"
    assert visual.motion_role == "side_illustration"
    assert visual.motion_asset_path
    assert visual.motion_asset_path.startswith("generated/motion/")
    assert (tmp_path / "renderer" / "public" / visual.motion_asset_path).exists()
    assert list_motion_assets(settings)[0]["license"] == "test-license"


def test_motion_import_zip_skips_duplicate_names(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    zip_path = tmp_path / "pack.zip"
    json_path = tmp_path / "source.json"
    _write_lottie(json_path)

    import zipfile

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(json_path, "nested/source.json")

    first = import_motion_asset(zip_path, settings, layouts=["architecture_map"])[0]
    second = import_motion_asset(zip_path, settings, layouts=["architecture_map"])[0]

    assert first.status == "imported"
    assert second.status == "skipped"


def test_motion_import_rejects_large_solid_background(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    source = tmp_path / "downloaded" / "large-background.json"
    _write_lottie(
        source,
        layers=[
            {
                "ddd": 0,
                "ind": 1,
                "ty": 1,
                "nm": "background",
                "sw": 512,
                "sh": 512,
                "sc": "#0b1220",
                "ks": {"o": {"k": 100}},
            }
        ],
    )

    result = import_motion_asset(source, settings, layouts=["github_hero"])[0]

    assert result.status == "failed"
    assert result.reason
    assert "solid layer" in result.reason


def test_motion_import_rejects_large_rectangle_background(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    source = tmp_path / "downloaded" / "large-rect.json"
    _write_lottie(
        source,
        layers=[
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,
                "nm": "shape-background",
                "ks": {"o": {"k": 100}},
                "shapes": [
                    {
                        "ty": "rc",
                        "s": {"k": [500, 500]},
                    }
                ],
            }
        ],
    )

    result = import_motion_asset(source, settings, layouts=["flow"])[0]

    assert result.status == "failed"
    assert result.reason
    assert "rectangle background" in result.reason


def test_motion_attach_does_not_add_complex_motion_to_cta(tmp_path) -> None:
    settings = Settings(motion_cache_dir=tmp_path / "cache")
    source = tmp_path / "downloaded" / "success.json"
    _write_lottie(source)
    import_motion_asset(
        source,
        settings,
        role="side_illustration",
        tags=["success", "repo"],
        layouts=["cta"],
    )
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-cta",
                type="cta",
                start=0,
                duration=4,
                narration="CTA",
                visual=VisualSpec(layout="cta", headline="Try it"),
            )
        ],
    )

    enhanced = attach_motion_library_assets(
        storyboard,
        output_dir=tmp_path / "out",
        renderer_dir=tmp_path / "renderer",
        settings=settings,
    )

    assert enhanced.scenes[0].visual.motion_asset_path is None


def _write_lottie(path: Path, *, layers: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "v": "5.13.0",
                "fr": 30,
                "w": 512,
                "h": 512,
                "ip": 0,
                "op": 90,
                "layers": layers or [{"ddd": 0, "ind": 1, "ty": 4, "nm": "shape"}],
            }
        ),
        encoding="utf-8",
    )
