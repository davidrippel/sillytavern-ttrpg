from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import GMOverlay, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "06_gm_prompt_overlay.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> GMOverlay:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "pressure_flavor": brief.pressure_flavor,
        "advantages_disadvantages_hint": brief.advantages_disadvantages_hint,
        "complications_hint": brief.complications_hint,
    }
    return call_llm(
        client=client,
        stage_name="gm_prompt_overlay",
        system_prompt=system_prompt,
        context=context,
        schema=GMOverlay,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
