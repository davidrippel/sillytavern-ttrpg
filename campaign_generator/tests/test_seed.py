from pathlib import Path

import yaml

from campaign_generator.pack import load_pack
from campaign_generator.seed import load_seed


def test_examples_validate_against_symbaroum_pack():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    for name in ["seed_minimal.yaml", "seed_balanced.yaml", "seed_maximum.yaml"]:
        loaded = load_seed(Path("examples") / name, pack)
        assert loaded.resolved.genre == "symbaroum_dark_fantasy"


def test_seed_merges_exclusions_and_strictness(tmp_path):
    pack = load_pack("genres/symbaroum_dark_fantasy")
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(
        yaml.safe_dump(
            {
                "genre": "symbaroum_dark_fantasy",
                "themes_exclude": ["torture_as_spectacle"],
                "strictness": {
                    "canon_consistency": "strict",
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = load_seed(seed_path, pack)
    assert "modern_anachronism" in (loaded.resolved.themes_exclude or [])
    assert "torture_as_spectacle" in (loaded.resolved.themes_exclude or [])
    assert loaded.resolved.strictness is not None
    assert loaded.resolved.strictness.canon_consistency == "strict"
