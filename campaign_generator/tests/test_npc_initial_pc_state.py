from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from campaign_generator.schemas import NPC


def _valid_npc() -> dict:
    return {
        "name": "Mira",
        "role": "observatory keeper",
        "physical_description": "A watchful woman in a weathered coat.",
        "speaking_style": "Quiet and precise.",
        "motivation": "Protect the telescope.",
        "secret": "She broke the lens.",
        "relationships": [],
        "initial_pc_state": {
            "attitude": "Treats {{user}} as a cautious new ally.",
            "scales": {
                "trust": 10,
                "affection": 5,
                "want_to_help": 15,
                "fear": 0,
            },
        },
    }


def test_npc_accepts_complete_initial_pc_state() -> None:
    npc = NPC.model_validate(_valid_npc())

    assert npc.initial_pc_state.scales.trust == 10


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("initial_pc_state"),
        lambda payload: payload["initial_pc_state"]["scales"].pop("trust"),
        lambda payload: payload["initial_pc_state"].update({"last_seen_turn": 0}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"portrait_url": None}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"trust": "10"}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"trust": 10.0}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"trust": True}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"trust": -101}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"affection": 101}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"want_to_help": 101}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"fear": -1}),
        lambda payload: payload["initial_pc_state"]["scales"].update({"fear": 101}),
    ],
)
def test_npc_rejects_invalid_initial_pc_state(mutate) -> None:
    payload = deepcopy(_valid_npc())
    mutate(payload)

    with pytest.raises(ValidationError):
        NPC.model_validate(payload)
