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
from pathlib import Path

from loguru import logger

from automation import __version__
from automation.config import ConfigError, load_config
from automation.launcher import Launcher
from automation.logging_utils import setup_logging

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

    try:
        report = launcher.run(profile_override=_split_profiles(args.profiles))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Exiting.")
        return 130

    launcher.write_report(report, BASE_DIR)

    if report.total_profiles == 0:
        return 1
    return 0 if report.failed == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
