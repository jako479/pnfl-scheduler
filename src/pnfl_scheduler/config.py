from __future__ import annotations

import configparser
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from pnfl_scheduler.domain.league import League, build_league

StrPath = str | PathLike[str]

CONFIG_CANDIDATES = [
    Path.cwd() / "generate-schedule.dev.ini",
    Path.cwd() / "generate-schedule.ini",
    Path.cwd() / "config" / "generate-schedule.dev.ini",
    Path.cwd() / "config" / "generate-schedule.ini",
]

HISTORY_CANDIDATES = [
    Path.cwd() / "nonconf_history.json",
    Path.cwd() / "data" / "nonconf_history.json",
]

DEFAULT_TIME_LIMIT = 1800.0


class ConfigError(Exception):
    """The config file is missing, or present but invalid."""


@dataclass(frozen=True)
class Config:
    time_limit: float = DEFAULT_TIME_LIMIT


def load_config(path: StrPath | None = None) -> Config:
    cp = _read_config(_resolve_config_path(path))
    return Config(time_limit=_time_limit(cp))


def load_league(path: StrPath | None = None) -> League:
    resolved = _resolve_config_path(path)
    cp = _read_config(resolved)
    _require_section(cp, resolved, "Divisions")
    _require_section(cp, resolved, "ConferenceRanking")
    divisions = {key: _parse_multiline(cp, "Divisions", key) for key in cp.options("Divisions")}
    afc_ranking = _required_multiline(cp, resolved, "ConferenceRanking", "AFC")
    nfc_ranking = _required_multiline(cp, resolved, "ConferenceRanking", "NFC")
    try:
        return build_league(divisions, afc_ranking, nfc_ranking)
    except ValueError as error:
        raise ConfigError(f"Config file '{resolved}' has invalid league data: {error}") from error


def find_config_path() -> Path:
    """Return the first existing config file, or raise ConfigError if none exist."""
    return _resolve_config_path(None)


def find_history_path() -> Path:
    return next(
        (c for c in HISTORY_CANDIDATES if c.is_file()),
        HISTORY_CANDIDATES[0],
    )


def _resolve_config_path(path: StrPath | None) -> Path:
    if path is not None:
        resolved = Path(path)
        if not resolved.is_file():
            raise ConfigError(f"Config file not found: '{resolved}'.")
        return resolved
    found = next((c for c in CONFIG_CANDIDATES if c.is_file()), None)
    if found is None:
        candidates = "\n  ".join(str(c) for c in CONFIG_CANDIDATES)
        raise ConfigError("No config file found. Pass --config, or create one of:\n  " + candidates)
    return found


def _read_config(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp.optionxform = str  # type: ignore[assignment]
    try:
        cp.read(path, encoding="utf-8")
    except configparser.Error as error:
        raise ConfigError(f"Config file '{path}' is not valid INI: {error}") from error
    return cp


def _time_limit(cp: configparser.ConfigParser) -> float:
    raw = cp.get("Settings", "TimeLimit", fallback=None)
    if raw is None:
        return DEFAULT_TIME_LIMIT
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"Invalid 'TimeLimit' value: {raw!r} (expected a number).") from None


def _require_section(cp: configparser.ConfigParser, path: Path, section: str) -> None:
    if not cp.has_section(section):
        raise ConfigError(f"Config file '{path}' is missing the required [{section}] section.")


def _required_multiline(cp: configparser.ConfigParser, path: Path, section: str, key: str) -> tuple[str, ...]:
    if not cp.has_option(section, key):
        raise ConfigError(f"Config file '{path}' is missing required setting '{key}' in [{section}].")
    values = _parse_multiline(cp, section, key)
    if not values:
        raise ConfigError(f"Config file '{path}' has an empty '{key}' in [{section}].")
    return values


def _parse_multiline(cp: configparser.ConfigParser, section: str, key: str) -> tuple[str, ...]:
    raw = cp.get(section, key, fallback="")
    return tuple(line.strip() for line in raw.splitlines() if line.strip())
