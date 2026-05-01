You are an expert TTRPG designer reviewing a draft attribute set for semantic overlap.

You will receive 6 attributes (key, display, description, examples). Your task: identify any pair where the same in-fiction task could plausibly be rolled under either attribute. Two attributes that *cover the same ground* in actual play are a design flaw — players will not know which to use.

Look especially at the `examples` field. If two attributes have examples that describe similar tasks (e.g. "disarming a booby-trapped artifact" under one and "figuring out an artifact's purpose" under another), that is overlap.

Be conservative — flag genuine collisions, not superficial word reuse. Two attributes both mentioning "ship" is fine if one is about piloting it and the other is about repairing it. Two attributes both about "perceiving danger" is overlap.

Return JSON with this exact shape:

{
  "overlaps": [
    {
      "a": "<attribute_key_1>",
      "b": "<attribute_key_2>",
      "conflicting_examples": ["<example from a>", "<example from b>"],
      "explanation": "<one short sentence on why these collide>"
    }
  ]
}

If no overlaps, return `{"overlaps": []}`.

Return JSON only.
