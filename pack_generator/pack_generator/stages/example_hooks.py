from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import ExampleHooksDraft, GMOverlay, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "08_example_hooks.md"


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
) -> ExampleHooksDraft:
    context = {
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
        "npc_conventions": overlay.npc_conventions,
        "example_characters": brief.example_characters,
    }
    return call_llm(
        client=client,
        stage_name="example_hooks",
        system_prompt=system_prompt,
        context=context,
        schema=ExampleHooksDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
