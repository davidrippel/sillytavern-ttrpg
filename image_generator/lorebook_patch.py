"""Patch a campaign's lorebook with NPC image-gen prompts.

After `image_generator` writes `npc_images/index.json`, this module embeds each
prompt as a disabled lorebook entry (one per NPC) so the SillyTavern extension
can surface it through the existing world-info read path. Entries are tagged in
the `comment` field as ``NPC Image Prompt: <name>`` and have empty keys with
``disable: true`` so they never inject into the LLM context.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


IMAGE_PROMPT_COMMENT_PREFIX = "NPC Image Prompt: "


class LorebookPatchError(RuntimeError):
    """Raised when the lorebook can't be patched."""


def _build_entry(uid: int, display_index: int, name: str, prompt: str) -> dict[str, Any]:
    """Mirror the entry shape used by campaign_generator.lorebook._entry."""
    return {
        "uid": uid,
        "key": [],
        "keysecondary": [],
        "comment": f"{IMAGE_PROMPT_COMMENT_PREFIX}{name}",
        "content": prompt,
        "constant": False,
        "vectorized": False,
        "selective": False,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": 100,
        "position": 0,
        "disable": True,
        "excludeRecursion": True,
        "preventRecursion": True,
        "delayUntilRecursion": 0,
        "probability": 0,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": 0,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 0,
        "sticky": None,
        "cooldown": None,
        "delay": None,
        "displayIndex": display_index,
    }


def _find_lorebook_file(campaign_dir: Path) -> Path:
    """Return the campaign's lorebook JSON file (the one with an `entries` dict).

    Skips known non-lorebook artifacts (sample_characters.json). If multiple
    candidates exist, picks the largest one — campaign generator produces a
    single lorebook per campaign, so collisions are not expected in practice.
    """
    skip = {"sample_characters.json"}
    candidates: list[tuple[int, Path]] = []
    for path in sorted(campaign_dir.glob("*.json")):
        if path.name in skip:
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("entries"), dict):
            candidates.append((path.stat().st_size, path))
    if not candidates:
        raise LorebookPatchError(
            f"no lorebook JSON file (with `entries`) found in {campaign_dir}"
        )
    candidates.sort(reverse=True)
    return candidates[0][1]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def patch_lorebook_with_prompts(campaign_dir: Path) -> tuple[Path, int, int]:
    """Embed image-gen prompts from npc_images/index.json into the campaign's lorebook.

    Returns ``(lorebook_path, added, updated)``. Idempotent: re-running updates
    the ``content`` of existing entries in place rather than duplicating.
    """
    campaign_dir = Path(campaign_dir)
    index_path = campaign_dir / "npc_images" / "index.json"
    if not index_path.exists():
        raise LorebookPatchError(f"no portrait index at {index_path}")

    with index_path.open("r", encoding="utf-8") as handle:
        index = json.load(handle)
    if not isinstance(index, dict) or not index:
        return (_find_lorebook_file(campaign_dir), 0, 0)

    lorebook_path = _find_lorebook_file(campaign_dir)
    with lorebook_path.open("r", encoding="utf-8") as handle:
        lorebook = json.load(handle)

    entries: dict[str, Any] = lorebook.setdefault("entries", {})

    # Map existing image-prompt entries by NPC name for in-place updates.
    existing_by_name: dict[str, str] = {}
    max_uid = 0
    max_display_index = -1
    for entry_id, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        uid = entry.get("uid")
        if isinstance(uid, int) and uid > max_uid:
            max_uid = uid
        di = entry.get("displayIndex")
        if isinstance(di, int) and di > max_display_index:
            max_display_index = di
        comment = str(entry.get("comment") or "")
        if comment.startswith(IMAGE_PROMPT_COMMENT_PREFIX):
            name = comment[len(IMAGE_PROMPT_COMMENT_PREFIX):]
            existing_by_name[name] = entry_id

    added = 0
    updated = 0
    next_uid = max_uid + 1
    next_display_index = max_display_index + 1

    for name, record in index.items():
        if not isinstance(record, dict):
            continue
        prompt = str(record.get("prompt") or "").strip()
        if not prompt:
            continue
        if name in existing_by_name:
            entry = entries[existing_by_name[name]]
            if entry.get("content") != prompt:
                entry["content"] = prompt
                updated += 1
            entry["disable"] = True
        else:
            entry = _build_entry(next_uid, next_display_index, name, prompt)
            entries[str(next_uid)] = entry
            next_uid += 1
            next_display_index += 1
            added += 1

    _atomic_write_json(lorebook_path, lorebook)
    return (lorebook_path, added, updated)
