"""Shared data, roll-adjustment, session and statistics helpers.

Independent re-implementation for the quant-trading prop-firm research.
Reads the raw MNQ parquet read-only; nothing here mutates the source data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DATA_PATH = "/Users/kostas/Documents/quant-trading/data/MNQ_1m_continuous_v2.parquet"

# MNQ contract conventions
POINT_VALUE = 2.0     # $ per index point per contract
TICK_SIZE = 0.25      # index points per tick
TZ = "America/New_York"

# Regular trading hours (ET), minutes after midnight
RTH_OPEN = 570    # 09:30
RTH_CLOSE = 960   # 16:00


def load_raw(path: str = DATA_PATH) -> pd.DataFrame:
    """Read the raw MNQ 1m parquet, sorted by timestamp."""
    df = pd.read_parquet(path)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def back_adjust(df: pd.DataFrame, method: str = "difference") -> pd.DataFrame:
    """Back-adjust a stitched futures series across contract rolls.

    method='difference': shift every bar before a roll by the cumulative sum of
        later roll gaps (open - prev close at the roll bar). Preserves POINT
        moves; distorts PERCENTAGE moves when the price level drifts far.
    method='ratio': multiply every bar before a roll by the cumulative product
        of later roll ratios (open / prev close at the roll bar). Preserves
        PERCENTAGE moves; scales POINT moves.

    The most recent contract is the anchor (unadjusted) in both methods.
    """
    d = df.copy().reset_index(drop=True)
    roll = (d["symbol"] != d["symbol"].shift()).to_numpy()
    roll[0] = False
    o = d["open"].to_numpy()
    prev_close = d["close"].shift().to_numpy()

    if method == "difference":
        gap = np.where(roll, o - prev_close, 0.0)
        cum = np.cumsum(gap[::-1])[::-1]      # cum[i] = sum_{j>=i} gap[j]
        adj = np.roll(cum, -1)                 # adj[i] = sum_{j>i} gap[j]
        adj[-1] = 0.0
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] + adj
    elif method == "ratio":
        ratio = np.where(roll, o / prev_close, 1.0)
        ratio = np.where(np.isfinite(ratio) & (ratio > 0), ratio, 1.0)
        cum = np.cumprod(ratio[::-1])[::-1]
        adj = np.roll(cum, -1)
        adj[-1] = 1.0
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] * adj
    else:
        raise ValueError(f"unknown method: {method}")
    return d


def et_clock(df: pd.DataFrame) -> pd.DataFrame:
    """Add an America/New_York timestamp column to a raw (UTC) frame."""
    d = df.copy()
    d["ts_et"] = pd.to_datetime(d["timestamp"], utc=True).dt.tz_convert(TZ)
    d["minute_of_day"] = d["ts_et"].dt.hour * 60 + d["ts_et"].dt.minute
    d["day"] = d["ts_et"].dt.date
    return d


def build_rth_sessions(df: pd.DataFrame) -> list[dict]:
    """Cut a 1m futures series into complete RTH sessions (09:30-16:00 ET).

    Each session: day, mod (minute-of-day array), OHLC arrays, volume, session
    VWAP anchored at 09:30, and prev_close (prior session's last close).
    Full sessions only: half-days (early close) and partial data are skipped.
    """
    d = et_clock(df)
    rth = d[(d["minute_of_day"] >= RTH_OPEN) & (d["minute_of_day"] < RTH_CLOSE)]
    days = []
    for day, x in rth.groupby("day", sort=True):
        if len(x) < 370 or x["minute_of_day"].iloc[0] != RTH_OPEN:
            continue
        h, l, c = x["high"].to_numpy(), x["low"].to_numpy(), x["close"].to_numpy()
        v = np.maximum(x["volume"].to_numpy().astype(float), 1.0)
        tp = (h + l + c) / 3.0
        days.append(dict(
            day=day, mod=x["minute_of_day"].to_numpy(),
            open=x["open"].to_numpy(), high=h, low=l, close=c,
            volume=v, vwap=np.cumsum(v * tp) / np.cumsum(v),
        ))
    for i, s in enumerate(days):
        s["prev_close"] = days[i - 1]["close"][-1] if i > 0 else np.nan
    return days


def tstat(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.nan
    sd = x.std(ddof=1)
    if sd == 0:
        return np.nan
    return x.mean() / (sd / np.sqrt(len(x)))


def newey_west_tstat(x: np.ndarray, max_lag: int | None = None) -> float:
    """HAC (Newey-West) t-statistic for the mean of a possibly-autocorrelated
    series (e.g. clustered intraday trades)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return np.nan
    if max_lag is None:
        max_lag = min(int(4 * (n / 100.0) ** (2.0 / 9.0)), n - 1)
    e = x - x.mean()
    var = np.sum(e ** 2)
    for lag in range(1, max_lag + 1):
        w = 1.0 - lag / (max_lag + 1.0)
        var += 2.0 * w * np.sum(e[lag:] * e[:-lag])
    var /= n
    se = np.sqrt(var / n)
    if se == 0:
        return np.nan
    return x.mean() / se


def max_t_prob(t_obs: float, n_trials: int) -> float:
    """Approximate probability that the best of N independent |t|-statistics
    (each ~N(0,1) under the null) reaches |t_obs| or higher — the multiple-
    testing / deflation penalty for a best-of-N selection."""
    t_obs = abs(t_obs)
    if n_trials < 1:
        n_trials = 1
    p_single = 2.0 * (1.0 - _norm_cdf(t_obs))
    return 1.0 - (1.0 - p_single) ** n_trials


def _norm_cdf(x: float) -> float:
    # Abramowitz-Stegun 7.1.26 approximation (scipy-free)
    s = 1.0 / (1.0 + 0.2316419 * x)
    t = 0.31938153 * s - 0.356563782 * s ** 2 + 1.781477937 * s ** 3 \
        - 1.821255978 * s ** 4 + 1.330274429 * s ** 5
    pdf = np.exp(-x * x / 2.0) / np.sqrt(2.0 * np.pi)
    return 1.0 - pdf * t


def round_trip_cost(reason: str, commission_per_side: float, slippage_ticks: float,
                    tick_size: float = TICK_SIZE, point_value: float = POINT_VALUE) -> float:
    """Dollar cost per contract of one round trip.

    commission_per_side is charged on both fills (entry + exit).
    Slippage (in ticks) is charged per MARKET fill only; a take-profit
    ('target') exit is a resting limit and pays no slippage.
    """
    market_fills = 1 if reason == "target" else 2
    return (2.0 * commission_per_side
            + market_fills * slippage_ticks * tick_size * point_value)


def daily_pnl_from_trades(tr: pd.DataFrame, net_col: str = "net_usd") -> pd.Series:
    """Sum a net-$ column by entry day, over a full day index."""
    if tr.empty:
        return pd.Series(dtype=float)
    return tr.groupby("day")[net_col].sum()
