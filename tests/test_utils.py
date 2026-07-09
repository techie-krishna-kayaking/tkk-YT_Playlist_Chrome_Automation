"""Unit tests for utilities, playlist parsing and grid computation."""

from __future__ import annotations

import pytest

from automation.config import GridConfig, WindowConfig
from automation.playlist import build_playlists
from automation.utils import Stopwatch, chunked, retry
from automation.window_manager import compute_auto_grid, compute_grid


def test_retry_succeeds_after_failures() -> None:
    calls = {"n": 0}

    @retry(attempts=3, delay=0.0)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_reraises_after_exhaustion() -> None:
    @retry(attempts=2, delay=0.0)
    def always_fail() -> None:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        always_fail()


def test_stopwatch_measures_time() -> None:
    with Stopwatch() as sw:
        sum(range(1000))
    assert sw.elapsed >= 0.0


def test_chunked_splits_evenly() -> None:
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_build_playlists_filters_invalid() -> None:
    playlists = build_playlists(
        ["https://youtube.com/watch?v=1", "ftp://bad", "", "not a url"],
        autoplay=False,
    )
    assert len(playlists) == 1
    assert playlists[0].provider == "youtube"


def test_build_playlists_autoplay_hint() -> None:
    playlists = build_playlists(["https://www.youtube.com/watch?v=1"], autoplay=True)
    assert "autoplay=1" in playlists[0].url
    assert playlists[0].original_url == "https://www.youtube.com/watch?v=1"


def test_build_playlists_youtube_playlist_becomes_watch_url() -> None:
    playlists = build_playlists(
        ["https://www.youtube.com/playlist?list=PLABC123"], autoplay=True
    )
    assert playlists[0].url == (
        "https://www.youtube.com/watch?list=PLABC123&playnext=1&index=1&autoplay=1"
    )
    assert playlists[0].original_url == "https://www.youtube.com/playlist?list=PLABC123"


def test_build_playlists_playlist_unchanged_when_autoplay_off() -> None:
    playlists = build_playlists(
        ["https://www.youtube.com/playlist?list=PLABC123"], autoplay=False
    )
    assert playlists[0].url == "https://www.youtube.com/playlist?list=PLABC123"


def test_build_playlists_provider_classification() -> None:
    playlists = build_playlists(
        [
            "https://open.spotify.com/playlist/1",
            "https://music.youtube.com/playlist?list=2",
            "https://example.com/x",
        ],
        autoplay=False,
    )
    providers = [p.provider for p in playlists]
    assert providers == ["spotify", "youtube_music", "generic"]


def test_compute_grid_positions() -> None:
    window = WindowConfig(width=100, height=100)
    grid = GridConfig(columns=2, padding=10, origin_x=5, origin_y=5)
    cells = compute_grid(3, window, grid)
    assert len(cells) == 3
    assert (cells[0].x, cells[0].y) == (5, 5)
    assert (cells[1].x, cells[1].y) == (5 + 110, 5)
    # Third window wraps to the next row.
    assert (cells[2].x, cells[2].y) == (5, 5 + 110)


def test_compute_auto_grid_fits_on_screen() -> None:
    grid = GridConfig(auto_fit=True, padding=8)
    cells = compute_auto_grid(14, grid, screen=(1920, 1080))
    assert len(cells) == 14
    # Every window must stay within the screen bounds.
    for cell in cells:
        assert cell.x + cell.width <= 1920
        assert cell.y + cell.height <= 1080
        assert cell.width >= 360
        assert cell.height >= 240


def test_compute_auto_grid_empty() -> None:
    grid = GridConfig(auto_fit=True)
    assert compute_auto_grid(0, grid, screen=(1920, 1080)) == []
