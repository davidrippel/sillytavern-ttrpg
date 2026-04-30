You are designing the resources (HP, genre-specific pools, threshold mechanics) for a TTRPG genre pack.

You will receive: the brief's `resource_flavor` hint, the attributes produced in the previous stage, and the tone/pillars.

Produce JSON: a `resources` array. It MUST include `hp_current` and `hp_max` (the universal HP pool). Beyond those, include 2-4 additional genre-specific resources that interact with the GM loop.

For each resource:
- `key`: lowercase snake_case
- `display`: short label
- `kind`: one of `pool`, `pool_with_threshold`, `counter`, `static_value`, `flag`, `tally`
- `description`: when this changes, what causes it, what hitting limits feels like. NO hard line wraps.
- `starting_value`: typical starting value (number, or a string like "true"/"false" for flags)
- For `pool` resources, set `max_value_field` to the matching max-resource key (e.g. `hp_current.max_value_field = "hp_max"`).
- For `pool_with_threshold` resources, set `threshold_field` to a sibling resource key holding the threshold; optionally include `threshold_consequence` describing what happens when the threshold is reached (e.g. `{field: "corruption_permanent", delta: "+1", then_reset: true}`).
- For long-arc `counter` resources, optionally include `threshold` (a number) and `threshold_effect` (string), and optional `endgame_value` + `endgame_effect`.

Pick resources that interact with play. Good types:
- Resources that tick up from ability use (corruption from magic, heat from loud action)
- Resources that tick up from failure (sanity loss, stress)
- Resources that tick down from time (oxygen, fuel)
- Resources representing relationships (faction reputation, crew morale)

Avoid:
- Resources that don't change in play (those are character descriptors, not mechanics)
- Overdesigning — a pack with HP and one signature genre resource is enough; HP plus four mental/physical/social pools is too much.

Bias toward the pattern: the genre's signature ability category should have a genre-defining resource cost (magic costs corruption; cyberware costs humanity; psionics costs focus). This is where the genre's thematic weight lives.

Return JSON only.
