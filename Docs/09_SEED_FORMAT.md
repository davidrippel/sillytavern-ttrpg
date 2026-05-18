# Campaign Seed Format

What you write to generate a campaign with the campaign generator.

The seed is a small YAML file (typically 10–40 lines). It anchors the generator on a specific campaign's themes, tone, and structural shape. Everything else — premise, plot, NPCs, locations, truths, complications — comes from the generator.

This is the **v2 seed format** (story-mode runtime). v1 fields (`num_acts`, `clue_chain_density`, `branch_points`, `nodes_per_act`) are retired; the loader ignores them with a warning.

---

## Worked example

```yaml
# Required: must match the pack's pack_name.
genre: symbaroum_dark_fantasy

# Optional but high-leverage: one paragraph describing the campaign.
campaign_pitch: >
  A disgraced scholar is called to Thistle Hold after their former mentor
  vanishes while investigating a noble family's private excavations in
  Davokar. The deeper truth points toward both church scrutiny and
  something old that has begun answering back.

themes_include:
  - the_cost_of_inheritance
  - knowledge_that_makes_you_complicit
  - pity_for_the_monstrous

themes_exclude:
  - torture_as_spectacle

protagonist_archetype: >
  A lore-seeker or hedge mystic who solves problems by noticing patterns,
  reading old signs, and knowing which truths to leave unsaid.

protagonist_known_facts:
  - "My mentor disappeared eight days ago, somewhere along the Davokar fringe."
  - "I owe the Iron Pact a debt I never wanted to take."

antagonist_archetypes_preferred:
  - tainted_noble
  - corrupt_inquisitor

opening_hook_seed: >
  A raven brought a folded letter sealed with my mentor's old sigil.
  Three words: "Come. Now. —I."

tone_modifiers:
  - a_touch_more_tragic_than_default
  - patient_horror_in_the_first_half

image_style_hint: >
  Full-body photorealistic character portrait, realistic skin texture,
  cinematic lighting, no illustration or painting look.

# Optional structural counts.
num_npcs: 18
num_locations: 12
num_factions: 4
num_truths: 7
num_complications: 12
num_sample_characters: 5

# Optional generation controls.
random_seed: 44119
model: anthropic/claude-sonnet-4.5
temperature: 0.7

# Optional strictness overrides. Merge field-by-field with pack defaults.
strictness:
  truth_adjacency: strict
  npc_voice_diversity: strict
  canon_consistency: strict
```

---

## Field reference

### Required

- `genre` — the pack's `pack_name` (snake_case). Must match exactly. The generator refuses to run against a mismatched pack.

### High-leverage prose (recommended)

- `campaign_pitch` — one paragraph naming the central tension, the protagonist's stake, and the world detail that makes this campaign specific. The single most influential field.
- `protagonist_archetype` — a short phrase describing the kind of protagonist the seed asks for. Feeds the opening hook's character-creation guidance and the sample-characters stage.
- `protagonist_known_facts` — list of short sentences describing what the protagonist already knows at game start. Reaches the "What you already know" section of the opening hook.

### Theme controls

- `themes_include` — themes to weave in (snake_case). 2–6 entries typical.
- `themes_exclude` — themes to avoid (snake_case). 1–4 entries. Merges with the pack's defaults; the generator validates that no entry appears in both `themes_include` and `themes_exclude`.
- `tone` / `tone_modifiers` — short keywords adjusting tone on top of the pack defaults.

### Setting & antagonists

- `setting_anchors` — specific places, locales, or institutions the campaign hangs on. snake_case.
- `antagonist_archetypes_preferred` — must be a subset of the pack's `antagonist_archetypes_preferred` (defined in the pack's `generator_seed.yaml`). The seed loader rejects unknown values with a list of valid options.

### Opening hook

- `opening_hook_seed` — one short paragraph the opening-hook stage uses as raw material for the opening scene. Optional; the generator invents one if omitted.

### Image style

- `image_style_hint` — full prompt-style guidance the NPC stage embeds into every `image_generation_prompt`. Use this to enforce a consistent visual look across the campaign's portraits (photorealistic vs. painterly, full-body vs. portrait, etc.).

### Structural counts (v2)

| Field | Range | Default | Effect |
|---|---|---|---|
| `num_npcs` | 6–30 | from pack | NPC roster size. |
| `num_locations` | 5–20 | from pack | Location catalog size. |
| `num_factions` | 2–6 | from pack | Faction count. |
| `num_truths` | 4–10 | from pack | Atomic truth count. Fewer = tighter mystery; more = sprawling campaign. |
| `num_complications` | 6–15 | from pack | Campaign-specific complications (on top of the pack's universal list). |
| `num_sample_characters` | 1–10 | 5 | Pregenerated story-mode sample characters. |

**Retired v1 fields** (the loader ignores them with a warning):

- `num_acts` — acts are now thematic chapters, not beat sequences; the act count is generator-decided (typically 2–4).
- `nodes_per_act` — there are no nodes.
- `clue_chain_density` — there are no clue chains.
- `branch_points` — `branches` are still emitted, but their count is generator-decided.

### Generation controls

- `random_seed` — reproducibility hint. Picks the naming-diversity seed and may inform LLM sampling on supported models.
- `model` — OpenRouter model slug. Overrides the env default for this run.
- `temperature` — sampling temperature. Defaults to the env value.

### Strictness

- `strictness` — a map of strictness levers. Recognised keys (others pass through):
  - `truth_adjacency` — `strict` rejects truths whose `adjacency_keys` don't match any NPC, location, or faction in the campaign.
  - `npc_voice_diversity` — `strict` rejects rosters whose NPCs share a speaking style.
  - `canon_consistency` — `strict` rejects branches referencing tokens not in the canon menu.

Defaults come from the pack's `generator_seed.yaml`. The seed merges field-by-field — set only the keys you want to override.

---

## Pack-default fallbacks

Any field omitted from the seed falls back to the pack's `generator_seed.yaml`. Fields the pack didn't supply fall back to the generator's hard-coded defaults. The seed loader prints a warning for any unknown top-level field.

To generate a fully-annotated empty seed for a specific pack:

```bash
python -m campaign_generator --init-seed my_seed.yaml --genre <pack_name>
```

The output is a YAML file with every field documented and pre-filled with the pack's antagonist menu and other pack-specific suggestions.

---

## Migrating a v1 seed

A v1 seed with `num_acts`, `clue_chain_density`, `branch_points`, or `nodes_per_act` will load with warnings; those fields are silently stripped during merge. Replace them as follows:

- `num_acts` → drop entirely; acts emerge from the premise.
- `nodes_per_act` → drop entirely.
- `clue_chain_density: heavy` → translate to a higher `num_truths` if you want a more layered mystery.
- `branch_points: 8` → drop entirely; branches are generator-decided.

Add the v2 fields you actually want to control (`num_truths`, `num_complications`, `num_factions`).
