"""CLI entry point for the Chrome multi-profile playlist automation framework.

Usage examples::

    python main.py
    python main.py --config config/config.yaml
    python main.py --profiles "Profile 1,Profile 3"
    python main.py --dry-run
    python main.py --list-profiles
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from loguru import logger

from automation import __version__
from automation.chrome import terminate_chrome
from automation.config import AppConfig, ConfigError, load_config
from automation.launcher import Launcher
from automation.logging_utils import setup_logging
from automation.notifier import TelegramNotifier
from automation.power import KeepAwake

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config" / "config.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="playlist-automation",
        description=(
            "Launch existing Chrome profiles, open playlist tabs, arrange "
            "windows in a grid and start playback."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=str(DEFAULT_CONFIG),
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--profiles",
        "-p",
        type=str,
        default=None,
        help='Comma-separated profile directories to launch, e.g. "Profile 1,Profile 3". '
        "Overrides the config 'profiles' list.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without launching any Chrome windows.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List discovered Chrome profiles and exit.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Override the log level from config (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def _split_profiles(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _run_scheduled(
    config: AppConfig,
    launcher: Launcher,
    notifier: TelegramNotifier,
    profile_override: list[str] | None,
) -> int:
    """Run the repeating play -> close Chrome -> wait -> relaunch cycle.

    Loops forever (or until ``schedule.max_cycles``), sending a Telegram update
    after every launch and after every Chrome shutdown.
    """
    sched = config.schedule
    play_seconds = sched.play_hours * 3600.0
    cooldown_seconds = sched.cooldown_minutes * 60.0
    cycle = 0

    logger.info(
        "Scheduler enabled: play {:g}h -> close Chrome -> wait {:g}min -> repeat"
        "{}.",
        sched.play_hours,
        sched.cooldown_minutes,
        f" (max {sched.max_cycles} cycles)" if sched.max_cycles else " (forever)",
    )

    keep_awake = KeepAwake() if sched.prevent_sleep else None
    if keep_awake is not None:
        keep_awake.start()
    try:
        while True:
            cycle += 1
            logger.info("################  CYCLE {}  ################", cycle)

            report = launcher.run(profile_override=profile_override)
            launcher.write_report(report, BASE_DIR)

            notifier.send(
                f"🟢 TKK Playlist — cycle {cycle} started\n"
                f"Opened {report.succeeded}/{report.total_profiles} Chrome "
                f"profile(s) with playlists (loop + shuffle).\n"
                f"Playing for {sched.play_hours:g} hour(s)."
            )

            logger.info("Playing for {:g} hour(s)...", sched.play_hours)
            time.sleep(max(0.0, play_seconds))

            terminate_chrome()
            notifier.send(
                f"🔴 TKK Playlist — cycle {cycle} ended\n"
                f"Closed all Chrome windows."
                + (
                    ""
                    if (sched.max_cycles and cycle >= sched.max_cycles)
                    else f"\nWaiting {sched.cooldown_minutes:g} minute(s) before "
                    "the next cycle."
                )
            )

            if sched.max_cycles and cycle >= sched.max_cycles:
                logger.info(
                    "Reached max_cycles={}. Stopping scheduler.", sched.max_cycles
                )
                return 0

            logger.info("Cooling down for {:g} minute(s)...", sched.cooldown_minutes)
            time.sleep(max(0.0, cooldown_seconds))
    finally:
        if keep_awake is not None:
            keep_awake.stop()


def main(argv: list[str] | None = None) -> int:
    """Program entry point. Returns a process exit code."""
    args = parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.log_level:
        config.logging.level = args.log_level.upper()

    setup_logging(config.logging, BASE_DIR)
    logger.info("Chrome Playlist Automation v{}", __version__)

    try:
        launcher = Launcher(config, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - surface setup failures cleanly
        logger.error("Failed to initialise launcher: {}", exc)
        return 3

    if args.list_profiles:
        profiles = launcher.list_profiles()
        if not profiles:
            logger.warning("No Chrome profiles discovered.")
            return 1
        print("\nDiscovered Chrome profiles:")
        for profile in profiles:
            print(f"  - {profile.directory:<12} {profile.display_name}")
        print()
        return 0

    profile_override = _split_profiles(args.profiles)
    notifier = TelegramNotifier(config.telegram)

    try:
        if config.schedule.enabled and not args.dry_run:
            return _run_scheduled(config, launcher, notifier, profile_override)

        report = launcher.run(profile_override=profile_override)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Exiting.")
        return 130

    launcher.write_report(report, BASE_DIR)

    if report.total_profiles == 0:
        return 1
    return 0 if report.failed == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
