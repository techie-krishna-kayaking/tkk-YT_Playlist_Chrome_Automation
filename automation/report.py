"""Execution reporting: structured JSON report and human summary."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


@dataclass
class ProfileReport:
    """Per-profile execution record."""

    profile_directory: str
    display_name: str = ""
    success: bool = False
    attempts: int = 0
    tabs_opened: int = 0
    tabs_playing: int = 0
    windows_arranged: int = 0
    elapsed_seconds: float = 0.0
    pid: int | None = None
    remote_debugging_port: int | None = None
    error: str | None = None
    urls: list[str] = field(default_factory=list)


@dataclass
class ExecutionReport:
    """Aggregate execution report for a single run."""

    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str | None = None
    platform: str = field(default_factory=platform.platform)
    dry_run: bool = False
    total_profiles: int = 0
    succeeded: int = 0
    failed: int = 0
    total_elapsed_seconds: float = 0.0
    profiles: list[ProfileReport] = field(default_factory=list)

    def add(self, record: ProfileReport) -> None:
        self.profiles.append(record)
        if record.success:
            self.succeeded += 1
        else:
            self.failed += 1

    def finalize(self, elapsed: float) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.total_elapsed_seconds = round(elapsed, 3)
        self.total_profiles = len(self.profiles)

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        """Persist the report as JSON and return the file path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)
        logger.info("Execution report written to {}", path)
        return path

    def log_summary(self) -> None:
        """Emit a human-readable summary to the logs."""
        logger.info("=" * 60)
        logger.info("EXECUTION SUMMARY")
        logger.info(
            "Profiles: {} total | {} succeeded | {} failed",
            self.total_profiles,
            self.succeeded,
            self.failed,
        )
        logger.info("Total elapsed: {:.2f}s", self.total_elapsed_seconds)
        for record in self.profiles:
            status = "OK " if record.success else "FAIL"
            logger.info(
                "[{}] {} | tabs={} playing={} | {:.2f}s{}",
                status,
                record.profile_directory,
                record.tabs_opened,
                record.tabs_playing,
                record.elapsed_seconds,
                f" | error: {record.error}" if record.error else "",
            )
        logger.info("=" * 60)
