from pathlib import Path

from pnfl_scheduler.writers.report import TeamScheduleReport, build_schedule_report
from tests.conftest import LEAGUE_5_SLOTS, LEAGUE_6_SLOTS, LEAGUE_7_SLOTS

EXPECTED_ROWS = {
    "5-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=6,
            schedule_rank=3,
            nonconference_rank=10,
            extra_opponent="Philadelphia",
            history_opponent="Washington",
            history_last_played="2047",
            nonconference_opponents=("Green Bay", "New York", "Philadelphia", "San Francisco", "Washington"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=4,
            schedule_rank=18,
            nonconference_rank=12,
            extra_opponent="",
            history_opponent="Seattle",
            history_last_played="2045",
            nonconference_opponents=("Chicago", "New York", "San Francisco", "Seattle"),
        ),
    },
    "6-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=5,
            schedule_rank=1,
            nonconference_rank=4,
            extra_opponent="Washington",
            history_opponent="Minnesota",
            history_last_played="2047",
            nonconference_opponents=("Atlanta", "Minnesota", "New York", "San Francisco", "Washington"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=7,
            schedule_rank=11,
            nonconference_rank=13,
            extra_opponent="",
            history_opponent="Chicago",
            history_last_played="2047",
            nonconference_opponents=("Chicago", "New York", "San Francisco", "Seattle"),
        ),
    },
    "7-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=4,
            schedule_rank=6,
            nonconference_rank=10,
            extra_opponent="Atlanta",
            history_opponent="Seattle",
            history_last_played="2047",
            nonconference_opponents=("Atlanta", "Chicago", "Minnesota", "New York", "Seattle"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=7,
            schedule_rank=12,
            nonconference_rank=13,
            extra_opponent="",
            history_opponent="Chicago",
            history_last_played="2047",
            nonconference_opponents=("Chicago", "Philadelphia", "San Francisco", "Seattle"),
        ),
    },
}


def _league_id(league) -> str:
    if league is LEAGUE_5_SLOTS:
        return "5-free-slots"
    if league is LEAGUE_6_SLOTS:
        return "6-free-slots"
    if league is LEAGUE_7_SLOTS:
        return "7-free-slots"
    raise AssertionError(f"Unexpected league fixture: {league}")


def test_schedule_report_rows_for_one_four_team_and_one_five_team_division(schedule, matchup_plan, league, history):
    report = build_schedule_report(
        schedule=schedule,
        matchup_plan=matchup_plan,
        league=league,
        history=history,
        seed=0,
        scheduler_kind="fixed-matchup",
        config_path=Path("test-config.ini"),
        history_path=Path("test-history.json"),
        elapsed_time_seconds=0.0,
    )

    rows_by_team = {row.team: row for row in report.teams}
    expected_rows = EXPECTED_ROWS[_league_id(league)]

    assert rows_by_team["Buffalo"] == expected_rows["Buffalo"]
    assert rows_by_team["Denver"] == expected_rows["Denver"]
