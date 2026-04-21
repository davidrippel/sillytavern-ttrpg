from __future__ import annotations

import json

from ..llm import LLMClient, generate_structured
from ..pack import GenrePack
from ..schemas import PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "02_plot_skeleton.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    premise: PremiseDocument,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> PlotSkeleton:
    context = {
        "premise": premise.model_dump(),
        "gm_overlay_excerpt": pack.gm_prompt_overlay,
        "requested_num_acts": seed.num_acts,
    }
    return generate_structured(
        client=client,
        stage_name="plot_skeleton",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=PlotSkeleton,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
