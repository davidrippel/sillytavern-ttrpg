# Campaign Seed Format

The seed file is a small YAML document you write to shape a specific campaign within a genre. This file documents exactly what fields it supports, how they interact with the pack's defaults, and how much you should write.

Read this when: you're about to generate a new campaign and need to know what to put in your seed file. Come back when: the campaign didn't turn out how you wanted and you need to tune the seed for the next generation.

---

## Mental model

The pack answers "what kind of world is this?" (dark fantasy, cyberpunk, space opera). The seed answers "what kind of story in that world?" (a corrupt inquisitor's hunt, a heist gone wrong, a derelict colony mystery).

Your seed sits on top of the pack's `generator_seed.yaml`, which provides genre-level defaults. Your seed's fields override matching fields in the pack's defaults; fields you omit fall through to pack defaults.

---

## Quickest start

If you just want to generate something now and see what comes out:

```yaml
genre: symbaroum_dark_fantasy
campaign_pitch: >
  A missing mentor, a frontier town that's hiding something,
  and a forest that's been watching.
```

That's a legal seed. You'll get a playable campaign — generic, but playable. Every other field falls through to pack defaults.

---

## Getting a blank template

The campaign generator can produce a blank annotated seed file for you to fill in:

```bash
python -m campaign_generator --init-seed my_seed.yaml --genre genres/symbaroum_dark_fantasy/
```

This writes `my_seed.yaml` with every field present, commented out, with inline documentation — so you can uncomment and edit what you want and leave the rest. Much faster than writing from scratch.

---

## Full field reference

### Required fields

**`genre`** *(string)*
Which pack this seed is for. Must match the pack's `pack_name` from `pack.yaml`. The campaign generator validates this before running anything.

```yaml
genre: symbaroum_dark_fantasy
```

### High-leverage fields (write these first)

These four shape the campaign more than all other fields combined. If you're only writing a few fields, write these.

**`campaign_pitch`** *(string, paragraph-length)*
One paragraph describing the campaign you want. The generator uses this as the spine of the premise and plot skeleton. The single biggest lever in the whole seed.

```yaml
campaign_pitch: >
  A mentor's last letter summons the protagonist to a frontier town
  where the witch-hunters have turned predator. Something old in the
  forest has been woken.
```

Omitting this field is legal — the generator will invent a pitch from the pack's tone alone. But explicit pitches produce sharper campaigns than implicit ones.

**`themes_include`** *(list of strings)*
Themes you want woven through the campaign. Use specific, concrete themes ("a mentor's last secret") rather than abstract ones ("mystery"). Overrides the pack's default.

```yaml
themes_include:
  - a_mentor's_last_secret
  - trust_in_institutions_eroding
  - the_forest_as_witness
```

**`themes_exclude`** *(list of strings)*
Themes to avoid for this specific campaign. Merges with the pack's default exclusions — pack-level exclusions always apply; your seed can only add to them, not remove.

```yaml
themes_exclude:
  - sexual_violence
  - torture_as_spectacle
```

**`protagonist_archetype`** *(string, 1-3 sentences)*
Rough shape of the character you intend to play. Not a character sheet — the generator uses this to craft a hook and opening scene that fits this kind of character.

```yaml
protagonist_archetype: >
  Changeling witch, elf-touched, trained in shadow magic.
  Outlawed in most of Ambria. Has a raven familiar.
```

### Structural fields (affect campaign shape)

**`num_acts`** *(integer, default 4)*
How many acts the campaign has. 3 = tight, 4 = standard, 5 = sprawling. Range 3–6.

**`num_npcs`** *(integer, default 10)*
How many named NPCs to generate. Range 6–15 reasonable.

**`num_locations`** *(integer, default 8)*
How many locations to generate. Range 5–12 reasonable.

**`clue_chain_density`** *(string: `light`, `medium`, or `heavy`, default `medium`)*
How many clues and how branching the investigation graph is. Light = linear, easy to follow; heavy = dense, many red herrings and branches.

**`branch_points`** *(integer, default 7)*
How many explicit "if player does X, then Y" contingencies the generator creates. Range 4–10.

### Setting fields (ground the campaign in specific places and powers)

**`setting_anchors`** *(list of strings)*
Specific, evocative nouns that locate the campaign. Not themes — these are *places and things*. Overrides the pack's defaults.

```yaml
setting_anchors:
  - thistle_hold
  - davokar_outskirts
  - abandoned_ordo_magica_lodge
  - a_ruin_that_shouldnt_exist
```

**`antagonist_archetypes_preferred`** *(list of strings)*
Preferred archetypes for the main antagonist. The generator picks one as the primary antagonist and may use others as secondary threats. Values must be archetypes the pack knows about — see the pack's `generator_seed.yaml` for the menu.

```yaml
antagonist_archetypes_preferred:
  - corrupt_inquisitor
  - ancient_sorcerer
```

### Protagonist context fields (shape the opening)

**`protagonist_known_facts`** *(list of strings)*
Facts the protagonist already knows at campaign start. These become lorebook entries accessible from turn one — the GM treats them as established canon the protagonist can reference.

```yaml
protagonist_known_facts:
  - Their mentor is named Iselde and taught them for eleven years.
  - Their mentor was researching something she wouldn't name.
  - The Church of Prios has opinions about people like them.
```

Use this to anchor backstory without having to explain it during play.

**`opening_hook_seed`** *(string, paragraph-length)*
Explicit opening hook. Rare — use only when you have a specific first scene in mind. If omitted, the generator invents the hook from premise + tone + protagonist.

```yaml
opening_hook_seed: >
  The protagonist receives a raven-delivered letter from their
  mentor, summoning them to Thistle Hold with urgency. When they
  arrive, the mentor is missing.
```

**Warning:** the more you specify here, the less surprised you'll be. Consider leaving this blank unless you really want control.

### Tone fields

**`tone_modifiers`** *(list of strings)*
Adjustments layered on top of the pack's tone. Each modifier is a dial rotating the pack tone slightly. Free-form — the generator interprets them.

```yaml
tone_modifiers:
  - slightly_more_hopeful_than_default
  - investigative_rather_than_action_heavy
  - quieter_in_the_opening_acts
```

### Generation control fields

**`random_seed`** *(integer, optional)*
Seed for reproducibility. Same random_seed + same model + same prompts + same pack = same campaign. Useful for regenerating after editing the seed.

**`model`** *(string, optional)*
OpenRouter model slug. Overrides the `--model` CLI flag. Default: the pack's preferred model, or the CLI flag's value.

**`temperature`** *(float, optional, default 0.8)*
LLM temperature for generation. 0.5 = more predictable, 1.0 = more varied. Values above 1.0 get unstable; stay in 0.5–1.0.

### Strictness fields

**`strictness`** *(object)*
How rigorously the generator validates and repairs its outputs. Merges with pack defaults field-by-field.

```yaml
strictness:
  clue_graph_connectivity: strict    # strict | lenient
  npc_voice_diversity: strict        # reject if NPCs sound alike
  canon_consistency: strict          # cross-reference validation
```

Leave this alone for your first few campaigns. Tighten specific fields if you see quality issues in those areas.

---

## How seed fields interact with the pack

- Fields in the pack's `generator_seed.yaml` are defaults.
- Your seed's fields override those defaults — EXCEPT:
  - **`themes_exclude` merges** (both apply; pack exclusions are never weakened)
  - **`strictness` merges field-by-field** (your seed's settings override only the fields you specify)
- Any field you omit falls through to the pack default.
- Any field present in your seed but not in the pack default is still used — your seed can add fields the pack didn't mention.

---

## How much should I write?

A real question with a real answer: write as much as you want to control, and no more. The unwritten parts are where the generator surprises you.

### Minimum-specificity seed (generator does most of the work)

```yaml
genre: symbaroum_dark_fantasy
campaign_pitch: >
  A missing mentor, a frontier town that's hiding something,
  and a forest that's been watching.
```

Legal. Playable. Generic.

### Balanced seed (recommended starting point)

```yaml
genre: symbaroum_dark_fantasy

campaign_pitch: >
  A mentor's last letter summons the protagonist to a frontier town
  where the witch-hunters have turned predator. Something old in the
  forest has been woken.

themes_include:
  - a_mentor's_last_secret
  - trust_in_institutions_eroding

protagonist_archetype: >
  Someone connected to the old magical traditions — a witch or
  changeling. Not a warrior; they solve problems by knowing things.

antagonist_archetypes_preferred:
  - corrupt_inquisitor
  - ancient_sorcerer
```

Specific enough to produce a campaign with clear shape. Vague enough that the details will surprise you.

### Maximum-specificity seed (tight control, low surprise)

```yaml
genre: symbaroum_dark_fantasy

campaign_pitch: >
  A changeling witch returns to the town where their mentor died
  to investigate rumors of corruption in the Ordo Magica. What
  they find implicates both the Church and their own mentor.

protagonist_archetype: >
  Changeling witch, elf-touched, trained in shadow magic.
  Outlawed in most of Ambria. Has a raven familiar.

protagonist_known_facts:
  - The mentor's name was Varanise.
  - Varanise was researching pre-Symbaroum ruins in northern Davokar.
  - The protagonist has 1 permanent corruption from their training.

setting_anchors:
  - thistle_hold
  - the_ordo_magica_chapterhouse
  - a_ruin_north_of_thistle_hold

themes_include:
  - betrayal_by_an_institution_you_trusted
  - the_cost_of_truth
  - being_the_monster_they_fear_you_are

themes_exclude:
  - romance

antagonist_archetypes_preferred:
  - corrupt_inquisitor
  - ancient_sorcerer

num_acts: 4
clue_chain_density: medium

opening_hook_seed: >
  The protagonist arrives in Thistle Hold in a cold autumn rain.
  The raven carries a letter they cannot yet read.
```

You know most of what's coming. The generator fills in NPCs, secondary clues, and the resolution, but the shape is set.

---

## Validation

The campaign generator validates your seed before running the pipeline. Invalid seeds fail fast with clear messages:

- **Missing `genre`**: error — field is required
- **`genre` doesn't match the pack's `pack_name`**: error — pack mismatch, showing both the expected and provided values
- **`antagonist_archetypes_preferred` contains archetypes not in the pack's menu**: error, listing the pack's available archetypes
- **`num_acts` outside 3–6**: warning — will still run, but may produce unbalanced pacing
- **`themes_include` and `themes_exclude` contain the same theme**: error — contradictory
- **Unknown fields**: warning — the field is ignored, but typos in field names won't silently do nothing

Fail-fast validation is intentional: the campaign generator can take 15–30 minutes to run end-to-end, and you don't want to discover a typo in your seed after twenty minutes of LLM calls.

---

## Common mistakes

**Over-specifying the opening hook.** You wrote out the whole first scene, character-by-character, beat-by-beat. The generator produces what you described and the opening doesn't surprise you. Fix: leave `opening_hook_seed` blank unless you really need that control.

**Contradicting the pack.** Your seed's tone modifiers pull toward lighthearted romance, but the pack is grim dark fantasy. The generator tries to honor both and produces mush. Fix: pick a pack that matches the tone you want, or change the pack's tone modifiers directly for this run.

**Themes as abstractions rather than hooks.** `themes_include: [mystery, adventure, growth]` is too abstract to steer anything. `themes_include: [a_mentor's_last_secret, trust_in_institutions_eroding]` gives the generator something specific to weave. Fix: make themes concrete.

**Too many antagonist archetypes preferred.** You listed six. The generator picks arbitrarily, and you don't know which you'll get. Fix: list 1–3; if you want variety, run multiple campaigns with different preferences.

**Stale `random_seed`.** You ran once, didn't like the output, edited the seed, ran again with the same `random_seed`. Same LLM inputs + same seed ≈ same output. Fix: change the random_seed OR remove it entirely when iterating.

---

## Working with the blank template

After running `--init-seed`, you'll have a file like:

```yaml
# Required: which pack this seed is for.
# Must match the pack.yaml pack_name of your --genre pack.
genre: symbaroum_dark_fantasy

# Optional but high-leverage: one paragraph describing the campaign.
# campaign_pitch: >
#   (your pitch here)

# Optional: specific themes to weave through the campaign.
# Concrete phrases work better than abstractions.
# themes_include:
#   - a_mentor's_last_secret
#   - trust_in_institutions_eroding

# Optional: themes to avoid. Merges with pack-level exclusions.
# themes_exclude:
#   - romance

# ... (all other fields, each commented, with docs)
```

Uncomment and edit what you want to control. Leave the rest commented — it will fall through to pack defaults.

The blank template is regenerated per-pack, so the available `antagonist_archetypes_preferred` values (for example) are listed in a comment, pulled from that pack's `generator_seed.yaml`. This means the template is always accurate to the pack you're targeting.
