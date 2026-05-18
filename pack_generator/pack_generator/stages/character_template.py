from __future__ import annotations

from typing import Any


def build() -> dict[str, Any]:
    """Story-mode (v2) character template.

    The shape is fixed by ``common.pack.CharacterTemplate``; this stage
    is deterministic and produces the empty starting sheet a player
    fills in. Genre-specific default ``belongings`` may be seeded by
    editing this function for a specific pack if desired — but the
    default is empty, so the player makes every creative choice.
    """
    return {
        "name": "",
        "concept": "",
        "advantages": [],
        "disadvantages": [],
        "belongings": [],
        "relationships": [],
        "notes": "",
    }
