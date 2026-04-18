from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..app.config import ConferenceRanking
from ..domain.history import NonConfHistory
from ..domain.schedule import Schedule
from ..domain.teams import Division, TEAMS, Team
from ..schedulers.two_phase import (
    _fixed_rank_pairs,
    _normalize_conference_ranking,
    _rank_by_id,
    _solve_four_team_extra_rank_pairs,
)


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


@dataclass(frozen=True)
class ScheduleReport:
    seed: int
    scheduler_kind: str
    config_path: str | None
    history_path: str | None
    elapsed_time_seconds: float
    teams: tuple[TeamScheduleReport, ...]
    command_line: str | None = None


def _canonical_pair(team_a: Team, team_b: Team) -> tuple[int, int]:
    return (min(team_a.id, team_b.id), max(team_a.id, team_b.id))


def _ordered_teams() -> list[Team]:
    division_order = {
        Division.AFC_EAST: 0,
        Division.AFC_WEST: 1,
        Division.NFC_EAST: 2,
        Division.NFC_WEST: 3,
    }
    return sorted(TEAMS, key=lambda team: (division_order[team.division], team.city))


def _nonconference_opponents(schedule: Schedule, team: Team) -> tuple[Team, ...]:
    opponents = {
        (game.away if game.home == team else game.home)
        for game in schedule.games_for(team)
        if (game.away if game.home == team else game.home).conference != team.conference
    }
    return tuple(sorted(opponents, key=lambda opponent: opponent.city))


def _history_pairs(
    schedule: Schedule,
    conference_ranking: ConferenceRanking,
) -> set[tuple[int, int]]:
    ranked_teams_by_conf = _normalize_conference_ranking(conference_ranking)
    rank_by_id = _rank_by_id(ranked_teams_by_conf)
    fixed_pairs = _fixed_rank_pairs(ranked_teams_by_conf)
    extra_pairs = _solve_four_team_extra_rank_pairs(
        ranked_teams_by_conf=ranked_teams_by_conf,
        rank_by_id=rank_by_id,
        forbidden_pairs=fixed_pairs,
    )
    scheduled_nonconference = {
        _canonical_pair(game.home, game.away)
        for game in schedule.games
        if game.home.conference != game.away.conference
    }
    return scheduled_nonconference - fixed_pairs - extra_pairs


def _extra_pairs(conference_ranking: ConferenceRanking) -> set[tuple[int, int]]:
    ranked_teams_by_conf = _normalize_conference_ranking(conference_ranking)
    rank_by_id = _rank_by_id(ranked_teams_by_conf)
    fixed_pairs = _fixed_rank_pairs(ranked_teams_by_conf)
    return _solve_four_team_extra_rank_pairs(
        ranked_teams_by_conf=ranked_teams_by_conf,
        rank_by_id=rank_by_id,
        forbidden_pairs=fixed_pairs,
    )


def _schedule_rank_by_team(
    schedule: Schedule,
    conference_ranking: ConferenceRanking,
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    ranked_teams_by_conf = _normalize_conference_ranking(conference_ranking)
    rank_by_id = _rank_by_id(ranked_teams_by_conf)

    score_by_team: dict[int, int] = {}
    for team in TEAMS:
        score_by_team[team.id] = sum(
            rank_by_id[(game.away if game.home == team else game.home).id]
            for game in schedule.games_for(team)
        )

    ordered = sorted(TEAMS, key=lambda team: (score_by_team[team.id], team.city))
    schedule_rank_by_team = {team.id: idx + 1 for idx, team in enumerate(ordered)}

    nonconference_average_by_team: dict[int, float] = {}
    for team in TEAMS:
        nonconference_opponents = _nonconference_opponents(schedule, team)
        nonconference_average_by_team[team.id] = sum(
            rank_by_id[opponent.id] for opponent in nonconference_opponents
        ) / len(nonconference_opponents)

    nonconference_ordered = sorted(
        TEAMS,
        key=lambda team: (nonconference_average_by_team[team.id], team.city),
    )
    nonconference_rank_by_team = {team.id: idx + 1 for idx, team in enumerate(nonconference_ordered)}

    return rank_by_id, schedule_rank_by_team, nonconference_rank_by_team


def build_schedule_report(
    *,
    schedule: Schedule,
    conference_ranking: ConferenceRanking,
    history: NonConfHistory | None,
    seed: int,
    scheduler_kind: str,
    config_path: Path | None,
    history_path: Path | None,
    elapsed_time_seconds: float,
    command_line: str | None = None,
) -> ScheduleReport:
    rank_by_id, schedule_rank_by_team, nonconference_rank_by_team = _schedule_rank_by_team(
        schedule, conference_ranking
    )
    extra_pairs = _extra_pairs(conference_ranking)
    history_pairs = _history_pairs(schedule, conference_ranking)
    extra_opponent_by_team: dict[int, Team] = {}
    for team_a_id, team_b_id in extra_pairs:
        team_a = next(team for team in TEAMS if team.id == team_a_id)
        team_b = next(team for team in TEAMS if team.id == team_b_id)
        extra_opponent_by_team[team_a.id] = team_b
        extra_opponent_by_team[team_b.id] = team_a
    history_opponent_by_team: dict[int, Team] = {}
    for team_a_id, team_b_id in history_pairs:
        team_a = next(team for team in TEAMS if team.id == team_a_id)
        team_b = next(team for team in TEAMS if team.id == team_b_id)
        history_opponent_by_team[team_a.id] = team_b
        history_opponent_by_team[team_b.id] = team_a

    rows: list[TeamScheduleReport] = []
    for team in _ordered_teams():
        extra_opponent = extra_opponent_by_team.get(team.id)
        history_opponent = history_opponent_by_team.get(team.id)
        extra_opponent_city = extra_opponent.city if extra_opponent is not None else ""
        if history_opponent is None:
            history_opponent_city = "-"
            history_last_played = "-"
        else:
            history_opponent_city = history_opponent.city
            if history is None:
                history_last_played = "unknown"
            else:
                last_played = history.last_played(team, history_opponent)
                history_last_played = "never" if last_played is None else str(last_played)

        rows.append(
            TeamScheduleReport(
                team=team.city,
                conference_rank=rank_by_id[team.id],
                schedule_rank=schedule_rank_by_team[team.id],
                nonconference_rank=nonconference_rank_by_team[team.id],
                extra_opponent=extra_opponent_city,
                history_opponent=history_opponent_city,
                history_last_played=history_last_played,
                nonconference_opponents=tuple(
                    opponent.city for opponent in _nonconference_opponents(schedule, team)
                ),
            )
        )

    return ScheduleReport(
        seed=seed,
        scheduler_kind=scheduler_kind,
        command_line=command_line,
        config_path=str(config_path) if config_path is not None else None,
        history_path=str(history_path) if history_path is not None else None,
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
                        row.extra_opponent.ljust(15),
                        row.history_opponent.ljust(15),
                        row.history_last_played.ljust(12),
                        opponents,
                    ]
                )
            )

        lines.append("")
        return "\n".join(lines)
