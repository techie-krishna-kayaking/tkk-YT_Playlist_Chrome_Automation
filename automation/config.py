"""Configuration classes and YAML loading.

All configuration is represented by frozen-ish dataclasses so the rest of the
framework depends on typed objects instead of raw dictionaries. Missing keys
fall back to the defaults defined here, meaning a nearly empty ``config.yaml``
still produces a valid, runnable configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def _load_dotenv(path: Path) -> None:
    """Load ``KEY=VALUE`` pairs from a ``.env`` file into ``os.environ``.

    Lines that are blank or start with ``#`` are ignored. Surrounding quotes on
    values are stripped. Existing environment variables are never overwritten,
    so a real environment value always wins over the file.
    """
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class WindowConfig:
    """Per-window pixel dimensions used for grid arrangement."""

    width: int = 650
    height: int = 500

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "WindowConfig":
        data = data or {}
        return cls(
            width=int(data.get("width", 650)),
            height=int(data.get("height", 500)),
        )


@dataclass
class GridConfig:
    """Screen grid layout for arranging launched windows."""

    columns: int = 3
    padding: int = 8
    origin_x: int = 0
    origin_y: int = 0
    # When True, ignore the fixed window size / columns and instead tile ALL
    # launched windows to fit on the detected screen (a video-wall layout).
    auto_fit: bool = True
    # Number of columns to use for the auto-fit (video-wall) layout. 0 means
    # auto-pick a column count from the screen aspect ratio. Set e.g. 5 to force
    # exactly 5 windows per row, wrapping to the next row after that.
    fill_columns: int = 0
    # When True, stack the (small) windows on top of each other with a fixed
    # diagonal offset - a "cascade" layout. Takes precedence over auto_fit.
    cascade: bool = False
    # Pixel offset applied to each successive cascaded window.
    cascade_offset_x: int = 40
    cascade_offset_y: int = 40
    # Optional explicit screen size overrides (0 = auto-detect).
    screen_width: int = 0
    screen_height: int = 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "GridConfig":
        data = data or {}
        columns = int(data.get("columns", 3))
        if columns < 1:
            raise ConfigError("grid.columns must be >= 1")
        return cls(
            columns=columns,
            padding=int(data.get("padding", 8)),
            origin_x=int(data.get("origin_x", 0)),
            origin_y=int(data.get("origin_y", 0)),
            auto_fit=bool(data.get("auto_fit", True)),
            fill_columns=max(0, int(data.get("fill_columns", 0))),
            cascade=bool(data.get("cascade", False)),
            cascade_offset_x=int(data.get("cascade_offset_x", 40)),
            cascade_offset_y=int(data.get("cascade_offset_y", 40)),
            screen_width=int(data.get("screen_width", 0)),
            screen_height=int(data.get("screen_height", 0)),
        )


@dataclass
class PlaybackConfig:
    """Playback behaviour and Playwright connection settings."""

    autoplay: bool = True
    loop: bool = True
    mode: str = "native"  # "native" | "playwright"
    remote_debugging_port: int = 9222
    play_selectors: list[str] = field(
        default_factory=lambda: [
            "button[aria-label='Play']",
            "button[title='Play']",
            ".ytp-play-button[aria-label*='Play']",
            "button.play",
        ]
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "PlaybackConfig":
        data = data or {}
        mode = str(data.get("mode", "native")).lower()
        if mode not in {"native", "playwright"}:
            raise ConfigError("playback.mode must be 'native' or 'playwright'")
        selectors = data.get("play_selectors")
        cfg = cls(
            autoplay=bool(data.get("autoplay", True)),
            loop=bool(data.get("loop", True)),
            mode=mode,
            remote_debugging_port=int(data.get("remote_debugging_port", 9222)),
        )
        if selectors:
            cfg.play_selectors = [str(s) for s in selectors]
        return cfg


@dataclass
class ExecutionConfig:
    """Concurrency and retry orchestration settings."""

    parallel: bool = False
    max_concurrent: int = 3
    retries: int = 2
    retry_delay: float = 3.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ExecutionConfig":
        data = data or {}
        max_concurrent = int(data.get("max_concurrent", 3))
        if max_concurrent < 1:
            raise ConfigError("execution.max_concurrent must be >= 1")
        return cls(
            parallel=bool(data.get("parallel", False)),
            max_concurrent=max_concurrent,
            retries=max(0, int(data.get("retries", 2))),
            retry_delay=float(data.get("retry_delay", 3.0)),
        )


@dataclass
class LoggingConfig:
    """Logging destinations and rotation policy."""

    level: str = "INFO"
    dir: str = "logs"
    app_log: str = "automation.log"
    error_log: str = "errors.log"
    rotation: str = "10 MB"
    retention: str = "14 days"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "LoggingConfig":
        data = data or {}
        return cls(
            level=str(data.get("level", "INFO")).upper(),
            dir=str(data.get("dir", "logs")),
            app_log=str(data.get("app_log", "automation.log")),
            error_log=str(data.get("error_log", "errors.log")),
            rotation=str(data.get("rotation", "10 MB")),
            retention=str(data.get("retention", "14 days")),
        )


@dataclass
class ReportConfig:
    """JSON execution report settings."""

    enabled: bool = True
    dir: str = "logs"
    filename: str = "execution_report.json"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ReportConfig":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            dir=str(data.get("dir", "logs")),
            filename=str(data.get("filename", "execution_report.json")),
        )


@dataclass
class ScheduleConfig:
    """Repeating play -> close Chrome -> wait -> relaunch cycle settings."""

    enabled: bool = False
    play_hours: float = 5.0
    cooldown_minutes: float = 9.0
    max_cycles: int = 0  # 0 = repeat forever
    prevent_sleep: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ScheduleConfig":
        data = data or {}
        play_hours = float(data.get("play_hours", 5.0))
        cooldown_minutes = float(data.get("cooldown_minutes", 9.0))
        if play_hours < 0 or cooldown_minutes < 0:
            raise ConfigError("schedule play_hours/cooldown_minutes must be >= 0.")
        return cls(
            enabled=bool(data.get("enabled", False)),
            play_hours=play_hours,
            cooldown_minutes=cooldown_minutes,
            max_cycles=max(0, int(data.get("max_cycles", 0))),
            prevent_sleep=bool(data.get("prevent_sleep", True)),
        )


@dataclass
class TelegramConfig:
    """Telegram Bot API notification settings.

    ``bot_token`` / ``chat_id`` may be set here or, preferably, via the
    ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` environment variables (which
    take precedence and keep secrets out of the config file).
    """

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "TelegramConfig":
        data = data or {}
        token = str(data.get("bot_token", "") or "").strip()
        chat_id = str(data.get("chat_id", "") or "").strip()
        # Environment variables win over file values.
        token = os.environ.get("TELEGRAM_BOT_TOKEN", token).strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", chat_id).strip()
        return cls(
            enabled=bool(data.get("enabled", False)),
            bot_token=token,
            chat_id=chat_id,
        )


@dataclass
class AppConfig:
    """Top-level, fully-typed application configuration."""

    chrome_path: str | None = None
    user_data_dir: str | None = None
    profiles: list[str] = field(default_factory=list)
    exclude_profiles: list[str] = field(default_factory=list)
    playlists: list[str] = field(default_factory=list)
    delay_between_profiles: float = 8.0
    delay_between_tabs: float = 2.0
    launch_ready_timeout: float = 20.0
    window: WindowConfig = field(default_factory=WindowConfig)
    grid: GridConfig = field(default_factory=GridConfig)
    playback: PlaybackConfig = field(default_factory=PlaybackConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    # Absolute path of the loaded config file, if any (used for hot reload).
    source_path: Path | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "AppConfig":
        """Build an :class:`AppConfig` from a raw mapping (e.g. parsed YAML)."""
        data = data or {}

        def _str_list(value: Any) -> list[str]:
            if not value:
                return []
            if isinstance(value, str):
                return [value.strip()]
            return [str(v).strip() for v in value if str(v).strip()]

        chrome_path = data.get("chrome_path") or None
        user_data_dir = data.get("user_data_dir") or None

        return cls(
            chrome_path=str(chrome_path) if chrome_path else None,
            user_data_dir=str(user_data_dir) if user_data_dir else None,
            profiles=_str_list(data.get("profiles")),
            exclude_profiles=_str_list(data.get("exclude_profiles")),
            playlists=_str_list(data.get("playlists")),
            delay_between_profiles=float(data.get("delay_between_profiles", 8)),
            delay_between_tabs=float(data.get("delay_between_tabs", 2)),
            launch_ready_timeout=float(data.get("launch_ready_timeout", 20)),
            window=WindowConfig.from_dict(data.get("window")),
            grid=GridConfig.from_dict(data.get("grid")),
            playback=PlaybackConfig.from_dict(data.get("playback")),
            execution=ExecutionConfig.from_dict(data.get("execution")),
            logging=LoggingConfig.from_dict(data.get("logging")),
            report=ReportConfig.from_dict(data.get("report")),
            schedule=ScheduleConfig.from_dict(data.get("schedule")),
            telegram=TelegramConfig.from_dict(data.get("telegram")),
        )

    def validate(self) -> None:
        """Validate cross-field invariants. Raises :class:`ConfigError`."""
        if not self.playlists:
            raise ConfigError(
                "No playlists configured. Add at least one URL under 'playlists' "
                "in the config file."
            )
        if self.delay_between_profiles < 0 or self.delay_between_tabs < 0:
            raise ConfigError("Delays must be non-negative.")
        if self.window.width < 100 or self.window.height < 100:
            raise ConfigError("window.width/height must be >= 100 pixels.")


def load_config(path: str | Path) -> AppConfig:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A validated :class:`AppConfig`.

    Raises:
        ConfigError: If the file is missing or contains invalid values.
    """
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")

    # Load secrets from a project-root .env into the environment (without
    # overriding any variables already set in the real environment).
    _load_dotenv(config_path.parent.parent / ".env")

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise ConfigError(f"Failed to parse YAML config: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise ConfigError("Top-level YAML config must be a mapping/object.")

    config = AppConfig.from_dict(raw)
    config.source_path = config_path
    config.validate()
    return config
