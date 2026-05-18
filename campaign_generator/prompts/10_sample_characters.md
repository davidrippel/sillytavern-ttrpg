You write only valid JSON matching the requested schema.

Task: generate pregenerated story-mode sample characters that fit the campaign and exist plausibly in its opening situation.

You will receive:

- `pack` — metadata for the active genre pack: `pack_name`, `display_name`, the `character_template` (the v2 story-mode shape), and `advantages_disadvantages` (the markdown vocabulary that lists axes and example phrases for advantages and disadvantages).
- `protagonist` — optional `archetype` (a phrase describing the kind of protagonist the seed asks for) and `known_facts` (background facts).
- `premise`, `plot`, `factions`, `npcs`, `locations` — campaign context. `npcs` here is the *known-to-PC* subset; sample-character hooks should reference these, not the full roster.
- `num_sample_characters` — exactly how many sample characters to produce.

For each character produce a story-mode profile in the v2 character template shape:

- `name` — a name appropriate to the genre's naming registers.
- `concept` — 1–2 sentences. Who they are, what drew them in, one complication.
- `advantages` — 2–4 short phrases drawn (loosely) from the pack's advantages vocabulary. Specific over generic.
- `disadvantages` — 1–2 short phrases that the world will use against them.
- `belongings` — 3–6 notable items beyond travel basics.
- `relationships` — 1–3 entries `{ "name": "...", "tie": "..." }`. At least one should reference a known NPC if any are supplied.
- `hook_into_campaign` — one short paragraph naming a known faction / NPC / location and the personal stake that brings this character into the campaign.

Hard constraints:

- There is no stats mode. Do NOT emit attribute scores, ability names, resource pools, dice expressions, or any numeric mechanical fields. The runtime has no concept of them.
- Each character is internally consistent: their advantages, disadvantages, belongings, and hook all support the same concept.
- Across the set, vary gender, age, social standing, and emotional centre. Two cynics with different clothes is not variety.
- At least half the sample characters reference a *known* NPC, faction, or location in their `hook_into_campaign` so the opening scene can land them in fiction immediately.

Naming diversity:

- Avoid the model's default English-Latinate name attractors (Marcus, Elias, Lyra, Cassia, etc.).
- Draw names from the genre's `naming.yaml` registers when the pack provides them.

Return JSON only.
