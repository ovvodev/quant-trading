# Momentum Sequence Strategy+ [Herman] — Forensic Notes & Insights

## Source File Analyzed
`strategies/momentum_sequence/Momentum Sequence Strategy+ [Herman]  .txt` (536 lines of Pine Script v6)

---

## 1. Structural Comparison With the Other Two Strategies

Unlike Trieu and Strong Buy/Sell (which are declared as `indicator(...)`), Herman's Momentum Sequence is declared as an official Pine Script `strategy(...)`:
```pinescript
strategy(
     "Momentum Sequence Strategy [Herman]",
     overlay = true,
     pyramiding = 0,
     initial_capital = 50000,
     currency = currency.USD,
     default_qty_type = strategy.fixed,
     default_qty_value = 1,
     commission_type = strategy.commission.cash_per_contract,
     commission_value = 2.50,
     slippage = 1,
     margin_long = 5,
     margin_short = 5
)
```

This means:
1. It is the **only strategy in the project with native stop loss, take profit, and position-sizing parameters** embedded directly in the source code.
2. It enforces single-position execution (`pyramiding = 0` and `strategy.position_size == 0`). While a trade is open, all intermediate signals are ignored.

---

## 2. Sequence Counting Mathematics

The lookback index logic is critical:
- Lookback length: `followingCandles` (options: 2, 3, 4, or 5; default is 5).
- Main candle index: `followingCandles` bars ago.
- Follow-through candles: array from `i = 0` (current bar) back to `i = followingCandles - 1`.

### Sequence Rules (for Long):
1. Main Candle: `close[followingCandles] < open[followingCandles]` (Bearish)
2. Follow-through 1: `close[i] > open[i]` (All follow-through candles must be green)
3. Follow-through 2: `low[i] > low[followingCandles]` (No wick can touch or violate the main candle low)
4. Follow-through 3: `close[i] > close[i+1]` (Monotonically rising closes: `close[0] > close[1] > close[2] > close[3] > close[4]`)

### Sequence Stringency:
Requiring 5 consecutive candles that are green, each closing higher than the previous, without any wick violating the anchor low, is a very strict geometric filter. On a 1-minute chart, this setup occurs during clean momentum breakouts or sharp V-reversals.

---

## 3. Directional Asymmetry

In lines 52-64:
- `enableLongTrades`: `true`
- `enableShortTrades`: `false`

The original author disabled Short trades by default. For our Phase 2 backtest, we must test:
1. Long Only (Pine Script default),
2. Short Only,
3. Both Long and Short enabled.

---

## 4. Execution Timing in Pine Script

Pine Script strategies execute order placements at the close of the trigger bar, which means the fill price in standard backtesting is the **Open of the next bar** (`open[bar_index + 1]`).
Exits are then evaluated on subsequent bars at the exact Stop Loss (`stopLossPrice`) or Take Profit (`takeProfitPrice`) price levels.
