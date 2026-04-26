from collections.abc import Sequence
from dataclasses import dataclass

from pnfl_scheduler.domain.league import Team
from pnfl_scheduler.domain.schedule import Schedule

Matchup = tuple[Team, Team]
Matchups = Sequence[Matchup]


def make_matchup(team_a: Team, team_b: Team) -> Matchup:
    a, b = sorted((team_a, team_b), key=lambda t: t.metro)
    return (a, b)


@dataclass(frozen=True)
class MatchupPlan:
    matchups: Matchups
    fixed_nonconference_pairs: frozenset[Matchup] = frozenset()
    extra_nonconference_pairs: frozenset[Matchup] = frozenset()
    history_nonconference_pairs: frozenset[Matchup] = frozenset()


@dataclass(frozen=True)
class SchedulerResult:
    schedule: Schedule
    matchup_plan: MatchupPlan
