# -*- coding: utf-8 -*-
"""
SAMAY module entrypoint.
Run as `python3 -m samay.modules` to print a summary of the supported modules.
"""

import sys
import os
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, str(Path(HERE).parent.parent))
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, os.path.join(Path(HERE).parent.parent, "vendor"))

MODULES = {
    "clock": "⏰ Clock — analog + digital, live weather widget",
    "countdown": "⏳ Countdown — HH:MM:SS picker, circular progress, start/pause/reset",
    "stopwatch": "⏱️ Stopwatch — laps, max 100, export ~/.samay/laps.csv",
    "world": "🌍 World Clock — preset cities + search-add, saved ~/.samay/world.json",
    "alarm": "⏰ Alarm — time/repeat/sound/label, checked every second",
    "calendar": "📅 Calendar — monthly grid, Indian holidays, cached festivals",
}

def main() -> int:
    print("SAMAY modules")
    for key, desc in MODULES.items():
        print(f"  {key:>10}  {desc}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
