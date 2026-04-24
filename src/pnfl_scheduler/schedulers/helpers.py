from pnfl_scheduler.domain.teams import FOUR_TEAM_DIVISIONS, Team
from pnfl_scheduler.schedulers.types import Matchup


def canonical_pair(team_a: Team, team_b: Team) -> Matchup:
    a, b = sorted((team_a, team_b), key=lambda t: t.metro)
    return (a, b)


def required_nonconference_games(team: Team) -> int:
    return 5 if team.division in FOUR_TEAM_DIVISIONS else 4
