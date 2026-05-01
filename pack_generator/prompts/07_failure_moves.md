You are writing the genre-specific failure moves for a TTRPG genre pack. The GM uses these on a failed roll (2-6) to make the situation worse without ending the scene.

You will receive: tone/pillars, resources, NPC conventions from the GM overlay, and the example characters.

Produce JSON:
- `moves`: 8-12 genre-flavored failure moves. Each move has `title` (a short evocative phrase, e.g. "The corruption wells up", "A witch-hunter's horn sounds") and `body` (one or two sentences naming the specific consequence, e.g. "Inflict 1 temporary corruption" or "An ally is exposed; introduce a complication for them within the next scene"). NO hard line wraps in `body`.
- `partial_success_trades`: 6-10 trades the GM can offer on a partial (7-9). Each trade is a single line in the form "Success, but ..." (e.g. "Success, but you leave a trail — someone can follow", "Success, but at a cost of corruption (1 temporary)"). These are short — single string entries, no titles.

Good moves are:
- Specific to the genre (not "something bad happens")
- Actionable (describe a concrete change)
- Tension-ratcheting rather than scene-ending

Bad moves to avoid (these will be rejected by validation):
- "The player loses." (Not a move, a dead end.)
- "Something happens" / "Something bad happens" / "Something mysterious happens." (Too vague.)
- "The GM decides" / "The GM chooses" / "You fail" / "The worst happens." (Not a move.)

Reference the pack's resources and NPC archetypes by name where it sharpens the move. At least one-third of the moves should call out a specific resource change using the `<resource_key>: ±N` notation (e.g. `heat: +1`, `ship_condition: -1`); the rest can be purely narrative consequences.

Return JSON only.
