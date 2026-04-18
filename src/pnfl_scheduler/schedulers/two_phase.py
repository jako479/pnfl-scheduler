"""Two-phase PNFL scheduler.

Phase 1 builds the full opponent inventory before any week placement:
divisional home-and-homes, same-conference cross-division games, 3 fixed
non-conference opponents from the conference rank table, 1 extra AFC East vs
NFC East rank-based pairing for teams in the four-team divisions, then 1 final
history-based AFC vs NFC pairing for every team. That yields 5 non-conference
games for four-team divisions and 4 non-conference games for five-team
divisions.

Phase 2 uses CP-SAT to place that full inventory into the calendar while keeping the
existing weekly/home-away sequencing constraints.

Schedule requirements enforced by this scheduler:

Basic schedule structure and inventory requirements:
- Each team plays 16 total games, exactly 1 in each week.
- Each team hosts exactly 8 games.
- No pair of teams may play each other in back-to-back weeks.

Home/away sequencing requirements:
- No 4 straight home or away games.
- At most 1 total 3-game home/away streak per team.
- No 3-game home/away streak to start or end the season.
- Every 6-game span must contain between 2 and 4 home games.

Divisional scheduling requirements:
- Each team plays every divisional opponent twice, once at home and once away.
- No 4 straight divisional games.
- Either 0 teams or exactly 2 teams may open the season with back-to-back divisional games.
- No 3 straight divisional games to start or end the season.
- At most 1 total 3-game divisional streak per team.
- 5-team divisions: max 7 divisional games in any 10-game span and no 7 in any 9-game span.
- 4-team divisions: max 5 divisional games in any 8-game span and no 4 in any 7-game span.
- At least half of each team's divisional games must occur in the second half of the season.
- At most 2 divisional opponents may be non-interleaved between a team's 2 meetings with that rival.
- Every team must play at least 1 divisional game in the final 2 weeks.
- Week 16 must contain exactly 8 divisional games.

Conference scheduling requirements:
- Each team plays every same-conference opponent outside its division exactly once.
- Conference home balance:
  - 5-team division teams host exactly 2 of 4.
  - In each 4-team division, the 5 conference games split 2, 2, 3, 3 across the 4 teams.

Non-conference scheduling requirements:
- After divisional and same-conference games are assigned, the remaining schedule slots are
  non-conference games.
- 5-team division teams play 4 non-conference games.
- 4-team division teams play 5 non-conference games.
- Non-conference home balance:
  - 5-team division teams host exactly 2 of 4.
  - In each 4-team division, the 5 non-conference games split 2, 2, 3, 3 across the 4 teams.

NFL guideposts based on 5-team division data from 1999-2001 and 4-team division data
from 2016-2025:

Home/away:
- 3-game home/away streaks are common, so the model allows them but prevents multiple for any 1 team.
- 3-game home/away streaks at the start or end of the season are very rare, so the model forbids them.
- 5-of-6 home/away windows are rare, so every 6-game span is capped at 4 home or away games. However,
  common to have 4 in a 5-game span, so that's allowed.

Divisional:
- Modern NFL averages 3.4 teams/season open the season with back-to-back divisional games, and it's
  exceptionally rare for just 1 team, so allows at most 1 pair of teams to open the season with
  back-to-back divisional games.
- 3 straight divisional games are common, so the model allows them but prevents multiple for any 1 team.
- 3 straight divisional games at the start or end of the season are rare, so the model forbids them.
- For 5-team divisions, very rare to have 8 div games in a 10-game span, so capping at 7 in 10 games
  and preventing 7 in 9 games.
- For 4-team divisions, very rare to have all 6 div games in an 8-game span, so capping at 5 in 8 games
  and preventing 4 in 7 games.
- Modern NFL tries to back-load divisional games to the last half of the season, so at least
  half of each team's divisional games must occur in the second half of the season.

PNFL policy choices layered on top of those guideposts:
- All teams have at least one divisional game in the final two weeks.
- Week 16 is forced to have 8 divisional games (the most possible) and a single non-conference game.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ortools.graph.python import linear_sum_assignment
from ortools.sat.python import cp_model

from ..app.config import ConferenceRanking
from ..domain.history import NonConfHistory
from ..domain.schedule import Game, Schedule
from ..domain.teams import NUM_WEEKS, TEAMS, Conference, Division, Team, lookup_team

MatchupPair = tuple[int, int]
PhaseOneInventory = tuple[MatchupPair, ...]
# 8/5 ratio results in 1.60x multiplier on H2H cost
H2H_COST_SCALE = 8
INVERSE_RANK_COST_SCALE = 5
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

TEAM_BY_ID = {team.id: team for team in TEAMS}


class SchedulerError(RuntimeError):
    """Raised when the scheduler cannot build a valid matchup inventory or schedule."""


@dataclass
class _PhaseOneState:
    matchups: list[MatchupPair]
    selected_nonconference: set[MatchupPair]
    remaining_nonconference: dict[int, int]


def _canonical_pair(team_a: Team, team_b: Team) -> MatchupPair:
    return (min(team_a.id, team_b.id), max(team_a.id, team_b.id))


def _is_nonconference_pair(pair: MatchupPair) -> bool:
    return TEAM_BY_ID[pair[0]].conference != TEAM_BY_ID[pair[1]].conference


def _required_nonconference_games(team: Team) -> int:
    return 5 if team.division in (Division.AFC_EAST, Division.NFC_EAST) else 4


def _new_phase_one_state() -> _PhaseOneState:
    return _PhaseOneState(
        matchups=[],
        selected_nonconference=set(),
        remaining_nonconference={team.id: _required_nonconference_games(team) for team in TEAMS},
    )


def _normalize_conference_ranking(
    conference_ranking: ConferenceRanking | Mapping[Conference | str, Sequence[str]] | None,
) -> dict[Conference, tuple[Team, ...]]:
    if conference_ranking is None:
        raise SchedulerError("Two-phase scheduler requires conference_ranking input")

    if isinstance(conference_ranking, ConferenceRanking):
        raw_rankings: dict[Conference, Sequence[str]] = {
            Conference.AFC: conference_ranking.AFC,
            Conference.NFC: conference_ranking.NFC,
        }
    else:
        raw_rankings = {}
        for conf in Conference:
            if conf in conference_ranking:
                raw_rankings[conf] = conference_ranking[conf]
            elif conf.value in conference_ranking:
                raw_rankings[conf] = conference_ranking[conf.value]
            else:
                raise SchedulerError(f"conference_ranking missing {conf.value} list")

    ranked_teams_by_conf: dict[Conference, tuple[Team, ...]] = {}
    all_ranked_ids: set[int] = set()
    for conf in Conference:
        ranked_teams = tuple(lookup_team(city) for city in raw_rankings[conf])
        if len(ranked_teams) != 9:
            raise SchedulerError(f"Expected 9 ranked {conf.value} teams, got {len(ranked_teams)}")
        if any(team.conference != conf for team in ranked_teams):
            raise SchedulerError(f"{conf.value} ranking contains a team from the wrong conference")
        if len({team.id for team in ranked_teams}) != 9:
            raise SchedulerError(f"Duplicate team in {conf.value} conference ranking")
        overlap = {team.id for team in ranked_teams} & all_ranked_ids
        if overlap:
            raise SchedulerError(f"Conference ranking reuses teams across conferences: {sorted(overlap)}")
        all_ranked_ids |= {team.id for team in ranked_teams}
        ranked_teams_by_conf[conf] = ranked_teams

    if len(all_ranked_ids) != len(TEAMS):
        raise SchedulerError("Conference ranking must include all 18 teams exactly once")
    return ranked_teams_by_conf


def _rank_by_id(ranked_teams_by_conf: Mapping[Conference, Sequence[Team]]) -> dict[int, int]:
    rank_by_id: dict[int, int] = {}
    for conf in Conference:
        for rank, team in enumerate(ranked_teams_by_conf[conf], start=1):
            rank_by_id[team.id] = rank
    return rank_by_id


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


def _fixed_rank_pairs(ranked_teams_by_conf: Mapping[Conference, Sequence[Team]]) -> set[MatchupPair]:
    afc_ranked = ranked_teams_by_conf[Conference.AFC]
    nfc_ranked = ranked_teams_by_conf[Conference.NFC]

    fixed_pairs: set[MatchupPair] = set()
    for rank, afc_team in enumerate(afc_ranked, start=1):
        for opp_rank in FIXED_NONCONF_RANK_OPPONENTS[rank]:
            fixed_pairs.add(_canonical_pair(afc_team, nfc_ranked[opp_rank - 1]))
    return fixed_pairs


def _pseudo_inverse_target_rank(rank: int) -> int:
    if rank == 5:
        return 5
    if rank < 5:
        return rank + 5
    return rank - 5


def _pseudo_inverse_rank_cost(team_a: Team, team_b: Team, rank_by_id: dict[int, int]) -> int:
    """Directional cost for the final AFC->NFC H2H assignment.

    The preferred opponent ranks are 1->6, 2->7, 3->8, 4->9, 5->5, 6->1,
    7->2, 8->3, 9->4. For ranks 1-4, moving to a harder opponent than that
    target costs more per slot. For ranks 6-9, moving to an easier opponent
    than that target costs more per slot. Rank 5 is the neutral pivot and
    uses a symmetric cost around rank 5.
    """
    team_rank = rank_by_id[team_a.id]
    target_rank = _pseudo_inverse_target_rank(team_rank)
    opp_rank = rank_by_id[team_b.id]
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


def _history_pair_cost(
    team_a: Team,
    team_b: Team,
    rank_by_id: dict[int, int],
    history: NonConfHistory | None,
    season: int | None,
) -> int:
    inverse_rank_cost = _pseudo_inverse_rank_cost(team_a, team_b, rank_by_id)
    if history is None or season is None:
        return INVERSE_RANK_COST_SCALE * inverse_rank_cost

    return H2H_COST_SCALE * history.opponent_cost(team_a, team_b, season) + INVERSE_RANK_COST_SCALE * inverse_rank_cost


def _add_nonconference_pairs(state: _PhaseOneState, pairs: set[MatchupPair]) -> None:
    for i, j in sorted(pairs):
        pair = (i, j)
        if pair in state.selected_nonconference:
            raise SchedulerError(f"Duplicate non-conference pair in phase-1 inventory: {pair}")
        state.matchups.append(pair)
        state.selected_nonconference.add(pair)
        state.remaining_nonconference[i] -= 1
        state.remaining_nonconference[j] -= 1
        if state.remaining_nonconference[i] < 0 or state.remaining_nonconference[j] < 0:
            raise SchedulerError(f"Non-conference slot count went negative after reserving pair {pair}")


def _solve_exact_assignment(
    left_teams: list[Team],
    right_teams: list[Team],
    cost_fn,
    forbidden_pairs: set[MatchupPair] | None = None,
) -> set[MatchupPair]:
    """Solve one-to-one bipartite matching with additive edge costs."""
    if forbidden_pairs is None:
        forbidden_pairs = set()
    if len(left_teams) != len(right_teams):
        raise SchedulerError(f"Unbalanced assignment sides: left={len(left_teams)}, right={len(right_teams)}")

    assignment = linear_sum_assignment.SimpleLinearSumAssignment()
    left_index = {team.id: idx for idx, team in enumerate(left_teams)}
    right_index = {team.id: idx for idx, team in enumerate(right_teams)}
    left_by_index = {idx: team for idx, team in enumerate(left_teams)}
    right_by_index = {idx: team for idx, team in enumerate(right_teams)}

    for left in left_teams:
        for right in right_teams:
            pair = _canonical_pair(left, right)
            if pair in forbidden_pairs:
                continue
            assignment.add_arc_with_cost(left_index[left.id], right_index[right.id], cost_fn(left, right))

    status = assignment.solve()
    if status != assignment.OPTIMAL:
        raise SchedulerError(f"LinearSumAssignment failed with status {status}")

    selected: set[MatchupPair] = set()
    for left_idx, left_team in left_by_index.items():
        right_idx = assignment.right_mate(left_idx)
        if right_idx < 0:
            raise SchedulerError(f"Assignment left {left_team.city} unmatched")
        selected.add(_canonical_pair(left_team, right_by_index[right_idx]))
    return selected


def _add_divisional_matchups(state: _PhaseOneState) -> None:
    for i, team_i in enumerate(TEAMS):
        for team_j in TEAMS[i + 1 :]:
            if team_i.division == team_j.division:
                pair = _canonical_pair(team_i, team_j)
                state.matchups.append(pair)
                state.matchups.append(pair)


def _add_conference_matchups(state: _PhaseOneState) -> None:
    for i, team_i in enumerate(TEAMS):
        for team_j in TEAMS[i + 1 :]:
            if team_i.conference == team_j.conference and team_i.division != team_j.division:
                state.matchups.append(_canonical_pair(team_i, team_j))


def _add_fixed_rank_nonconference_matchups(
    state: _PhaseOneState,
    ranked_teams_by_conf: Mapping[Conference, Sequence[Team]],
) -> None:
    _add_nonconference_pairs(state, _fixed_rank_pairs(ranked_teams_by_conf))


def _solve_four_team_extra_rank_pairs(
    ranked_teams_by_conf: Mapping[Conference, Sequence[Team]],
    rank_by_id: dict[int, int],
    forbidden_pairs: set[MatchupPair],
) -> set[MatchupPair]:
    afc_east = [team for team in ranked_teams_by_conf[Conference.AFC] if team.division == Division.AFC_EAST]
    nfc_east = [team for team in ranked_teams_by_conf[Conference.NFC] if team.division == Division.NFC_EAST]
    if len(afc_east) != 4 or len(nfc_east) != 4:
        raise SchedulerError("Expected exactly 4 teams per East division for extra SOS assignment")

    return _solve_exact_assignment(
        afc_east,
        nfc_east,
        lambda left, right: abs(rank_by_id[left.id] - rank_by_id[right.id]),
        forbidden_pairs=forbidden_pairs,
    )


def _add_four_team_extra_rank_matchups(
    state: _PhaseOneState,
    ranked_teams_by_conf: Mapping[Conference, Sequence[Team]],
    rank_by_id: dict[int, int],
) -> None:
    extra_pairs = _solve_four_team_extra_rank_pairs(
        ranked_teams_by_conf=ranked_teams_by_conf,
        rank_by_id=rank_by_id,
        forbidden_pairs=state.selected_nonconference,
    )
    _add_nonconference_pairs(state, extra_pairs)


def _add_history_matchups(
    state: _PhaseOneState,
    rank_by_id: dict[int, int],
    history: NonConfHistory | None,
    season: int | None,
) -> None:
    afc_remaining = [team for team in TEAMS if team.conference == Conference.AFC and state.remaining_nonconference[team.id] > 0]
    nfc_remaining = [team for team in TEAMS if team.conference == Conference.NFC and state.remaining_nonconference[team.id] > 0]
    if {state.remaining_nonconference[team.id] for team in afc_remaining + nfc_remaining} - {1}:
        unresolved = {TEAM_BY_ID[team_id].city: remaining for team_id, remaining in state.remaining_nonconference.items() if remaining > 0}
        raise SchedulerError(f"History step expected only single-slot teams, got {unresolved}")

    history_pairs = _solve_exact_assignment(
        afc_remaining,
        nfc_remaining,
        lambda left, right: _history_pair_cost(left, right, rank_by_id, history, season),
        forbidden_pairs=state.selected_nonconference,
    )
    _add_nonconference_pairs(state, history_pairs)


def build_phase_one_matchup_inventory(
    conference_ranking: ConferenceRanking | Mapping[Conference | str, Sequence[str]] | None,
    history: NonConfHistory | None = None,
    season: int | None = None,
) -> PhaseOneInventory:
    """Build the full season opponent inventory in phase-1 order."""
    _validate_fixed_rank_table()
    ranked_teams_by_conf = _normalize_conference_ranking(conference_ranking)
    rank_by_id = _rank_by_id(ranked_teams_by_conf)
    state = _new_phase_one_state()
    _add_divisional_matchups(state)
    _add_conference_matchups(state)
    _add_fixed_rank_nonconference_matchups(state, ranked_teams_by_conf)
    _add_four_team_extra_rank_matchups(state, ranked_teams_by_conf, rank_by_id)
    _add_history_matchups(state, rank_by_id, history, season)

    if any(slots != 0 for slots in state.remaining_nonconference.values()):
        unresolved = {TEAM_BY_ID[team_id].city: slots for team_id, slots in state.remaining_nonconference.items() if slots != 0}
        raise SchedulerError(f"Non-conference inventory left unresolved slots: {unresolved}")
    if len(state.selected_nonconference) != 40:
        raise SchedulerError(f"Expected 40 non-conference games, got {len(state.selected_nonconference)}")
    if len(state.matchups) != 144:
        raise SchedulerError(f"Expected 144 total matchups in phase-1 inventory, got {len(state.matchups)}")

    return tuple(state.matchups)


def compute_nonconference_inventory(
    conference_ranking: ConferenceRanking | Mapping[Conference | str, Sequence[str]] | None,
    history: NonConfHistory | None = None,
) -> set[MatchupPair]:
    """Return just the non-conference subset of the phase-1 inventory.

    This wrapper is kept so existing callers can inspect the selected
    non-conference opponent set without needing the full inventory.
    """
    return {
        pair
        for pair in build_phase_one_matchup_inventory(
            conference_ranking=conference_ranking,
            history=history,
        )
        if _is_nonconference_pair(pair)
    }


class _ScheduleModel:
    """Encapsulates the CP-SAT placement model for the two-phase scheduler.

    Hard constraints
    ----------------
    C1  Each team plays exactly one game per week.
    C2  Each team has exactly 8 home games across the season.
    C3  Max 3 consecutive home/away games.
    C4  Max 1 total 3-game home/away streak across the whole season, and none
        may occur at the start or end of the season. Also, no team may have
        more than 4 home games or 4 away games in any 6-game span.
    C5  No back-to-back games between the same two teams.
    C6  Pair meeting counts are fixed by the phase-1 inventory.
    C7  Each divisional pair splits its two meetings one home game each.
    C8  Conference matchup home balance: five-team division teams host 2 of their 4
        cross-division conference games; in each four-team division, the 5-game split
        is 2, 2, 3, 3 home games across the four teams.
    C9  Non-conference home balance: five-team division teams host exactly 2 of their
        4 non-conference games; in each four-team division, the 5-game split is
        2, 2, 3, 3 home games across the four teams.
    C10 Max 3 consecutive divisional games. At most 1 pair of teams may open
        with 2 straight divisional games, no team may start or end the season
        with 3 straight divisional games, and each team may have at most 1
        total 3-game divisional streak.
    C11 Teams in five-team divisions: max 7 divisional games in any 10-game span
        and no 7 divisional games in any 9-game span. Teams in four-team divisions:
        max 5 divisional games in any 8-game span and no 4 divisional games in any
        7-game span.
    C12 At least half of each team's divisional games fall in the last half of the season.
    C13 Divisional opponent interleaving: at most 2 divisional opponents may have
        no other divisional meeting between their two meetings (limits AABBCCDD patterns).
    C14 Week 16: 8 divisional games.
    C15 Each team must play at least one divisional game in the last two weeks.
    """

    def __init__(self) -> None:
        self.model = cp_model.CpModel()

        self.team_ids = [t.id for t in TEAMS]
        self.weeks = range(NUM_WEEKS)
        self.home_games_per_team = 8
        self.team_by_id = {t.id: t for t in TEAMS}

        self.div_opponents: dict[int, list[int]] = {}
        for team in TEAMS:
            self.div_opponents[team.id] = [opp.id for opp in TEAMS if opp.division == team.division and opp.id != team.id]

        self.four_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)}
        self.five_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_WEST, Division.NFC_WEST)}

        self.divisional_pairs: list[MatchupPair] = []
        self.conference_pairs: list[MatchupPair] = []
        self.non_conference_pairs: list[MatchupPair] = []
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                team_i = self.team_by_id[i]
                team_j = self.team_by_id[j]
                if team_i.division == team_j.division:
                    self.divisional_pairs.append((i, j))
                elif team_i.conference == team_j.conference:
                    self.conference_pairs.append((i, j))
                else:
                    self.non_conference_pairs.append((i, j))

        self.x: dict[tuple[int, int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for j in self.team_ids:
                if i == j:
                    continue
                for w in self.weeks:
                    self.x[i, j, w] = self.model.new_bool_var(f"x_{i}_{j}_w{w}")

        self.h: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for w in self.weeks:
                self.h[i, w] = self.model.new_bool_var(f"h_{i}_w{w}")
                self.model.add(self.h[i, w] == sum(self.x[i, j, w] for j in self.team_ids if j != i))

        self.d: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in self.team_ids:
            for w in self.weeks:
                self.d[i, w] = self.model.new_bool_var(f"d_{i}_w{w}")
                self.model.add(self.d[i, w] == sum(self.x[i, j, w] + self.x[j, i, w] for j in self.div_opponents[i]))

    def _constraint_one_game_per_week(self) -> None:
        # Require each team to play exactly 1 game in each of the 16 weeks.
        for i in self.team_ids:
            for w in self.weeks:
                self.model.add(sum(self.x[i, j, w] + self.x[j, i, w] for j in self.team_ids if j != i) == 1)

    def _constraint_home_balance(self) -> None:
        # Require each team to host exactly 8 home games.
        for i in self.team_ids:
            self.model.add(sum(self.x[i, j, w] for j in self.team_ids if j != i for w in self.weeks) == self.home_games_per_team)

    def _constraint_no_four_straight_home_or_away(self) -> None:
        # Every 4-game window must contain at least 1 home and at least 1 away game.
        for i in self.team_ids:
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] <= 3)
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[i, w] + self.h[i, w + 1] + self.h[i, w + 2] + self.h[i, w + 3] >= 1)

    def _constraint_home_away_balance_in_six_game_windows(self) -> None:
        # Every 6-game window must have between 2 and 4 home games, which also forces 2 to 4 away games.
        for i in self.team_ids:
            for w in range(NUM_WEEKS - 5):
                six_game_home_total = sum(self.h[i, w + k] for k in range(6))
                self.model.add(six_game_home_total <= 4)
                self.model.add(six_game_home_total >= 2)

    def _constraint_no_three_game_home_or_away_streak_at_season_start_or_end(self) -> None:
        # The first and last 3 games must each contain at least 1 home and at least 1 away game.
        for i in self.team_ids:
            self.model.add(self.h[i, 0] + self.h[i, 1] + self.h[i, 2] <= 2)
            self.model.add(self.h[i, 0] + self.h[i, 1] + self.h[i, 2] >= 1)
            self.model.add(self.h[i, NUM_WEEKS - 3] + self.h[i, NUM_WEEKS - 2] + self.h[i, NUM_WEEKS - 1] <= 2)
            self.model.add(self.h[i, NUM_WEEKS - 3] + self.h[i, NUM_WEEKS - 2] + self.h[i, NUM_WEEKS - 1] >= 1)

    def _constraint_max_one_total_three_game_home_or_away_streak(self) -> None:
        # Allow at most one 3-game streak total, counting both home and away streaks together.
        for i in self.team_ids:
            # Track each 3-game all-home window so the total number of home streaks can be capped.
            streak3h: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3h_{i}_w{w}")
                self.model.add_bool_and([self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]).only_enforce_if(streak)
                self.model.add_bool_or([self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]).only_enforce_if(streak.Not())
                streak3h.append(streak)

            # Track each 3-game all-away window so home and away streaks can share one combined cap.
            streak3a: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3a_{i}_w{w}")
                self.model.add_bool_and([self.h[i, w].Not(), self.h[i, w + 1].Not(), self.h[i, w + 2].Not()]).only_enforce_if(streak)
                self.model.add_bool_or([self.h[i, w], self.h[i, w + 1], self.h[i, w + 2]]).only_enforce_if(streak.Not())
                streak3a.append(streak)

            self.model.add(sum(streak3h) + sum(streak3a) <= 1)

    def _constraint_no_back_to_back(self) -> None:
        # Prevent any pair of teams from playing in consecutive weeks.
        for i in self.team_ids:
            for j in self.team_ids:
                if i >= j:
                    continue
                for w in range(NUM_WEEKS - 1):
                    self.model.add(self.x[i, j, w] + self.x[j, i, w] + self.x[i, j, w + 1] + self.x[j, i, w + 1] <= 1)

    def _constraint_phase_one_inventory(self, phase_one_inventory: PhaseOneInventory) -> None:
        # Force phase II to schedule each team pair exactly as many times as phase I selected: 0, 1, or 2 meetings.
        expected_counts = Counter(phase_one_inventory)
        all_pairs = self.divisional_pairs + self.conference_pairs + self.non_conference_pairs

        unknown_pairs = set(expected_counts) - set(all_pairs)
        if unknown_pairs:
            raise SchedulerError(f"Phase-1 inventory contains unknown team pairs: {sorted(unknown_pairs)}")

        for i, j in all_pairs:
            total_meetings = sum(self.x[i, j, w] + self.x[j, i, w] for w in self.weeks)
            self.model.add(total_meetings == expected_counts.get((i, j), 0))

    def _constraint_divisional_home_balance(self) -> None:
        # Split each divisional home-and-home into exactly 1 home game and 1 away game for each team.
        for i, j in self.divisional_pairs:
            self.model.add(sum(self.x[i, j, w] for w in self.weeks) == 1)
            self.model.add(sum(self.x[j, i, w] for w in self.weeks) == 1)

    def _constraint_conference_home_balance(self) -> None:
        # Require 5-team division teams to host exactly 2 conference cross-division games and 4-team teams to host 2 or 3.
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
                self.model.add(conf_home_games >= 2)
                self.model.add(conf_home_games <= 3)

    def _constraint_nonconference_home_balance(self) -> None:
        # Require teams in 5-team divisions to host 2 non-conference games and teams in 4-team divisions
        # to host 2 or 3.
        for i in self.team_ids:
            team = self.team_by_id[i]
            non_conference_opponents = [j for j in self.team_ids if self.team_by_id[j].conference != team.conference]
            non_conf_home_games = sum(self.x[i, j, w] for j in non_conference_opponents for w in self.weeks)

            if i in self.five_team_ids:
                self.model.add(non_conf_home_games == 2)
            else:
                self.model.add(non_conf_home_games >= 2)
                self.model.add(non_conf_home_games <= 3)

    def _constraint_max_consecutive_division(self) -> None:
        # Allow at most 3 straight divisional games but forbid any 4-game divisional streak.
        for i in self.team_ids:
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.d[i, w] + self.d[i, w + 1] + self.d[i, w + 2] + self.d[i, w + 3] <= 3)

    def _constraint_no_back_to_back_divisional_games_to_open_season(self) -> None:
        # Allow either 0 teams or exactly 2 teams to open with divisional games in both weeks 1 and 2.
        opening_back_to_back: list[cp_model.IntVar] = []
        for i in self.team_ids:
            opens_with_two_div = self.model.new_bool_var(f"open2div_{i}")
            self.model.add(opens_with_two_div <= self.d[i, 0])
            self.model.add(opens_with_two_div <= self.d[i, 1])
            self.model.add(opens_with_two_div >= self.d[i, 0] + self.d[i, 1] - 1)
            opening_back_to_back.append(opens_with_two_div)

        has_opening_pair = self.model.new_bool_var("has_opening_divisional_pair")
        self.model.add(sum(opening_back_to_back) == 2 * has_opening_pair)

    def _constraint_no_three_game_divisional_streak_at_season_start_or_end(self) -> None:
        # Forbid teams from starting or ending the season with 3 straight divisional games.
        for i in self.team_ids:
            self.model.add(self.d[i, 0] + self.d[i, 1] + self.d[i, 2] <= 2)
            self.model.add(self.d[i, NUM_WEEKS - 3] + self.d[i, NUM_WEEKS - 2] + self.d[i, NUM_WEEKS - 1] <= 2)

    def _constraint_max_one_total_three_game_divisional_streak(self) -> None:
        # Allow each team at most 1 total 3-game divisional streak across the season.
        for i in self.team_ids:
            streak3d: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3d_{i}_w{w}")
                self.model.add_bool_and([self.d[i, w], self.d[i, w + 1], self.d[i, w + 2]]).only_enforce_if(streak)
                self.model.add_bool_or([self.d[i, w].Not(), self.d[i, w + 1].Not(), self.d[i, w + 2].Not()]).only_enforce_if(streak.Not())
                streak3d.append(streak)
            self.model.add(sum(streak3d) <= 1)

    def _constraint_division_density(self) -> None:
        # Cap divisional clustering at 7 in 10 and forbid 7 in 9 for 5-team divisions; cap at 5 in 8 and forbid 4 in 7 for 4-team divisions.
        for i in self.five_team_ids:
            for w in range(NUM_WEEKS - 9):
                self.model.add(sum(self.d[i, w + k] for k in range(10)) <= 7)
            for w in range(NUM_WEEKS - 8):
                self.model.add(sum(self.d[i, w + k] for k in range(9)) <= 6)
        for i in self.four_team_ids:
            for w in range(NUM_WEEKS - 7):
                self.model.add(sum(self.d[i, w + k] for k in range(8)) <= 5)
            for w in range(NUM_WEEKS - 6):
                self.model.add(sum(self.d[i, w + k] for k in range(7)) <= 3)

    def _constraint_second_half_division(self) -> None:
        # Put at least half of each team's divisional games in weeks 9-16: 4 of 8 for 5-team divisions and 3 of 6 for 4-team divisions.
        second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
        for i in self.five_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 4)
        for i in self.four_team_ids:
            self.model.add(sum(self.d[i, w] for w in second_half) >= 3)

    def _constraint_max_two_non_interleaved_divisional_opponents(self) -> None:
        # Count a divisional opponent as interleaved if another rival's first or second meeting
        # falls between the team's first and second meeting with that opponent.
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

            # Allow at most 2 non-interleaved divisional opponents per team.
            self.model.add(sum(interleaved) >= len(opps) - 2)

    def _constraint_week_16_matchups(self) -> None:
        # Require exactly 8 of the 9 games in the final week to be divisional.
        last_week = NUM_WEEKS - 1
        self.model.add(sum(self.x[i, j, last_week] + self.x[j, i, last_week] for i, j in self.divisional_pairs) == 8)

    def _constraint_late_divisional_presence(self) -> None:
        # Ensure every team has at least 1 divisional game across the last 2 weeks.
        for i in self.team_ids:
            self.model.add(self.d[i, NUM_WEEKS - 2] + self.d[i, NUM_WEEKS - 1] >= 1)

    def build(
        self,
        phase_one_inventory: PhaseOneInventory,
    ) -> None:
        self._constraint_one_game_per_week()
        self._constraint_home_balance()
        self._constraint_no_four_straight_home_or_away()
        self._constraint_home_away_balance_in_six_game_windows()
        self._constraint_no_three_game_home_or_away_streak_at_season_start_or_end()
        self._constraint_max_one_total_three_game_home_or_away_streak()
        self._constraint_no_back_to_back()
        self._constraint_phase_one_inventory(phase_one_inventory)
        self._constraint_divisional_home_balance()
        self._constraint_conference_home_balance()
        self._constraint_nonconference_home_balance()
        self._constraint_max_consecutive_division()
        self._constraint_no_back_to_back_divisional_games_to_open_season()
        self._constraint_no_three_game_divisional_streak_at_season_start_or_end()
        self._constraint_max_one_total_three_game_divisional_streak()
        self._constraint_division_density()
        self._constraint_second_half_division()
        self._constraint_max_two_non_interleaved_divisional_opponents()
        self._constraint_week_16_matchups()
        self._constraint_late_divisional_presence()

    def solve(self, seed: int = 0, time_limit: float = 1800.0) -> Schedule:
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = seed
        solver.parameters.randomize_search = True
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.solve(self.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise SchedulerError(f"CP-SAT returned status {solver.status_name(status)} - no feasible schedule")

        games: list[Game] = []
        for (i, j, w), var in self.x.items():
            if solver.value(var) == 1:
                games.append(Game(week=w + 1, home=self.team_by_id[i], away=self.team_by_id[j]))

        return Schedule(games=tuple(games))


def solve_phase_two_schedule(
    phase_one_inventory: PhaseOneInventory,
    seed: int = 0,
    time_limit: float = 3600.0,
) -> Schedule:
    """Place the phase-1 opponent inventory into weeks and home/away slots."""
    schedule_model = _ScheduleModel()
    schedule_model.build(phase_one_inventory=phase_one_inventory)
    return schedule_model.solve(seed=seed, time_limit=time_limit)


def solve_schedule(
    seed: int = 0,
    time_limit: float = 3600.0,
    conference_ranking: ConferenceRanking | Mapping[Conference | str, Sequence[str]] | None = None,
    history: NonConfHistory | None = None,
    season: int | None = None,
) -> Schedule:
    """Overall driver: build the phase-1 inventory, then solve phase 2."""

    phase_one_inventory = build_phase_one_matchup_inventory(
        conference_ranking=conference_ranking,
        history=history,
        season=season,
    )
    return solve_phase_two_schedule(
        phase_one_inventory=phase_one_inventory,
        seed=seed,
        time_limit=time_limit,
    )
