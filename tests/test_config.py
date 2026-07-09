"""Unit tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from automation.config import AppConfig, ConfigError, load_config


def test_from_dict_defaults() -> None:
    cfg = AppConfig.from_dict({"playlists": ["https://example.com"]})
    assert cfg.delay_between_profiles == 8
    assert cfg.delay_between_tabs == 2
    assert cfg.window.width == 650
    assert cfg.grid.columns == 3
    assert cfg.playback.mode == "native"
    assert cfg.execution.parallel is False


def test_validate_requires_playlists() -> None:
    cfg = AppConfig.from_dict({})
    with pytest.raises(ConfigError):
        cfg.validate()


def test_invalid_playback_mode() -> None:
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"playback": {"mode": "selenium"}})


def test_grid_columns_must_be_positive() -> None:
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"grid": {"columns": 0}})


def test_load_config_roundtrip(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
playlists:
  - https://www.youtube.com/playlist?list=abc
profiles:
  - Default
  - Profile 1
delay_between_profiles: 5
window:
  width: 800
  height: 600
grid:
  columns: 2
""",
        encoding="utf-8",
    )
    cfg = load_config(config_file)
    assert cfg.playlists == ["https://www.youtube.com/playlist?list=abc"]
    assert cfg.profiles == ["Default", "Profile 1"]
    assert cfg.delay_between_profiles == 5
    assert cfg.window.width == 800
    assert cfg.grid.columns == 2
    assert cfg.source_path == config_file.resolve()


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")
