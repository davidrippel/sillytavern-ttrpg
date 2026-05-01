from __future__ import annotations

from pathlib import Path

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import AttributeOverlapReport, AttributesDraft, ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "02_attributes.md"
JUDGE_PROMPT_FILE = "02a_attribute_overlap_judge.md"
MAX_OVERLAP_RETRIES = 1


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AttributesDraft:
    context = {
        "brief": {
            "one_line_pitch": brief.one_line_pitch,
            "tone_keywords": brief.tone_keywords,
            "attribute_flavor": brief.attribute_flavor,
            "example_characters": brief.example_characters,
        },
        "tone_and_pillars": tone.model_dump(),
    }

    judge_prompt = _load_judge_prompt()
    repair_note: str | None = None
    draft: AttributesDraft | None = None

    for attempt in range(MAX_OVERLAP_RETRIES + 1):
        attempt_context = dict(context)
        if repair_note:
            attempt_context["overlap_repair_note"] = repair_note
        draft = call_llm(
            client=client,
            stage_name="attributes",
            system_prompt=system_prompt,
            context=attempt_context,
            schema=AttributesDraft,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        if judge_prompt is None:
            break
        report = _judge_overlap(
            client=client,
            judge_prompt=judge_prompt,
            draft=draft,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        if not report.overlaps:
            break
        repair_note = _format_repair_note(report)
        validation_log.write(
            f"[attributes overlap-judge] attempt {attempt + 1} found {len(report.overlaps)} overlap(s); "
            f"repair note: {repair_note}"
        )
        if attempt == MAX_OVERLAP_RETRIES:
            validation_log.write(
                "[attributes overlap-judge] still overlapping after retries; proceeding with last draft"
            )
    assert draft is not None
    return draft


def _load_judge_prompt() -> str | None:
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / JUDGE_PROMPT_FILE
    if not prompt_path.exists():
        return None
    return prompt_path.read_text(encoding="utf-8").strip()


def _judge_overlap(
    *,
    client: LLMClient,
    judge_prompt: str,
    draft: AttributesDraft,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AttributeOverlapReport:
    judge_context = {"attributes": [a.model_dump() for a in draft.attributes]}
    try:
        report = call_llm(
            client=client,
            stage_name="attributes_overlap_judge",
            system_prompt=judge_prompt,
            context=judge_context,
            schema=AttributeOverlapReport,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )
        assert isinstance(report, AttributeOverlapReport)
        return report
    except Exception as exc:
        validation_log.write(f"[attributes overlap-judge] judge call failed: {exc}; skipping check")
        return AttributeOverlapReport(overlaps=[])


def _format_repair_note(report: AttributeOverlapReport) -> str:
    parts: list[str] = []
    for overlap in report.overlaps:
        examples = " | ".join(overlap.conflicting_examples) or "(no examples cited)"
        parts.append(
            f"Attributes {overlap.a!r} and {overlap.b!r} overlap: {overlap.explanation} "
            f"Conflicting examples: {examples}."
        )
    return (
        "Two or more attributes have semantic overlap and must be revised. Rewrite descriptions and "
        "examples so each attribute covers distinct ground. Specifics: " + " ".join(parts)
    )
