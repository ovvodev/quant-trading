"""Cross-check my re-implementations against the reference Python backtests
(which the repo claims match Pine one-for-one), on identical difference-
adjusted data and identical parameters. Reports counts, direction/exit mixes,
and exact per-trade match rates.
"""
import importlib.util
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import scalp
import momentum as my_momentum

REPO = "/Users/kostas/Documents/quant-trading"


def load_ref(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pfs = load_ref("pfs_ref", os.path.join(REPO, "Prop Firm Scalping backtest.py"))
ref_mom = load_ref("ref_mom", os.path.join(REPO, "Prop Firm Intraday Momentum backtest.py"))

raw = common.load_raw()
diff = common.back_adjust(raw, "difference")


def compare(name, ref, mine, keys, price_cols=("entry_price", "exit_price")):
    print("=" * 80)
    print(f"CROSS-CHECK: {name}")
    print("=" * 80)
    print(f"reference trades: {len(ref)}   mine: {len(mine)}")
    if len(ref) == 0 or len(mine) == 0:
        return
    for col in ("side", "reason"):
        if col in ref.columns and col in mine.columns:
            r = ref[col].value_counts().sort_index().to_dict()
            m = mine[col].value_counts().sort_index().to_dict()
            print(f"  {col}: ref {r}  mine {m}")
    # exact per-trade match on composite key
    rk = ref.copy(); mk = mine.copy()
    for k in keys:
        rk[k] = rk[k].astype(str)
        mk[k] = mk[k].astype(str)
    mr = rk.merge(mk, on=list(keys) + list(price_cols), how="inner", indicator=False)
    print(f"  exact matches on {list(keys)+list(price_cols)}: {len(mr)} "
          f"({len(mr)/max(len(ref),1):.1%} of reference)")
    # match on keys only (ignore exit price ticks)
    mr2 = rk.merge(mk, on=list(keys), how="inner")
    print(f"  matches on {list(keys)} only: {len(mr2)} ({len(mr2)/max(len(ref),1):.1%})")


# ---------------- scalp ----------------
t0 = time.time()
ref_tr, _ref_d = pfs.signal_generation_ohlc(
    diff, tz="America/New_York", stop_mult=3.0, target_mult=1.5,
    session_start="09:30", session_end="16:00",
    target_through_ticks=1, tick_size=0.25)
print(f"[scalp reference: {len(ref_tr)} trades in {time.time()-t0:.1f}s]")

t0 = time.time()
my_tr = scalp.generate_trades(
    diff, stop_mult=3.0, target_mult=1.5, target_through_ticks=1.0)
print(f"[scalp mine: {len(my_tr)} trades in {time.time()-t0:.1f}s]")

compare("SCALP (NY 09:30-16:00, 3x/1.5x)", ref_tr, my_tr,
        ["entry_idx", "side", "entry_price"])

# ---------------- momentum ----------------
ref_days = ref_mom.build_days(diff)
my_days = common.build_rth_sessions(diff)
print(f"\n[momentum sessions: ref {len(ref_days)} vs mine {len(my_days)}]")

ref_mt = ref_mom.signal_generation(ref_days)
my_mt = my_momentum.generate_trades(my_days)
print(f"[momentum reference trades: {len(ref_mt)}  mine: {len(my_mt)}]")

compare("MOMENTUM (noise area, 14d/30m/1x)", ref_mt, my_mt,
        ["day", "side", "entry_price"])
