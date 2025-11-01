"""Utilities for handling narrator voice selection."""

from __future__ import annotations

import random
from typing import Any, Iterable, List, Optional, Sequence, Tuple

DEFAULT_VOICE_POOL: Sequence[str] = (
    "Aoede",
    "Charon",
    "Kore",
    "Puck",
    "Achird",
)


def _flatten_voice_values(raw: Any) -> List[str]:
    """Turn a raw config value into a clean list of voice names."""
    if raw is None:
        return []
    if isinstance(raw, str):
        candidates = [part.strip() for part in raw.split(",")]
        return [voice for voice in candidates if voice]
    if isinstance(raw, (list, tuple, set)):
        flattened: List[str] = []
        for item in raw:
            flattened.extend(_flatten_voice_values(item))
        return flattened
    return []


def choose_narrator_voice(
    basic_cfg: dict,
    rng: Optional[random.Random] = None,
) -> Tuple[str, List[str], bool]:
    """Resolve the narrator voice based on configuration.

    Returns:
        Tuple containing the selected voice, the candidate pool that was used
        when randomization is enabled (empty list if not), and a boolean
        indicating whether random selection was applied.
    """

    rng = rng or random

    random_markers = {
        True,
        "random",
        "Random",
        "RANDOM",
    }

    raw_voice = basic_cfg.get("narrator_voice", "Aoede")
    voice_mode = str(basic_cfg.get("narrator_voice_mode", "") or "").strip().lower()
    random_flag = bool(basic_cfg.get("narrator_voice_random", False))

    if isinstance(raw_voice, list):
        candidate_pool = _flatten_voice_values(raw_voice)
        random_flag = True
    else:
        candidate_pool = []
        if isinstance(raw_voice, str) and raw_voice.strip() in random_markers:
            random_flag = True
        elif voice_mode == "random":
            random_flag = True

    if random_flag:
        candidate_pool.extend(_flatten_voice_values(basic_cfg.get("narrator_voice_candidates")))
        candidate_pool.extend(_flatten_voice_values(basic_cfg.get("narrator_voice_choices")))

        if isinstance(raw_voice, str) and raw_voice.strip() and raw_voice.strip().lower() != "random":
            candidate_pool.append(raw_voice.strip())

        if not candidate_pool:
            candidate_pool.extend(DEFAULT_VOICE_POOL)

        # Remove duplicates while preserving insertion order
        seen = set()
        deduped: List[str] = []
        for voice in candidate_pool:
            if voice not in seen:
                seen.add(voice)
                deduped.append(voice)
        candidate_pool = deduped

        if not candidate_pool:
            raise ValueError("narrator_voice 隨機模式需要至少一個可用的聲線候選項目")

        selected_voice = rng.choice(candidate_pool)
        return selected_voice, candidate_pool, True

    # Fixed voice mode
    if isinstance(raw_voice, str) and raw_voice.strip():
        return raw_voice.strip(), [], False

    return "Aoede", [], False
