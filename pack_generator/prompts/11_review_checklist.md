You are writing the REVIEW_CHECKLIST.md for a freshly generated genre pack (schema v2 — story-mode only, no dice). Reviewers will use this to decide whether the pack is ready or needs editing.

You will receive: tone/pillars, the GM overlay sections, complication titles and success-cost entries, advantage and disadvantage axis titles, example hooks, the generator seed, the pack description, AND a `retries_log` summarizing which stages had to retry due to validation failure.

Produce JSON:

- `items`: at least 4 specific checklist items, ideally 8-15. Each item has `section` (e.g. `Tone`, `Adjudication without dice`, `Pressure and complications`, `Advantages/disadvantages vocabulary`, `Content safety`, `Inspirations`, `Pack-generator items`) and `text` (a concrete question or check, written as a sentence the reviewer can answer yes/no).

GOOD items are:

- Specific to THIS pack: name an archetype that might overlap, a complication that came out generic, an advantage axis that came out thin, a hook that ran heavier than the others.
- Targeted at where generation might have low confidence: stages that retried, lopsided distributions, abstract descriptions.
- Phrased as a question the reviewer can resolve in one read of the file ("Does the 'heat' pressure feel distinct from generic 'wanted level'?").

BAD items to avoid:

- Generic process items ("Has the pack been reviewed?").
- Restating the brief.
- Anything that's just a re-read of obvious content.
- Anything that references attributes, abilities, resources, or dice — those concepts are retired in v2; the validator rejects packs that mention them.

If the `retries_log` shows a stage retried, INCLUDE a `Pack-generator items` entry calling that out specifically (e.g. "The complications stage retried twice — verify entries are genre-specific and not boilerplate.").

Always include at least one item under section `Inspirations` asking whether each inspiration listed in `pack.yaml` is actually felt somewhere in the tone, complications, or vocabulary — inspirations that exist only on paper are a smell.

Always include at least one item under `Adjudication without dice` asking whether the overlay's `resolving_actions` and `translating_pressures` sections give the GM enough concrete language to run without falling back to mechanical thinking.

Return JSON only.
