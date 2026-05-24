"""Shared helpers for building NPC portrait prompt manifests.

Both `campaign_generator` (which writes the manifest at the end of the npcs
stage) and `image_generator` (which renders portraits from it) use these to
produce identical `npc_images/index.json` entries.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from .settings import (
    get_campaigns_base_dir,
    get_image_aspect_ratio,
    get_image_dimension,
    get_image_model,
    get_image_style_override,
)


class PortraitPromptError(RuntimeError):
    """Raised when NPC portrait prompts cannot be resolved."""


_STYLE_MEDIUM_RE = re.compile(
    r"\b(?:illustration|comic|cartoon|painting|painted|"
    r"sketch|line drawing|anime|manga|watercolor|charcoal|oil(?:\s+painting)?|pulp|inked|vector|cel[- ]shaded|"
    r"3d render|digital painting)\b",
    flags=re.IGNORECASE,
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "npc"


def apply_style_override(prompt: str, style_override: str | None) -> str:
    base_prompt = prompt.strip()
    if not base_prompt or not style_override:
        return base_prompt

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", base_prompt) if part.strip()]
    filtered = [sentence for sentence in sentences if not _STYLE_MEDIUM_RE.search(sentence)]
    cleaned = " ".join(filtered).strip() or base_prompt

    override = style_override.strip()
    if override and override[-1] not in ".!?":
        override = f"{override}."
    guardrail = "Do not render as an illustration, painting, sketch, comic, or cartoon."
    return f"{cleaned} {override} {guardrail}".strip()


def resolve_image_size() -> tuple[int, int]:
    """Resolve (width, height) from IMAGE_GEN_DIMENSION and IMAGE_GEN_ASPECT_RATIO."""
    dimension = get_image_dimension()
    aspect_ratio = get_image_aspect_ratio()
    try:
        w_str, h_str = aspect_ratio.split(":", 1)
        w_ratio = float(w_str)
        h_ratio = float(h_str)
    except (ValueError, AttributeError) as exc:
        raise PortraitPromptError(
            f"invalid IMAGE_GEN_ASPECT_RATIO {aspect_ratio!r}; expected W:H"
        ) from exc
    if w_ratio <= 0 or h_ratio <= 0:
        raise PortraitPromptError(
            f"aspect ratio components must be positive, got {aspect_ratio!r}"
        )
    if w_ratio >= h_ratio:
        width = dimension
        height = int(round(dimension * (h_ratio / w_ratio) / 8) * 8)
    else:
        height = dimension
        width = int(round(dimension * (w_ratio / h_ratio) / 8) * 8)
    return max(width, 8), max(height, 8)


def resolve_campaign_dir(campaign: str | Path) -> Path:
    """Resolve a campaign directory, falling back to CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR."""
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
    raise PortraitPromptError(f"campaign directory not found: {campaign}{hint}")


def load_npcs(campaign_dir: Path) -> list[dict]:
    npcs_path = campaign_dir / "stages" / "npcs.json"
    if not npcs_path.exists():
        raise PortraitPromptError(f"no NPC roster found at {npcs_path}")
    with npcs_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    npcs = data.get("npcs")
    if not isinstance(npcs, list):
        raise PortraitPromptError(f"unexpected npcs.json shape at {npcs_path}")
    return npcs


def filter_npcs(npcs: list[dict], only: Iterable[str] | None) -> list[dict]:
    if not only:
        return npcs
    wanted = {name.strip() for name in only if name.strip()}
    if not wanted:
        return npcs
    return [npc for npc in npcs if npc.get("name") in wanted]


def resolve_portrait_entries(
    npcs: list[dict],
    *,
    model: str,
    style_override: str | None,
    width: int,
    height: int,
) -> list[tuple[dict, str, str, str]]:
    """Build (npc, name, slug_filename, effective_prompt) tuples for the given NPCs.

    Slug uniqueness is enforced within the returned list. NPCs with an empty
    `image_generation_prompt` are still returned (with `effective_prompt == ""`)
    so callers can decide whether to skip or warn.
    """
    used_slugs: set[str] = set()
    entries: list[tuple[dict, str, str, str]] = []
    for npc in npcs:
        name = npc.get("name") or "Unnamed"
        prompt = (npc.get("image_generation_prompt") or "").strip()
        effective_prompt = apply_style_override(prompt, style_override)
        slug = slugify(name)
        candidate = slug
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{slug}_{suffix}"
            suffix += 1
        used_slugs.add(candidate)
        entries.append((npc, name, f"{candidate}.png", effective_prompt))
    return entries


def manifest_entry(
    *,
    filename: str,
    prompt: str,
    model: str,
    width: int,
    height: int,
) -> dict:
    return {
        "file": filename,
        "prompt": prompt,
        "model": model,
        "width": width,
        "height": height,
    }


def read_manifest(manifest_path: Path) -> dict[str, dict]:
    if not manifest_path.exists():
        return {}
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {}


def write_manifest(manifest_path: Path, manifest: dict[str, dict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)


def write_portrait_index(
    campaign_dir: Path,
    *,
    model: str | None = None,
    style_override: str | None = None,
    only: Iterable[str] | None = None,
) -> Path:
    """Build and write `<campaign_dir>/npc_images/index.json` from stages/npcs.json.

    Returns the path to the written index. Skips NPCs with no
    `image_generation_prompt`. Merges over any existing entries (preserving
    fields like `generated_at` on entries the renderer has already produced).
    """
    if model is not None:
        resolved_model = model
    else:
        try:
            resolved_model = get_image_model()
        except RuntimeError as exc:
            raise PortraitPromptError(str(exc)) from exc
    resolved_style_override = style_override or get_image_style_override()
    width, height = resolve_image_size()

    npcs = filter_npcs(load_npcs(campaign_dir), only)
    images_dir = campaign_dir / "npc_images"
    manifest_path = images_dir / "index.json"
    manifest = read_manifest(manifest_path)

    for _npc, name, filename, effective_prompt in resolve_portrait_entries(
        npcs,
        model=resolved_model,
        style_override=resolved_style_override,
        width=width,
        height=height,
    ):
        if not effective_prompt:
            continue
        existing = manifest.get(name, {})
        new_entry = manifest_entry(
            filename=filename,
            prompt=effective_prompt,
            model=resolved_model,
            width=width,
            height=height,
        )
        # Preserve generated_at when the rendered image's prompt hasn't changed.
        if (
            "generated_at" in existing
            and existing.get("prompt") == effective_prompt
            and existing.get("file") == filename
        ):
            new_entry["generated_at"] = existing["generated_at"]
        manifest[name] = new_entry

    write_manifest(manifest_path, manifest)
    return manifest_path
