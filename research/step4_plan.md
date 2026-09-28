# Step 4 — Pre-registration (frozen before any run)

**Date:** 2026-09-28
**Method note:** All filters below are CAUSAL — realised-vol and thresholds are
computed only from data available strictly BEFORE the entry bar. No full-sample
cut points. Thresholds fitted on in-sample (before 2024-04-01) only, applied
frozen to out-of-sample.

**Lookahead correction (Step 3):** Step 3's vol-tercile table used `pd.qcut` over
the full 5-year range → full-sample cut points = lookahead. This is re-derived
causally in this step and the change is reported.

---

## Variants (10 total, frozen — no additions)

Strategy = noise-area intraday momentum (published params), 2 MNQ unless a sizing
variant says otherwise. Cost = $0.50/side + 1 tick. Brief prop rules unless noted.

**V0 — Baseline.** Unfiltered momentum, 2 MNQ.
Hypothesis: the reference point (net +$18/t, 28% rolling pass rate).

**V1 — Regime filter, expanding 67th percentile.**
Trade only when causal RV ≥ expanding 67th pct of RV history.
Hypothesis: removes low-vol loser days (−$36/t in Step 3), lifts net $/trade and pass rate.

**V2 — Regime filter, trailing 250-day 67th percentile.**
Same filter, threshold from a trailing 250-day window.
Hypothesis: more stable threshold; similar or better than V1.

**V3 — Regime filter, expanding 50th percentile (median).**
Trade above-median vol.
Hypothesis: milder filter, keeps more trades (frequency matters for pass speed).

**V4 — Regime filter, expanding 80th percentile.**
Trade top-quintile vol.
Hypothesis: most selective; highest $/trade but may fall under the ~200-trade minimum.

**V5 — Daily profit lock +$1,000 (2 MNQ).**
Stop entering for the day once day P&L ≥ +$1,000.
Hypothesis: locks daily gains, reduces give-back and daily-loss fails.

**V6 — Daily soft stop −$500.**
Stand down for the day after −$500 realized (softer than the $1,000 hard fail).
Hypothesis: cuts tail days before they reach the $1,000 daily-loss breach.

**V7 — Drawdown-aware sizing.**
2 MNQ while trailing buffer > $1,500, else 1 MNQ (floor; cannot go below 1).
Hypothesis: reduces drawdown fails near the floor; slower but safer.

**V8 — Stand-down after 3 consecutive losing days.**
Skip entries until a winning day after 3 straight losing days.
Hypothesis: shortens losing streaks that drain the trailing buffer.

**V9 — Combined.** V1 (regime) + V5 (profit lock) + V7 (sizing).
Hypothesis: individually-best levers stack.

---

## Causal regime definition (shared by V1–V4)

- `RV[D]` = trailing 20-trading-day **median** of the RTH session high−low range
  (points), computed from sessions strictly before D.
- Thresholds are percentiles of the RV series **up to D** (expanding) or over the
  trailing 250 days (V2). Warmup: first ~40 sessions unfiltered (insufficient RV).

## Mechanism check (analysis, not a variant)

- Cost as a fraction of band width (`sigma · open`) by regime — does friction
  explain the low-vol loss, or is it the signal itself?

## Account fit (sweep on the best variant, not a variant)

- (a) $50k / $2k intraday trailing, (b) $100k and $150k tiers (scaled target &
  DD), (c) EOD-trailing rule set.
- Report pass rate, median days-to-pass, post-pass 30/60/90-day survival.
- **EV per attempt** = pass_rate × payout_share × target − fee; `payout_share=0.8`,
  `fee=$150` (config inputs). Rank by EV.

## Reporting requirements (per variant)

- IS, OOS, walk-forward, trade count, and a ~200-trade-minimum flag.
- Block-bootstrap CIs on regime t-stats; high-vol edge with top-3 profit months removed.
- Deflated significance on the final winner (prior 62 configs + these 10 variants).
