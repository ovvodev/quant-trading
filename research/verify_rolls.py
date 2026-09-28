"""Verify roll back-adjustment: difference vs ratio, price sanity, distortion.

Answers the brief's step-0 requirement to confirm the method and check for
negative/implausible prices, and quantifies how much each method distorts the
percentage moves that the noise-area momentum strategy reads.
"""
import numpy as np
import pandas as pd

from common import load_raw, back_adjust, build_rth_sessions, RTH_OPEN, RTH_CLOSE

RAW = load_raw()
DIFF = back_adjust(RAW, "difference")
RATIO = back_adjust(RAW, "ratio")

print("=" * 90)
print("ROLL BACK-ADJUSTMENT VERIFICATION")
print("=" * 90)

# 1. price sanity
for name, d in (("raw", RAW), ("difference", DIFF), ("ratio", RATIO)):
    for c in ("open", "high", "low", "close"):
        col = d[c]
        neg = int((col <= 0).sum())
        oob = int((col > 1e6).sum())
        print(f"{name:10s} {c:5s}: min {col.min():,.2f}  max {col.max():,.2f}  "
              f"nonpositive {neg}  >1e6 {oob}")
    # OHLC internal consistency
    bad = int((d["high"] < d["low"]).sum())
    print(f"{name:10s} {'':5s}  high<low violations: {bad}")

# 2. roll gap magnitude
roll = RAW["symbol"] != RAW["symbol"].shift()
roll.iloc[0] = False
gap = (RAW["open"] - RAW["close"].shift())[roll]
print(f"\nroll count: {int(roll.sum())}")
print(f"raw roll gaps (open - prev close): median {gap.median():,.1f}, "
      f"min {gap.min():,.1f}, max {gap.max():,.1f} pts")

# 3. how much each method shifts the oldest bar
for name, d in (("difference", DIFF), ("ratio", RATIO)):
    shift = d["close"].iloc[0] - RAW["close"].iloc[0]
    mult = d["close"].iloc[0] / RAW["close"].iloc[0]
    print(f"{name}: first-bar close {RAW['close'].iloc[0]:,.2f} -> "
          f"{d['close'].iloc[0]:,.2f}  (shift {shift:+,.1f} pts, x{mult:.3f})")

# 4. effect on intraday percentage moves (what the momentum strategy reads)
def intraday_pct_moves(d):
    s = build_rth_sessions(d)
    moves = []
    for x in s:
        m = np.abs(x["close"] / x["open"][0] - 1.0)
        moves.append(m)
    return np.concatenate(moves)

m_raw = intraday_pct_moves(RAW)
m_diff = intraday_pct_moves(DIFF)
m_ratio = intraday_pct_moves(RATIO)
print("\nintraday |close/open - 1| distribution (the momentum signal's input):")
for name, m in (("raw", m_raw), ("difference", m_diff), ("ratio", m_ratio)):
    print(f"  {name:10s}: median {np.nanmedian(m):.5f}  mean {np.nanmean(m):.5f}  "
          f"p99 {np.nanpercentile(m, 99):.5f}")

# raw vs difference should differ (difference adds a constant -> changes ratios)
# raw vs ratio should be near-identical (ratio preserves intraday % moves)
print("\nmax |difference - raw| in intraday % moves:", np.nanmax(np.abs(m_diff - m_raw)))
print("max |ratio - raw| in intraday % moves:   ", np.nanmax(np.abs(m_ratio - m_raw)))

# 5. effect on prev_close vs open (band anchors) on roll days
print("\nprev_close vs session open, difference-adjusted vs ratio-adjusted, roll days only:")
s_diff = build_rth_sessions(DIFF)
s_ratio = build_rth_sessions(RATIO)
roll_days = set(RAW.loc[roll, "timestamp"].dt.tz_localize("UTC").dt.tz_convert(
    "America/New_York").dt.date)
cnt = 0
for xd, xr in zip(s_diff, s_ratio):
    if xd["day"] not in roll_days:
        continue
    cnt += 1
print(f"  roll-day sessions in sample: {cnt}")
