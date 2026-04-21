from __future__ import annotations

import json

from ..llm import LLMClient, LLMError, generate_structured
from ..schemas import ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from ..validation import ValidationLog, validate_clue_graph


PROMPT_FILE = "06_clue_chains.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    density: str,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ClueGraph:
    repair_note = ""
    for attempt in range(1, 4):
        context = {
            "premise": premise.model_dump(),
            "plot": plot.model_dump(),
            "factions": factions.model_dump(),
            "npcs": npcs.model_dump(),
            "locations": locations.model_dump(),
            "clue_chain_density": density,
            "repair_note": repair_note,
        }
        clue_graph = generate_structured(
            client=client,
            stage_name="clue_chains",
            system_prompt=system_prompt,
            user_prompt=json.dumps(context, indent=2),
            schema=ClueGraph,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        errors = validate_clue_graph(plot, npcs, locations, clue_graph)
        if not errors:
            return clue_graph
        validation_log.write(f"[clue_chains] repair attempt {attempt}: {'; '.join(errors)}")
        repair_note = "Repair these constraint failures: " + "; ".join(errors)
    raise LLMError("clue_chains failed cross-stage validation after 3 attempts")
