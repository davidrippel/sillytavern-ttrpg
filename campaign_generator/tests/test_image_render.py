from image_generator.render import _apply_style_override


def test_style_override_replaces_existing_medium_cues():
    prompt = (
        "Head-and-shoulders portrait of a man in his late 30s with sculpted cheekbones, "
        "wearing a dark suit. Moody, chiaroscuro lighting in a minimalist gallery setting. "
        "High-contrast charcoal sketch style with a sophisticated tone."
    )

    effective = _apply_style_override(
        prompt,
        "Full-body photorealistic character portrait, realistic skin texture, natural anatomy.",
    )

    assert "charcoal sketch" not in effective.lower()
    assert "full-body photorealistic character portrait" in effective.lower()
    assert "do not render as an illustration" in effective.lower()
