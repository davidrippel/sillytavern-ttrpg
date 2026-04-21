from pathlib import Path

import json
import yaml

from campaign_generator.llm import ReplayLLMClient
from campaign_generator.paths import build_auto_campaign_dir_name, resolve_output_path
from campaign_generator.pipeline import run_pipeline
from campaign_generator.placeholders import sanitize_text


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
    assert (output_dir / "partials" / "opening_hook.partial.txt").exists()
    assert (output_dir / "partials" / "initial_authors_note.partial.txt").exists()
    assert (output_dir / "partials" / "npcs.partial.json").exists()
    assert (output_dir / "partials" / "locations.partial.json").exists()
    assert (output_dir / "partials" / "clue_chains.partial.json").exists()
    plot_payload = json.loads((output_dir / "stages" / "plot_skeleton.json").read_text(encoding="utf-8"))
    locations_payload = json.loads((output_dir / "stages" / "locations.json").read_text(encoding="utf-8"))
    clues_payload = json.loads((output_dir / "stages" / "clue_chains.json").read_text(encoding="utf-8"))
    assert plot_payload["acts"][0]["beats"][0]["id"] == "act1_beat1"
    assert plot_payload["acts"][0]["beats"][0]["rendered"] == "1.1 Recover the ferryman's satchel"
    assert "plot_beats_detail" in locations_payload["locations"][0]
    assert clues_payload["clues"][0]["supports_beats_detail"][0]["id"] == "act1_beat1"


def test_protagonist_name_sanitizer_uses_user_placeholder():
    text = "Valeria meets the protagonist. Valeria's mentor warns the player character."
    sanitized = sanitize_text(text, protagonist_names={"Valeria"})
    assert sanitized == "{{user}} meets {{user}}. {{user}}'s mentor warns {{user}}."


def test_auto_campaign_dir_name_is_predictable():
    from datetime import datetime

    actual = build_auto_campaign_dir_name(
        pack_name="symbaroum_dark_fantasy",
        seed_path="my_seed.yaml",
        now=datetime(2026, 4, 21, 15, 30, 0),
    )
    assert actual == "20260421_153000_symbaroum_dark_fantasy_my_seed"


def test_output_defaults_to_campaigns_base_dir(monkeypatch, tmp_path):
    from datetime import datetime

    monkeypatch.setenv("CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR", str(tmp_path / "campaigns"))
    resolved = resolve_output_path(
        output=None,
        pack_name="symbaroum_dark_fantasy",
        seed_path="my_seed.yaml",
        now=datetime(2026, 4, 21, 15, 30, 0),
    )
    assert resolved == (tmp_path / "campaigns" / "20260421_153000_symbaroum_dark_fantasy_my_seed").resolve()


def test_relative_output_uses_campaigns_base_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR", str(tmp_path / "campaigns"))
    resolved = resolve_output_path(
        output="my_first_campaign",
        pack_name="symbaroum_dark_fantasy",
        seed_path="my_seed.yaml",
    )
    assert resolved == (tmp_path / "campaigns" / "my_first_campaign").resolve()


def test_output_name_gets_incremented_when_taken(monkeypatch, tmp_path):
    campaigns_dir = tmp_path / "campaigns"
    existing = campaigns_dir / "my_first_campaign"
    existing.mkdir(parents=True)
    monkeypatch.setenv("CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR", str(campaigns_dir))
    resolved = resolve_output_path(
        output="my_first_campaign",
        pack_name="symbaroum_dark_fantasy",
        seed_path="my_seed.yaml",
    )
    assert resolved == (campaigns_dir / "my_first_campaign_1").resolve()


def test_auto_output_gets_incremented_when_taken(monkeypatch, tmp_path):
    from datetime import datetime

    campaigns_dir = tmp_path / "campaigns"
    existing = campaigns_dir / "20260421_153000_symbaroum_dark_fantasy_my_seed"
    existing.mkdir(parents=True)
    monkeypatch.setenv("CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR", str(campaigns_dir))
    resolved = resolve_output_path(
        output=None,
        pack_name="symbaroum_dark_fantasy",
        seed_path="my_seed.yaml",
        now=datetime(2026, 4, 21, 15, 30, 0),
    )
    assert resolved == (campaigns_dir / "20260421_153000_symbaroum_dark_fantasy_my_seed_1").resolve()
