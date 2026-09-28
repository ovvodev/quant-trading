# Search 2 — preregistration and mechanisms

**Registered:** 2026-09-28. No candidate backtest has been run in this workspace at registration.
**Source data:** `data/MNQ_1m_continuous_v2.parquet`; source read-only. Price rolls use `research.common.back_adjust(..., "difference")`; roll bars must not be treated as market moves.
**Costs/rules:** frozen to `research/prop_config.json` `generic_50k`: $0.50/side commission, 1 tick per market fill, MNQ $2/point, $0.25 tick; 5-contract cap; $50k/$3k/$2k; intraday trailing DD, $1k daily-loss fail, 40% consistency, flat 16:45 ET; $150 attempt fee. No modifications to earlier research or config.

## Immutable splits
- Development: 2021-09-23 through 2024-06-30 inclusive.
- Validation: 2024-07-01 through 2025-08-31 inclusive; a candidate gets one evaluation only.
- Sealed final: 2025-09-01 through 2026-09-22 inclusive. Stored at `data/holdout_sealed/`; never loaded except through `final_holdout.py`, which atomically locks and logs its single allowed use. Do not run final unless exactly one candidate independently passes criteria 1–7 on dev+validation. If it fails, stop.

`create_splits.py` wrote analysis splits and sealed final, checksums, and manifest before any candidate run. This is setup only, not performance evaluation. Verified ranges/row counts: dev 980,772 bars; validation 413,487; sealed final 376,020. Source spans 2021-09-23 00:00 UTC to 2026-09-22 23:59 UTC. Holdout hash is in `data/holdout_sealed/SEALED.json` and checksum-verified; no holdout performance outcomes have been inspected.

## Frozen success criteria and limits
The user's posted criteria are unchanged: (1) at least 300 trades on dev + validation, (2) expectancy positive at 2x costs and day-block bootstrap 95% CI lower bound >0 on combined dev+validation, (3) positive after dropping top 3 months with month <=25% and day <=30% total profit, (4) positive in >=4/5 calendar years or >=60% of six-month segments, (5) every +/-20% parameter neighbor net positive on development, (6) multiple-testing adjusted p<0.10 with N including 72 inherited trials, (7) prop simulator pass-rate >=3x zero-edge, median pass <=45 trading days, EV after $150 attempt fee >0, and (8) one sealed final run with positive expectancy at 1.5x costs, pass-rate above zero-edge, and max DD <=1.5x dev+validation. Budget: <=120 configs overall, <=8/family, <=3 validation candidates; no criterion change.

## Fixed criteria and trial budget
The attached brief's success criteria and limits are binding, including 120 total configurations, 8 iterations/family, prior 72 trials included in multiple-testing adjustment, no more than 3 validation candidates, one final candidate at most, and no relaxation. Full criterion text remains in the user-provided prompt. All failed runs must enter the ledger. Only development is available for exploration/tuning; validation is one-shot per candidate; final is one-shot globally.

## Existing-work inventory and contamination
- Existing `research/results/STEP4_VERDICT.md` explicitly closes the Bollinger scalp and noise-area momentum strategy; do not resurrect them. It reports OOS pass-rate decay for the latter.
- `/Users/kostas/Documents/Bot_v2/PHASE_4_RESULTS.md` reports extensive Momentum Sequence stop/target tests: native anchor stop failed OOS (PF 0.977), while a chosen 50-point/2R candidate is reported positive. Treat this family as contaminated; do not retest as fresh discovery absent a genuinely distinct preregistered mechanism.
- `/Users/kostas/Documents/custom bot v3/FINDINGS.md` reports multiple overlapping registrations including Trieu Confluence, intraday momentum, and many indicator families; OOS windows have already been used. Its summary says none survived its own OOS protocol. Treat as contaminated, not new evidence.
- `custom bot v3/PROJECT_MAP.md` identifies Morning Exhaustion Pine and AW liquidity reversal source. Morning's prior report describes only 12 validation and 12 final trades; the period overlaps this project’s dates, so do not claim fresh OOS confirmation. AW source contains two execution models: a signal-close Strategy Tester bridge and a theoretical FVG tracker. Do not test unless one authoritative path is identified without discretionary choice.
- Trieu Confluence source exists, but prior `FINDINGS.md` reports negative/weak results; no label-change rerun.
- Prior reports and source files are historical evidence only; they do not satisfy this protocol's event-level verification.

## Candidate-family mechanism hypotheses (maximum 8; options to triage, not automatic trial authorization)
Each mechanism must be written as an exact standalone plan before any test. Do not use the sealed period to validate previous work or decide candidate eligibility.
1. **Momentum Sequence continuation (sourced port).** Consecutive directional closes after an opposing anchor might encode short-term persistence. Heavily contaminated by prior parameter searches; closed absent an independently justified distinct hypothesis. 1m OHLCV measures candle persistence, not true order flow.
2. **AW liquidity-reversal (sourced port).** Sweep → neckline displacement → FVG retrace might capture failed auction reversal. Exclude unless source execution path and intrabar semantics are uniquely resolved; 1m OHLCV cannot test absorption/delta.
3. **Morning Exhaustion (sourced port).** Opening impulse exhaustion followed by reversal might mean-revert. Existing small samples overlap the target time span; no final-split use to claim confirmation.
4. **Trieu Confluence System (sourced port).** Trend alignment might condition continuation; prior tests are weak/negative and overlap in time. Closed unless a distinct mechanism is established before testing.
5. **NY opening-range breakout.** Acceptance beyond opening range might capture price discovery; prior broad walk-forward failed, so closed absent a materially distinct mechanism.
6. **Overnight range → NY expansion.** Overnight balance might store energy for regular-session expansion. Prior work examined related overnight/session ideas; any distinct candidate requires precise registration first.
7. **VWAP exhaustion reversion.** Stretched price returning toward session VWAP might mean-revert. Overlap with the closed scalp/prior tests must be checked before any dev trial.
8. **Compression → expansion.** Causal intraday compression might precede directional expansion. Prior pattern tests make evidence contaminated; only a materially distinct, precisely registered rule could be screened.

## Trial S2-001 pre-registration — overnight range breakout, development only
**Mechanism:** overnight balance can store energy; acceptance beyond its extrema during NY regular hours may initiate expansion. This is a specific candidate from family 6, not an assertion of a novel/pristine discovery. Historical overlaps are counted in the inherited 72 trials.

**Rules frozen before run:**
- Use difference-adjusted MNQ OHLC; exclude any ET trade date containing a contract-symbol transition, and never treat roll bars as price moves.
- ET calendar trade date D overnight range = high/low of bars timestamped from 18:00 on D−1 through 09:29 on D inclusive. Require at least 600 valid overnight minute bars and finite bounds. RTH session must have at least 300 bars between 09:30 and 16:43 ET and every adjacent RTH timestamp exactly one minute apart; otherwise exclude the whole date uniformly from candidate and controls. These are data-integrity exclusions, not a strategy filter.
- Observe 09:30–16:44 ET bars. First bar whose close is strictly above overnight high signals long; strictly below overnight low signals short. On simultaneous impossible conditions, skip. One opportunity per date.
- Fill market at next bar open plus one adverse tick. If no next bar exists, no trade. Require structural stop distance >=2.0 points: long stop = overnight low, short stop = overnight high.
- Stop is active from the entry bar, adverse one tick; if that bar opens through stop, fill at the worse of stop and open plus adverse tick. Otherwise stop on first bar whose low/high touches stop. If no stop, exit at the close of the 16:44 ET bar (by 16:45) with adverse one tick. No profit target, no re-entry, no scaling.
- Baseline cost is $0.50 per side commission plus one tick adverse slippage each market fill, MNQ $2/point; one contract for diagnostics. Also calculate 2x cost sensitivity. The prop simulator may use its existing size controls only if this rule passes the development kill gate.
- Exact same signal dates/times for one-bar-delay integrity test; delay fill to open after an additional completed minute and skip if unavailable. Random-entry control: seeded random entry minute within 09:30–16:44 on each candidate date, same direction sampled from candidate-day direction frequencies, same stop distance as original, same exit/flat rule. Opposite-side control flips direction at the original entry time and mirrors stop distance.
- A single configuration only; no tuning. Run development only. Kill if net $/trade at 2x costs or Newey-West t-stat is <0 / <1.5 respectively. If retained, diagnostics must precede any one-change iteration.

**Reproducibility:** `trial_s2_001.py` loads only `splits/development.parquet`, produces event CSV + JSON summary and records `rules_hash`; seeded controls. No validation or final access in this script.

No further family is selected until this trial's kill-gate report is complete. If it dies, stop unless a genuinely distinct family hypothesis has a written mechanism and exact rules registered first.

## Fixed execution / integrity protocol
- Signals confirmed on bar close; market fills at next bar open plus adverse slippage; resting limits only if traded through by one tick. Stops get adverse slippage. Roll bars are excluded from signal generation/outcomes.
- Before any run, log exact operational rules, mechanism, source fidelity/uncertainties and one-script reproducibility path. Candidate code is only in this folder.
- Every development configuration is logged. Failures are retained.
- Validation is at most once per candidate and never tuned against. A final evaluation is only through `final_holdout.py`, exactly once globally.
- Stop if no family can be implemented faithfully, artifacts/data are missing, integrity checks fail, or the trial budget is exhausted. A negative outcome is acceptable; no criteria are relaxed.

## Integrity / inherited evidence
The prior project reports already searched many related MNQ families on overlapping data. The stated earlier trial count is 72 and is included in any multiple-testing adjustment. Existing results are not re-used as fresh evidence and no new performance claim will be made without running this new protocol. A report asserting a candidate survives does not replace event-level verification.

## Candidate mechanisms (triage only)
Other options in the initial scope include Momentum Sequence, AW liquidity reversal, Morning Exhaustion, Trieu Confluence, NY opening range, VWAP exhaustion, and compression-expansion. These remain closed pending distinct pre-registration; do not conflate them with S2-001 or use final-period data.

## Deliverables
Keep all Search 2 scripts, reports, event outputs and plots under this folder. `ledger.csv`, `STATE.md`, and `log.md` must be updated after every trial/family milestone; include failures. If nothing passes, give a per-family criterion failure matrix and clear negative verdict. Do not loosen any fixed criterion.

**No trial has been executed yet.**

## Execution and integrity protocol
- Signals confirmed on bar close; market fills at next bar open plus adverse slippage; resting limits only if traded through by one tick. Stops get adverse slippage. Roll bars are excluded from signal generation/outcomes.
- Before any run, log exact operational rules, mechanism, source fidelity/uncertainties and one-script reproducibility path. Candidate code is only in this folder.
- Required diagnostics per development candidate: base and 2x costs, NW t-stat, time-of-day expectancy, MAE/MFE, trade count, random-entry and opposite-side controls, extra-bar delay integrity probe, year/6-month slices, month/day/top-3-month concentration, parameter plateau, and prop simulator. Never use full-sample percentiles or any future information.
- Integrity: random/opposite controls must be worse; extra-bar delay must not improve; PF >2.5 or WR >75% is assumed bug pending investigation.
- Freeze exact candidate/hash before validation; validation once only. If candidate passes 1–7 and is sole best, final only via `final_holdout.py`.

## Split/access artifacts and deliverables
- `create_splits.py`; analysis files in `splits/`; hashes/rows/ranges in `splits/manifest.json`.
- `final_holdout.py` is intended as sole final loader. Its global atomic lock is consumed before any read attempt, including failure; it requires a validation gate and writes an access log. Never manually inspect sealed Parquet.
- `ledger.csv`, `STATE.md`, and `log.md` must be updated after every trial/family milestone; keep scripts, reports, events and charts in `research/search2/`.
- If nothing passes, provide a per-family criterion failure matrix and clear negative verdict. Do not loosen any fixed criterion.
