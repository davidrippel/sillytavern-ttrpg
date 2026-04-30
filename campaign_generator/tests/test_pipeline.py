from pathlib import Path

import json
import yaml

from campaign_generator.llm import UsageStats
from campaign_generator.llm import ReplayLLMClient
from campaign_generator.paths import build_auto_campaign_dir_name, resolve_output_path
from campaign_generator.pipeline import run_pipeline
from campaign_generator.pipeline import _format_duration
from campaign_generator.pipeline import _format_usage_summary
from campaign_generator.placeholders import sanitize_text
from campaign_generator.schemas import Clue, ClueGraph, ClueTarget, LocationCatalog, NPCRoster, PlotSkeleton
from campaign_generator.stages.npcs import _extract_required_npc_names
from campaign_generator.stages.clue_chains import _build_hybrid_fallback_clue_graph, build_clue_skeleton
from campaign_generator.stages.opening_hook import _autofix_casing, _detect_issues
from campaign_generator.validation import validate_clue_graph


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
    lorebook_files = [
        path for path in output_dir.glob("*.json") if path.name != "sample_characters.json"
    ]
    assert len(lorebook_files) == 1, f"expected one lorebook json, got {lorebook_files}"
    assert lorebook_files[0].name == "the_ferryman_s_satchel.json"
    assert (output_dir / "spoilers" / "full_campaign.md").exists()
    assert (output_dir / "stages" / "premise.json").exists()
    assert (output_dir / "stages" / "branches.json").exists()
    assert (output_dir / "stages" / "sample_characters.json").exists()
    assert (output_dir / "sample_characters.json").exists()
    samples_payload = json.loads((output_dir / "sample_characters.json").read_text(encoding="utf-8"))
    assert samples_payload["pack_name"] == "symbaroum_dark_fantasy"
    assert len(samples_payload["characters"]) == 3
    assert samples_payload["characters"][0]["story"]["strengths"]
    assert samples_payload["characters"][0]["pack"]["attributes"]
    lorebook_payload = json.loads(lorebook_files[0].read_text(encoding="utf-8"))
    assert any(
        entry.get("comment") == "Sample Characters"
        for entry in lorebook_payload["entries"].values()
    )
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
    assert _format_usage_summary(
        UsageStats(calls=1, prompt_tokens=120, completion_tokens=30, total_tokens=150, cost=0.0125)
    ) == "1 call, 150 tokens, 0.0125 credits"


def test_hybrid_clue_fallback_preserves_valid_clues_and_synthesizes_missing_slots():
    plot = PlotSkeleton.model_validate(
        {
            "acts": [
                {
                    "title": "Act One",
                    "goal": "Start the investigation.",
                    "beats": [
                        "Find the hidden ledger.",
                        "Reach the ruined tower.",
                        "Confront the keeper.",
                    ],
                },
                {
                    "title": "Act Two",
                    "goal": "Push deeper.",
                    "beats": [
                        "Follow the ritual marks.",
                        "Break the sealed door.",
                        "Learn the patron's bargain.",
                    ],
                },
                {
                    "title": "Act Three",
                    "goal": "End the threat.",
                    "beats": [
                        "Survive the awakening.",
                        "Choose who takes the relic.",
                        "Escape the collapse.",
                    ],
                },
            ],
            "main_antagonist": {
                "name": "Ivara Kelm",
                "motivation": "Open the ruin.",
                "secret": "She killed the courier.",
                "relationship_to_protagonist": "{{user}} is an obstacle.",
            },
            "driving_mystery": "Who is feeding the ruin and why?",
            "hook": "A dead courier leaves a trail.",
            "escalation_arc": "A murder becomes a frontier conspiracy.",
        }
    )
    npcs = NPCRoster.model_validate(
        {
            "npcs": [
                {
                    "name": "Maelin Voss",
                    "role": "Factor",
                    "physical_description": "Lean and watchful.",
                    "speaking_style": "Measured.",
                    "motivation": "Protect the guild.",
                    "secret": "He signed false ledgers.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
                {
                    "name": "Sister Orsa",
                    "role": "Priest",
                    "physical_description": "Mud-stained robes.",
                    "speaking_style": "Blunt.",
                    "motivation": "Contain the ruin.",
                    "secret": "She hid an old report.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
                {
                    "name": "Dren Halvek",
                    "role": "Witness",
                    "physical_description": "Thin and anxious.",
                    "speaking_style": "Fast.",
                    "motivation": "Stay alive.",
                    "secret": "He touched the relic first.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
                {
                    "name": "Ivara Kelm",
                    "role": "Surveyor",
                    "physical_description": "Tall and pale.",
                    "speaking_style": "Patient.",
                    "motivation": "Open the ruin.",
                    "secret": "She ordered the killing.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
                {
                    "name": "Odel Fen",
                    "role": "Guide",
                    "physical_description": "Heavy boots and a patched cloak.",
                    "speaking_style": "Suspicious.",
                    "motivation": "Protect the road.",
                    "secret": "He once ferried contraband.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
                {
                    "name": "Archivist Serel",
                    "role": "Scholar",
                    "physical_description": "Ink-stained sleeves.",
                    "speaking_style": "Precise.",
                    "motivation": "Decode the ledger.",
                    "secret": "Serel marked the dig site.",
                    "relationships": [],
                    "abilities": [],
                    "act_presence": [],
                },
            ]
        }
    )
    locations = LocationCatalog.model_validate(
        {
            "locations": [
                {
                    "name": "Sunken Watchtower",
                    "type": "Ruin",
                    "sensory_description": {"sight": "Black stone.", "sound": "Wind in broken arches."},
                    "notable_features": ["Collapsed stairs."],
                    "hidden_elements": ["A sealed crawlspace."],
                    "npc_names": ["Maelin Voss"],
                    "plot_beats": ["act1_beat1"],
                },
                {
                    "name": "Frontier Waystation",
                    "type": "Roadhouse",
                    "sensory_description": {"sight": "Mud and lanternlight.", "smell": "Wet wool and ash."},
                    "notable_features": ["A locked office."],
                    "hidden_elements": ["Smuggler marks under the eaves."],
                    "npc_names": ["Maelin Voss"],
                    "plot_beats": ["act1_beat2"],
                },
                {
                    "name": "Old Quarry",
                    "type": "Excavation",
                    "sensory_description": {"sight": "Broken cranes.", "sound": "Loose stone rattling."},
                    "notable_features": ["A flooded trench."],
                    "hidden_elements": ["An idol beneath the silt."],
                    "npc_names": ["Maelin Voss"],
                    "plot_beats": ["act1_beat3"],
                },
                {
                    "name": "Ritual Cellar",
                    "type": "Vault",
                    "sensory_description": {"sight": "Rune-scratched walls.", "smell": "Wax and damp clay."},
                    "notable_features": ["A black altar."],
                    "hidden_elements": ["A hidden trapdoor."],
                    "npc_names": ["Maelin Voss"],
                    "plot_beats": ["act2_beat1"],
                },
                {
                    "name": "Collapsed Shrine",
                    "type": "Shrine",
                    "sensory_description": {"sight": "Fractured idols.", "sound": "Dripping water."},
                    "notable_features": ["A cracked bell."],
                    "hidden_elements": ["A blood-marked niche."],
                    "npc_names": ["Maelin Voss"],
                    "plot_beats": ["act2_beat2"],
                },
            ]
        }
    )
    candidate_graph = ClueGraph.model_validate(
        {
            "entry_clue_ids": ["kept_clue", "bad_clue"],
            "clues": [
                {
                    "id": "kept_clue",
                    "found_at_type": "location",
                    "found_at": "Sunken Watchtower",
                    "reveals": "A waterlogged page names the missing courier.",
                    "points_to": [{"type": "beat", "value": "act1_beat1"}],
                    "supports_beats": ["act1_beat1"],
                },
                {
                    "id": "bad_clue",
                    "found_at_type": "npc",
                    "found_at": "Invented Smuggler",
                    "reveals": "This clue should be dropped.",
                    "points_to": [{"type": "beat", "value": "act1_beat2"}],
                    "supports_beats": ["act1_beat2"],
                },
                {
                    "id": "bad_clue_2",
                    "found_at_type": "location",
                    "found_at": "Invented Hideout",
                    "reveals": "This clue should also be dropped.",
                    "points_to": [{"type": "beat", "value": "act1_beat3"}],
                    "supports_beats": ["act1_beat3"],
                },
                {
                    "id": "bad_clue_3",
                    "found_at_type": "npc",
                    "found_at": "Invented Priest",
                    "reveals": "Another invalid clue.",
                    "points_to": [{"type": "beat", "value": "act2_beat1"}],
                    "supports_beats": ["act2_beat1"],
                },
            ],
        }
    )

    repaired_graph, preserved_count, synthetic_count = _build_hybrid_fallback_clue_graph(
        plot=plot,
        npcs=npcs,
        locations=locations,
        candidate_graph=candidate_graph,
    )

    errors = validate_clue_graph(plot, npcs, locations, repaired_graph)

    assert preserved_count == 1
    assert synthetic_count >= 1
    assert not errors
    kept = next(clue for clue in repaired_graph.clues if clue.id == "kept_clue")
    assert kept.reveals == "A waterlogged page names the missing courier."
    assert all(clue.id != "bad_clue" for clue in repaired_graph.clues)


def _ferryman_plot_npcs_locations():
    plot = PlotSkeleton.model_validate(
        json.loads(Path("tests/fixtures/canned_llm_responses/plot_skeleton.json").read_text())
    )
    npcs = NPCRoster.model_validate(
        {"npcs": [json.loads(Path(f"tests/fixtures/canned_llm_responses/npc_{i}.json").read_text()) for i in range(1, 7)]}
    )
    locations = LocationCatalog.model_validate(
        {"locations": [json.loads(Path(f"tests/fixtures/canned_llm_responses/location_{i}.json").read_text()) for i in range(1, 6)]}
    )
    return plot, npcs, locations


def test_build_clue_skeleton_produces_valid_graph_without_llm():
    plot, npcs, locations = _ferryman_plot_npcs_locations()
    skeleton = build_clue_skeleton(plot=plot, npcs=npcs, locations=locations)
    errors = validate_clue_graph(plot, npcs, locations, skeleton)
    assert errors == []
    beat_ids = set(plot.beat_id_to_text())
    for beat_id in beat_ids:
        supports = sum(1 for clue in skeleton.clues for t in clue.points_to if t.type == "beat" and t.value == beat_id)
        assert supports >= 2, f"beat {beat_id} should be supported by >= 2 clues, got {supports}"


def test_opening_hook_post_validation_flags_lowercase_proper_nouns():
    bad = "you arrive at the threshold of thistle hold with a raven delivers the news."
    issues = _detect_issues(bad, {"Thistle Hold"})
    assert any("Thistle Hold" in issue for issue in issues)
    assert any("with a raven delivers" in issue for issue in issues)


def test_opening_hook_autofix_corrects_casing_only():
    bad = "you arrive at the threshold of thistle hold and the storm thickens around you tonight."
    fixed = _autofix_casing(bad, {"Thistle Hold"})
    assert "Thistle Hold" in fixed
    assert "thistle hold" not in fixed
