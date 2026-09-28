# Strong Buy/Sell — Forensic Notes & Insights

## Source File Analyzed
`strategies/strong_buy_sell/strong_buy_sell.txt` (342 lines of Pine Script v6)

---

## 1. Key Forensic Discoveries

### Discovery 1: Plotted Labels vs Internal Signals Discrepancy
- The input `minScoreInput` has a default value of `55`.
- The internal variable `rawBuy` checks `mScore >= minScore` (55).
- If confirmed and warmed up, `confirmedBuy` evaluates to `true`.
- **However**, lines 326–329 only render a label on the chart if:
  ```pinescript
  showSignalsInput and confirmedBuy and isStrongBuy
  ```
  where:
  ```pinescript
  isStrongBuy = confirmedBuy and mScore >= 75
  ```
- **Impact**: A trader running this indicator on TradingView with default settings only ever sees signals when the confluence score reaches **75 or higher**, even though `confirmedBuy` was armed at **55**. The intermediate signals ($55 \le \text{score} < 75$) are completely hidden visually!

### Discovery 2: The "Ghost" Pullback Engine
- Lines 289–322 implement a complete, sophisticated pullback detection engine based on:
  - Trend continuity (`avteDir == 1 and not trendFlipBull`),
  - Retracement to dynamic EMA (`close <= pullEma`, where `pullEma = ta.ema(close, 24)`),
  - Oversold RSI hook (`pullRsi < 35 and pullRsi > pullRsi[1]`, where `pullRsi = ta.rsi(close, 8)`),
  - Passing all active filters (`bullFiltersPass`).
- **However**, nowhere in the rest of the script is `pullbackBuy` or `pullbackSell` plotted, alerted, or utilized. It is completely orphaned in the source code.
- **Forensic Decision**: In Phase 2 signal extraction, we should capture `pullbackBuy` and `pullbackSell` as a separate signal category so we don't discard this potential source of alpha.

---

## 2. Mathematical Architecture of the AVTE

The core trend detection engine is the **Adaptive Volatility Trend Engine (AVTE)**, which is significantly more complex than standard SuperTrend or ATR trailing stops:
1. **Pre-filtering**: Price is smoothed using John Ehlers' 2-pole Super Smoother (`ehlersSS`), which filters out high-frequency market noise with minimal phase lag.
2. **Kaufman Efficiency Ratio (ER)**: Volatility is scaled adaptively using Perry Kaufman's ER ($|\Delta \text{close}| / \sum |\Delta \text{close}_i|$), which accelerates smoothing constants during directional trends and decelerates them in chop.
3. **Ratchet Mechanism**: Bands only tighten or ratchet forward; they do not expand backward until price violates the band and flips trend direction (`avteDir`).

---

## 3. Confluence Score Breakdown (100 Points Total)

| Factor | Weight | Bull Condition | Bear Condition | Neutral / Fallback |
|---|---|---|---|---|
| 1. EMA Alignment | $\pm 15$ | Close > EMA 50 > EMA 200 | Close < EMA 50 < EMA 200 | 0 |
| 2. RSI 14 | $\pm 10$ | $50 < \text{RSI} < 70$ | $30 < \text{RSI} \le 50$ | 0 |
| 3. MACD Histogram | $\pm 12$ | $\text{Hist} > 0 \land \text{Hist} > \text{Hist}[1]$ | $\text{Hist} < 0 \land \text{Hist} < \text{Hist}[1]$ | 0 |
| 4. Volume Confirmation | $\pm 8$ | Volume $> 1.2\times$ SMA20 & Close Up | Volume $> 1.2\times$ SMA20 & Close Down | $\pm 4$ if low vol |
| 5. ADX 14 | $\pm 8$ | ADX $> 20 \land \text{DI}^+ > \text{DI}^-$ | ADX $> 20 \land \text{DI}^- > \text{DI}^+$ | 0 |

---

## 4. Risk Management Forensics

- The original script contains **no stop loss, no take profit, and no trailing exit**.
- To test this strategy objectively, risk models must be provided externally during Phase 2 / Phase 3.
