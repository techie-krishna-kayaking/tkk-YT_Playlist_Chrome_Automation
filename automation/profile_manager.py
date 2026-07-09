"""Chrome profile discovery and selection.

Reads the Chrome ``User Data`` directory, enumerates profile sub-directories
(``Default``, ``Profile 1`` ...), and resolves friendly display names from each
profile's ``Preferences`` file when available.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

# Profile directories always look like "Default" or "Profile N".
_PROFILE_DIR_RE = re.compile(r"^(Default|Profile \d+)$")


@dataclass(frozen=True)
class ChromeProfile:
    """A discovered Chrome profile.

    Attributes:
        directory: The on-disk directory name passed to ``--profile-directory``.
        display_name: Friendly account name from Preferences (falls back to dir).
        path: Absolute path to the profile directory.
    """

    directory: str
    display_name: str
    path: Path

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        if self.display_name and self.display_name != self.directory:
            return f"{self.directory} ({self.display_name})"
        return self.directory


class ProfileManager:
    """Discovers and filters Chrome profiles within a User Data directory."""

    def __init__(self, user_data_dir: Path) -> None:
        self._user_data_dir = Path(user_data_dir)

    @property
    def user_data_dir(self) -> Path:
        return self._user_data_dir

    def _read_display_name(self, profile_dir: Path) -> str:
        """Best-effort read of the friendly profile name from Preferences."""
        prefs = profile_dir / "Preferences"
        try:
            with prefs.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            name = data.get("profile", {}).get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return profile_dir.name

    def discover(self) -> list[ChromeProfile]:
        """Return all valid profiles found in the User Data directory."""
        if not self._user_data_dir.is_dir():
            logger.error("User Data directory does not exist: {}", self._user_data_dir)
            return []

        profiles: list[ChromeProfile] = []
        for child in sorted(self._user_data_dir.iterdir()):
            if not child.is_dir():
                continue
            if not _PROFILE_DIR_RE.match(child.name):
                continue
            profiles.append(
                ChromeProfile(
                    directory=child.name,
                    display_name=self._read_display_name(child),
                    path=child,
                )
            )

        # Sort so "Default" is first, then Profile 1, 2, 3 ... numerically.
        def sort_key(p: ChromeProfile) -> tuple[int, int]:
            if p.directory == "Default":
                return (0, 0)
            match = re.search(r"(\d+)", p.directory)
            return (1, int(match.group(1)) if match else 0)

        profiles.sort(key=sort_key)
        logger.debug("Discovered {} profile(s): {}", len(profiles), [p.directory for p in profiles])
        return profiles

    def select(
        self,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> list[ChromeProfile]:
        """Resolve the effective profile list based on include/exclude rules.

        Args:
            include: Directory names to launch. Empty/None means "all discovered".
            exclude: Directory names to always drop.

        Returns:
            Ordered list of profiles to launch. Requested-but-missing profiles
            are logged and skipped.
        """
        exclude_set = {e.strip() for e in (exclude or [])}
        discovered = {p.directory: p for p in self.discover()}

        if include:
            selected: list[ChromeProfile] = []
            for name in include:
                name = name.strip()
                if name in exclude_set:
                    logger.warning("Profile '{}' is in exclude list; skipping.", name)
                    continue
                profile = discovered.get(name)
                if profile is None:
                    logger.warning(
                        "Requested profile '{}' not found in {}; skipping.",
                        name,
                        self._user_data_dir,
                    )
                    continue
                selected.append(profile)
            return selected

        # No explicit include -> all discovered minus excludes.
        return [p for p in discovered.values() if p.directory not in exclude_set]
