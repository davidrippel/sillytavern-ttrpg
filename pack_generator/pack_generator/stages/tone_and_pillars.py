from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "01_tone_and_pillars.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ToneAndPillars:
    context = {
        "brief": brief.model_dump(exclude_none=True),
    }
    return call_llm(
        client=client,
        stage_name="tone_and_pillars",
        system_prompt=system_prompt,
        context=context,
        schema=ToneAndPillars,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
