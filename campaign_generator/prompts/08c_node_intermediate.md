You write only valid JSON matching the requested schema.

Task: design an **intermediate node** — a "point of interest" the player MAY engage with on the way from this act's start to its final node.

Critical: intermediate nodes are **unordered and optional**. The player can visit them in any order, or skip them entirely and beeline to the final node. So:

- This node must NOT depend on any other intermediate node having been visited.
- It must NOT advance a fixed plot sequence — it stands on its own.
- It should feel like a discrete, self-contained scene/encounter/location that fits this act's tone.
- It's an *opportunity* (texture, character moment, side investigation, optional encounter) — not a mandatory plot stop.

Context provided:
- `act_start_node`: the act's opening scene.
- `act_final_node`: the act's culmination (target).
- `act_npcs` and `act_locations`: the NPCs and locations relevant to this act. Pick from these.
- `previous_intermediates`: descriptions of intermediate nodes already designed for this act. Do not duplicate their concepts — make this one *distinct*.
- `intermediate_index`: which intermediate this is (1, 2, or 3).

Your job:
- `kind`: `location` / `npc_encounter` / `event`.
- `description`: 1–3 sentences (20–400 chars). A standalone scene the player can choose to engage with. Concrete and evocative. Distinct from `previous_intermediates`.
- `relevant_npcs`: NPCs involved (subset of `act_npcs`; typically 1–3).
- `relevant_location`: primary location (one of `act_locations`).

Rules:
- Use NPC and location names EXACTLY as supplied in `act_npcs` and `act_locations`.
- Whenever referring to the player character, use the exact placeholder `{{user}}`. Never invent a name.
- Do not assume the player has visited any other intermediate node, or that they will.
- Each intermediate node is **parallel** to the others — they're alternative engagements, not steps in a sequence.
