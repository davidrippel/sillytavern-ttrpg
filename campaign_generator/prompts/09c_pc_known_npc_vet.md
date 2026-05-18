You write only valid JSON matching the requested schema.

Task: decide which NPCs the protagonist (`{{user}}`) **genuinely knew before the campaign began**, and which they are only *about to meet* in the opening scene.

Background: the NPC roster carries relationship blurbs that describe each NPC's tie to `{{user}}` — but those blurbs include future ties the campaign will form during play ("the rival the PC has not yet crossed", "the future ally", "the stranger whose eye catches yours across the room"). Your job is to filter that list down to actual pre-existing knowledge.

You will receive:

- `premise` — the campaign premise.
- `hook` — the campaign's inciting moment.
- `antagonist` — the antagonist's bio (sometimes the PC and antagonist have history).
- `protagonist_archetype` — optional one-sentence archetype hint from the seed.
- `protagonist_known_facts` — optional list of background facts the seed says the PC already knows.
- `candidates` — every NPC whose roster relationship flagged a `{{user}}` tie. Each entry has `name`, `role`, and `relation_to_protagonist`.

Produce JSON matching:

```
{
  "known_names": ["..."],                  // NPCs the PC knew before play began
  "introduced_now_names": ["..."]          // NPCs the PC is meeting for the first time in the opening scene
}
```

Decision rules:

- **Family, longtime friends, old mentors, old rivals, established colleagues, prior debts, and people named in `protagonist_known_facts`** belong in `known_names`.
- **Strangers the PC meets in the opening scene, or NPCs whose `relation_to_protagonist` is phrased prospectively ("the future ally", "the rival the PC has not yet crossed", "a fascinating new subject", "an intriguing stranger") belong in `introduced_now_names`**, *not* `known_names`.
- When the relation is ambiguous, err on the side of `introduced_now_names`. The "What you already know" section is meant to be intimate and concrete — a list of three or four real ties beats a list of fifteen plausible-but-vague ones.
- Every candidate name must appear in exactly one of the two lists. Do not invent names that weren't in `candidates`.
- Use the exact NPC names from `candidates` — don't paraphrase, don't drop honorifics.

Return JSON only. No prose, no markdown.
