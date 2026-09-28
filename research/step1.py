"""STEP 1 — re-implement both prop strategies, headline stats, and the
roll-adjustment-method comparison for the (percentage-based) momentum signal.
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
import stats
from config import load_rules

RULES = load_rules("generic_50k")
raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
ratio = common.back_adjust(raw, "ratio")

print("=" * 100)
print("STEP 1 — STRATEGY RE-IMPLEMENTATION AND HEADLINE STATS")
print(f"costs: ${RULES.commission_per_side:.2f}/side + {RULES.slippage_ticks:.0f} tick/market-fill; "
      f"MNQ ${RULES.point_value:.0f}/pt, tick {RULES.tick_size}")
print("=" * 100)

# ===================== SCALP =====================
print("\n" + "#" * 100)
print("PROP FIRM SCALPING  (NY 09:30-16:00, stop 3x / target 1.5x vol)")
print("#" * 100)
scalp_tr = scalp.generate_trades(diff, stop_mult=3.0, target_mult=1.5, target_through_ticks=1.0)
scalp_tr["entry_minute"] = pd.to_datetime(scalp_tr["entry_date"]).dt.hour * 60 \
    + pd.to_datetime(scalp_tr["entry_date"]).dt.minute
scalp_net = sim.enrich(scalp_tr, RULES)

print(f"\ngross avg R/trade = {scalp_tr['r_multiple'].mean():+.4f}  "
      f"(t-stat {common.tstat(scalp_tr['r_multiple']):+.2f})")
stats.print_trade_stats("SCALP, net per contract ($0.50/side + 1 tick)",
                        stats.trade_stats(scalp_net))
# reference cost model ($0.70 RT + 1 tick) for comparison
ref_rules = load_rules("generic_50k")
ref_rules.commission_per_side = 0.35  # $0.70 round trip
scalp_net_ref = sim.enrich(scalp_tr, ref_rules)
print(f"  (reference cost $0.70 RT: net $/trade = {scalp_net_ref['net_usd'].mean():+.3f})")

# ===================== MOMENTUM =====================
print("\n" + "#" * 100)
print("INTRADAY MOMENTUM  (noise area, 14d / 30m / stop 1x)")
print("#" * 100)

def momentum_net(mt):
    mt = mt.copy()
    mt = sim.enrich(mt, RULES)   # net_usd per contract with $0.50/side + 1 tick
    return mt

days_diff = common.build_rth_sessions(diff)
days_raw = common.build_rth_sessions(raw)
days_ratio = common.build_rth_sessions(ratio)

mt_diff = momentum.generate_trades(days_diff)
mt_raw = momentum.generate_trades(days_raw)
mt_ratio = momentum.generate_trades(days_ratio)
ctrl = momentum.generate_trades(days_diff, flip=True)

for name, mt in (("difference (reference method)", mt_diff),
                 ("raw", mt_raw),
                 ("ratio", mt_ratio)):
    net = momentum_net(mt)
    print(f"\n  MOMENTUM [{name}]: {len(mt)} trades, win { (net['net_usd']>0).mean():.1%}, "
          f"net ${net['net_usd'].mean():+,.2f}/trade (t {common.tstat(net['net_usd']):+.2f})")

print("\n  momentum difference-vs-raw trade count delta:",
      len(mt_diff) - len(mt_raw), "trades")
print("  momentum ratio-vs-raw trade count delta:    ",
      len(mt_ratio) - len(mt_raw), "trades")

# headline stats on the difference-adjusted (reference) momentum
net_diff = momentum_net(mt_diff)
print("\n  MOMENTUM net per contract, difference-adjusted:")
s = stats.trade_stats(net_diff)
stats.print_trade_stats("  MOMENTUM", s)
print(f"  longs/shorts net $/trade: "
      f"{net_diff[net_diff['side']==1]['net_usd'].mean():+.2f} / "
      f"{net_diff[net_diff['side']==-1]['net_usd'].mean():+.2f}")
net_ctrl = momentum_net(ctrl)
print(f"  CONTROL (opposite side): net ${net_ctrl['net_usd'].mean():+.2f}/trade "
      f"(t {common.tstat(net_ctrl['net_usd']):+.2f})")
yr = net_diff.groupby(pd.to_datetime(net_diff['day']).dt.year)['net_usd'].sum()
print("  net $ per contract by year: " + ", ".join(f"{y}: {v:+,.0f}" for y, v in yr.items()))
