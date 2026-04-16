from pnfl_scheduler.domain.teams import Division, NUM_WEEKS, TEAMS


def test_each_team_plays_exactly_one_game_per_week(schedule):
    """Each team plays exactly one game per week."""
    for team in TEAMS:
        for w in range(1, NUM_WEEKS + 1):
            games = [g for g in schedule.games_for(team) if g.week == w]
            assert len(games) == 1, f"{team.city} week {w}: {len(games)} games, expected 1"


def test_each_team_has_equal_home_and_away_games(schedule):
    """Every team plays the same number of home and away games."""
    for team in TEAMS:
        home = len(schedule.home_games_for(team))
        away = len(schedule.away_games_for(team))
        assert home == away, f"{team.city}: {home} home vs {away} away"


def test_each_team_plays_division_opponents_twice_home_and_away(schedule):
    """Every division pairing happens exactly twice, once home and once away."""
    for division in Division:
        div_teams = [t for t in TEAMS if t.division == division]
        for i, team_a in enumerate(div_teams):
            for team_b in div_teams[i + 1 :]:
                meetings = schedule.games_between(team_a, team_b)
                assert len(meetings) == 2, (
                    f"{team_a.city} vs {team_b.city}: {len(meetings)} meetings, expected 2"
                )
                homes = {g.home for g in meetings}
                assert homes == {team_a, team_b}, (
                    f"{team_a.city} vs {team_b.city}: both games had the same host"
                )


def test_same_conference_cross_division_pairs_meet_exactly_once(schedule):
    """Every same-conference cross-division pair meets exactly once."""
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            if team_a.division == team_b.division:
                continue
            if team_a.conference != team_b.conference:
                continue
            meetings = schedule.games_between(team_a, team_b)
            assert len(meetings) == 1, (
                f"{team_a.city} vs {team_b.city}: {len(meetings)} meetings, expected 1"
            )


def test_non_conference_pairs_meet_at_most_once(schedule):
    """Every non-conference pair meets at most once."""
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            if team_a.conference == team_b.conference:
                continue
            meetings = schedule.games_between(team_a, team_b)
            assert len(meetings) <= 1, (
                f"{team_a.city} vs {team_b.city}: {len(meetings)} meetings, expected <= 1"
            )


def test_no_back_to_back_games_between_same_teams(schedule):
    """Two teams cannot play each other in consecutive weeks."""
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            meetings = schedule.games_between(team_a, team_b)
            if len(meetings) < 2:
                continue
            weeks_played = sorted(g.week for g in meetings)
            for k in range(len(weeks_played) - 1):
                assert weeks_played[k + 1] - weeks_played[k] > 1, (
                    f"{team_a.city} vs {team_b.city}: back-to-back in weeks "
                    f"{weeks_played[k]} and {weeks_played[k + 1]}"
                )


def _home_pattern(schedule, team):
    """Return a list of bools, True if team is home in that week (1-indexed weeks)."""
    pattern = [False] * NUM_WEEKS
    for g in schedule.home_games_for(team):
        pattern[g.week - 1] = True
    return pattern


def _div_pattern(schedule, team):
    """Return a list of bools, True if team plays divisional in that week."""
    pattern = [False] * NUM_WEEKS
    for g in schedule.games_for(team):
        opponent = g.away if g.home == team else g.home
        if opponent.division == team.division:
            pattern[g.week - 1] = True
    return pattern


def _max_streak(pattern):
    """Return the length of the longest consecutive True run."""
    best = 0
    current = 0
    for v in pattern:
        if v:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _count_streaks_of(pattern, length):
    """Count how many runs of exactly `length` or more consecutive Trues exist."""
    count = 0
    run = 0
    for v in pattern:
        if v:
            run += 1
        else:
            if run >= length:
                count += 1
            run = 0
    if run >= length:
        count += 1
    return count


def test_no_more_than_three_consecutive_home_games(schedule):
    """The maximum home streak is 3."""
    for team in TEAMS:
        streak = _max_streak(_home_pattern(schedule, team))
        assert streak <= 3, f"{team.city}: {streak} consecutive home games"


def test_no_more_than_three_consecutive_away_games(schedule):
    """The maximum away streak is 3."""
    for team in TEAMS:
        away = [not h for h in _home_pattern(schedule, team)]
        streak = _max_streak(away)
        assert streak <= 3, f"{team.city}: {streak} consecutive away games"


def test_three_home_streak_at_most_once(schedule):
    """A 3-game home streak can happen at most once per season."""
    for team in TEAMS:
        count = _count_streaks_of(_home_pattern(schedule, team), 3)
        assert count <= 1, f"{team.city}: {count} home streaks of 3+"


def test_three_away_streak_at_most_once(schedule):
    """A 3-game away streak can happen at most once per season."""
    for team in TEAMS:
        away = [not h for h in _home_pattern(schedule, team)]
        count = _count_streaks_of(away, 3)
        assert count <= 1, f"{team.city}: {count} away streaks of 3+"


def test_max_five_division_games_in_eight_game_span_four_team_div(schedule):
    """Four-team divisions cannot have more than 5 divisional games in any 8-game window."""
    four_team_teams = [t for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)]
    for team in four_team_teams:
        pattern = _div_pattern(schedule, team)
        for w in range(NUM_WEEKS - 7):
            count = sum(pattern[w : w + 8])
            assert count <= 5, (
                f"{team.city} weeks {w + 1}-{w + 8}: {count} division games in 8-game span"
            )


def test_at_least_half_divisional_games_in_second_half(schedule):
    """At least half of each team's divisional games fall in the last 8 weeks."""
    second_half_start = NUM_WEEKS // 2
    for team in TEAMS:
        pattern = _div_pattern(schedule, team)
        second_half = sum(pattern[second_half_start:])
        if team.division in (Division.AFC_WEST, Division.NFC_WEST):
            minimum = 4
        else:
            minimum = 3
        assert second_half >= minimum, (
            f"{team.city}: {second_half} divisional games in last 8 weeks, expected >= {minimum}"
        )


def test_divisional_opponent_interleaving(schedule):
    """At least 2 divisional opponents must have another opponent's game between meetings."""
    min_interleaved = 2
    for team in TEAMS:
        div_opps = [t for t in TEAMS if t.division == team.division and t != team]
        meeting_weeks = {}
        for opp in div_opps:
            meetings = schedule.games_between(team, opp)
            assert len(meetings) == 2
            meeting_weeks[opp] = sorted(g.week for g in meetings)

        interleaved = 0
        for opp in div_opps:
            first, second = meeting_weeks[opp]
            has_game_between = False
            for other in div_opps:
                if other == opp:
                    continue
                for w in meeting_weeks[other]:
                    if first < w < second:
                        has_game_between = True
                        break
                if has_game_between:
                    break
            if has_game_between:
                interleaved += 1

        assert interleaved >= min_interleaved, (
            f"{team.city}: {interleaved} interleaved opponents, expected >= {min_interleaved}"
        )


def test_last_week_has_eight_intra_division_games(schedule):
    """Week 16 has exactly 8 divisional games and 1 inter-division game."""
    last_week_games = [g for g in schedule.games if g.week == NUM_WEEKS]
    intra = sum(1 for g in last_week_games if g.home.division == g.away.division)
    assert intra == 8, f"Week {NUM_WEEKS}: {intra} divisional games, expected 8"
