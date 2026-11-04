"""Watcher agent facade over deterministic incident detection."""
from watcher.main import run_once


class WatcherAgent:
    def run(self):
        return run_once()
