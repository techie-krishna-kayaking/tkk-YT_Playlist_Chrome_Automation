"""Cross-platform window arrangement into a grid.

Windows-first: uses ``pygetwindow`` (and optionally Win32) to move/resize the
launched Chrome windows into a tidy grid. On macOS/Linux the operations degrade
gracefully to no-ops with a warning, because the Chrome ``--window-position`` /
``--window-size`` flags already handle initial placement there.
"""

from __future__ import annotations

import math
import subprocess
import time
from dataclasses import dataclass

from loguru import logger

from .config import GridConfig, WindowConfig
from .utils import Platform


# Conservative fallback resolution when detection is unavailable.
_FALLBACK_SCREEN = (1920, 1080)
# Leave room for the OS taskbar / menu bar / dock.
_SCREEN_MARGIN_Y = 80


def detect_screen_size(
    override_w: int = 0, override_h: int = 0
) -> tuple[int, int]:
    """Best-effort detection of the primary screen's usable pixel size.

    Args:
        override_w: Explicit width; used when > 0.
        override_h: Explicit height; used when > 0.

    Returns:
        ``(width, height)`` in pixels. Falls back to 1920x1080 on failure.
    """
    if override_w > 0 and override_h > 0:
        return override_w, override_h

    try:
        if Platform.is_windows():
            import ctypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.SetProcessDPIAware()
            return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))

        if Platform.is_macos():
            script = (
                'tell application "Finder" to get bounds of window of desktop'
            )
            out = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            parts = [p.strip() for p in out.stdout.strip().split(",")]
            if len(parts) == 4:
                return int(parts[2]), int(parts[3])

        else:  # Linux
            out = subprocess.run(
                ["xrandr"], capture_output=True, text=True, timeout=5
            )
            for line in out.stdout.splitlines():
                if "*" in line:
                    res = line.split()[0]
                    w, h = res.lower().split("x")
                    return int(w), int(h)
    except Exception as exc:  # noqa: BLE001 - detection is best-effort
        logger.debug("Screen size detection failed ({}); using fallback.", exc)

    return _FALLBACK_SCREEN


@dataclass(frozen=True)
class GridCell:
    """A computed position/size for one window in the grid."""

    index: int
    x: int
    y: int
    width: int
    height: int


def compute_grid(
    count: int,
    window: WindowConfig,
    grid: GridConfig,
) -> list[GridCell]:
    """Compute grid cell rectangles for ``count`` windows.

    Args:
        count: Number of windows to place.
        window: Per-window width/height.
        grid: Grid layout (columns, padding, origin).

    Returns:
        A list of :class:`GridCell` positions, row-major.
    """
    cells: list[GridCell] = []
    columns = max(1, grid.columns)
    for index in range(count):
        row = index // columns
        col = index % columns
        x = grid.origin_x + col * (window.width + grid.padding)
        y = grid.origin_y + row * (window.height + grid.padding)
        cells.append(
            GridCell(index=index, x=x, y=y, width=window.width, height=window.height)
        )
    return cells


def compute_auto_grid(
    count: int,
    grid: GridConfig,
    screen: tuple[int, int],
    columns_override: int | None = None,
) -> list[GridCell]:
    """Tile ``count`` windows to fit entirely on the given screen.

    Chooses a column/row count whose cells are as close to the screen's aspect
    ratio as possible, then divides the usable area evenly so every window is
    visible (a "video wall" layout).

    Args:
        count: Number of windows to place.
        grid: Grid layout (padding/origin honoured; columns ignored).
        screen: ``(width, height)`` of the target screen in pixels.
        columns_override: When > 0, force this many columns (windows per row)
            instead of picking a column count from the screen aspect ratio.

    Returns:
        A list of :class:`GridCell` positions/sizes, row-major.
    """
    if count <= 0:
        return []

    screen_w, screen_h = screen
    usable_h = max(200, screen_h - _SCREEN_MARGIN_Y)
    pad = max(0, grid.padding)

    if columns_override and columns_override > 0:
        # Force an exact number of windows per row (wrapping to the next row).
        columns = max(1, min(count, columns_override))
    else:
        # Pick columns so tiles roughly match the screen aspect ratio.
        columns = max(1, min(count, round(math.sqrt(count * screen_w / usable_h))))
    rows = math.ceil(count / columns)

    cell_w = max(360, (screen_w - (columns + 1) * pad) // columns)
    cell_h = max(240, (usable_h - (rows + 1) * pad) // rows)

    cells: list[GridCell] = []
    for index in range(count):
        row = index // columns
        col = index % columns
        x = grid.origin_x + pad + col * (cell_w + pad)
        y = grid.origin_y + pad + row * (cell_h + pad)
        cells.append(GridCell(index=index, x=x, y=y, width=cell_w, height=cell_h))

    logger.info(
        "Auto-fit grid: {} windows in {}x{} (cols x rows) at {}x{} px each on a "
        "{}x{} screen.",
        count,
        columns,
        rows,
        cell_w,
        cell_h,
        screen_w,
        screen_h,
    )
    return cells


def compute_cascade(
    count: int,
    window: WindowConfig,
    grid: GridConfig,
    screen: tuple[int, int],
) -> list[GridCell]:
    """Stack ``count`` small windows on top of each other with a diagonal offset.

    Produces the classic "cascade" look where each window keeps the configured
    (small) size and is shifted down-right from the previous one, so every title
    bar stays visible. When the cascade would run off the screen it wraps back
    to the origin, starting a new overlapping stack.

    Args:
        count: Number of windows to place.
        window: Per-window width/height (kept as-is; windows stay small).
        grid: Grid layout (origin + cascade offsets honoured).
        screen: ``(width, height)`` of the target screen in pixels.

    Returns:
        A list of :class:`GridCell` positions/sizes, in launch order.
    """
    if count <= 0:
        return []

    screen_w, screen_h = screen
    usable_h = max(200, screen_h - _SCREEN_MARGIN_Y)
    win_w = window.width
    win_h = window.height
    off_x = max(0, grid.cascade_offset_x)
    off_y = max(0, grid.cascade_offset_y)

    cells: list[GridCell] = []
    step = 0
    for index in range(count):
        x = grid.origin_x + step * off_x
        y = grid.origin_y + step * off_y
        # Wrap back to the origin if the next window would fall off-screen.
        if (x + win_w > screen_w or y + win_h > usable_h) and step > 0:
            step = 0
            x = grid.origin_x
            y = grid.origin_y
        cells.append(GridCell(index=index, x=x, y=y, width=win_w, height=win_h))
        step += 1

    logger.info(
        "Cascade layout: {} windows at {}x{} px each, offset ({}, {}) on a "
        "{}x{} screen.",
        count,
        win_w,
        win_h,
        off_x,
        off_y,
        screen_w,
        screen_h,
    )
    return cells


def build_grid(
    count: int,
    window: WindowConfig,
    grid: GridConfig,
) -> list[GridCell]:
    """Return grid cells using the configured layout.

    Precedence: ``cascade`` (overlapping stack) > ``auto_fit`` (video wall) >
    fixed grid.
    """
    if grid.cascade:
        screen = detect_screen_size(grid.screen_width, grid.screen_height)
        return compute_cascade(count, window, grid, screen)
    if grid.auto_fit:
        screen = detect_screen_size(grid.screen_width, grid.screen_height)
        return compute_auto_grid(count, grid, screen, grid.fill_columns)
    return compute_grid(count, window, grid)



class WindowManager:
    """Arranges Chrome windows into a grid across platforms."""

    def __init__(self, window: WindowConfig, grid: GridConfig) -> None:
        self._window = window
        self._grid = grid
        self._gw = self._import_pygetwindow()

    @staticmethod
    def _import_pygetwindow():
        try:
            import pygetwindow  # type: ignore

            return pygetwindow
        except Exception:  # noqa: BLE001 - optional dependency / non-Windows
            return None

    def _find_window(self, title_contains: str):
        """Return the most recently created window whose title matches."""
        if self._gw is None:
            return None
        try:
            matches = [
                w
                for w in self._gw.getAllWindows()
                if title_contains.lower() in (w.title or "").lower()
            ]
            return matches[-1] if matches else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Window lookup failed: {}", exc)
            return None

    def arrange_single(self, cell: GridCell, title_hint: str, retries: int = 5) -> bool:
        """Move/resize a single window identified by a title hint.

        Args:
            cell: Target rectangle.
            title_hint: Substring to match the window title (e.g. profile name
                or a page title).
            retries: How many times to poll for the window to appear.

        Returns:
            True on success, False if the window could not be arranged.
        """
        if not Platform.is_windows() or self._gw is None:
            logger.debug(
                "Window arrangement skipped (platform={}, pygetwindow={}). "
                "Relying on Chrome --window-position/size.",
                Platform.name(),
                self._gw is not None,
            )
            return False

        for _ in range(max(1, retries)):
            window = self._find_window(title_hint)
            if window is not None:
                try:
                    window.moveTo(cell.x, cell.y)
                    window.resizeTo(cell.width, cell.height)
                    logger.debug(
                        "Arranged window '{}' -> ({}, {}) {}x{}",
                        title_hint,
                        cell.x,
                        cell.y,
                        cell.width,
                        cell.height,
                    )
                    return True
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to arrange window '{}': {}", title_hint, exc)
                    return False
            time.sleep(0.5)

        logger.debug("Window matching '{}' not found for arrangement.", title_hint)
        return False
