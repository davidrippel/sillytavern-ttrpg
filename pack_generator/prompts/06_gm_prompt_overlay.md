You are writing the GM prompt overlay for a TTRPG genre pack. This file is embedded into the game-master LLM's context every turn (as the constant lorebook entry `__pack_gm_overlay`), so it shapes the texture and voice of play.

The system is **story-mode only**: no dice, no attribute scores, no resource pools, no STATUS_UPDATE blocks. The GM resolves actions narratively, leaning on the character's advantages and disadvantages and the genre's accumulating pressures. Never reference dice, attribute scores, "+1 to a roll," or numeric resource changes anywhere in your output.

You will receive: tone/pillars, the brief's `pressure_flavor` (the genre's signature accumulating pressure), the brief's `advantages_disadvantages_hint`, and the brief's `complications_hint`.

Produce JSON with these fields. Each field is a markdown chunk (one or more paragraphs). NO hard line wraps — write each paragraph as a single long line, separated only by blank lines. Total document under 1500 words; hard fail at 1800.

- `setting_and_tone`: 2-3 paragraphs. Sensory texture of the world, mood, the kind of stories told here. Specific — name the smells, sounds, weights. Not "dark and mysterious."
- `thematic_pillars`: a markdown bulleted list, one bullet per pillar. Each bullet: `**Title.** Description.` Reuse the pillars from earlier.
- `resolving_actions`: 2-3 paragraphs explaining how the GM adjudicates without dice in this genre. Must cover:
  - What success-with-cost looks like when an advantage is in play and the situation is favorable (clean wins are rare and earned).
  - What failure or partial-success-with-a-complication looks like when a disadvantage is in play or the situation is hostile.
  - The default for neutral cases ("which outcome makes the next scene more interesting").
  - Point the GM at the genre's vocabulary in `__pack_reference` (the advantages_disadvantages reference embedded in the same lorebook).
- `translating_pressures`: 2-3 paragraphs naming the genre's signature accumulating pressure (corruption / heat / sanity / ship damage / exposure — whichever the brief's `pressure_flavor` describes) and rendering it as **prose signs**, not counters. List at least 4 concrete sensory or social signs the GM can drop into narration (smells, sweat, animal reactions, NPC body language, a reflection wrong, a debt remembered, a passing patrol's interest). Explain when accumulated signs should escalate into a permanent change (a scar, a mark, a debt, a reputation shift). End by stating that the system's fact extractor picks up these signs from prose — the GM never tracks numbers.
- `npc_conventions`: 3-6 recognizable archetypes for the genre, each one paragraph. For each archetype: how they speak (one-line speech note), what they want, default disposition toward the protagonist. Give the GM a vocabulary for improvising NPCs between named lorebook entries.
- `content_to_include`: a bulleted list of textures the GM should lean into.
- `content_to_avoid`: a bulleted list of themes the GM should not generate. Merge user-supplied content_to_avoid (in the brief) with universal safety items (sexual content involving minors, romance unless the genre invites it, gratuitous torture-as-entertainment).
- `character_creation`: a paragraph or short bulleted list covering how a character in this genre is built using the v2 character template (`name`, `concept`, `advantages`, `disadvantages`, `belongings`, `relationships`). State how many advantages (typically 2-3) and disadvantages (typically 1-2), what kinds of belongings fit, how many relationships to seed. Note any genre-specific starting marks (already-marked? already-hunted? already-bonded?). DO NOT mention attribute spreads, ability counts, or starting resource values — those concepts are retired.

Avoid:
- Restating engine-level rules (scene structure, NPC format, OOC handling, length cap, "never invent campaign truths") — the base GM prompt already covers those.
- ANY reference to dice, attribute scores, resource pools, ability slots, STATUS_UPDATE, or numeric mechanical changes. The schema validator rejects overlays that contain "2d6", "+1 to ", "attribute roll", "make a roll", or "status_update" anywhere in resolving_actions / translating_pressures / character_creation.
- Vague vibes ("make it dark") — the LLM will over-correct.
- Internal contradictions (e.g. "prioritize mood" alongside "always be clear about options").
- Padding. Total under 1500 words.

Constraint generates style: prefer "always do X" / "never do Y" instructions over generic descriptors. `content_to_avoid` and `content_to_include` should be lists of imperatives, not adjectives.

Return JSON only.
