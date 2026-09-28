"""Intraday momentum (noise area) — independent re-implementation.

Rules: Zarattini, Aziz & Barbon (2024) "Beat the Market", published parameters.
Takes a list of pre-built RTH sessions (see common.build_rth_sessions) and
returns one row per completed trade. The caller decides the price adjustment
by choosing which series it builds sessions from; pnl_price is measured in the
same units as the input series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import RTH_OPEN, RTH_CLOSE

LOOKBACK_DAYS = 14
CHECK_EVERY = 30
FIRST_CHECK = "10:00"
STOP_BAND_MULT = 1.0


def generate_trades(days, lookback=LOOKBACK_DAYS, check_every=CHECK_EVERY,
                    first_check=FIRST_CHECK, stop_band_mult=STOP_BAND_MULT,
                    flip=False) -> pd.DataFrame:
    h0, m0 = (int(v) for v in first_check.split(":"))
    # a check "at 10:00" acts on the bar that CLOSES at 10:00 (minute index 599)
    marks = set(range(h0 * 60 + m0 - 1, RTH_CLOSE - 1, check_every))

    nmin = RTH_CLOSE - RTH_OPEN
    move = np.full((len(days), nmin), np.nan)
    for i, s in enumerate(days):
        move[i, s["mod"] - RTH_OPEN] = np.abs(s["close"] / s["open"][0] - 1.0)

    trades = []
    for i, s in enumerate(days):
        if i < lookback or np.isnan(s["prev_close"]):
            continue
        sigma = np.nanmean(move[i - lookback:i], axis=0)
        mod, o, h, l, c, vwap = s["mod"], s["open"], s["high"], s["low"], s["close"], s["vwap"]
        top, bot = max(o[0], s["prev_close"]), min(o[0], s["prev_close"])

        pos = 0
        entry = k = stop = stop_dist = mae = mfe = 0.0
        for j in range(len(c)):
            exit_px = reason = None

            if pos != 0:
                # protective stop, every minute; a gap through it fills at open
                if pos == 1 and l[j] <= stop:
                    exit_px, reason = min(o[j], stop), "stop"
                elif pos == -1 and h[j] >= stop:
                    exit_px, reason = max(o[j], stop), "stop"
                elif mod[j] >= RTH_CLOSE - 1:
                    exit_px, reason = c[j], "session_end"
                if exit_px is None:
                    mae = max(mae, (entry - l[j]) if pos == 1 else (h[j] - entry))
                    mfe = max(mfe, (h[j] - entry) if pos == 1 else (entry - l[j]))

            if exit_px is None and mod[j] in marks and not np.isnan(sigma[mod[j] - RTH_OPEN]):
                sg = sigma[mod[j] - RTH_OPEN]
                upper, lower = top * (1 + sg), bot * (1 - sg)
                if pos == 1 and c[j] < max(upper, vwap[j]) and not c[j] > upper:
                    exit_px, reason = c[j], "trail"
                elif pos == -1 and c[j] > min(lower, vwap[j]) and not c[j] < lower:
                    exit_px, reason = c[j], "trail"

            if exit_px is not None:
                side = -pos if flip else pos
                if reason == "stop":
                    mae = abs(exit_px - entry)
                trades.append(dict(
                    day=s["day"], side=side, entry_idx=k, exit_idx=j,
                    entry_mod=mod[k], entry_price=entry, exit_price=exit_px,
                    reason=reason, stop_dist=stop_dist,
                    pnl_price=(exit_px - entry) * side,
                    mae_price=mae if not flip else mfe,
                    mfe_price=mfe if not flip else mae,
                ))
                pos = 0
                if reason == "stop" or mod[j] >= RTH_CLOSE - 1:
                    continue

            if pos == 0 and mod[j] in marks and mod[j] < RTH_CLOSE - 1:
                sg = sigma[mod[j] - RTH_OPEN]
                if np.isnan(sg):
                    continue
                upper, lower = top * (1 + sg), bot * (1 - sg)
                if c[j] > upper or c[j] < lower:
                    pos = 1 if c[j] > upper else -1
                    entry, k, mae, mfe = c[j], j, 0.0, 0.0
                    stop_dist = stop_band_mult * sg * o[0]
                    stop = entry - pos * stop_dist

    tr = pd.DataFrame(trades)
    if not tr.empty:
        tr["r_multiple"] = tr["pnl_price"] / tr["stop_dist"]
    return tr
