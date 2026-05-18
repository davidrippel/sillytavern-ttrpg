You are writing the `complications.md` file for a TTRPG genre pack. This file is embedded into the GM's context every turn (as the constant lorebook entry `__pack_complications`) and gives the GM a vocabulary of concrete narrative complications to pick from when an action goes badly or when the pacing system signals "lean in."

The runtime has no dice and no roll bands. Complications are picked by GM judgement of the fiction, not by 2-6 / 7-9 thresholds. Do NOT structure entries by roll band.

You will receive: tone/pillars, the overlay's setting_and_tone and translating_pressures sections, the brief's `complications_hint` and `pressure_flavor`.

Produce JSON:

- `complications`: 10-15 entries, each with `title` (short bold phrase, e.g. "The shadows in the forest remember.") and `body` (one or two sentences describing the concrete narrative consequence). These are GENRE-SPECIFIC — they should not be drop-in for any other genre. Layer them with the genre's accumulating pressure when natural (a corruption sign appearing alongside the complication, a heat-meter implied without a number).

- `success_costs`: 6-12 entries, each a short string completing "Success, but ..." — these are what a clean win looks like in this genre, which should be rare. Examples: "Success, but it takes much longer than hoped." "Success, but you leave a trail." "Success, but at a cost of a corruption sign." Each entry must be a complete clause, at least 4 words.

Quality bar:

- Each complication is **specific** (concrete imagery — a witch-hunter's horn, a fixer who stops returning calls, an inquisitor at the inn — not "something bad happens").
- Each complication is **actionable** (describes a concrete change to the situation, not "the GM decides").
- Each complication **ratchets tension**, never ends the scene. ("You die" is not a complication.)
- Drop in the genre's pressure language naturally — if the genre's pressure is corruption, several complications should let a corruption sign appear; if it's heat, several should turn the screws on visibility/pursuit.

Forbidden phrases (the validator rejects any of these): "something happens," "something bad happens," "something mysterious happens," "the gm decides," "you fail," "you lose."

Return JSON only.
