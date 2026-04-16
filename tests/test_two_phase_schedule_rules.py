from collections import Counter

import pytest

from pnfl_scheduler.domain.teams import Division, NUM_WEEKS, TEAMS
from pnfl_scheduler.schedulers.two_phase import build_phase_one_matchup_inventory

@pytest.fixture(scope="session")
def expected_phase_one_inventory(standings_data, history):
    return build_phase_one_matchup_inventory(
        conference_ranking=standings_data["conference_ranking"],
        history=history,
    )


def _schedule_pair_counts(schedule) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for game in schedule.games:
        pair = (min(game.home.id, game.away.id), max(game.home.id, game.away.id))
        counts[pair] += 1
    return counts


def _home_pattern(schedule, team):
    pattern = [False] * NUM_WEEKS
    for game in schedule.home_games_for(team):
        pattern[game.week - 1] = True
    return pattern


def _divisional_pattern(schedule, team):
    pattern = [False] * NUM_WEEKS
    for game in schedule.games_for(team):
        opponent = game.away if game.home == team else game.home
        if opponent.division == team.division:
            pattern[game.week - 1] = True
    return pattern


def _count_streaks_of(pattern, length):
    count = 0
    run = 0
    for value in pattern:
        if value:
            run += 1
        else:
            if run >= length:
                count += 1
            run = 0
    if run >= length:
        count += 1
    return count


def test_two_phase_schedule_matches_phase_one_inventory(schedule, expected_phase_one_inventory):
    assert _schedule_pair_counts(schedule) == Counter(expected_phase_one_inventory)


def test_each_team_plays_exactly_one_game_each_week(schedule):
    for team in TEAMS:
        week_counts = Counter(game.week for game in schedule.games_for(team))
        assert len(schedule.games_for(team)) == NUM_WEEKS, f"{team.city}: expected {NUM_WEEKS} total games"
        for week in range(1, NUM_WEEKS + 1):
            assert week_counts[week] == 1, f"{team.city}: expected exactly 1 game in week {week}"


def test_each_team_hosts_exactly_eight_games(schedule):
    for team in TEAMS:
        assert len(schedule.home_games_for(team)) == 8, f"{team.city}: expected exactly 8 home games"


def test_no_pair_of_teams_plays_in_back_to_back_weeks(schedule):
    pair_weeks: dict[tuple[int, int], list[int]] = {}
    for game in schedule.games:
        pair = (min(game.home.id, game.away.id), max(game.home.id, game.away.id))
        pair_weeks.setdefault(pair, []).append(game.week)

    for pair, weeks in pair_weeks.items():
        weeks.sort()
        for first, second in zip(weeks, weeks[1:]):
            assert second - first > 1, f"{pair}: played in back-to-back weeks {first} and {second}"


def test_each_divisional_pair_is_split_one_home_one_away(schedule):
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            if team_a.division != team_b.division:
                continue
            meetings = [
                game
                for game in schedule.games
                if {game.home.id, game.away.id} == {team_a.id, team_b.id}
            ]
            assert len(meetings) == 2, f"{team_a.city}/{team_b.city}: expected 2 divisional meetings"
            assert sum(1 for game in meetings if game.home == team_a) == 1, (
                f"{team_a.city}/{team_b.city}: expected {team_a.city} to host exactly once"
            )
            assert sum(1 for game in meetings if game.home == team_b) == 1, (
                f"{team_a.city}/{team_b.city}: expected {team_b.city} to host exactly once"
            )


def test_same_conference_cross_division_pairs_appear_once(schedule):
    pair_counts = _schedule_pair_counts(schedule)
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            if team_a.conference == team_b.conference and team_a.division != team_b.division:
                assert pair_counts[(team_a.id, team_b.id)] == 1, (
                    f"{team_a.city}/{team_b.city}: expected exactly 1 same-conference cross-division game"
                )


def test_nonconference_game_counts_match_division_size(schedule):
    for team in TEAMS:
        nonconference_games = [
            game for game in schedule.games_for(team) if game.home.conference != game.away.conference
        ]
        expected = 5 if team.division in (Division.AFC_EAST, Division.NFC_EAST) else 4
        assert len(nonconference_games) == expected, (
            f"{team.city}: expected {expected} non-conference games, got {len(nonconference_games)}"
        )


def test_each_team_has_divisional_game_in_last_two_weeks(schedule):
    for team in TEAMS:
        late_games = [g for g in schedule.games_for(team) if g.week in (NUM_WEEKS - 1, NUM_WEEKS)]
        assert len(late_games) == 2
        assert any(
            (g.away if g.home == team else g.home).division == team.division
            for g in late_games
        ), f"{team.city}: no divisional game in weeks {NUM_WEEKS - 1}-{NUM_WEEKS}"


def test_at_most_one_pair_of_teams_opens_with_back_to_back_divisional_games(schedule):
    teams_with_opening_back_to_back_divisional = 0
    for team in TEAMS:
        opening_divisional = sum(
            1
            for g in schedule.games_for(team)
            if g.week in (1, 2) and (g.away if g.home == team else g.home).division == team.division
        )
        if opening_divisional == 2:
            teams_with_opening_back_to_back_divisional += 1

    assert teams_with_opening_back_to_back_divisional in (0, 2), (
        "expected either 0 teams or exactly 2 teams to open with back-to-back divisional games, "
        f"got {teams_with_opening_back_to_back_divisional}"
    )


def test_no_three_consecutive_divisional_games_to_start_or_end(schedule):
    for team in TEAMS:
        start_divisional = sum(
            1
            for g in schedule.games_for(team)
            if g.week in (1, 2, 3) and (g.away if g.home == team else g.home).division == team.division
        )
        end_divisional = sum(
            1
            for g in schedule.games_for(team)
            if g.week in (NUM_WEEKS - 2, NUM_WEEKS - 1, NUM_WEEKS) and (g.away if g.home == team else g.home).division == team.division
        )
        assert start_divisional <= 2, f"{team.city}: opens with 3 straight divisional games"
        assert end_divisional <= 2, f"{team.city}: ends with 3 straight divisional games"


def test_max_one_total_three_game_divisional_streak(schedule):
    for team in TEAMS:
        divisional_pattern = _divisional_pattern(schedule, team)
        total_three_game_streaks = _count_streaks_of(divisional_pattern, 3)
        assert total_three_game_streaks <= 1, (
            f"{team.city}: {total_three_game_streaks} divisional streaks of 3+"
        )


def test_no_four_consecutive_divisional_games(schedule):
    for team in TEAMS:
        divisional_pattern = _divisional_pattern(schedule, team)
        assert _count_streaks_of(divisional_pattern, 4) == 0, (
            f"{team.city}: has a divisional streak of 4+ games"
        )


def test_divisional_density_windows(schedule):
    for team in TEAMS:
        divisional_pattern = _divisional_pattern(schedule, team)
        if team.division in (Division.AFC_WEST, Division.NFC_WEST):
            for start in range(NUM_WEEKS - 9):
                div_count = sum(divisional_pattern[start : start + 10])
                assert div_count <= 7, (
                    f"{team.city} weeks {start + 1}-{start + 10}: {div_count} divisional games in 10-game span"
                )
            for start in range(NUM_WEEKS - 8):
                div_count = sum(divisional_pattern[start : start + 9])
                assert div_count <= 6, (
                    f"{team.city} weeks {start + 1}-{start + 9}: {div_count} divisional games in 9-game span"
                )
        else:
            for start in range(NUM_WEEKS - 7):
                div_count = sum(divisional_pattern[start : start + 8])
                assert div_count <= 5, (
                    f"{team.city} weeks {start + 1}-{start + 8}: {div_count} divisional games in 8-game span"
                )
            for start in range(NUM_WEEKS - 6):
                div_count = sum(divisional_pattern[start : start + 7])
                assert div_count <= 3, (
                    f"{team.city} weeks {start + 1}-{start + 7}: {div_count} divisional games in 7-game span"
                )


def test_at_least_half_of_divisional_games_are_in_second_half(schedule):
    second_half_weeks = set(range((NUM_WEEKS // 2) + 1, NUM_WEEKS + 1))
    for team in TEAMS:
        divisional_games_in_second_half = sum(
            1
            for game in schedule.games_for(team)
            if game.week in second_half_weeks
            and (game.away if game.home == team else game.home).division == team.division
        )
        expected_minimum = 4 if team.division in (Division.AFC_WEST, Division.NFC_WEST) else 3
        assert divisional_games_in_second_half >= expected_minimum, (
            f"{team.city}: expected at least {expected_minimum} divisional games in second half"
        )


def test_at_most_two_divisional_opponents_are_non_interleaved(schedule):
    for team in TEAMS:
        divisional_meeting_weeks: dict[int, list[int]] = {}
        for game in schedule.games_for(team):
            opponent = game.away if game.home == team else game.home
            if opponent.division == team.division:
                divisional_meeting_weeks.setdefault(opponent.id, []).append(game.week)

        interleaved_opponents = 0
        for opponent_id, weeks in divisional_meeting_weeks.items():
            first, second = sorted(weeks)
            has_other_meeting_between = any(
                first < other_week < second
                for other_id, other_weeks in divisional_meeting_weeks.items()
                if other_id != opponent_id
                for other_week in other_weeks
            )
            if has_other_meeting_between:
                interleaved_opponents += 1

        non_interleaved_opponents = len(divisional_meeting_weeks) - interleaved_opponents
        assert non_interleaved_opponents <= 2, (
            f"{team.city}: {non_interleaved_opponents} divisional opponents are non-interleaved"
        )


def test_max_one_total_home_or_away_three_game_streak(schedule):
    for team in TEAMS:
        home_pattern = _home_pattern(schedule, team)
        away_pattern = [not is_home for is_home in home_pattern]
        total_three_game_streaks = _count_streaks_of(home_pattern, 3) + _count_streaks_of(away_pattern, 3)
        assert total_three_game_streaks <= 1, (
            f"{team.city}: {total_three_game_streaks} total home/away streaks of 3+"
        )


def test_max_four_home_or_away_games_in_any_six_game_span(schedule):
    for team in TEAMS:
        home_pattern = _home_pattern(schedule, team)
        for start in range(NUM_WEEKS - 5):
            home_count = sum(home_pattern[start : start + 6])
            assert 2 <= home_count <= 4, (
                f"{team.city} weeks {start + 1}-{start + 6}: {home_count} home games in 6-game span"
            )


def test_no_three_game_home_or_away_streak_to_start_or_end(schedule):
    for team in TEAMS:
        home_pattern = _home_pattern(schedule, team)
        start_home = sum(home_pattern[:3])
        end_home = sum(home_pattern[-3:])
        assert 1 <= start_home <= 2, f"{team.city}: invalid home/away split in first 3 weeks"
        assert 1 <= end_home <= 2, f"{team.city}: invalid home/away split in last 3 weeks"


def test_five_team_divisions_split_conference_home_games_evenly(schedule):
    five_team_divisions = (Division.AFC_WEST, Division.NFC_WEST)

    for team in TEAMS:
        if team.division not in five_team_divisions:
            continue

        cross_div_conf_games = [
            g
            for g in schedule.games_for(team)
            if g.home.conference == g.away.conference and g.home.division != g.away.division
        ]
        home = sum(1 for g in cross_div_conf_games if g.home == team)
        away = sum(1 for g in cross_div_conf_games if g.away == team)

        assert home == 2, f"{team.city}: expected 2 home conference games, got {home}"
        assert away == 2, f"{team.city}: expected 2 away conference games, got {away}"


def test_four_team_divisions_split_conference_home_games_2_2_3_3(schedule):
    four_team_divisions = (Division.AFC_EAST, Division.NFC_EAST)

    for division in four_team_divisions:
        home_counts = []
        for team in TEAMS:
            if team.division != division:
                continue

            cross_div_conf_games = [
                g
                for g in schedule.games_for(team)
                if g.home.conference == g.away.conference and g.home.division != g.away.division
            ]
            home_counts.append(sum(1 for g in cross_div_conf_games if g.home == team))

        assert sorted(home_counts) == [2, 2, 3, 3], (
            f"{division.name}: expected conference home split [2, 2, 3, 3], got {sorted(home_counts)}"
        )


def test_five_team_divisions_have_two_nonconference_home_games(schedule):
    five_team_divisions = (Division.AFC_WEST, Division.NFC_WEST)

    for team in TEAMS:
        if team.division not in five_team_divisions:
            continue

        non_conf_games = [g for g in schedule.games_for(team) if g.home.conference != g.away.conference]
        home = sum(1 for g in non_conf_games if g.home == team)
        away = sum(1 for g in non_conf_games if g.away == team)

        assert home == 2, f"{team.city}: expected 2 home non-conference games, got {home}"
        assert away == 2, f"{team.city}: expected 2 away non-conference games, got {away}"


def test_four_team_divisions_split_nonconference_home_games_2_2_3_3(schedule):
    four_team_divisions = (Division.AFC_EAST, Division.NFC_EAST)

    for division in four_team_divisions:
        home_counts = []
        for team in TEAMS:
            if team.division != division:
                continue

            non_conf_home = sum(
                1 for g in schedule.home_games_for(team) if g.away.conference != team.conference
            )
            home_counts.append(non_conf_home)

        assert sorted(home_counts) == [2, 2, 3, 3], (
            f"{division.name}: expected non-conference home split [2, 2, 3, 3], "
            f"got {sorted(home_counts)}"
        )


def test_no_four_consecutive_home_or_away_games(schedule):
    for team in TEAMS:
        home_pattern = _home_pattern(schedule, team)
        away_pattern = [not is_home for is_home in home_pattern]
        assert _count_streaks_of(home_pattern, 4) == 0, f"{team.city}: has a home streak of 4+ games"
        assert _count_streaks_of(away_pattern, 4) == 0, f"{team.city}: has an away streak of 4+ games"


def test_week_16_has_exactly_eight_divisional_games(schedule):
    final_week_divisional_games = sum(
        1 for game in schedule.games if game.week == NUM_WEEKS and game.home.division == game.away.division
    )
    assert final_week_divisional_games == 8, (
        f"week {NUM_WEEKS}: expected exactly 8 divisional games, got {final_week_divisional_games}"
    )
