from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = PACKAGE_DIR.parent.parent

DEFAULT_TIME_LIMIT = 3600.0

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
class ConferenceRanking:
    AFC: list[str]
    NFC: list[str]


@dataclass(frozen=True)
class AppConfig:
    Settings: Settings
    ConferenceRanking: ConferenceRanking


def find_config_path() -> Path:
    return next(
        (c for c in CONFIG_CANDIDATES if c.is_file()),
        CONFIG_CANDIDATES[0],
    )


def _parse_ranking(cp: configparser.ConfigParser, key: str) -> list[str]:
    raw = cp.get("ConferenceRanking", key, fallback="")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or find_config_path()
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    return AppConfig(
        Settings=Settings(
            TimeLimit=cp.getfloat("Settings", "TimeLimit", fallback=DEFAULT_TIME_LIMIT),
        ),
        ConferenceRanking=ConferenceRanking(
            AFC=_parse_ranking(cp, "AFC"),
            NFC=_parse_ranking(cp, "NFC"),
        ),
    )
