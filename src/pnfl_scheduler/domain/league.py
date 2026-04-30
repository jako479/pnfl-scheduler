"""League structure: conferences, divisions, teams, and conference rankings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

TOTAL_TEAMS = 18
TEAMS_PER_CONFERENCE = 9


class Conference(Enum):
    AFC = "AFC"
    NFC = "NFC"


class Division(Enum):
    AFC_EAST = "AFC East"
    AFC_WEST = "AFC West"
    NFC_EAST = "NFC East"
    NFC_WEST = "NFC West"

    @property
    def conference(self) -> Conference:
        return _DIVISION_META[self].conference

    @property
    def expected_size(self) -> int:
        return _DIVISION_META[self].expected_size


@dataclass(frozen=True)
class _DivisionMeta:
    conference: Conference
    expected_size: int


_DIVISION_META: dict[Division, _DivisionMeta] = {
    Division.AFC_EAST: _DivisionMeta(Conference.AFC, 4),
    Division.AFC_WEST: _DivisionMeta(Conference.AFC, 5),
    Division.NFC_EAST: _DivisionMeta(Conference.NFC, 4),
    Division.NFC_WEST: _DivisionMeta(Conference.NFC, 5),
}

DIVISION_ORDER: tuple[Division, ...] = (
    Division.AFC_EAST,
    Division.AFC_WEST,
    Division.NFC_EAST,
    Division.NFC_WEST,
)
DIVISION_INDEX = {division: index for index, division in enumerate(DIVISION_ORDER)}


@dataclass(frozen=True)
class ConferenceRankings:
    """Ordered standings for each conference; index 0 is the top-ranked team."""

    afc: tuple[Team, ...]
    nfc: tuple[Team, ...]

    def rank_of(self, team: Team) -> int:
        """Return 1-based rank within `team`'s conference."""
        ranking = self.afc if team.conference == Conference.AFC else self.nfc
        return ranking.index(team) + 1


@dataclass(frozen=True)
class Team:
    metro: str
    division: Division

    @property
    def conference(self) -> Conference:
        return self.division.conference


def build_teams(divisions: Mapping[str, Sequence[str]]) -> tuple[Team, ...]:
    """Build the canonical teams tuple from division-keyed metro lists.

    Validates that all four divisions are present, that each has its expected
    size, and that no metro is duplicated. Teams are returned in division order.
    """
    by_division: dict[Division, Sequence[str]] = {}
    for key, metros in divisions.items():
        try:
            division = Division[key]
        except KeyError as exc:
            valid = ", ".join(d.name for d in DIVISION_ORDER)
            raise ValueError(f"Unknown division key {key!r}; expected one of {valid}") from exc
        by_division[division] = metros

    missing = [d.name for d in DIVISION_ORDER if d.name not in divisions]
    if missing:
        raise ValueError(f"Missing divisions: {missing}")

    teams: list[Team] = []
    seen_metros: set[str] = set()

    for division in DIVISION_ORDER:
        metros = tuple(m.strip() for m in by_division[division] if m.strip())
        if len(metros) != division.expected_size:
            raise ValueError(f"{division.name} must list exactly {division.expected_size} teams; got {len(metros)}")
        for metro in metros:
            if metro in seen_metros:
                raise ValueError(f"Duplicate team in divisions config: {metro}")
            teams.append(Team(metro=metro, division=division))
            seen_metros.add(metro)

    expected_teams = sum(d.expected_size for d in DIVISION_ORDER)
    if len(teams) != expected_teams:
        raise ValueError(f"Expected exactly {expected_teams} teams across all divisions, got {len(teams)}")
    return tuple(teams)


def team_by_metro(teams: Sequence[Team]) -> dict[str, Team]:
    return {team.metro: team for team in teams}


def lookup_team(teams: Sequence[Team], metro: str) -> Team:
    by_metro = team_by_metro(teams)
    if metro not in by_metro:
        raise ValueError(f"Unknown team: {metro!r}. Valid: {sorted(by_metro)}")
    return by_metro[metro]


def ordered_teams(teams: Sequence[Team]) -> list[Team]:
    return sorted(teams, key=lambda team: (DIVISION_INDEX[team.division], team.metro))


@dataclass(frozen=True)
class League:
    """The set of teams plus the AFC/NFC standings used for strength-of-schedule math."""

    teams: tuple[Team, ...]
    rankings: ConferenceRankings


def build_league(
    divisions: Mapping[str, Sequence[str]],  # section-name ("AFCEast") -> team metros
    afc_ranking: Sequence[str],  # ranked metros
    nfc_ranking: Sequence[str],
) -> League:
    """Build a `League` from raw INI-style division and ranking inputs.

    Each ranking must list all teams of its conference exactly once.
    """
    teams = build_teams(divisions)
    afc_ranked = tuple(lookup_team(teams, metro) for metro in afc_ranking)
    nfc_ranked = tuple(lookup_team(teams, metro) for metro in nfc_ranking)

    _validate_ranking(afc_ranked, Conference.AFC)
    _validate_ranking(nfc_ranked, Conference.NFC)

    return League(
        teams=teams,
        rankings=ConferenceRankings(afc=afc_ranked, nfc=nfc_ranked),
    )


def _validate_ranking(ranking: tuple[Team, ...], conference: Conference) -> None:
    label = conference.value
    if len(ranking) != TEAMS_PER_CONFERENCE:
        raise ValueError(f"{label} ranking must have {TEAMS_PER_CONFERENCE} teams; got {len(ranking)}")
    if len(set(ranking)) != len(ranking):
        duplicates = sorted({t.metro for t in ranking if ranking.count(t) > 1})
        raise ValueError(f"{label} ranking has duplicate teams: {duplicates}")
    wrong_conf = [t.metro for t in ranking if t.conference != conference]
    if wrong_conf:
        raise ValueError(f"{label} ranking contains teams from wrong conference: {sorted(wrong_conf)}")
