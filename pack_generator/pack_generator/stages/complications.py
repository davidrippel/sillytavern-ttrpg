from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import ComplicationsDraft, GMOverlay, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "07_complications.md"


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
) -> ComplicationsDraft:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
        "translating_pressures": overlay.translating_pressures,
        "npc_conventions": overlay.npc_conventions,
        "complications_hint": brief.complications_hint,
        "pressure_flavor": brief.pressure_flavor,
    }
    return call_llm(
        client=client,
        stage_name="complications",
        system_prompt=system_prompt,
        context=context,
        schema=ComplicationsDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
