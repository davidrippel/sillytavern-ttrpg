You are writing the GM prompt overlay for a TTRPG genre pack. This file is injected into the game-master LLM's context every turn, so it shapes the texture and voice of play.

You will receive: tone/pillars, attributes, resources, ability categories, and the brief.

Produce JSON with these fields. Each field is a markdown chunk (one or more paragraphs). NO hard line wraps — write each paragraph as a single long line, separated only by blank lines. Total document should be under 1500 words.

- `setting_and_tone`: 2-3 paragraphs. Sensory texture of the world, mood, the kind of stories told here. Specific, not "dark and mysterious" — name the smells, sounds, weights.
- `thematic_pillars`: a markdown bulleted list, one bullet per pillar. Each bullet: `**Title.** Description.` Reuse the pillars from earlier.
- `attribute_guidance`: one paragraph explaining when the GM should call for each attribute. EVERY one of the six attribute keys must be mentioned by its `display` name with a clear in-genre cue. Close with a line on what to do when uncertain.
- `resource_mechanics`: one or two paragraphs per non-static resource explaining when it ticks up/down, what hitting thresholds feels like in narration, and how to describe state (sensory, not numeric). EVERY resource key from resources.yaml must be referenced.
- `ability_adjudication`: one paragraph per category explaining how to narrate activations, what success/partial/failure look like, and how the category's costs (corruption, heat, etc.) get applied. EVERY category key must be covered.
- `npc_conventions`: 3-5 recognizable archetypes for the genre, each with one paragraph (e.g. "Inquisitors of Prios. Believers, often sincere, often dangerous..."). Give the GM a vocabulary for improvising NPCs.
- `content_to_include`: a bulleted list of textures the GM should lean into.
- `content_to_avoid`: a bulleted list of themes the GM should not generate. Merge user-supplied content_to_avoid with universal safety items (sexual content, child endangerment).
- `character_creation`: a paragraph or short bulleted list covering: point-buy distribution for attributes (e.g. "+4 spread with at least one -1, no value above +3"), starting abilities count (typically 3), starting equipment guidance, and starting resource values (HP at max, signature resources at 0).

Avoid:
- Restating engine-level rules (scene structure, STATUS_UPDATE format, dice mechanics) — the base GM prompt already covers those.
- Mere vibes ("make it dark") — the LLM will over-correct.
- Internal contradictions (e.g. "prioritize mood" alongside "always be clear about options").

Constraint generates style: prefer "always do X" / "never do Y" instructions over generic descriptors.

Return JSON only.
