from pnfl_scheduler.teams import TEAMS, Division


def test_each_forced_pairing_appears_in_schedule(history_schedule, forced_pairings):
    """Every forced pairing from the assignment solver appears in the schedule."""
    team_by_id = {t.id: t for t in TEAMS}
    for a_id, b_id in forced_pairings:
        team_a = team_by_id[a_id]
        team_b = team_by_id[b_id]
        games = history_schedule.games_between(team_a, team_b)
        assert len(games) == 1, f"{team_a.city} vs {team_b.city}: expected 1 game, got {len(games)}"


def test_five_team_divisions_split_conference_games_evenly(history_schedule):
    """Five-team division teams have 2 home and 2 away conference games."""
    five_team_divisions = (Division.AFC_WEST, Division.NFC_WEST)

    for team in TEAMS:
        if team.division not in five_team_divisions:
            continue

        cross_div_conf_games = [
            g for g in history_schedule.games_for(team) if g.home.conference == g.away.conference and g.home.division != g.away.division
        ]
        home = sum(1 for g in cross_div_conf_games if g.home == team)
        away = sum(1 for g in cross_div_conf_games if g.away == team)

        assert home == 2, f"{team.city}: expected 2 home conference games, got {home}"
        assert away == 2, f"{team.city}: expected 2 away conference games, got {away}"


def test_four_team_divisions_split_conference_home_games_2_2_3_3(history_schedule):
    """Each 4-team division has two teams with 2 and two teams with 3 home conference games."""
    four_team_divisions = (Division.AFC_EAST, Division.NFC_EAST)

    for division in four_team_divisions:
        home_counts = []
        for team in TEAMS:
            if team.division != division:
                continue

            cross_div_conf_games = [
                g for g in history_schedule.games_for(team) if g.home.conference == g.away.conference and g.home.division != g.away.division
            ]
            home_counts.append(sum(1 for g in cross_div_conf_games if g.home == team))

        assert sorted(home_counts) == [2, 2, 3, 3], (
            f"{division.name}: expected conference home split [2, 2, 3, 3], got {sorted(home_counts)}"
        )


def test_five_team_divisions_have_two_nonconference_home_games(history_schedule):
    """Five-team division teams host exactly 2 non-conference games."""
    five_team_divisions = (Division.AFC_WEST, Division.NFC_WEST)

    for team in TEAMS:
        if team.division not in five_team_divisions:
            continue

        non_conf_games = [
            g for g in history_schedule.games_for(team) if g.home.conference != g.away.conference
        ]
        home = sum(1 for g in non_conf_games if g.home == team)
        away = sum(1 for g in non_conf_games if g.away == team)

        assert home == 2, f"{team.city}: expected 2 home non-conference games, got {home}"
        assert away == 2, f"{team.city}: expected 2 away non-conference games, got {away}"


def test_four_team_divisions_split_nonconference_home_games_2_2_3_3(history_schedule):
    """Each 4-team division has two teams with 2 and two teams with 3 home non-conference games."""
    four_team_divisions = (Division.AFC_EAST, Division.NFC_EAST)

    for division in four_team_divisions:
        home_counts = []
        for team in TEAMS:
            if team.division != division:
                continue

            non_conf_home = sum(
                1 for g in history_schedule.home_games_for(team) if g.away.conference != team.conference
            )
            home_counts.append(non_conf_home)

        assert sorted(home_counts) == [2, 2, 3, 3], (
            f"{division.name}: expected non-conference home split [2, 2, 3, 3], "
            f"got {sorted(home_counts)}"
        )
