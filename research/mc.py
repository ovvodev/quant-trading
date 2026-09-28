"""Monte Carlo helpers: daily-P&L bootstrap and funded-account survival."""
from __future__ import annotations

import numpy as np

from config import PropRules


def daily_prop_walk(daily, rules: PropRules, horizon: int | None = None):
    """Walk a daily net-$ series (at traded size) under the prop rules.

    Returns (outcome, n_days, final_balance). 'time' = horizon or data ran out.
    """
    bal = rules.account
    hwm = rules.account
    pnls: list[float] = []
    for i, pnl in enumerate(daily):
        if horizon is not None and i >= horizon:
            return "time", i, bal
        bal += pnl
        pnls.append(pnl)
        if rules.daily_loss is not None and pnl <= -rules.daily_loss:
            return "failed_daily_loss", i + 1, bal
        hwm = max(hwm, bal)
        floor = min(hwm - rules.max_loss, rules.account)
        if bal <= floor:
            return "failed_drawdown", i + 1, bal
        if bal - rules.account >= rules.target:
            total = bal - rules.account
            best = max(pnls)
            if rules.consistency is not None and best > rules.consistency * total:
                return "failed_consistency", i + 1, bal
            return "passed", i + 1, bal
    return "time", len(daily), bal


def funded_survives(daily, rules: PropRules, n_days: int) -> bool:
    """Funded-account model: $50k balance, trailing $max_loss from peak,
    floor locks at starting balance. Survive = no breach within n_days."""
    bal = rules.account
    hwm = rules.account
    for pnl in daily[:n_days]:
        bal += pnl
        hwm = max(hwm, bal)
        floor = min(hwm - rules.max_loss, rules.account)
        if bal <= floor:
            return False
    return True


def bootstrap(daily_pnl, rules: PropRules, n=5000, horizon=250, seed=0):
    """Resample daily P&L blocks with replacement into n synthetic paths.

    Returns (outcomes list, days list, survival dict {30/60/90: fraction}).
    """
    rng = np.random.default_rng(seed)
    daily = np.asarray(daily_pnl, dtype=float)
    n_days = len(daily)
    outcomes: list[str] = []
    days: list[int] = []
    surv = {30: 0, 60: 0, 90: 0}

    for _ in range(n):
        idx = rng.integers(0, n_days, horizon)
        out, d, _ = daily_prop_walk(daily[idx], rules, horizon=horizon)
        outcomes.append(out)
        days.append(d)
        # funded survival on a fresh 90-day draw
        idx2 = rng.integers(0, n_days, 90)
        path2 = daily[idx2]
        for nd in (30, 60, 90):
            if funded_survives(path2, rules, nd):
                surv[nd] += 1
    return outcomes, days, {k: v / n for k, v in surv.items()}


def summarize_bootstrap(outcomes, days, surv, label=""):
    from collections import Counter
    c = Counter(outcomes)
    n = len(outcomes)
    passed = [d for o, d in zip(outcomes, days) if o == "passed"]
    print(f"\n--- {label} BOOTSTRAP (n={n}) ---")
    for k in ("passed", "failed_drawdown", "failed_daily_loss", "failed_consistency", "time"):
        if c.get(k, 0) > 0:
            print(f"  {k:18s}: {c.get(k,0):5d} ({c.get(k,0)/n:.1%})")
    if passed:
        print(f"  days to pass: median {np.median(passed):.0f}, "
              f"mean {np.mean(passed):.0f}")
    print(f"  funded survival 30/60/90d: {surv[30]:.1%} / {surv[60]:.1%} / {surv[90]:.1%}")
