from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import AttributesDraft, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "02_attributes.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AttributesDraft:
    context = {
        "brief": {
            "one_line_pitch": brief.one_line_pitch,
            "tone_keywords": brief.tone_keywords,
            "attribute_flavor": brief.attribute_flavor,
            "example_characters": brief.example_characters,
        },
        "tone_and_pillars": tone.model_dump(),
    }
    return call_llm(
        client=client,
        stage_name="attributes",
        system_prompt=system_prompt,
        context=context,
        schema=AttributesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
