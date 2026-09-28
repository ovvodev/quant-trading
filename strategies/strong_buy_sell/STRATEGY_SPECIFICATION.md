# Strategy Specification: Strong Buy/Sell

## 1. Strategy Overview

- **Strategy Name**: Strong Buy/Sell (Indicator version 1.1.0)
- **Original Source File**: `strategies/strong_buy_sell/strong_buy_sell.txt` (Pine Script v6 Indicator)
- **Strategy Category**: Adaptive Volatility Trend-Following with Multi-Factor Confluence Scoring
- **Core Idea**: Uses an **Adaptive Volatility Trend Engine (AVTE)** combining a 2-pole Ehlers Super Smoother and Kaufman-adaptive ATR bands to detect trend direction and trend flips. Trend flip signals are scored using a 0–100 symmetric momentum confluence score (EMA alignment, RSI, MACD histogram, volume expansion/contraction, and ADX direction).
- **Intended Market Conditions**: Trending intraday or swing markets; designed to reject choppy, range-bound environments via confluence thresholding and optional ADX/volume filters.

---

## 2. Inputs

The following configurable inputs are declared in `strong_buy_sell.txt`:

| Input Name | Pine Identifier | Default Value | Allowed Values / Type | Purpose | Directly Affects Signals? |
|---|---|---|---|---|---|
| Trend Sensitivity | `sensitivityInput` | `2.5` | Float [0.5, 8.0], step 0.1 | AVTE band factor / multiplier | **YES** |
| ATR Period | `atrPeriodInput` | `21` | Integer [5, 100] | Volatility measurement lookback | **YES** |
| Source | `sourceInput` | `close` | Price Source | Input price series for AVTE | **YES** |
| Preset | `presetInput` | `"Balanced"` | `"Conservative"`, `"Balanced"`, `"Aggressive"`, `"Scalping"` | Overrides/scales sensitivity, ATR, and minScore | **YES** |
| Min Signal Score (0-100) | `minScoreInput` | `55` | Integer [10, 95], step 5 | Confluence score gate for trend-flip signals | **YES** |
| Strong Signals Only (75+) | `showStrongOnlyInput` | `false` | Boolean | If true, raises score threshold to 75 | **YES** |
| Show Pullback Signals | `showPullbackInput` | `true` | Boolean | Enables calculation of pullback entries | **YES (for pullback signals)** |
| Pullback Sensitivity | `pullbackSensInput` | `8` | Integer [3, 20] | Lookback period for pullback RSI and EMA | **YES (for pullback signals)** |
| Volume Filter | `useVolFilterInput` | `false` | Boolean | Requires Volume Fast EMA > Slow EMA | **YES (if enabled)** |
| ADX Trend Strength Filter | `useAdxFilterInput` | `false` | Boolean | Requires ADX > 20 | **YES (if enabled)** |
| Momentum Filter | `useMomentumFilterInput`| `false` | Boolean | Requires MACD histogram expansion in direction | **YES (if enabled)** |
| Theme | `themeInput` | `"Auto"` | `"Auto"`, `"Dark"`, `"Light"` | Visual chart appearance | No |
| Show Buy/Sell Signals | `showSignalsInput` | `true` | Boolean | Visual chart display of signal labels | No |
| Bull Color | `bullColorInput` | `#089981` | Color | Visual palette | No |
| Bear Color | `bearColorInput` | `#FF5252` | Color | Visual palette | No |
| Neutral Color | `neutralColorInput` | `#FFEB3B` | Color | Visual palette | No |
| EMA Length (Overlay) | `len` | `9` | Integer (min 1) | Cosmetic colored 9 EMA line | No |
| EMA Source (Overlay) | `src` | `close` | Price Source | Cosmetic colored 9 EMA source | No |

### Preset Modification Matrix
When `presetInput` is set, effective parameters are transformed as follows:
```
effectiveSensitivity = 
    preset == "Conservative" ? sensitivityInput * 1.4 :
    preset == "Aggressive"   ? sensitivityInput * 0.7 :
    preset == "Scalping"     ? sensitivityInput * 0.5 :
    sensitivityInput

effectiveAtr = 
    preset == "Conservative" ? round(atrPeriodInput * 1.3) :
    preset == "Aggressive"   ? round(atrPeriodInput * 0.8) :
    preset == "Scalping"     ? round(atrPeriodInput * 0.6) :
    atrPeriodInput

effectiveMinScore = 
    preset == "Conservative" ? max(minScoreInput, 70) :
    preset == "Aggressive"   ? min(minScoreInput, 45) :
    preset == "Scalping"     ? min(minScoreInput, 40) :
    minScoreInput
```

---

## 3. Long Entry Logic

The strategy defines two distinct types of Long signals in code:
1. **Trend Flip Long** (with sub-tiers: Standard Buy vs Strong Buy)
2. **Pullback Long**

### Signal Type 1: Trend Flip Long
A trend flip Long occurs when the Adaptive Volatility Trend Engine flips from bearish (-1) to bullish (+1):
```
trendFlipBull = (avteDir == 1) AND (avteDir[1] == -1)

minScore = showStrongOnlyInput ? max(effectiveMinScore, 75) : effectiveMinScore

rawBuy = trendFlipBull 
     AND (mScore >= minScore)
     AND bullFiltersPass

confirmedBuy = rawBuy 
           AND barstate.isconfirmed 
           AND (bar_index >= max(effectiveAtr * 3, 200))

isStrongBuy = confirmedBuy AND (mScore >= 75)
```
*Filter conditions (`bullFiltersPass`)*:
```
volFilterOk  = useVolFilterInput      ? (EMA(volume, 10) > EMA(volume, 25)) : true
adxFilterOk  = useAdxFilterInput      ? (ADX > 20.0)                        : true
bullMomOk    = useMomentumFilterInput ? (macdHist > 0 AND macdHist > macdHist[1]) : true

bullFiltersPass = volFilterOk AND adxFilterOk AND bullMomOk
```

### Signal Type 2: Pullback Long
Occurs within an established bullish trend when price pulls back to dynamic support:
```
pullRsi = RSI(close, pullbackSensInput)       // default 8
pullEma = EMA(close, pullbackSensInput * 3)   // default 24

pullbackBuyRaw = showPullbackInput
             AND (avteDir == 1)
             AND NOT trendFlipBull
             AND (close <= pullEma)
             AND (pullRsi < 35)
             AND (pullRsi > pullRsi[1])

pullbackBuy = pullbackBuyRaw
          AND bullFiltersPass
          AND barstate.isconfirmed
          AND (bar_index >= max(effectiveAtr * 3, 200))
```

---

## 4. Short Entry Logic

### Signal Type 1: Trend Flip Short
```
trendFlipBear = (avteDir == -1) AND (avteDir[1] == 1)

minScore      = showStrongOnlyInput ? max(effectiveMinScore, 75) : effectiveMinScore
sellThreshold = 100 - minScore

rawSell = trendFlipBear 
      AND (mScore <= sellThreshold)
      AND bearFiltersPass

confirmedSell = rawSell 
            AND barstate.isconfirmed 
            AND (bar_index >= max(effectiveAtr * 3, 200))

isStrongSell = confirmedSell AND (mScore <= 25)
```
*Filter conditions (`bearFiltersPass`)*:
```
volFilterOk  = useVolFilterInput      ? (EMA(volume, 10) > EMA(volume, 25)) : true
adxFilterOk  = useAdxFilterInput      ? (ADX > 20.0)                        : true
bearMomOk    = useMomentumFilterInput ? (macdHist < 0 AND macdHist < macdHist[1]) : true

bearFiltersPass = volFilterOk AND adxFilterOk AND bearMomOk
```

### Signal Type 2: Pullback Short
```
pullRsi = RSI(close, pullbackSensInput)       // default 8
pullEma = EMA(close, pullbackSensInput * 3)   // default 24

pullbackSellRaw = showPullbackInput
              AND (avteDir == -1)
              AND NOT trendFlipBear
              AND (close >= pullEma)
              AND (pullRsi > 65)
              AND (pullRsi < pullRsi[1])

pullbackSell = pullbackSellRaw
           AND bearFiltersPass
           AND barstate.isconfirmed
           AND (bar_index >= max(effectiveAtr * 3, 200))
```

---

## 5. Signal Confirmation

- **Barstate Guard**: Every signal requires `barstate.isconfirmed == true`.
- **Warmup Guard**: Every signal requires `bar_index >= max(effectiveAtr * 3, 200)`.
- **Timing**: Signals become valid strictly upon completion of the 1-minute candle (at candle close). Execution takes place on the subsequent tick/bar open.

---

## 6. Indicator Calculations

### 1. Ehlers 2-Pole Super Smoother Filter (`ehlersSS(src, period)`)
Applied to price source with period $\max(\text{round}(\text{effectiveAtr} / 2), 3)$:
$$\omega = \frac{\sqrt{2} \cdot \pi}{\max(\text{period}, 2)}$$
$$a_1 = \exp(-\omega), \quad b_1 = 2 \cdot a_1 \cdot \cos(\omega)$$
$$c_2 = b_1, \quad c_3 = -a_1^2, \quad c_1 = 1.0 - c_2 - c_3$$
For $t \ge 3$:
$$\text{SS}_t = c_1 \cdot \frac{\text{src}_t + \text{src}_{t-1}}{2} + c_2 \cdot \text{SS}_{t-1} + c_3 \cdot \text{SS}_{t-2}$$
(For $t < 3$, $\text{SS}_t = \text{src}_t$).

### 2. Kaufman Adaptive ATR (`adaptiveAtr(period)`)
$$\text{direction} = |\text{close}_t - \text{close}_{t - \text{period}}|$$
$$\text{volatility} = \sum_{i=0}^{\text{period}-1} |\text{close}_{t-i} - \text{close}_{t-i-1}|$$
$$\text{ER} = \frac{\text{direction}}{\text{volatility}} \quad (\text{safe division, fallback } 0.5)$$
$$\text{fastSc} = \frac{2}{3}, \quad \text{slowSc} = \frac{2}{31}$$
$$\text{SC} = \left(\text{ER} \cdot (\text{fastSc} - \text{slowSc}) + \text{slowSc}\right)^2$$
$$\text{aATR}_t = \text{aATR}_{t-1} + \text{SC} \cdot (\text{rawATR}_t - \text{aATR}_{t-1})$$
where $\text{rawATR}_t = \text{ta.atr}(\text{period})$.

### 3. Adaptive Volatility Trend Engine (AVTE)
$$\text{filteredPrice} = \text{ehlersSS}(\text{source}, \max(\text{round}(\text{effectiveAtr}/2), 3))$$
$$\text{upperBand}_t = \text{filteredPrice}_t + \text{factor} \cdot \text{aATR}_t$$
$$\text{lowerBand}_t = \text{filteredPrice}_t - \text{factor} \cdot \text{aATR}_t$$
Trailing band updates:
$$\text{lower}_t = (\text{lowerBand}_t > \text{lower}_{t-1} \text{ or } \text{close}_{t-1} < \text{lower}_{t-1}) \ ? \ \text{lowerBand}_t : \text{lower}_{t-1}$$
$$\text{upper}_t = (\text{upperBand}_t < \text{upper}_{t-1} \text{ or } \text{close}_{t-1} > \text{upper}_{t-1}) \ ? \ \text{upperBand}_t : \text{upper}_{t-1}$$
Direction flip logic:
$$\text{if } \text{close}_t > \text{upper}_t \implies \text{dir}_t = 1$$
$$\text{else if } \text{close}_t < \text{lower}_t \implies \text{dir}_t = -1$$
$$\text{else } \text{dir}_t = \text{dir}_{t-1}$$

### 4. Confluence Momentum Score (`calcMomentumScore()`)
Base score starts at $50.0$:
- **Factor 1: EMA Alignment ($\pm 15$)**:
  - If $\text{close} > \text{EMA}_{50}$ and $\text{EMA}_{50} > \text{EMA}_{200}$: $+15.0$
  - Else if $\text{close} < \text{EMA}_{50}$ and $\text{EMA}_{50} < \text{EMA}_{200}$: $-15.0$
- **Factor 2: RSI 14 ($\pm 10$)**:
  - If $\text{RSI}_{14} > 50$ and $\text{RSI}_{14} < 70$: $+10.0$
  - Else if $\text{RSI}_{14} \le 50$ and $\text{RSI}_{14} > 30$: $-10.0$
- **Factor 3: MACD Histogram (12, 26, 9) ($\pm 12$)**:
  - If $\text{Hist}_t > 0$ and $\text{Hist}_t > \text{Hist}_{t-1}$: $+12.0$
  - Else if $\text{Hist}_t < 0$ and $\text{Hist}_t < \text{Hist}_{t-1}$: $-12.0$
- **Factor 4: Volume Confirmation ($\pm 8$)**:
  - $\text{volAbove} = (\text{vol} > \text{SMA}_{20}(\text{vol}) \cdot 1.2)$
  - $\text{volBelow} = (\text{vol} < \text{SMA}_{20}(\text{vol}) \cdot 0.8)$
  - If $\text{volAbove}$ and $(\text{close}_t - \text{close}_{t-1} > 0)$: $+8.0$
  - Else if $\text{volAbove}$ and $(\text{close}_t - \text{close}_{t-1} < 0)$: $-8.0$
  - Else if $\text{volBelow}$: if $(\text{close}_t - \text{close}_{t-1} > 0)$ $-4.0$, else $+4.0$
- **Factor 5: ADX Strength (14, 14) ($\pm 8$)**:
  - If $\text{ADX}_{14} > 20$ and $\text{DI}^+ > \text{DI}^-$: $+8.0$
  - Else if $\text{ADX}_{14} > 20$ and $\text{DI}^- > \text{DI}^+$: $-8.0$
- **Clamping**:
  $$\text{mScore} = \min(100.0, \max(0.0, \text{score}))$$

---

## 7. Filters

### Built-in Core Filter:
- **Warmup Filter**: `bar_index >= max(effectiveAtr * 3, 200)` (Required).
- **Confluence Score Filter**: `mScore >= minScore` (for Buy) and `mScore <= (100 - minScore)` (for Sell) (Required).

### Optional User Filters:
1. **Volume Filter (`useVolFilterInput`, default `false`)**: Requires $\text{EMA}_{10}(\text{volume}) > \text{EMA}_{25}(\text{volume})$.
2. **ADX Filter (`useAdxFilterInput`, default `false`)**: Requires $\text{ADX}_{14} > 20.0$.
3. **Momentum Filter (`useMomentumFilterInput`, default `false`)**:
   - For Long: $\text{macdHist} > 0$ and $\text{macdHist} > \text{macdHist}[1]$.
   - For Short: $\text{macdHist} < 0$ and $\text{macdHist} < \text{macdHist}[1]$.

---

## 8. Invalidations

- **Trend Flip Invalidation**: Trend flips occur on single bar transitions (`avteDir == 1 and prevDir == -1`). If `mScore` or filters do not pass on that exact flip bar, the opportunity is lost and no signal fires until the next full trend reversal.
- **Pullback Invalidation**: If price breaches `pullEma` but RSI does not hook back (`pullRsi > pullRsi[1]`), or if the trend direction flips before the pullback criteria complete, the setup is invalidated.

---

## 9. Stop Loss Logic

**NO NATIVE STOP LOSS DEFINED** in the original Pine script — external testing framework must provide risk model.

*Forensic Finding*:
- `strong_buy_sell.txt` is an indicator script with zero trade execution functions (`strategy.exit`, etc.).
- There is no trailing stop or SL calculation in the code.
- Phase 2 backtesting must inject a standardized risk model (e.g. ATR multiple, AVTE trendline trailing stop, or swing high/low stop).

---

## 10. Take Profit Logic

**NO NATIVE TAKE PROFIT DEFINED** — external testing framework must provide exit model.

*Forensic Finding*:
- The script contains no fixed target, R-multiple target, or partial exit logic.
- Natural theoretical exit: A position is held until an opposing trend flip (`avteDir` flips) or opposite signal fires.

---

## 11. Timeframe

- **Intended Timeframe**: Adaptable across timeframes. Tooltip mentions "Balanced: 15M-4H", "Scalping: 1-5M".
- **Dependence**: Indicators are calculated directly on chart timeframe candles. No cross-timeframe calls.

---

## 12. Repainting / Lookahead Audit

- **Classification**: **NON-REPAINTING**
- **Analysis**:
  - No `request.security()` or multi-timeframe fetching.
  - Calculations strictly reference historical and current bar values ($t, t-1, t-2$).
  - `barstate.isconfirmed` prevents intrabar recalculations.

---

## 13. Python Implementation Requirements

To reproduce Strong Buy/Sell signals on `MNQ_1m_continuous.parquet`:
1. **Iterative AVTE Engine**:
   - Because of the state-dependent recursive equations for Ehlers Super Smoother, Kaufman Adaptive ATR, and trailing band updates, a vectorized or Numba/Cython-accelerated loop is required in Python.
2. **Indicator Suite**:
   - TA-Lib or standard formulas for EMA(50, 200), RSI(14), MACD(12, 26, 9), DMI/ADX(14), Volume EMAs (10, 25), and Volume SMA (20).
3. **Signal Categorization**:
   - Must output separate signal columns:
     - `trend_flip_buy` / `trend_flip_sell`
     - `strong_buy` / `strong_sell`
     - `pullback_buy` / `pullback_sell`

---

## 14. AMBIGUITIES / DECISIONS REQUIRED

1. **Discrepancy Between Plotted Signal vs Calculated Signal**:
   - **Critical Forensic Finding**: In lines 326–329:
     ```pinescript
     plotshape(showSignalsInput and confirmedBuy and isStrongBuy ? low : na, "Strong Buy", ...)
     plotshape(showSignalsInput and confirmedSell and isStrongSell ? high : na, "Strong Sell", ...)
     ```
     The script *calculates* `confirmedBuy` (score $\ge 55$), but the chart *only displays labels* when `isStrongBuy` is true (score $\ge 75$)!
   - *Decision*: In Python Phase 2, we must test both:
     - Variant A: `Strong_Buy_Sell_Strict` (Score $\ge 75$)
     - Variant B: `Strong_Buy_Sell_Standard` (Score $\ge 55$)
2. **Orphaned Pullback Signals**:
   - Lines 311–322 compute `pullbackBuy` and `pullbackSell`, but the script contains **no plotshape, no alert, and no display** for them!
   - *Decision*: Treat Pullback signals as an optional sub-engine (`Strong_Buy_Sell_Pullback`) rather than discarding them.
3. **Absence of Exit Rules**:
   - Because no SL/TP exists, Phase 2 must benchmark:
     - (a) Exit on opposite trend flip (`avteDir` reverse),
     - (b) Fixed R-multiple (e.g. 1.5R / 2R),
     - (c) Trailing stop along the AVTE trendline (`avteLine`).
