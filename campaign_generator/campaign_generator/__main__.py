from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from common.env import load_project_dotenv
from .paths import resolve_genre_input, resolve_output_path
from common.pack import load_pack
from .pipeline import run_pipeline
from common.settings import get_default_model
from .seed_template import write_seed_template

load_project_dotenv()

app = typer.Typer(add_completion=False)
console = Console()


def _progress(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[{timestamp}] {message}")


@app.callback(invoke_without_command=True)
def main(
    genre: str | None = typer.Option(None, "--genre"),
    seed: Path | None = typer.Option(None, "--seed", exists=True, file_okay=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output"),
    model: str | None = typer.Option(None, "--model"),
    stages: str = typer.Option("all", "--stages"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    random_seed: int | None = typer.Option(None, "--random-seed"),
    init_seed: Path | None = typer.Option(None, "--init-seed"),
) -> None:
    if init_seed is not None:
        if genre is None:
            raise typer.BadParameter("--genre is required with --init-seed")
        pack = load_pack(resolve_genre_input(genre))
        destination = write_seed_template(init_seed, pack)
        console.print(f"Wrote seed template to {destination}")
        return

    if genre is None or seed is None:
        raise typer.BadParameter("--genre and --seed are required for generation")

    resolved_genre = resolve_genre_input(genre)
    pack = load_pack(resolved_genre)
    resolved_output = resolve_output_path(
        output=output,
        pack_name=pack.metadata.pack_name,
        seed_path=seed,
    )

    result = run_pipeline(
        genre_path=resolved_genre,
        seed_path=seed,
        output_path=resolved_output,
        model=model or get_default_model(),
        dry_run=dry_run,
        random_seed=random_seed,
        stages=stages,
        progress_callback=_progress,
    )
    console.print(f"Campaign written to {result.output_dir}")


if __name__ == "__main__":
    app()
