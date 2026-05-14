You write only valid JSON matching the requested schema.

Task: given the candidate NPCs present in the campaign's opening scene, decide which of them the protagonist (`{{user}}`) already knew **before** play begins, and which they are meeting for the very first time **in** the opening scene.

Input context fields:
- `premise_paragraphs`, `tone_statement`, `central_conflict` — the premise that establishes the protagonist's situation as the campaign opens.
- `opening_scene` — the prose that describes the opening moment of the campaign.
- `opening_node_description` — the structured description of the act-1 starting node.
- `protagonist_known_facts` — explicit background facts the seed asserts the protagonist already knows.
- `candidate_npcs` — the NPCs the node graph says are present at the opening scene. Each has `name`, `role`, `archetype`, `summary`, and `relationship_to_user` (the bond as described in the NPC card).

How to decide:

- **Mark as `known` (PC knew them before the campaign starts):**
  - Family ties (parent, child, sibling, spouse, ex-spouse).
  - Current employer or longtime colleague named in the premise.
  - Established friends, mentors, or rivals the premise treats as part of the PC's existing life.
  - Anyone explicitly named in `protagonist_known_facts` as already known.
  - Anyone whose `relationship_to_user` describes a bond that clearly predates the campaign opening ("his daughter", "the partner he hasn't spoken to in years", "her childhood friend").

- **Mark as `introduced_now` (PC meets them for the first time in the opening scene):**
  - First-meeting cues in the opening scene: "catches your eye", "a stranger", "you don't recognize", "across the room", "introduces themselves", "you've heard of but never met".
  - NPCs merely co-present at the opening location with no established prior tie to the PC — the rival they're about to clash with, the future ally introduced here, the romance that hasn't started, the daremaster who has chosen them as a new target.
  - Anyone whose `relationship_to_user` describes a dynamic that is *about to* unfold rather than one that already exists.

Be conservative about marking NPCs as `known`. The default for an NPC who is simply present at the opening scene, without any premise-level backstory tying them to the PC, is `introduced_now`. A campaign typically has only a small handful of pre-known NPCs (often just one — a family member or close tie).

Output schema:
- `known_names`: list of NPC names the PC already knew.
- `introduced_now_names`: list of NPC names the PC is meeting for the first time in the opening scene.
- `rationale`: 1–3 sentences explaining the split.

Hard constraints:
- The union of `known_names` and `introduced_now_names` must equal exactly the set of `candidate_npcs` names — no additions, no omissions.
- The two lists must be disjoint.
- Use NPC names exactly as they appear in `candidate_npcs`.
