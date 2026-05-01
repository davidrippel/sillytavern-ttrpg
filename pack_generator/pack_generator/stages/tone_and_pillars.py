from __future__ import annotations

import re

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import ToneAndPillars
from ._common import call_llm

PROMPT_FILE = "01_tone_and_pillars.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ToneAndPillars:
    context = {
        "brief": brief.model_dump(exclude_none=True),
    }
    draft = call_llm(
        client=client,
        stage_name="tone_and_pillars",
        system_prompt=system_prompt,
        context=context,
        schema=ToneAndPillars,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
    _validate_brief_avoid_honored(draft, brief, validation_log)
    return draft


_AVOID_NORMALIZE = re.compile(r"[^a-z0-9]+")


def _normalize_avoid_term(term: str) -> str:
    return _AVOID_NORMALIZE.sub("", term.lower())


def _term_present_in_avoid_list(term: str, avoid_list: list[str]) -> bool:
    needle = _normalize_avoid_term(term)
    if not needle:
        return True
    for entry in avoid_list:
        if needle in _normalize_avoid_term(entry):
            return True
    return False


def _validate_brief_avoid_honored(
    draft: ToneAndPillars,
    brief: GenreBrief,
    validation_log: ValidationLog,
) -> None:
    if not brief.content_to_avoid:
        return
    missing: list[str] = []
    for term in brief.content_to_avoid:
        if not _term_present_in_avoid_list(term, draft.content_to_avoid):
            missing.append(term)
    if missing:
        message = (
            f"brief.content_to_avoid items missing from generated content_to_avoid: {missing}; "
            f"every avoid term in the brief must be reflected in the pack's content_to_avoid"
        )
        validation_log.write(f"[tone_and_pillars brief-avoid] {message}")
        raise ValueError(message)
