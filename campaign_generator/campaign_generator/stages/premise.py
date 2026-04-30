from __future__ import annotations

import json

from common.llm import LLMClient, generate_structured
from common.pack import GenrePack
from ..schemas import PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "01_premise.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    pack: GenrePack,
    seed: CampaignSeed,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> PremiseDocument:
    context = {
        "pack_name": pack.metadata.pack_name,
        "tone": pack.tone,
        "example_hooks": pack.example_hooks,
        "seed": seed.model_dump(exclude_none=True),
    }
    return generate_structured(
        client=client,
        stage_name="premise",
        system_prompt=system_prompt,
        user_prompt=json.dumps(context, indent=2),
        schema=PremiseDocument,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
