"""Configurable prop-firm simulator rule sets.

Defaults follow the trader's brief (the numbers in the original prompt);
Topstep/Apex-style presets are swappable and editable via `prop_config.json`.
Nothing in this module is strategy-specific.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "prop_config.json")


@dataclass
class PropRules:
    account: float = 50_000.0          # starting balance ($)
    target: float = 3_000.0            # profit target ($)
    max_loss: float = 2_000.0          # trailing max drawdown ($)
    trailing: str = "intraday"         # 'eod' or 'intraday'
    daily_loss: float | None = 1_000.0  # daily loss limit ($); None = off
    daily_loss_is_fail: bool = True    # True: breach=fail (brief); False: halt-for-day
    daily_profit_lock: float | None = None  # stop entering after day P&L >= X ($)
    daily_soft_stop: float | None = None    # stand down after day worst <= -Y ($)
    stand_down_days: int | None = None      # skip a day after N consecutive losing days
    dd_sizing: list | None = None           # [(buffer_threshold, contracts), ...] desc
    consistency: float | None = 0.40   # max single-day share of total profit
    max_contracts: int = 5             # MNQ-equivalent contract cap
    flat_time: str = "16:45"           # ET, hard flat time
    commission_per_side: float = 0.50  # $ per side per contract
    slippage_ticks: float = 1.0        # ticks per market fill
    tick_size: float = 0.25
    point_value: float = 2.0           # MNQ $/point
    news_blackout: list = field(default_factory=list)  # [(start,end) ET, ...]
    min_days: int = 0                  # min trading days for some firms

    def flat_minute(self) -> int:
        h, m = map(int, self.flat_time.split(":"))
        return h * 60 + m


_DEFAULTS = dict(account=50_000, target=3_000, max_loss=2_000, trailing="intraday",
                 daily_loss=1_000, consistency=0.40, max_contracts=5, flat_time="16:45",
                 commission_per_side=0.50, slippage_ticks=1.0, tick_size=0.25,
                 point_value=2.0, news_blackout=[], min_days=0)


def _generic_50k() -> dict:
    """The trader's own defaults from the brief."""
    return dict(_DEFAULTS)


def _topstep_50k() -> dict:
    """Topstep-style shape (illustrative; numbers are generic, not official)."""
    return dict(account=50_000, target=3_000, max_loss=2_000, trailing="eod",
                daily_loss=1_000, consistency=0.50, max_contracts=5,
                flat_time="16:45", commission_per_side=0.50, slippage_ticks=1.0,
                tick_size=0.25, point_value=2.0, news_blackout=[], min_days=2)


def _apex_50k() -> dict:
    """Apex-style shape (illustrative; numbers are generic, not official)."""
    return dict(account=50_000, target=3_000, max_loss=2_500, trailing="eod",
                daily_loss=None, consistency=None, max_contracts=5,
                flat_time="16:45", commission_per_side=0.50, slippage_ticks=1.0,
                tick_size=0.25, point_value=2.0, news_blackout=[], min_days=7)


_PRESETS = {
    "generic_50k": _generic_50k(),
    "topstep_50k": _topstep_50k(),
    "apex_50k": _apex_50k(),
}


def _ensure_config_file() -> str:
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(_PRESETS, f, indent=2)
    return CONFIG_PATH


def load_rules(name: str = "generic_50k") -> PropRules:
    """Load a named rule set from prop_config.json (created on first use)."""
    path = _ensure_config_file()
    with open(path) as f:
        presets = json.load(f)
    if name not in presets:
        raise KeyError(f"unknown preset {name!r}; available: {list(presets)}")
    return PropRules(**presets[name])


def list_presets() -> list[str]:
    with open(_ensure_config_file()) as f:
        return list(json.load(f).keys())


if __name__ == "__main__":
    for p in list_presets():
        print(p, "->", asdict(load_rules(p)))
