You are writing the default campaign seed for a TTRPG genre pack. This file is loaded by the campaign generator when the user runs it without supplying their own seed.

You will receive: tone/pillars, attributes, resources, ability categories, the GM overlay, and the brief.

Produce JSON with these fields:
- `setting_anchors`: 4-6 specific named places, locales, or institutions the campaign generator should anchor on. SPECIFIC — "derelict_colonies, alien_ruins, contested_trade_routes" beats "the frontier". Use snake_case identifiers.
- `themes_include`: 4-6 thematic threads the generator should weave in (e.g. `betrayal`, `the_cost_of_knowledge`, `small_lights_in_dark_places`). snake_case.
- `themes_exclude`: 2-4 themes the generator should not touch (e.g. `romance`, `child_endangerment`, `modern_anachronism`). snake_case.
- `tone`: 3-5 tone keywords for the campaign (e.g. `grim`, `mysterious`, `morally_ambiguous`, `patient`). snake_case.
- `antagonist_archetypes_preferred`: 3-6 antagonist types the generator should draw from (e.g. `corrupt_inquisitor`, `ancient_sorcerer`, `cult_leader`, `forest_spirit`). snake_case.
- `num_acts`: integer, typically 3 or 4
- `num_npcs`: integer, typically 8-12
- `num_locations`: integer, typically 6-10
- `clue_chain_density`: one of `low`, `medium`, `high`. Default `medium` unless the genre cries out for an investigation focus.
- `branch_points`: integer, typically 5-8

Be specific everywhere. The campaign generator will instantiate against these defaults — vague anchors produce a vague campaign.

Return JSON only.
