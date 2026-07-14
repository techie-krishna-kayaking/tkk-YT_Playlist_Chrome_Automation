"""Chrome executable / user-data detection and process launching.

This module never hardcodes paths: it discovers the Chrome binary and the
``User Data`` directory from OS-standard locations, and launches Chrome using
command-line arguments against an existing profile (never a temp profile).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from .utils import Platform


class ChromeNotFoundError(Exception):
    """Raised when the Chrome executable cannot be located."""


class UserDataDirNotFoundError(Exception):
    """Raised when the Chrome User Data directory cannot be located."""


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
        if options.load_extension:
            # Load the bundled loop extension. Chrome 137+ disables the
            # --load-extension switch by default, so we also re-enable it via
            # the accompanying feature flag.
            args.append(f"--load-extension={options.load_extension}")
            args.append(
                "--disable-features=DisableLoadExtensionCommandLineSwitch"
            )
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
