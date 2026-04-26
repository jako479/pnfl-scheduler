"""Phase-1 matchup builder for the rank-only two-phase scheduler.

This module builds the fixed matchup list before the shared schedule builder
assigns weeks and home/away slots. It selects divisional home-and-homes,
same-conference cross-division games, then all 40 non-conference games at once
with the rank-only CP-SAT model.

Phase-1 matchup builder for the scheduler.

This module builds the full opponent inventory for the schedule builder to use
to build the schedule: divisional home and away games, conference games, and
non-conference games.

Non-Conference Games:
Since every team plays every other team in their division twice plus all the
remaining teams in their conference once, the only flexibility in matchups
comes from the non-conference games.

This module selects all of the non-conference matchups using Google OR-Tools
CP-SAT, a fast, open-source constraint programming solver designed for
complex scheduling, resource allocation, and optimization problems.

Basic schedule inventory requirements enforced by the matchup builder:
- Each team plays 16 total games, exactly 1 in each week.
- Each team plays every divisional opponent twice, once at home and once away.
- Each team plays every conference opponent exactly once.
- Teams in 5-team divisions play 4 non-conference games.
- Teams in 4-team divisions play 5 non-conference games.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ortools.sat.python import cp_model

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import TEAMS_PER_CONFERENCE, Conference, ConferenceRankings, Team
from pnfl_scheduler.domain.schedule import GAMES_PER_WEEK, NUM_WEEKS, nonconference_games_for
from pnfl_scheduler.schedulers.errors import SchedulerError
from pnfl_scheduler.schedulers.types import Matchup, MatchupPlan, Matchups, make_matchup

TOP_HALF_MAX_RANK = 5
BOTTOM_HALF_MIN_RANK = 5
RANK_GAP_COST_SCALE = 100


class _RankBasedNonConferenceModel:
    """Select every AFC/NFC matchup directly from conference rank order."""

    def __init__(
        self,
        ranked_teams_by_conf: Mapping[Conference, Sequence[Team]],
        rank_by_team: dict[Team, int],
    ) -> None:
        self.model = cp_model.CpModel()
        self.ranked_teams_by_conf = ranked_teams_by_conf
        self.rank_by_team = rank_by_team
        self.afc_teams = list(ranked_teams_by_conf[Conference.AFC])
        self.nfc_teams = list(ranked_teams_by_conf[Conference.NFC])
        self.teams = tuple(self.afc_teams + self.nfc_teams)
        # Name "x" is OR-Tools convention; tuple is [AFC team, NFC team]
        self.x: dict[tuple[Team, Team], cp_model.IntVar] = {}
        self.opponent_rank_sum: dict[Team, cp_model.IntVar] = {}

        for afc_team in self.afc_teams:
            for nfc_team in self.nfc_teams:
                self.x[afc_team, nfc_team] = self.model.new_bool_var(f"nc_{afc_team.metro}_{nfc_team.metro}")

    def _var_for_pair(self, team: Team, opponent: Team) -> cp_model.IntVar:
        if team.conference == Conference.AFC:
            return self.x[team, opponent]
        return self.x[opponent, team]

    def _opponents_for(self, team: Team) -> list[Team]:
        return self.nfc_teams if team.conference == Conference.AFC else self.afc_teams

    def _add_degree_constraints(self) -> None:
        for afc_team in self.afc_teams:
            self.model.add(sum(self.x[afc_team, nfc_team] for nfc_team in self.nfc_teams) == nonconference_games_for(afc_team.division))
        for nfc_team in self.nfc_teams:
            self.model.add(sum(self.x[afc_team, nfc_team] for afc_team in self.afc_teams) == nonconference_games_for(nfc_team.division))

    def _add_top_bottom_constraints(self) -> None:
        for team in self.teams:
            opponents = self._opponents_for(team)
            top_half_vars = [
                self._var_for_pair(team, opponent) for opponent in opponents if self.rank_by_team[opponent] <= TOP_HALF_MAX_RANK
            ]
            bottom_half_vars = [
                self._var_for_pair(team, opponent) for opponent in opponents if self.rank_by_team[opponent] >= BOTTOM_HALF_MIN_RANK
            ]
            self.model.add(sum(top_half_vars) >= 1)
            self.model.add(sum(bottom_half_vars) >= 1)

    def _add_opponent_rank_sum_constraints(self) -> None:
        for team in self.teams:
            opponents = self._opponents_for(team)
            score = self.model.new_int_var(
                nonconference_games_for(team.division),
                TEAMS_PER_CONFERENCE * nonconference_games_for(team.division),
                f"nc_rank_sum_{team.metro}",
            )
            self.model.add(score == sum(self.rank_by_team[opponent] * self._var_for_pair(team, opponent) for opponent in opponents))
            self.opponent_rank_sum[team] = score

    def _add_rank_order_constraints(self) -> None:
        for conf in Conference:
            ranked_teams = self.ranked_teams_by_conf[conf]
            for stronger_team, weaker_team in zip(ranked_teams, ranked_teams[1:]):
                stronger_games = nonconference_games_for(stronger_team.division)
                weaker_games = nonconference_games_for(weaker_team.division)
                self.model.add(
                    weaker_games * self.opponent_rank_sum[stronger_team] <= stronger_games * self.opponent_rank_sum[weaker_team],
                )

    def _set_objective(self) -> None:
        objective_terms: list[cp_model.LinearExpr] = []
        for afc_team in self.afc_teams:
            afc_rank = self.rank_by_team[afc_team]
            for nfc_team in self.nfc_teams:
                nfc_rank = self.rank_by_team[nfc_team]
                pair_cost = RANK_GAP_COST_SCALE * abs(afc_rank - nfc_rank) + afc_rank + nfc_rank
                objective_terms.append(pair_cost * self.x[afc_team, nfc_team])
        self.model.minimize(sum(objective_terms))

    def build(self) -> None:
        self._add_degree_constraints()
        self._add_top_bottom_constraints()
        self._add_opponent_rank_sum_constraints()
        self._add_rank_order_constraints()
        self._set_objective()

    def solve(self) -> set[Matchup]:
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1

        status = solver.solve(self.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise SchedulerError(f"Rank-only non-conference model returned status {solver.status_name(status)} - no feasible inventory")

        # fmt: off
        return {
            make_matchup(afc_team, nfc_team)
            for (afc_team, nfc_team), var in self.x.items()
            if solver.value(var) == 1
        }
        # fmt: on


class MatchupBuilder:
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

    def _add_conference_matchups(self) -> None:
        for i, team_i in enumerate(self.teams):
            for team_j in self.teams[i + 1 :]:
                if team_i.conference == team_j.conference and team_i.division != team_j.division:
                    self.matchups.append(make_matchup(team_i, team_j))

    def _add_divisional_matchups(self) -> None:
        for i, team_i in enumerate(self.teams):
            for team_j in self.teams[i + 1 :]:
                if team_i.division == team_j.division:
                    pair = make_matchup(team_i, team_j)
                    self.matchups.append(pair)
                    self.matchups.append(pair)

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

    def _rank_by_team(self) -> dict[Team, int]:
        rank_by_team: dict[Team, int] = {}
        for conf in Conference:
            for rank, team in enumerate(self.ranked_teams_by_conf[conf], start=1):
                rank_by_team[team] = rank
        return rank_by_team

    def _solve_rank_only_nonconference_pairs(self) -> set[Matchup]:
        rank_model = _RankBasedNonConferenceModel(
            ranked_teams_by_conf=self.ranked_teams_by_conf,
            rank_by_team=self.rank_by_team,
        )
        rank_model.build()
        return rank_model.solve()

    def build_matchup_plan(self) -> MatchupPlan:
        self._add_divisional_matchups()
        self._add_conference_matchups()
        self._add_nonconference_pairs(
            self._solve_rank_only_nonconference_pairs(),
        )

        if any(slots != 0 for slots in self.remaining_nonconference.values()):
            unresolved = {team.metro: slots for team, slots in self.remaining_nonconference.items() if slots != 0}
            raise SchedulerError(f"Non-conference inventory left unresolved slots: {unresolved}")
        if len(self.selected_nonconference) != 40:
            raise SchedulerError(f"Expected 40 non-conference games, got {len(self.selected_nonconference)}")
        if len(self.matchups) != (NUM_WEEKS * GAMES_PER_WEEK):
            raise SchedulerError(f"Expected {NUM_WEEKS * GAMES_PER_WEEK} total matchups in phase-1 inventory, got {len(self.matchups)}")

        return MatchupPlan(matchups=self.matchups)

    def build_matchups(self) -> Matchups:
        self._add_divisional_matchups()
        self._add_conference_matchups()
        self._add_nonconference_pairs(
            self._solve_rank_only_nonconference_pairs(),
        )

        if any(slots != 0 for slots in self.remaining_nonconference.values()):
            unresolved = {team.metro: slots for team, slots in self.remaining_nonconference.items() if slots != 0}
            raise SchedulerError(f"Non-conference inventory left unresolved slots: {unresolved}")
        if len(self.selected_nonconference) != 40:
            raise SchedulerError(f"Expected 40 non-conference games, got {len(self.selected_nonconference)}")
        if len(self.matchups) != 144:
            raise SchedulerError(f"Expected 144 total matchups in phase-1 inventory, got {len(self.matchups)}")

        return tuple(self.matchups)
