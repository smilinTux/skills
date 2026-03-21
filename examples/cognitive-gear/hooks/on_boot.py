#!/usr/bin/env python3
"""
On-boot hook: Set default cognitive gear to CRUISE.
"""

import json
from pathlib import Path
import os

STATE_DIR = Path(os.environ.get("SKCAPSTONE_DIR", Path.home() / ".skcapstone"))
STATE_FILE = STATE_DIR / "cognitive-gear.json"


def set_default_gear() -> dict:
    """
    Ensure cognitive gear state exists with CRUISE as default.
    Does NOT override if already set (preserves user preference across restarts).
    """
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            return {
                "action": "preserved",
                "gear": state.get("current_gear", "cruise"),
                "message": f"Gear already set: {state.get('current_gear', 'cruise')}",
            }
        except (json.JSONDecodeError, IOError):
            pass

    # First boot — initialize to cruise
    state = {
        "current_gear": "cruise",
        "switched_at": None,
        "switches": 0,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    return {
        "action": "initialized",
        "gear": "cruise",
        "message": "🚗 Default gear set to CRUISE",
    }


if __name__ == "__main__":
    result = set_default_gear()
    print(json.dumps(result, indent=2))
