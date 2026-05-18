from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import AdvantagesDisadvantagesDraft, GMOverlay, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "04_advantages_disadvantages.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    overlay: GMOverlay,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AdvantagesDisadvantagesDraft:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
        "npc_conventions": overlay.npc_conventions,
        "advantages_disadvantages_hint": brief.advantages_disadvantages_hint,
        "example_characters": brief.example_characters,
    }
    return call_llm(
        client=client,
        stage_name="advantages_disadvantages",
        system_prompt=system_prompt,
        context=context,
        schema=AdvantagesDisadvantagesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
