"""Prevent the operating system from sleeping while the scheduler runs.

macOS goes to sleep when idle. During the scheduler's cooldown (Chrome closed,
no user activity) the machine would sleep, suspending this process so the next
relaunch never happens. This module keeps the system (and display) awake for the
lifetime of a :class:`KeepAwake` block, cross-platform:

* macOS   -> ``caffeinate`` subprocess.
* Windows -> ``SetThreadExecutionState`` power request.
* Linux   -> ``systemd-inhibit`` subprocess (best effort).
"""

from __future__ import annotations

import subprocess

from loguru import logger

from .utils import Platform

# Windows SetThreadExecutionState flags.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


class KeepAwake:
    """Context manager / handle that blocks OS idle sleep while active."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._windows_active = False

    def __enter__(self) -> "KeepAwake":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def start(self) -> None:
        """Begin preventing sleep. Never raises; degrades to a warning."""
        try:
            if Platform.is_macos():
                # -d display, -i idle, -m disk, -s system, -u declare user active.
                self._proc = subprocess.Popen(  # noqa: S607 - fixed, trusted argv
                    ["caffeinate", "-dimsu"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logger.info(
                    "Sleep prevention ON (caffeinate, pid {}).", self._proc.pid
                )
            elif Platform.is_windows():
                import ctypes

                ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
                    _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
                )
                self._windows_active = True
                logger.info("Sleep prevention ON (SetThreadExecutionState).")
            else:  # Linux
                self._proc = subprocess.Popen(  # noqa: S607 - fixed, trusted argv
                    [
                        "systemd-inhibit",
                        "--what=idle:sleep",
                        "--who=tkk-playlist",
                        "--why=Playing playlists",
                        "sleep",
                        "infinity",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                logger.info("Sleep prevention ON (systemd-inhibit).")
        except FileNotFoundError:
            logger.warning(
                "Sleep-prevention tool not found; the system may sleep and "
                "interrupt the cycle."
            )
        except Exception as exc:  # noqa: BLE001 - best effort, never fatal
            logger.warning("Could not enable sleep prevention: {}", exc)

    def stop(self) -> None:
        """Release the sleep block."""
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None
        if self._windows_active:
            try:
                import ctypes

                ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
            self._windows_active = False
        logger.info("Sleep prevention OFF.")
