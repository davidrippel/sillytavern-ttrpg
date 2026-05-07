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


def test_style_override_keeps_subject_details_when_prompt_is_already_photorealistic():
    prompt = (
        "Full-body photorealistic character portrait of a woman in her early 40s with perfectly coiffed blonde hair "
        "showing silver roots, wearing a conservative but expensive dress in a refined drawing room. "
        "Sharp, observant eyes and a gentle expression. No illustration, comic, painting, or sketch look."
    )

    effective = _apply_style_override(
        prompt,
        "Full-body photorealistic character portrait, realistic skin texture, natural anatomy, cinematic lighting.",
    )

    assert "woman in her early 40s" in effective.lower()
    assert "blonde hair showing silver roots" in effective.lower()
    assert "refined drawing room" in effective.lower()
