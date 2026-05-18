from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.pack import GenrePack


class SeedValidationError(ValueError):
    pass


class StrictnessConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    truth_adjacency: str | None = None
    npc_voice_diversity: str | None = None
    canon_consistency: str | None = None


class CampaignSeed(BaseModel):
    """Campaign-generator seed (v2 / story-mode).

    The fields ``num_acts``, ``nodes_per_act``, ``clue_chain_density``,
    and ``branch_points`` from v1 are retired. v2 introduces ``num_truths``
    and ``num_complications`` and adds ``num_factions`` to the count
    block.
    """

    model_config = ConfigDict(extra="allow")

    genre: str
    campaign_pitch: str | None = None
    themes_include: list[str] | None = None
    themes_exclude: list[str] | None = None
    protagonist_archetype: str | None = None
    protagonist_known_facts: list[str] | None = None
    setting_anchors: list[str] | None = None
    antagonist_archetypes_preferred: list[str] | None = None
    opening_hook_seed: str | None = None
    tone_modifiers: list[str] | None = None
    tone: list[str] | None = None
    image_style_hint: str | None = None
    num_npcs: int | None = None
    num_locations: int | None = None
    num_factions: int | None = None
    num_truths: int | None = None
    num_complications: int | None = None
    num_sample_characters: int | None = None
    random_seed: int | None = None
    model: str | None = None
    temperature: float | None = None
    strictness: StrictnessConfig | None = None

    @model_validator(mode="after")
    def validate_theme_contradictions(self) -> "CampaignSeed":
        include = set(self.themes_include or [])
        exclude = set(self.themes_exclude or [])
        overlap = sorted(include & exclude)
        if overlap:
            raise ValueError(f"themes_include and themes_exclude overlap: {overlap}")
        return self


class LoadedSeed(BaseModel):
    raw: dict[str, Any]
    resolved: CampaignSeed
    warnings: list[str] = Field(default_factory=list)


KNOWN_SEED_FIELDS = set(CampaignSeed.model_fields)

# Retired v1 fields. If a seed file (or pack defaults) still carries
# them, we ignore them with a warning rather than failing — the user
# may be carrying forward a half-migrated pack while they iterate.
RETIRED_SEED_FIELDS = {"num_acts", "nodes_per_act", "clue_chain_density", "branch_points"}


def _read_seed_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SeedValidationError("seed file must be a YAML mapping")
    return data


def _merge_seed_defaults(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    for key, value in overrides.items():
        if value is None:
            continue
        if key == "themes_exclude":
            merged[key] = list(dict.fromkeys([*(merged.get(key, []) or []), *value]))
            continue
        if key == "strictness":
            strictness = dict(merged.get(key, {}) or {})
            strictness.update(value)
            merged[key] = strictness
            continue
        merged[key] = value
    return merged


def load_seed(path: str | Path, pack: GenrePack) -> LoadedSeed:
    seed_path = Path(path).resolve()
    raw = _read_seed_file(seed_path)
    warnings: list[str] = []

    unknown = sorted(set(raw) - KNOWN_SEED_FIELDS - RETIRED_SEED_FIELDS)
    if unknown:
        warnings.extend(f"Unknown seed field ignored: {field}" for field in unknown)

    retired_present = sorted(set(raw) & RETIRED_SEED_FIELDS)
    if retired_present:
        warnings.append(
            f"Retired v1 seed fields ignored: {retired_present}. v2 uses "
            "num_truths / num_complications / num_factions instead."
        )

    if raw.get("genre") != pack.metadata.pack_name:
        raise SeedValidationError(
            f"seed genre mismatch: expected {pack.metadata.pack_name}, got {raw.get('genre')!r}"
        )

    # Strip retired fields before merging so they don't end up in the
    # pack defaults' carry-forward.
    sanitized = {k: v for k, v in raw.items() if k not in RETIRED_SEED_FIELDS}
    pack_defaults = {k: v for k, v in pack.generator_seed_defaults.items() if k not in RETIRED_SEED_FIELDS}
    merged = _merge_seed_defaults(pack_defaults, sanitized)
    resolved = CampaignSeed.model_validate(merged)

    pack_archetypes = set(pack.generator_seed_defaults.get("antagonist_archetypes_preferred", []))
    requested_archetypes = set(resolved.antagonist_archetypes_preferred or [])
    unknown_archetypes = sorted(requested_archetypes - pack_archetypes)
    if unknown_archetypes:
        raise SeedValidationError(
            "antagonist_archetypes_preferred contains unknown values: "
            f"{unknown_archetypes}. Pack options: {sorted(pack_archetypes)}"
        )

    if resolved.num_npcs is not None and not 6 <= resolved.num_npcs <= 30:
        warnings.append("num_npcs is outside the recommended 6-30 range")
    if resolved.num_locations is not None and not 5 <= resolved.num_locations <= 20:
        warnings.append("num_locations is outside the recommended 5-20 range")
    if resolved.num_factions is not None and not 2 <= resolved.num_factions <= 6:
        warnings.append("num_factions is outside the recommended 2-6 range")
    if resolved.num_truths is not None and not 4 <= resolved.num_truths <= 10:
        warnings.append("num_truths is outside the recommended 4-10 range")
    if resolved.num_complications is not None and not 6 <= resolved.num_complications <= 15:
        warnings.append("num_complications is outside the recommended 6-15 range")
    if resolved.num_sample_characters is not None and not 1 <= resolved.num_sample_characters <= 10:
        warnings.append("num_sample_characters is outside the recommended 1-10 range")

    return LoadedSeed(raw=raw, resolved=resolved, warnings=warnings)
