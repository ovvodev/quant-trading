"""Step 4 — run the 10 pre-registered variants.

Per variant: IS/OOS net $/trade + t, purged walk-forward stitched OOS, and the
prop-firm Monte Carlo (rolling starts) with fail breakdown + median days-to-pass.
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
from common import tstat

RULES = load_rules("generic_50k")
raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
sessions = common.build_rth_sessions(diff)
mt = momentum.generate_trades(sessions)
mt["entry_minute"] = mt["entry_mod"]
SPLIT = pd.Timestamp("2024-04-01")

day_range = {s["day"]: s["high"].max() - s["low"].min() for s in sessions}
day_idx = sorted(day_range)


def causal_keep_days(pct=67, window=None):
    """Days to KEEP: warmup (kept) + days whose causal RV >= expanding/trailing pct."""
    rv = {}
    for i, d in enumerate(day_idx):
        lo = max(0, i - 20)
        prior = [day_range[day_idx[k]] for k in range(lo, i)]
        rv[d] = float(np.median(prior)) if len(prior) >= 20 else np.nan
    keep = set()
    rv_hist = []
    for d in day_idx:
        cur = rv[d]
        if np.isnan(cur) or len(rv_hist) < 40:
            keep.add(d)                      # warmup: unfiltered
        else:
            p = np.array(rv_hist[-window:] if window else rv_hist)
            if cur >= np.percentile(p, pct):
                keep.add(d)
        if not np.isnan(cur):
            rv_hist.append(cur)
    return keep


def split_isoos(tr):
    ts = pd.to_datetime(tr["day"])
    return tr[ts < SPLIT], tr[ts >= SPLIT]


def walk_forward(tr):
    """Purged 24mo-train / 6mo-test, stride 6mo. Returns list of (test_start, n, net, t)."""
    lo0, hi0 = pd.to_datetime(tr["day"].min()), pd.to_datetime(tr["day"].max())
    train, test = pd.DateOffset(months=24), pd.DateOffset(months=6)
    out = []
    w = lo0
    while w + train + test <= hi0:
        te_lo, te_hi = w + train, w + train + test
        seg = tr[(pd.to_datetime(tr["day"]) >= te_lo) & (pd.to_datetime(tr["day"]) < te_hi)]
        if len(seg):
            s = sim.enrich(seg, RULES)["net_usd"]
            out.append((te_lo.date(), len(seg), s.mean(), tstat(s)))
        w += test
    return out


def rolling_mc(tr, rules, contracts=2, risk_usd=None):
    starts = sorted(tr["day"].unique())
    out = []
    days = []
    for s in starts:
        sub = tr[tr["day"] >= s]
        cyc = sim.simulate(sub, rules, contracts=contracts, risk_usd=risk_usd)
        c = cyc[0] if cyc else None
        if c is None:
            continue
        out.append("time" if c["outcome"] == "in_progress" else c["outcome"])
        if c["outcome"] == "passed":
            days.append((c["end_day"] - s).days)
    return out, days


def report_mc(out, days):
    n = len(out)
    c = Counter(out)
    print(f"    passes {c['passed']}/{n} = {c['passed']/n:.1%}")
    for k in ("failed_drawdown", "failed_daily_loss", "failed_consistency", "time"):
        if c[k]:
            print(f"      {k}: {c[k]} ({c[k]/n:.1%})")
    if days:
        print(f"      days-to-pass median {int(np.median(days))}, mean {np.mean(days):.0f}")


# pre-registered variants
variants = [
    ("V0", "baseline", None, {}),
    ("V1", "regime exp-67pct", ("exp", 67, None), {}),
    ("V2", "regime trail250-67pct", ("exp", 67, 250), {}),
    ("V3", "regime exp-50pct", ("exp", 50, None), {}),
    ("V4", "regime exp-80pct", ("exp", 80, None), {}),
    ("V5", "profit-lock +$1000", None, {"daily_profit_lock": 1000.0}),
    ("V6", "soft-stop -$500", None, {"daily_soft_stop": 500.0}),
    ("V7", "dd-aware sizing", None, {"dd_sizing": [(1500.0, 1.0)]}),
    ("V8", "stand-down 3", None, {"stand_down_days": 3}),
    ("V9", "combined (V1+V5+V7)", ("exp", 67, None), {"daily_profit_lock": 1000.0, "dd_sizing": [(1500.0, 1.0)]}),
]

print("=" * 100)
print("STEP 4 — VARIANT RESULTS (pre-registered, causal filters)")
print("=" * 100)

for vid, name, filt, overrides in variants:
    tr = mt.copy()
    if filt:
        keep = causal_keep_days(pct=filt[1], window=filt[2])
        tr = tr[tr["day"].map(lambda d: d in keep)].reset_index(drop=True)
    ins, oos = split_isoos(tr)
    n_in, n_oos = len(ins), len(oos)
    net_in = sim.enrich(ins, RULES)["net_usd"] if n_in else pd.Series()
    net_oos = sim.enrich(oos, RULES)["net_usd"] if n_oos else pd.Series()

    print(f"\n{vid} — {name}  [{len(tr)} trades]"
          + ("" if len(tr) >= 200 else "  <-- BELOW 200-TRADE MIN"))
    print(f"  IS  (< {SPLIT.date()}): net ${net_in.mean():+.2f}/t (t {tstat(net_in):+.2f}, n={n_in})")
    print(f"  OOS (>= {SPLIT.date()}): net ${net_oos.mean():+.2f}/t (t {tstat(net_oos):+.2f}, n={n_oos})")
    wf = walk_forward(tr)
    wf_nets = [w[2] for w in wf]
    wf_n = [w[1] for w in wf]
    wf_stitched = sum(a * b for a, b in zip(wf_nets, wf_n)) / sum(wf_n) if sum(wf_n) else float("nan")
    print(f"  walk-forward stitched OOS: net ${wf_stitched:+.2f}/t ({sum(wf_n)} trades), "
          f"segments: {['%+.0f' % w[2] for w in wf]}")

    rules = load_rules("generic_50k")
    for k, v in overrides.items():
        setattr(rules, k, v)
    out, days = rolling_mc(tr, rules, contracts=2)
    report_mc(out, days)

print("\ndone")
