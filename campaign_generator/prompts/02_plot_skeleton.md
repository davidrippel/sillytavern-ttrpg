You write only valid JSON matching the requested schema.

Task: create the campaign's act structure and main dramatic spine.

Requirements:
- exactly the requested number of acts
- each act has a title, goal, and 3-5 beats
- each beat should be a structured object with a stable id like `act1_beat1` and a `text` field
- define the main antagonist, driving mystery, hook, and escalation arc
- keep names and references internally consistent
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name

Cast declaration (READ CAREFULLY — this is enforced by downstream validators):
- `supporting_cast` MUST contain exactly `target_supporting_cast_size` entries. Each entry has a `name`, an `archetype` (e.g. "young female confidant", "older guildmaster ally", "rival journalist", "guilt-ridden parent"), and a one-line `narrative_role` describing what they do in the story.
- Treat `supporting_cast` as a casting call: each entry will become a fully-realized NPC in the next stage, so request the *kinds* of characters the story actually needs (vary gender, age, social role, and faction alignment so the plot has somewhere for each NPC to live).
- Every `supporting_cast` entry MUST appear by name in at least one beat, in `escalation_arc`, in `driving_mystery`, or in `hook`. Do not pad the cast list with names you don't use.
- Conversely, ANY personal name that appears in `hook`, `driving_mystery`, `escalation_arc`, act titles, act goals, or beat text MUST be one of: `{{user}}`, the `main_antagonist.name`, or a `supporting_cast[i].name`. Do not drop new personal names into prose — if you need an additional figure, add them to `supporting_cast` first.
- Do not invent characters by referring to them only by role ("the witness", "the courier") and then giving them a name later. If a character is named anywhere, they belong in `supporting_cast` (or are the antagonist).

Naming:
- avoid the model's default English-Latinate name attractors (Marcus, Elias, Lyra, Cassia, Anya, Vivian, Jasper, Caleb, Felix, Margot, Thorne, Vance, Reed, Petrova, Beaumont, Finch, Elara, Lyric, Ronan, Sera) unless the campaign's setting specifically calls for them — these are overused defaults the NPC stage will reject.
- pick names that fit the premise's setting and cultural texture rather than reaching for generic fantasy or English-Latinate defaults.
