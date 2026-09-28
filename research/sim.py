"""Configurable futures prop-firm evaluation simulator (v2).

Hard rules from the brief, all swappable via config.py:
  - trailing $-drawdown ('eod' or 'intraday'), breached by OPEN losses,
    floor locks at the starting balance
  - daily loss limit -> FAIL (the brief specifies "breach = fail")
  - consistency-at-target -> FAIL if best day exceeds the allowed share
  - max contract cap, fixed-contract or risk-based sizing
  - commission per side + per-market-fill slippage
  - optional news-blackout entry filter

Strategy-agnostic. Required trade columns: day, side, pnl_price, stop_dist,
mae_price, mfe_price, reason (+ entry_minute for the blackout filter).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import PropRules


def _to_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _vector_cost(reasons, commission_per_side, slippage_ticks, tick_size, point_value):
    r = np.asarray(reasons)
    market_fills = np.where(r == "target", 1, 2)
    return (2.0 * commission_per_side
            + market_fills * slippage_ticks * tick_size * point_value)


def enrich(trades: pd.DataFrame, rules: PropRules) -> pd.DataFrame:
    tr = trades.copy().reset_index(drop=True)
    pv, ts = rules.point_value, rules.tick_size
    tr["net_usd"] = tr["pnl_price"] * pv - _vector_cost(
        tr["reason"], rules.commission_per_side, rules.slippage_ticks, ts, pv)
    tr["mae_usd"] = tr["mae_price"] * pv
    tr["mfe_usd"] = tr["mfe_price"] * pv
    return tr


def apply_blackout(tr: pd.DataFrame, rules: PropRules) -> pd.DataFrame:
    if not rules.news_blackout or "entry_minute" not in tr.columns:
        return tr
    blocked = np.zeros(len(tr), dtype=bool)
    em = tr["entry_minute"].to_numpy()
    for s, e in rules.news_blackout:
        sm, emm = _to_min(s), _to_min(e)
        blocked |= (em >= sm) & (em < emm)
    return tr[~blocked].reset_index(drop=True)


def simulate(trades: pd.DataFrame, rules: PropRules,
             contracts: int | None = None, risk_usd: float | None = None,
             ) -> list[dict]:
    """Walk the trade list under `rules`, resetting to a fresh cycle on every
    pass/fail. Returns one dict per cycle: outcome (passed / failed_drawdown /
    failed_daily_loss / failed_consistency / failed_min_days / in_progress),
    start_day, end_day, n_trades, final_equity."""
    tr = enrich(apply_blackout(trades, rules), rules)
    pv = rules.point_value
    use_fixed = contracts is not None

    def _floor(hwm: float) -> float:
        return min(hwm - rules.max_loss, rules.account)

    cycles: list[dict] = []
    bal = hwm = day_start = rules.account
    day = None
    day_low = rules.account
    day_halted = False
    stand_down_active = False
    consec_losses = 0
    n_trades = 0
    start_day = None
    daily_pnl: dict = {}
    trading_days: set = set()

    def _reset():
        nonlocal bal, hwm, day_start, day, day_low, day_halted, n_trades
        nonlocal start_day, daily_pnl, trading_days, stand_down_active, consec_losses
        bal = hwm = day_start = rules.account
        day = None
        day_low = rules.account
        day_halted = False
        stand_down_active = False
        consec_losses = 0
        n_trades = 0
        start_day = None
        daily_pnl = {}
        trading_days = set()

    for row in tr.itertuples(index=False):
        d = row.day
        if start_day is None:
            start_day = d
        if d != day:
            if rules.trailing == "eod" and day is not None:
                hwm = max(hwm, bal)
            if day is not None:
                prev_pnl = daily_pnl.get(day, 0.0)
                consec_losses = consec_losses + 1 if prev_pnl < 0 else 0
                stand_down_active = (rules.stand_down_days is not None
                                     and consec_losses >= rules.stand_down_days)
            day, day_start, day_low = d, bal, bal
            day_halted = stand_down_active

        if day_halted:
            continue

        if use_fixed:
            units = float(contracts)
        else:
            units = np.floor(risk_usd / (row.stop_dist * pv)) if row.stop_dist > 0 else 0.0
        if rules.dd_sizing:
            buffer = bal - _floor(hwm)
            for thresh, c in sorted(rules.dd_sizing, reverse=True):
                if buffer <= thresh:
                    units = float(c)
                    break
        if rules.max_contracts is not None:
            units = min(units, float(rules.max_contracts))
        if units < 1:
            continue

        worst = bal - units * row.mae_usd          # worst OPEN equity during the trade
        if rules.trailing == "intraday":
            hwm = max(hwm, bal + units * row.mfe_usd)

        n_trades += 1
        trading_days.add(d)

        new_bal = bal + units * row.net_usd        # realized
        daily_pnl[d] = daily_pnl.get(d, 0.0) + units * row.net_usd
        day_low = min(day_low, worst, new_bal)

        outcome = None
        daily_breached = (rules.daily_loss is not None
                          and day_start - day_low >= rules.daily_loss)
        if daily_breached and rules.daily_loss_is_fail:
            outcome = "failed_daily_loss"
        elif worst <= _floor(hwm):
            outcome = "failed_drawdown"
        elif new_bal <= _floor(hwm):
            outcome = "failed_drawdown"
        elif new_bal - rules.account >= rules.target:
            total = new_bal - rules.account
            best = max(daily_pnl.values(), default=0.0)
            if rules.consistency is not None and best > rules.consistency * total:
                outcome = "failed_consistency"
            elif rules.min_days > 0 and len(trading_days) < rules.min_days:
                outcome = "failed_min_days"
            else:
                outcome = "passed"

        if outcome is not None:
            bal = min(worst, _floor(hwm)) if outcome == "failed_drawdown" else new_bal
            cycles.append(dict(outcome=outcome, start_day=start_day, end_day=d,
                               n_trades=n_trades, final_equity=bal))
            _reset()
        else:
            bal = new_bal
            if daily_breached:
                day_halted = True                      # daily-loss halt (resume next day)
            elif rules.daily_profit_lock is not None and daily_pnl[d] >= rules.daily_profit_lock:
                day_halted = True
            elif rules.daily_soft_stop is not None and day_start - day_low >= rules.daily_soft_stop:
                day_halted = True

    if n_trades > 0:
        cycles.append(dict(outcome="in_progress", start_day=start_day, end_day=None,
                           n_trades=n_trades, final_equity=bal))
    return cycles


def pass_rate(cycles: list[dict]) -> tuple[int, float]:
    done = [c for c in cycles if c["outcome"] != "in_progress"]
    if not done:
        return 0, float("nan")
    return len(done), sum(c["outcome"] == "passed" for c in done) / len(done)


def fail_breakdown(cycles: list[dict]) -> dict:
    out = {"passed": 0, "failed_drawdown": 0, "failed_daily_loss": 0,
           "failed_consistency": 0, "failed_min_days": 0, "in_progress": 0}
    for c in cycles:
        out[c["outcome"]] = out.get(c["outcome"], 0) + 1
    return out
