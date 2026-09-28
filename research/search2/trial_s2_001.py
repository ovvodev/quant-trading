"""S2-001: frozen overnight-range-break candidate on development only.

This script intentionally refuses validation/final inputs. See plan.md for the
pre-registered rules. All outputs stay in search2/outputs/.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEARCH = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import common

DEV = SEARCH / "splits" / "development.parquet"
OUT = SEARCH / "outputs"
RULES = {
    "id": "S2-001", "family": "overnight_range_breakout",
    "overnight_et": "prior date 18:00 through current date 09:29",
    "overnight_min_bars": 600, "entry_window_et": "09:30..16:43 signal close; next bar open",
    "trigger": "first close strictly outside overnight high/low",
    "stop": "opposite overnight extreme", "target": None,
    "exit": "stop touch or close of final bar before 16:45 ET",
    "cost": "1 tick adverse each market fill + $0.50/side commission",
    "roll_policy": "exclude all session dates whose mapped overnight/RTH bars contain symbol transition",
    "contracts": 1, "random_seed": 20260928,
}
RULES_HASH = hashlib.sha256(json.dumps(RULES, sort_keys=True).encode()).hexdigest()
TICK = 0.25
PV = 2.0
COMMISSION_RT = 1.0
SLIP_USD_PER_FILL = TICK * PV


def _attach_et(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ts_et"] = pd.to_datetime(d["timestamp"], utc=True).dt.tz_convert("America/New_York")
    d["mod"] = d["ts_et"].dt.hour * 60 + d["ts_et"].dt.minute
    d["calday"] = d["ts_et"].dt.date
    # Assign evening bars to the following RTH trading date, morning bars to current.
    d["session_day"] = d["calday"]
    evening = d["mod"] >= 18 * 60
    d.loc[evening, "session_day"] = d.loc[evening, "ts_et"].dt.date + pd.Timedelta(days=1)
    return d


def _simulate_one(daybars: pd.DataFrame, side: int, stop_dist: float,
                  entry_idx: int | None = None, signal_idx: int | None = None,
                  delayed: bool = False) -> dict | None:
    """Resolve one market trade. side +1/-1; entry_idx indexes sorted daybars."""
    if entry_idx is None:
        if signal_idx is None:
            return None
        entry_idx = signal_idx + (2 if delayed else 1)
    if entry_idx >= len(daybars):
        return None
    entry = daybars.iloc[entry_idx]
    if int(entry["mod"]) >= 16 * 60 + 45:
        return None
    raw_entry = float(entry["open"])
    if not np.isfinite(raw_entry) or not np.isfinite(stop_dist) or stop_dist < 2:
        return None
    stop = raw_entry - side * stop_dist
    mae = 0.0
    mfe = 0.0
    exit_raw = None
    reason = None
    exit_idx = None
    for j in range(entry_idx, len(daybars)):
        row = daybars.iloc[j]
        if int(row["mod"]) >= 16 * 60 + 45:
            break
        op, hi, lo, cl = map(float, (row["open"], row["high"], row["low"], row["close"]))
        fav = (hi - raw_entry) if side == 1 else (raw_entry - lo)
        adv = (raw_entry - lo) if side == 1 else (hi - raw_entry)
        mfe = max(mfe, fav)
        mae = max(mae, adv)
        stop_hit = (lo <= stop) if side == 1 else (hi >= stop)
        if stop_hit:
            # Gap-through stop: worse of stop and open. Intrabar stop: stop price.
            exit_raw = min(stop, op) if side == 1 else max(stop, op)
            reason, exit_idx = "stop", j
            break
    if exit_raw is None:
        valid = daybars[(daybars["mod"] < 16 * 60 + 45) & (daybars.index >= entry_idx)]
        if valid.empty:
            return None
        exitrow = valid.iloc[-1]
        exit_raw = float(exitrow["close"])
        exit_idx = int(exitrow["_pos"])
        reason = "flat"
    points = side * (exit_raw - raw_entry)
    # Entry and exit are market fills: adverse 1 tick each. Stop gap is already
    # represented in exit_raw, then slippage is charged separately.
    net1 = points * PV - COMMISSION_RT - 2 * SLIP_USD_PER_FILL
    net2 = points * PV - 2 * COMMISSION_RT - 4 * SLIP_USD_PER_FILL
    return {
        "side": side, "entry_ts": entry["ts_et"].isoformat(), "entry_idx": int(entry["_pos"]),
        "signal_idx": int(daybars.iloc[signal_idx]["_pos"]) if signal_idx is not None else -1,
        "entry_price": raw_entry, "stop_price": stop, "exit_price": exit_raw,
        "exit_idx": int(exit_idx), "reason": reason, "stop_dist": stop_dist,
        "pnl_points_gross": points, "net_usd": net1, "net_2x_usd": net2,
        "mae_points": mae, "mfe_points": mfe, "day": str(entry["session_day"]),
        "entry_minute": int(entry["mod"]),
    }


def _extract_candidate(df: pd.DataFrame, delayed: bool = False) -> list[dict]:
    d = df.sort_values("timestamp").reset_index(drop=True)
    if "roll" not in d:
        raise ValueError("Input must carry roll flags from the shared adjustment helper")
    d = _attach_et(d)
    if "_exclude_day" in d:
        excluded = set(d.loc[d["_exclude_day"], "session_day"])
    else:
        excluded = set()
    bad_days = set(d.loc[d["roll"], "session_day"])
    results: list[dict] = []
    for session_day, full in d.groupby("session_day", sort=True):
        if session_day in bad_days or session_day in excluded:
            continue
        # Keep only evening of D-1 and all bars on date D; remove prior ETH.
        keep = (((full["mod"] >= 18 * 60) & (full["calday"] < session_day)) |
                ((full["mod"] < 18 * 60) & (full["calday"] == session_day)))
        g = full.loc[keep].sort_values("timestamp").reset_index(drop=True)
        g["_pos"] = np.arange(len(g), dtype=int)
        overnight = g.loc[(g["mod"] >= 18 * 60) | (g["mod"] < 9 * 60 + 30)]
        if len(overnight) < 600:
            continue
        overnight_high = float(overnight["high"].max())
        overnight_low = float(overnight["low"].min())
        rth = g.loc[(g["mod"] >= 9 * 60 + 30) & (g["mod"] <= 16 * 60 + 43)].reset_index(drop=True)
        if rth.empty or not np.isfinite(overnight_high + overnight_low):
            continue
        for i in range(len(rth) - 1):
            row = rth.iloc[i]
            close = float(row["close"])
            side = 1 if close > overnight_high else (-1 if close < overnight_low else 0)
            if side == 0:
                continue
            fill_i = i + (2 if delayed else 1)
            if fill_i >= len(rth):
                break
            fill = rth.iloc[fill_i]
            stop_dist = (float(fill["open"]) - overnight_low) if side == 1 else (overnight_high - float(fill["open"]))
            if stop_dist >= 2.0:
                entry_pos = int(g.index[g["timestamp"] == fill["timestamp"]][0])
                signal_pos = int(g.index[g["timestamp"] == row["timestamp"]][0])
                trade = _simulate_one(g, side, stop_dist, entry_pos, signal_pos)
                if trade:
                    trade.update({"overnight_high": overnight_high, "overnight_low": overnight_low})
                    results.append(trade)
            break
    return results


def _summarize(trades: list[dict], label: str) -> dict:
    if not trades:
        return {"label": label, "trades": 0, "net_usd_per_trade": None, "tstat_nw": None}
    t = pd.DataFrame(trades).sort_values("entry_ts")
    x = t.net_usd.to_numpy(float)
    # Session-day aggregate Newey-West t, one observation per session.
    daily = t.groupby("day").net_usd.sum().to_numpy(float)
    n = len(daily)
    if n > 1:
        e = daily - daily.mean()
        lag = min(int(4 * (n / 100.0) ** (2 / 9)), n - 1)
        var = np.dot(e, e)
        for k in range(1, lag + 1):
            var += 2 * (1 - k / (lag + 1)) * np.dot(e[k:], e[:-k])
        se = np.sqrt(max(var / n, 0) / n)
        tstat = float(daily.mean() / se) if se > 0 else None
    else:
        tstat = None
    months = pd.to_datetime(t["day"]).dt.to_period("M")
    mon = t.assign(month=months).groupby("month").net_usd.sum().sort_values(ascending=False)
    top3 = set(mon.head(3).index)
    trimmed = float(t.loc[~months.isin(top3), "net_usd"].sum())
    day_sum = t.groupby("day").net_usd.sum()
    total = float(x.sum())
    return {
        "label": label, "trades": len(t), "sessions": n,
        "gross_points_mean": float(t.pnl_points_gross.mean()),
        "net_usd_per_trade": float(x.mean()), "net_2x_usd_per_trade": float(t.net_2x_usd.mean()),
        "net_total_usd": total, "net_total_2x_usd": float(t.net_2x_usd.sum()),
        "win_rate_net": float((x > 0).mean()), "profit_factor_net": float(x[x > 0].sum() / abs(x[x < 0].sum())) if np.any(x < 0) else None,
        "tstat_nw_daily": tstat, "mean_mae_points": float(t.mae_points.mean()),
        "mean_mfe_points": float(t.mfe_points.mean()), "top3_months_removed_net_usd": trimmed,
        "max_month_share": float(mon.iloc[0] / total) if total > 0 and len(mon) else None,
        "max_day_share": float(day_sum.max() / total) if total > 0 and len(day_sum) else None,
        "by_year_net_usd": {str(k): float(v) for k, v in t.groupby(pd.to_datetime(t["day"]).dt.year).net_usd.sum().items()},
        "by_entry_hour_net_usd": {str(k): float(v) for k, v in t.groupby(t["entry_minute"] // 60).net_usd.sum().items()},
    }


def _bootstrap_ci(trades: list[dict], reps: int = 5000, seed: int = 20260928) -> list[float] | None:
    if not trades:
        return None
    t = pd.DataFrame(trades)
    daily = t.groupby("day").net_2x_usd.sum().to_numpy(float)
    if len(daily) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    for i in range(reps):
        means[i] = rng.choice(daily, size=len(daily), replace=True).mean()
    return [float(np.quantile(means, .025)), float(np.quantile(means, .975))]


def _controls(df: pd.DataFrame, candidate: list[dict]) -> tuple[list[dict], list[dict]]:
    rng = np.random.default_rng(20260928)
    data = _attach_et(df.sort_values("timestamp").reset_index(drop=True))
    data["roll"] = df.sort_values("timestamp").reset_index(drop=True)["roll"].to_numpy()
    data["_pos"] = np.arange(len(data), dtype=int)
    bad_days = set(data.loc[data["roll"], "session_day"])
    excluded_days = set(data.loc[data["_exclude_day"], "session_day"]) if "_exclude_day" in data else set()
    allbars = {}
    for key, frame in data.groupby("session_day", sort=True):
        if key not in bad_days and key not in excluded_days:
            clean = frame.reset_index(drop=True)
            clean["_pos"] = np.arange(len(clean), dtype=int)
            allbars[str(key)] = clean
    random, opposite = [], []
    for original in candidate:
        g = allbars.get(original["day"])
        if g is None:
            continue
        eligible = g.loc[(g["mod"] >= 9 * 60 + 30) & (g["mod"] <= 16 * 60 + 43)].reset_index(drop=True)
        if len(eligible) < 3:
            continue
        k = int(rng.integers(0, len(eligible) - 1))
        random_side = int(original["side"] if rng.random() < 0.5 else -original["side"])
        random_pos = int(g.index[g["timestamp"] == eligible.iloc[k + 1]["timestamp"]][0])
        random_trade = _simulate_one(g, random_side, float(original["stop_dist"]), random_pos)
        if random_trade:
            random.append(random_trade)
        original_ts = pd.Timestamp(original["entry_ts"]).tz_convert("UTC")
        match_pos = np.flatnonzero(g["timestamp"].to_numpy() == original_ts)
        if len(match_pos):
            opposite_trade = _simulate_one(g, -int(original["side"]), float(original["stop_dist"]), int(match_pos[0]))
            if opposite_trade:
                opposite.append(opposite_trade)
    return random, opposite


def main() -> None:
    if not DEV.is_file():
        raise FileNotFoundError(DEV)
    OUT.mkdir(exist_ok=True)
    source_hash = hashlib.sha256(DEV.read_bytes()).hexdigest()
    raw = pd.read_parquet(DEV)
    # Apply the existing verified roll-adjustment helper. Exclude every bar at
    # a contract transition and all trade dates touched by such a transition.
    raw = raw.sort_values("timestamp").reset_index(drop=True)
    roll = raw["symbol"].ne(raw["symbol"].shift())
    if len(roll):
        roll.iloc[0] = False
    adjusted = common.back_adjust(raw, "difference")
    adjusted["roll"] = roll.to_numpy()
    df = adjusted
    # Verify each assigned RTH signal interval is consecutive 1-minute bars;
    # missing timestamps invalidate the candidate day rather than being skipped.
    et = _attach_et(df)
    day_gaps = []
    for day, g in et.groupby("session_day", sort=True):
        rth = g.loc[(g["mod"] >= 570) & (g["mod"] <= 1003), "timestamp"].sort_values()
        if len(rth) < 300 or (len(rth) > 1 and not (rth.diff().dropna() == pd.Timedelta(minutes=1)).all()):
            day_gaps.append(day)
    if day_gaps:
        # Exclude affected sessions uniformly from candidate and controls.
        df["_exclude_day"] = et["session_day"].isin(day_gaps).to_numpy()
    trades = _extract_candidate(df, delayed=False)
    delayed = _extract_candidate(df, delayed=True)
    random, opposite = _controls(df, trades)
    summary = {
        "candidate_id": "S2-001", "family": RULES["family"], "rules_hash": RULES_HASH,
        "development_file_sha256": source_hash,
        "rules": RULES,
        "candidate": _summarize(trades, "candidate"),
        "extra_bar_delay": _summarize(delayed, "extra_bar_delay"),
        "random_entry_control": _summarize(random, "random_entry"),
        "opposite_side_control": _summarize(opposite, "opposite_side"),
        "day_block_bootstrap_2x_95ci_mean_daily_usd": _bootstrap_ci(trades),
        "seed": 20260928,
    }
    pd.DataFrame(trades).to_csv(OUT / "S2-001-development-trades.csv", index=False)
    (OUT / "S2-001-development-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
