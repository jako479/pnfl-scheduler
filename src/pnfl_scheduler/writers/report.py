from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import League, Team, ordered_teams
from pnfl_scheduler.domain.schedule import Schedule
from pnfl_scheduler.schedulers.types import MatchupPlan


@dataclass(frozen=True)
class TeamScheduleReport:
    team: str
    conference_rank: int
    schedule_rank: int
    nonconference_rank: int
    extra_opponent: str
    history_opponent: str
    history_last_played: str
    nonconference_opponents: tuple[str, ...]
    nonconference_game_ranks: str


@dataclass(frozen=True)
class ScheduleReport:
    seed: int
    scheduler_kind: str
    config_path: str
    history_path: str
    elapsed_time_seconds: float
    teams: tuple[TeamScheduleReport, ...]
    command_line: str | None = None


def _nonconference_opponents(schedule: Schedule, team: Team) -> tuple[Team, ...]:
    opponents = {
        (game.away if game.home == team else game.home)
        for game in schedule.games_for(team)
        if (game.away if game.home == team else game.home).conference != team.conference
    }
    return tuple(sorted(opponents, key=lambda opponent: opponent.metro))


def _schedule_rank_by_team(
    schedule: Schedule,
    league: League,
) -> tuple[dict[Team, int], dict[Team, int], dict[Team, int]]:
    rank_by_team: dict[Team, int] = {team: league.rankings.rank_of(team) for team in league.teams}

    score_by_team: dict[Team, int] = {}
    for team in league.teams:
        score_by_team[team] = sum(rank_by_team[(game.away if game.home == team else game.home)] for game in schedule.games_for(team))

    ordered = sorted(league.teams, key=lambda t: (score_by_team[t], t.metro))
    schedule_rank_by_team = {team: idx + 1 for idx, team in enumerate(ordered)}

    nonconference_average_by_team: dict[Team, float] = {}
    for team in league.teams:
        opponents = _nonconference_opponents(schedule, team)
        nonconference_average_by_team[team] = sum(rank_by_team[opp] for opp in opponents) / len(opponents)

    nonconference_ordered = sorted(
        league.teams,
        key=lambda t: (nonconference_average_by_team[t], t.metro),
    )
    nonconference_rank_by_team = {team: idx + 1 for idx, team in enumerate(nonconference_ordered)}

    return rank_by_team, schedule_rank_by_team, nonconference_rank_by_team


def build_schedule_report(
    *,
    schedule: Schedule,
    matchup_plan: MatchupPlan,
    league: League,
    history: NonConfHistory | None,
    seed: int,
    scheduler_kind: str,
    config_path: Path,
    history_path: Path,
    elapsed_time_seconds: float,
    command_line: str | None = None,
) -> ScheduleReport:
    teams = ordered_teams(league.teams)
    rank_by_team, schedule_rank_by_team, nonconference_rank_by_team = _schedule_rank_by_team(schedule, league)

    extra_opponent_by_team: dict[Team, Team] = {}
    for team_a, team_b in matchup_plan.extra_nonconference_pairs:
        extra_opponent_by_team[team_a] = team_b
        extra_opponent_by_team[team_b] = team_a

    history_opponent_by_team: dict[Team, Team] = {}
    for team_a, team_b in matchup_plan.history_nonconference_pairs:
        history_opponent_by_team[team_a] = team_b
        history_opponent_by_team[team_b] = team_a

    rows: list[TeamScheduleReport] = []
    for team in teams:
        nonconference_opponents = _nonconference_opponents(schedule, team)
        nonconference_game_ranks = ",".join(str(rank) for rank in sorted(rank_by_team[opp] for opp in nonconference_opponents))
        extra_opponent = extra_opponent_by_team.get(team)
        history_opponent = history_opponent_by_team.get(team)
        extra_opponent_metro = extra_opponent.metro if extra_opponent is not None else "-"
        if history_opponent is None:
            history_opponent_metro = "-"
            history_last_played = "-"
        else:
            history_opponent_metro = history_opponent.metro
            if history is None:
                history_last_played = "unknown"
            else:
                last_played = history.last_played(team, history_opponent)
                history_last_played = "never" if last_played is None else str(last_played)

        rows.append(
            TeamScheduleReport(
                team=team.metro,
                conference_rank=rank_by_team[team],
                schedule_rank=schedule_rank_by_team[team],
                nonconference_rank=nonconference_rank_by_team[team],
                nonconference_game_ranks=nonconference_game_ranks,
                extra_opponent=extra_opponent_metro,
                history_opponent=history_opponent_metro,
                history_last_played=history_last_played,
                nonconference_opponents=tuple(opponent.metro for opponent in nonconference_opponents),
            )
        )

    return ScheduleReport(
        seed=seed,
        scheduler_kind=scheduler_kind,
        command_line=command_line,
        config_path=str(config_path),
        history_path=str(history_path),
        elapsed_time_seconds=elapsed_time_seconds,
        teams=tuple(rows),
    )


@dataclass(frozen=True)
class TxtReportWriter:
    path: Path | str

    def write(self, report: ScheduleReport) -> None:
        Path(self.path).write_text(self.render(report), encoding="utf-8")

    def render(self, report: ScheduleReport) -> str:
        lines = [
            "PNFL Schedule Report",
            "====================",
            "",
            f"Seed: {report.seed}",
            f"Scheduler kind: {report.scheduler_kind}",
            f"Command line: {report.command_line or '-'}",
            f"Config path: {report.config_path or '-'}",
            f"History path: {report.history_path or '-'}",
            f"Elapsed time (seconds): {report.elapsed_time_seconds:.3f}",
            "",
        ]

        headers = (
            ("Team", 15),
            ("Conf Rank", 10),
            ("Sched Rank", 11),
            ("Non-conf Rank", 13),
            ("NC Game Ranks", 15),
            ("Extra Opponent", 15),
            ("H2H Opponent", 15),
            ("Last Played", 12),
            ("Non-Conference Opponents", 0),
        )
        header_line = "  ".join(name.ljust(width) if width else name for name, width in headers)
        rule_line = "  ".join(("-" * len(name)).ljust(width) if width else "-" * len(name) for name, width in headers)
        lines.extend([header_line, rule_line])

        for row in report.teams:
            opponents = ", ".join(row.nonconference_opponents)
            lines.append(
                "  ".join(
                    [
                        row.team.ljust(15),
                        str(row.conference_rank).ljust(10),
                        str(row.schedule_rank).ljust(11),
                        str(row.nonconference_rank).ljust(13),
                        row.nonconference_game_ranks.ljust(15),
                        row.extra_opponent.ljust(15),
                        row.history_opponent.ljust(15),
                        row.history_last_played.ljust(12),
                        opponents,
                    ]
                )
            )

        lines.append("")
        return "\n".join(lines)
