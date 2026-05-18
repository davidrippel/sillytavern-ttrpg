from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import GeneratorSeedDraft, GMOverlay, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "09_generator_seed.md"


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
) -> GeneratorSeedDraft:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
        "npc_conventions": overlay.npc_conventions,
    }
    return call_llm(
        client=client,
        stage_name="generator_seed",
        system_prompt=system_prompt,
        context=context,
        schema=GeneratorSeedDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
