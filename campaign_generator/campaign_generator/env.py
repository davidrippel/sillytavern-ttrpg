from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_dotenv(start: str | Path | None = None) -> None:
    current = Path(start).resolve() if start is not None else Path.cwd().resolve()
    candidates = [current, *current.parents]

    for directory in candidates:
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            return
