You write only valid JSON matching the requested schema.

Task: generate one location at a time for the campaign.

Requirements:
- strong sensory detail
- concrete notable features and hidden elements
- reference only supplied NPC names from `npc_name_menu` and supplied plot beat ids
- never invent or infer an NPC name that is not in the supplied roster
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name
- do not reuse any name in `avoid_names` (these are location names from recent campaigns — pick something different)

Naming diversity:
- `diversity_seed.district_flavor` hints the kind of neighborhood or precinct the campaign's locations cluster around — let it shape what types of places appear and what they're named after
- `diversity_seed.naming_style` describes one stylistic pattern to favor for this campaign's location names; vary within the pattern rather than repeating the same template
- avoid the model's default English-evocative location attractors ("The Velvet ___", "The Silk ___", "The Midnight ___", "The Jade ___", "The Archive of Whispers", "The Luminous ___", "The Chiaroscuro ___", "The ___ Grotto", etc.) unless they genuinely fit the genre and naming style
- prefer names rooted in the city's cultural register (from the NPC roster's diversity hint) over generic atmospheric English compounds

Length budgets (locations fire keyword-gated, often several at once — keep entries lean so the GM's context isn't flooded):
- `type`: <= 60 characters, a short label ("rooftop garden", "abandoned chapel")
- each sensory line (`sight`, `sound`, `smell`): <= 220 characters, one or two vivid concrete details, not a paragraph
- each `notable_features` item: <= 220 characters, one feature in one sentence
- each `hidden_elements` item: <= 220 characters, one secret/clue-bearing element in one sentence
- prefer 2-4 features and 2-4 hidden elements, not exhaustive lists

Concrete beats specific things, not all things. The GM expands from a tight prompt better than they trim a wall of prose.
