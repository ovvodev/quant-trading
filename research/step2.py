"""STEP 2 — prop-firm Monte Carlo.

Rolling-start evaluations (every trade day) + 5000x daily-P&L bootstrap, for
both strategies, with a zero-edge baseline under the same simulator/start
distribution. Also reproduces the review's 48% vs 23% verification under its
exact rule shape (weekly starts, EOD trailing, daily-loss-as-halt).
"""
import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import scalp
import momentum
import sim
import mc
from config import load_rules

raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
RULES = load_rules("generic_50k")


def zero_edge(tr, seed):
    rng = np.random.default_rng(seed)
    out = tr.copy()
    pnl = out["pnl_price"].to_numpy() - out["pnl_price"].mean()  # zero gross edge
    perm = rng.permutation(len(out))
    out["pnl_price"] = pnl[perm]
    out["mae_price"] = out["mae_price"].to_numpy()[perm]
    out["mfe_price"] = out["mfe_price"].to_numpy()[perm]
    return out


def rolling_starts(tr, rules, contracts=None, risk_usd=None, every_day=True):
    """Start one eval per unique trade day (or per week), follow to first
    pass/fail. Returns a DataFrame of outcomes."""
    starts = sorted(tr["day"].unique())
    if not every_day:
        starts = pd.to_datetime(starts).to_series()
        starts = starts.dt.to_period("W").dt.start_time.dt.date.unique()
        starts = sorted(pd.Timestamp(s).date() for s in starts)
    rows = []
    for s in starts:
        sub = tr[tr["day"] >= pd.Timestamp(s).date()]
        cyc = sim.simulate(sub, rules, contracts=contracts, risk_usd=risk_usd)
        if not cyc:
            continue
        c = cyc[0]
        if c["outcome"] == "in_progress":
            rows.append(dict(start=s, outcome="time", days=None))
        else:
            rows.append(dict(start=s, outcome=c["outcome"],
                             days=(pd.Timestamp(c["end_day"]) - pd.Timestamp(s)).days))
    return pd.DataFrame(rows)


def report_rolling(df, label):
    n = len(df)
    done = df[df["outcome"] != "time"]
    passed = df[df["outcome"] == "passed"]
    c = Counter(df["outcome"])
    print(f"\n--- {label} (rolling starts, n={n}) ---")
    for k in ("passed", "failed_drawdown", "failed_daily_loss",
              "failed_consistency", "time"):
        if c.get(k, 0) > 0:
            print(f"  {k:18s}: {c.get(k,0):5d} ({c.get(k,0)/n:.1%})")
    if len(passed):
        print(f"  days to pass: median {passed['days'].median():.0f}, "
              f"mean {passed['days'].mean():.0f}, max {passed['days'].max():.0f}")
    return c


# ===================== MOMENTUM =====================
print("=" * 100)
print("STEP 2 — MOMENTUM (noise area) MONTE CARLO")
print("=" * 100)
mt = momentum.generate_trades(common.build_rth_sessions(diff))
mt["entry_minute"] = mt["entry_mod"]

# --- 2 MNQ, brief rules (intraday trailing, daily-loss=fail) ---
brief = load_rules("generic_50k")          # trailing=intraday, daily_loss_is_fail=True
t0 = time.time()
roll = rolling_starts(mt, brief, contracts=2, every_day=True)
print(f"[rolling starts {time.time()-t0:.1f}s]")
report_rolling(roll, "MOMENTUM 2 MNQ, brief rules (intraday trailing $2k, $1k daily=fail, $3k target, consistency 40%)")

# zero-edge baseline (trade permutation), same rules
t0 = time.time()
zrates = []
for seed in range(10):
    z = rolling_starts(zero_edge(mt, seed), brief, contracts=2, every_day=True)
    done = z[z["outcome"] != "time"]
    if len(done):
        zrates.append((done["outcome"] == "passed").mean())
print(f"[zero-edge {time.time()-t0:.1f}s]")
print(f"  ZERO-EDGE pass rate (10 seeds): mean {np.mean(zrates):.1%}  "
      f"range {min(zrates):.1%}-{max(zrates):.1%}")

# --- reproduce the review's 48% vs 23%: weekly starts, EOD trailing, daily=halt ---
ref_rules = load_rules("generic_50k")
ref_rules.trailing = "eod"
ref_rules.daily_loss_is_fail = False   # the reference treats daily loss as a halt
t0 = time.time()
roll_ref = rolling_starts(mt, ref_rules, contracts=2, every_day=False)
report_rolling(roll_ref, "MOMENTUM 2 MNQ, reference shape (weekly starts, EOD trailing, daily=halt)")
zrates_ref = []
for seed in range(20):
    z = rolling_starts(zero_edge(mt, seed), ref_rules, contracts=2, every_day=False)
    done = z[z["outcome"] != "time"]
    if len(done):
        zrates_ref.append((done["outcome"] == "passed").mean())
print(f"[zero-edge {time.time()-t0:.1f}s]")
print(f"  ZERO-EDGE pass rate (20 seeds): mean {np.mean(zrates_ref):.1%}  "
      f"range {min(zrates_ref):.1%}-{max(zrates_ref):.1%}")

# --- bootstrap of daily P&L (brief rules, 2 MNQ) ---
daily_2 = mt.groupby("day")["pnl_price"].sum() * brief.point_value \
    - mt.groupby("day").size() * 2 * (2 * brief.commission_per_side + 2 * brief.slippage_ticks * brief.tick_size * brief.point_value)
daily_2 = daily_2 * 2  # 2 contracts
t0 = time.time()
outcomes, days, surv = mc.bootstrap(daily_2.values, brief, n=5000, horizon=250, seed=42)
print(f"[bootstrap {time.time()-t0:.1f}s]")
mc.summarize_bootstrap(outcomes, days, surv, "MOMENTUM 2 MNQ")

# ===================== SCALP =====================
print("\n" + "=" * 100)
print("STEP 2 — SCALP (Bollinger pullback) MONTE CARLO")
print("=" * 100)
st = scalp.generate_trades(diff, stop_mult=3.0, target_mult=1.5, target_through_ticks=1.0)
st["entry_minute"] = (pd.to_datetime(st["entry_date"]).dt.hour * 60
                      + pd.to_datetime(st["entry_date"]).dt.minute)

t0 = time.time()
roll_s = rolling_starts(st, brief, risk_usd=500.0, every_day=True)
print(f"[rolling starts {time.time()-t0:.1f}s]")
report_rolling(roll_s, "SCALP risk $500/trade, brief rules")

t0 = time.time()
zrates_s = []
for seed in range(5):
    z = rolling_starts(zero_edge(st, seed), brief, risk_usd=500.0, every_day=True)
    done = z[z["outcome"] != "time"]
    if len(done):
        zrates_s.append((done["outcome"] == "passed").mean())
print(f"[zero-edge {time.time()-t0:.1f}s]")
print(f"  ZERO-EDGE pass rate (5 seeds): mean {np.mean(zrates_s):.1%}")

daily_s = sim.enrich(st, brief).groupby("day")["net_usd"].sum()
t0 = time.time()
outcomes_s, days_s, surv_s = mc.bootstrap(daily_s.values, brief, n=5000, horizon=250, seed=42)
print(f"[bootstrap {time.time()-t0:.1f}s]")
mc.summarize_bootstrap(outcomes_s, days_s, surv_s, "SCALP (per-contract daily P&L)")
