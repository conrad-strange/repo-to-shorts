from pathlib import Path
import getpass
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from gva.config import Settings
from gva.agents.evaluator import evaluate_output
from gva.core.llm_client import llm_settings_error, normalize_llm_provider, has_real_api_key
from gva.core.render_bridge import find_ffmpeg, find_node, find_npm
from gva.core.runs import clean_old_runs, list_run_ids, resolve_run_dir
from gva.workflow import run_render_workflow

app = typer.Typer(help="Generate Chinese vertical explainer videos from code projects.")
console = Console()


@app.callback()
def main() -> None:
    """GitHub Video Agent command line interface."""


@app.command()
def render(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Local project path to analyze."),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Public GitHub repository URL to analyze."),
    out: Path = typer.Option(Path("outputs/demo"), "--out", "-o", help="Output directory."),
    target_duration: Optional[int] = typer.Option(
        None,
        "--target-duration",
        help="Optional target video duration in seconds. Leave empty for automatic timing.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Generate structured planning files without rendering video yet.",
    ),
    force_insight: bool = typer.Option(False, "--force-insight", help="Regenerate project insight."),
    force_script: bool = typer.Option(False, "--force-script", help="Regenerate script and downstream artifacts."),
    force_storyboard: bool = typer.Option(False, "--force-storyboard", help="Regenerate storyboard and downstream artifacts."),
    force_tts: bool = typer.Option(False, "--force-tts", help="Regenerate TTS and downstream artifacts."),
    force_render: bool = typer.Option(False, "--force-render", help="Regenerate video render and evaluation."),
    render_strategy: str = typer.Option(
        "remotion-primary",
        "--render-strategy",
        help="Visual strategy. The current product line supports remotion-primary.",
    ),
    video_mode: str = typer.Option(
        "standard_60s",
        "--video-mode",
        help="Planned pacing mode: short_30s, standard_60s, or technical_90s.",
    ),
    render_profile: str = typer.Option(
        "final",
        "--render-profile",
        help="Render size profile: draft, preview, or final. CLI defaults to final.",
    ),
    remotion_concurrency: Optional[int] = typer.Option(
        None,
        "--remotion-concurrency",
        min=1,
        help="Optional Remotion frame-rendering concurrency override.",
    ),
    allow_unverified: bool = typer.Option(
        False,
        "--allow-unverified",
        help="Continue after high-severity verifier findings. Intended for debugging only.",
    ),
    auto_repair: bool = typer.Option(
        True,
        "--auto-repair/--no-auto-repair",
        help="Automatically ask the Repair Agent to rewrite unsupported claims once before stopping.",
    ),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Optional explicit run id, such as 0003."),
) -> None:
    """Run the MVP repo-to-storyboard workflow."""
    settings = Settings()
    settings.render_strategy = render_strategy
    settings.video_mode = video_mode
    settings.render_profile = render_profile
    settings.remotion_concurrency = remotion_concurrency
    settings.repair_enabled = auto_repair
    result = run_render_workflow(
        project_path=path,
        repo_url=repo,
        output_dir=out,
        settings=settings,
        target_duration_seconds=target_duration,
        dry_run=dry_run,
        force_insight=force_insight,
        force_script=force_script,
        force_storyboard=force_storyboard,
        force_tts=force_tts,
        force_render=force_render,
        allow_unverified=allow_unverified,
        run_id=run_id,
    )
    console.print("[green]Workflow completed.[/green]")
    console.print(f"Run id: [bold]{result.metadata.get('run_id', 'unknown')}[/bold]")
    console.print(f"Run directory: [bold]{result.output_dir}[/bold]")
    if result.metadata.get("video_path"):
        console.print(f"Video: [bold]{result.metadata['video_path']}[/bold]")
    if result.metadata.get("verification_passed") is not None:
        console.print(f"Verifier passed: [bold]{result.metadata['verification_passed']}[/bold]")
    if result.metadata.get("evaluation_score") is not None:
        console.print(f"Evaluation score: [bold]{result.metadata['evaluation_score']}[/bold]")
    if result.metadata.get("demo_report_path"):
        console.print(f"Demo report: [bold]{result.metadata['demo_report_path']}[/bold]")
    if result.metadata.get("next_step_requires"):
        console.print(f"[yellow]Next step requires: {result.metadata['next_step_requires']}[/yellow]")


@app.command("runs")
def runs_command(
    out: Path = typer.Option(Path("outputs/demo"), "--out", "-o", help="Output root directory."),
) -> None:
    """List versioned render runs."""
    ids = list_run_ids(out)
    if not ids:
        console.print("[yellow]No runs found.[/yellow]")
        return
    for run_id in ids:
        console.print(run_id)


@app.command("eval")
def eval_command(
    out: Path = typer.Option(Path("outputs/demo"), "--out", "-o", help="Output root directory."),
    run: str = typer.Option("latest", "--run", help="Run id or latest."),
) -> None:
    """Re-run artifact and media evaluation for a run."""
    settings = Settings()
    run_dir = resolve_run_dir(out, run)
    report = evaluate_output(run_dir, settings)
    console.print(f"Run directory: [bold]{run_dir}[/bold]")
    console.print(f"Passed: [bold]{report.passed}[/bold]")
    console.print(f"Score: [bold]{report.score}[/bold]")


@app.command("clean")
def clean_command(
    out: Path = typer.Option(Path("outputs/demo"), "--out", "-o", help="Output root directory."),
    keep: int = typer.Option(3, "--keep", min=1, help="Number of newest runs to keep."),
) -> None:
    """Delete older versioned runs."""
    removed = clean_old_runs(out, keep)
    console.print(f"Removed {len(removed)} run(s).")
    for path in removed:
        console.print(str(path))


@app.command("setup")
def setup_command(
    portable: bool = typer.Option(
        False,
        "--portable/--no-portable",
        help="Download portable Node.js and FFmpeg under .tools on Windows.",
    ),
    skip_build: bool = typer.Option(
        False,
        "--skip-build",
        help="Skip npm install/build steps and only prepare .env/tools.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Answer yes to non-secret setup prompts.",
    ),
) -> None:
    """Prepare .env, tools, JS dependencies, frontend build, then run doctor."""
    env_path = Path(".env")
    env_example = Path(".env.example")
    if not env_path.exists():
        if not env_example.exists():
            raise FileNotFoundError(".env.example does not exist.")
        shutil.copyfile(env_example, env_path)
        console.print("[green]Created .env from .env.example.[/green]")
    else:
        console.print("[green].env already exists.[/green]")

    if portable:
        _run_portable_tools_installer()

    settings = Settings()
    _prompt_for_missing_llm(settings, yes=yes)
    settings = Settings()

    if not skip_build:
        _install_node_package(settings, settings.renderer_dir.resolve(), build=False)
        _install_node_package(settings, settings.frontend_dir.resolve(), build=True)

    console.print("[green]Setup finished. Running doctor...[/green]")
    doctor_command()


@app.command("doctor")
def doctor_command() -> None:
    """Check local dependencies needed by the web UI and renderer."""
    settings = Settings()
    checks: list[tuple[str, bool, str, str, bool]] = []

    checks.append(("Python", sys.version_info >= (3, 11), sys.version.split()[0], "Use Python 3.11+.", True))
    checks.append((".env", Path(".env").exists(), ".env found", "Run: copy .env.example .env", True))

    provider = normalize_llm_provider(settings.llm_provider)
    llm_error = llm_settings_error(settings)
    checks.append(("LLM provider", llm_error is None, provider, llm_error or "Configured", True))

    node_path, node_detail = _tool_detail(lambda: find_node(settings), ["-v"])
    node_ok = bool(node_path) and _node_version_ok(node_detail)
    checks.append(("Node.js", node_ok, node_detail, "Install Node.js 20.19+ or run scripts/install-portable-tools.ps1.", True))

    npm_path, npm_detail = _tool_detail(lambda: find_npm(settings), ["-v"])
    checks.append(("npm", bool(npm_path), npm_detail, "Install Node.js/npm or run scripts/install-portable-tools.ps1.", True))

    ffmpeg_path, ffmpeg_detail = _tool_detail(lambda: find_ffmpeg(settings), ["-version"], first_line=True)
    checks.append(("FFmpeg", bool(ffmpeg_path), ffmpeg_detail, "Install FFmpeg or run scripts/install-portable-tools.ps1.", True))

    chrome = settings.chrome_exe.resolve() if settings.chrome_exe else None
    chrome_ok = bool(chrome and chrome.exists())
    checks.append(("Chrome", chrome_ok, "Configured" if chrome_ok else "Optional", "Optional. Used for GitHub screenshots.", False))

    frontend_dir = settings.frontend_dir.resolve()
    renderer_dir = settings.renderer_dir.resolve()
    checks.append(("Frontend package", (frontend_dir / "package.json").exists(), str(frontend_dir), "Missing frontend/package.json.", True))
    checks.append(("Frontend build", (frontend_dir / "dist" / "index.html").exists(), "dist/index.html found", "gva ui builds it automatically.", False))
    checks.append(("Renderer package", (renderer_dir / "package.json").exists(), str(renderer_dir), "Missing renderer/package.json.", True))
    checks.append(("Renderer deps", (renderer_dir / "node_modules").exists(), "node_modules found", "Renderer deps install automatically before render.", False))

    table = Table(title="Repo to Shorts Doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Hint")

    failed_required = False
    for name, ok, detail, hint, required in checks:
        status = "[green]OK[/green]" if ok else ("[red]Missing[/red]" if required else "[yellow]Optional[/yellow]")
        table.add_row(name, status, detail, "" if ok else hint)
        failed_required = failed_required or (required and not ok)

    console.print(table)
    if failed_required:
        raise typer.Exit(1)


@app.command("ui")
def ui_command(
    host: str = typer.Option("127.0.0.1", "--host", help="Local host for the web UI."),
    port: int = typer.Option(7860, "--port", min=1, max=65535, help="Local port for the web UI."),
    rebuild_frontend: bool = typer.Option(
        False,
        "--rebuild-frontend",
        help="Rebuild the bundled React UI before starting.",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open-browser/--no-open-browser",
        help="Open the local UI in the default browser.",
    ),
) -> None:
    """Start the single-command local web UI."""
    from gva.web.app import main as run_web_ui

    console.print(f"[green]Starting Repo to Shorts UI on http://{host}:{port}[/green]")
    run_web_ui(host=host, port=port, rebuild_frontend=rebuild_frontend, open_browser=open_browser)


def _tool_detail(
    resolver,
    version_args: list[str],
    first_line: bool = False,
) -> tuple[Path | None, str]:
    try:
        path = resolver()
    except Exception as exc:
        return None, str(exc)
    try:
        completed = subprocess.run(
            [str(path), *version_args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=8,
        )
    except Exception as exc:
        return path, f"{path} ({exc.__class__.__name__})"
    output = (completed.stdout or completed.stderr or "").strip()
    if first_line and output:
        output = output.splitlines()[0]
    return path, output or f"{path.name} found"


def _run_portable_tools_installer() -> None:
    if sys.platform != "win32":
        console.print("[yellow]Portable tools installer is Windows-only. Skipping.[/yellow]")
        return
    script = Path("scripts") / "install-portable-tools.ps1"
    if not script.exists():
        raise FileNotFoundError(f"Portable tools script does not exist: {script}")
    console.print("[cyan]Installing portable Node.js and FFmpeg under .tools...[/cyan]")
    powershell = _find_powershell_exe()
    if powershell is None:
        console.print(
            "[red]PowerShell was not found.[/red]\n"
            "Please check that Windows PowerShell exists at "
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe, "
            "or add PowerShell/pwsh to PATH, then rerun: gva setup --portable"
        )
        raise typer.Exit(1)
    try:
        subprocess.run(
            [
                str(powershell),
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        console.print(
            "[red]Portable tools installer failed.[/red]\n"
            "If the error mentions ZipArchive, Expand-Archive, or a missing central directory, "
            "the downloaded zip is likely damaged. Delete .tools/downloads and rerun: gva setup --portable"
        )
        raise typer.Exit(exc.returncode)


def _find_powershell_exe() -> Path | None:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return Path(found)
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windir / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        windir / "Sysnative" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
        Path(r"C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe"),
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
    ]
    return next((path for path in candidates if path.exists()), None)


def _prompt_for_missing_llm(settings: Settings, yes: bool = False) -> None:
    provider = normalize_llm_provider(settings.llm_provider)
    if provider == "deepseek":
        if not has_real_api_key(settings.deepseek_api_key):
            _prompt_secret_to_env("DEEPSEEK_API_KEY", "Enter DEEPSEEK_API_KEY")
        return
    if provider == "openai":
        if not has_real_api_key(settings.openai_api_key):
            _prompt_secret_to_env("OPENAI_API_KEY", "Enter OPENAI_API_KEY")
        return
    if provider == "openai_compatible":
        if not has_real_api_key(settings.openai_compatible_api_key):
            _prompt_secret_to_env("OPENAI_COMPATIBLE_API_KEY", "Enter OPENAI_COMPATIBLE_API_KEY")
        if not (settings.openai_compatible_base_url or "").strip():
            _prompt_value_to_env("OPENAI_COMPATIBLE_BASE_URL", "Enter OPENAI_COMPATIBLE_BASE_URL")
        if not (settings.openai_compatible_model_generation or "").strip():
            _prompt_value_to_env("OPENAI_COMPATIBLE_MODEL_GENERATION", "Enter OPENAI_COMPATIBLE_MODEL_GENERATION")
        if yes and not (settings.openai_compatible_model_reasoning or "").strip():
            return
        if not (settings.openai_compatible_model_reasoning or "").strip():
            value = input("Enter OPENAI_COMPATIBLE_MODEL_REASONING (optional, press Enter to reuse generation model): ").strip()
            if value:
                _set_env_value(Path(".env"), "OPENAI_COMPATIBLE_MODEL_REASONING", value)
        return
    console.print(f"[yellow]Unsupported LLM_PROVIDER in .env: {settings.llm_provider}[/yellow]")


def _prompt_secret_to_env(key: str, prompt: str) -> None:
    value = getpass.getpass(f"{prompt}: ").strip()
    if not value:
        console.print(f"[yellow]{key} not set. You can fill it in .env later.[/yellow]")
        return
    _set_env_value(Path(".env"), key, value)
    console.print(f"[green]{key} saved to .env.[/green]")


def _prompt_value_to_env(key: str, prompt: str) -> None:
    value = input(f"{prompt}: ").strip()
    if not value:
        console.print(f"[yellow]{key} not set. You can fill it in .env later.[/yellow]")
        return
    _set_env_value(Path(".env"), key, value)
    console.print(f"[green]{key} saved to .env.[/green]")


def _set_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pattern = re.compile(rf"^{re.escape(key)}=")
    updated = False
    next_lines = []
    for line in lines:
        if pattern.match(line):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        next_lines.append(f"{key}={value}")
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def _install_node_package(settings: Settings, directory: Path, build: bool = False) -> None:
    package_json = directory / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"package.json does not exist: {package_json}")
    npm = find_npm(settings)
    env = _npm_setup_env(npm)
    if not (directory / "node_modules").exists():
        console.print(f"[cyan]Installing npm dependencies in {directory}...[/cyan]")
        _run_npm_command(npm, ["install", "--no-audit", "--no-fund"], directory, env)
    else:
        console.print(f"[green]npm dependencies already exist in {directory}.[/green]")
    if build:
        console.print(f"[cyan]Building frontend in {directory}...[/cyan]")
        _run_npm_command(npm, ["run", "build"], directory, env)


def _npm_setup_env(npm: Path) -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = (Path(".tools") / "npm-cache").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["npm_config_cache"] = str(cache_dir)
    env["npm_config_audit"] = "false"
    env["npm_config_fund"] = "false"
    env["npm_config_update_notifier"] = "false"
    env["PATH"] = f"{npm.parent};{env.get('PATH', '')}"
    return env


def _run_npm_command(npm: Path, args: list[str], cwd: Path, env: dict[str, str]) -> None:
    command = [str(npm), *args]
    try:
        subprocess.run(command, cwd=cwd, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        console.print(
            "[red]npm install/build failed.[/red]\n"
            f"Command: {' '.join(command)}\n"
            f"Working directory: {cwd}\n"
            "Repo to Shorts uses a project-local npm cache at .tools/npm-cache during setup. "
            "If the failure is a network or registry issue, delete .tools/npm-cache/_logs after checking it, "
            "then rerun: gva setup --portable"
        )
        raise typer.Exit(exc.returncode)


def _node_version_ok(detail: str) -> bool:
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", detail)
    if not match:
        return False
    major, minor, _patch = (int(part) for part in match.groups())
    return major > 22 or (major == 22 and minor >= 12) or (major == 20 and minor >= 19)


if __name__ == "__main__":
    app()
