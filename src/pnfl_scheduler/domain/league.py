from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pnfl_scheduler.domain.teams import Conference, Team, build_teams, lookup_team


@dataclass(frozen=True)
class ConferenceRankings:
    afc: tuple[Team, ...]
    nfc: tuple[Team, ...]

    def rank_of(self, team: Team) -> int:
        ranking = self.afc if team.conference == Conference.AFC else self.nfc
        return ranking.index(team) + 1


@dataclass(frozen=True)
class League:
    teams: tuple[Team, ...]
    rankings: ConferenceRankings


def build_league(
    divisions: Mapping[str, Sequence[str]],  # section-name ("AFCEast") -> team metros
    afc_ranking: Sequence[str],  # ranked metros
    nfc_ranking: Sequence[str],
) -> League:
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
    if len(ranking) != 9:
        raise ValueError(f"{label} ranking must have 9 teams; got {len(ranking)}")
    if len(set(ranking)) != len(ranking):
        duplicates = sorted({t.metro for t in ranking if ranking.count(t) > 1})
        raise ValueError(f"{label} ranking has duplicate teams: {duplicates}")
    wrong_conf = [t.metro for t in ranking if t.conference != conference]
    if wrong_conf:
        raise ValueError(f"{label} ranking contains teams from wrong conference: {sorted(wrong_conf)}")
