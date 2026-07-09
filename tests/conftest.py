"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_user_data_dir(tmp_path: Path) -> Path:
    """Create a fake Chrome 'User Data' directory with several profiles."""
    root = tmp_path / "User Data"
    root.mkdir()

    def make_profile(dir_name: str, display: str) -> None:
        pdir = root / dir_name
        pdir.mkdir()
        (pdir / "Preferences").write_text(
            json.dumps({"profile": {"name": display}}), encoding="utf-8"
        )

    make_profile("Default", "Personal")
    make_profile("Profile 1", "Work")
    make_profile("Profile 2", "Streaming")
    make_profile("System Profile", "System")  # should be excluded by default
    # A non-profile directory that must be ignored.
    (root / "ShaderCache").mkdir()
    return root


@pytest.fixture
def fake_chrome_binary(tmp_path: Path) -> Path:
    """Create a fake executable that stands in for chrome.exe."""
    binary = tmp_path / "chrome-bin"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary
