from tests.conftest import CONFIG_5_SLOTS, CONFIG_6_SLOTS, CONFIG_7_SLOTS

from pnfl_scheduler.writers.report import TeamScheduleReport, build_schedule_report

EXPECTED_ROWS = {
    "5-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=6,
            schedule_rank=6,
            nonconference_rank=11,
            extra_opponent="Philadelphia",
            history_opponent="Washington",
            history_last_played="2047",
            nonconference_opponents=("Minnesota", "New York", "Philadelphia", "Seattle", "Washington"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=4,
            schedule_rank=9,
            nonconference_rank=8,
            extra_opponent="",
            history_opponent="Atlanta",
            history_last_played="2047",
            nonconference_opponents=("Atlanta", "Philadelphia", "San Francisco", "Washington"),
        ),
    },
    "6-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=5,
            schedule_rank=3,
            nonconference_rank=8,
            extra_opponent="Philadelphia",
            history_opponent="Washington",
            history_last_played="2047",
            nonconference_opponents=("Chicago", "Green Bay", "New York", "Philadelphia", "Washington"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=7,
            schedule_rank=14,
            nonconference_rank=14,
            extra_opponent="",
            history_opponent="Philadelphia",
            history_last_played="never",
            nonconference_opponents=("Green Bay", "Minnesota", "Philadelphia", "San Francisco"),
        ),
    },
    "7-free-slots": {
        "Buffalo": TeamScheduleReport(
            team="Buffalo",
            conference_rank=4,
            schedule_rank=3,
            nonconference_rank=7,
            extra_opponent="Philadelphia",
            history_opponent="Atlanta",
            history_last_played="2046",
            nonconference_opponents=("Atlanta", "New York", "Philadelphia", "San Francisco", "Washington"),
        ),
        "Denver": TeamScheduleReport(
            team="Denver",
            conference_rank=7,
            schedule_rank=13,
            nonconference_rank=12,
            extra_opponent="",
            history_opponent="Philadelphia",
            history_last_played="never",
            nonconference_opponents=("Green Bay", "New York", "Philadelphia", "San Francisco"),
        ),
    },
}


def _config_id(standings_data) -> str:
    if standings_data == CONFIG_5_SLOTS:
        return "5-free-slots"
    if standings_data == CONFIG_6_SLOTS:
        return "6-free-slots"
    if standings_data == CONFIG_7_SLOTS:
        return "7-free-slots"
    raise AssertionError(f"Unexpected standings config: {standings_data}")


def test_schedule_report_rows_for_one_four_team_and_one_five_team_division(
    schedule, standings_data, history
):
    conference_ranking = standings_data["conference_ranking"]
    report = build_schedule_report(
        schedule=schedule,
        conference_ranking=conference_ranking,
        history=history,
        seed=0,
        scheduler_kind="two-phase",
        config_path=None,
        history_path=None,
        elapsed_time_seconds=0.0,
    )

    rows_by_team = {row.team: row for row in report.teams}
    expected_rows = EXPECTED_ROWS[_config_id(standings_data)]

    assert rows_by_team["Buffalo"] == expected_rows["Buffalo"]
    assert rows_by_team["Denver"] == expected_rows["Denver"]
