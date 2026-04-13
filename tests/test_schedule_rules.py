from pnfl_scheduler.teams import TEAMS, NUM_WEEKS, Division, lookup_team


def test_each_team_has_equal_home_and_away_games(schedule):
    """C3: every team plays the same number of home and away games."""
    for team in TEAMS:
        home = len(schedule.home_games_for(team))
        away = len(schedule.away_games_for(team))
        assert home == away, f"{team.city}: {home} home vs {away} away"


def test_each_team_plays_division_opponents_twice_home_and_away(schedule):
    """C4: every division pairing happens exactly twice — once home, once away."""
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
    """C5: every same-conference cross-division pair meets exactly once."""
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
    """C5: every non-conference pair meets at most once."""
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            if team_a.conference == team_b.conference:
                continue
            meetings = schedule.games_between(team_a, team_b)
            assert len(meetings) <= 1, (
                f"{team_a.city} vs {team_b.city}: {len(meetings)} meetings, expected <= 1"
            )


def test_no_back_to_back_games_between_same_teams(schedule):
    """C6: two teams cannot play each other in consecutive weeks."""
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
    """C7: max home streak is 3."""
    for team in TEAMS:
        streak = _max_streak(_home_pattern(schedule, team))
        assert streak <= 3, f"{team.city}: {streak} consecutive home games"


def test_no_more_than_three_consecutive_away_games(schedule):
    """C7: max away streak is 3."""
    for team in TEAMS:
        away = [not h for h in _home_pattern(schedule, team)]
        streak = _max_streak(away)
        assert streak <= 3, f"{team.city}: {streak} consecutive away games"


def test_three_home_streak_at_most_once(schedule):
    """C7: a 3-game home streak can happen at most once per season."""
    for team in TEAMS:
        count = _count_streaks_of(_home_pattern(schedule, team), 3)
        assert count <= 1, f"{team.city}: {count} home streaks of 3+"


def test_three_away_streak_at_most_once(schedule):
    """C7: a 3-game away streak can happen at most once per season."""
    for team in TEAMS:
        away = [not h for h in _home_pattern(schedule, team)]
        count = _count_streaks_of(away, 3)
        assert count <= 1, f"{team.city}: {count} away streaks of 3+"


def test_no_more_than_three_consecutive_division_games(schedule):
    """C8: max divisional streak is 3."""
    for team in TEAMS:
        streak = _max_streak(_div_pattern(schedule, team))
        assert streak <= 3, f"{team.city}: {streak} consecutive division games"


def test_three_division_streak_at_most_once(schedule):
    """C8: a 3-game divisional streak can happen at most once per season."""
    for team in TEAMS:
        count = _count_streaks_of(_div_pattern(schedule, team), 3)
        assert count <= 1, f"{team.city}: {count} division streaks of 3+"


def test_max_four_division_games_in_six_game_span(schedule):
    """C9: no more than 4 divisional games in any 6-game window."""
    for team in TEAMS:
        pattern = _div_pattern(schedule, team)
        for w in range(NUM_WEEKS - 5):
            count = sum(pattern[w : w + 6])
            assert count <= 4, (
                f"{team.city} weeks {w + 1}-{w + 6}: {count} division games in 6-game span"
            )


def test_max_five_division_games_in_eight_game_span(schedule):
    """C10: no more than 5 divisional games in any 8-game window."""
    for team in TEAMS:
        pattern = _div_pattern(schedule, team)
        for w in range(NUM_WEEKS - 7):
            count = sum(pattern[w : w + 8])
            assert count <= 5, (
                f"{team.city} weeks {w + 1}-{w + 8}: {count} division games in 8-game span"
            )


def test_no_more_than_two_division_games_in_first_three_weeks(schedule):
    """C11: no more than 2 divisional games in the first 3 weeks."""
    for team in TEAMS:
        pattern = _div_pattern(schedule, team)
        count = sum(pattern[:3])
        assert count <= 2, (
            f"{team.city}: {count} division games in first 3 weeks, expected <= 2"
        )


def test_divisional_opponent_interleaving(schedule):
    """C12: at least 1 divisional opponent's games must be interleaved per team."""
    for team in TEAMS:
        div_opps = [t for t in TEAMS if t.division == team.division and t != team]
        # For each opponent, find the weeks of the two meetings
        intervals = {}
        for opp in div_opps:
            meetings = schedule.games_between(team, opp)
            assert len(meetings) == 2
            weeks_played = sorted(g.week for g in meetings)
            intervals[opp] = (weeks_played[0], weeks_played[1])

        # Opponent is non-interleaved if its interval doesn't overlap with any other
        non_interleaved = 0
        for opp in div_opps:
            first_j, second_j = intervals[opp]
            others = [o for o in div_opps if o != opp]
            overlaps_any = False
            for other in others:
                first_k, second_k = intervals[other]
                if first_j < second_k and first_k < second_j:
                    overlaps_any = True
                    break
            if not overlaps_any:
                non_interleaved += 1

        max_non_interleaved = len(div_opps) - 1
        assert non_interleaved <= max_non_interleaved, (
            f"{team.city}: {non_interleaved} non-interleaved opponents, "
            f"expected <= {max_non_interleaved}"
        )


# C13 COMMENTED OUT — close rematch cap test. May be re-enabled later.
# def test_at_most_one_close_divisional_rematch(schedule):
#     """C12: at most one divisional pair league-wide has both meetings within a 3-week span."""
#     close_count = 0
#     for i, team_a in enumerate(TEAMS):
#         for team_b in TEAMS[i + 1 :]:
#             if team_a.division != team_b.division:
#                 continue
#             meetings = schedule.games_between(team_a, team_b)
#             if len(meetings) != 2:
#                 continue
#             weeks_played = sorted(g.week for g in meetings)
#             gap = weeks_played[1] - weeks_played[0]
#             if gap <= 2:
#                 close_count += 1
#     assert close_count <= 1, (
#         f"{close_count} divisional pairs have both meetings within a 3-week span, expected <= 1"
#     )


def test_last_week_has_eight_intra_division_games(schedule):
    """C14: week 16 has exactly 8 divisional games and 1 inter-division."""
    last_week_games = [g for g in schedule.games if g.week == NUM_WEEKS]
    intra = sum(1 for g in last_week_games if g.home.division == g.away.division)
    assert intra == 8, f"Week {NUM_WEEKS}: {intra} divisional games, expected 8"


def test_last_week_inter_division_game_is_last_place_matchup(schedule, standings_data):
    """C14: the inter-division game in the last week is between the two last-place teams."""
    last_week_games = [g for g in schedule.games if g.week == NUM_WEEKS]
    inter_games = [g for g in last_week_games if g.home.division != g.away.division]
    assert len(inter_games) == 1
    game = inter_games[0]
    lp_a = lookup_team(standings_data["last_place"][0])
    lp_b = lookup_team(standings_data["last_place"][1])
    assert {game.home, game.away} == {lp_a, lp_b}, (
        f"Last week inter-division game is {game.home.city} vs {game.away.city}, "
        f"expected {lp_a.city} vs {lp_b.city}"
    )


def test_division_winners_play_both_non_conference_division_winners(schedule, standings_data):
    """C15: each division winner plays both division winners from the other conference."""
    div_winners, _ = standings_data["playoffs"].resolved()
    for team in div_winners:
        other_dws = [t for t in div_winners if t.conference != team.conference]
        for opp in other_dws:
            meetings = schedule.games_between(team, opp)
            assert len(meetings) == 1, (
                f"DW {team.city} vs DW {opp.city}: {len(meetings)} meetings, expected 1"
            )


def test_division_winners_play_exactly_one_non_conference_wild_card(schedule, standings_data):
    """C15: each division winner plays exactly 1 wild card from the other conference."""
    div_winners, wild_cards = standings_data["playoffs"].resolved()
    for team in div_winners:
        other_wcs = [t for t in wild_cards if t.conference != team.conference]
        total = sum(len(schedule.games_between(team, opp)) for opp in other_wcs)
        assert total == 1, (
            f"DW {team.city}: {total} non-conference wild card games, expected 1"
        )


def test_wild_cards_play_exactly_one_non_conference_division_winner(schedule, standings_data):
    """C15: each wild card plays exactly 1 division winner from the other conference."""
    div_winners, wild_cards = standings_data["playoffs"].resolved()
    for team in wild_cards:
        other_dws = [t for t in div_winners if t.conference != team.conference]
        total = sum(len(schedule.games_between(team, opp)) for opp in other_dws)
        assert total == 1, (
            f"WC {team.city}: {total} non-conference division winner games, expected 1"
        )


def test_wild_cards_play_both_non_conference_wild_cards(schedule, standings_data):
    """C15: each wild card plays both wild cards from the other conference."""
    _, wild_cards = standings_data["playoffs"].resolved()
    for team in wild_cards:
        other_wcs = [t for t in wild_cards if t.conference != team.conference]
        for opp in other_wcs:
            meetings = schedule.games_between(team, opp)
            assert len(meetings) == 1, (
                f"WC {team.city} vs WC {opp.city}: {len(meetings)} meetings, expected 1"
            )


def test_non_playoff_teams_face_at_most_one_non_conference_division_winner(schedule, standings_data):
    """C15: non-playoff teams face at most 1 non-conference division winner."""
    div_winners, wild_cards = standings_data["playoffs"].resolved()
    all_playoff = set(div_winners + wild_cards)
    for team in TEAMS:
        if team in all_playoff:
            continue
        other_dws = [t for t in div_winners if t.conference != team.conference]
        total = sum(len(schedule.games_between(team, opp)) for opp in other_dws)
        assert total <= 1, (
            f"{team.city}: {total} non-conference division winner games, expected <= 1"
        )


def test_non_playoff_teams_face_exact_number_of_non_conference_playoff_opponents(schedule, standings_data):
    """C15: each non-playoff team faces exactly 1 or 2 non-conference playoff opponents,
    determined by rank. Highest-ranked absorb overflow, rest get exactly 1."""
    div_winners, wild_cards = standings_data["playoffs"].resolved()
    all_playoff = div_winners + wild_cards
    np_ranked = [lookup_team(c) for c in standings_data["non_playoff_ranked"]]

    for conf in [Division.AFC_EAST.conference, Division.NFC_EAST.conference]:
        other_conf_playoff = [t for t in all_playoff if t.conference != conf]
        np_in_conf = [t for t in np_ranked if t.conference == conf]

        free_slots = 0
        for t in other_conf_playoff:
            if t.division in (Division.AFC_EAST, Division.NFC_EAST):
                free_slots += 2
            else:
                free_slots += 1
        overflow = free_slots - len(np_in_conf)

        for rank, t in enumerate(np_in_conf):
            expected = 2 if rank < overflow else 1
            total = sum(len(schedule.games_between(t, opp)) for opp in other_conf_playoff)
            assert total == expected, (
                f"{t.city} (rank {rank + 1}): {total} non-conference playoff games, expected {expected}"
            )
