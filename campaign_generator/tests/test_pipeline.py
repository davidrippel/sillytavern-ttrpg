from pathlib import Path

import yaml

from campaign_generator.llm import ReplayLLMClient
from campaign_generator.pipeline import run_pipeline


def test_pipeline_replay_writes_outputs(tmp_path):
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(
        yaml.safe_dump(
            {
                "genre": "symbaroum_dark_fantasy",
                "campaign_pitch": "A ferryman's death opens a path into a buried conspiracy.",
                "num_npcs": 6,
                "num_locations": 5,
                "branch_points": 4,
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "campaign"
    client = ReplayLLMClient.from_fixture_dir("tests/fixtures/canned_llm_responses")
    run_pipeline(
        genre_path="genres/symbaroum_dark_fantasy",
        seed_path=seed_path,
        output_path=output_dir,
        llm_client=client,
        dry_run=True,
    )

    assert (output_dir / "opening_hook.txt").exists()
    assert (output_dir / "initial_authors_note.txt").exists()
    assert (output_dir / "campaign_lorebook.json").exists()
    assert (output_dir / "spoilers" / "full_campaign.md").exists()
    assert (output_dir / "stages" / "premise.json").exists()
    assert (output_dir / "stages" / "branches.json").exists()
    assert (output_dir / "stages" / "calls.jsonl").exists()
    assert (output_dir / "stages" / "validation_log.txt").exists()
