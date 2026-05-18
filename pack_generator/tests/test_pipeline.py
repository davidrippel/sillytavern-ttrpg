"""Pipeline-level smoke tests for the v2 pack generator.

The full LLM-replay pipeline test from v1 has been retired with the v1
schema. A new replay-fixture set needs to be captured against a real
LLM run before that test can be restored. Until then this module
covers what can be tested without LLM calls: the pipeline's basic
plumbing and its refusal to overwrite an existing pack directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.llm import ReplayLLMClient
from pack_generator.pipeline import run_pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_BRIEF = REPO_ROOT / "pack_generator" / "examples" / "space_opera_brief.yaml"


def test_pipeline_refuses_non_empty_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    (output_dir / "stuff.txt").write_text("hello", encoding="utf-8")

    # We never actually reach the LLM client because the directory check
    # fails first; a replay client with no fixtures suffices.
    client = ReplayLLMClient(responses={})
    with pytest.raises(ValueError, match="not empty"):
        run_pipeline(
            brief_path=EXAMPLE_BRIEF,
            output_path=output_dir,
            stages="all",
            llm_client=client,
        )


@pytest.mark.skip(
    reason=(
        "v2 replay fixtures not yet captured. Capture a real LLM run against the v2 "
        "pipeline (`python -m pack_generator --brief examples/space_opera_brief.yaml ...`) "
        "and re-record fixtures under tests/fixtures/canned_llm_responses/space_opera/. "
        "Then restore this test to exercise the full pipeline offline."
    )
)
def test_pipeline_replays_to_valid_pack(tmp_path: Path) -> None:  # pragma: no cover
    raise AssertionError("see skip reason")
