You write only valid JSON matching the requested schema.

Task: create the campaign's act outline and main dramatic spine. There are no beats in this system; acts are thematic chapters with a title and a goal, and the campaign's escalation is expressed as a `thematic_spine` of 3–5 short themes.

Requirements:

- 2–4 acts. Each act has a `title` and a `goal`. The `act_number` is assigned automatically by the validator — leave it null or omit it.
- A `main_antagonist` with `name`, `motivation`, `secret`, and `relationship_to_protagonist`.
- A `driving_mystery` (one sentence — the question the player will be pulling on).
- A `hook` (one sentence — the opening inciting moment, what gets the protagonist into the story).
- An `escalation_arc` (one short paragraph — how stakes rise without naming specific beats).
- A `thematic_spine`: 3–5 short escalation themes the GM should honor as time passes. NOT a beat sequence and NOT ordered — these are vibe vectors the GM keeps in mind. Example for a dark-fantasy investigation: "stakes climb from personal grief to civic exposure", "trust erodes between protagonist and former allies", "the old world reveals itself as larger than mortal scale". Specific, not generic.
- A `supporting_cast` of cast briefs (typically 6–12). Each entry has a `name`, an `archetype` (e.g. "young female confidant", "older guildmaster ally"), and a one-line `narrative_role`. Vary gender, age, social role, and faction alignment.
- Use `{{user}}` whenever you refer to the player character. Never invent a protagonist name.

Cast declaration (READ CAREFULLY — this is enforced by downstream validators):

- Every `supporting_cast` entry MUST appear by name in `escalation_arc`, `driving_mystery`, `hook`, an act title, or an act goal. No padding the cast list.
- Conversely, ANY personal name that appears in any of those prose fields MUST be one of: `{{user}}`, `main_antagonist.name`, or a `supporting_cast[i].name`. Don't drop new personal names into prose — add them to `supporting_cast` first.

Naming:

- Avoid the model's default English-Latinate attractors (Marcus, Elias, Lyra, Cassia, Anya, Vivian, Jasper, Caleb, Felix, Margot, Thorne, Vance, Reed, Petrova, Beaumont, Finch, Elara, Lyric, Ronan, Sera) unless the campaign's setting specifically calls for them — the NPC stage rejects these as overused defaults.
- Pick names that fit the premise's setting and cultural texture.

Do NOT include any of these v1 concepts: `acts[i].beats`, beat ids, ability references, attribute scores, resource pools, or roll mechanics. They are retired.

Return JSON only.
