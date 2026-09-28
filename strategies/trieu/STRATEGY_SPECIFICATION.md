# Strategy Specification: Trieu / Confluence Trading System (v6)

## 1. Strategy Overview

- **Strategy Name**: Confluence Trading System — Trieu Trades Method (v6)
- **Original Source File**: `strategies/trieu/Trieu_stra.txt` (Pine Script v6 Indicator)
- **Reference Manual**: `strategies/trieu/Trieu_Trading_System_PRINT.pdf`
- **Strategy Category**: Trend-Following / Moving Average Confluence & Mean-Reversion Rotation
- **Core Idea**: Capitalizes on moving average alignment and the rotational dynamic between fast and slow moving averages (specifically the 50 MA rotating toward the 200 MA, triggered by 9/21 and 9/50 EMA interactions).
- **Intended Market Conditions**: Trending and rotational intraday markets with clear directional structure; designed to stand down during low-separation chop (50/200 separation < 30 points) or overlapping supply/demand zones.

---

## 2. Inputs

The following configurable inputs are declared in `Trieu_stra.txt`:

| Input Name | Pine Identifier | Default Value | Allowed Values / Type | Purpose | Directly Affects Signals? |
|---|---|---|---|---|---|
| Palette | `theme` | `"Dark"` | `"Dark"`, `"Light"`, `"Custom"` | Visual color scheme | No |
| Show MA ladder | `showMA` | `true` | Boolean | Toggles rendering of moving averages | No |
| Show MA labels | `showLabels` | `true` | Boolean | Toggles end-of-chart MA value tags | No |
| Label offset | `labOffset` | `3` | Integer [1, 30] | Right offset for price tags | No |
| Min. 50↔200 separation to arm | `sepMin` | `30.0` | Float (min 0.1) | Separation threshold between 50 SMA and 200 SMA | **Yes (in Strict mode)** |
| Separation measured in | `sepMode` | `"Points"` | `"Points"`, `"ATR multiple"` | Unit for separation gate | **Yes (in Strict mode)** |
| ATR length | `atrLen` | `14` | Integer (min 1) | Lookback period for ATR when in ATR mode | **Yes (in Strict mode)** |
| SMA line width | `wSMA` | `3` | Integer [1, 6] | Visual line thickness | No |
| EMA line width | `wEMA` | `1` | Integer [1, 6] | Visual line thickness | No |
| Show VWAP | `showVwap` | `true` | Boolean | Toggles VWAP line | No |
| Show swing labels | `showSwing` | `false` | Boolean | Toggles HH/LH/HL/LL pivot labels | No |
| Swing pivot length | `swingLen` | `10` | Integer [2, 50] | Pivot high/low lookback window | No |
| Show balance grid | `showBal` | `true` | Boolean | Renders horizontal balance grid | No |
| Balance step | `balStep` | `30.0` | Float (min 0.25) | Distance between balance lines in points | No |
| Anchor mode | `balAnchorMode` | `"Manual"` | `"Manual"`, `"Auto"` | Anchor point calculation method | No |
| Manual anchor price | `balAnchorPrice` | `0.0` | Float (step 0.25) | Price anchor for balance grid | No |
| Lines above/below price | `balRange` | `6` | Integer [1, 15] | Number of grid lines drawn | No |
| Grid transparency | `balTrans` | `45` | Integer [0, 95] | Visual transparency | No |
| Show suggested anchor | `showAnchorSuggestion`| `true` | Boolean | Displays suggested anchor label | No |
| Candle colouring | `volMode` | `"All candles"` | `"Off"`, `"Dots only"`, `"High-volume candles"`, `"All candles"` | Volume-based bar color | No |
| Volume average length | `volLen` | `20` | Integer (min 1) | SMA length for average volume | **Yes (in Strict mode if `requireVol` is true)** |
| High-volume multiplier | `volMult` | `1.5` | Float (min 1.0, step 0.1)| Threshold multiplier for high volume | **Yes (in Strict mode if `requireVol` is true)** |
| Show entry/exit markers | `showSig` | `true` | Boolean | Visual display of entry/exit shapes | No |
| **Signal engine** | `signalEngine` | `"Original Signal"` | `"Original Signal"`, `"Strict 50→200"` | **Selects active entry engine** | **YES (Primary switch)** |
| Require high-vol confirmation | `requireVol` | `true` | Boolean | Requires volume > 1.5x average on Strict entries | **Yes (in Strict mode)** |
| Mark 100/200 touches | `showTrimTgt` | `true` | Boolean | Plots MA touch diamonds | No |
| Confirm signals on bar close | `confirmOnClose` | `true` | Boolean | Disallows intrabar firing | **YES** |
| Show condition table | `showTable` | `true` | Boolean | UI status dashboard | No |
| Table position | `tablePosIn` | `"Middle Right"` | Table positions | UI layout | No |
| Table text size | `tblSizeIn` | `"Small"` | Sizes | UI font | No |

---

## 3. Long Entry Logic

The strategy contains **two separate signal engines** selectable via `signalEngine`.

### Engine A: "Original Signal" (Default)
Matches the screenshot-style confluence:
```
cond921Long  = EMA(close, 9) > EMA(close, 21)
cond950Long  = EMA(close, 9) > EMA(close, 50)
condSmaLong  = close > SMA(close, 50)

originalLongState = cond921Long AND cond950Long AND condSmaLong

LONG SIGNAL (Original) = originalLongState AND NOT originalLongState[1]
                         AND confirmedBar
```
*In words*: A Long signal fires on the exact bar when all three directional conditions become simultaneously true, having not all been true on the immediately preceding bar.

### Engine B: "Strict 50→200"
Implements the setup from the manual (Setup A + Setup B):
```
crossUp    = ta.crossover(EMA(close, 9), EMA(close, 50))
separation = |SMA(close, 50) - SMA(close, 200)|
sepThresh  = sepMode == "ATR multiple" ? ATR(atrLen) * sepMin : sepMin
armed      = separation >= sepThresh

volAvg     = SMA(volume, volLen)
highVol    = volume > volAvg * volMult
volPass    = (NOT requireVol) OR highVol

LONG SIGNAL (Strict) = crossUp AND armed AND volPass AND confirmedBar
```
*In words*: A Long signal fires when the 9 EMA crosses over the 50 EMA, provided the 50 SMA and 200 SMA are separated by at least `sepMin` (default 30 points), and (if `requireVol` is active) the candle volume exceeds 1.5x its 20-period SMA.

---

## 4. Short Entry Logic

### Engine A: "Original Signal" (Default)
```
cond921Short = EMA(close, 9) < EMA(close, 21)
cond950Short = EMA(close, 9) < EMA(close, 50)
condSmaShort = close < SMA(close, 50)

originalShortState = cond921Short AND cond950Short AND condSmaShort

SHORT SIGNAL (Original) = originalShortState AND NOT originalShortState[1]
                          AND confirmedBar
```
*In words*: A Short signal fires on the exact bar when all three bearish conditions become simultaneously true, having not all been true on the immediately preceding bar.

### Engine B: "Strict 50→200"
```
crossDown  = ta.crossunder(EMA(close, 9), EMA(close, 50))
separation = |SMA(close, 50) - SMA(close, 200)|
sepThresh  = sepMode == "ATR multiple" ? ATR(atrLen) * sepMin : sepMin
armed      = separation >= sepThresh

volAvg     = SMA(volume, volLen)
highVol    = volume > volAvg * volMult
volPass    = (NOT requireVol) OR highVol

SHORT SIGNAL (Strict) = crossDown AND armed AND volPass AND confirmedBar
```
*In words*: A Short signal fires when the 9 EMA crosses under the 50 EMA, provided the 50 SMA and 200 SMA are separated by at least `sepMin` (default 30 points), and (if `requireVol` is active) the candle volume exceeds 1.5x its 20-period SMA.

---

## 5. Signal Confirmation

- **Execution Timing**: Governed by `confirmOnClose = input.bool(true, ...)`:
  ```pinescript
  confirmedBar = not confirmOnClose or barstate.isconfirmed
  longSignal   = engineLong and confirmedBar
  shortSignal  = engineShort and confirmedBar
  ```
- **Evaluation**: On historical bars, `barstate.isconfirmed` is always `true`. In live/backtesting execution, signals become valid **strictly at candle close** (the final tick of the 1-minute bar).
- **Subsequent Action**: Orders are evaluated for execution at the open of the bar immediately following the signal bar (or filled at signal bar close depending on backtesting engine execution convention).

---

## 6. Indicator Calculations

All indicators are calculated on `close` (or `volume`):

1. **9 EMA**:
   $$\text{EMA}_9(t) = \alpha \cdot \text{close}_t + (1 - \alpha) \cdot \text{EMA}_9(t-1), \quad \alpha = \frac{2}{9 + 1} = 0.2$$
2. **21 EMA**:
   $$\text{EMA}_{21}(t) = \alpha \cdot \text{close}_t + (1 - \alpha) \cdot \text{EMA}_{21}(t-1), \quad \alpha = \frac{2}{21 + 1} = \frac{2}{22}$$
3. **50 EMA**:
   $$\text{EMA}_{50}(t) = \alpha \cdot \text{close}_t + (1 - \alpha) \cdot \text{EMA}_{50}(t-1), \quad \alpha = \frac{2}{50 + 1} = \frac{2}{51}$$
4. **50 SMA**:
   $$\text{SMA}_{50}(t) = \frac{1}{50} \sum_{i=0}^{49} \text{close}_{t-i}$$
5. **100 SMA**:
   $$\text{SMA}_{100}(t) = \frac{1}{100} \sum_{i=0}^{99} \text{close}_{t-i}$$
6. **200 SMA**:
   $$\text{SMA}_{200}(t) = \frac{1}{200} \sum_{i=0}^{199} \text{close}_{t-i}$$
7. **Volume 20 SMA**:
   $$\text{volAvg}_{20}(t) = \frac{1}{20} \sum_{i=0}^{19} \text{volume}_{t-i}$$
8. **High-Volume Condition**:
   $$\text{highVol}_t = \text{volume}_t > 1.5 \times \text{volAvg}_{20}(t)$$
9. **ATR (14)** (Only used if `sepMode == "ATR multiple"`):
   $$\text{TR}_t = \max(\text{high}_t - \text{low}_t, |\text{high}_t - \text{close}_{t-1}|, |\text{low}_t - \text{close}_{t-1}|)$$
   $$\text{ATR}_{14}(t) = \text{RMA}_{14}(\text{TR}_t)$$
10. **Separation**:
    $$\text{separation}_t = |\text{SMA}_{50}(t) - \text{SMA}_{200}(t)|$$

---

## 7. Filters

### Required Filters:
- **For Original Signal Engine**:
  - None beyond the 3 simultaneous alignment conditions (`9 EMA > 21 EMA`, `9 EMA > 50 EMA`, `close > 50 SMA`).
- **For Strict 50→200 Engine**:
  - **Separation Gate (`armed`)**: Separation between 50 SMA and 200 SMA must be $\ge 30$ points (or $30 \times \text{ATR}_{14}$).
  - **Volume Filter (`highVol`)**: When `requireVol = true` (default), volume must exceed $1.5 \times \text{SMA}_{20}(\text{volume})$.

### Optional Filters / Visuals:
- **VWAP**: Intraday session VWAP plotted for manual visual reference; does not gate signals programmatically.
- **Balance Grid**: 30-point spaced grid; visual reference only.
- **Swing Structure**: 10-bar pivot highs/lows for visual labeling only.
- **Shoulder Tap**: $9/21$ EMA crossover alert (`tapUp`/`tapDown`), visual and alert only ("prepare, do not enter").

---

## 8. Invalidations

- **State Transition Invalidation**: If the indicator is waiting in state, an entry only fires on the exact rising edge (`state and not state[1]`). If the condition is broken before execution, no signal fires.
- **Position Flip Invalidation**:
  - If already Long (`positionState == 1`), new Long signals are ignored until position is flattened or flipped by a Short signal.
  - If already Short (`positionState == -1`), new Short signals are ignored until flattened or flipped.

---

## 9. Stop Loss Logic

**NO NATIVE STOP LOSS DEFINED** in the Pine Script code — external testing framework must provide risk model.

*Forensic Note from Source & PDF*:
- In `Trieu_stra.txt`, there is no `strategy.exit` or stop price variable calculated for risk termination.
- In `Trieu_Trading_System_PRINT.pdf` (Part Five: Execution & Risk), the manual states: *"Just beyond the prior swing high or low — a little past the wick, never exactly on it. A working reference is roughly $300 of risk on one contract."*
- Because this is discretionary in the script, for systematic backtesting, a quantitative swing-pivot stop (e.g. `ta.pivotlow(low, 10, 10)`) or fixed point stop ($300 = 150$ MNQ points / $15$ NQ points) must be explicitly parameterized in Phase 2.

---

## 10. Take Profit Logic

### Script-Defined Exits:
1. **Trailing Trend Exit (9 EMA Cross)**:
   - Position state transitions:
     ```pinescript
     exitLong  = positionState == 1  and ta.crossunder(close, ema9) and confirmedBar
     exitShort = positionState == -1 and ta.crossover(close, ema9)  and confirmedBar
     ```
   - When active, a Long trade exits when a candle closes below the 9 EMA. A Short trade exits when a candle closes above the 9 EMA.
2. **Trim / Target Touches (Alerts & Shapes Only)**:
   - `touched100 = ta.cross(close, sma100)` (100 MA touch — Trim level)
   - `touched200 = ta.cross(close, sma200)` (200 MA touch — Target level)
   - *Note*: In the Pine script, these plot diamond markers and emit alerts, but do **not** flatten `positionState` automatically.

---

## 11. Timeframe

- **Intended Timeframe**: 1-minute chart (1m) as specified in the manual, with 3m/5m mentioned as alternate scalping views.
- **Multi-Timeframe Logic**: None in script. Operates directly on the chart's current resolution.
- **VWAP Reset**: Requires intraday session data (`timeframe.isintraday`).

---

## 12. Repainting / Lookahead Audit

- **Classification**: **NON-REPAINTING**
- **Analysis**:
  - No `request.security()` calls exist.
  - No negative index lookaheads (`close[-1]`) exist.
  - `confirmOnClose = true` ensures signals are evaluated strictly at the completion of each bar.
  - The pivot calculation (`ta.pivothigh(10, 10)`) is delayed by 10 bars and is used strictly for chart labels, having zero influence on signal calculations.

---

## 13. Python Implementation Requirements

To reproduce Trieu signals on `MNQ_1m_continuous.parquet`:
1. **Indicator Vectorization**:
   - Compute EMA(9), EMA(21), EMA(50) using standard exponential smoothing ($\alpha = 2/(N+1)$).
   - Compute SMA(50), SMA(100), SMA(200) using rolling means.
   - Compute Volume SMA(20).
2. **Dual Engine Flags**:
   - Create two distinct signal columns: `trieu_orig_signal` and `trieu_strict_signal`.
3. **State Machine for Exits**:
   - Track `position_state` iteratively to reproduce the 9 EMA trailing crossunder/crossover exit.

---

## 14. AMBIGUITIES / DECISIONS REQUIRED

1. **Dual Signal Engine Separation**:
   - *Decision*: Treat "Original Signal" and "Strict 50→200" as **two separate strategy variants** during backtesting (`Trieu_Original` and `Trieu_Strict`). They have completely different triggers (state-alignment vs 9/50 crossover with 50/200 separation).
2. **Stop Loss Model for Backtesting**:
   - The script has zero stop loss logic. Phase 2 must define whether to test:
     - (a) A fixed dollar stop (e.g. $150 / $300),
     - (b) A swing-pivot stop (e.g. lowest low of last $N$ bars), or
     - (c) ATR-based stop.
3. **Profit Target Execution**:
   - In Pine Script, touching 100 SMA and 200 SMA is an alert/marker only. For the backtester, we must specify whether to:
     - (a) Exit 50% at 100 SMA and 50% at 200 SMA, or
     - (b) Exit 100% at 200 SMA, or
     - (c) Only use the 9 EMA trail exit.
