"""Chrome executable / user-data detection and process launching.

This module never hardcodes paths: it discovers the Chrome binary and the
``User Data`` directory from OS-standard locations, and launches Chrome using
command-line arguments against an existing profile (never a temp profile).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from .utils import Platform


class ChromeNotFoundError(Exception):
    """Raised when the Chrome executable cannot be located."""


class UserDataDirNotFoundError(Exception):
    """Raised when the Chrome User Data directory cannot be located."""


def _chrome_running() -> bool:
    """Return True if any Google Chrome process is currently running."""
    try:
        if Platform.is_windows():
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "chrome.exe" in out.stdout.lower()
        pattern = "Google Chrome" if Platform.is_macos() else "chrome"
        out = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(out.stdout.strip())
    except Exception as exc:  # noqa: BLE001 - detection is best-effort
        logger.debug("Chrome running-check failed: {}", exc)
        return False


def terminate_chrome(graceful_timeout: float = 12.0) -> bool:
    """Close all running Google Chrome windows/processes.

    Tries a graceful quit first (so the next launch does not show a crash-restore
    bubble) and force-kills anything still alive afterwards.

    Args:
        graceful_timeout: Seconds to wait for a clean shutdown before force-kill.

    Returns:
        True if Chrome is confirmed stopped (or was not running).
    """
    if not _chrome_running():
        logger.info("Chrome is not running; nothing to close.")
        return True

    logger.info("Closing Google Chrome (graceful)...")
    try:
        if Platform.is_windows():
            subprocess.run(["taskkill", "/IM", "chrome.exe"], capture_output=True)
        elif Platform.is_macos():
            subprocess.run(
                ["osascript", "-e", 'tell application "Google Chrome" to quit'],
                capture_output=True,
            )
        else:  # Linux
            subprocess.run(["pkill", "-TERM", "-f", "chrome"], capture_output=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Graceful Chrome quit failed: {}", exc)

    deadline = time.monotonic() + max(0.0, graceful_timeout)
    while time.monotonic() < deadline:
        if not _chrome_running():
            logger.info("Chrome closed gracefully.")
            return True
        time.sleep(0.5)

    logger.warning("Chrome still running after {:.0f}s; force-killing.", graceful_timeout)
    try:
        if Platform.is_windows():
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
        elif Platform.is_macos():
            subprocess.run(["pkill", "-9", "-f", "Google Chrome"], capture_output=True)
        else:  # Linux
            subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Force-kill of Chrome failed: {}", exc)

    time.sleep(2.0)
    stopped = not _chrome_running()
    logger.info("Chrome stopped: {}", stopped)
    return stopped


def detect_chrome_path(explicit: str | None = None) -> Path:
    """Locate the Chrome executable.

    Args:
        explicit: A user-provided path (from config). Used verbatim if valid.

    Returns:
        Absolute path to the Chrome executable.

    Raises:
        ChromeNotFoundError: If Chrome cannot be found.
    """
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        logger.warning("Configured chrome_path '{}' not found; auto-detecting.", explicit)

    candidates: list[Path] = []
    if Platform.is_windows():
        env_dirs = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for base in env_dirs:
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif Platform.is_macos():
        candidates.append(
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        )
        candidates.append(
            Path.home()
            / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
    else:  # Linux
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

    # Fall back to PATH lookups on any platform.
    for name in ("chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        if candidate.is_file():
            logger.debug("Detected Chrome at: {}", candidate)
            return candidate.resolve()

    raise ChromeNotFoundError(
        "Could not locate the Chrome executable. Set 'chrome_path' in config.yaml."
    )


def detect_user_data_dir(explicit: str | None = None) -> Path:
    """Locate the Chrome ``User Data`` directory.

    Args:
        explicit: A user-provided path (from config). Used verbatim if valid.

    Returns:
        Absolute path to the User Data directory.

    Raises:
        UserDataDirNotFoundError: If the directory cannot be found.
    """
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_dir():
            return candidate.resolve()
        logger.warning("Configured user_data_dir '{}' not found; auto-detecting.", explicit)

    if Platform.is_windows():
        base = os.environ.get("LOCALAPPDATA")
        candidate = Path(base) / "Google" / "Chrome" / "User Data" if base else None
    elif Platform.is_macos():
        candidate = Path.home() / "Library/Application Support/Google/Chrome"
    else:  # Linux
        candidate = Path.home() / ".config/google-chrome"

    if candidate and candidate.is_dir():
        logger.debug("Detected User Data dir at: {}", candidate)
        return candidate.resolve()

    raise UserDataDirNotFoundError(
        "Could not locate the Chrome 'User Data' directory. "
        "Set 'user_data_dir' in config.yaml."
    )


@dataclass
class LaunchOptions:
    """Options describing a single Chrome window launch."""

    profile_directory: str
    urls: list[str]
    user_data_dir: Path
    window_width: int = 650
    window_height: int = 500
    position_x: int = 0
    position_y: int = 0
    remote_debugging_port: int | None = None
    load_extension: Path | None = None
    autoplay: bool = False
    extra_args: list[str] = field(default_factory=list)


@dataclass
class LaunchResult:
    """The outcome of launching a Chrome window."""

    profile_directory: str
    pid: int | None
    command: list[str]
    remote_debugging_port: int | None


class ChromeLauncher:
    """Launches Chrome windows against existing profiles via the command line."""

    def __init__(self, chrome_path: Path) -> None:
        self._chrome_path = chrome_path

    @property
    def chrome_path(self) -> Path:
        return self._chrome_path

    def build_command(self, options: LaunchOptions) -> list[str]:
        """Construct the Chrome command-line for a launch.

        A ``--new-window`` flag guarantees each profile opens as a distinct
        window even if Chrome is already running.
        """
        args: list[str] = [
            str(self._chrome_path),
            f"--user-data-dir={options.user_data_dir}",
            f"--profile-directory={options.profile_directory}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={options.window_width},{options.window_height}",
            f"--window-position={options.position_x},{options.position_y}",
        ]
        if options.remote_debugging_port:
            args.append(f"--remote-debugging-port={options.remote_debugging_port}")

        # Chrome only honours a single --disable-features switch, so collect all
        # features we want disabled and emit one combined flag at the end.
        disabled_features: list[str] = []

        if options.autoplay:
            # Force media to autoplay without a user gesture and keep background
            # / occluded tabs and windows fully alive so *every* tab plays, not
            # just the visible one.
            args.extend(
                [
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ]
            )
            # Occlusion detection can pause rendering of tiled/overlapping
            # windows; disabling it keeps them playing.
            disabled_features.append("CalculateNativeWinOcclusion")

        if options.load_extension:
            # Load the bundled loop extension. Chrome 137+ disables the
            # --load-extension switch by default, so we also re-enable it via
            # the accompanying feature flag.
            args.append(f"--load-extension={options.load_extension}")
            disabled_features.append("DisableLoadExtensionCommandLineSwitch")

        if disabled_features:
            args.append("--disable-features=" + ",".join(disabled_features))

        args.extend(options.extra_args)
        args.extend(options.urls)
        return args

    def launch(self, options: LaunchOptions, dry_run: bool = False) -> LaunchResult:
        """Launch a Chrome window.

        Args:
            options: The launch specification.
            dry_run: If True, only build the command; do not start a process.

        Returns:
            A :class:`LaunchResult` (pid is ``None`` on dry runs).
        """
        command = self.build_command(options)
        if dry_run:
            logger.info("[dry-run] Would launch: {}", " ".join(command))
            return LaunchResult(
                profile_directory=options.profile_directory,
                pid=None,
                command=command,
                remote_debugging_port=options.remote_debugging_port,
            )

        logger.debug("Launching Chrome: {}", " ".join(command))
        creationflags = 0
        if Platform.is_windows():
            # Detach so the launcher does not block on the browser process.
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0)

        process = subprocess.Popen(  # noqa: S603 - trusted, self-built argv
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return LaunchResult(
            profile_directory=options.profile_directory,
            pid=process.pid,
            command=command,
            remote_debugging_port=options.remote_debugging_port,
        )
