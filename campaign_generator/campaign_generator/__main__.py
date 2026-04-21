from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .env import load_project_dotenv
from .pack import load_pack
from .pipeline import run_pipeline
from .settings import get_default_model
from .seed_template import write_seed_template

load_project_dotenv()

app = typer.Typer(add_completion=False)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    genre: Path | None = typer.Option(None, "--genre", exists=True, file_okay=False, dir_okay=True),
    seed: Path | None = typer.Option(None, "--seed", exists=True, file_okay=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", file_okay=False, dir_okay=True),
    model: str | None = typer.Option(None, "--model"),
    stages: str = typer.Option("all", "--stages"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    random_seed: int | None = typer.Option(None, "--random-seed"),
    init_seed: Path | None = typer.Option(None, "--init-seed"),
) -> None:
    if init_seed is not None:
        if genre is None:
            raise typer.BadParameter("--genre is required with --init-seed")
        pack = load_pack(genre)
        destination = write_seed_template(init_seed, pack)
        console.print(f"Wrote seed template to {destination}")
        return

    if genre is None or seed is None or output is None:
        raise typer.BadParameter("--genre, --seed, and --output are required for generation")

    result = run_pipeline(
        genre_path=genre,
        seed_path=seed,
        output_path=output,
        model=model or get_default_model(),
        dry_run=dry_run,
        random_seed=random_seed,
        stages=stages,
    )
    console.print(f"Campaign written to {result.output_dir}")


if __name__ == "__main__":
    app()
