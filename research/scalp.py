"""Prop Firm Scalping (Bollinger pullback) — independent re-implementation.

EMA90/300 trend filter, pullback entry off a 30-bar / 1.3-std Bollinger band,
rolling vol-percentile filter, stop/target sized off rolling vol. Takes the
raw/back-adjusted 1m frame and returns one row per completed trade, with
MAE/MFE for intraday trailing-drawdown rules.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import TZ, POINT_VALUE, TICK_SIZE

EMA_FAST = 90
EMA_SLOW = 300
BB_WINDOW = 30
BB_K = 1.3
VOL_WINDOW = 60
STOP_MULT = 3.0
TARGET_MULT = 1.5
MIN_VOL_PCT = 0.30
MAX_VOL_PCT = 0.97
VOL_PCT_LOOKBACK = 500
MAX_HOLD_MINUTES = 45
MAX_TRADES_PER_DAY = 5


def generate_trades(df, session_start="09:30", session_end="16:00",
                    sessions=None, ema_fast=EMA_FAST, ema_slow=EMA_SLOW,
                    bb_win=BB_WINDOW, bb_k=BB_K, vol_win=VOL_WINDOW,
                    stop_mult=STOP_MULT, target_mult=TARGET_MULT,
                    min_vol_pct=MIN_VOL_PCT, max_vol_pct=MAX_VOL_PCT,
                    vol_pct_lookback=VOL_PCT_LOOKBACK,
                    max_hold=MAX_HOLD_MINUTES, max_trades_day=MAX_TRADES_PER_DAY,
                    target_through_ticks=1.0, tick_size=TICK_SIZE) -> pd.DataFrame:
    """df must already be back-adjusted (or raw) and have a UTC `timestamp`
    column. Returns the trade table; sizing/prop rules are applied later."""
    d = df.copy().reset_index(drop=True)
    ts_utc = pd.to_datetime(d["timestamp"], utc=True)
    d["date"] = ts_utc.dt.tz_convert(TZ)
    d["price"] = d["close"]

    d["ema_fast"] = d["close"].ewm(span=ema_fast, adjust=False).mean()
    d["ema_slow"] = d["close"].ewm(span=ema_slow, adjust=False).mean()
    d["trend"] = np.where(d["ema_fast"] > d["ema_slow"], 1, -1)

    d["bb_mid"] = d["close"].rolling(bb_win).mean()
    d["bb_std"] = d["close"].rolling(bb_win).std()
    d["bb_upper"] = d["bb_mid"] + bb_k * d["bb_std"]
    d["bb_lower"] = d["bb_mid"] - bb_k * d["bb_std"]

    d["vol"] = d["close"].rolling(vol_win).std()
    d["vol_pctrank"] = d["vol"].rolling(vol_pct_lookback).rank(pct=True)

    def _to_min(hhmm: str) -> int:
        h, m = map(int, hhmm.split(":"))
        return h * 60 + m

    windows = sessions if sessions is not None else [(session_start, session_end)]
    d["minute_of_day"] = d["date"].dt.hour * 60 + d["date"].dt.minute
    d["day"] = d["date"].dt.date

    in_session = np.zeros(len(d), dtype=bool)
    mod_arr = d["minute_of_day"].to_numpy()
    for s, e in windows:
        sm, em = _to_min(s), _to_min(e)
        if sm < em:
            in_session |= (mod_arr >= sm) & (mod_arr < em)
        else:
            in_session |= (mod_arr >= sm) | (mod_arr < em)

    ok_vol = ((d["vol"] > 0) & (d["vol_pctrank"] >= min_vol_pct)
              & (d["vol_pctrank"] <= max_vol_pct)).to_numpy()

    opens = d["open"].to_numpy(); highs = d["high"].to_numpy()
    lows = d["low"].to_numpy(); closes = d["close"].to_numpy()
    lower = d["bb_lower"].to_numpy(); upper = d["bb_upper"].to_numpy()
    trend = d["trend"].to_numpy(); vol = d["vol"].to_numpy()
    days = d["day"].to_numpy()
    bb_ready = ~np.isnan(lower)

    through = target_through_ticks * tick_size
    trades = []
    position = 0
    entry_price = entry_idx = stop_price = target_price = None
    mae = mfe = 0.0
    trades_today = 0
    current_day = None
    was_below = was_above = False

    n = len(d)
    for i in range(n):
        if current_day != days[i]:
            current_day = days[i]
            trades_today = 0
            if position != 0:
                trades.append((entry_idx, i - 1, position, entry_price,
                               opens[i], "day_end", vol[entry_idx], mae, mfe))
                position = 0

        if position == 0:
            can_trade = (in_session[i] and trades_today < max_trades_day
                         and bb_ready[i] and ok_vol[i])
            if not can_trade:
                was_below = was_above = False
            else:
                if trend[i] == 1 and closes[i] < lower[i]:
                    was_below = True
                elif trend[i] == 1 and was_below and closes[i] >= lower[i]:
                    position = 1
                    mae = mfe = 0.0
                    entry_price, entry_idx = closes[i], i
                    stop_price = entry_price - stop_mult * vol[i]
                    target_price = entry_price + target_mult * vol[i]
                    trades_today += 1
                    was_below = False
                else:
                    was_below = False

                if trend[i] == -1 and closes[i] > upper[i]:
                    was_above = True
                elif trend[i] == -1 and was_above and closes[i] <= upper[i]:
                    position = -1
                    mae = mfe = 0.0
                    entry_price, entry_idx = closes[i], i
                    stop_price = entry_price + stop_mult * vol[i]
                    target_price = entry_price - target_mult * vol[i]
                    trades_today += 1
                    was_above = False
                else:
                    was_above = False
        else:
            exit_reason = None
            exit_price = None
            if position == 1:
                mae = max(mae, min(entry_price - lows[i], entry_price - stop_price))
                mfe = max(mfe, min(highs[i] - entry_price, target_price - entry_price))
                if lows[i] <= stop_price:
                    exit_reason, exit_price = "stop", stop_price
                elif highs[i] >= target_price + through:
                    exit_reason, exit_price = "target", target_price
            else:
                mae = max(mae, min(highs[i] - entry_price, stop_price - entry_price))
                mfe = max(mfe, min(entry_price - lows[i], entry_price - target_price))
                if highs[i] >= stop_price:
                    exit_reason, exit_price = "stop", stop_price
                elif lows[i] <= target_price - through:
                    exit_reason, exit_price = "target", target_price

            if exit_reason is None and (i - entry_idx) >= max_hold:
                exit_reason, exit_price = "time", closes[i]
            if exit_reason is None and not in_session[i]:
                exit_reason, exit_price = "session_end", closes[i]

            if exit_reason is not None:
                trades.append((entry_idx, i, position, entry_price, exit_price,
                               exit_reason, vol[entry_idx], mae, mfe))
                position = 0

    if position != 0:
        trades.append((entry_idx, n - 1, position, entry_price, closes[n - 1],
                       "eof", vol[entry_idx], mae, mfe))

    tr = pd.DataFrame(trades, columns=["entry_idx", "exit_idx", "side",
                                       "entry_price", "exit_price", "reason",
                                       "entry_vol", "mae_price", "mfe_price"])
    tr["pnl_price"] = (tr["exit_price"] - tr["entry_price"]) * tr["side"]
    tr["stop_dist"] = stop_mult * tr["entry_vol"]
    tr["r_multiple"] = tr["pnl_price"] / tr["stop_dist"]
    d_date = d["date"].reset_index(drop=True)
    tr["entry_date"] = d_date.loc[tr["entry_idx"]].to_numpy()
    tr["exit_date"] = d_date.loc[tr["exit_idx"]].to_numpy()
    tr["day"] = pd.DatetimeIndex(tr["entry_date"]).date
    return tr
