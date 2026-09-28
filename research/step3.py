"""STEP 3 — robustness: walk-forward/IS-OOS, regime decay, parameter
sensitivity, cost stress, news-blackout sensitivity, deflated significance.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import scalp
import momentum
import sim
from config import load_rules
from common import tstat, newey_west_tstat, max_t_prob

raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
RULES = load_rules("generic_50k")
SPLIT = pd.Timestamp("2024-04-01")


def net(tr, commission_per_side=0.50, slippage_ticks=1.0):
    return sim.enrich(tr, RULES)["net_usd"]


print("=" * 100)
print("STEP 3 — ROBUSTNESS")
print("=" * 100)

# ===================== MOMENTUM =====================
print("\n" + "#" * 90)
print("MOMENTUM")
print("#" * 90)
days = common.build_rth_sessions(diff)
mt = momentum.generate_trades(days)
mtn = net(mt)

# 1. IS / OOS
ins = pd.to_datetime(mt["day"]) < SPLIT
print("\n[1] IS/OOS split at 2024-04-01 (single chronological split, as prior study)")
print(f"  full sample: net ${mtn.mean():+.2f}/trade, t {tstat(mtn):+.2f}")
print(f"  in-sample  (< {SPLIT}): net ${mtn[ins].mean():+.2f}/trade, t {tstat(mtn[ins]):+.2f} "
      f"({ins.sum()} trades)")
print(f"  out-of-sample        : net ${mtn[~ins].mean():+.2f}/trade, t {tstat(mtn[~ins]):+.2f} "
      f"({(~ins).sum()} trades)")

# 2. purged walk-forward: train 2yr / test 6mo, stitched OOS
print("\n[2] Purged walk-forward (train 24mo -> test 6mo, stride 6mo, no overlap)")
train_len = pd.DateOffset(months=24)
test_len = pd.DateOffset(months=6)
start = pd.Timestamp(mt["day"].min())
end = pd.Timestamp(mt["day"].max())
stitched = []
w = start
while w + train_len + test_len <= end:
    tr_lo, tr_hi = w, w + train_len
    te_lo, te_hi = w + train_len, w + train_len + test_len
    seg = mt[(pd.to_datetime(mt["day"]) >= te_lo) & (pd.to_datetime(mt["day"]) < te_hi)]
    if len(seg):
        s = net(seg)
        stitched.append((te_lo.date(), len(seg), s.mean(), tstat(s)))
    w += test_len
if stitched:
    st = pd.DataFrame(stitched, columns=["test_start", "n", "net", "t"])
    print("  stitched OOS segments:")
    for _, r in st.iterrows():
        print(f"    {r['test_start']}  n={r['n']:4d}  net ${r['net']:+.2f}  t {r['t']:+.2f}")
    all_net = mt[mt["day"].isin(st["test_start"].map(lambda d: None))]  # placeholder
    print(f"  stitched OOS total: {st['n'].sum()} trades, "
          f"weighted net ${(st['net']*st['n']).sum()/st['n'].sum():+.2f}")

# 3. regime decay: rolling 6-month expectancy + realized-vol terciles
print("\n[3] Regime decay")
mt_d = mt.copy()
mt_d["net"] = mtn
mt_d["ts"] = pd.to_datetime(mt_d["day"])
mt_d = mt_d.set_index("ts").sort_index()
roll6 = mt_d["net"].rolling("180D").mean()
print("  rolling 6-month net $/trade (first/last values + min):")
print(f"    {roll6.iloc[0]:+.2f} ... {roll6.iloc[-1]:+.2f}  (min over sample {roll6.min():+.2f})")

# realized-vol regime: RTH session high-low range, terciles
day_range = {}
for s in days:
    day_range[s["day"]] = s["high"].max() - s["low"].min()
rng = pd.Series(day_range).sort_index()
terc = pd.qcut(rng, 3, labels=["low-vol", "mid-vol", "high-vol"])
mt_d["vol_regime"] = mt_d["day"].map(terc)
print("  net $/trade by realized-vol tercile (RTH high-low range):")
for regime, grp in mt_d.groupby("vol_regime", observed=True):
    print(f"    {regime}: {len(grp):4d} trades, net ${grp['net'].mean():+.2f}/trade, "
          f"t {tstat(grp['net']):+.2f}")

# 4. parameter sensitivity +/-20%
print("\n[4] Parameter sensitivity (+/-20%)")
print("  momentum grid (lookback, check_every, stop_band):")
count = 0
for lb in (11, 14, 17):
    for ce in (24, 30, 36):
        for sb in (0.8, 1.0, 1.2):
            t = momentum.generate_trades(days, lookback=lb, check_every=ce, stop_band_mult=sb)
            n = net(t)
            count += 1
            if (lb, ce, sb) == (14, 30, 1.0):
                mark = "  <- base"
            else:
                mark = ""
            print(f"    lb={lb:2d} ce={ce:2d} sb={sb:.1f}: n={len(t):4d} "
                  f"net ${n.mean():+.2f} t {tstat(n):+.2f}{mark}")

# 5. cost stress
print("\n[5] Cost stress (double commission + double slippage)")
n2 = sim.enrich(mt, load_rules("generic_50k"))["net_usd"]
stress = mt.copy()
stress_rules = load_rules("generic_50k")
stress_rules.commission_per_side = 1.00
stress_rules.slippage_ticks = 2.0
n_stress = sim.enrich(mt, stress_rules)["net_usd"]
print(f"  base (${0.50:.2f}/side, 1 tick): net ${n2.mean():+.2f}/trade")
print(f"  2x   (${1.00:.2f}/side, 2 ticks): net ${n_stress.mean():+.2f}/trade")

# 6. news blackout sensitivity
print("\n[6] News blackout (2min before -> 5min after 10:00 & 14:00 ET)")
nb = load_rules("generic_50k")
nb.news_blackout = [("09:58", "10:05"), ("13:58", "14:05")]
mt["entry_minute"] = mt["entry_mod"]
nb_tr = sim.apply_blackout(mt, nb)
print(f"  trades removed: {len(mt) - len(nb_tr)} of {len(mt)} "
      f"({(len(mt)-len(nb_tr))/len(mt):.1%})")
n_nb = net(nb_tr)
print(f"  remaining net ${n_nb.mean():+.2f}/trade, t {tstat(n_nb):+.2f} "
      f"(vs ${n2.mean():+.2f}, t {tstat(n2):+.2f} without)")

# 7. deflated significance
print("\n[7] Deflated significance (multiple-testing)")
N_TRIALS = 62 + count  # prior search configs + this parameter grid
t_full = tstat(mtn)
print(f"  momentum full-sample t = {t_full:+.2f}")
print(f"  variants tried (prior 62 + this grid {count}) = {N_TRIALS}")
print(f"  P(best of {N_TRIALS} null |t| >= {abs(t_full):.2f}) ~= {max_t_prob(t_full, N_TRIALS):.1%}")
print("  note: momentum parameters are PUBLISHED (Zarattini 2024), so no parameter")
print("  tuning penalty applies to its t-stat; the selection penalty above is the")
print("  'best idea among the prior 7' penalty.")

# ===================== SCALP =====================
print("\n" + "#" * 90)
print("SCALP (brief sensitivity only — already shown to have no edge)")
print("#" * 90)
st = scalp.generate_trades(diff, stop_mult=3.0, target_mult=1.5, target_through_ticks=1.0)
stn = net(st)
print(f"  base net ${stn.mean():+.3f}/trade, t {tstat(stn):+.2f}")
print("  stop/target grid (net $/trade):")
for sm in (2.4, 3.0, 3.6):
    for tm in (1.2, 1.5, 1.8):
        t = scalp.generate_trades(diff, stop_mult=sm, target_mult=tm, target_through_ticks=1.0)
        n = net(t)
        print(f"    stop {sm:.1f}x target {tm:.1f}x: n={len(t):4d} net ${n.mean():+.3f} t {tstat(n):+.2f}")
