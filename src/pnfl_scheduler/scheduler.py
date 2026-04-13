"""Joint CP-SAT model that produces a full PNFL season schedule."""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .schedule import Game, Schedule
from .teams import NUM_WEEKS, TEAMS, Conference, Division, Team, lookup_team


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayoffTeams:
    """Previous season's playoff participants, used for strength-of-schedule constraints."""

    division_winners: tuple[str, str, str, str]  # 4 city names, one per division
    wild_cards: tuple[str, str, str, str]  # 4 city names, 2 per conference

    def validate(self) -> None:
        all_cities = self.division_winners + self.wild_cards
        teams = [lookup_team(c) for c in all_cities]

        if len(set(all_cities)) != 8:
            raise ValueError("Playoff teams must be 8 unique teams")

        # One division winner per division
        dw_divs = {t.division for t in teams[:4]}
        if dw_divs != set(Division):
            raise ValueError("Must have exactly one division winner per division")

        # Wild cards: 2 per conference
        wc_teams = teams[4:]
        for conf in Conference:
            count = sum(1 for t in wc_teams if t.conference == conf)
            if count != 2:
                raise ValueError(f"Must have exactly 2 wild cards from {conf.value}")

    def resolved(self) -> tuple[list[Team], list[Team]]:
        """Return (division_winners, wild_cards) as Team objects."""
        return (
            [lookup_team(c) for c in self.division_winners],
            [lookup_team(c) for c in self.wild_cards],
        )


class _ScheduleModel:
    """Encapsulates the CP-SAT model for PNFL season scheduling.

    Hard constraints
    ----------------
    C1  Each team plays exactly one game per week.
    C2  Each team has exactly 8 home games across the season.
    C3  Every divisional pair meets exactly twice, split 1 home / 1 away per side.
    C4  Intra-conference cross-division pairs meet exactly once; non-conference at most once.
    C5  No back-to-back games between the same two teams.
    C6  Max 3 consecutive home games; a 3-streak at most once per season. Same for away.
    C7  Max 2 consecutive divisional games.
    C8  No consecutive divisional games to start the season.
    C9  Divisional density caps by division size: 5-team divisions max 7 in
        any 11-game span; 4-team divisions max 5 in any 8-game span.
    C10 At least half of each team's divisional games fall in the last 8 weeks.
    C11 Divisional opponent interleaving: at least 2 opponents must have a different
        opponent's game between their two meetings (prevents AABBCCDD patterns).
    C12 Strength of schedule: division winners play both non-conference division
        winners plus one non-conference wild card. Wild cards play one non-conference
        division winner plus both non-conference wild cards. Non-playoff teams face
        at most one non-conference division winner. Each non-playoff team faces exactly
        1 or 2 non-conference playoff opponents (determined by available slots);
        highest-ranked non-playoff teams get 2.
    C13 Last week: 8 divisional games + 1 inter-division between the two
        last-place 5-team-division teams.
    """

    def __init__(self) -> None:
        self.model = cp_model.CpModel()

        self.team_ids = [t.id for t in TEAMS]
        self.weeks = range(NUM_WEEKS)
        self.home_games_per_team = NUM_WEEKS // 2  # 8
        self.team_by_id = {t.id: t for t in TEAMS}

        # Division-derived lookups
        self.div_opponents: dict[int, list[int]] = {}
        for t in TEAMS:
            self.div_opponents[t.id] = [
                o.id for o in TEAMS if o.division == t.division and o.id != t.id
            ]

        self.four_team_ids = {
            t.id for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)
        }
        self.five_team_ids = {
            t.id for t in TEAMS if t.division in (Division.AFC_WEST, Division.NFC_WEST)
        }

        # Pair classifications
        self.intra_div_pairs: list[tuple[int, int]] = []
        self.intra_conf_cross_div: list[tuple[int, int]] = []
        self.non_conf_pairs: list[tuple[int, int]] = []
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                ti, tj = self.team_by_id[i], self.team_by_id[j]
                if ti.division == tj.division:
                    self.intra_div_pairs.append((i, j))
                elif ti.conference == tj.conference:
                    self.intra_conf_cross_div.append((i, j))
                else:
                    self.non_conf_pairs.append((i, j))

        # Decision variables: x[i, j, w] = 1 iff team i hosts team j in week w
        self.x: dict[tuple[int, int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for j in self.team_ids:
                if i == j:
                    continue
                for w in self.weeks:
                    self.x[i, j, w] = self.model.new_bool_var(f"x_{i}_{j}_w{w}")

        # Indicator variables: h[i, w] = 1 iff team i is home in week w
        self.h: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for w in self.weeks:
                self.h[i, w] = self.model.new_bool_var(f"h_{i}_w{w}")
                self.model.add(
                    self.h[i, w] == sum(self.x[i, j, w] for j in self.team_ids if j != i)
                )

        # Indicator variables: d[i, w] = 1 iff team i plays a division opponent in week w
        self.d: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for w in self.weeks:
                self.d[i, w] = self.model.new_bool_var(f"d_{i}_w{w}")
                self.model.add(
                    self.d[i, w] == sum(
                        self.x[i, j, w] + self.x[j, i, w] for j in self.div_opponents[i]
                    )
                )

    def _c1_one_game_per_week(self) -> None:
        for i in self.team_ids:
            for w in self.weeks:
                self.model.add(
                    sum(self.x[i, j, w] + self.x[j, i, w] for j in self.team_ids if j != i) == 1
                )

    def _c2_home_balance(self) -> None:
        for i in self.team_ids:
            self.model.add(
                sum(self.x[i, j, w] for j in self.team_ids if j != i for w in self.weeks)
                == self.home_games_per_team
            )

    def _c3_divisional_pairs(self) -> None:
        for i, j in self.intra_div_pairs:
            self.model.add(sum(self.x[i, j, w] for w in self.weeks) == 1)
            self.model.add(sum(self.x[j, i, w] for w in self.weeks) == 1)

    def _c4_cross_division(self) -> None:
        for i, j in self.intra_conf_cross_div:
            self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)
        for i, j in self.non_conf_pairs:
            self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) <= 1)

    def _c5_no_back_to_back(self) -> None:
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                for w in range(NUM_WEEKS - 1):
                    self.model.add(
                        self.x[i, j, w] + self.x[j, i, w]
                        + self.x[i, j, w + 1] + self.x[j, i, w + 1]
                        <= 1
                    )

    def _c6_home_away_streaks(self) -> None:
        for i in self.team_ids:
            # No 4 consecutive home games
            for w in range(NUM_WEEKS - 3):
                self.model.add(
                    self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] <= 3
                )

            # No 4 consecutive away games
            for w in range(NUM_WEEKS - 3):
                self.model.add(
                    self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] >= 1
                )

            # A 3-home-streak can happen at most once per season
            streak3h: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                s = self.model.new_bool_var(f"s3h_{i}_w{w}")
                self.model.add_bool_and(
                    [self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]
                ).only_enforce_if(s)
                self.model.add_bool_or(
                    [self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]
                ).only_enforce_if(s.Not())
                streak3h.append(s)
            self.model.add(sum(streak3h) <= 1)

            # A 3-away-streak can happen at most once per season
            streak3a: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                s = self.model.new_bool_var(f"s3a_{i}_w{w}")
                self.model.add_bool_and(
                    [self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]
                ).only_enforce_if(s)
                self.model.add_bool_or(
                    [self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]
                ).only_enforce_if(s.Not())
                streak3a.append(s)
            self.model.add(sum(streak3a) <= 1)

    def _c7_max_consecutive_division(self) -> None:
        for i in self.team_ids:
            for w in range(NUM_WEEKS - 2):
                self.model.add(self.d[i, w] + self.d[i, w + 1] + self.d[i, w + 2] <= 2)

    def _c8_no_division_opener(self) -> None:
        for i in self.team_ids:
            self.model.add(self.d[i, 0] + self.d[i, 1] <= 1)

    def _c9_division_density(self) -> None:
        for i in self.five_team_ids:
            for w in range(NUM_WEEKS - 10):
                self.model.add(sum(self.d[i, w + k] for k in range(11)) <= 7)
        for i in self.four_team_ids:
            for w in range(NUM_WEEKS - 7):
                self.model.add(sum(self.d[i, w + k] for k in range(8)) <= 5)

    def _c10_second_half_division(self) -> None:
        second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
        for i in self.five_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 4)
        for i in self.four_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 3)

    def _c11_interleaving(self) -> None:
        min_interleaved = 2
        for i in self.team_ids:
            opps = self.div_opponents[i]
            first_meet: dict[int, cp_model.IntVar] = {}
            second_meet: dict[int, cp_model.IntVar] = {}
            for j in opps:
                wh = self.model.new_int_var(0, NUM_WEEKS - 1, f"wh_{i}_{j}")
                wa = self.model.new_int_var(0, NUM_WEEKS - 1, f"wa_{i}_{j}")
                self.model.add(wh == sum(w * self.x[i, j, w] for w in self.weeks))
                self.model.add(wa == sum(w * self.x[j, i, w] for w in self.weeks))
                w1 = self.model.new_int_var(0, NUM_WEEKS - 1, f"fm_{i}_{j}")
                w2 = self.model.new_int_var(0, NUM_WEEKS - 1, f"sm_{i}_{j}")
                self.model.add_min_equality(w1, [wh, wa])
                self.model.add_max_equality(w2, [wh, wa])
                first_meet[j] = w1
                second_meet[j] = w2

            interleaved: list[cp_model.IntVar] = []
            for j in opps:
                il = self.model.new_bool_var(f"il_{i}_{j}")
                between_vars: list[cp_model.IntVar] = []
                for k in opps:
                    if k == j:
                        continue
                    bk1 = self.model.new_bool_var(f"btw_{i}_{j}_{k}_1")
                    self.model.add(first_meet[k] > first_meet[j]).only_enforce_if(bk1)
                    self.model.add(first_meet[k] < second_meet[j]).only_enforce_if(bk1)
                    between_vars.append(bk1)
                    bk2 = self.model.new_bool_var(f"btw_{i}_{j}_{k}_2")
                    self.model.add(second_meet[k] > first_meet[j]).only_enforce_if(bk2)
                    self.model.add(second_meet[k] < second_meet[j]).only_enforce_if(bk2)
                    between_vars.append(bk2)
                self.model.add_bool_or(between_vars).only_enforce_if(il)
                interleaved.append(il)

            self.model.add(sum(interleaved) >= min_interleaved)

    def _c12_strength_of_schedule(
        self,
        playoffs: PlayoffTeams,
        non_playoff_ranked: list[str] | None,
    ) -> None:
        playoffs.validate()
        div_winners, wild_cards = playoffs.resolved()

        for team in div_winners:
            other_dws = [t for t in div_winners if t.conference != team.conference]
            for opp in other_dws:
                i, j = team.id, opp.id
                self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)

            other_wcs = [t for t in wild_cards if t.conference != team.conference]
            self.model.add(
                sum(
                    self.x[team.id, opp.id, w] + self.x[opp.id, team.id, w]
                    for opp in other_wcs
                    for w in self.weeks
                )
                == 1
            )

        for team in wild_cards:
            other_dws = [t for t in div_winners if t.conference != team.conference]
            self.model.add(
                sum(
                    self.x[team.id, opp.id, w] + self.x[opp.id, team.id, w]
                    for opp in other_dws
                    for w in self.weeks
                )
                == 1
            )

            other_wcs = [t for t in wild_cards if t.conference != team.conference]
            for opp in other_wcs:
                i, j = team.id, opp.id
                self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)

        all_playoff_ids = {t.id for t in div_winners + wild_cards}
        for i in self.team_ids:
            if i in all_playoff_ids:
                continue
            other_dws = [t for t in div_winners if t.conference != self.team_by_id[i].conference]
            self.model.add(
                sum(self.x[i, t.id, w] + self.x[t.id, i, w] for t in other_dws for w in self.weeks)
                <= 1
            )

        np_ranked = [lookup_team(c) for c in non_playoff_ranked] if non_playoff_ranked else []
        all_playoff = div_winners + wild_cards
        for conf in [Conference.AFC, Conference.NFC]:
            other_conf_playoff = [t for t in all_playoff if t.conference != conf]
            np_in_conf = [t for t in np_ranked if t.conference == conf]

            free_slots = 0
            for t in other_conf_playoff:
                if t.division in (Division.AFC_EAST, Division.NFC_EAST):
                    free_slots += 2  # 4-team div: 5 non-conf - 3 C11 = 2
                else:
                    free_slots += 1  # 5-team div: 4 non-conf - 3 C11 = 1

            overflow = free_slots - len(np_in_conf)

            for rank, t in enumerate(np_in_conf):
                target = 2 if rank < overflow else 1
                self.model.add(
                    sum(
                        self.x[t.id, opp.id, w] + self.x[opp.id, t.id, w]
                        for opp in other_conf_playoff
                        for w in self.weeks
                    )
                    == target
                )

    def _c13_last_week(self, last_place: tuple[str, str] | None) -> None:
        last_week = NUM_WEEKS - 1
        self.model.add(
            sum(
                self.x[i, j, last_week] + self.x[j, i, last_week]
                for i, j in self.intra_div_pairs
            )
            == 8
        )

        if last_place is not None:
            lp_a = lookup_team(last_place[0])
            lp_b = lookup_team(last_place[1])
            if lp_a.conference == lp_b.conference:
                raise SchedulerError("Last-place teams must be from different conferences")
            if lp_a.division not in (Division.AFC_WEST, Division.NFC_WEST):
                raise SchedulerError(f"{lp_a.city} is not in a 5-team division")
            if lp_b.division not in (Division.AFC_WEST, Division.NFC_WEST):
                raise SchedulerError(f"{lp_b.city} is not in a 5-team division")
            i, j = lp_a.id, lp_b.id
            self.model.add(self.x[i, j, last_week] + self.x[j, i, last_week] == 1)

    def build(
        self,
        playoffs: PlayoffTeams | None = None,
        last_place: tuple[str, str] | None = None,
        non_playoff_ranked: list[str] | None = None,
    ) -> None:
        self._c1_one_game_per_week()
        self._c2_home_balance()
        self._c3_divisional_pairs()
        self._c4_cross_division()
        self._c5_no_back_to_back()
        self._c6_home_away_streaks()
        self._c7_max_consecutive_division()
        self._c8_no_division_opener()
        self._c9_division_density()
        self._c10_second_half_division()
        self._c11_interleaving()
        if playoffs is not None:
            self._c12_strength_of_schedule(playoffs, non_playoff_ranked)
        self._c13_last_week(last_place)

    def solve(self, seed: int = 0, time_limit: float = 1800.0) -> Schedule:
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = seed
        solver.parameters.randomize_search = True
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.solve(self.model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise SchedulerError(
                f"CP-SAT returned status {solver.status_name(status)} — no feasible schedule"
            )

        games: list[Game] = []
        for (i, j, w), var in self.x.items():
            if solver.value(var) == 1:
                games.append(Game(week=w + 1, home=self.team_by_id[i], away=self.team_by_id[j]))

        return Schedule(games=tuple(games))


def solve_schedule(
    seed: int = 0,
    time_limit: float = 1800.0,
    playoffs: PlayoffTeams | None = None,
    last_place: tuple[str, str] | None = None,
    non_playoff_ranked: list[str] | None = None,
) -> Schedule:
    """Build and solve the CP-SAT model for a single PNFL season."""
    sm = _ScheduleModel()
    sm.build(playoffs=playoffs, last_place=last_place, non_playoff_ranked=non_playoff_ranked)
    return sm.solve(seed=seed, time_limit=time_limit)
