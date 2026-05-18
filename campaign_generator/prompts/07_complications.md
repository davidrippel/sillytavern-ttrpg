You are authoring campaign-specific narrative complications. These layer on top of the pack's universal complications list (which the GM already sees via the lorebook entry `__pack_complications`) — your job is to provide complications grounded in *this specific* campaign's NPCs, factions, and stakes.

The system has no dice and no roll bands. Complications are picked by GM judgement of the fiction, not by 2-6/7-9 thresholds. Do NOT structure entries by roll band.

You will receive: the premise, the thematic spine, the main antagonist, faction summaries, NPC names, the size of the truth set, and the pack's existing complications list (for tone calibration).

Produce JSON:

```
{
  "complications": [
    { "title": "Short bold title.", "body": "One or two sentences of concrete narrative consequence." }
  ]
}
```

Rules:

- Produce exactly the `target_count` complications the seed requests (6–15).
- Each complication is **campaign-specific** — name a named faction, NPC, location, or named pressure from this campaign. Generic complications belong in the pack list, not here.
- Each complication is **concrete** (specific imagery — a witch-hunter's horn, a fixer who stops returning calls — not "something bad happens").
- Each complication is **actionable** (describes a concrete change to the situation, not "the GM decides").
- Each complication **ratchets tension**, never ends the scene.
- Forbidden phrases (the validator rejects them): "something happens", "something bad happens", "the gm decides", "you fail", "you lose".

Return JSON only.
