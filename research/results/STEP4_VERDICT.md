# Step 4 — Improve/Create (final) + Overall Verdict

**Date:** 2026-09-28 · all code in `research/`, outputs in `research/results/`

---

## 1. Lookahead correction (what Step 3 got wrong)

Step 3's "the edge dies in low-vol" used full-sample cut points (`pd.qcut` over 5 years)
— **lookahead**. Re-derived causally (expanding percentiles, prior data only), the finding
**reverses**:

| Regime | net $/trade (lookahead) | net $/trade (causal) |
|---|---|---|
| low-vol | −$36.28 (t −9.0) | **+$17.67 (t +2.56)** |
| mid-vol | −$1.88 | +$5.87 (t +0.54) |
| high-vol | +$60.08 (t +4.3) | +$30.94 (t +1.91) |

**The vol-dependence was an artifact.** Causally, the momentum strategy is positive in every
regime. Mechanism check: low-vol gross is **+$19.67** (cost only $2) — the "low-vol loss" was
never a cost effect, because it never existed. The real decay is **chronological**, not vol.

## 2. The real problem — the edge has decayed

- By year ($/contract): 2022 +$6,097 → 2023 +$4,433 → 2024 +$4,282 → 2025 +$3,423 → 2026 +$1,259.
- Purged walk-forward stitched OOS +$13.05/t, but the segments run **+$58 → −$2 → −$14**.
- **OOS pass rate (rolling starts, ≥ 2024-04-01): baseline 5.5% — versus 4.2% zero-edge.**
  On recent data the strategy is a coin flip.

## 3. Variant results (10 pre-registered, causal)

| Variant | trades | IS $/t | OOS $/t | WF OOS $/t | **Pass (full)** | **Pass (OOS)** |
|---|---|---|---|---|---|---|
| V0 baseline | 1100 | +19.35 (t 2.97) | +16.82 (t 1.38) | +13.05 | 28.0% | **5.5%** |
| V1 regime exp-67 | 415 | +22.29 | +30.87 | +38.78 | 14.4% | — |
| V2 regime trail-67 | 464 | +18.53 | +33.41 | +29.83 | 15.4% | — |
| V3 regime exp-50 | 612 | +26.63 | +16.16 | +15.14 | 13.3% | — |
| V4 regime exp-80 | 327 | +24.35 | +30.82 | +39.98 | 11.7% | — |
| V5 profit-lock | 1100 | =V0 | =V0 | =V0 | 28.0% | — |
| V6 soft-stop −$500 | 1100 | =V0 | =V0 | =V0 | 28.7% | — |
| V7 dd-aware sizing | 1100 | =V0 | =V0 | =V0 | **46.7%** | **2.9%** |
| V8 stand-down 3 | 1100 | =V0 | =V0 | =V0 | 31.8% | — |
| V9 combined | 415 | +22.29 | +30.87 | +38.78 | 20.3% | — |

**Regime filters raise $/trade but crash the pass rate** (they cut frequency, and frequency —
not expectancy — is what binds a $3k target under a $2k trailing DD). **V7 (size down near the
floor) is the only full-sample winner**, but its benefit is entirely in-sample.

## 4. EV — the honest number

`EV = pass_rate × 0.8 × target − $150/attempt`.

- **Full sample:** V7 = **+$971**, V0 = +$522 (V7 wins — but this is in-sample-inflated).
- **OOS:** V0 = **−$18**, V7 = **−$80**. **Negative expected value in both cases.**

Account tiers don't change the pass rate (the rules are scale-invariant); they only scale the
dollar EV. The dd-sizing threshold is monotone — higher threshold (≈always 1 MNQ) reaches 61.9%
full-sample — but that is the "size down to raise P(pass)" principle applied to a dead OOS edge.

## 5. Deflated significance

10 variants × 62 prior configs = 72. **No variant survives out-of-sample**, so there is no
deflated-significant winner to promote. V7's full-sample lift is not OOS-robust; the correct
conclusion is "no tradable edge out of sample."

## 6. Diversification

Not evaluated — the only two strategies in scope are the scalp (no edge) and the momentum
(decayed). There is no second positive strategy to combine.

---

# Verdict

**Do not trade the noise-area intraday momentum strategy — and do not trade the scalp.**

The momentum strategy had a real edge in 2021–2024 (reproduced here: +$18/t, t 2.69, both
sides positive, opposite-side control −$22/t). But the edge has chronologically decayed: on
out-of-sample data (2024-04 onward) it passes 5.5% of evals — a coin flip — and is negative
expected value after costs and fees. The "edge dies in low-vol" narrative was a lookahead
artifact; the truth is simpler and worse: **the edge is gone**.

**What would revive it:** a sustained return to a high-volatility regime *at a level comparable
to 2021–2024* (the strategy cannot be filtered to it causally — that's what this step proved).
**What would permanently kill it:** another 12 months flat-to-negative (already the case since
~mid-2025).

The genuinely useful outputs of this exercise are the reproducible harness (`research/`) — a
configurable prop-firm simulator, causal regime tools, and a Monte Carlo/EV framework — that
you can point at any future strategy. The strategy itself: not tradeable.
