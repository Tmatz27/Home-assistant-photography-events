"""Dependency-free container for explicitly retired historical tests."""
from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[2] / "custom_components/photography_events"))
