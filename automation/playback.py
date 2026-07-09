"""Playback control via Playwright over the Chrome DevTools Protocol.

When ``playback.mode == "playwright"``, Chrome is launched with
``--remote-debugging-port``. This module connects Playwright to that running
browser (over CDP) *without* creating a new browser or profile, then attempts to
start playback on each open tab by:

1. checking whether media is already playing (skip if so),
2. clicking a known play-button selector, or
3. dispatching the Space key as a fallback.

Playwright is an optional dependency; if it is not installed this module reports
a clear error and the launcher falls back to native autoplay.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .config import PlaybackConfig


class PlaybackError(Exception):
    """Raised when playback control fails irrecoverably."""


@dataclass
class PlaybackOutcome:
    """Result of attempting to start playback across a browser's tabs."""

    tabs_total: int = 0
    tabs_playing: int = 0
    already_playing: int = 0
    errors: int = 0


# JS that returns True if any <video>/<audio> element is currently playing.
_IS_PLAYING_JS = """
() => {
  const media = Array.from(document.querySelectorAll('video, audio'));
  return media.some(m => !m.paused && !m.ended && m.readyState > 2);
}
"""


class PlaywrightPlaybackController:
    """Drives media playback in an already-running Chrome via CDP."""

    def __init__(self, cfg: PlaybackConfig) -> None:
        self._cfg = cfg

    def _endpoint(self, port: int) -> str:
        return f"http://127.0.0.1:{port}"

    def start_playback(self, port: int, timeout_ms: int = 15000) -> PlaybackOutcome:
        """Connect to Chrome on ``port`` and ensure each tab is playing.

        Args:
            port: The remote debugging port Chrome was launched with.
            timeout_ms: Per-operation timeout in milliseconds.

        Returns:
            A :class:`PlaybackOutcome` summarising what happened.

        Raises:
            PlaybackError: If Playwright is unavailable or the connection fails.
        """
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise PlaybackError(
                "Playwright is not installed. Run 'pip install playwright' and "
                "'playwright install chromium', or set playback.mode to 'native'."
            ) from exc

        outcome = PlaybackOutcome()
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.connect_over_cdp(self._endpoint(port))
            except Exception as exc:  # noqa: BLE001
                raise PlaybackError(
                    f"Could not connect to Chrome DevTools on port {port}: {exc}"
                ) from exc

            try:
                pages = [p for ctx in browser.contexts for p in ctx.pages]
                outcome.tabs_total = len(pages)
                for page in pages:
                    self._play_page(page, outcome, timeout_ms)
            finally:
                # Detach only; never close the user's browser or profile.
                try:
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass
        return outcome

    def _play_page(self, page, outcome: PlaybackOutcome, timeout_ms: int) -> None:
        """Attempt to start playback on one page/tab."""
        url = getattr(page, "url", "<unknown>")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            logger.debug("Tab did not reach domcontentloaded in time: {}", url)

        # 1. Already playing? Skip.
        try:
            if page.evaluate(_IS_PLAYING_JS):
                outcome.already_playing += 1
                outcome.tabs_playing += 1
                logger.debug("Tab already playing, skipping: {}", url)
                return
        except Exception:  # noqa: BLE001
            pass

        # 2. Try clicking a known play button.
        for selector in self._cfg.play_selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0:
                    locator.click(timeout=2000)
                    if self._confirm_playing(page):
                        outcome.tabs_playing += 1
                        logger.debug("Started playback via selector '{}': {}", selector, url)
                        return
            except Exception:  # noqa: BLE001
                continue

        # 3. Fallback: focus the body and press Space.
        try:
            page.bring_to_front()
            page.keyboard.press("Space")
            if self._confirm_playing(page):
                outcome.tabs_playing += 1
                logger.debug("Started playback via Space key: {}", url)
                return
        except Exception as exc:  # noqa: BLE001
            logger.debug("Space-key playback failed for {}: {}", url, exc)

        outcome.errors += 1
        logger.warning("Could not confirm playback for tab: {}", url)

    @staticmethod
    def _confirm_playing(page, attempts: int = 4) -> bool:
        """Poll the page briefly to confirm media started playing."""
        import time

        for _ in range(attempts):
            try:
                if page.evaluate(_IS_PLAYING_JS):
                    return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        return False
