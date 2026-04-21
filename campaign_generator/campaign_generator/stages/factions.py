from __future__ import annotations

import json

from ..llm import LLMClient, generate_structured
from ..pack import GenrePack
from ..schemas import FactionSet, PlotSkeleton, PremiseDocument
from ..validation import ValidationLog


PROMPT_FILE = "03_factions.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> FactionSet:
    context = {
        "premise": premise.model_dump(),
        "plot": plot.model_dump(),
        "tone": pack.tone,
    }
    return generate_structured(
        client=client,
        stage_name="factions",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=FactionSet,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
