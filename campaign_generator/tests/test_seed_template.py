from campaign_generator.pack import load_pack
from campaign_generator.seed import load_seed
from campaign_generator.seed_template import build_seed_template


def test_seed_template_contains_pack_specific_menu(tmp_path):
    pack = load_pack("genres/symbaroum_dark_fantasy")
    content = build_seed_template(pack)
    assert "corrupt_inquisitor" in content
    path = tmp_path / "seed_template.yaml"
    path.write_text(content, encoding="utf-8")
    loaded = load_seed(path, pack)
    assert loaded.resolved.genre == "symbaroum_dark_fantasy"
