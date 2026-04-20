"""PNFL league data structures and config-driven team helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum


class Conference(Enum):
    AFC = "AFC"
    NFC = "NFC"


class Division(Enum):
    AFC_EAST = ("AFC", "East", "AFCEast")
    AFC_WEST = ("AFC", "West", "AFCWest")
    NFC_EAST = ("NFC", "East", "NFCEast")
    NFC_WEST = ("NFC", "West", "NFCWest")

    @property
    def conference(self) -> Conference:
        return Conference(self.value[0])

    @property
    def section_name(self) -> str:
        return self.value[2]


DIVISION_ORDER: tuple[Division, ...] = (
    Division.AFC_EAST,
    Division.AFC_WEST,
    Division.NFC_EAST,
    Division.NFC_WEST,
)
DIVISION_BY_SECTION_NAME = {division.section_name: division for division in DIVISION_ORDER}
DIVISION_INDEX = {division: index for index, division in enumerate(DIVISION_ORDER)}
EXPECTED_DIVISION_SIZES = {
    Division.AFC_EAST: 4,
    Division.AFC_WEST: 5,
    Division.NFC_EAST: 4,
    Division.NFC_WEST: 5,
}
FOUR_TEAM_DIVISIONS = frozenset({Division.AFC_EAST, Division.NFC_EAST})
FIVE_TEAM_DIVISIONS = frozenset({Division.AFC_WEST, Division.NFC_WEST})


@dataclass(frozen=True)
class Team:
    id: int
    city: str
    division: Division

    @property
    def conference(self) -> Conference:
        return self.division.conference


NUM_WEEKS = 16
GAMES_PER_WEEK = 9


def _normalize_divisions(
    divisions: Mapping[Division | str, Sequence[str]],
) -> dict[Division, tuple[str, ...]]:
    normalized: dict[Division, tuple[str, ...]] = {}
    for key, cities in divisions.items():
        division = key if isinstance(key, Division) else DIVISION_BY_SECTION_NAME.get(key)
        if division is None:
            valid = ", ".join(sorted(DIVISION_BY_SECTION_NAME))
            raise ValueError(f"Unknown division key {key!r}; expected one of {valid}")
        if division in normalized:
            raise ValueError(f"Division {division.section_name} defined more than once")
        normalized[division] = tuple(city.strip() for city in cities if city.strip())

    missing = [division.section_name for division in DIVISION_ORDER if division not in normalized]
    if missing:
        raise ValueError(f"Missing divisions: {missing}")
    return normalized


def build_teams(divisions: Mapping[Division | str, Sequence[str]]) -> tuple[Team, ...]:
    normalized = _normalize_divisions(divisions)
    teams: list[Team] = []
    seen_cities: set[str] = set()

    for division in DIVISION_ORDER:
        cities = normalized[division]
        expected_size = EXPECTED_DIVISION_SIZES[division]
        if len(cities) != expected_size:
            raise ValueError(
                f"{division.section_name} must list exactly {expected_size} teams; got {len(cities)}"
            )
        for city in cities:
            if city in seen_cities:
                raise ValueError(f"Duplicate team in divisions config: {city}")
            teams.append(Team(id=len(teams), city=city, division=division))
            seen_cities.add(city)

    if len(teams) != 18:
        raise ValueError(f"Expected exactly 18 teams across all divisions, got {len(teams)}")
    return tuple(teams)


def team_by_city(teams: Sequence[Team]) -> dict[str, Team]:
    return {team.city: team for team in teams}


def team_by_id(teams: Sequence[Team]) -> dict[int, Team]:
    return {team.id: team for team in teams}


def lookup_team(teams: Sequence[Team], city: str) -> Team:
    by_city = team_by_city(teams)
    if city not in by_city:
        raise ValueError(f"Unknown team: {city!r}. Valid: {sorted(by_city)}")
    return by_city[city]


def ordered_teams(teams: Sequence[Team]) -> list[Team]:
    return sorted(teams, key=lambda team: (DIVISION_INDEX[team.division], team.city))
