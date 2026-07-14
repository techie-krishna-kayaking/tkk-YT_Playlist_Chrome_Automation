"""Launcher orchestration: the heart of the framework.

Coordinates profile discovery, Chrome launching, window arrangement, playback
control, retries, reporting and (optional) parallel execution. Everything is
wired via dependency injection so components can be swapped or mocked in tests.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from .chrome import ChromeLauncher, LaunchOptions, detect_chrome_path, detect_user_data_dir
from .config import AppConfig
from .logging_utils import profile_logger
from .playback import PlaybackError, PlaywrightPlaybackController
from .playlist import Playlist, build_playlists
from .profile_manager import ChromeProfile, ProfileManager
from .report import ExecutionReport, ProfileReport
from .utils import Stopwatch
from .window_manager import WindowManager, build_grid


class Launcher:
    """Orchestrates the end-to-end automation run."""

    def __init__(
        self,
        config: AppConfig,
        *,
        dry_run: bool = False,
        chrome_launcher: ChromeLauncher | None = None,
        profile_manager: ProfileManager | None = None,
        window_manager: WindowManager | None = None,
    ) -> None:
        self._config = config
        self._dry_run = dry_run

        # --- Dependency injection with sensible auto-wired defaults ---------
        self._user_data_dir = detect_user_data_dir(config.user_data_dir)
        chrome_path = detect_chrome_path(config.chrome_path)
        logger.info("Chrome executable: {}", chrome_path)
        logger.info("User Data directory: {}", self._user_data_dir)

        self._chrome = chrome_launcher or ChromeLauncher(chrome_path)
        self._profiles = profile_manager or ProfileManager(self._user_data_dir)
        self._windows = window_manager or WindowManager(config.window, config.grid)
        self._playback = PlaywrightPlaybackController(config.playback)

        self._playlists: list[Playlist] = build_playlists(
            config.playlists, autoplay=config.playback.autoplay
        )
        self._loop_extension_dir = self._resolve_loop_extension()
        self._interrupted = False

    @staticmethod
    def _resolve_loop_extension() -> Path | None:
        """Return the bundled loop-extension directory if it exists."""
        ext_dir = (
            Path(__file__).resolve().parent.parent / "assets" / "loop_extension"
        )
        if (ext_dir / "manifest.json").is_file():
            return ext_dir
        logger.warning(
            "Loop extension not found at {}; playlists will not loop.", ext_dir
        )
        return None

    # ------------------------------------------------------------------ API
    def list_profiles(self) -> list[ChromeProfile]:
        """Return all discovered profiles (for the --list-profiles command)."""
        return self._profiles.discover()

    def run(self, profile_override: list[str] | None = None) -> ExecutionReport:
        """Execute the automation for all selected profiles.

        Args:
            profile_override: Optional explicit list of profile directory names
                (from ``--profiles``) that overrides the config selection.

        Returns:
            The completed :class:`ExecutionReport`.
        """
        report = ExecutionReport(dry_run=self._dry_run)
        include = profile_override if profile_override else self._config.profiles
        selected = self._profiles.select(
            include=include, exclude=self._config.exclude_profiles
        )

        if not selected:
            logger.error("No profiles selected/found. Nothing to do.")
            report.finalize(0.0)
            return report

        if not self._playlists:
            logger.error("No valid playlists configured. Nothing to do.")
            report.finalize(0.0)
            return report

        logger.info(
            "Launching {} profile(s) with {} playlist tab(s) each. Mode: {}",
            len(selected),
            len(self._playlists),
            "parallel" if self._config.execution.parallel else "sequential",
        )

        cells = build_grid(len(selected), self._config.window, self._config.grid)

        with Stopwatch("run") as sw:
            try:
                if self._config.execution.parallel and not self._dry_run:
                    self._run_parallel(selected, cells, report)
                else:
                    self._run_sequential(selected, cells, report)
            except KeyboardInterrupt:
                self._interrupted = True
                logger.warning("Keyboard interrupt received - stopping gracefully.")

        report.finalize(sw.elapsed)
        report.log_summary()
        return report

    # ------------------------------------------------------- run strategies
    def _run_sequential(
        self,
        profiles: list[ChromeProfile],
        cells: list,
        report: ExecutionReport,
    ) -> None:
        for index, profile in enumerate(profiles):
            if self._interrupted:
                break
            record = self._launch_with_retries(profile, cells[index])
            report.add(record)

            is_last = index == len(profiles) - 1
            if not is_last and not self._dry_run:
                logger.info(
                    "Waiting {:.1f}s before next profile...",
                    self._config.delay_between_profiles,
                )
                self._interruptible_sleep(self._config.delay_between_profiles)

    def _run_parallel(
        self,
        profiles: list[ChromeProfile],
        cells: list,
        report: ExecutionReport,
    ) -> None:
        max_workers = min(self._config.execution.max_concurrent, len(profiles))
        logger.info("Parallel execution with up to {} concurrent windows.", max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self._launch_with_retries, profile, cells[index]): profile
                for index, profile in enumerate(profiles)
            }
            for future in as_completed(futures):
                report.add(future.result())

    # -------------------------------------------------------- single launch
    def _launch_with_retries(
        self, profile: ChromeProfile, cell
    ) -> ProfileReport:
        plog = profile_logger(profile.directory)
        record = ProfileReport(
            profile_directory=profile.directory,
            display_name=profile.display_name,
            urls=[p.url for p in self._playlists],
        )
        attempts = self._config.execution.retries + 1

        with Stopwatch() as sw:
            for attempt in range(1, attempts + 1):
                record.attempts = attempt
                try:
                    self._launch_once(profile, cell, record, plog)
                    record.success = True
                    plog.success(
                        "Profile '{}' launched successfully ({} tabs).",
                        profile.directory,
                        record.tabs_opened,
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - isolate per-profile
                    record.error = str(exc)
                    plog.error(
                        "Attempt {}/{} failed for profile '{}': {}",
                        attempt,
                        attempts,
                        profile.directory,
                        exc,
                    )
                    if attempt < attempts:
                        self._interruptible_sleep(self._config.execution.retry_delay)

        record.elapsed_seconds = round(sw.elapsed, 3)
        return record

    def _launch_once(
        self,
        profile: ChromeProfile,
        cell,
        record: ProfileReport,
        plog,
    ) -> None:
        """Perform one full launch attempt for a profile."""
        port: int | None = None
        if self._config.playback.mode == "playwright" and self._config.playback.autoplay:
            port = self._config.playback.remote_debugging_port + cell.index

        load_extension = (
            self._loop_extension_dir if self._config.playback.loop else None
        )

        options = LaunchOptions(
            profile_directory=profile.directory,
            urls=[p.url for p in self._playlists],
            user_data_dir=self._user_data_dir,
            window_width=cell.width,
            window_height=cell.height,
            position_x=cell.x,
            position_y=cell.y,
            remote_debugging_port=port,
            load_extension=load_extension,
        )

        result = self._chrome.launch(options, dry_run=self._dry_run)
        record.pid = result.pid
        record.remote_debugging_port = result.remote_debugging_port
        record.tabs_opened = len(self._playlists)

        if self._dry_run:
            return

        # Give Chrome a moment to create the window before arranging/playback.
        self._interruptible_sleep(min(self._config.delay_between_tabs, 3.0))

        # Arrange the window into its grid cell.
        if self._windows.arrange_single(cell, title_hint=profile.display_name):
            record.windows_arranged = 1

        # Drive playback if requested via Playwright.
        if self._config.playback.autoplay and self._config.playback.mode == "playwright":
            self._drive_playback(port, record, plog)

    def _drive_playback(self, port: int | None, record: ProfileReport, plog) -> None:
        if port is None:
            return
        # Wait for the debugging endpoint to become responsive.
        self._interruptible_sleep(min(self._config.launch_ready_timeout, 5.0))
        try:
            outcome = self._playback.start_playback(port)
            record.tabs_playing = outcome.tabs_playing
            plog.info(
                "Playback: {}/{} tabs playing ({} already playing, {} errors).",
                outcome.tabs_playing,
                outcome.tabs_total,
                outcome.already_playing,
                outcome.errors,
            )
        except PlaybackError as exc:
            plog.warning("Playback control unavailable: {}", exc)

    # --------------------------------------------------------------- helpers
    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in small slices so Ctrl+C is responsive."""
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._interrupted:
                return
            time.sleep(min(0.25, end - time.monotonic()))

    def write_report(self, report: ExecutionReport, base_dir: Path) -> Path | None:
        """Persist the JSON execution report if enabled in config."""
        if not self._config.report.enabled:
            return None
        report_path = (base_dir / self._config.report.dir / self._config.report.filename).resolve()
        return report.write_json(report_path)
