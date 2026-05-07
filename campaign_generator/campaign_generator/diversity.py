from __future__ import annotations

import json
import random
from pathlib import Path

from common.pack import GenrePack

DEFAULT_CULTURAL_REGISTERS = [
    "Slavic-coded (Polish, Czech, Russian roots)",
    "Mediterranean port-city (Italian, Greek, Maltese)",
    "Levantine and Anatolian (Turkish, Lebanese, Armenian)",
    "Iberian and Latin American (Spanish, Portuguese, Mexican)",
    "Yoruba- and Akan-influenced West African",
    "Ethiopian and Eritrean Horn-of-Africa",
    "Persian and Central Asian (Farsi, Tajik, Uzbek)",
    "South Asian (Bengali, Tamil, Punjabi)",
    "Southeast Asian (Vietnamese, Thai, Filipino)",
    "Sinophone diaspora (Cantonese, Hokkien, Mandarin)",
    "Japanese with regional and Ainu influences",
    "Korean with mixed hanja and native Korean roots",
    "Pacific Islander (Samoan, Maori, Hawaiian)",
    "Nordic and Sami (Icelandic, Norwegian, Finnish)",
    "Gaelic and Brythonic (Irish, Scottish, Welsh, Cornish)",
    "Basque and Occitan",
    "Romani-influenced central European",
    "Andean and Quechua-influenced",
    "Caribbean creole (Haitian, Jamaican, Trinidadian)",
    "Afro-Brazilian and Bahian",
    "Indigenous North American (Diné, Lakota, Cree — used respectfully)",
    "Roman/Late-Antique with vulgar Latin contractions",
    "Old Norse and skaldic compound names",
    "Byzantine Greek with court titles",
]

DEFAULT_DISTRICT_FLAVORS = [
    "working docks and warehouse blocks",
    "old religious quarter with overlapping shrines",
    "immigrant market streets named after trades",
    "industrial flats converted to lofts",
    "tenement courts and back-alley speakeasies",
    "high-society avenues and private clubs",
    "university and library precincts",
    "red-light and after-hours districts",
    "canal-side or riverside neighborhoods",
    "rail-adjacent freight and shunting yards",
    "outer-ring slums and shantytowns",
    "rooftop gardens and tower-top gentry",
    "ruined or half-abandoned old town",
    "mixed-use bazaars and caravanserai",
    "subterranean service tunnels and undercity",
    "embassy row and diplomatic enclaves",
    "garrison and military quarter",
    "cemetery, crematorium, and mortuary trades",
]

NAMING_STYLES = [
    "place names built from a trade plus a topographic feature (e.g. Tanners' Reach)",
    "place names referencing a saint, prophet, or local folk-hero",
    "place names with a color and a noun (e.g. The Vermilion Cistern)",
    "place names borrowing from a foreign language pocket in the city",
    "place names that are local nicknames, not official designations",
    "place names tied to weather, seasons, or time of day",
    "place names referencing past disasters (the Drowned Mile, the Burned Tier)",
    "place names that are numeric or directional (Ninth Cut, Eastern Spit)",
    "place names that are proprietor-possessive (someone's tavern, parlor, garage)",
]


def pick_diversity_seed(
    random_seed: int | None,
    pack: GenrePack | None = None,
) -> dict[str, str]:
    """Sample one cultural register, one secondary register, one district
    flavor, and one naming style. Pack-supplied lists from `naming.yaml`
    override the cross-genre defaults; missing/empty lists fall back to the
    defaults defined in this module."""
    rng = random.Random(random_seed)
    registers = (
        list(pack.naming.naming_registers)
        if pack is not None and pack.naming.naming_registers
        else DEFAULT_CULTURAL_REGISTERS
    )
    districts = (
        list(pack.naming.district_flavors)
        if pack is not None and pack.naming.district_flavors
        else DEFAULT_DISTRICT_FLAVORS
    )
    return {
        "cultural_register": rng.choice(registers),
        "secondary_register": rng.choice(registers),
        "district_flavor": rng.choice(districts),
        "naming_style": rng.choice(NAMING_STYLES),
    }


def _load_names(path: Path, key: str) -> list[str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    items = data.get(key) or []
    names: list[str] = []
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def collect_recent_names(
    *,
    campaigns_dir: Path,
    current_dir: Path,
    max_campaigns: int = 5,
) -> tuple[list[str], list[str]]:
    """Return (npc_names, location_names) drawn from up to `max_campaigns` most
    recently modified sibling campaigns (excluding `current_dir`)."""
    if not campaigns_dir.exists() or not campaigns_dir.is_dir():
        return [], []

    current_resolved = current_dir.resolve()
    siblings: list[tuple[float, Path]] = []
    for child in campaigns_dir.iterdir():
        if not child.is_dir():
            continue
        if child.resolve() == current_resolved:
            continue
        stages_dir = child / "stages"
        if not stages_dir.is_dir():
            continue
        try:
            mtime = stages_dir.stat().st_mtime
        except OSError:
            continue
        siblings.append((mtime, child))

    siblings.sort(key=lambda pair: pair[0], reverse=True)
    siblings = siblings[:max_campaigns]

    npc_names: list[str] = []
    location_names: list[str] = []
    for _, sibling in siblings:
        for name in _load_names(sibling / "stages" / "npcs.json", "npcs"):
            if name not in npc_names:
                npc_names.append(name)
        for name in _load_names(sibling / "stages" / "locations.json", "locations"):
            if name not in location_names:
                location_names.append(name)

    return npc_names, location_names
