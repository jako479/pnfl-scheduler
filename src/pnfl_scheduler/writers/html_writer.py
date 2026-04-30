"""HTML schedule writer (week-by-week and team-by-team navigation pages)."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from os import PathLike
from pathlib import Path
from typing import TypeVar

from pnfl_scheduler.domain.league import Team, ordered_teams
from pnfl_scheduler.domain.schedule import Game, Schedule

StrPath = str | PathLike[str]

T = TypeVar("T")


def _chunked(items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _week_games(schedule: Schedule) -> dict[int, list[Game]]:
    games_by_week: dict[int, list[Game]] = {}
    for game in sorted(schedule.games, key=lambda g: (g.week, g.away.metro, g.home.metro)):
        games_by_week.setdefault(game.week, []).append(game)
    return games_by_week


def _team_games(schedule: Schedule) -> dict[Team, list[Game]]:
    teams = _schedule_teams(schedule)
    return {team: sorted(schedule.games_for(team), key=lambda g: g.week) for team in teams}


def _schedule_teams(schedule: Schedule) -> list[Team]:
    teams = {team for game in schedule.games for team in (game.home, game.away)}
    return ordered_teams(tuple(teams))


def _format_week_game(game: Game) -> str:
    return f"{game.away.metro} at {game.home.metro}"


def _format_team_game(team: Team, game: Game) -> str:
    opponent = game.away if game.home == team else game.home
    prefix = "vs" if game.home == team else "at"
    return f"Week {game.week}: {prefix} {opponent.metro}"


def _render_nav_links(labels: list[tuple[str, str]], columns: int, width: int) -> list[str]:
    rows: list[str] = []
    for chunk in _chunked(labels, columns):
        rows.append(
            "".join(
                f'<A HREF="#{target}">{escape(label)}</A>' + (" " * max(width - len(label), 0))
                for target, label in chunk
            ).rstrip()
        )
    return rows


def _named_header(name: str, label: str, width: int) -> str:
    return f'<A NAME="{escape(name)}"></A><b>{escape(label)}</b>' + (" " * max(width - len(label), 0))


@dataclass(frozen=True)
class HtmlScheduleWriter:
    """Writes a navigation-rich HTML schedule (week-by-week + team-by-team) to `path`."""

    path: StrPath
    league_name: str = "PNFL"
    season_label: str | None = None

    def write(self, schedule: Schedule) -> None:
        output_path = Path(self.path)
        output_path.write_text(self.render(schedule), encoding="utf-8")

    def render(self, schedule: Schedule) -> str:
        week_section = self._render_week_by_week(schedule)
        team_section = self._render_team_by_team(schedule)
        title = self.league_name if self.season_label is None else f"{self.league_name}, {self.season_label}"

        lines = [
            "<html>",
            "<head>",
            f"<title>{escape(title)}</title>",
            "</head>",
            "<body><pre>",
            *week_section,
            "",
            "",
            *team_section,
            "</pre></body>",
            "</html>",
            "",
        ]
        return "\n".join(lines)

    def _render_week_by_week(self, schedule: Schedule) -> list[str]:
        games_by_week = _week_games(schedule)
        weeks = sorted(games_by_week)
        week_columns = _chunked(weeks, 2)
        col_width = 42
        season = f"<EM>{escape(self.season_label)}</EM>" if self.season_label else ""

        lines = [
            f"<H1>{escape(self.league_name)}",
            "<A NAME='W0'>League Schedule by week</A></H1>",
        ]
        if season:
            lines.append(season)
        lines.extend(
            [
                "",
                "<h2>Week by Week</h2>",
                "<h3><a href='#T0'>Go to Team by Team schedule</a></h3>",
                *_render_nav_links([(f"W{week}", f"Week {week}") for week in weeks], columns=4, width=26),
                "",
            ]
        )

        for week_pair in week_columns:
            left_week = week_pair[0]
            right_week = week_pair[1] if len(week_pair) > 1 else None

            left_header = _named_header(f"W{left_week}", f"Week {left_week}", col_width)
            right_header = (
                _named_header(f"W{right_week}", f"Week {right_week}", col_width) if right_week is not None else ""
            )
            lines.append(left_header + right_header)

            left_games = [_format_week_game(game) for game in games_by_week[left_week]]
            right_games = (
                [_format_week_game(game) for game in games_by_week.get(right_week, [])]
                if right_week is not None
                else []
            )
            row_count = max(len(left_games), len(right_games))
            for idx in range(row_count):
                left = left_games[idx] if idx < len(left_games) else ""
                right = right_games[idx] if idx < len(right_games) else ""
                lines.append(left.ljust(col_width) + right)
            lines.extend(
                [
                    '<em><A HREF="#W0">Back to top</A></em>',
                    "",
                ]
            )

        return lines

    def _render_team_by_team(self, schedule: Schedule) -> list[str]:
        games_by_team = _team_games(schedule)
        teams = _schedule_teams(schedule)
        team_columns = _chunked(teams, 2)
        col_width = 42
        season = f"<EM>{escape(self.season_label)}</EM>" if self.season_label else ""

        lines = [
            f"<H1>{escape(self.league_name)}",
            "<A NAME='T0'>League Schedule by team</A></H1>",
        ]
        if season:
            lines.append(season)
        lines.extend(
            [
                "",
                "<h2>Team by Team</h2>",
                "<h3><a href='#W0'>Go to Week by Week schedule</a></h3>",
                *_render_nav_links(
                    [(f"T{idx}", team.metro) for idx, team in enumerate(teams, start=1)], columns=2, width=34
                ),
                "",
            ]
        )

        for index, team_pair in enumerate(team_columns):
            left_team = team_pair[0]
            left_anchor = 2 * index + 1
            right_team = team_pair[1] if len(team_pair) > 1 else None
            right_anchor = left_anchor + 1 if right_team is not None else None

            left_header = _named_header(f"T{left_anchor}", left_team.metro, col_width)
            right_header = (
                _named_header(f"T{right_anchor}", right_team.metro, col_width) if right_team is not None else ""
            )
            lines.append(left_header + right_header)

            left_games = [_format_team_game(left_team, game) for game in games_by_team[left_team]]
            right_games = (
                [_format_team_game(right_team, game) for game in games_by_team[right_team]]
                if right_team is not None
                else []
            )
            row_count = max(len(left_games), len(right_games))
            for idx in range(row_count):
                left = left_games[idx] if idx < len(left_games) else ""
                right = right_games[idx] if idx < len(right_games) else ""
                lines.append(left.ljust(col_width) + right)
            lines.extend(
                [
                    '<em><A HREF="#T0">Back to top</A></em>',
                    "",
                ]
            )

        return lines
