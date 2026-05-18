"""Smoke tests for the v2 pack loader.

The v1 file checked attribute count and ability-catalog membership.
v2 packs have neither; we now check the v2 surface area instead.
"""
from __future__ import annotations

from common.pack import load_pack


def test_symbaroum_pack_loads():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    assert pack.metadata.pack_name == "symbaroum_dark_fantasy"
    assert pack.metadata.schema_version == 2
    assert pack.character_template.advantages == []
    assert "Davokar" in pack.gm_prompt_overlay or "forest" in pack.gm_prompt_overlay.lower()
    assert pack.complications, "complications.md should load"
    assert pack.advantages_disadvantages, "advantages_disadvantages.md should load"
    seed = pack.generator_seed_defaults
    assert seed["genre"] == pack.metadata.pack_name
    assert "num_truths" in seed
    assert "num_acts" not in seed  # retired
