"""Reusable trade-level and prop-firm statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import tstat, newey_west_tstat


def trade_stats(tr: pd.DataFrame, net_col: str = "net_usd", per_contract: bool = True) -> dict:
    """Per-trade and daily stats for a trade table that already has a net-$ column."""
    if tr.empty:
        return {}
    n = tr[net_col].to_numpy()
    win = n > 0
    loss = n < 0
    gross_win = n[win].sum()
    gross_loss = -n[loss].sum()
    daily = tr.groupby("day")[net_col].sum()
    curve = daily.cumsum()
    dd = (curve.cummax() - curve).max()

    # longest losing streak (consecutive losing trades)
    streak = max_streak = 0
    for v in n:
        if v < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return dict(
        n_trades=len(tr),
        win_rate=float(win.mean()),
        avg_win=float(n[win].mean()) if win.any() else float("nan"),
        avg_loss=float(n[loss].mean()) if loss.any() else float("nan"),
        profit_factor=float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        expectancy=float(n.mean()),
        t_stat=float(tstat(n)),
        t_stat_nw=float(newey_west_tstat(n)),
        max_dd=float(dd),
        worst_day=float(daily.min()),
        best_day=float(daily.max()),
        longest_losing_streak=max_streak,
        pct_days_profitable=float((daily > 0).mean()),
        n_days=len(daily),
        daily_sharpe=float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else float("nan"),
    )


def print_trade_stats(label: str, s: dict) -> None:
    print(f"\n--- {label} ---")
    print(f"trades            : {s['n_trades']}")
    print(f"win rate          : {s['win_rate']:.1%}")
    print(f"avg win / loss    : {s['avg_win']:+,.2f} / {s['avg_loss']:+,.2f}")
    print(f"profit factor     : {s['profit_factor']:.3f}")
    print(f"expectancy        : {s['expectancy']:+,.3f}")
    print(f"t-stat (simple/NW): {s['t_stat']:+.2f} / {s['t_stat_nw']:+.2f}")
    print(f"max drawdown      : {s['max_dd']:,.2f}")
    print(f"worst / best day  : {s['worst_day']:,.2f} / {s['best_day']:,.2f}")
    print(f"longest losing run: {s['longest_losing_streak']}")
    print(f"% days profitable : {s['pct_days_profitable']:.1%}  ({s['n_days']} days)")
    print(f"daily Sharpe      : {s['daily_sharpe']:.2f}")
