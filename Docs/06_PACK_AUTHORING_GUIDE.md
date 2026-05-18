# Genre Pack Authoring Guide

Reference for humans (or LLMs) writing genre packs by hand, without the pack generator. Also useful for reviewing and editing packs produced by the generator.

Read `02_GENRE_PACK_SPEC.md` first for the formal contract. This document is the conceptual guide — what each file is *for*, common pitfalls, and patterns that work across genres.

This guide describes **schema v2** packs (story-mode only — no attribute scores, no resource pools, no dice). For migrating v1 packs, see the migration section in `02_GENRE_PACK_SPEC.md`.

---

## Before you start

Answer these questions. The answers shape every file in the pack.

### What is one campaign in this genre about?

Not the meta-genre ("cyberpunk"), but what a typical campaign looks like. "Street-level netrunners pulling a job that goes wrong" is a campaign. "Cyberpunk" is not. The answer drives tone, complications, the kinds of advantages players will pick, and the default generator seed.

### What does failure feel like?

In Symbaroum, failure means corruption creeping in — you succeed but lose a piece of yourself. In cosmic horror, failure means losing grip on sanity. In heist, failure means heat rising — the law closing in. The failure texture is the genre's emotional core. Get this right and the rest falls into place.

The pack expresses failure in two places: the *complications* list (concrete consequences) and the *translating pressures into fiction* section of the overlay (how accumulating signs land in prose).

### What are the protagonist's signature capabilities?

Fantasy protagonists wield magic — supernatural, costly. Cyberpunk protagonists wield cyberware — technological, invasive, also costly. Hard SF protagonists wield training and tools — mundane but hard-won. What is the *class* of power available, and what's its cost?

In v2 packs, this lives in two places: the *advantages_disadvantages* vocabulary (the kinds of phrases a character builds with) and the overlay's *resolving actions* section (how the GM leans on those advantages).

### What is the genre's accumulating pressure?

The thing that piles up. Symbaroum: corruption. Cosmic horror: sanity loss. Heist: heat. Hard SF: ship damage / oxygen / supply. Cyberpunk: a mix — humanity, heat, debt.

The pack does not track this as a number. The GM describes accumulating signs in prose, and the system's fact extractor picks them up. The overlay must give the GM a vocabulary of concrete signs for the pressure (smells, sensations, NPC reactions, physical marks) so the prose stays specific.

### What content is in-bounds, and what is out?

Not every genre wants every theme. Dark fantasy probably wants body horror; it probably doesn't want techno-babble. Cyberpunk wants corporate violence; it may not want cosmic horror. Declare these early — the GM overlay references them, the campaign generator uses them, and the player's safety hinges on them.

---

## File-by-file guidance

### `pack.yaml`

Metadata. Fill it in last, when everything else is stable. The `description` field is what shows in the extension's pack picker — make it evocative in one sentence. Make sure `schema_version: 2`.

### `character_template.json`

Almost no creative work. The shape is fixed (`name`, `concept`, `advantages`, `disadvantages`, `belongings`, `relationships`, `notes`). You may pre-seed defaults that fit the genre — a witch-hunter pack might pre-fill `belongings` with `["silver-edged knife", "manual of rites"]` so new characters start with genre-appropriate gear without the player having to invent every item.

Don't pre-fill `advantages` or `disadvantages` — those are the player's expressive choices. The vocabulary file is the right place to suggest, not the template.

### `gm_prompt_overlay.md`

**The hardest file.** This is what makes the pack *feel* like the genre in play. The base GM prompt handles structure; this handles voice, texture, and priorities.

Keep it under 1500 words. The GM doesn't need every subtlety spelled out — LLMs interpolate well from a few strong examples. What they need:

- **Sensory markers of the genre.** Not "dark and mysterious" but "the smell of wet stone and old blood; the sound of distant bells; the ever-present weight of the forest."
- **The adjudication grammar.** When does an advantage land hard? What does a clean win look like in this genre (rare, costly, earned)? What does a failure look like? Don't restate the engine — describe the *texture* the engine should produce.
- **The pressure vocabulary.** For the genre's accumulating pressure, give the GM 4–8 concrete signs they can drop into prose — sweat, smell, animals reacting, a reflection wrong, a debt remembered. Without this list, the GM defaults to "you feel corrupted" and the genre dies.
- **NPC voices.** 3–6 archetypes with one-line speech notes — "the inquisitor speaks in formal, certain cadence" lands; "NPCs talk normally" doesn't.

Avoid:

- Lists of rules the base prompt already covers (NPC format, OOC handling, length cap, "never invent campaign truths")
- Mere vibes without specifics ("make it dark")
- Internal contradictions ("prioritize mood" vs "always be clear about options")
- References to dice, attribute scores, abilities, or resources — those concepts are retired in v2

### `tone.md`

Optional and not runtime-injected. Think of it as the pack's mood board. Soundtrack notes, writing samples, visual references. Useful for pack authors and pack reviewers; ignored by tools at runtime, but the campaign generator does scan it to calibrate hook prose.

Can be empty. Don't pad.

### `complications.md`

Genre-flavored narrative complications. Aim for 10–15 genre-specific entries plus 5–8 universal ones (marked `[universal]`).

Good complications:

- Are *specific* to the genre (not "something bad happens").
- Are *actionable* (describe a concrete change to the situation).
- Ratchet tension rather than ending scenes.
- Layer with the pressure vocabulary — when an action goes badly *and* a corruption sign appears, the genre's emotional core lands harder.

Bad complications:

- "The player loses." (Dead end.)
- "Something mysterious happens." (Too vague.)
- "The GM decides." (Not a move.)

The mandatory "success but..." section is where most packs get sloppy. Authors write 12 great failure complications and then list 3 lazy "success but slower" entries. Spend the same effort on the success-with-cost section — that's where the genre's texture shows up most often, because most player actions succeed.

### `advantages_disadvantages.md`

Two parts: advantages and disadvantages, each grouped by axis. The genre defines its own axes. Symbaroum uses bodily / knowledge / mystical / social. A heist pack might use crew-role / contact-network / mark / heat. A space opera pack might use shipboard / planetside / faction-credit / debt.

Each entry is a short phrase that:

- Names a **specific** thing the GM can picture (place, person, training, mark).
- Is invocable — the player can point to it and say *"this is in play."*
- Cuts both ways when appropriate. "Spoken for by a forest spirit" is an advantage in the woods and a disadvantage in church.
- Stays grounded in the genre. No mechanical jargon, no anachronism, no genre-mixing.

Aim for 20–35 advantages and 15–25 disadvantages total. Less than that and the player has too few suggestions; more than that and the list reads like a catalog and stops being scannable.

### `example_hooks.md`

Three is plenty. Two in the same tone, one deliberately different (a comic relief hook in an otherwise grim pack — shows the GM the tonal range available).

Each hook is 2–3 paragraphs, written from the player's perspective or as an opening scene. Ends at a moment of choice — "What do you do?"

These don't run at runtime. They're read by the campaign generator's prompts to calibrate its own hook generation, and by humans reviewing the pack.

### `generator_seed.yaml`

The defaults a campaign generator uses when you run it with no seed file. Be specific — "setting_anchors: [the frontier]" is useless; "setting_anchors: [derelict_colonies, alien_ruins, contested_trade_routes]" is useful.

Key v2 fields:

- `num_truths`: typical 5–10. The atomic underlying facts the campaign hangs on. Fewer for shorter campaigns, more for sprawling ones.
- `num_complications`: typical 8–15. Campaign-specific complications layered on top of the pack's universal list.
- `num_factions`: typical 3–5.

Retired fields (don't include): `clue_chain_density`, `branch_points`, `num_acts`.

The campaign-level seed file overrides these. The pack seed is a starting point.

### `naming.yaml` (optional)

Two lists of one-sentence prompts the campaign generator uses to keep NPC and location naming diverse and on-genre across runs.

- `naming_registers`: 8–14 entries, each a culturally or stylistically distinct naming convention an LLM can sample names from. Cover the genre's social spectrum (insiders, outsiders, underclass, institutions). For real-world-coded registers, name the source culture(s) concretely. For invented-culture registers, describe the *pattern* (compound construction, honorific particles, generational markers), not just vibes.
- `district_flavors`: 8–16 entries, each a kind of neighborhood, deck, settlement, or precinct cluster the genre actually has. Concrete and rooted in the genre.

When in doubt, **author this file**. The campaign generator has cross-genre fallbacks but they're Earth-historical-coded and will misfire on hard-SF, weird-fiction, or strongly-coded fantasy packs.

### `REVIEW_CHECKLIST.md`

When hand-authoring, write this last. It should contain items *specific to the pack* that a reviewer should check, not generic process items. Examples:

- Specific archetypes you're uncertain about
- Pressure signs that might be too subtle or too on-the-nose
- Tone sections you're not sure landed
- Whether the advantages_disadvantages vocabulary covers the genre's spectrum

If you can't think of concrete items, the pack is either very good or you're not being critical enough.

---

## Patterns that work across genres

### The signature pressure

Every genre has one accumulating pressure that defines its emotional core. Magic costs corruption. Cyberware costs humanity. Sanity is sanity. Heat is heat. Pick one. Two is overdesign — the GM will track neither well.

The pressure is rendered in *prose signs* (sensory and social), not numbers. The pack's overlay must enumerate at least 4 concrete signs for that pressure. The campaign generator's truth-discovery surfaces can hook into the same vocabulary.

### Advantages that cut both ways

The best advantages in story mode are double-edged. "Known to the river clans as one of theirs" is a clear advantage at the docks and a clear disadvantage at the bishop's palace. The pack's vocabulary should favor these — they generate scene variety without the player having to invent it.

### Specific NPC voices

The overlay's NPC conventions should list 3–6 recognizable archetypes for the genre. Give each a one-line speech note. The GM uses these as a vocabulary when improvising NPCs between the named ones in the lorebook.

### Tone via constraint

The overlay is most effective when it says "never do X" and "always do Y" rather than "try to be grim." Constraints generate style more reliably than descriptors.

### Complications that escalate, not end

Every complication should leave the scene playable. "You die" is not a complication; it's a dead end. "You wake up somewhere you shouldn't be" is a complication — it opens new scenes.

---

## Anti-patterns

### The "everything-and-the-kitchen-sink" pack

"My pack is fantasy AND science fiction AND horror." This is not a pack; it's three packs fighting in a trenchcoat. Pick one. Ship three if you really need all of them.

### The empty overlay

"The setting is grimdark fantasy." Not enough. The LLM will fill in generic grimdark fantasy, which is usually lazy. Specific is kind.

### The overloaded overlay

The GM prompt bloats to 3000 words and starts repeating itself. If you can't say it in 1500 words, the pack isn't crystallized yet. Cut.

### The number-leak

A v2 pack that says "1 temporary corruption" or "+1 to rolls" anywhere. The system has no numbers. Every quantity must be expressed in prose — *a single corruption sign*, *a clear advantage in this moment*, etc. Audit every file for stray integers and dice notation before shipping.

### The vague advantage

`advantages_disadvantages.md` listing "strong," "smart," "lucky." The GM cannot adjudicate against these specifically enough. Force concreteness — "knife-fighter from the river camps," "schooled in herbalism," "a face people forget within an hour."

### The contradictory content list

"content_to_avoid: grimdark" alongside "tone_keywords: grim, bleak, unforgiving." Pick a lane.

---

## Editing a generated pack

If you're reviewing and editing a pack the pack generator produced, work in this order:

1. Read `REVIEW_CHECKLIST.md` first. Address each item.
2. Read `gm_prompt_overlay.md` with the genre in your ear. Cut the generic, sharpen the specific. Audit for any leaked stat-mode language ("rolls," "attributes," "+1").
3. Read `complications.md`. Are at least 10 entries specific to the genre? Is the "success but..." section as strong as the failure section?
4. Read `advantages_disadvantages.md`. Are the entries concrete enough to invoke? Are the axes the right axes for this genre?
5. Read `example_hooks.md`. Do the hooks promise the tone the overlay describes?
6. Spot-check `character_template.json` for genre-appropriate default `belongings` (if seeded).
7. Run the pack through the validator. Fix errors.
8. Run a test campaign generation. Scan the opening hook and initial Author's Note. Does it feel like the genre? Does the AN list live threads, recent facts, and (when applicable) a director's note — and nothing else?

The goal is not perfection on the first pass. The pack improves with play. After a session or two, come back and revise the overlay, add complications that came up, sharpen advantage phrases the player kept rephrasing.

---

## When to give up and start over

Sometimes a pack generation goes wrong in ways that aren't worth fixing by editing. Signs:

- The complications list is generic across genres — the pack hasn't found its specific voice.
- The advantages vocabulary reads like every-genre-ever — no genre-specific texture.
- The overlay is structurally generic and rewriting it would be writing from scratch.
- The pressure vocabulary doesn't connect to the complications (signs accumulate to nothing).

When this happens, rewrite the brief (the tone hints and pressure description are usually the culprits) and regenerate. Editing a bad pack takes longer than generating a new one.
