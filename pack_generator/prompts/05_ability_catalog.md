You are filling out the ability catalog for a TTRPG genre pack.

You will receive: the categories, the attributes, the resources, the example characters from the brief, and the tone/pillars.

Produce JSON: a `catalog` array with 15-25 abilities. Each ability:
- `name`: title-cased ability name (e.g. `Witchsight`, `Cyberdeck Jack-In`). Names must be unique.
- `category`: must exactly match one of the category keys.
- `prerequisite`: a string. Use `"none"` for no prerequisite, or `"<attribute_key> >= <number>"` (e.g. `"shadow >= 2"`), or `"<ability_name>"` for an ability prerequisite, or a comma-separated mix.
- `description`: 1-2 sentences explaining what the ability is in-fiction. NO hard line wraps.
- `effect`: 1-3 sentences explaining the mechanical effect. Reference real attribute keys, real resource keys, and real category-level mechanics. Distinguish full / partial / failure outcomes when the activation is active or ritual. NO hard line wraps.

Distribute across categories:
- At least 2 abilities per category.
- No more than 8 abilities in any one category.
- The genre-defining category should have enough catalog entries to feel substantive (typically 4-6).

Aim for catalog *diversity* over size. 15 abilities spanning 4 categories with 4 power ranges beats 30 abilities all in one category.

Use prerequisite chains sparingly — most abilities should be independent, so character builds aren't straitjacketed.

Each catalog entry should be something a starting character or a campaign-generated antagonist might plausibly take. Don't include abilities with no in-play role.

Return JSON only.
