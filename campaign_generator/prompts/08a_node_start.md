You write only valid JSON matching the requested schema.

Task: design the **opening node** of act 1 of a node-driven campaign, and pick the act's relevant NPCs and locations.

Background:
- Nodes are discrete situations the player can engage with. In a node-driven campaign, players move between nodes by following clues, not by being shepherded along a fixed sequence.
- The start node is where the player begins the campaign. It must establish tone, introduce immediate stakes, and feel like a definite **opening** — not a midpoint.

Your job for this prompt:

1. **Pick the NPCs and locations relevant to act 1.** From the supplied `npc_roster` and `location_catalog`, choose the subset that fits act 1's themes. These will anchor every node in act 1 (including this start node and three intermediate "points of interest").
   - Pick between 3 and 7 NPCs.
   - Pick between 2 and 5 locations.
   - Use NPC and location names EXACTLY as they appear in the rosters.

2. **Design the start node** — the opening scene of act 1.
   - `kind`: one of `location` / `npc_encounter` / `event` (which best characterizes the scene).
   - `description`: 1–3 sentences (20–400 chars) describing what's happening when the player arrives. Concrete and evocative. Reference at least one NPC or location by name.
   - `relevant_npcs`: the NPCs present at this specific node (subset of the act's NPC selection — typically 1 to 4).
   - `relevant_location`: the primary location this node takes place at (one of the act's selected locations).

Rules:
- Whenever referring to the player character, use the exact placeholder `{{user}}`. Never invent a protagonist name.
- All NPC and location names you emit must be from the supplied rosters; don't invent new ones.
- The start node must feel like an **entry point**, not a midpoint. The player has just arrived.
- The act's `beats_as_texture` field is *backstory texture* describing the dramatic arc of this act — it's not a sequence to follow. Use it to understand the tone and themes, not to mirror the order.
