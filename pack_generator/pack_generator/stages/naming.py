from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import GMOverlay, NamingDraft, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "12_naming.md"


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
) -> NamingDraft:
    context = {
        "pack_name": brief.pack_name,
        "display_name": brief.display_name,
        "one_line_pitch": brief.one_line_pitch,
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
        "npc_conventions": overlay.npc_conventions,
        "campaign_style_hint": brief.campaign_style_hint,
        "example_inspirations": brief.example_inspiration_list,
    }
    return call_llm(
        client=client,
        stage_name="naming",
        system_prompt=system_prompt,
        context=context,
        schema=NamingDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
