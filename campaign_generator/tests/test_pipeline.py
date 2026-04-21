from pathlib import Path

import json
import yaml

from campaign_generator.llm import ReplayLLMClient
from campaign_generator.paths import build_auto_campaign_dir_name, resolve_output_path
from campaign_generator.pipeline import run_pipeline
from campaign_generator.pipeline import _format_duration
from campaign_generator.pipeline import _format_usage_summary
from campaign_generator.placeholders import sanitize_text
from campaign_generator.schemas import PlotSkeleton
from campaign_generator.stages.npcs import _extract_required_npc_names


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


def test_required_npc_names_include_plot_critical_named_characters():
    plot = PlotSkeleton.model_validate(
        {
            "acts": [
                {
                    "title": "Act One",
                    "goal": "Reach the excavation.",
                    "beats": [
                        "{{user}} meets Sister Anya in town.",
                        "{{user}} is hired by Lady Valeria Orsin.",
                        "{{user}} clashes with Foreman Borin at the dig.",
                    ],
                },
                {
                    "title": "Act Two",
                    "goal": "Uncover the truth.",
                    "beats": [
                        "Kaelen's notes point deeper underground.",
                        "The corruption spreads through camp.",
                        "Brother Tarvos guards the vault.",
                    ],
                },
                {
                    "title": "Act Three",
                    "goal": "Survive the awakening.",
                    "beats": [
                        "The chamber opens.",
                        "The Church intervenes.",
                        "The forest answers.",
                    ],
                },
            ],
            "main_antagonist": {
                "name": "Lady Valeria Orsin",
                "motivation": "Claim the Heartwood Seed.",
                "secret": "She ordered Foreman Borin to keep digging.",
                "relationship_to_protagonist": "{{user}} is a useful outsider.",
            },
            "driving_mystery": "Why did Kaelen vanish beneath the dig?",
            "hook": "A missing mentor and a sealed vault pull {{user}} into the frontier.",
            "escalation_arc": "What begins as a local disappearance becomes a struggle over a buried intelligence.",
        }
    )

    required_names = _extract_required_npc_names(plot)

    assert "Lady Valeria Orsin" in required_names
    assert "Sister Anya" in required_names
    assert "Foreman Borin" in required_names
    assert "Brother Tarvos" in required_names


def test_duration_formatter_uses_minutes_after_sixty_seconds():
    assert _format_duration(59.9) == "59.9s"
    assert _format_duration(60.0) == "1.0m"
    assert _format_duration(125.2) == "2.1m"


def test_replay_client_tracks_call_counts_without_usage_data():
    client = ReplayLLMClient({"premise": [{"paragraphs": ["a", "b"], "central_conflict": "x", "tone_statement": "y", "thematic_pillars": ["1", "2", "3"]}]})

    client.complete(
        stage_name="premise",
        system_prompt="system",
        user_prompt="user",
        model="test-model",
        temperature=0.0,
    )

    usage = client.usage_snapshot()
    assert usage.calls == 1
    assert usage.total_tokens == 0
    assert usage.cost == 0.0


def test_usage_summary_formatter_includes_calls_tokens_and_cost():
    client = ReplayLLMClient({})
    client._record_usage({"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150, "cost": 0.0125})
    assert _format_usage_summary(client.usage_snapshot()) == "1 call, 150 tokens, 0.0125 credits"
