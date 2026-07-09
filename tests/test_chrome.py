"""Unit tests for Chrome detection and command building."""

from __future__ import annotations

from pathlib import Path

import pytest

from automation.chrome import (
    ChromeLauncher,
    ChromeNotFoundError,
    LaunchOptions,
    detect_chrome_path,
)


def test_detect_chrome_path_explicit(fake_chrome_binary: Path) -> None:
    assert detect_chrome_path(str(fake_chrome_binary)) == fake_chrome_binary.resolve()


def test_detect_chrome_path_falls_back_when_explicit_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An invalid explicit path is ignored and auto-detection runs. Simulate a
    # machine with no Chrome so the fallback path raises deterministically.
    import automation.chrome as chrome_mod

    monkeypatch.setattr(chrome_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(chrome_mod.Platform, "is_windows", staticmethod(lambda: False))
    monkeypatch.setattr(chrome_mod.Platform, "is_macos", staticmethod(lambda: False))
    monkeypatch.setattr(chrome_mod.Platform, "is_linux", staticmethod(lambda: True))

    with pytest.raises(ChromeNotFoundError):
        detect_chrome_path(str(tmp_path / "not-chrome"))


def test_build_command_contains_profile_and_urls(fake_chrome_binary: Path, tmp_path: Path) -> None:
    launcher = ChromeLauncher(fake_chrome_binary)
    options = LaunchOptions(
        profile_directory="Profile 1",
        urls=["https://a.com", "https://b.com"],
        user_data_dir=tmp_path,
        window_width=800,
        window_height=600,
        position_x=10,
        position_y=20,
        remote_debugging_port=9333,
    )
    cmd = launcher.build_command(options)
    assert str(fake_chrome_binary) == cmd[0]
    assert "--profile-directory=Profile 1" in cmd
    assert f"--user-data-dir={tmp_path}" in cmd
    assert "--new-window" in cmd
    assert "--window-size=800,600" in cmd
    assert "--window-position=10,20" in cmd
    assert "--remote-debugging-port=9333" in cmd
    assert cmd[-2:] == ["https://a.com", "https://b.com"]


def test_launch_dry_run_does_not_start_process(fake_chrome_binary: Path, tmp_path: Path) -> None:
    launcher = ChromeLauncher(fake_chrome_binary)
    options = LaunchOptions(
        profile_directory="Default",
        urls=["https://a.com"],
        user_data_dir=tmp_path,
    )
    result = launcher.launch(options, dry_run=True)
    assert result.pid is None
    assert result.profile_directory == "Default"
