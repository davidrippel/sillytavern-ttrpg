from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

from common.portrait_prompts import (
    PortraitPromptError,
    filter_npcs,
    load_npcs,
    manifest_entry,
    read_manifest,
    resolve_campaign_dir as _resolve_campaign_dir,
    resolve_image_size,
    resolve_portrait_entries,
    write_manifest,
)
from common.settings import (
    get_image_model,
    get_image_style_override,
)

from .client import ImageGenError, OpenRouterImageClient


ProgressCallback = Callable[[str], None]


def resolve_campaign_dir(campaign: str | Path) -> Path:
    """Resolve a campaign directory, raising ImageGenError on failure.

    Thin wrapper that re-raises common's PortraitPromptError as ImageGenError to
    preserve the renderer's historical exception type.
    """
    try:
        return _resolve_campaign_dir(campaign)
    except PortraitPromptError as exc:
        raise ImageGenError(str(exc)) from exc


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
    try:
        npcs = filter_npcs(load_npcs(campaign_dir), only)
    except PortraitPromptError as exc:
        raise ImageGenError(str(exc)) from exc

    resolved_model = model or get_image_model()
    resolved_style_override = style_override or get_image_style_override()
    try:
        width, height = resolve_image_size()
    except PortraitPromptError as exc:
        raise ImageGenError(str(exc)) from exc

    images_dir = campaign_dir / "npc_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = images_dir / "index.json"
    manifest = read_manifest(manifest_path)

    image_client = None if prompts_only else (client or OpenRouterImageClient())

    if progress_callback is not None:
        if prompts_only:
            progress_callback(f"Resolving prompts for {len(npcs)} NPC(s) (no images)")
        else:
            progress_callback(
                f"Rendering portraits for {len(npcs)} NPC(s) at {width}x{height} with {resolved_model}"
            )

    entries = resolve_portrait_entries(
        npcs,
        model=resolved_model,
        style_override=resolved_style_override,
        width=width,
        height=height,
    )
    for _npc, name, filename, effective_prompt in entries:
        out_path = images_dir / filename

        if not effective_prompt:
            if progress_callback is not None:
                progress_callback(f"Skipped {name}: no image_generation_prompt (re-run --stages npcs to populate)")
            continue

        if prompts_only:
            manifest[name] = manifest_entry(
                filename=filename,
                prompt=effective_prompt,
                model=resolved_model,
                width=width,
                height=height,
            )
            write_manifest(manifest_path, manifest)
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
        entry = manifest_entry(
            filename=filename,
            prompt=effective_prompt,
            model=resolved_model,
            width=width,
            height=height,
        )
        entry["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest[name] = entry
        write_manifest(manifest_path, manifest)
        if progress_callback is not None:
            progress_callback(f"Wrote {out_path.relative_to(campaign_dir)}")

    return images_dir
