from __future__ import annotations

from datetime import date
from typing import Any

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import GMOverlay, PackDescription, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "10_pack_description.md"


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
) -> PackDescription:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "setting_and_tone": overlay.setting_and_tone,
    }
    return call_llm(
        client=client,
        stage_name="pack_yaml",
        system_prompt=system_prompt,
        context=context,
        schema=PackDescription,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )


def build_metadata(brief: GenreBrief, description: PackDescription) -> dict[str, Any]:
    inspirations: list[str] = []
    if brief.example_inspiration_list:
        for token in brief.example_inspiration_list.replace(";", ",").split(","):
            cleaned = token.strip().lower().replace(" ", "_").rstrip(".")
            if cleaned:
                inspirations.append(cleaned)
    return {
        "schema_version": brief.schema_version,
        "pack_name": brief.pack_name,
        "display_name": brief.display_name,
        "version": "1.0.0",
        "description": description.description,
        "inspirations": inspirations,
        "created": date.today().isoformat(),
        "author": None,
    }
