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


def solve_schedule(
    seed: int = 0,
    time_limit: float = 1800.0,
    playoffs: PlayoffTeams | None = None,
    last_place: tuple[str, str] | None = None,
    non_playoff_ranked: list[str] | None = None,
) -> Schedule:
    """Build and solve the CP-SAT model for a single PNFL season.

    Decision variables
    ------------------
    x[i, j, w] : BoolVar  — 1 iff team i hosts team j in week w (i != j).

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
    C9  Max 7 divisional games in any 11-game span for teams in 5-team divisions;
        Max 5 divisional games in any 8-game span for teams in 4-team divisions.
    C10 At least 4 divisional games in the last 8 weeks for teams in 5-team divisions;
        At least 3 divisional games in the last 8 weeks for teams in 4-team divisions.
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
    model = cp_model.CpModel()

    team_ids = [t.id for t in TEAMS]
    weeks = range(NUM_WEEKS)
    home_games_per_team = NUM_WEEKS // 2  # 8

    # x[i, j, w] = 1 iff team i hosts team j in week w
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for i in team_ids:
        for j in team_ids:
            if i == j:
                continue
            for w in weeks:
                x[i, j, w] = model.new_bool_var(f"x_{i}_{j}_w{w}")

    # C1: each team plays exactly one game per week
    for i in team_ids:
        for w in weeks:
            model.add(sum(x[i, j, w] + x[j, i, w] for j in team_ids if j != i) == 1)

    # C2: each team has exactly 8 home games across the season
    for i in team_ids:
        model.add(sum(x[i, j, w] for j in team_ids if j != i for w in weeks) == home_games_per_team)

    # Division and non-division pair enumeration
    team_by_id = {t.id: t for t in TEAMS}
    intra_div_pairs: list[tuple[int, int]] = []
    inter_div_pairs: list[tuple[int, int]] = []
    for i in team_ids:
        for j in team_ids:
            if i >= j:
                continue
            if team_by_id[i].division == team_by_id[j].division:
                intra_div_pairs.append((i, j))
            else:
                inter_div_pairs.append((i, j))

    # C3: every divisional pair meets exactly twice, split 1H/1A per side
    for i, j in intra_div_pairs:
        model.add(sum(x[i, j, w] for w in weeks) == 1)
        model.add(sum(x[j, i, w] for w in weeks) == 1)

    # C4: intra-conference cross-division pairs meet exactly once;
    # non-conference pairs meet at most once.
    intra_conf_cross_div: list[tuple[int, int]] = []
    non_conf_pairs: list[tuple[int, int]] = []
    for i, j in inter_div_pairs:
        if team_by_id[i].conference == team_by_id[j].conference:
            intra_conf_cross_div.append((i, j))
        else:
            non_conf_pairs.append((i, j))

    for i, j in intra_conf_cross_div:
        model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) == 1)

    for i, j in non_conf_pairs:
        model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) <= 1)

    # C5: no back-to-back games between the same two teams
    for i in team_ids:
        for j in team_ids:
            if i >= j:
                continue
            for w in range(NUM_WEEKS - 1):
                model.add(x[i, j, w] + x[j, i, w] + x[i, j, w + 1] + x[j, i, w + 1] <= 1)

    # C6: max 3 consecutive home games, and a 3-streak can happen at most once per season.
    # Same for away games. A "home indicator" h[i,w] = 1 iff team i is home in week w.
    h: dict[tuple[int, int], cp_model.IntVar] = {}
    for i in team_ids:
        for w in weeks:
            h[i, w] = model.new_bool_var(f"h_{i}_w{w}")
            model.add(h[i, w] == sum(x[i, j, w] for j in team_ids if j != i))

    for i in team_ids:
        # No 4 consecutive home games
        for w in range(NUM_WEEKS - 3):
            model.add(h[i, w] + h[i, w + 1] + h[i, w + 2] + h[i, w + 3] <= 3)

        # No 4 consecutive away games (away = not home, so 4 consecutive away
        # means 0 home in a 4-week window)
        for w in range(NUM_WEEKS - 3):
            model.add(h[i, w] + h[i, w + 1] + h[i, w + 2] + h[i, w + 3] >= 1)

        # A 3-home-streak can happen at most once per season.
        # streak3h[i,w] = 1 iff weeks w, w+1, w+2 are all home.
        streak3h: list[cp_model.IntVar] = []
        for w in range(NUM_WEEKS - 2):
            s = model.new_bool_var(f"s3h_{i}_w{w}")
            model.add_bool_and([h[i, w], h[i, w + 1], h[i, w + 2]]).only_enforce_if(s)
            model.add_bool_or(
                [h[i, w].Not(), h[i, w + 1].Not(), h[i, w + 2].Not()]
            ).only_enforce_if(s.Not())
            streak3h.append(s)
        model.add(sum(streak3h) <= 1)

        # A 3-away-streak can happen at most once per season.
        streak3a: list[cp_model.IntVar] = []
        for w in range(NUM_WEEKS - 2):
            s = model.new_bool_var(f"s3a_{i}_w{w}")
            model.add_bool_and(
                [h[i, w].Not(), h[i, w + 1].Not(), h[i, w + 2].Not()]
            ).only_enforce_if(s)
            model.add_bool_or([h[i, w], h[i, w + 1], h[i, w + 2]]).only_enforce_if(s.Not())
            streak3a.append(s)
        model.add(sum(streak3a) <= 1)

    # C7: max 2 consecutive divisional games.
    # d[i,w] = 1 iff team i plays a division opponent in week w.
    div_opponents = {}
    for t in TEAMS:
        div_opponents[t.id] = [o.id for o in TEAMS if o.division == t.division and o.id != t.id]

    d: dict[tuple[int, int], cp_model.IntVar] = {}
    for i in team_ids:
        for w in weeks:
            d[i, w] = model.new_bool_var(f"d_{i}_w{w}")
            model.add(d[i, w] == sum(x[i, j, w] + x[j, i, w] for j in div_opponents[i]))

    for i in team_ids:
        # No 3 consecutive division games
        for w in range(NUM_WEEKS - 2):
            model.add(d[i, w] + d[i, w + 1] + d[i, w + 2] <= 2)

    # C8: no consecutive divisional games in weeks 1-2
    for i in team_ids:
        model.add(d[i, 0] + d[i, 1] <= 1)

    # C9: divisional density caps by division size
    four_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)}
    five_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_WEST, Division.NFC_WEST)}
    for i in five_team_ids:
        for w in range(NUM_WEEKS - 10):
            model.add(sum(d[i, w + k] for k in range(11)) <= 7)
    for i in four_team_ids:
        for w in range(NUM_WEEKS - 7):
            model.add(sum(d[i, w + k] for k in range(8)) <= 5)

    # C10: at least half of divisional games in the last 8 weeks
    second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
    for i in five_team_ids:
        model.add(sum(d[i, w] for w in second_half) >= 4)
    for i in four_team_ids:
        model.add(sum(d[i, w] for w in second_half) >= 3)

    # C11: divisional opponent interleaving — for each team, at least
    # min_interleaved opponents must have a game by a different divisional
    # opponent between their two meetings (prevents AABBCCDD patterns).
    min_interleaved = 2
    for i in team_ids:
        opps = div_opponents[i]
        # Per opponent: compute first and second meeting weeks
        first_meet: dict[int, cp_model.IntVar] = {}
        second_meet: dict[int, cp_model.IntVar] = {}
        for j in opps:
            wh = model.new_int_var(0, NUM_WEEKS - 1, f"wh_{i}_{j}")
            wa = model.new_int_var(0, NUM_WEEKS - 1, f"wa_{i}_{j}")
            model.add(wh == sum(w * x[i, j, w] for w in weeks))
            model.add(wa == sum(w * x[j, i, w] for w in weeks))
            w1 = model.new_int_var(0, NUM_WEEKS - 1, f"fm_{i}_{j}")
            w2 = model.new_int_var(0, NUM_WEEKS - 1, f"sm_{i}_{j}")
            model.add_min_equality(w1, [wh, wa])
            model.add_max_equality(w2, [wh, wa])
            first_meet[j] = w1
            second_meet[j] = w2

        # For each opponent j, check if any other opponent k has a game
        # between j's two meetings. If so, j is interleaved.
        interleaved: list[cp_model.IntVar] = []
        for j in opps:
            il = model.new_bool_var(f"il_{i}_{j}")
            between_vars: list[cp_model.IntVar] = []
            for k in opps:
                if k == j:
                    continue
                # bk = 1 if k's first meeting falls between j's two meetings
                bk1 = model.new_bool_var(f"btw_{i}_{j}_{k}_1")
                model.add(first_meet[k] > first_meet[j]).only_enforce_if(bk1)
                model.add(first_meet[k] < second_meet[j]).only_enforce_if(bk1)
                between_vars.append(bk1)
                # bk2 = 1 if k's second meeting falls between j's two meetings
                bk2 = model.new_bool_var(f"btw_{i}_{j}_{k}_2")
                model.add(second_meet[k] > first_meet[j]).only_enforce_if(bk2)
                model.add(second_meet[k] < second_meet[j]).only_enforce_if(bk2)
                between_vars.append(bk2)
            model.add_bool_or(between_vars).only_enforce_if(il)
            interleaved.append(il)

        model.add(sum(interleaved) >= min_interleaved)

    # C12: strength of schedule — playoff-based non-conference matchups
    if playoffs is not None:
        playoffs.validate()
        div_winners, wild_cards = playoffs.resolved()

        for team in div_winners:
            # Division winners play both division winners from the other conference
            other_dws = [t for t in div_winners if t.conference != team.conference]
            for opp in other_dws:
                i, j = team.id, opp.id
                model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) == 1)

            # Division winners play exactly 1 wild card from the other conference
            other_wcs = [t for t in wild_cards if t.conference != team.conference]
            model.add(
                sum(
                    x[team.id, opp.id, w] + x[opp.id, team.id, w]
                    for opp in other_wcs
                    for w in weeks
                )
                == 1
            )

        for team in wild_cards:
            # Wild cards play exactly 1 division winner from the other conference
            other_dws = [t for t in div_winners if t.conference != team.conference]
            model.add(
                sum(
                    x[team.id, opp.id, w] + x[opp.id, team.id, w]
                    for opp in other_dws
                    for w in weeks
                )
                == 1
            )

            # Wild cards play both wild cards from the other conference
            other_wcs = [t for t in wild_cards if t.conference != team.conference]
            for opp in other_wcs:
                i, j = team.id, opp.id
                model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) == 1)

        # Non-playoff teams face at most 1 non-conference division winner
        all_playoff_ids = {t.id for t in div_winners + wild_cards}
        for i in team_ids:
            if i in all_playoff_ids:
                continue
            other_dws = [t for t in div_winners if t.conference != team_by_id[i].conference]
            model.add(sum(x[i, t.id, w] + x[t.id, i, w] for t in other_dws for w in weeks) <= 1)

        # Each non-playoff team faces exactly 1 or 2 non-conference playoff
        # opponents. The count is deterministic from the playoff composition:
        # 5 free slots → all get 1; 6 → top-ranked gets 2; 7 → top 2 get 2.
        # Equalities propagate much faster than >= / <= pairs in CP-SAT.
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
                model.add(
                    sum(
                        x[t.id, opp.id, w] + x[opp.id, t.id, w]
                        for opp in other_conf_playoff
                        for w in weeks
                    )
                    == target
                )

    # C13: last week has exactly 8 divisional games and 1 inter-division game
    # between the two last-place teams from the 5-team divisions.
    last_week = NUM_WEEKS - 1
    model.add(sum(x[i, j, last_week] + x[j, i, last_week] for i, j in intra_div_pairs) == 8)

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
        model.add(x[i, j, last_week] + x[j, i, last_week] == 1)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = seed
    solver.parameters.randomize_search = True
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = time_limit

    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SchedulerError(
            f"CP-SAT returned status {solver.status_name(status)} — no feasible schedule"
        )

    games: list[Game] = []
    for (i, j, w), var in x.items():
        if solver.value(var) == 1:
            games.append(Game(week=w + 1, home=team_by_id[i], away=team_by_id[j]))

    return Schedule(games=tuple(games))
