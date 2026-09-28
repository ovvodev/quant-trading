"""Reproduce the review's 48% vs 23% exactly, and diff my simulator against the
reference's backtesting_futures_prop (continuous cycles, not rolling starts).
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import momentum
import sim
from config import load_rules

REPO = "/Users/kostas/Documents/quant-trading"


def load_ref(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def zero_edge_mine(tr, seed):
    rng = np.random.default_rng(seed)
    out = tr.copy()
    pnl = out["pnl_price"].to_numpy() - out["pnl_price"].mean()
    perm = rng.permutation(len(out))
    out["pnl_price"] = pnl[perm]
    out["mae_price"] = out["mae_price"].to_numpy()[perm]
    out["mfe_price"] = out["mfe_price"].to_numpy()[perm]
    return out


pfs = load_ref("pfs_v", os.path.join(REPO, "Prop Firm Scalping backtest.py"))

raw = common.load_raw()
diff = common.back_adjust(raw, "difference")
mt = momentum.generate_trades(common.build_rth_sessions(diff))

fixed = mt.copy()
fixed["stop_dist"] = 1.0
fixed["r_multiple"] = fixed["pnl_price"]

rule = dict(account=50000, target=3000, max_loss=2000, trailing="eod", daily_loss=1000)
kw = dict(rule, risk_usd=2 * 2.0, point_value=2.0, tick_size=0.25)

print("=== REFERENCE backtesting_futures_prop (continuous cycles, EOD, daily=halt, 2 MNQ) ===")
cyc = pfs.backtesting_futures_prop(fixed, commission_round_trip=0.70, slippage_ticks=1.0, **kw)
done = cyc[cyc["outcome"] != "in_progress"]
print(f"  reference: {len(done)} cycles, pass rate {(done['outcome']=='passed').mean():.1%}")
zero = []
for s in range(20):
    z = pfs.backtesting_futures_prop(pfs.zero_edge_trades(fixed, s),
                                     commission_round_trip=0.70, slippage_ticks=1.0, **kw)
    zd = z[z["outcome"] != "in_progress"]
    if len(zd):
        zero.append((zd["outcome"] == "passed").mean())
print(f"  reference zero-edge (20 seeds): {np.mean(zero):.1%}")

print("\n=== MY sim.simulate (continuous cycles, EOD, daily=halt, 2 MNQ) ===")
r = load_rules("generic_50k")
r.trailing = "eod"
r.daily_loss_is_fail = False
r.consistency = None
r.commission_per_side = 0.35
my = sim.simulate(fixed, r, contracts=2)
my_done = [c for c in my if c["outcome"] != "in_progress"]
print(f"  mine: {len(my_done)} cycles, pass rate {sum(c['outcome']=='passed' for c in my_done)/len(my_done):.1%}")

myz = []
for s in range(20):
    zc = sim.simulate(zero_edge_mine(fixed, s), r, contracts=2)
    zd = [c for c in zc if c["outcome"] != "in_progress"]
    if zd:
        myz.append(sum(c["outcome"] == "passed" for c in zd) / len(zd))
print(f"  mine zero-edge (20 seeds): {np.mean(myz):.1%}")
