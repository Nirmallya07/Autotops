"""Watcher agent facade over deterministic incident detection."""
import sys
from pathlib import Path

class WatcherAgent:
    def run(self):
        watcher_dir = str(Path(__file__).resolve().parents[3] / "watcher")
        if watcher_dir not in sys.path:
            sys.path.insert(0, watcher_dir)
        from main import run_once
        return run_once()
