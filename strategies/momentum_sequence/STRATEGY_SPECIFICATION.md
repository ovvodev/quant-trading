# Strategy Specification: Momentum Sequence Strategy+ [Herman]

## 1. Strategy Overview

- **Strategy Name**: Momentum Sequence Strategy+ [Herman]
- **Original Source File**: `strategies/momentum_sequence/Momentum Sequence Strategy+ [Herman]  .txt` (Pine Script v6 Strategy)
- **Strategy Category**: Candlestick Sequence Momentum / Exhaustion-Reversal
- **Core Idea**: Identifies a multi-bar momentum run immediately following an anchor candle of opposite polarity. For a Long setup: an initial bearish "main candle" is followed by a sequence of $N$ consecutive bullish candles, each closing higher than the previous, while price never breaches the low of the initial bearish main candle. The opposite logic defines a Short setup.
- **Intended Market Conditions**: Strongly trending or momentum continuation conditions where persistent candle sequences indicate directional buyer/seller control.

---

## 2. Inputs

The following configurable inputs are declared in the strategy:

| Input Name | Pine Identifier | Default Value | Allowed Values / Type | Purpose | Directly Affects Signals? |
|---|---|---|---|---|---|
| Following Candles | `followingCandles` | `5` | Integer options: `[2, 3, 4, 5]` | Number of consecutive candles required after the main candle | **YES (Core parameter)** |
| Take Profit | `takeProfitR` | `"1.5R"` | String options: `["0.5R", "1R", "1.5R", "2R"]` | R-multiple target based on initial risk | **YES (Exits)** |
| Long Trades | `enableLongTrades` | `true` | Boolean | Enables/disables Long trade entries | **YES** |
| Short Trades | `enableShortTrades`| `false` | Boolean | Enables/disables Short trade entries | **YES** |
| Show Entry Signal | `showSignal` | `true` | Boolean | Displays entry triangles on chart | No |
| Show Stop Loss / Take Profit | `showSLTP` | `true` | Boolean | Plots SL and TP horizontal price lines | No |
| Show Table | `showTable` | `true` | Boolean | Renders statistics table | No |
| Theme | `tableTheme` | `"Light"` | `"Dark"`, `"Light"` | Table color palette | No |
| Size | `tableSize` | `"small"` | `"tiny"`, `"small"`, `"normal"`, `"large"` | Table font size | No |
| Position | `tablePos` | `top_right`| Four corner positions | Table screen placement | No |

---

## 3. Long Entry Logic

A Long setup occurs when an initial **bearish main candle** is followed by $N$ consecutive **bullish candles** adhering strictly to three geometric rules:

### Rule 1: Main Candle Definition
The candle located `followingCandles` bars in the past must be strictly bearish:
```
mainBearish = close[followingCandles] < open[followingCandles]
```

### Rule 2: Consecutive Following Bullish Candles
For each candle $i$ in the range $i = 0$ to $\text{followingCandles} - 1$ (where $i = 0$ is the current forming/closing candle, and $i = \text{followingCandles} - 1$ is the first candle immediately after the main candle):
1. **Bullish Body**:
   $$\text{close}[i] > \text{open}[i]$$
   *(If $\text{close}[i] \le \text{open}[i]$, the sequence is INVALID).*
2. **Floor Constraint (Low above Main Candle Low)**:
   $$\text{low}[i] > \text{low}[\text{followingCandles}]$$
   *(If $\text{low}[i] \le \text{low}[\text{followingCandles}]$, the sequence is INVALID).*
3. **Monotonically Higher Closes**:
   For $i < \text{followingCandles} - 1$:
   $$\text{close}[i] > \text{close}[i + 1]$$
   *(Newer candle close must be strictly greater than previous candle close. If $\text{close}[i] \le \text{close}[i + 1]$, the sequence is INVALID).*

### Rule 3: Execution Condition
```
longSetup = mainBearish AND validBullishSequence

LONG ENTRY = enableLongTrades 
         AND longSetup 
         AND (strategy.position_size == 0)
```
*(Pyramiding is disabled: an entry only occurs if the strategy is currently flat).*

---

## 4. Short Entry Logic

### Rule 1: Main Candle Definition
The candle located `followingCandles` bars in the past must be strictly bullish:
```
mainBullish = close[followingCandles] > open[followingCandles]
```

### Rule 2: Consecutive Following Bearish Candles
For each candle $i$ in the range $i = 0$ to $\text{followingCandles} - 1$:
1. **Bearish Body**:
   $$\text{close}[i] < \text{open}[i]$$
   *(If $\text{close}[i] \ge \text{open}[i]$, the sequence is INVALID).*
2. **Ceiling Constraint (High below Main Candle High)**:
   $$\text{high}[i] < \text{high}[\text{followingCandles}]$$
   *(If $\text{high}[i] \ge \text{high}[\text{followingCandles}]$, the sequence is INVALID).*
3. **Monotonically Lower Closes**:
   For $i < \text{followingCandles} - 1$:
   $$\text{close}[i] < \text{close}[i + 1]$$
   *(Newer candle close must be strictly lower than previous candle close. If $\text{close}[i] \ge \text{close}[i + 1]$, the sequence is INVALID).*

### Rule 3: Execution Condition
```
shortSetup = mainBullish AND validBearishSequence

SHORT ENTRY = enableShortTrades 
          AND shortSetup 
          AND (strategy.position_size == 0)
```

---

## 5. Signal Confirmation

- **Execution Timing**: Evaluated at the close of candle $i=0$ (the final candle of the sequence).
- **In Pine Script Strategy Engine**:
  - Strategy calls `strategy.entry("Long", strategy.long)` when `strategy.position_size == 0`.
  - By default in Pine Script v6 strategy execution, the entry order is filled at the **open of the very next candle** ($t+1$).
- **Intrabar Guard**: Conditions depend strictly on completed candle values (`open`, `high`, `low`, `close`).

---

## 6. Indicator Calculations

This strategy is a pure price-action / candlestick geometry algorithm and requires **no moving averages, oscillators, or volume filters**.

Calculations required:
1. Candlestick polarity: $\text{close} > \text{open}$ (bullish) vs $\text{close} < \text{open}$ (bearish).
2. Lookback reference offsets: index $t - \text{followingCandles}$.
3. Pairwise close comparisons: $\text{close}[i] > \text{close}[i+1]$ across the lookback array.
4. Extrema comparisons: $\min(\text{low}[0 \dots N-1]) > \text{low}[N]$ (Long) and $\max(\text{high}[0 \dots N-1]) < \text{high}[N]$ (Short).

---

## 7. Filters

- **Flat Position Filter**: `strategy.position_size == 0` (No concurrent or pyramided positions allowed).
- **Directional Enablement Filters**:
  - `enableLongTrades` (default `true`)
  - `enableShortTrades` (default `false`)
- **No external indicator filters** (no volume, ATR, or trend indicators are used).

---

## 8. Invalidations

A setup is invalidated if any of the following occur before candle $i=0$ closes:
1. Any candle in the sequence fails to close in the setup direction.
2. Any candle in the sequence breaches the main candle's extreme (low for long, high for short).
3. Any candle in the sequence fails to close beyond the previous candle's close (non-monotonic close progression).
4. An existing open position has not yet been closed by SL or TP.

---

## 9. Stop Loss Logic

**NATIVE STOP LOSS IS FULLY DEFINED IN CODE.**

### For Long Positions:
$$\text{stopLossPrice} = \text{low}[\text{followingCandles}]$$
The stop loss is anchored exactly at the low of the initial bearish main candle.
$$\text{longRisk} = \text{close} - \text{stopLossPrice}$$

### For Short Positions:
$$\text{stopLossPrice} = \text{high}[\text{followingCandles}]$$
The stop loss is anchored exactly at the high of the initial bullish main candle.
$$\text{shortRisk} = \text{stopLossPrice} - \text{close}$$

---

## 10. Take Profit Logic

**NATIVE TAKE PROFIT IS FULLY DEFINED IN CODE.**

R-multiple selection via `takeProfitR`:
- `"0.5R"` $\implies \text{rrMultiple} = 0.5$
- `"1R"` $\implies \text{rrMultiple} = 1.0$
- `"1.5R"` $\implies \text{rrMultiple} = 1.5$ (Default)
- `"2R"` $\implies \text{rrMultiple} = 2.0$

### Target Price Calculation:
- **Long Take Profit**:
  $$\text{takeProfitPrice} = \text{close} + \text{longRisk} \cdot \text{rrMultiple}$$
- **Short Take Profit**:
  $$\text{takeProfitPrice} = \text{close} - \text{shortRisk} \cdot \text{rrMultiple}$$

### Order Execution:
Executed via Pine Script OCO bracket:
```pinescript
strategy.exit(
     "Long Take Profit / Stop Loss",
     from_entry = "Long",
     stop = stopLossPrice,
     limit = takeProfitPrice
)
```

---

## 11. Timeframe

- **Intended Timeframe**: Designed for lower intraday timeframes (1m, 3m, 5m).
- **Timeframe Dependence**: Strategy logic is strictly relative to bar sequence count ($N$ bars). It will run on any timeframe, but signal frequency drops sharply on higher timeframes.

---

## 12. Repainting / Lookahead Audit

- **Classification**: **NON-REPAINTING**
- **Analysis**:
  - The script relies exclusively on past bars: `[0]` through `[followingCandles]`.
  - In historical bar replay and live trading, candle closes are immutable once the bar finishes.
  - No `request.security()`, no future bar indexing, no repainting functions.

---

## 13. Python Implementation Requirements

To reproduce Herman's Momentum Sequence signals on `MNQ_1m_continuous.parquet`:
1. **Vectorized / Windowed Sequence Detection**:
   - For a given window of $N+1$ candles ($N \in \{2, 3, 4, 5\}$):
     - Check `mainBearish` at index $0$ of the window.
     - Check `close[1:] > open[1:]` (all positive candle bodies).
     - Check `low[1:] > low[0]` (all lows strictly above anchor candle low).
     - Check `diff(close[1:]) > 0` (all sequential closes strictly ascending).
2. **State Machine / Position Simulator**:
   - Because subsequent signals are ignored while a position is open (`strategy.position_size == 0`), signals cannot be backtested as independent events.
   - An event-loop or bar-by-bar simulator must simulate entry at the next bar's Open, and monitor High/Low on subsequent bars to check whether Stop Loss or Limit Target is triggered first.
3. **Execution Nuance**:
   - Intrabar evaluation: If both SL and TP price levels fall within the High/Low range of the same subsequent bar, the fill resolution rule (e.g. conservative SL first, or tick-level simulation) must be explicitly stated.

---

## 14. AMBIGUITIES / DECISIONS REQUIRED

1. **Default Short Disablement**:
   - In the Pine script, `enableShortTrades` is set to `false` by default:
     ```pinescript
     enableShortTrades = input.bool(false, title = "Short Trades", ...)
     ```
   - *Decision*: In Phase 2, we must evaluate both Long-only (Pine default) and Long+Short configurations to test whether directional asymmetry exists on MNQ.
2. **Same-Bar SL/TP Collision Rule**:
   - If high volatility causes both `takeProfitPrice` and `stopLossPrice` to be spanned by a single 1-minute candle, Pine Script's internal simulator uses bar construction heuristics (or tick data) to determine which hit first.
   - *Decision*: In Python backtesting, adopt a conservative convention (assume worst-case: Stop Loss triggers first if ambiguous) or utilize the Open price relative to levels.
3. **Zero Risk Anomaly Guard**:
   - If `close == low[followingCandles]` (impossible if sequence closes are strictly ascending, but numerically safe to guard), `longRisk` would be zero. A minimum risk delta (e.g., 1 tick) should be enforced in Python.
