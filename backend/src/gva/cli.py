from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from gva.config import Settings
from gva.agents.evaluator import evaluate_output
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
        help="Visual strategy: remotion-primary or hyperframes-primary.",
    ),
    allow_unverified: bool = typer.Option(
        False,
        "--allow-unverified",
        help="Continue after high-severity verifier findings. Intended for debugging only.",
    ),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Optional explicit run id, such as 0003."),
) -> None:
    """Run the MVP repo-to-storyboard workflow."""
    settings = Settings()
    settings.render_strategy = render_strategy
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
    if result.metadata.get("latest_video_path"):
        console.print(f"Latest video: [bold]{result.metadata['latest_video_path']}[/bold]")
    if result.metadata.get("verification_passed") is not None:
        console.print(f"Verifier passed: [bold]{result.metadata['verification_passed']}[/bold]")
    if result.metadata.get("evaluation_score") is not None:
        console.print(f"Evaluation score: [bold]{result.metadata['evaluation_score']}[/bold]")
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


if __name__ == "__main__":
    app()
