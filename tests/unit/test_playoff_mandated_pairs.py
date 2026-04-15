"""Unit tests for _compute_playoff_mandated_pairs."""

from pnfl_scheduler.scheduler import PlayoffTeams
from pnfl_scheduler.scheduler_history import _compute_playoff_mandated_pairs
from pnfl_scheduler.teams import lookup_team

# 5-slot config: all playoff teams from 5-team divisions
PLAYOFFS_5_SLOTS = PlayoffTeams(
    division_winners=("New England", "Cincinnati", "Washington", "Chicago"),
    wild_cards=("Pittsburgh", "Denver", "Minnesota", "San Francisco"),
)

# 6-slot config: mixed divisions
PLAYOFFS_6_SLOTS = PlayoffTeams(
    division_winners=("New England", "Cincinnati", "Washington", "Chicago"),
    wild_cards=("Miami", "Pittsburgh", "Atlanta", "Minnesota"),
)


def _pair(city_a: str, city_b: str) -> tuple[int, int]:
    a = lookup_team(city_a).id
    b = lookup_team(city_b).id
    return (min(a, b), max(a, b))


class TestDivisionWinnerPairs:
    """Division winners play both non-conference division winners."""

    def test_each_dw_plays_both_cross_conf_dws(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        # AFC DWs: New England, Cincinnati. NFC DWs: Washington, Chicago.
        assert _pair("New England", "Washington") in mandated
        assert _pair("New England", "Chicago") in mandated
        assert _pair("Cincinnati", "Washington") in mandated
        assert _pair("Cincinnati", "Chicago") in mandated

    def test_dw_vs_dw_count(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        dw_ids = {lookup_team(c).id for c in PLAYOFFS_5_SLOTS.division_winners}
        dw_pairs = {(a, b) for a, b in mandated if a in dw_ids and b in dw_ids}
        # 2 AFC DWs x 2 NFC DWs = 4 pairs
        assert len(dw_pairs) == 4


class TestWildCardPairs:
    """Wild cards play both non-conference wild cards."""

    def test_each_wc_plays_both_cross_conf_wcs(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        # AFC WCs: Pittsburgh, Denver. NFC WCs: Minnesota, San Francisco.
        assert _pair("Pittsburgh", "Minnesota") in mandated
        assert _pair("Pittsburgh", "San Francisco") in mandated
        assert _pair("Denver", "Minnesota") in mandated
        assert _pair("Denver", "San Francisco") in mandated

    def test_wc_vs_wc_count(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        wc_ids = {lookup_team(c).id for c in PLAYOFFS_5_SLOTS.wild_cards}
        wc_pairs = {(a, b) for a, b in mandated if a in wc_ids and b in wc_ids}
        # 2 AFC WCs x 2 NFC WCs = 4 pairs
        assert len(wc_pairs) == 4


class TestDivisionWinnerWildCardCross:
    """Division winners play one non-conference wild card.

    Wild cards play one non-conference division winner, and all possible
    cross-conference division-winner versus wild-card pairs must be present.
    """

    def test_dw_vs_cross_conf_wc_pairs_present(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        # AFC DWs vs NFC WCs
        assert _pair("New England", "Minnesota") in mandated
        assert _pair("New England", "San Francisco") in mandated
        assert _pair("Cincinnati", "Minnesota") in mandated
        assert _pair("Cincinnati", "San Francisco") in mandated

    def test_wc_vs_cross_conf_dw_pairs_present(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        # AFC WCs vs NFC DWs
        assert _pair("Pittsburgh", "Washington") in mandated
        assert _pair("Pittsburgh", "Chicago") in mandated
        assert _pair("Denver", "Washington") in mandated
        assert _pair("Denver", "Chicago") in mandated

    def test_dw_wc_cross_count(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        dw_ids = {lookup_team(c).id for c in PLAYOFFS_5_SLOTS.division_winners}
        wc_ids = {lookup_team(c).id for c in PLAYOFFS_5_SLOTS.wild_cards}
        cross_pairs = {
            (a, b)
            for a, b in mandated
            if (a in dw_ids and b in wc_ids) or (a in wc_ids and b in dw_ids)
        }
        # 2 AFC DWs x 2 NFC WCs + 2 AFC WCs x 2 NFC DWs = 8
        assert len(cross_pairs) == 8


class TestTotalMandatedCount:
    """All cross-conference playoff pairs should be mandated."""

    def test_total_is_16(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        # 4 DW-vs-DW + 4 WC-vs-WC + 8 DW-vs-WC = 16
        assert len(mandated) == 16

    def test_all_are_cross_conference(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        for a, b in mandated:
            team_a = next(
                t
                for t in PLAYOFFS_5_SLOTS.division_winners + PLAYOFFS_5_SLOTS.wild_cards
                if lookup_team(t).id in (a, b)
            )
            ta = lookup_team(team_a)
            other_id = b if ta.id == a else a
            from pnfl_scheduler.teams import TEAMS

            tb = next(t for t in TEAMS if t.id == other_id)
            assert ta.conference != tb.conference


class TestNoSameConferencePairs:
    """Mandated set should never include same-conference pairs."""

    def test_no_same_conf(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_5_SLOTS)
        from pnfl_scheduler.teams import TEAMS

        team_by_id = {t.id: t for t in TEAMS}
        for a, b in mandated:
            assert team_by_id[a].conference != team_by_id[b].conference


class TestDifferentPlayoffConfig:
    """Verify with a different playoff configuration."""

    def test_6_slot_dw_vs_dw(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_6_SLOTS)
        assert _pair("New England", "Washington") in mandated
        assert _pair("New England", "Chicago") in mandated
        assert _pair("Cincinnati", "Washington") in mandated
        assert _pair("Cincinnati", "Chicago") in mandated

    def test_6_slot_wc_vs_wc(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_6_SLOTS)
        # AFC WCs: Miami, Pittsburgh. NFC WCs: Atlanta, Minnesota.
        assert _pair("Miami", "Atlanta") in mandated
        assert _pair("Miami", "Minnesota") in mandated
        assert _pair("Pittsburgh", "Atlanta") in mandated
        assert _pair("Pittsburgh", "Minnesota") in mandated

    def test_6_slot_dw_vs_wc_cross(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_6_SLOTS)
        # AFC DWs vs NFC WCs
        assert _pair("New England", "Atlanta") in mandated
        assert _pair("New England", "Minnesota") in mandated
        assert _pair("Cincinnati", "Atlanta") in mandated
        assert _pair("Cincinnati", "Minnesota") in mandated
        # AFC WCs vs NFC DWs
        assert _pair("Miami", "Washington") in mandated
        assert _pair("Miami", "Chicago") in mandated
        assert _pair("Pittsburgh", "Washington") in mandated
        assert _pair("Pittsburgh", "Chicago") in mandated

    def test_6_slot_total(self):
        mandated = _compute_playoff_mandated_pairs(PLAYOFFS_6_SLOTS)
        assert len(mandated) == 16
