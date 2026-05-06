from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from common.env import load_project_dotenv

from .render import render_campaign

load_project_dotenv()

app = typer.Typer(add_completion=False)
console = Console()


def _progress(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[{timestamp}] {message}")


@app.callback(invoke_without_command=True)
def main(
    campaign: Path = typer.Option(..., "--campaign", exists=True, file_okay=False, dir_okay=True),
    model: str | None = typer.Option(None, "--model", help="Override IMAGE_GEN_MODEL from env."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate portraits even if they already exist."),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Comma-separated NPC names to render (default: all NPCs in stages/npcs.json).",
    ),
) -> None:
    only_list = [name.strip() for name in only.split(",")] if only else None
    images_dir = render_campaign(
        campaign,
        model=model,
        overwrite=overwrite,
        only=only_list,
        progress_callback=_progress,
    )
    console.print(f"Portraits written under {images_dir}")


if __name__ == "__main__":
    app()
