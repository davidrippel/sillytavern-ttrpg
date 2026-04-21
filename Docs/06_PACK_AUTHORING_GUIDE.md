# Genre Pack Authoring Guide

Reference for humans (or LLMs) writing genre packs by hand, without the pack generator. Also useful for reviewing and editing packs produced by the generator.

Read `02_GENRE_PACK_SPEC.md` first for the formal contract. This document is the conceptual guide — what each file is *for*, common pitfalls, and patterns that work across genres.

---

## Before you start

Answer these questions. The answers shape every file in the pack.

### What is one campaign in this genre about?

Not the meta-genre ("cyberpunk"), but what a typical campaign looks like. "Street-level netrunners pulling a job that goes wrong" is a campaign. "Cyberpunk" is not. The answer drives tone, ability catalog, and the default generator seed.

### What does failure feel like?

In Symbaroum, failure means corruption creeping in — you succeed at magic but lose a piece of yourself. In cosmic horror, failure means losing grip on sanity. In heist, failure means heat rising — the law closing in. The failure texture is the genre's emotional core. Get this right and the rest falls into place.

### What are the protagonist's abilities *in kind*, not in list?

Fantasy protagonists wield magic (supernatural, costly). Cyberpunk protagonists wield cyberware (technological, invasive, also costly). Hard SF protagonists wield training and tools (mundane but hard-won). What is the *class* of power available, and what's its cost? This is the ability catalog's backbone.

### What do the six attributes care about?

Most genres have a physical, a mental, a social, and a "skill" pool. The sixth attribute is where the genre lives. Symbaroum has Shadow (the occult). Cyberpunk might have Edge (street instinct). Hard SF might have Discipline (training). The sixth attribute tells you what the game is *about*.

### What content is in-bounds, and what is out?

Not every genre wants every theme. Dark fantasy probably wants body horror; it probably doesn't want techno-babble. Cyberpunk wants corporate violence; it may not want cosmic horror. Declare these early — the GM overlay references them, the campaign generator uses them, and the player's safety hinges on them.

---

## File-by-file guidance

### `pack.yaml`

Metadata. Fill it in last, when everything else is stable. The `description` field is what shows in the extension's pack picker — make it evocative in one sentence.

### `attributes.yaml`

**The hardest file.** Six attributes must cover everything the GM might call for, without overlap. Common failure modes:

- *Overlap.* "Strength" and "Might" are the same attribute. "Charisma" and "Presence" are the same. If two attributes share any core examples, collapse them.
- *Abstraction imbalance.* One attribute names a specific skill (Pilot), while others name capabilities (Wits, Will). Keep the level of abstraction consistent — either all capabilities or all domains, not a mix.
- *Overloaded social.* Many genres put "persuade, intimidate, deceive, and lead" all in one attribute (Presence, Charisma). This is usually fine in narrative play. Don't split them across two attributes just because tabletop systems do.
- *The sixth attribute problem.* If the sixth attribute is just "magic" or "hacking" or "psionics", you've created a tax: characters who don't do that thing have a wasted stat slot. Better: name the sixth attribute something broader that magic/hacking/psionics *uses*, so non-specialists can still benefit. Symbaroum's Shadow isn't only for witches — it's perception of the unnatural, usable by anyone. Cyberpunk's Edge isn't only for netrunners — it's street instinct.

The six names, collectively, should sound like a genre, not like a checklist. Read them in sequence: Might, Finesse, Wits, Will, Presence, Shadow. That's fantasy. Now: Grit, Reflex, Tech, Nerve, Charm, Edge. That's cyberpunk. Different feel entirely.

### `resources.yaml`

Every pack needs HP (universal). Beyond that, pick resources that *interact* with the GM loop:

- Resources that tick up from ability use (corruption from magic, heat from loud action)
- Resources that tick up from failure (sanity loss, stress)
- Resources that tick down from time (oxygen, fuel)
- Resources that represent relationships (faction reputation, crew morale)

Avoid resources that don't change in play — those are just character descriptors, not mechanics.

A pack with one HP and one "genre resource" is enough. A pack with HP and four different mental/physical/social resources is overdesigned — the player spends all their time tracking state instead of playing.

Threshold mechanics (accumulate to N, then bad thing happens, reset) are almost always good. They create escalation pressure without instant death.

### `abilities.yaml`

Two-part structure: categories declare how abilities *work mechanically*, the catalog is concrete examples.

**Category design:**

A category's `activation` and `roll_attribute` determine its mechanical signature. Active abilities (roll to use, cost on failure) are the most interesting — they're where player choices have real weight. Passive abilities are the supporting cast. Ritual abilities are the genre's "I spend a scene doing a thing" lever.

A good pack has:
- 1-3 active categories (the main levers)
- 1 "passive/general" category for skills that don't need a mechanical signature
- Optionally 1 ritual category for out-of-combat setup-to-payoff moments
- Optionally 1 trait category for permanent character features

If every category is active and uses the same attribute and the same consequence, you've actually only made one category.

**Catalog design:**

Players pick from the catalog (loosely) or invent within categories (also fine). The catalog's job is:
- Establish the *flavor* of what's possible in the genre
- Give new players concrete starting points
- Give the campaign generator a pool to draw from when creating antagonist capabilities

Catalog diversity matters more than size. 15 abilities spanning 4 categories with 4 ranges of power is better than 30 abilities all in one category.

Prerequisite chains (A requires B requires C) create progression arcs — a character starts with A, earns B, eventually unlocks C. Use sparingly. Most abilities should be independent so character builds aren't straitjacketed.

### `character_template.json`

Largely mechanical: derived from attributes.yaml and resources.yaml. Little creative work here. The starting values for resources should represent "a healthy character at the start of their story" — full HP, zero corruption/heat/stress, etc.

### `gm_prompt_overlay.md`

**The second-hardest file.** This is what makes the pack *feel* like the genre in play. The base GM prompt (`07_GM_BASE_PROMPT.md`) handles structure and mechanics; this handles voice, texture, and priorities.

Keep it under 1500 words. The GM doesn't need every subtlety spelled out — LLMs interpolate well from a few strong examples. What they need:

- **Sensory markers of the genre.** Not "dark and mysterious" but "the smell of wet stone and old blood; the sound of distant bells; the ever-present weight of the forest."
- **Priority hierarchy.** When in doubt, does the GM favor mood over clarity? Player agency over authored plot? Danger over comfort? State the tradeoffs.
- **Specific things to do / not to do.** "Describe corruption as physical — sweat, nausea, a buzzing at the edge of vision — not as a number going up." "Don't soften witch-hunters. They believe they're right."
- **Reference to the pack's mechanics.** When is corruption inflicted? What does a failed Shadow roll feel like? What does a successful ability activation look like in narration?

Avoid:
- Lists of rules the base prompt already covers (scene structure, STATUS_UPDATE format, roll interpretation — these are engine-level)
- Mere vibes without specifics ("make it dark") — the LLM will read this as "be grim constantly" and over-correct
- Internal contradictions ("prioritize mood" vs "always be clear about options")

### `tone.md`

Optional and not runtime-injected. Think of it as the pack's mood board. Soundtrack notes, writing samples, visual references. Useful for pack authors and pack reviewers; ignored by tools.

Can be empty. Don't pad.

### `failure_moves.md`

Genre-flavored additions to the universal failure-move list. Aim for 6-10 genre-specific moves. Each move is a concrete thing the GM can do on a 2-6 result.

Good moves:
- Are *specific* to the genre (not "something bad happens")
- Are *actionable* (describe a concrete change to the situation)
- Ratchet tension rather than ending scenes

Bad moves:
- "The player loses." (Not a move, a dead end.)
- "Something mysterious happens." (Too vague.)
- "The GM decides." (Not a move.)

The best moves are specific enough that the GM, reading the list during play, can pick one and immediately know what to narrate.

### `example_hooks.md`

Three is plenty. Two in the same tone, one deliberately different (a comic relief hook in an otherwise grim pack — shows the GM the tonal range available).

Each hook is 2-3 paragraphs, written from the player's perspective or as an opening scene. Ends at a moment of choice — what does the player do?

These don't run at runtime. They're read by the campaign generator's prompts to calibrate its own hook generation, and by humans reviewing the pack.

### `generator_seed.yaml`

The defaults a campaign generator uses when you run it with no seed file. Be specific — "setting_anchors: [the frontier]" is useless; "setting_anchors: [derelict_colonies, alien_ruins, contested_trade_routes]" is useful.

The campaign-level seed file overrides these. The pack seed is a starting point.

### `REVIEW_CHECKLIST.md`

When hand-authoring, write this last. It should contain items *specific to the pack* that a reviewer should check, not generic process items. Examples:

- Specific attribute overlaps you're uncertain about
- Ability categories that might feel thin
- Tone sections you're not sure landed
- Mechanics that might be too fiddly

If you can't think of concrete items, the pack is either very good or you're not being critical enough.

---

## Patterns that work across genres

### The "weird" category

Every genre pack should have one ability category that makes the genre *itself* — not a substitute for combat or social, but the thing that makes this genre different from generic adventure. Magic, cyberware, psionics, alien tech, the taint.

### Resource tied to the weird category

The genre-defining category should have a genre-defining resource cost. Magic costs corruption. Cyberware costs humanity. Psionics costs focus. This cost is what prevents the weird from being strictly better than the mundane, and it's where the genre's thematic weight lives.

### The ambiguous social resource

Reputation, standing, heat, notoriety — something that rises with visibility and makes the character more powerful AND more exposed. Creates interesting tradeoffs.

### Tone via constraint

The overlay is most effective when it says "never do X" and "always do Y" rather than "try to be grim." Constraints generate style more reliably than descriptors.

### One NPC archetype per faction type

The overlay's NPC conventions should list 3-5 recognizable archetypes for the genre (inquisitor, witch-hunter, cultist, corrupt noble; or: fixer, netrunner, corp suit, street samurai). The GM uses these as a vocabulary when improvising NPCs between the named ones in the lorebook.

---

## Anti-patterns

### The "everything-and-the-kitchen-sink" pack

"My pack is fantasy AND science fiction AND horror." This is not a pack; it's three packs fighting in a trenchcoat. Pick one. Ship three if you really need all of them.

### The "system heartbreaker" pack

Porting a full tabletop system's mechanics into the pack. Skill lists, combat subsystems, specific spell lists. The engine is PbtA-adjacent; it doesn't support granular mechanics. Narrative fidelity to the source system beats mechanical fidelity.

### The empty overlay

"The setting is grimdark fantasy." Not enough. The LLM will fill in generic grimdark fantasy, which is usually lazy. Specific is kind.

### The overloaded overlay

The GM prompt bloats to 3000 words and starts repeating itself. If you can't say it in 1500 words, the pack isn't crystallized yet. Cut.

### The unused catalog entry

An ability in the catalog that no NPC could ever have and no starting character would take. If it doesn't enter play, delete it.

### The contradictory content list

"content_to_avoid: grimdark" alongside "tone_keywords: grim, bleak, unforgiving." Pick a lane.

---

## Editing a generated pack

If you're reviewing and editing a pack the pack generator produced, work in this order:

1. Read `REVIEW_CHECKLIST.md` first. Address each item.
2. Read `attributes.yaml`. This is where generation most often lacks taste. Rename, redefine, consolidate.
3. Read `gm_prompt_overlay.md` with the genre in your ear. Cut the generic, sharpen the specific.
4. Read `failure_moves.md` and `example_hooks.md` together. Do the moves land the tone the hooks promise?
5. Read `abilities.yaml`. Are there obvious gaps? Any two abilities doing the same thing?
6. Spot-check `resources.yaml` and `character_template.json` for consistency.
7. Run the pack through the validator. Fix errors.
8. Run a test campaign generation. Scan the opening hook and initial Author's Note. Does it feel like the genre?

The goal is not perfection on the first pass. The pack improves with play. After a session or two, come back and revise the overlay, add abilities that came up, delete categories that never fired.

---

## When to give up and start over

Sometimes a pack generation goes wrong in ways that aren't worth fixing by editing. Signs:

- The six attributes fundamentally don't carve the genre correctly
- The GM overlay is structurally generic and rewriting it would be writing from scratch
- The resource mechanics don't interact with the ability categories at all
- The tone keywords produced a pack whose tone you don't actually want

When this happens, rewrite the brief (the tone and attribute hints are usually the culprits) and regenerate. Editing a bad pack takes longer than generating a new one.
