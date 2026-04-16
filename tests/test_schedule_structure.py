from collections import Counter

from pnfl_scheduler.domain.teams import GAMES_PER_WEEK, NUM_WEEKS, TEAMS


def test_game_count(schedule):
    assert len(schedule.games) == NUM_WEEKS * GAMES_PER_WEEK  # 144


def test_each_week_has_nine_games(schedule):
    by_week = Counter(g.week for g in schedule.games)
    assert set(by_week.keys()) == set(range(1, NUM_WEEKS + 1))
    assert all(c == GAMES_PER_WEEK for c in by_week.values())


def test_each_team_plays_once_per_week(schedule):
    for week in range(1, NUM_WEEKS + 1):
        week_games = [g for g in schedule.games if g.week == week]
        appearances: Counter = Counter()
        for g in week_games:
            appearances[g.home] += 1
            appearances[g.away] += 1
        for team in TEAMS:
            assert appearances[team] == 1, (
                f"Week {week}: {team.city} appears {appearances[team]} times"
            )


def test_each_team_plays_sixteen_games(schedule):
    for team in TEAMS:
        assert len(schedule.games_for(team)) == 16


def test_no_team_plays_itself(schedule):
    for g in schedule.games:
        assert g.home != g.away


def test_each_team_has_eight_home_games(schedule):
    # Redundant with the equal-home-away rule but pinpoints the failure axis.
    for team in TEAMS:
        assert len(schedule.home_games_for(team)) == 8
