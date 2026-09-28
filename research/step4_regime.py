"""Step 4 — causal regime re-derivation + mechanism check + robustness.

Fixes the Step 3 lookahead (full-sample qcut) by classifying each day's regime
from PRIOR data only, then re-reports the vol-dependence and tests whether the
low-vol loss is a cost artifact.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import momentum
import sim
from config import load_rules
from common import tstat

RULES = load_rules("generic_50k")
raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
sessions = common.build_rth_sessions(diff)
mt = momentum.generate_trades(sessions)
mt = sim.enrich(mt, RULES)

# per-day RTH high-low range
day_range = {s["day"]: s["high"].max() - s["low"].min() for s in sessions}
day_idx = sorted(day_range)
rng_series = pd.Series({d: day_range[d] for d in day_idx}).sort_index()

# ---- causal RV: trailing 20-day median of RTH range, STRICTLY BEFORE D ----
rv = {}
for i, d in enumerate(day_idx):
    lo = max(0, i - 20)
    prior = [day_range[day_idx[k]] for k in range(lo, i)]  # excludes D
    rv[d] = float(np.median(prior)) if len(prior) >= 20 else np.nan

# ---- causal terciles via EXPANDING percentiles of prior RV ----
causal = {}
rv_hist = []
for d in day_idx:
    cur = rv[d]
    if np.isnan(cur) or len(rv_hist) < 40:
        causal[d] = "warmup"
    else:
        p = np.array(rv_hist)
        p67, p33 = np.percentile(p, 67), np.percentile(p, 33)
        causal[d] = "high" if cur >= p67 else ("low" if cur <= p33 else "mid")
    if not np.isnan(cur):
        rv_hist.append(cur)

# ---- full-sample (lookahead) terciles for comparison ----
rng_clean = rng_series.dropna()
lookahead_terc = pd.qcut(rng_clean, 3, labels=["low", "mid", "high"])

mt = mt.copy()
mt["causal"] = pd.to_datetime(mt["day"]).map(causal)
mt["lookahead"] = pd.to_datetime(mt["day"]).map(lookahead_terc)
mt["gross_usd"] = mt["net_usd"] + mt["cost_usd"] if "cost_usd" in mt.columns else mt["net_usd"] + 2.0

print("=" * 90)
print("CAUSAL REGIME RE-DERIVATION (vs Step 3 full-sample lookahead)")
print("=" * 90)
print("\nnet $/trade by regime — CAUSAL (expanding pct, prior data only):")
for regime in ["low", "mid", "high"]:
    g = mt[mt["causal"] == regime]
    if len(g):
        print(f"  {regime:5s}: {len(g):4d} trades, net ${g['net_usd'].mean():+7.2f}/t "
              f"(t {tstat(g['net_usd']):+5.2f})")

print("\nnet $/trade by regime — LOOKAHEAD (full-sample qcut, Step 3):")
for regime in ["low", "mid", "high"]:
    g = mt[mt["lookahead"] == regime]
    if len(g):
        print(f"  {regime:5s}: {len(g):4d} trades, net ${g['net_usd'].mean():+7.2f}/t "
              f"(t {tstat(g['net_usd']):+5.2f})")

# ---- mechanism: is low-vol loss a cost artifact? ----
print("\nMECHANISM — gross vs net by CAUSAL regime (cost ~$2/contract):")
for regime in ["low", "mid", "high"]:
    g = mt[mt["causal"] == regime]
    if len(g):
        print(f"  {regime:5s}: gross ${(g['net_usd']+2.0).mean():+7.2f}/t, "
              f"net ${g['net_usd'].mean():+7.2f}/t, cost ${2.0:5.2f}/t")

# cost as fraction of band width (stop_dist * point_value)
mt["band_usd"] = mt["stop_dist"] * RULES.point_value
print("\ncost as fraction of band width (stop_dist x $2) by regime:")
for regime in ["low", "mid", "high"]:
    g = mt[mt["causal"] == regime]
    if len(g):
        frac = 2.0 / g["band_usd"]
        print(f"  {regime:5s}: median band ${g['band_usd'].median():7.2f}, "
              f"cost/band {frac.median():.1%}")

# ---- block-bootstrap CI on high-vol t-stat ----
print("\nBLOCK BOOTSTRAP (session-block resample, 2000 reps) — high-vol net $/trade:")
high = mt[mt["causal"] == "high"]
days_high = sorted(high["day"].unique())
daily_net = high.groupby("day")["net_usd"].sum()
rng = np.random.default_rng(0)
boot = []
for _ in range(2000):
    idx = rng.integers(0, len(daily_net), len(daily_net))
    boot.append(daily_net.iloc[idx].mean())
boot = np.array(boot)
print(f"  observed ${high['net_usd'].mean():+.2f}/t, "
      f"95% CI [${np.percentile(boot,2.5):+.2f}, ${np.percentile(boot,97.5):+.2f}]")

# ---- high-vol edge with top-3 profit months removed ----
print("\nTOP-3 PROFIT MONTHS REMOVED (high-vol regime):")
high = high.copy()
high["ym"] = pd.to_datetime(high["day"]).dt.to_period("M")
month_pnl = high.groupby("ym")["net_usd"].sum().sort_values(ascending=False)
top3 = set(month_pnl.head(3).index)
kept = high[~high["ym"].isin(top3)]
print(f"  full high-vol: {len(high)} trades, net ${high['net_usd'].mean():+.2f}/t "
      f"(t {tstat(high['net_usd']):+.2f})")
print(f"  minus top-3 months ({list(top3)}): {len(kept)} trades, "
      f"net ${kept['net_usd'].mean():+.2f}/t (t {tstat(kept['net_usd']):+.2f})")

print("\ndone")
