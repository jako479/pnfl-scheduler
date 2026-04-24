from collections.abc import Sequence
from dataclasses import dataclass

from pnfl_scheduler.domain.schedule import Schedule
from pnfl_scheduler.domain.teams import Team

Matchup = tuple[Team, Team]
Matchups = Sequence[Matchup]


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
