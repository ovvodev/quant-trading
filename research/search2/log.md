# Search 2 log

## 2026-09-28 — registration and split setup
- Read the attached protocol and existing `research/` harness/config before work.
- Confirmed MNQ parquet exists and Python has pandas 2.3.3 / pyarrow 21.0.0.
- Existing reports explicitly close Bollinger scalp and noise-area momentum; do not resurrect. Existing project material shows overlapping prior tests of several sourced strategies, so evidence is contaminated; inherited trial count remains 72.
- Candidate mechanisms and splits were registered in `plan.md` before any new candidate run.
- Ran `create_splits.py` successfully. Source coverage: 2021-09-23 00:00 to 2026-09-22 23:59 UTC. Dev 980,772 bars, validation 413,487 bars, sealed final 376,020 bars. Hashes recorded in `splits/manifest.json`; sealed checksum repeated in `data/holdout_sealed/SEALED.json`.
- Sealed final is isolated at `data/holdout_sealed/final.parquet`; setup checked its checksum. No trade outcomes or strategy results on that split were loaded or calculated. `final_holdout.py` requires a validation gate and globally consumes an atomic lock before any possible read.
- Source inventory across Bot_v2/custom bot v3 confirms overlap for Momentum Sequence, Confluence, Morning Exhaustion, and AW liquidity reversal; reports contain prior OOS use and/or competing execution definitions. No family is currently eligible for a fresh Search 2 run without a materially distinct, pre-registered mechanism.
- No backtests run. Current decision: stop before candidate testing rather than consume trials under contaminated labels. Any future restart needs a distinct hypothesis permitted by the brief and must still use dev only.
