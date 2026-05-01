You are writing the REVIEW_CHECKLIST.md for a freshly generated genre pack. Reviewers will use this to decide whether the pack is ready or needs editing.

You will receive: the full pack contents (tone/pillars, attributes, resources, ability categories, ability catalog, GM overlay sections, failure moves, example hooks, generator seed, pack description) AND a `retries_log` summarizing which stages had to retry due to validation failure.

Produce JSON:
- `items`: at least 4 specific checklist items, ideally 8-15. Each item has `section` (e.g. `Mechanics`, `Tone`, `Content safety`, `Pack-generator items`) and `text` (a concrete question or check, written as a sentence the reviewer can answer yes/no).

GOOD items are:
- Specific to THIS pack: name an attribute that might overlap, a category that came out thin, a hook that ran heavier than the others.
- Targeted at where the generation might have low confidence: stages that retried, lopsided distributions, abstract descriptions.
- Phrased as a question the reviewer can resolve in one read of the file ("Does Edge feel distinct from Wits in play?").

BAD items to avoid:
- Generic process items ("Has the pack been reviewed?")
- Restating the brief
- Anything that's just a re-read of obvious content

If the `retries_log` shows a stage retried, INCLUDE a Pack-generator-items entry calling that out specifically (e.g. "The attributes stage retried twice — verify the six names feel distinct in practice, not just on paper").

If a category in the ability catalog has only 2 abilities, flag it. If example_hooks #2 is much darker/lighter than the others, flag it. Read the actual content and surface where reviewer attention is most valuable.

Always include at least one item under section `Inspirations` that asks the reviewer whether each inspiration listed in `pack.yaml` is actually felt somewhere in the tone, hooks, or mechanics — inspirations that exist only on paper are a smell.

Return JSON only.
