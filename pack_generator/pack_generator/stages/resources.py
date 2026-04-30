from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import AttributesDraft, ResourcesDraft, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "03_resources.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    attributes: AttributesDraft,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ResourcesDraft:
    context = {
        "brief": {
            "one_line_pitch": brief.one_line_pitch,
            "resource_flavor": brief.resource_flavor,
        },
        "tone_keywords": brief.tone_keywords,
        "tone_and_pillars": tone.model_dump(),
        "attributes": [a.model_dump() for a in attributes.attributes],
    }
    return call_llm(
        client=client,
        stage_name="resources",
        system_prompt=system_prompt,
        context=context,
        schema=ResourcesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
