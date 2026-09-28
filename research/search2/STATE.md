# Search 2 state

- Status: immutable splits created and sealed; source inventory finds all named/source families already investigated on overlapping data. No candidate backtest executed; no fresh candidate yet justified.
- Current phase: halted at source-triage gate; no unambiguously novel, uncontaminated candidate identified.
- Current family / iteration: none / 0.
- Trials used in this search: 0 / 120 (inherited prior trials: 72).
- Validation candidates used: 0 / 3.
- Split artifacts verified: dev 980,772 rows (2021-09-23..2024-06-30), validation 413,487 (2024-07-01..2025-08-31), sealed final 376,020 (2025-09-01..2026-09-22). Source checksum and sealed-file checksum recorded in manifest.
- Holdout: sealed file must only be loaded via final_holdout.py; do not evaluate it unless a sole validated candidate passes criteria 1–7. No holdout performance inspection has occurred.
- Next: complete candidate source inventory; pre-register exact executable rules and integrity protocol; then development-only test.
- Assumption: UTC timestamps and stated coverage were checked against source. Date boundaries use exclusive next-day cutoffs to preserve inclusive calendar-date splits.
