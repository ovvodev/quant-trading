# Prop-Firm Strategy Evaluation — Steps 1–3

**Date:** 2026-09-28
**Data:** MNQ 1-min continuous, 2021-09-23 → 2026-09-22 (1,770,279 bars, 20 rolls)
**Scope:** re-implement + validate the two prop-firm strategies in
`je-suis-tm/quant-trading`, then run them through a configurable prop simulator.
All code in `research/`; all outputs in `research/results/`. Original data files untouched.

**Cost model (brief defaults):** $0.50/side commission + 1 tick slippage per market fill, MNQ $2/pt, tick 0.25.
**Prop rules (brief defaults, swappable):** $50k account, $3,000 target, $2,000 trailing DD (intraday), $1,000 daily loss (breach=fail), consistency ≤40% of total profit at target, 5-MNQ cap, flat by 16:45 ET, news-blackout windows (off for main run).

---

## 1. Re-implementation fidelity (vs the reference / Pine)

| Strategy | My trades | Reference | Exact match |
|---|---|---|---|
| Scalping (Bollinger pullback) | 5,916 | 5,916 | 100.0% (entry/exit/reason/side) |
| Intraday Momentum (noise area) | 1,100 | 1,100 | 100.0% (entry/exit/reason/side) |

Per-trade parity is exact, so source-level Pine parity is confirmed. (Pine cannot execute locally; parity is read against the Python reference which the repo states matches Pine one-for-one.)

## 2. Roll-adjustment method (difference vs ratio)

- Difference adjustment shifts the 2021 price level **+3,774 pts (+24.8%)** and distorts intraday %-moves by ~13–14% (median 0.477% → 0.414%); ratio adjustment preserves them exactly (machine-precision zero).
- For the momentum strategy (a %-based signal) the distortion is almost fully self-cancelling: **0 trade-count delta** difference-vs-raw, net **+$18.14 vs +$17.60/trade (+3%)**. Ratio gives 3 extra trades and +$20.22, but that dollar figure is inflated ~10% (ratio scales point moves) — not used for $.
- **Verdict:** difference adjustment does NOT invalidate the momentum finding; the ~3% flatter comes from the protective stop (σ·adjusted-open) being ~7% wider in points in early years. No negative/implausible prices in any method.

## 3. Step 1 — headline stats (net, per contract)

| Metric | Scalping | Momentum |
|---|---|---|
| trades | 5,916 | 1,100 |
| win rate | 60.5% | 39.5% |
| avg win / loss | +$56.1 / −$88.4 | +$193.1 / −$95.9 |
| profit factor | 0.977 | 1.312 |
| **expectancy $/trade** | **−$0.78** | **+$18.14** |
| t-stat (simple/NW) | −0.68 / −0.68 | +2.69 / +2.94 |
| max drawdown ($/contract) | $11,000 | $3,609 |
| worst / best day | −$919 / +$1,113 | −$723 / +$2,991 |
| longest losing run | 10 | 11 |
| % days profitable | 52.1% | 45.8% |
| daily Sharpe | −0.30 | 1.70 |
| longs / shorts | — | +$24.88 / +$11.47 |
| **control (flip side)** | — | **−$22.14 (t −3.28)** |
| by year | — | 2021 +$461, 2022 +$6,097, 2023 +$4,433, 2024 +$4,282, 2025 +$3,423, 2026 +$1,259 |

**Scalp has no edge** — gross +0.0073R (t 0.93), net negative, PF < 1, and all 9 stop/target grid cells negative (−$0.73 to −$1.37). Reproduces the review's "0 of 25 positive".

**Momentum has a real edge** — net +$18.14/t (t 2.69), PF 1.31, both sides positive, opposite-side control strongly negative (t −3.28). This reproduces the review's +$18.44 (t 2.74).

## 4. Step 2 — prop-firm Monte Carlo

### Momentum, 2 MNQ (rolling starts, brief rules — intraday trailing, daily=fail, consistency 40%)

| Outcome | Count | Share |
|---|---|---|
| **passed** | 205 | **28.0%** |
| failed_drawdown | 308 | 42.1% |
| failed_daily_loss | 135 | 18.4% |
| failed_consistency | 72 | 9.8% |
| time | 12 | 1.6% |

Days to pass: median 76, mean 86. **Zero-edge pass rate 4.2%** (10 seeds) → momentum is ~6.7× the coin.

### Verification of the review's "48% vs 23%" — CONFIRMED

Under the review's exact method (continuous cycles, EOD trailing, daily-as-halt, no consistency, $0.70 RT): **48.3% pass vs 22.1% zero-edge** — my simulator reproduces it exactly. The lower 28% above is the *brief's harsher metric* (rolling starts + intraday trailing + daily-loss-as-fail + consistency), not a discrepancy.

### Bootstrap (5,000 resamples of daily P&L blocks)

| | Momentum 2 MNQ | Scalp (per-contract) |
|---|---|---|
| pass | 24.4% | 17.7% |
| failed_drawdown | 31.5% | 77.2% |
| failed_daily_loss | 19.9% | — |
| failed_consistency | 24.2% | — |
| days to pass (median) | 24 | 121 |
| funded survival 30/60/90d | 66.4% / 52.3% / 48.6% | 92.2% / 70.4% / 53.5% |

### Scalp, risk $500/trade (rolling starts, brief rules)

Pass 13.4% (zero-edge 5.4%), failed_drawdown 31.0%, failed_daily_loss 54.8%, days-to-pass median 20.

## 5. Step 3 — robustness

### IS/OOS and walk-forward (momentum)

- In-sample (< 2024-04): **+$19.35/t (t 2.97)**; out-of-sample: **+$16.82/t (t 1.38)** — OOS not independently significant.
- Purged walk-forward (train 24mo → test 6mo, no overlap): stitched OOS +$13.05/t, but the segments **decay**: 2023-10 +$1.67, 2024-04 +$23.20, 2024-10 +$57.75, **2025-04 −$1.90, 2025-10 −$14.34**.

### Regime decay — the headline finding

| Volatility tercile (RTH range) | net $/trade | t-stat | trades |
|---|---|---|---|
| low-vol | **−$36.28** | **−9.00** | 237 |
| mid-vol | −$1.88 | −0.30 | 376 |
| high-vol | **+$60.08** | **+4.27** | 487 |

**The entire edge lives in high-volatility regimes, and the strategy actively loses (−$36/t, t −9) in low-vol.** Rolling 6-month net $/trade wanders −$17 → +$17 (min −$30). The "flat since May 2025" is really "negative in the low-vol regime in force since then."

### Parameter sensitivity, cost stress, blackout, significance

- **Parameter grid (27 cells, ±20%):** all positive (+$13.48 to +$18.27/t), a broad monotone plateau — not a curve-fit spike.
- **Cost stress (2× commission + 2× slippage):** +$16.14/t — survives.
- **News blackout ON:** removes 33% of trades (the 10:00/14:00 entries), remaining **+$20.10/t (t 2.32)** — blacking out the news-window entries actually *improves* per-trade expectancy.
- **Deflated significance:** momentum t = 2.69; P(best of 89 variants) ≈ 47%. **But momentum parameters are published (Zarattini et al. 2024), so no parameter-tuning penalty applies** — the honest penalty is only "selected from the prior 7 ideas," and the OOS t 1.38 is the independent ceiling.

## 6. Leaderboard (ranked by pass rate × funded survivability)

| Rank | Strategy | Pass rate (brief rules) | Zero-edge | Edge ratio | Verdict |
|---|---|---|---|---|---|
| **1** | **Intraday Momentum, 2 MNQ** | **28.0%** | 4.2% | 6.7× | Real but regime-dependent edge |
| 2 | Scalping, $500 risk | 13.4% | 5.4% | 2.5× | No edge (negative expectancy) |

---

*Charts written to `research/results/`: momentum_equity_dd.png, momentum_rolling_6m.png, momentum_vol_regime.png, passfail_distribution.png.*
