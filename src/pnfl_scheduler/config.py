from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from pnfl_scheduler.domain.league import League, build_league

CONFIG_CANDIDATES = [
    Path.cwd() / "generate-schedule.dev.ini",
    Path.cwd() / "generate-schedule.ini",
    Path.cwd() / "config" / "generate-schedule.dev.ini",
    Path.cwd() / "config" / "generate-schedule.ini",
]

DEFAULT_TIME_LIMIT = 900.0


@dataclass(frozen=True)
class Settings:
    time_limit: float = DEFAULT_TIME_LIMIT


def load_settings(path: Path | None = None) -> Settings:
    cp = _read_config(path or find_config_path())
    return Settings(
        time_limit=cp.getfloat("Settings", "TimeLimit", fallback=DEFAULT_TIME_LIMIT),
    )


def load_league(path: Path | None = None) -> League:
    cp = _read_config(path or find_config_path())
    divisions = {key: _parse_multiline(cp, "Divisions", key) for key in cp.options("Divisions")}
    afc_ranking = _parse_multiline(cp, "ConferenceRanking", "AFC")
    nfc_ranking = _parse_multiline(cp, "ConferenceRanking", "NFC")
    return build_league(divisions, afc_ranking, nfc_ranking)


def find_config_path() -> Path:
    return next(
        (c for c in CONFIG_CANDIDATES if c.is_file()),
        CONFIG_CANDIDATES[0],
    )


def _read_config(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp.optionxform = str  # type: ignore[assignment]
    cp.read(path, encoding="utf-8")
    return cp


def _parse_multiline(cp: configparser.ConfigParser, section: str, key: str) -> tuple[str, ...]:
    raw = cp.get(section, key, fallback="")
    return tuple(line.strip() for line in raw.splitlines() if line.strip())
