"""Count the total number of valid schedules for the 6-free-slots config."""

import time

from ortools.sat.python import cp_model

from src.pnfl_scheduler.teams import NUM_WEEKS, TEAMS, Conference, Division, lookup_team

# 6-free-slots config: 1 WC from each div per conference
PLAYOFFS_DW = ["New England", "Cincinnati", "Washington", "Chicago"]
PLAYOFFS_WC = ["Miami", "Pittsburgh", "Atlanta", "Minnesota"]
LAST_PLACE = ("Las Vegas", "Seattle")
NON_PLAYOFF_RANKED = [
    "Buffalo",
    "Jacksonville",
    "Denver",
    "Los Angeles",
    "Las Vegas",
    "New York",
    "Philadelphia",
    "San Francisco",
    "Green Bay",
    "Seattle",
]

model = cp_model.CpModel()
team_ids = [t.id for t in TEAMS]
weeks = range(NUM_WEEKS)
home_games = NUM_WEEKS // 2
team_by_id = {t.id: t for t in TEAMS}

x = {}
for i in team_ids:
    for j in team_ids:
        if i == j:
            continue
        for w in weeks:
            x[i, j, w] = model.new_bool_var(f"x_{i}_{j}_{w}")

# One game per week
for i in team_ids:
    for w in weeks:
        model.add(sum(x[i, j, w] + x[j, i, w] for j in team_ids if j != i) == 1)

# Home balance
for i in team_ids:
    model.add(sum(x[i, j, w] for j in team_ids if j != i for w in weeks) == home_games)

intra_div = []
inter_div = []
for i in team_ids:
    for j in team_ids:
        if i >= j:
            continue
        if team_by_id[i].division == team_by_id[j].division:
            intra_div.append((i, j))
        else:
            inter_div.append((i, j))

# Divisional home-and-away matchups
for i, j in intra_div:
    model.add(sum(x[i, j, w] for w in weeks) == 1)
    model.add(sum(x[j, i, w] for w in weeks) == 1)

# Cross-division matchup counts
intra_conf = []
non_conf = []
for i, j in inter_div:
    if team_by_id[i].conference == team_by_id[j].conference:
        intra_conf.append((i, j))
    else:
        non_conf.append((i, j))
for i, j in intra_conf:
    model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) == 1)
for i, j in non_conf:
    model.add(sum(x[i, j, w] + x[j, i, w] for w in weeks) <= 1)

# No back-to-back rematches
for i in team_ids:
    for j in team_ids:
        if i >= j:
            continue
        for w in range(NUM_WEEKS - 1):
            model.add(x[i, j, w] + x[j, i, w] + x[i, j, w + 1] + x[j, i, w + 1] <= 1)

# Home and away streak limits
h = {}
for i in team_ids:
    for w in weeks:
        h[i, w] = model.new_bool_var(f"h_{i}_{w}")
        model.add(h[i, w] == sum(x[i, j, w] for j in team_ids if j != i))

for i in team_ids:
    for w in range(NUM_WEEKS - 3):
        model.add(h[i, w] + h[i, w + 1] + h[i, w + 2] + h[i, w + 3] <= 3)
        model.add(h[i, w] + h[i, w + 1] + h[i, w + 2] + h[i, w + 3] >= 1)

    streak3h = []
    for w in range(NUM_WEEKS - 2):
        s = model.new_bool_var(f"s3h_{i}_{w}")
        model.add_bool_and([h[i, w], h[i, w + 1], h[i, w + 2]]).only_enforce_if(s)
        model.add_bool_or([h[i, w].Not(), h[i, w + 1].Not(), h[i, w + 2].Not()]).only_enforce_if(
            s.Not()
        )
        streak3h.append(s)
    model.add(sum(streak3h) <= 1)

    streak3a = []
    for w in range(NUM_WEEKS - 2):
        s = model.new_bool_var(f"s3a_{i}_{w}")
        model.add_bool_and([h[i, w].Not(), h[i, w + 1].Not(), h[i, w + 2].Not()]).only_enforce_if(s)
        model.add_bool_or([h[i, w], h[i, w + 1], h[i, w + 2]]).only_enforce_if(s.Not())
        streak3a.append(s)
    model.add(sum(streak3a) <= 1)

# Maximum consecutive divisional games
div_opponents = {}
for t in TEAMS:
    div_opponents[t.id] = [o.id for o in TEAMS if o.division == t.division and o.id != t.id]

d = {}
for i in team_ids:
    for w in weeks:
        d[i, w] = model.new_bool_var(f"d_{i}_{w}")
        model.add(d[i, w] == sum(x[i, j, w] + x[j, i, w] for j in div_opponents[i]))

for i in team_ids:
    for w in range(NUM_WEEKS - 2):
        model.add(d[i, w] + d[i, w + 1] + d[i, w + 2] <= 2)

# No divisional opener in both weeks 1 and 2
for i in team_ids:
    model.add(d[i, 0] + d[i, 1] <= 1)

# Divisional density caps
four_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_EAST, Division.NFC_EAST)}
five_team_ids = {t.id for t in TEAMS if t.division in (Division.AFC_WEST, Division.NFC_WEST)}
for i in five_team_ids:
    for w in range(NUM_WEEKS - 10):
        model.add(sum(d[i, w + k] for k in range(11)) <= 7)
for i in four_team_ids:
    for w in range(NUM_WEEKS - 7):
        model.add(sum(d[i, w + k] for k in range(8)) <= 5)

# Second-half divisional minimums
second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
for i in five_team_ids:
    model.add(sum(d[i, w] for w in second_half) >= 4)
for i in four_team_ids:
    model.add(sum(d[i, w] for w in second_half) >= 3)

# Divisional interleaving
for i in team_ids:
    opps = div_opponents[i]
    fm = []
    sm = []
    for j in opps:
        wh = model.new_int_var(0, NUM_WEEKS - 1, f"wh_{i}_{j}")
        wa = model.new_int_var(0, NUM_WEEKS - 1, f"wa_{i}_{j}")
        model.add(wh == sum(w * x[i, j, w] for w in weeks))
        model.add(wa == sum(w * x[j, i, w] for w in weeks))
        w1 = model.new_int_var(0, NUM_WEEKS - 1, f"fm_{i}_{j}")
        w2 = model.new_int_var(0, NUM_WEEKS - 1, f"sm_{i}_{j}")
        model.add_min_equality(w1, [wh, wa])
        model.add_max_equality(w2, [wh, wa])
        fm.append(w1)
        sm.append(w2)
    lf = model.new_int_var(0, NUM_WEEKS - 1, f"lf_{i}")
    es = model.new_int_var(0, NUM_WEEKS - 1, f"es_{i}")
    model.add_max_equality(lf, fm)
    model.add_min_equality(es, sm)
    model.add(lf < es)

# Final-week matchup pattern
last_week = NUM_WEEKS - 1
model.add(sum(x[i, j, last_week] + x[j, i, last_week] for i, j in intra_div) == 8)
lp_a = lookup_team(LAST_PLACE[0])
lp_b = lookup_team(LAST_PLACE[1])
model.add(x[lp_a.id, lp_b.id, last_week] + x[lp_b.id, lp_a.id, last_week] == 1)

# Strength of schedule
dw = [lookup_team(c) for c in PLAYOFFS_DW]
wc = [lookup_team(c) for c in PLAYOFFS_WC]

for team in dw:
    other_dws = [t for t in dw if t.conference != team.conference]
    for opp in other_dws:
        model.add(sum(x[team.id, opp.id, w] + x[opp.id, team.id, w] for w in weeks) == 1)
    other_wcs = [t for t in wc if t.conference != team.conference]
    model.add(
        sum(x[team.id, opp.id, w] + x[opp.id, team.id, w] for opp in other_wcs for w in weeks) == 1
    )

for team in wc:
    other_dws = [t for t in dw if t.conference != team.conference]
    model.add(
        sum(x[team.id, opp.id, w] + x[opp.id, team.id, w] for opp in other_dws for w in weeks) == 1
    )
    other_wcs = [t for t in wc if t.conference != team.conference]
    for opp in other_wcs:
        model.add(sum(x[team.id, opp.id, w] + x[opp.id, team.id, w] for w in weeks) == 1)

all_playoff_ids = {t.id for t in dw + wc}
for i in team_ids:
    if i in all_playoff_ids:
        continue
    other_dws = [t for t in dw if t.conference != team_by_id[i].conference]
    model.add(sum(x[i, t.id, w] + x[t.id, i, w] for t in other_dws for w in weeks) <= 1)

np_ranked = [lookup_team(c) for c in NON_PLAYOFF_RANKED]
all_playoff = dw + wc
for conf in [Conference.AFC, Conference.NFC]:
    other_conf_po = [t for t in all_playoff if t.conference != conf]
    np_in_conf = [t for t in np_ranked if t.conference == conf]
    free_slots = 0
    for t in other_conf_po:
        if t.division in (Division.AFC_EAST, Division.NFC_EAST):
            free_slots += 2
        else:
            free_slots += 1
    overflow = free_slots - len(np_in_conf)
    for rank, t in enumerate(np_in_conf):
        target = 2 if rank < overflow else 1
        model.add(
            sum(x[t.id, opp.id, w] + x[opp.id, t.id, w] for opp in other_conf_po for w in weeks)
            == target
        )


# Enumerate and bucket by close-rematch count
class Analyzer(cp_model.CpSolverSolutionCallback):
    def __init__(self, x_vars, intra_div_pairs, num_weeks):
        super().__init__()
        self.x = x_vars
        self.intra_div_pairs = intra_div_pairs
        self.num_weeks = num_weeks
        self.count = 0
        self.buckets = {}  # {close_rematch_count: number_of_schedules}
        self.start = time.time()

    def on_solution_callback(self):
        self.count += 1
        # Count divisional pairs whose two meetings are within a 3-week span
        close = 0
        for i, j in self.intra_div_pairs:
            meet_weeks = []
            for w in range(self.num_weeks):
                if self.value(self.x[i, j, w]) + self.value(self.x[j, i, w]) == 1:
                    meet_weeks.append(w)
            if len(meet_weeks) == 2 and meet_weeks[1] - meet_weeks[0] <= 2:
                close += 1
        self.buckets[close] = self.buckets.get(close, 0) + 1
        if self.count % 1000 == 0:
            elapsed = time.time() - self.start
            print(
                f"{self.count} solutions in {elapsed:.0f}s — buckets so far: {dict(sorted(self.buckets.items()))}",
                flush=True,
            )


solver = cp_model.CpSolver()
solver.parameters.num_search_workers = 1
solver.parameters.enumerate_all_solutions = True
solver.parameters.max_time_in_seconds = 600  # 10 min cap

analyzer = Analyzer(x, intra_div, NUM_WEEKS)
start = time.time()
status = solver.solve(model, analyzer)
elapsed = time.time() - start
print(
    f"\nTotal: {analyzer.count} solutions in {elapsed:.0f}s (status: {solver.status_name(status)})"
)
print("\nClose-rematch distribution (pairs within 3-week span):")
for n_close in sorted(analyzer.buckets):
    count = analyzer.buckets[n_close]
    pct = 100 * count / analyzer.count
    print(f"  {n_close} close pairs: {count} schedules ({pct:.1f}%)")
