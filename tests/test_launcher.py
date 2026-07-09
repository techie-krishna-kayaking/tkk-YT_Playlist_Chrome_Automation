"""Integration test for the launcher orchestration (dry-run, no real Chrome)."""

from __future__ import annotations

from pathlib import Path

from automation.config import AppConfig
from automation.launcher import Launcher


def _make_config(user_data_dir: Path, chrome: Path) -> AppConfig:
    cfg = AppConfig.from_dict(
        {
            "chrome_path": str(chrome),
            "user_data_dir": str(user_data_dir),
            "playlists": [
                "https://www.youtube.com/playlist?list=a",
                "https://www.youtube.com/playlist?list=b",
            ],
            "exclude_profiles": ["System Profile"],
            "delay_between_profiles": 0,
            "delay_between_tabs": 0,
            "playback": {"autoplay": True, "mode": "native"},
        }
    )
    cfg.validate()
    return cfg


def test_launcher_dry_run_all_profiles(fake_user_data_dir: Path, fake_chrome_binary: Path) -> None:
    cfg = _make_config(fake_user_data_dir, fake_chrome_binary)
    launcher = Launcher(cfg, dry_run=True)

    report = launcher.run()

    assert report.dry_run is True
    assert report.total_profiles == 3  # Default, Profile 1, Profile 2
    assert report.failed == 0
    assert report.succeeded == 3
    for record in report.profiles:
        assert record.tabs_opened == 2
        assert record.success is True
        assert record.pid is None  # dry-run never starts a process


def test_launcher_profile_override(fake_user_data_dir: Path, fake_chrome_binary: Path) -> None:
    cfg = _make_config(fake_user_data_dir, fake_chrome_binary)
    launcher = Launcher(cfg, dry_run=True)

    report = launcher.run(profile_override=["Profile 1"])

    assert report.total_profiles == 1
    assert report.profiles[0].profile_directory == "Profile 1"


def test_launcher_writes_json_report(
    fake_user_data_dir: Path, fake_chrome_binary: Path, tmp_path: Path
) -> None:
    cfg = _make_config(fake_user_data_dir, fake_chrome_binary)
    launcher = Launcher(cfg, dry_run=True)
    report = launcher.run()

    written = launcher.write_report(report, tmp_path)
    assert written is not None
    assert written.is_file()
    assert written.name == "execution_report.json"


def test_launcher_list_profiles(fake_user_data_dir: Path, fake_chrome_binary: Path) -> None:
    cfg = _make_config(fake_user_data_dir, fake_chrome_binary)
    launcher = Launcher(cfg, dry_run=True)
    discovered = [p.directory for p in launcher.list_profiles()]
    assert "Default" in discovered
    assert "Profile 1" in discovered
