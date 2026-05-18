You are writing the `advantages_disadvantages.md` reference file for a TTRPG genre pack. This file is the vocabulary of strengths and weaknesses a story-mode character is built from. It is consumed by:

- The GM, as a constant lorebook entry (`__pack_reference`) — the GM uses this vocabulary to recognize and lean on what the player has put on their sheet.
- The extension's character-sheet UI, as autocomplete suggestions.
- The campaign generator, as raw material when sketching sample characters.

The system is story-mode only. There are no attribute scores. A character's mechanical identity is expressed entirely as 2-3 advantages and 1-2 disadvantages — concrete phrases the GM can picture and adjudicate against.

You will receive: tone/pillars, the overlay's setting_and_tone and npc_conventions sections, the brief's `advantages_disadvantages_hint`, and `example_characters`.

Produce JSON:

- `advantage_axes`: 3-5 axes (groups). Each axis has `title` (the axis name — e.g. "Bodily," "Mystical," "Crew-role," "Contact network") and `entries` (4-8 short phrases). Together across all advantage axes there must be **20-35 entries total**.
- `disadvantage_axes`: 3-5 axes, each with 4-8 entries. Together **15-25 entries total**.

Quality bar — every entry MUST:

- **Name a specific thing the GM can picture.** A place, a training, a mark, a debt, a person, a tool. "Knife-fighter from the river camps" lands; "good with a blade" does not.
- **Be invocable.** The player can point at it and say "this is in play right now."
- **Stay grounded in the genre.** No mechanical jargon (no "+1," no "feat," no "skill check"). No anachronism. No cross-genre items.
- **Be at least 3 words long.** Single adjectives are rejected.

Where appropriate, favor double-edged entries (an advantage that can also bite — "spoken for by a forest spirit," "ex-corp security from Helion"). The genre's NPC conventions and complications should make these double-edges payable in play.

Axis selection should fit the genre. Symbaroum naturally uses Bodily / Knowledge / Mystical / Social. A heist pack might use Crew-role / Contact-network / Mark / Heat. A hard-SF pack might use Shipboard / Planetside / Faction-credit / Wear. Don't force one genre's axes onto another.

Return JSON only.
