#!/usr/bin/env python3
"""
Cognitive Gear — Model + Memory depth switching for sovereign agents.

Three modes:
  SPRINT  — Fast model, keyword memory only
  CRUISE  — Deep model, tiered memory (default)
  DEEP    — Deep model + thinking, exhaustive memory search
"""

import json
import os
from pathlib import Path
from datetime import datetime

# State file for current gear
STATE_DIR = Path(os.environ.get("SKCAPSTONE_DIR", Path.home() / ".skcapstone"))
STATE_FILE = STATE_DIR / "cognitive-gear.json"

GEARS = {
    "sprint": {
        "name": "SPRINT",
        "emoji": "🏎️",
        "description": "Fast execution — quick answers, minimal memory",
        "model_alias": "claude",       # sonnet-class
        "model_fallback": "kimi",      # kimi-k2 as alt
        "thinking": "off",
        "memory_layers": ["skmemory_search"],
        "cost_tier": "low",
    },
    "cruise": {
        "name": "CRUISE",
        "emoji": "🚗",
        "description": "Balanced work — full reasoning, tiered memory",
        "model_alias": "opus",         # opus-class
        "model_fallback": "claude",    # sonnet as fallback
        "thinking": "adaptive",
        "memory_layers": ["skmemory_search", "skmemory_context"],
        "cost_tier": "moderate",
    },
    "deep": {
        "name": "DEEP DIVE",
        "emoji": "🔬",
        "description": "Research & analysis — all memory layers, extended thinking",
        "model_alias": "opus",         # opus-class
        "model_fallback": "claude",    # sonnet as fallback
        "thinking": "on",
        "memory_layers": [
            "skmemory_search",
            "skmemory_search_deep",
            "skmemory_context",
            "memory_search",
            "memory_get",
            "notion",
            "nextcloud",
        ],
        "cost_tier": "high",
    },
}

DEFAULT_GEAR = "cruise"


def _load_state() -> dict:
    """Load current gear state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"current_gear": DEFAULT_GEAR, "switched_at": None, "switches": 0}


def _save_state(state: dict) -> None:
    """Persist gear state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def gear_switch(mode: str) -> dict:
    """
    Switch cognitive gear.

    Args:
        mode: Target gear — sprint, cruise, or deep

    Returns:
        Dict with new gear config and model to set.
    """
    mode = mode.lower().strip()

    # Normalize aliases
    aliases = {
        "fast": "sprint",
        "quick": "sprint",
        "normal": "cruise",
        "balanced": "cruise",
        "research": "deep",
        "deep_dive": "deep",
        "deepdive": "deep",
        "think": "deep",
    }
    mode = aliases.get(mode, mode)

    if mode not in GEARS:
        return {
            "error": f"Unknown gear: {mode}",
            "valid_gears": list(GEARS.keys()),
            "aliases": aliases,
        }

    gear = GEARS[mode]
    state = _load_state()
    old_gear = state.get("current_gear", DEFAULT_GEAR)

    state["current_gear"] = mode
    state["switched_at"] = datetime.utcnow().isoformat()
    state["switches"] = state.get("switches", 0) + 1
    state["previous_gear"] = old_gear
    _save_state(state)

    return {
        "gear": mode,
        "name": gear["name"],
        "emoji": gear["emoji"],
        "description": gear["description"],
        "model_alias": gear["model_alias"],
        "model_fallback": gear["model_fallback"],
        "thinking": gear["thinking"],
        "memory_layers": gear["memory_layers"],
        "cost_tier": gear["cost_tier"],
        "previous_gear": old_gear,
        "action_required": {
            "set_model": f"session_status(model=\"{gear['model_alias']}\")",
            "set_thinking": gear["thinking"],
            "memory_protocol": gear["memory_layers"],
        },
        "message": f"{gear['emoji']} Shifted to {gear['name']} — {gear['description']}",
    }


def gear_status() -> dict:
    """
    Show current cognitive gear and its configuration.

    Returns:
        Dict with current gear info.
    """
    state = _load_state()
    mode = state.get("current_gear", DEFAULT_GEAR)
    gear = GEARS.get(mode, GEARS[DEFAULT_GEAR])

    return {
        "current_gear": mode,
        "name": gear["name"],
        "emoji": gear["emoji"],
        "description": gear["description"],
        "model_alias": gear["model_alias"],
        "thinking": gear["thinking"],
        "memory_layers": gear["memory_layers"],
        "cost_tier": gear["cost_tier"],
        "switched_at": state.get("switched_at"),
        "total_switches": state.get("switches", 0),
        "available_gears": {k: f"{v['emoji']} {v['name']}" for k, v in GEARS.items()},
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        result = gear_status()
    elif sys.argv[1] == "status":
        result = gear_status()
    else:
        result = gear_switch(sys.argv[1])

    print(json.dumps(result, indent=2))
