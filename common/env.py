from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_dotenv(start: str | Path | None = None) -> None:
    cwd = Path(start).resolve() if start is not None else Path.cwd().resolve()
    package_dir = Path(__file__).resolve().parent

    seen: set[Path] = set()
    candidates: list[Path] = []
    for root in (cwd, package_dir):
        for directory in (root, *root.parents):
            if directory in seen:
                continue
            seen.add(directory)
            candidates.append(directory)

    for directory in candidates:
        env_path = directory / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            return
