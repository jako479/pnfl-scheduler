from pnfl_scheduler.domain.teams import TEAMS, Conference, Division


def test_eighteen_teams():
    assert len(TEAMS) == 18


def test_team_ids_are_unique_and_sequential():
    assert sorted(t.id for t in TEAMS) == list(range(18))


def test_division_sizes():
    sizes = {d: sum(1 for t in TEAMS if t.division == d) for d in Division}
    assert sizes[Division.AFC_EAST] == 4
    assert sizes[Division.AFC_WEST] == 5
    assert sizes[Division.NFC_EAST] == 4
    assert sizes[Division.NFC_WEST] == 5


def test_conference_sizes():
    afc = sum(1 for t in TEAMS if t.conference == Conference.AFC)
    nfc = sum(1 for t in TEAMS if t.conference == Conference.NFC)
    assert afc == 9
    assert nfc == 9


def test_team_conference_matches_division():
    for team in TEAMS:
        assert team.conference == team.division.conference
