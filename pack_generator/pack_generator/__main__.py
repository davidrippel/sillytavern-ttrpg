from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from common.env import load_project_dotenv

from .pipeline import run_pipeline

load_project_dotenv()

app = typer.Typer(add_completion=False)
console = Console()


def _progress(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[{timestamp}] {message}")


@app.callback(invoke_without_command=True)
def main(
    brief: Path = typer.Option(..., "--brief", exists=True, file_okay=True, dir_okay=False),
    output: Path = typer.Option(..., "--output"),
    model: str | None = typer.Option(None, "--model"),
    stages: str = typer.Option("all", "--stages"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    result = run_pipeline(
        brief_path=brief,
        output_path=output,
        model=model,
        dry_run=dry_run,
        stages=stages,
        progress_callback=_progress,
    )
    console.print(f"Pack written to {result.output_dir}")


if __name__ == "__main__":
    app()
