"""Static PNFL league data: teams, divisions, conferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Conference(Enum):
    AFC = "AFC"
    NFC = "NFC"


class Division(Enum):
    AFC_EAST = ("AFC", "East")
    AFC_WEST = ("AFC", "West")
    NFC_EAST = ("NFC", "East")
    NFC_WEST = ("NFC", "West")

    @property
    def conference(self) -> Conference:
        return Conference(self.value[0])


@dataclass(frozen=True)
class Team:
    id: int
    city: str
    division: Division

    @property
    def conference(self) -> Conference:
        return self.division.conference


TEAMS: tuple[Team, ...] = (
    Team(0, "Buffalo", Division.AFC_EAST),
    Team(1, "Jacksonville", Division.AFC_EAST),
    Team(2, "Miami", Division.AFC_EAST),
    Team(3, "New England", Division.AFC_EAST),
    Team(4, "Cincinnati", Division.AFC_WEST),
    Team(5, "Denver", Division.AFC_WEST),
    Team(6, "Las Vegas", Division.AFC_WEST),
    Team(7, "Los Angeles", Division.AFC_WEST),
    Team(8, "Pittsburgh", Division.AFC_WEST),
    Team(9, "Atlanta", Division.NFC_EAST),
    Team(10, "New York", Division.NFC_EAST),
    Team(11, "Philadelphia", Division.NFC_EAST),
    Team(12, "Washington", Division.NFC_EAST),
    Team(13, "Chicago", Division.NFC_WEST),
    Team(14, "Green Bay", Division.NFC_WEST),
    Team(15, "Minnesota", Division.NFC_WEST),
    Team(16, "San Francisco", Division.NFC_WEST),
    Team(17, "Seattle", Division.NFC_WEST),
)

NUM_TEAMS = 18
NUM_WEEKS = 16
GAMES_PER_WEEK = 9

TEAM_BY_CITY = {t.city: t for t in TEAMS}


def lookup_team(city: str) -> Team:
    """Resolve a city name to a Team. Raises ValueError if not found."""
    if city not in TEAM_BY_CITY:
        raise ValueError(f"Unknown team: {city!r}. Valid: {sorted(TEAM_BY_CITY)}")
    return TEAM_BY_CITY[city]
