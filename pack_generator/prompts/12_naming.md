You write only valid JSON matching the requested schema.

Task: produce two lists that the campaign generator uses to keep NPC and location naming diverse and genre-appropriate across campaigns generated from this pack.

You produce:

- `naming_registers`: 8-14 entries. Each entry is a one-sentence description of a naming convention that fits this genre. The convention should be specific enough that a separate LLM, given just that one sentence, can sample plausible given names and surnames from it. Cover a broad range — different cultures, social classes, professions, eras, or fictional populations — so consecutive campaigns generated from this pack don't keep landing on the same handful of names. The campaign generator picks one register as primary and one as secondary per campaign.

- `district_flavors`: 8-16 entries. Each entry is a one-sentence description of a kind of neighborhood, precinct, deck, settlement, or other location-cluster archetype that fits this genre. The campaign generator picks one per campaign to flavor the locations.

Style guide for both lists:

- Be concrete and rooted in the genre's setting. A space opera should not have "embassy row" generically — it should have "diplomatic envoy berths at a neutral station, each flying its own atmosphere mix". A dark fantasy should not have "the immigrant quarter" — it should have a specific genre-true equivalent.
- Cover the genre's social spectrum: rich and poor, insiders and outsiders, the establishment and the underclass, the institutions and the people they exclude.
- Don't repeat the same register or flavor twice in different words. Each entry should be a meaningfully different option for the campaign generator to pick.
- For real-world-coded registers (historical or contemporary cultures), be respectful and concrete: name the cultural source(s) and give a couple of example name fragments where useful, rather than relying on stereotypes.
- For invented-culture registers (in fantasy or SF), describe the *pattern* (compound construction, honorific particles, generational markers, etc.), not just vibes.

Length:
- Each `naming_registers` entry should be at least 30 characters and ideally a full descriptive sentence.
- Each `district_flavors` entry should be at least 20 characters and concrete.

Do not produce a register list that's just real-world ethnicities for a science-fiction or high-fantasy pack — translate into the genre. The campaign generator will treat these as authoritative for this pack and not fall back to its generic defaults if you provide them.
