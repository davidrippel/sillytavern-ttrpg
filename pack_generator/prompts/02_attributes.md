You are designing the six character attributes for a TTRPG genre pack.

You will receive: the brief's `attribute_flavor` hint, the one-line pitch, tone keywords, and the setting/pillars from the previous stage.

Produce JSON: an `attributes` array with EXACTLY 6 entries. Each entry:
- `key`: lowercase snake_case identifier (e.g. `might`, `edge`, `tech`)
- `display`: short proper-cased label (e.g. `Might`, `Edge`, `Tech`)
- `description`: one or two sentences. Describe the attribute as a capability domain, not a skill. NO hard line wraps.
- `examples`: 2-4 concrete in-genre examples of when the GM would call this attribute (e.g. for Tech in a cyberpunk pack: "rerouting power around a damaged junction"). Specific, not generic.

Hard requirements (the validator will check):
- Exactly 6 attributes; unique keys; unique display names; descriptions distinct from one another (no two attributes covering the same ground).
- Most genres have a physical, a mental, a social, and a "skill/training" pool. The sixth attribute is where the genre lives — the thing that makes this genre different (e.g. Symbaroum's Shadow, cyberpunk's Edge).

Avoid these failure modes:
- Overlap: "Strength" and "Might" are the same attribute; "Charisma" and "Presence" are the same. Collapse them.
- Abstraction imbalance: don't mix specific skills (e.g. "Pilot") with capability domains (e.g. "Wits", "Will"). Pick one level of abstraction.
- The "tax stat" trap: if the sixth attribute is purely the genre's signature power (just "magic" or "hacking"), characters who don't do that thing have a wasted slot. Better: name it broader so non-specialists can still benefit (e.g. Shadow = perception of the unnatural, not just casting; Edge = street instinct, not just netrunning).
- Generic names that don't sound like the genre. Read the six names in sequence — they should evoke the pitch.

If the input contains an `overlap_repair_note` field, your previous attempt produced overlapping attributes. Read the note carefully and rewrite descriptions and examples to eliminate the specific overlaps it cites. Each attribute's examples must be unambiguous about which attribute they belong to — a reader should not be able to plausibly assign an example task to two different attributes.

Return JSON only.
