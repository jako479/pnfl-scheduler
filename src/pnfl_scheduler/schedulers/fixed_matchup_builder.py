"""Phase-1 matchup builder for the fixed-matchup scheduler.

This module builds the full opponent inventory for the schedule builder to use
to build out the schedule: divisional home-and-away games, conference games,
three non-conference opponents based on a fixed rank table, one extra AFC East
vs NFC East rank-based pairing for teams in the four-team divisions, and one
final AFC vs NFC pairing. Linear Sum Assignment is used to determine that final
non-conference pairing based on conference rankings along with head-to-head
history for the coaches. It is also used to determine the matchups for the
extra non-conference game for teams in the four-team divisions.

Non-Conference Games:
Since every team plays every other team in their division twice, and all the
remaining teams in their conference once, the only flexibility in schedules
comes from the non-conference games.

For three of the non-conference games, a fixed table is used to assign
opponents based on the conference rank of each team. The highest ranked team
in each conference gets assigned the hardest three matchups and the difficulty
decreases evenly as the rank of each team decreases.

The fourth non-conference game gets scheduled by Google OR-Tools
linear_sum_assignment, which solves for the "lowest cost" solution out of
all possible matchups. To accomplish this, a cost is assigned to each possible
matchup: a cost based on rankings of the teams in addition to a cost based on
head-to-head matchup history. The longer it's been since two coaches faced
each other, the lower that matchup costs; The closer the rankings of the two
teams match rankings of 1 vs 6, 2 vs 7, and so on, the lower the matchup costs.

A fifth non-conference game gets assigned to the teams in the four-team
divisions also by linear sum assignemnt, where matching ranks get the lowest
cost.

Basic schedule inventory requirements enforced by the matchup builder:
- Each team plays 16 total games, exactly 1 in each week.
- Each team plays every divisional opponent twice, once at home and once away.
- Each team plays every conference opponent exactly once.
- Teams in 5-team divisions play 4 non-conference games.
- Teams in 4-team divisions play 5 non-conference games.
"""

from __future__ import annotations

from collections.abc import Sequence

from ortools.graph.python import linear_sum_assignment

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import Conference, ConferenceRankings, Division, Team
from pnfl_scheduler.domain.schedule import nonconference_games_for
from pnfl_scheduler.schedulers.errors import SchedulerError
from pnfl_scheduler.schedulers.types import Matchup, MatchupPlan, make_matchup

# 1/1 keeps H2H and inverse-rank costs at equal weight.
H2H_COST_SCALE = 1
INVERSE_RANK_COST_SCALE = 1
UNFAVORABLE_MATCHUP_MULTIPLIER = 3

FIXED_NONCONF_RANK_OPPONENTS: dict[int, tuple[int, int, int]] = {
    1: (1, 2, 3),
    2: (1, 2, 4),
    3: (1, 3, 5),
    4: (2, 4, 6),
    5: (3, 5, 7),
    6: (4, 6, 8),
    7: (5, 7, 9),
    8: (6, 8, 9),
    9: (7, 8, 9),
}


def _validate_fixed_rank_table() -> None:
    if sorted(FIXED_NONCONF_RANK_OPPONENTS) != list(range(1, 10)):
        raise SchedulerError("Fixed non-conference rank table must define ranks 1..9")
    for rank, opp_ranks in FIXED_NONCONF_RANK_OPPONENTS.items():
        if len(opp_ranks) != 3:
            raise SchedulerError(f"Rank {rank} must have exactly 3 fixed non-conference opponents")
        if len(set(opp_ranks)) != 3:
            raise SchedulerError(f"Rank {rank} has duplicate fixed non-conference opponents")
        for opp_rank in opp_ranks:
            if opp_rank not in FIXED_NONCONF_RANK_OPPONENTS:
                raise SchedulerError(f"Rank {rank} references invalid opponent rank {opp_rank}")
            if rank not in FIXED_NONCONF_RANK_OPPONENTS[opp_rank]:
                raise SchedulerError(f"Fixed non-conference rank table is not symmetric: {rank} -> {opp_rank} without the reverse edge")


def _pseudo_inverse_target_rank(rank: int) -> int:
    if rank == 5:
        return 5
    if rank < 5:
        return rank + 5
    return rank - 5


class FixedMatchupBuilder:
    def __init__(
        self,
        teams: Sequence[Team],
        rankings: ConferenceRankings,
        history: NonConfHistory,
        season: int,
    ) -> None:
        self.teams = teams
        self.rankings = rankings
        self.history = history
        self.season = season

        self.ranked_teams_by_conf: dict[Conference, tuple[Team, ...]] = {
            Conference.AFC: rankings.afc,
            Conference.NFC: rankings.nfc,
        }
        self.rank_by_team = self._rank_by_team()
        self.matchups: list[Matchup] = []
        self.selected_nonconference: set[Matchup] = set()
        self.remaining_nonconference = {team: nonconference_games_for(team.division) for team in self.teams}

        self.fixed_nonconference_pairs: set[Matchup] = set()
        self.extra_nonconference_pairs: set[Matchup] = set()
        self.history_nonconference_pairs: set[Matchup] = set()

    def _add_nonconference_pairs(self, pairs: set[Matchup]) -> None:
        for i, j in sorted(pairs, key=lambda p: (p[0].metro, p[1].metro)):
            pair = (i, j)
            if pair in self.selected_nonconference:
                raise SchedulerError(f"Duplicate non-conference pair in phase-1 inventory: {pair}")
            self.matchups.append(pair)
            self.selected_nonconference.add(pair)
            self.remaining_nonconference[i] -= 1
            self.remaining_nonconference[j] -= 1
            if self.remaining_nonconference[i] < 0 or self.remaining_nonconference[j] < 0:
                raise SchedulerError(f"Non-conference slot count went negative after reserving pair {pair}")

    def _add_divisional_matchups(self) -> None:
        for i, team_i in enumerate(self.teams):
            for team_j in self.teams[i + 1 :]:
                if team_i.division == team_j.division:
                    pair = make_matchup(team_i, team_j)
                    self.matchups.append(pair)
                    self.matchups.append(pair)

    def _add_conference_matchups(self) -> None:
        for i, team_i in enumerate(self.teams):
            for team_j in self.teams[i + 1 :]:
                if team_i.conference == team_j.conference and team_i.division != team_j.division:
                    self.matchups.append(make_matchup(team_i, team_j))

    def _add_fixed_rank_nonconference_matchups(self) -> None:
        pairs = self._fixed_rank_pairs()
        self.fixed_nonconference_pairs = set(pairs)
        self._add_nonconference_pairs(pairs)

    def _add_four_team_extra_rank_matchups(self) -> None:
        pairs = self._solve_four_team_extra_rank_pairs(
            forbidden_pairs=self.selected_nonconference,
        )
        self.extra_nonconference_pairs = set(pairs)
        self._add_nonconference_pairs(pairs)

    def _add_history_matchups(self) -> None:
        afc_remaining = [team for team in self.teams if team.conference == Conference.AFC and self.remaining_nonconference[team] > 0]
        nfc_remaining = [team for team in self.teams if team.conference == Conference.NFC and self.remaining_nonconference[team] > 0]
        if {self.remaining_nonconference[team] for team in afc_remaining + nfc_remaining} - {1}:
            unresolved = {  # fmt: off
                team.metro: remaining for team, remaining in self.remaining_nonconference.items() if remaining > 0
            }  # fmt: on
            raise SchedulerError(f"History step expected only single-slot teams, got {unresolved}")

        pairs = self._solve_exact_assignment(
            afc_remaining,
            nfc_remaining,
            lambda left, right: self._history_pair_cost(left, right),
            forbidden_pairs=self.selected_nonconference,
        )
        self.history_nonconference_pairs = set(pairs)
        self._add_nonconference_pairs(pairs)

    def _fixed_rank_pairs(self) -> set[Matchup]:
        afc_ranked = self.ranked_teams_by_conf[Conference.AFC]
        nfc_ranked = self.ranked_teams_by_conf[Conference.NFC]

        fixed_pairs: set[Matchup] = set()
        for rank, afc_team in enumerate(afc_ranked, start=1):
            for opp_rank in FIXED_NONCONF_RANK_OPPONENTS[rank]:
                fixed_pairs.add(make_matchup(afc_team, nfc_ranked[opp_rank - 1]))
        return fixed_pairs

    def _history_pair_cost(
        self,
        team_a: Team,
        team_b: Team,
    ) -> int:
        inverse_rank_cost = self._pseudo_inverse_rank_cost(team_a, team_b)
        return H2H_COST_SCALE * self.history.opponent_cost(team_a, team_b, self.season) + INVERSE_RANK_COST_SCALE * inverse_rank_cost

    def _pseudo_inverse_rank_cost(
        self,
        team_a: Team,
        team_b: Team,
    ) -> int:
        """Directional cost for the final AFC->NFC H2H assignment.

        The preferred opponent ranks are 1->6, 2->7, 3->8, 4->9, 5->5, 6->1,
        7->2, 8->3, 9->4. For ranks 1-4, moving to a harder opponent than that
        target costs more per slot. For ranks 6-9, moving to an easier opponent
        than that target costs more per slot. Rank 5 is the neutral pivot and
        uses a symmetric cost around rank 5.
        """
        team_rank = self.rank_by_team[team_a]
        target_rank = _pseudo_inverse_target_rank(team_rank)
        opp_rank = self.rank_by_team[team_b]
        gap = abs(opp_rank - target_rank)
        if gap == 0:
            return 0

        if team_rank == 5:
            return gap

        # For the last non-conference matchup, we want to provide some relief for the
        # top teams and challenge the bottom teams. Therefore, using a multiplier to
        # increase the cost for the top teams to face a harder opponent and for the
        # bottom teams to face an easier opponent.
        if team_rank < 5:
            direction_scale = UNFAVORABLE_MATCHUP_MULTIPLIER if opp_rank < target_rank else 1
        else:
            direction_scale = UNFAVORABLE_MATCHUP_MULTIPLIER if opp_rank > target_rank else 1
        return direction_scale * gap

    def _rank_by_team(self) -> dict[Team, int]:
        rank_by_team: dict[Team, int] = {}
        for conf in Conference:
            for rank, team in enumerate(self.ranked_teams_by_conf[conf], start=1):
                rank_by_team[team] = rank
        return rank_by_team

    def _solve_exact_assignment(
        self,
        left_teams: list[Team],
        right_teams: list[Team],
        cost_fn,
        forbidden_pairs: set[Matchup],
    ) -> set[Matchup]:
        """Solve one-to-one bipartite matching with additive edge costs."""
        if len(left_teams) != len(right_teams):
            raise SchedulerError(f"Unbalanced assignment sides: left={len(left_teams)}, right={len(right_teams)}")

        assignment = linear_sum_assignment.SimpleLinearSumAssignment()
        left_index = {team: idx for idx, team in enumerate(left_teams)}
        right_index = {team: idx for idx, team in enumerate(right_teams)}
        left_by_index = {idx: team for idx, team in enumerate(left_teams)}
        right_by_index = {idx: team for idx, team in enumerate(right_teams)}

        for left in left_teams:
            for right in right_teams:
                pair = make_matchup(left, right)
                if pair in forbidden_pairs:
                    continue
                assignment.add_arc_with_cost(left_index[left], right_index[right], cost_fn(left, right))

        status = assignment.solve()
        if status != assignment.OPTIMAL:
            raise SchedulerError(f"LinearSumAssignment failed with status {status}")

        selected: set[Matchup] = set()
        for left_idx, left_team in left_by_index.items():
            right_idx = assignment.right_mate(left_idx)
            if right_idx < 0:
                raise SchedulerError(f"Assignment left {left_team.metro} unmatched")
            selected.add(make_matchup(left_team, right_by_index[right_idx]))
        return selected

    def _solve_four_team_extra_rank_pairs(
        self,
        forbidden_pairs: set[Matchup],
    ) -> set[Matchup]:
        afc_east = [team for team in self.ranked_teams_by_conf[Conference.AFC] if team.division == Division.AFC_EAST]
        nfc_east = [team for team in self.ranked_teams_by_conf[Conference.NFC] if team.division == Division.NFC_EAST]
        if len(afc_east) != 4 or len(nfc_east) != 4:
            raise SchedulerError("Expected exactly 4 teams per East division for extra SOS assignment")

        return self._solve_exact_assignment(
            afc_east,
            nfc_east,
            lambda left, right: abs(self.rank_by_team[left] - self.rank_by_team[right]),
            forbidden_pairs=forbidden_pairs,
        )

    def build_matchup_plan(self) -> MatchupPlan:
        _validate_fixed_rank_table()
        self._add_divisional_matchups()
        self._add_conference_matchups()
        self._add_fixed_rank_nonconference_matchups()
        self._add_four_team_extra_rank_matchups()
        self._add_history_matchups()

        if any(slots != 0 for slots in self.remaining_nonconference.values()):
            unresolved = {team.metro: slots for team, slots in self.remaining_nonconference.items() if slots != 0}
            raise SchedulerError(f"Non-conference inventory left unresolved slots: {unresolved}")
        if len(self.selected_nonconference) != 40:
            raise SchedulerError(f"Expected 40 non-conference games, got {len(self.selected_nonconference)}")
        if len(self.matchups) != 144:
            raise SchedulerError(f"Expected 144 total matchups in phase-1 inventory, got {len(self.matchups)}")

        return MatchupPlan(
            matchups=tuple(self.matchups),
            fixed_nonconference_pairs=frozenset(self.fixed_nonconference_pairs),
            extra_nonconference_pairs=frozenset(self.extra_nonconference_pairs),
            history_nonconference_pairs=frozenset(self.history_nonconference_pairs),
        )
