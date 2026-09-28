"""Generate the deliverable charts into results/."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import scalp
import momentum
import sim
from config import load_rules

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
RULES = load_rules("generic_50k")
raw = common.load_raw()
diff = common.back_adjust(raw, "difference")


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


# ---- momentum equity + drawdown (2 MNQ) ----
mt = momentum.generate_trades(common.build_rth_sessions(diff))
mt = sim.enrich(mt, RULES)
mt_scaled = mt.copy()
mt_scaled["net_usd"] = mt_scaled["net_usd"] * 2.0  # 2 MNQ
daily = mt_scaled.groupby("day")["net_usd"].sum()
curve = daily.cumsum()
dd = curve - curve.cummax()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(curve.index, curve.values, lw=1.2, color="#1f77b4")
ax1.set_ylabel("cumulative net $ (2 MNQ)")
ax1.set_title("Intraday Momentum (noise area) — cumulative net $, 2 MNQ, net of cost")
ax1.grid(alpha=0.3)
ax2.fill_between(dd.index, dd.values, 0, color="#d62728", alpha=0.6)
ax2.set_ylabel("drawdown $")
ax2.grid(alpha=0.3)
save(fig, "momentum_equity_dd.png")

# ---- rolling 6-month net $/trade ----
mt_d = mt.copy()
mt_d["ts"] = pd.to_datetime(mt_d["day"])
mt_d = mt_d.set_index("ts").sort_index()
roll = mt_d["net_usd"].rolling("180D").mean()
fig, ax = plt.subplots(figsize=(11, 3.4))
ax.plot(roll.index, roll.values, lw=1.4, color="#2ca02c")
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("net $/trade (6mo rolling)")
ax.set_title("Momentum — rolling 6-month net $/trade (regime decay)")
ax.grid(alpha=0.3)
save(fig, "momentum_rolling_6m.png")

# ---- vol-regime bar ----
day_range = {}
for s in common.build_rth_sessions(diff):
    day_range[s["day"]] = s["high"].max() - s["low"].min()
rng = pd.Series(day_range).sort_index()
terc = pd.qcut(rng, 3, labels=["low-vol", "mid-vol", "high-vol"])
mt_d["regime"] = mt_d["day"].map(terc)
means = mt_d.groupby("regime", observed=True)["net_usd"].mean()
fig, ax = plt.subplots(figsize=(7, 3.6))
colors = ["#d62728", "#7f7f7f", "#2ca02c"]
ax.bar(means.index.astype(str), means.values, color=colors)
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("net $/trade")
ax.set_title("Momentum net $/trade by realized-volatility tercile")
ax.grid(alpha=0.3, axis="y")
save(fig, "momentum_vol_regime.png")

# ---- pass/fail distribution (rolling starts) ----
import mc  # noqa
from sim import simulate

def rolling_outcomes(tr, rules, contracts=None, risk_usd=None):
    starts = sorted(tr["day"].unique())
    out = []
    for s in starts:
        sub = tr[tr["day"] >= pd.Timestamp(s).date()]
        cyc = simulate(sub, rules, contracts=contracts, risk_usd=risk_usd)
        c = cyc[0] if cyc else None
        if c is None:
            continue
        out.append("time" if c["outcome"] == "in_progress" else c["outcome"])
    return out

brief = load_rules("generic_50k")
mt2 = mt.copy()
mt2["entry_minute"] = mt2["entry_mod"]
mom_out = rolling_outcomes(mt2, brief, contracts=2)

st = scalp.generate_trades(diff, stop_mult=3.0, target_mult=1.5, target_through_ticks=1.0)
st["entry_minute"] = (pd.to_datetime(st["entry_date"]).dt.hour * 60
                      + pd.to_datetime(st["entry_date"]).dt.minute)
scalp_out = rolling_outcomes(st, brief, risk_usd=500.0)

labels = ["passed", "failed_drawdown", "failed_daily_loss", "failed_consistency", "time"]
order = {"passed": 0, "failed_drawdown": 1, "failed_daily_loss": 2,
         "failed_consistency": 3, "time": 4}

fig, ax = plt.subplots(figsize=(8, 4.2))
width = 0.38
xs = np.arange(len(labels))
for i, (name, outs) in enumerate((("Momentum 2 MNQ", mom_out), ("Scalp $500", scalp_out))):
    from collections import Counter
    c = Counter(outs)
    vals = [c.get(l, 0) / len(outs) for l in labels]
    ax.bar(xs + (i - 0.5) * width, vals, width, label=name)
ax.set_xticks(xs)
ax.set_xticklabels([l.replace("failed_", "") for l in labels], rotation=15)
ax.set_ylabel("fraction of rolling-start evaluations")
ax.set_title("Prop-firm outcome distribution (rolling starts, brief rules)")
ax.legend()
ax.grid(alpha=0.3, axis="y")
save(fig, "passfail_distribution.png")

print("done")
