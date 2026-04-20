from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from ..domain.teams import Division

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = PACKAGE_DIR.parent.parent

DEFAULT_TIME_LIMIT = 900.0

CONFIG_CANDIDATES = [
    Path.cwd() / "generate-schedule.dev.ini",
    Path.cwd() / "generate-schedule.ini",
    PROJECT_DIR / "config" / "generate-schedule.dev.ini",
    PROJECT_DIR / "config" / "generate-schedule.ini",
    PACKAGE_DIR / "generate-schedule.dev.ini",
    PACKAGE_DIR / "generate-schedule.ini",
]


@dataclass(frozen=True)
class Settings:
    TimeLimit: float = DEFAULT_TIME_LIMIT


@dataclass(frozen=True)
class ConferenceRankings:
    AFC: tuple[str, ...]
    NFC: tuple[str, ...]


@dataclass(frozen=True)
class Divisions:
    AFCEast: tuple[str, ...]
    AFCWest: tuple[str, ...]
    NFCEast: tuple[str, ...]
    NFCWest: tuple[str, ...]

    def as_mapping(self) -> dict[Division, tuple[str, ...]]:
        return {
            Division.AFC_EAST: self.AFCEast,
            Division.AFC_WEST: self.AFCWest,
            Division.NFC_EAST: self.NFCEast,
            Division.NFC_WEST: self.NFCWest,
        }


@dataclass(frozen=True)
class AppConfig:
    Settings: Settings
    ConferenceRankings: ConferenceRankings
    Divisions: Divisions


def find_config_path() -> Path:
    return next(
        (c for c in CONFIG_CANDIDATES if c.is_file()),
        CONFIG_CANDIDATES[0],
    )


def _parse_multiline(cp: configparser.ConfigParser, section: str, key: str) -> tuple[str, ...]:
    raw = cp.get(section, key, fallback="")
    return tuple(line.strip() for line in raw.splitlines() if line.strip())


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or find_config_path()
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    return AppConfig(
        Settings=Settings(
            TimeLimit=cp.getfloat("Settings", "TimeLimit", fallback=DEFAULT_TIME_LIMIT),
        ),
        ConferenceRankings=ConferenceRankings(
            AFC=_parse_multiline(cp, "ConferenceRanking", "AFC"),
            NFC=_parse_multiline(cp, "ConferenceRanking", "NFC"),
        ),
        Divisions=Divisions(
            AFCEast=_parse_multiline(cp, "Divisions", "AFCEast"),
            AFCWest=_parse_multiline(cp, "Divisions", "AFCWest"),
            NFCEast=_parse_multiline(cp, "Divisions", "NFCEast"),
            NFCWest=_parse_multiline(cp, "Divisions", "NFCWest"),
        ),
    )
