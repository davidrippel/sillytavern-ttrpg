from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .settings import get_campaigns_base_dir, get_genres_base_dir


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "campaign"


def resolve_genre_input(genre: str | Path) -> Path:
    genre_path = Path(genre)
    if genre_path.exists():
        return genre_path.resolve()

    base_dir = get_genres_base_dir()
    if base_dir is not None:
        candidate = (base_dir / genre_path).resolve()
        if candidate.exists():
            return candidate

    return genre_path


def build_auto_campaign_dir_name(*, pack_name: str, seed_path: str | Path, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    seed_stem = _slugify(Path(seed_path).stem)
    pack_slug = _slugify(pack_name)
    return f"{timestamp}_{pack_slug}_{seed_stem}"


def resolve_output_path(
    *,
    output: str | Path | None,
    pack_name: str,
    seed_path: str | Path,
    now: datetime | None = None,
) -> Path:
    if output is not None:
        return Path(output).resolve()

    base_dir = get_campaigns_base_dir()
    if base_dir is None:
        raise ValueError(
            "--output was not provided and CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR is not set"
        )

    return (base_dir / build_auto_campaign_dir_name(pack_name=pack_name, seed_path=seed_path, now=now)).resolve()
