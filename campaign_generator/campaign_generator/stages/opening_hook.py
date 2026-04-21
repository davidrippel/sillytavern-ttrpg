from __future__ import annotations

from ..pack import GenrePack
from ..schemas import OpeningHookDocument, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed


def render(pack: GenrePack, premise: PremiseDocument, plot: PlotSkeleton, seed: CampaignSeed) -> OpeningHookDocument:
    act_one = plot.acts[0]
    character_guidance = [
        "Create someone who belongs in this campaign's pressure points: faith, taint, ruins, or frontier survival.",
        "Give your character one reason to care about the opening hook before the first scene begins.",
        "Choose abilities and gear that let them investigate, survive, or negotiate under pressure.",
    ]
    if seed.protagonist_archetype:
        character_guidance.insert(0, f"Best fit: {seed.protagonist_archetype}")

    opening_scene = seed.opening_hook_seed or (
        f"You enter the campaign at the edge of {act_one.title.lower()}, with {plot.hook.lower()} already pulling "
        "you toward a decision you cannot comfortably ignore. The first scene should foreground danger, atmosphere, "
        "and one human detail worth protecting."
    )

    return OpeningHookDocument(
        premise=premise.premise_text,
        tone_statement=premise.tone_statement,
        character_creation_guidance=character_guidance,
        opening_scene=opening_scene,
    )
