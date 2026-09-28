# Trieu Confluence System — Forensic Notes & Insights

## Source Files Analyzed
1. `strategies/trieu/Trieu_stra.txt` (470 lines of Pine Script v6)
2. `strategies/trieu/Trieu_Trading_System_PRINT.pdf` (20 pages of system rules and manual discretionary execution guidance)

---

## 1. The Dual Engine Disconnect

In the Pine Script (`Trieu_stra.txt`), lines 6-8 state:
> Dual signal engines:
> 1) Original Signal — 9/21 + 9/50 + price vs 50 SMA alignment
> 2) Strict 50→200 — 9/50 cross + 50/200 separation + optional volume

### Engine 1: "Original Signal"
- **Implementation**: Lines 300-303
  ```pinescript
  originalLongState  = cond921Long and cond950Long and condSmaLong
  originalShortState = cond921Short and cond950Short and condSmaShort
  originalLong  = originalLongState and not originalLongState[1]
  originalShort = originalShortState and not originalShortState[1]
  ```
- **Nature**: Trend alignment state transition.
- **Frequency**: Relatively frequent. Fires whenever moving averages align in sequence ($9 > 21 > 50$) and price is on the correct side of the 50 SMA.
- **Crucial Note**: The 50/200 separation gate (`armed`) is **completely bypassed** in this engine.

### Engine 2: "Strict 50→200"
- **Implementation**: Lines 307-308
  ```pinescript
  strictLong  = crossUp   and armed and (not requireVol or highVol)
  strictShort = crossDown and armed and (not requireVol or highVol)
  ```
- **Nature**: Crossover event with structural volatility gating.
- **Frequency**: Low frequency. Requires:
  1. EMA 9 crossing EMA 50 (`ta.crossover(ema9, ema50)`),
  2. Absolute difference between SMA 50 and SMA 200 $\ge 30$ points,
  3. Bar volume $> 1.5\times$ 20 SMA of volume.

### Strategic Recommendation
Treat them as **two independent strategies** in Python:
- `Trieu_Original`
- `Trieu_Strict`

---

## 2. Risk Management Forensics

### Stop Loss
- The Pine script **omits stop loss entirely**.
- The PDF Manual (Page 15, "Execution & Risk") states:
  > *"Structure sets the stop; the stop sets the minimum acceptable target.*
  > *Stop Placement: Just beyond the prior swing high or low — a little past the wick, never exactly on it.*
  > *Dollar Ceiling: A working reference is roughly $300 of risk on one contract."*
- Systematic formulation: To test this objectively in Phase 2, we should test:
  1. Swing High/Low (last $N$ bars lowest low / highest high),
  2. Fixed point stop (e.g. 15 points = $300 on NQ, 150 points on MNQ, or dollar risk ceiling).

### Exit & Trailing Logic
- The Pine script defines a trail exit on 9 EMA cross (Lines 326-327):
  ```pinescript
  exitLong  = positionState == 1 and ta.crossunder(close, ema9) and confirmedBar
  exitShort = positionState == -1 and ta.crossover(close, ema9) and confirmedBar
  ```
- The PDF manual (Page 16, "The Trailing Ladder") explains:
  - Default: Trail behind 9 EMA. Exit the moment a candle closes through it.
  - Trim at 100 SMA, target at 200 SMA.

---

## 3. Visual / Discretionary Features That Do Not Affect Systematic Signals

The following elements exist in the script for trader psychology or visual reference, but have **zero impact on programmatic signals**:
- **Balance Grid** (`balLines`, `balanceAnchor`): Draws static horizontal lines spaced by 30 points.
- **VWAP**: Plotted on chart; not included in entry/exit boolean expressions.
- **Swing Structure Labels** (`ta.pivothigh`, `ta.pivotlow`): Generates "HH", "LH", "HL", "LL" labels; purely visual.
- **Shoulder Tap** (`ta.crossover(ema9, ema21)`): Alert / circle marker for preparation; not an entry.
