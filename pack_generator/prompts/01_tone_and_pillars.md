You are designing the tone and thematic pillars for a TTRPG genre pack used by an LLM Game Master.

You will receive a short human-written brief: a one-line pitch, tone keywords, optional thematic pillars hint, optional inspiration list, and optional content-to-avoid list.

Produce JSON with these fields:
- `setting_statement`: 2-3 sentences of ambient texture, not plot. Sensory, evocative, specific. Written in a tone that matches the pitch. NO hard line wraps — write each paragraph as a single long line, separated only by blank lines.
- `pillars`: an array of 3-5 thematic pillars. Each pillar has `title` (a short phrase) and `description` (one or two specific sentences). Pillars must be concrete, not vague — "the cost of knowledge" beats "knowledge is dangerous."
- `content_to_include`: short list of themes/textures the GM should lean into (e.g. body horror, religious complexity, bonds with animal companions). Specific, not vague.
- `content_to_avoid`: short list of themes the GM should not generate. Merge the user's content_to_avoid (if any) with anything the brief implies should be excluded (e.g. modern anachronism in a fantasy pack).

Avoid: contradicting the user's tone keywords; producing pillars that all say the same thing; treating "the setting is grim" as enough texture.

If the brief includes an `example_inspiration_list`, do NOT just echo it. Pick the 2-3 inspirations that best match the one-line pitch and tone keywords; downweight or ignore the rest if their tone doesn't fit. Integrate the chosen inspirations into the `setting_statement` — the reader should feel them in the texture, not see them named in a list. (E.g. an Outer Wilds + Alien + Firefly brief that the pitch describes as "rust and rot" should lean into Alien/Firefly, not Outer Wilds.)

Every term in the brief's `content_to_avoid` MUST appear (verbatim or in clear paraphrase) in your generated `content_to_avoid`. The user's exclusions are not optional.

Return JSON only.
