"""Joint CP-SAT model that produces a full PNFL season schedule.

Clone of scheduler.py with an additional history-based
non-conference rotation constraint.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from .history import NonConfHistory
from .schedule import Game, Schedule
from .scheduler import PlayoffTeams, SchedulerError
from .teams import NUM_WEEKS, TEAMS, Conference, Division, lookup_team

StandingRow = tuple[str, int, int, int]
DivisionStandings = tuple[StandingRow, ...]

# Static 2047 standings from the supplied image.

SEASON_2047_STANDINGS: dict[Division, DivisionStandings] = {
    Division.AFC_EAST: (
        ("Miami", 11, 5, 0),
        ("New England", 7, 8, 1),
        ("Jacksonville", 6, 10, 0),
        ("Buffalo", 4, 12, 0),
    ),
    Division.AFC_WEST: (
        ("Los Angeles", 13, 3, 0),
        ("Denver", 9, 6, 1),
        ("Las Vegas", 8, 8, 0),
        ("Cincinnati", 7, 9, 0),
        ("Pittsburgh", 5, 10, 1),
    ),
    Division.NFC_EAST: (
        ("Washington", 9, 6, 1),
        ("Atlanta", 9, 7, 0),
        ("New York", 7, 9, 0),
        ("Philadelphia", 6, 10, 0),
    ),
    Division.NFC_WEST: (
        ("Chicago", 12, 4, 0),
        ("Minnesota", 11, 5, 0),
        ("Green Bay", 7, 9, 0),
        ("San Francisco", 6, 10, 0),
        ("Seattle", 5, 11, 0),
    ),
}


class _ScheduleModel:
    """Encapsulates the CP-SAT model for PNFL season scheduling.

    Hard constraints
    ----------------
    C1  Each team plays exactly one game per week.
    C2  Each team has exactly 8 home games across the season.
    C3  Max 3 consecutive home games; a 3-streak at most once per season. Same for away.
    C4  No back-to-back games between the same two teams.
    C5  Each team plays every divisional opponent twice, once home and once away.
    C6  Each team plays every conference opponent exactly once.
    C7  Conference matchup home balance: five-team division teams host 2 of their 4
        cross-division conference games; in each four-team division, the 5-game split
        is 2, 2, 3, 3 home games across the four teams.
    C8  Each team plays any non-conference opponents at most once.
    C9  Non-conference home balance: five-team division teams host exactly 2 of their
        4 non-conference games; in each four-team division, the 5-game split is
        2, 2, 3, 3 home games across the four teams.
    C10 Max 2 consecutive divisional games.
    C11 No consecutive divisional games to start the season.
    C12 Teams in five-team divisions, max 7 divisional games in any 11-game span;
        Teams in four-team divisions, max 5 divisional games in any 8-game span.
    C13 At least half of each team's divisional games fall in the last half of the season.
    C14 Divisional opponent interleaving: at least 2 opponents must have a different
        opponent's game between their two meetings (prevents AABBCCDD patterns).
    C15 Strength of schedule: division winners play both non-conference division
        winners plus one non-conference wild card. Wild cards play one non-conference
        division winner plus both non-conference wild cards. Non-playoff teams face
        at most one non-conference division winner. Each non-playoff team faces exactly
        1 or 2 non-conference playoff opponents (determined by available slots);
        highest-ranked non-playoff teams get 2.
    C16 Week 16: 8 divisional games + 1 non-conference game between the two
        last-place teams in the five-team divisions.
    C17 History rotation: one non-conference game per team must be against their
        most-overdue non-conference opponent (longest since last played, or never).
    """

    def __init__(self) -> None:
        self.model = cp_model.CpModel()

        self.team_ids = [t.id for t in TEAMS]
        self.weeks = range(NUM_WEEKS)
        self.home_games_per_team = 8
        self.team_by_id = {t.id: t for t in TEAMS}

        # Division-derived lookups
        self.div_opponents: dict[int, list[int]] = {}
        for t in TEAMS:
            self.div_opponents[t.id] = [o.id for o in TEAMS if o.division == t.division and o.id != t.id]

        self.four_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)}
        self.five_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_WEST, Division.NFC_WEST)}

        # Pair classifications
        self.divisional_pairs: list[tuple[int, int]] = []
        self.conference_pairs: list[tuple[int, int]] = []
        self.non_conference_pairs: list[tuple[int, int]] = []
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                ti, tj = self.team_by_id[i], self.team_by_id[j]
                if ti.division == tj.division:
                    self.divisional_pairs.append((i, j))
                elif ti.conference == tj.conference:
                    self.conference_pairs.append((i, j))
                else:
                    self.non_conference_pairs.append((i, j))

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
                self.model.add(self.h[i, w] == sum(self.x[i, j, w] for j in self.team_ids if j != i))

        # Indicator variables: d[i, w] = 1 iff team i plays a division opponent in week w
        self.d: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for w in self.weeks:
                self.d[i, w] = self.model.new_bool_var(f"d_{i}_w{w}")
                self.model.add(self.d[i, w] == sum(self.x[i, j, w] + self.x[j, i, w] for j in self.div_opponents[i]))

    def _constraint_one_game_per_week(self) -> None:
        for i in self.team_ids:
            for w in self.weeks:
                self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for j in self.team_ids if j != i) == 1)

    def _constraint_home_balance(self) -> None:
        for i in self.team_ids:
            self.model.add(sum(self.x[i, j, w] for j in self.team_ids if j != i for w in self.weeks) == self.home_games_per_team)

    def _constraint_home_away_streaks(self) -> None:
        for i in self.team_ids:
            # No 4 consecutive home games
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] <= 3)

            # No 4 consecutive away games
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] >= 1)

            # A 3-home-streak can happen at most once per season
            streak3h: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                s = self.model.new_bool_var(f"s3h_{i}_w{w}")
                self.model.add_bool_and([self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]).only_enforce_if(s)
                self.model.add_bool_or([self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]).only_enforce_if(s.Not())
                streak3h.append(s)
            self.model.add(sum(streak3h) <= 1)

            # A 3-away-streak can happen at most once per season
            streak3a: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                s = self.model.new_bool_var(f"s3a_{i}_w{w}")
                self.model.add_bool_and([self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]).only_enforce_if(s)
                self.model.add_bool_or([self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]).only_enforce_if(s.Not())
                streak3a.append(s)
            self.model.add(sum(streak3a) <= 1)

    def _constraint_no_back_to_back(self) -> None:
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                for w in range(NUM_WEEKS - 1):
                    self.model.add(self.x[i, j, w] + self.x[j, i, w] + self.x[i, j, w + 1] + self.x[j, i, w + 1] <= 1)

    def _constraint_divisional_matchups(self) -> None:
        for i, j in self.divisional_pairs:
            self.model.add(sum(self.x[i, j, w] for w in self.weeks) == 1)
            self.model.add(sum(self.x[j, i, w] for w in self.weeks) == 1)

    def _constraint_conference_matchups(self) -> None:
        for i, j in self.conference_pairs:
            self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)

    def _constraint_conference_home_balance(self) -> None:
        for i in self.team_ids:
            team = self.team_by_id[i]
            conference_opponents = [
                j
                for j in self.team_ids
                if j != i and self.team_by_id[j].conference == team.conference and self.team_by_id[j].division != team.division
            ]
            conf_home_games = sum(self.x[i, j, w] for j in conference_opponents for w in self.weeks)

            if i in self.five_team_ids:
                self.model.add(conf_home_games == 2)
            else:
                # With the five-team side fixed at 10 of the 20 cross-division home slots,
                # these 2..3 bounds naturally force the four-team side to total 10, i.e. 2,2,3,3.
                self.model.add(conf_home_games >= 2)
                self.model.add(conf_home_games <= 3)

    def _constraint_nonconference_matchups(self) -> None:
        for i, j in self.non_conference_pairs:
            self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) <= 1)

    def _constraint_nonconference_home_balance(self) -> None:
        for i in self.team_ids:
            team = self.team_by_id[i]
            non_conference_opponents = [j for j in self.team_ids if self.team_by_id[j].conference != team.conference]
            non_conf_home_games = sum(self.x[i, j, w] for j in non_conference_opponents for w in self.weeks)

            if i in self.five_team_ids:
                self.model.add(non_conf_home_games == 2)
            else:
                # Four-team division teams host either 2 or 3 of their 5 non-conference games.
                self.model.add(non_conf_home_games >= 2)
                self.model.add(non_conf_home_games <= 3)

    def _constraint_max_consecutive_division(self) -> None:
        for i in self.team_ids:
            for w in range(NUM_WEEKS - 2):
                self.model.add(self.d[i, w] + self.d[i, w + 1] + self.d[i, w + 2] <= 2)

    def _constraint_no_division_opener(self) -> None:
        for i in self.team_ids:
            self.model.add(self.d[i, 0] + self.d[i, 1] <= 1)

    def _constraint_division_density(self) -> None:
        for i in self.five_team_ids:
            for w in range(NUM_WEEKS - 10):
                self.model.add(sum(self.d[i, w + k] for k in range(11)) <= 7)
        for i in self.four_team_ids:
            for w in range(NUM_WEEKS - 7):
                self.model.add(sum(self.d[i, w + k] for k in range(8)) <= 5)

    def _constraint_second_half_division(self) -> None:
        second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
        for i in self.five_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 4)
        for i in self.four_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 3)

    def _constraint_interleaving(self) -> None:
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

    def _constraint_strength_of_schedule(
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
            self.model.add(sum(self.x[team.id, opp.id, w] + self.x[opp.id, team.id, w] for opp in other_wcs for w in self.weeks) == 1)

        for team in wild_cards:
            other_dws = [t for t in div_winners if t.conference != team.conference]
            self.model.add(sum(self.x[team.id, opp.id, w] + self.x[opp.id, team.id, w] for opp in other_dws for w in self.weeks) == 1)

            other_wcs = [t for t in wild_cards if t.conference != team.conference]
            for opp in other_wcs:
                i, j = team.id, opp.id
                self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)

        all_playoff_ids = {t.id for t in div_winners + wild_cards}
        for i in self.team_ids:
            if i in all_playoff_ids:
                continue
            other_dws = [t for t in div_winners if t.conference != self.team_by_id[i].conference]
            self.model.add(sum(self.x[i, t.id, w] + self.x[t.id, i, w] for t in other_dws for w in self.weeks) <= 1)

        np_ranked = [lookup_team(c) for c in non_playoff_ranked] if non_playoff_ranked else []
        all_playoff = div_winners + wild_cards
        for conf in [Conference.AFC, Conference.NFC]:
            other_conf_playoff = [t for t in all_playoff if t.conference != conf]
            np_in_conf = [t for t in np_ranked if t.conference == conf]

            free_slots = 0
            for t in other_conf_playoff:
                if t.division in (Division.AFC_EAST, Division.NFC_EAST):
                    free_slots += 2  # 4-team division teams have 2 open non-conference slots.
                else:
                    free_slots += 1  # 5-team division teams have 1 open non-conference slot.

            overflow = free_slots - len(np_in_conf)

            for rank, t in enumerate(np_in_conf):
                target = 2 if rank < overflow else 1
                self.model.add(
                    sum(self.x[t.id, opp.id, w] + self.x[opp.id, t.id, w] for opp in other_conf_playoff for w in self.weeks) == target
                )

    def _constraint_week_16_matchups(self, last_place: tuple[str, str] | None) -> None:
        last_week = NUM_WEEKS - 1
        self.model.add(sum(self.x[i, j, last_week] + self.x[j, i, last_week] for i, j in self.divisional_pairs) == 8)

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

    def _constraint_history_rotation(self, forced_pairs: set[tuple[int, int]]) -> None:
        """Force one game between each pair in the forced set."""
        for i, j in forced_pairs:
            self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks) == 1)

    def build(
        self,
        playoffs: PlayoffTeams | None = None,
        last_place: tuple[str, str] | None = None,
        non_playoff_ranked: list[str] | None = None,
        forced_nonconf_pairs: set[tuple[int, int]] | None = None,
    ) -> None:
        self._constraint_one_game_per_week()
        self._constraint_home_balance()
        self._constraint_home_away_streaks()
        self._constraint_no_back_to_back()
        self._constraint_divisional_matchups()
        self._constraint_conference_matchups()
        self._constraint_conference_home_balance()
        self._constraint_nonconference_matchups()
        self._constraint_nonconference_home_balance()
        self._constraint_max_consecutive_division()
        self._constraint_no_division_opener()
        self._constraint_division_density()
        self._constraint_second_half_division()
        self._constraint_interleaving()
        if playoffs is not None:
            self._constraint_strength_of_schedule(playoffs, non_playoff_ranked)
        self._constraint_week_16_matchups(last_place)
        if forced_nonconf_pairs:
            self._constraint_history_rotation(forced_nonconf_pairs)

    def solve(self, seed: int = 0, time_limit: float = 1800.0) -> Schedule:
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = seed
        solver.parameters.randomize_search = True
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.solve(self.model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise SchedulerError(f"CP-SAT returned status {solver.status_name(status)} — no feasible schedule")

        games: list[Game] = []
        for (i, j, w), var in self.x.items():
            if solver.value(var) == 1:
                games.append(Game(week=w + 1, home=self.team_by_id[i], away=self.team_by_id[j]))

        return Schedule(games=tuple(games))


def _compute_playoff_mandated_pairs(playoffs: PlayoffTeams) -> set[tuple[int, int]]:
    """Extract all non-conference playoff pairs implied by the playoff rules.

    Includes DW-vs-DW (both), WC-vs-WC (both), DW-vs-WC (one each,
    but we don't know which, so exclude all possibilities).

    Returns pairs as (smaller_id, larger_id).
    """
    div_winners, wild_cards = playoffs.resolved()
    all_playoff = div_winners + wild_cards
    mandated: set[tuple[int, int]] = set()

    for team in all_playoff:
        for opp in all_playoff:
            if opp.conference != team.conference:
                mandated.add((min(team.id, opp.id), max(team.id, opp.id)))

    return mandated


def solve_schedule(
    seed: int = 0,
    time_limit: float = 3600.0,
    playoffs: PlayoffTeams | None = None,
    last_place: tuple[str, str] | None = None,
    non_playoff_ranked: list[str] | None = None,
    history: NonConfHistory | None = None,
) -> Schedule:
    """Build and solve the CP-SAT model for a single PNFL season.

    If *history* is provided, uses LinearSumAssignment to find the
    optimal 9 non-conference pairings and adds them as forced history matchups.
    """
    forced: set[tuple[int, int]] | None = None
    if history is not None:
        playoff_mandated_pairs = _compute_playoff_mandated_pairs(playoffs) if playoffs is not None else set()
        forced = history.compute_forced_pairings(playoff_mandated_pairs=playoff_mandated_pairs)

    sm = _ScheduleModel()
    sm.build(
        playoffs=playoffs,
        last_place=last_place,
        non_playoff_ranked=non_playoff_ranked,
        forced_nonconf_pairs=forced,
    )
    return sm.solve(seed=seed, time_limit=time_limit)
