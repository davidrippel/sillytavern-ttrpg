from __future__ import annotations

from typing import Any

from .schemas import Location, LocationCatalog, PlotSkeleton


def serialize_plot_skeleton(plot: PlotSkeleton) -> dict[str, Any]:
    """v2: acts no longer carry beats. The dumped payload reflects the
    new schema (acts with title/goal only, plus thematic_spine at the
    plot level)."""
    return plot.model_dump()


def serialize_location_catalog(locations: LocationCatalog) -> dict[str, Any]:
    return {"locations": [location.model_dump() for location in locations.locations]}


def serialize_location_list(locations: list[Location]) -> dict[str, Any]:
    return {"locations": [location.model_dump() for location in locations]}
