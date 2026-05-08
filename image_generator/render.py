from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

from common.settings import (
    get_campaigns_base_dir,
    get_image_aspect_ratio,
    get_image_dimension,
    get_image_model,
    get_image_style_override,
)

from .client import ImageGenError, OpenRouterImageClient, resolve_size


ProgressCallback = Callable[[str], None]
_STYLE_MEDIUM_RE = re.compile(
    r"\b(?:illustration|comic|cartoon|painting|painted|"
    r"sketch|line drawing|anime|manga|watercolor|charcoal|oil(?:\s+painting)?|pulp|inked|vector|cel[- ]shaded|"
    r"3d render|digital painting)\b",
    flags=re.IGNORECASE,
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "npc"


def _apply_style_override(prompt: str, style_override: str | None) -> str:
    base_prompt = prompt.strip()
    if not base_prompt or not style_override:
        return base_prompt

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", base_prompt) if part.strip()]
    filtered = [sentence for sentence in sentences if not _STYLE_MEDIUM_RE.search(sentence)]
    cleaned = " ".join(filtered).strip()
    if not cleaned:
        cleaned = base_prompt

    override = style_override.strip()
    if override and override[-1] not in ".!?":
        override = f"{override}."
    guardrail = "Do not render as an illustration, painting, sketch, comic, or cartoon."
    return f"{cleaned} {override} {guardrail}".strip()


def resolve_campaign_dir(campaign: str | Path) -> Path:
    """Resolve a campaign directory, falling back to CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR.

    If the given path exists, it is returned. Otherwise, if CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR
    is set, the path is interpreted as a campaign name relative to that base directory.
    Raises ImageGenError if neither resolves to an existing directory.
    """
    candidate = Path(campaign)
    if candidate.exists():
        return candidate.resolve()

    base_dir = get_campaigns_base_dir()
    if base_dir is not None and not candidate.is_absolute():
        base_candidate = (base_dir / candidate).resolve()
        if base_candidate.exists():
            return base_candidate

    hint = (
        f" (also checked under CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR={base_dir})"
        if base_dir is not None and not candidate.is_absolute()
        else ""
    )
    raise ImageGenError(f"campaign directory not found: {campaign}{hint}")


def _load_npcs(campaign_dir: Path) -> list[dict]:
    npcs_path = campaign_dir / "stages" / "npcs.json"
    if not npcs_path.exists():
        raise ImageGenError(f"no NPC roster found at {npcs_path}")
    with npcs_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    npcs = data.get("npcs")
    if not isinstance(npcs, list):
        raise ImageGenError(f"unexpected npcs.json shape at {npcs_path}")
    return npcs


def _filter_only(npcs: list[dict], only: Iterable[str] | None) -> list[dict]:
    if not only:
        return npcs
    wanted = {name.strip() for name in only if name.strip()}
    if not wanted:
        return npcs
    return [npc for npc in npcs if npc.get("name") in wanted]


def render_campaign(
    campaign_dir: Path,
    *,
    model: str | None = None,
    style_override: str | None = None,
    overwrite: bool = False,
    only: Iterable[str] | None = None,
    prompts_only: bool = False,
    progress_callback: ProgressCallback | None = None,
    client: OpenRouterImageClient | None = None,
) -> Path:
    """Render NPC portraits for a generated campaign directory.

    Returns the path to the npc_images directory.
    """
    campaign_dir = resolve_campaign_dir(campaign_dir)
    npcs = _filter_only(_load_npcs(campaign_dir), only)

    resolved_model = model or get_image_model()
    resolved_style_override = style_override or get_image_style_override()
    width, height = resolve_size(get_image_dimension(), get_image_aspect_ratio())

    images_dir = campaign_dir / "npc_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = images_dir / "index.json"
    manifest: dict[str, dict] = {}
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except json.JSONDecodeError:
            manifest = {}

    image_client = None if prompts_only else (client or OpenRouterImageClient())

    if progress_callback is not None:
        if prompts_only:
            progress_callback(f"Resolving prompts for {len(npcs)} NPC(s) (no images)")
        else:
            progress_callback(
                f"Rendering portraits for {len(npcs)} NPC(s) at {width}x{height} with {resolved_model}"
            )

    used_slugs: set[str] = set()
    for npc in npcs:
        name = npc.get("name") or "Unnamed"
        prompt = (npc.get("image_generation_prompt") or "").strip()
        effective_prompt = _apply_style_override(prompt, resolved_style_override)
        slug = _slugify(name)
        candidate = slug
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{slug}_{suffix}"
            suffix += 1
        used_slugs.add(candidate)
        out_path = images_dir / f"{candidate}.png"

        if not effective_prompt:
            if progress_callback is not None:
                progress_callback(f"Skipped {name}: no image_generation_prompt (re-run --stages npcs to populate)")
            continue

        if prompts_only:
            manifest[name] = {
                "file": out_path.name,
                "prompt": effective_prompt,
                "model": resolved_model,
                "width": width,
                "height": height,
            }
            with manifest_path.open("w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2, ensure_ascii=False)
            if progress_callback is not None:
                progress_callback(f"Recorded prompt for {name}")
            continue

        if out_path.exists() and not overwrite:
            if progress_callback is not None:
                progress_callback(f"Skipped {name}: {out_path.name} already exists (use --overwrite to regenerate)")
            continue

        if progress_callback is not None:
            progress_callback(f"Generating portrait for {name}")
        try:
            image_bytes = image_client.generate(
                model=resolved_model,
                prompt=effective_prompt,
                width=width,
                height=height,
            )
        except ImageGenError as exc:
            if progress_callback is not None:
                progress_callback(f"Failed to generate portrait for {name}: {exc}")
            continue

        out_path.write_bytes(image_bytes)
        manifest[name] = {
            "file": out_path.name,
            "prompt": effective_prompt,
            "model": resolved_model,
            "width": width,
            "height": height,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
        if progress_callback is not None:
            progress_callback(f"Wrote {out_path.relative_to(campaign_dir)}")

    return images_dir
