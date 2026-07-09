"""Playlist / URL modelling and validation.

The framework is URL-agnostic (YouTube, Spotify, YouTube Music, anything). This
module normalises and lightly validates the configured URLs, and optionally
appends autoplay hints for well-known providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from loguru import logger


@dataclass(frozen=True)
class Playlist:
    """A single playlist/page to open in a tab.

    Attributes:
        url: The (possibly autoplay-augmented) URL to open.
        original_url: The URL exactly as configured.
        provider: Best-effort provider label (``youtube``, ``spotify`` ...).
    """

    url: str
    original_url: str
    provider: str


def _classify(host: str) -> str:
    host = host.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube_music" if host.startswith("music.") else "youtube"
    if "spotify.com" in host:
        return "spotify"
    return "generic"


def _youtube_playlist_id(parsed) -> str | None:
    """Extract the ``list`` id from a YouTube playlist URL, if present."""
    if not parsed.path.rstrip("/").endswith("/playlist"):
        return None
    values = parse_qs(parsed.query).get("list")
    return values[0] if values else None


def _augment_autoplay(url: str, provider: str, parsed) -> str:
    """Rewrite/augment a URL so playback actually starts.

    A YouTube ``/playlist?list=ID`` URL only shows the playlist landing page
    (with a "Play all" button) and never auto-plays. Converting it to the
    ``/watch?list=ID&playnext=1`` form loads the first video and begins
    playback. For other YouTube pages we just append ``autoplay=1``.
    """
    if provider not in {"youtube", "youtube_music"}:
        return url

    playlist_id = _youtube_playlist_id(parsed)
    if playlist_id:
        host = parsed.netloc or "www.youtube.com"
        return (
            f"{parsed.scheme}://{host}/watch"
            f"?list={playlist_id}&playnext=1&index=1&autoplay=1"
        )

    if "autoplay=" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}autoplay=1"
    return url


def build_playlists(urls: list[str], autoplay: bool) -> list[Playlist]:
    """Validate and normalise configured URLs into :class:`Playlist` objects.

    Args:
        urls: Raw URL strings from configuration.
        autoplay: Whether to append provider autoplay hints.

    Returns:
        A list of valid :class:`Playlist` objects. Invalid URLs are skipped.
    """
    playlists: list[Playlist] = []
    for raw in urls:
        raw = raw.strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.warning("Skipping invalid URL (must be http/https): {}", raw)
            continue
        provider = _classify(parsed.netloc)
        url = _augment_autoplay(raw, provider, parsed) if autoplay else raw
        playlists.append(Playlist(url=url, original_url=raw, provider=provider))
    return playlists
