"""Unit tests for profile discovery and selection."""

from __future__ import annotations

from pathlib import Path

from automation.profile_manager import ProfileManager


def test_discover_finds_valid_profiles(fake_user_data_dir: Path) -> None:
    manager = ProfileManager(fake_user_data_dir)
    profiles = manager.discover()
    names = [p.directory for p in profiles]
    # Only Default / Profile N are real user profiles; System Profile and
    # ShaderCache are correctly ignored.
    assert names == ["Default", "Profile 1", "Profile 2"]
    assert "ShaderCache" not in names
    assert "System Profile" not in names


def test_display_name_from_preferences(fake_user_data_dir: Path) -> None:
    manager = ProfileManager(fake_user_data_dir)
    profiles = {p.directory: p for p in manager.discover()}
    assert profiles["Default"].display_name == "Personal"
    assert profiles["Profile 1"].display_name == "Work"


def test_select_all_excludes_system(fake_user_data_dir: Path) -> None:
    manager = ProfileManager(fake_user_data_dir)
    selected = manager.select(include=[], exclude=["System Profile"])
    names = [p.directory for p in selected]
    assert names == ["Default", "Profile 1", "Profile 2"]


def test_select_specific_profiles(fake_user_data_dir: Path) -> None:
    manager = ProfileManager(fake_user_data_dir)
    selected = manager.select(include=["Profile 2", "Default"], exclude=[])
    names = [p.directory for p in selected]
    # Order follows the requested include list.
    assert names == ["Profile 2", "Default"]


def test_select_skips_missing_profiles(fake_user_data_dir: Path) -> None:
    manager = ProfileManager(fake_user_data_dir)
    selected = manager.select(include=["Profile 9"], exclude=[])
    assert selected == []


def test_discover_missing_dir(tmp_path: Path) -> None:
    manager = ProfileManager(tmp_path / "does-not-exist")
    assert manager.discover() == []
