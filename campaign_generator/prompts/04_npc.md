You write only valid JSON matching the requested schema.

Task: generate one named NPC at a time for the campaign roster.

Requirements:
- do not duplicate names in the supplied roster
- cite only abilities that exist in the supplied ability catalog
- give the NPC a distinct voice, motivation, secret, and relationships
- vary demographics, role, and agenda from existing NPCs
- if `must_use_one_of_names` is non-empty, the NPC name must be one of those names exactly
- ensure every name in `required_npc_names` appears somewhere in the final roster
- in relationships, use only `{{user}}` or names that belong to the campaign's NPC roster
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name

Length budgets (these entries live in the GM's context every time the NPC is mentioned — write tight, evocative lines, not paragraphs):
- `role`: <= 80 characters, a short noun phrase that fits the campaign's genre (e.g. "the keeper of secrets", "the rival who never left town")
- `physical_description`: <= 220 characters, 1-2 sentences with one or two distinctive details, not a portrait
- `speaking_style`: <= 160 characters, voice and cadence in one sentence (a verbal tic or two is enough)
- `motivation`: <= 220 characters, what they want and why — one sentence
- `secret`: <= 320 characters, the hidden truth in 1-2 sentences
- each `relationships[].description`: <= 160 characters, the relationship in one sentence

Prefer specificity over completeness. The GM will riff; you don't need to spell out every nuance.
