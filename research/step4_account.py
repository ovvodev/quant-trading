"""Step 4 — winner verification (V7 dd-aware sizing): OOS-only MC, account tiers,
EV per attempt, and dd-sizing threshold sensitivity.
"""
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import momentum
import sim
from config import load_rules

raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
sessions = common.build_rth_sessions(diff)
mt = momentum.generate_trades(sessions)
mt["entry_minute"] = mt["entry_mod"]
SPLIT = pd.Timestamp("2024-04-01")
BASE = load_rules("generic_50k")


def mc(tr, rules, contracts=2):
    starts = sorted(tr["day"].unique())
    out, days = [], []
    for s in starts:
        cyc = sim.simulate(tr[tr["day"] >= s], rules, contracts=contracts)
        c = cyc[0] if cyc else None
        if c is None:
            continue
        out.append("time" if c["outcome"] == "in_progress" else c["outcome"])
        if c["outcome"] == "passed":
            days.append((c["end_day"] - s).days)
    c = Counter(out)
    return c, days


def pr(c):
    return c["passed"] / (sum(c.values()) or 1)


def v7_rules():
    r = load_rules("generic_50k")
    r.dd_sizing = [(1500.0, 1.0)]
    return r


def v0_rules():
    return load_rules("generic_50k")


print("=" * 90)
print("V7 OOS-ONLY (trades >= 2024-04-01)")
print("=" * 90)
oos_tr = mt[pd.to_datetime(mt["day"]) >= SPLIT]
for name, rules in (("V0 baseline", v0_rules()), ("V7 dd-sizing", v7_rules())):
    c, days = mc(oos_tr, rules)
    print(f"  {name}: pass {pr(c):.1%} ({c['passed']}/{sum(c.values())}), "
          f"drawdown {c['failed_drawdown']}, daily {c['failed_daily_loss']}, "
          f"consist {c['failed_consistency']}, median days {int(np.median(days)) if days else 'n/a'}")

print("\n" + "=" * 90)
print("ACCOUNT FIT + EV  (winner = V7)")
print("=" * 90)
payout_share, fee = 0.8, 150.0
tiers = [
    ("$50k", dict(account=50_000, target=3_000, max_loss=2_000, daily_loss=1_000,
                  max_contracts=5, contracts=2, dd_sizing=[(1500.0, 1.0)])),
    ("$100k", dict(account=100_000, target=6_000, max_loss=4_000, daily_loss=2_000,
                   max_contracts=10, contracts=4, dd_sizing=[(3000.0, 2.0)])),
    ("$150k", dict(account=150_000, target=9_000, max_loss=6_000, daily_loss=3_000,
                   max_contracts=15, contracts=6, dd_sizing=[(4500.0, 3.0)])),
]
print(f"\n  payout_share={payout_share}, fee=${fee}/attempt. EV = pass_rate x payout_share x target - fee")
for tier, p in tiers:
    r = load_rules("generic_50k")
    r.account, r.target, r.max_loss = p["account"], p["target"], p["max_loss"]
    r.daily_loss, r.max_contracts = p["daily_loss"], p["max_contracts"]
    r.dd_sizing = p["dd_sizing"]
    c, days = mc(mt, r, contracts=p["contracts"])
    payout = payout_share * p["target"]
    ev = pr(c) * payout - fee
    print(f"  {tier}: pass {pr(c):.1%} ({c['passed']}/{sum(c.values())}), "
          f"median days {int(np.median(days)) if days else 'n/a'}, "
          f"payout ${payout:.0f}, EV ${ev:+.0f}")

print("\nEOD-trailing rule set (V7 sizing, $50k):")
r = v7_rules()
r.trailing = "eod"
c, days = mc(mt, r, contracts=2)
print(f"  pass {pr(c):.1%}, median days {int(np.median(days)) if days else 'n/a'}")

print("\n" + "=" * 90)
print("DD-SIZING THRESHOLD SENSITIVITY (V7 family, $50k, full sample)")
print("=" * 90)
for thresh in (1000.0, 1500.0, 1800.0, 2000.0):
    r = load_rules("generic_50k")
    r.dd_sizing = [(thresh, 1.0)]
    c, days = mc(mt, r, contracts=2)
    print(f"  threshold ${thresh:.0f}: pass {pr(c):.1%} ({c['passed']}/{sum(c.values())}), "
          f"drawdown {c['failed_drawdown']}, consist {c['failed_consistency']}, "
          f"median days {int(np.median(days)) if days else 'n/a'}")

print("\ndone")
