You are designing the ability categories for a TTRPG genre pack.

You will receive: the brief's `ability_categories_hint`, the attributes, the resources, and the tone/pillars.

Produce JSON: a `categories` array with 3-6 categories. Each category:
- `key`: lowercase snake_case (e.g. `mystical_powers`, `general_abilities`)
- `display`: short label
- `description`: how abilities in this category work mechanically and narratively. NO hard line wraps.
- `activation`: one of `active`, `passive`, `passive_or_triggered`, `triggered`, `ritual`
- `has_levels`: bool — do abilities in this category progress through named levels?
- `level_names`: e.g. `[novice, adept, master]` if `has_levels` is true; empty list otherwise.
- `roll_attribute`: when `activation` is `active` or `ritual`, the attribute key to roll. MUST exactly match one of the attribute keys produced previously.
- `consequence_on_failure`: when applicable, a string referencing a resource (e.g. `"corruption_temporary: +1"`). The resource key MUST match a resource produced previously.
- `consequence_on_partial`: when applicable, similarly references a real resource.

Aim for this shape:
- 1-3 active categories (the main mechanical levers — the genre-defining ones)
- 1 passive/general category for skills without a mechanical signature
- Optionally 1 ritual category for slow, out-of-pressure setup-to-payoff abilities
- Optionally 1 trait category for permanent character features

If every category is `active` and uses the same `roll_attribute` and the same consequence, you have actually only made one category — diversify.

The genre-defining category (the "weird" one — magic, cyberware, psionics, alien tech) MUST have a genre-defining resource cost on failure or partial. That cost is what prevents the weird from being strictly better than the mundane.

Return JSON only.
