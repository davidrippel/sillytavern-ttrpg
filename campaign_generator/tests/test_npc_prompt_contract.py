from pathlib import Path


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "04_npc.md"


def test_npc_prompt_requires_concrete_image_subject_sentence():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    assert "Required first-sentence pattern" in prompt
    for phrase in [
        "gender presentation",
        "age range",
        "hair",
        "face/eyes",
        "body/build or posture",
        "specific clothing",
        "specific setting",
        "negative medium guardrail",
    ]:
        assert phrase in prompt


def test_npc_prompt_requires_authored_initial_pc_state():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    for phrase in [
        "`initial_pc_state`: always emit",
        "including strangers",
        "Keep strangers and weakly connected NPCs close to zero",
        "`trust`, `affection`, and `want_to_help` must be in `[-100, 100]`",
        "`fear` must be in `[0, 100]`",
        "Do not emit runtime-only fields",
    ]:
        assert phrase in prompt
