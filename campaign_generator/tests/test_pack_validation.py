from campaign_generator.pack import load_pack


def test_symbaroum_pack_loads():
    pack = load_pack("genres/symbaroum_dark_fantasy")
    assert pack.metadata.pack_name == "symbaroum_dark_fantasy"
    assert len(pack.attributes.attributes) == 6
    assert "Witchsight" in pack.ability_names
