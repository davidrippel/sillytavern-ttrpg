from __future__ import annotations

from typing import Any

from ..schemas import AttributesDraft, ResourcesDraft


def build(attributes: AttributesDraft, resources: ResourcesDraft) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for resource in resources.resources:
        starting = resource.starting_value
        if starting is None:
            # Fall back to a sensible default for unspecified resource kinds.
            starting = 0 if resource.kind != "flag" else False
        state[resource.key] = starting
    state["conditions"] = []

    return {
        "name": "",
        "concept": "",
        "attributes": {a.key: 0 for a in attributes.attributes},
        "abilities": [],
        "equipment": [],
        "state": state,
        "notes": "",
    }
