# Prop Firm Scalping: Strategy Review

*Review date: 27 September 2026. Data: 5 years of MNQ 1-minute bars (Sep 2021 – Sep 2026) and one month of GBPUSD 1-minute prices (June 2018).*

## Verdict

*Updated after the strategy search in sections 6 and 7.*

- **The scalping strategy has no edge on MNQ.** In its best configuration it makes +0.007R per trade before costs (t-stat 0.93, which can't be told apart from zero) and loses −0.007R per trade after costs. It passes fewer prop evaluations than a zero-edge strategy (14–25% vs 27–34%).
- **No true scalp survives costs on MNQ.** A pre-registered search of 62 configurations across seven ideas found nothing that holds trades for minutes and makes money after costs.
- **The best strategy found is intraday momentum, not a scalp.** It is the "noise area" strategy of Zarattini, Aziz & Barbon (2024), with the published parameters and trades lasting about two hours.
  - **Edge:** about +$18 per MNQ contract per trade after costs (t-stat 2.7). It is positive in both data halves and every year, and trading the opposite side loses about as much.
  - **Prop results:** on a 50k evaluation with end-of-day trailing drawdown, 2 MNQ passed 48% of evaluations vs 23% for zero edge.
- **Big caveat: it has been flat for the last 17 months.** Since May 2025 it has made about $0 per trade. 38% of all profit came from three volatile months, 19% from April 2025 alone. It earns in volatile, trending markets and goes nowhere in calm ones.
- **Use MNQ, not NQ, for prop accounts.** One NQ contract risks about $1,400 at a typical scalp stop, so on a 50k evaluation 94–99% of trades can't be sized at all.

"R" throughout is the amount risked on a trade: +0.1R means a profit of one tenth of the stop distance.

## 1. What the strategy does

One idea, implemented three times: [Python backtest](Prop%20Firm%20Scalping%20backtest.py), [Pine v6](Prop%20Firm%20Scalping%20strategy.pine) and [Pine v5 for forex](Prop%20Firm%20Scalping%20strategy_forex.pine).

1. **Trend filter:** trade only in the direction of a 90/300 EMA crossover on 1-minute bars.
2. **Entry:** price closes outside a 30-bar, 1.3-std Bollinger Band, then closes back inside. This buys the dip in an uptrend and sells the rip in a downtrend.
3. **Volatility filter:** skip the quietest 30% and the wildest 3% of volatility, measured as a rolling percentile.
4. **Exits:** stop at 3× recent volatility, target at 1.5× (2× for forex), a 45-minute time stop, and a forced close at session end.
5. **Prop-firm risk rules:** 0.5% risk per trade, 2% daily loss halt, 8% drawdown halt, profit-target lock, and at most 5 trades a day.

## 2. Problems found and fixed

| # | Problem | Effect | Fix |
|---|---|---|---|
| 1 | The forex backtest's volatility filter used quantiles from the **whole sample**, i.e. future data | GBPUSD profit factor inflated from 1.53 to 1.78 | Causal rolling percentile, identical to Pine's `ta.percentrank` |
| 2 | In Python, a band poke seen while trading was blocked (out of session, filter off, cap hit) still armed a later entry. Pine did not do this | Python and Pine traded different signals | The pending setup is now cleared whenever trading is blocked, in both Python paths |
| 3 | MNQ contract rolls were **not back-adjusted**; roll gaps of up to 423 points appeared as price moves | Distorted EMAs, bands and volatility, mostly at the Asia open where rolls land | `back_adjust_rolls()` |
| 4 | Take-profit filled when price merely touched it, and 2 ticks of slippage were charged even on limit exits | Fills too optimistic, costs mis-assigned | Take-profit needs a 1-tick trade-through (`target_through_ticks`, and `backtest_fill_limits_assumption` in Pine). Slippage is charged per market fill only (`trade_cost()`) |
| 5 | Prop rules were modelled only as % of closed equity. Futures prop firms use a **dollar** drawdown that trails the account high and is breached by **open** losses | Pass rates did not reflect futures evaluations | `backtesting_futures_prop()` with end-of-day and intraday trailing, using each trade's max adverse/favourable excursion. Pine v6 gets the same "$ trailing" modes plus a fixed-$ risk per trade |
| 6 | Pass rates were reported without a baseline, and from only 7–8 completed cycles | "57% pass rate" read as skill; a coin with this payoff shape passes about 30% | `zero_edge_trades()` baseline is now printed next to every pass rate |
| 7 | Pine v6 defaulted to **all three sessions on**, with New York at 08:00–17:00 | The default was the configuration the repo itself showed to be worst | New York 09:30–16:00 only by default |
| 8 | The all-sessions test shared the 5-trades-a-day cap, so Asia and London trades used up New York's slots | The comparison was not like-for-like | Documented, and re-tested with a 15-a-day cap; still loses (−0.006R) |
| 9 | The forex Pine script sized positions without `syminfo.pointvalue` and defaulted to zero costs | Oversized if loaded on a futures symbol; frictionless backtest | Sizing divides by point value; 0.3 pip slippage and trade-through by default |
| 10 | README and code comments claimed an edge "holding up every year 2021–2026" and a 57% / 12% pass rate | Overstated the strategy | Rewritten with the corrected numbers |

`backtesting_v5_legacy()` is kept unchanged so the original v5 script's result can still be reproduced.

## 3. Results after the fixes (MNQ, 5 years)

All figures after costs of $0.70 commission per round trip plus 1 tick of slippage on every market fill.

| Configuration | Trades/yr | Win rate | Gross R/trade | t-stat | Net R/trade |
|---|---|---|---|---|---|
| New York 09:30–16:00, 3/1.5 (default) | 1,183 | 61.1% | +0.007 | 0.93 | −0.007 |
| New York 10:00–16:00, 90-min hold (best variant found) | 1,029 | 62.8% | +0.013 | 1.49 | −0.000 |
| New York open 09:30–11:30, 3/2 (forex parameters) | 479 | 54.9% | −0.013 | −0.92 | −0.027 |
| London 03:00–12:00 | 1,286 | 59.0% | −0.013 | −1.69 | −0.041 |
| Asia 19:00–04:00 | 1,084 | 55.8% | −0.018 | −2.25 | −0.051 |
| All three sessions | 1,365 | 57.9% | −0.018 | −2.46 | −0.050 |

- **By year (default config, gross):** 2021 −0.020, 2022 +0.018, 2023 +0.011, 2024 −0.015, 2025 +0.012, 2026 +0.023. No single year is significant.
- **Bootstrap 95% range for gross R/trade:** −0.008 to +0.023. There is an 18% chance the true value is zero or below.
- **Parameter grid (stop 2–4×, target 1–3×):** 0 of 25 combinations are positive after costs. The best gross t-stat is 1.52.
- **The win rate is the payoff shape.** With the stop twice as far away as the target, random entries hit the target first about two-thirds of the time. Keeping the same entries and exits but choosing the direction at random gives a 59% win rate. The trend-plus-pullback signal adds about 0.01R per trade over that, which is within noise.
- **Where it bleeds:** 27% of trades end on the 45-minute time stop, at −0.17R each on average.
- **Costs are small, but the edge is smaller.** Costs average 1.45% of the amount risked, twice the 0.73% gross edge. With zero commission or zero slippage the result is exactly break-even, so no broker makes this viable.

## 4. Which prop firm setup and which contract

### Contract: MNQ

| | MNQ | NQ |
|---|---|---|
| $ per index point | 2 | 20 |
| Average risk per contract at the default stop | ~$139 | ~$1,389 |
| Cost per round trip in index points | 0.60–0.85 | 0.40–0.65 |
| Share of signals tradable on a 50k account at $500 risk | 99% | 6% |
| Net R per trade (scalp) | −0.007 | −0.003 |

NQ's lower cost per point doesn't turn the scalp positive. Its size makes it unusable below roughly a 150k account: even there at $1,500 risk only 68% of trades can be sized, and the ones skipped are the high-volatility days, which quietly changes the strategy. **MNQ is the contract for prop evaluations** because it can be sized in whole contracts at sensible risk. I had no ES/MES data, so the S&P micro is untested.

### Prop firm pass rates (repeated evaluations over 5 years, after costs)

Rule templates are generic shapes typical of futures prop firms, not any specific firm's rules.

| Strategy (MNQ) | Rules | Risk/trade | Cycles | Pass rate | Zero-edge baseline |
|---|---|---|---|---|---|
| Scalp, New York | 50k, EOD trailing: $3k target / $2k max loss / $1k daily | $500 | 105 | 21% | 27% |
| Scalp, New York | 50k, intraday trailing: $3k target / $2.5k max loss | $500 | 93 | 25% | 30% |
| Scalp, New York | 150k, EOD trailing: $9k / $4.5k / $3k daily | $1,500 | 177 | 19% | 21% |
| Scalp, New York | % rules: 100k, 10% target / 8% trailing | 0.5% | 7 | 14% | 31% |
| Scalp, all sessions | 50k, EOD trailing | $500 | 170 | 9% | 27% |
| **Opening range breakout, 30 min** | 50k, EOD trailing | $500 | 26 | **42%** | 26% |
| **Opening range breakout, 30 min** | 50k, intraday trailing | $500 | 23 | **52%** | 30% |
| **Opening range breakout, 30 min** | 150k, EOD trailing | $1,500 | 56 | 32% | 20% |

What this means for choosing an evaluation:

- **Passing without an edge is a lottery ticket.** A zero-edge strategy still passes 20–30% of evaluations. Whoever passes then trades the same zero edge on the funded account, so fees plus resets make this negative expected value. Don't buy evaluations for the scalping strategy.
- **Prefer end-of-day trailing over intraday trailing.** Intraday trailing raises the floor on open profit that later gives back, which penalises any trade that runs up and reverses. The simulator shows the intraday template doing slightly better only because its max loss is larger ($2.5k vs $2k).
- **Size at about a quarter of the max loss per trade.** On a 50k account that's about $500, or 2–3 MNQ. At $200–300 the whole-contract floor skips 6–18% of scalp trades (33–65% of breakout trades), all of them the wide-stop days, which changes the strategy being tested. Larger sizes were not tested.
- **A 50k account with MNQ is the right testbed.** The 150k template showed the same pattern relative to its baseline.

## 5. The opening range breakout (first lead, later rejected)

Rules tested:
- Mark the high and low of the first 30 minutes after 09:30 New York time.
- Take the first 1-minute close outside that range (long above, short below). One trade per day.
- Stop at the opposite side of the range; target 1R; flat at 16:00.
- Same cost and fill model as above.

| Test | Result |
|---|---|
| All 12 variants (range 15/30/60 min × target 1/1.5/2/3R) | All positive after costs, +0.020 to +0.070 R/trade, t-stat 1.0–2.0 |
| 30 min / 1R, full sample | +0.043 R/trade net, t = 1.78, 1,234 trades, ~$270 average risk per MNQ contract |
| By year (net R) | 2021 +0.087, 2022 +0.089, 2023 +0.023, 2024 +0.090, 2025 +0.019, 2026 −0.040 |
| First half vs second half | +0.062 (t 1.77) vs +0.025 (t 0.73) |
| Longs vs shorts | +0.085 vs −0.001 |

Why it beats the scalp: costs are about 0.5–1% of risk for both, but the breakout's gross edge (~5% of risk per trade) is several times its costs, while the scalp's (0.7%) is half of them.

Why it isn't proven:
- **Not significant:** t < 2 in every cell of the grid.
- **Mostly one side:** the edge comes almost entirely from long trades during a period when the Nasdaq-100 doubled, so it may be the market's drift rather than the breakout.
- **Weakening:** 2025 was weak and 2026 is negative so far.
- **Small evaluation sample:** its evaluation pass rates rest on only 23–56 completed cycles.

**Follow-up (section 6): rejected.** Going long on the same bar, regardless of which way the range broke, earned almost as much (+0.051R vs +0.064R per trade). Most of the breakout's profit was the Nasdaq's upward drift, not the breakout. Under the pre-registered test its in-sample winner also failed out-of-sample.

## 6. Searching for the best short-term strategy

### How the search was run

Hunting for "the best" strategy on one dataset is how overfit strategies get made, so the rules were fixed before any results were seen.

- **Data split:** in-sample is Sep 2021 – Mar 2024; out-of-sample is Apr 2024 – Sep 2026.
- **Selection:** the best configuration of each idea is chosen by in-sample net t-stat only, then tested out-of-sample once.
- **Costs and fills:** $0.70 round-trip commission plus 1 tick of slippage per market fill. Take-profits need a 1-tick trade-through, and stops that gap past their level fill at the bar open.
- **Pass/fail test:** a strategy counts only if it holds up out-of-sample and its prop pass rate beats the zero-edge baseline.

### Round 1: 62 configurations, seven ideas

| Idea | Configs | In-sample winner (net R/trade, t) | Same config out-of-sample |
|---|---|---|---|
| Bollinger pullback scalp (this repo) | 2 | +0.002 (t 0.14) | −0.002 (t −0.16) |
| Opening range breakout (5/15/30/60 min) | 24 | 60 min, 1R, mid stop: +0.072 (t 1.87) | −0.027 (t −0.72) |
| Late-day momentum (Gao et al.) | 8 | +0.107 (t **2.83**) | −0.068 (t **−2.06**) |
| VWAP mean reversion | 12 | +0.008 (t 0.07) | −0.012 (t −0.10) |
| VWAP trend pullback | 4 | +0.011 (t 0.22) | −0.068 (t −1.39) |
| Gap fade | 6 | +0.022 (t 0.52) | +0.054 (t 1.35) |
| Gap and go | 6 | +0.044 (t 0.61) | −0.055 (t −0.96) |

- **Every true scalp lost after costs.** That covers the Bollinger pullback, VWAP reversion and VWAP trend pullback: anything holding for minutes. Gross edges of a few hundredths of R can't carry $1.20–1.70 of costs per contract.
- **The best in-sample result of the whole search flipped to a significant loss out-of-sample** (late-day momentum, t 2.83 → −2.06). This is why the split matters: with 62 tries, a t of about 2.5 turns up by luck.
- **Opening range breakouts with the stop at the far side of the range** were positive in 11 of 12 in-sample and 12 of 12 out-of-sample variants. The drift control in section 5 shows this is mostly Nasdaq's rise.
- **The gap fade's profit is all on the short side** (fading up-gaps), so it's also drift-related.

### Round 2: three published rules, parameters unchanged

These rules come from published papers and were tested with the papers' own parameters, so there was nothing to tune. Only the Crabel filter involved a choice, made on the in-sample half.

| Rule | In-sample | Out-of-sample | Verdict |
|---|---|---|---|
| 5-min ORB (Zarattini & Aziz 2023; 10R target, exit at close) | +0.045R (t 0.48) | +0.130R (t 1.34) | Not significant; 2026 negative |
| Crabel narrow-range filter on the 30-min ORB (in-sample pick: "wide" days) | +0.127R (t 2.01) | −0.010R (t −0.18) | Failed out-of-sample |
| **Noise-area momentum (Zarattini, Aziz & Barbon 2024)** | **+$16.15/contract (t 2.45)** | **+$17.46/contract (t 1.50)** | **Held up** (section 7) |

## 7. The best strategy found: intraday momentum (noise area)

Implemented in [Prop Firm Intraday Momentum backtest.py](Prop%20Firm%20Intraday%20Momentum%20backtest.py) and [Prop Firm Intraday Momentum strategy.pine](Prop%20Firm%20Intraday%20Momentum%20strategy.pine).

**Rules**
1. **Noise area:** for every minute of the session, average |price / today's open − 1| over the last 14 sessions. This is how far price usually wanders by that time of day.
2. **Bands:** upper = max(open, previous close) × (1 + noise); lower = min(open, previous close) × (1 − noise).
3. **Entries:** checked only at 10:00, 10:30 … 15:30 New York time. A close above the upper band goes long; a close below the lower band goes short.
4. **Exits:** at the same half-hours, exit when price falls back inside the band or through the session VWAP, whichever is tighter. Flat at 16:00.
5. **Protective stop:** one band-width from entry, checked every minute.
   - It was the in-sample-best of four stop sizes and held out-of-sample (+$16.01, t 1.47).
   - It cuts the worst trade from −$648 to −$438 per contract.

**Results (per MNQ contract, after costs, Sep 2021 – Sep 2026)**

| Measure | Value |
|---|---|
| Trades | 1,100 (~225 a year), 40% winners, average win $193 vs average loss $96 |
| Net $ per trade | +$18.44 (t 2.74); in-sample +$19.65 (t 3.01), out-of-sample +$17.12 (t 1.40) |
| Longs / shorts | +$25.18 / +$11.77, so both sides make money |
| **Control: opposite side** | **−$21.84 (t −3.24).** The direction call is real, not drift |
| Double costs | +$16.74 |
| By year | 2021 +$476 (3 months), 2022 +$6,172, 2023 +$4,497, 2024 +$4,345, 2025 +$3,485, 2026 +$1,308 |
| Daily Sharpe / max drawdown | 1.33 / $3,560 |
| Parameter robustness (not used for selection) | Lookback 10/20/30 days, checks every 60 min, no-VWAP exit: all positive in both halves |

**Prop evaluations (repeated cycles over 5 years, after costs; generic rule shapes)**

| Rules | Size | Pass rate | Zero-edge baseline | Median days per cycle |
|---|---|---|---|---|
| 50k, EOD trailing $2k, $3k target, $1k daily | 1 MNQ | 75% (8 cycles) | 25% | 180 |
| 50k, EOD trailing $2k, $3k target, $1k daily | **2 MNQ** | **48% (29 cycles)** | **23%** | **49** |
| 50k, EOD trailing $2k, $3k target, $1k daily | 3 MNQ | 38% (56 cycles) | 25% | 22 |
| 50k, intraday trailing $2.5k, $3k target | 2 MNQ | 41% (32 cycles) | 19% | 32 |
| 150k, EOD trailing $4.5k, $9k target, $3k daily | 6 MNQ | 37% (43 cycles) | 19% | 34 |

- **2 MNQ on a 50k end-of-day-trailing evaluation is the best trade-off.** It roughly doubles the zero-edge pass rate, with a median of about 7 weeks per attempt.
- **1 MNQ passes more often but is too slow.** Around six months per attempt means monthly fees eat the advantage.
- **Intraday trailing does worse, and the gap grows with size.** It ratchets the floor on open profit, which a trend strategy gives back; without the protective stop, intraday trailing fell below the zero-edge baseline.

**Caveats. These are the reasons not to over-trust it.**
- **Profit is concentrated.** The top 3 months produced 38% of all profit, and April 2025 (the tariff-shock volatility) produced 19%. Without April 2025, the out-of-sample average is +$10.28 per trade (t 1.01).
- **Flat for 17 months.** From May 2025 to September 2026 it made +$95 in total per contract, about $0 per trade. 10 of 11 half-years are positive, but only 2025H2 lost, and it's the most recent. Momentum strategies earn in volatile, trending markets and chop in quiet ones, and it's not clear which regime comes next.
- **Out-of-sample alone it isn't significant** (t 1.40). The case rests on the full-sample t of 2.7, a published rule with no tuning, and the strong opposite-side control.
- **One instrument, 5 years.** It hasn't been tested on ES/MES or on data from before 2021.
- **It is not a scalp.** Trades last about two hours and there are about one a day.

## 8. Recommendations

1. **Don't trade the Bollinger-pullback scalp or buy evaluations for it.** No short-hold scalp tested here survives MNQ costs.
2. **If you want to attempt an evaluation, use the intraday momentum strategy:** MNQ, 50k account, **end-of-day** trailing drawdown, 2 MNQ, protective stop on.
   - Expect roughly half of attempts to fail even if the edge is real.
   - Given the flat last 17 months, **paper-trade it or run it on the cheapest evaluation first**, and set in advance how long a flat stretch you'll accept.
3. **Don't add filters to fix the flat period** (volatility-regime filters and the like). Both halves of the data have now been looked at, so there's no clean test left to validate a new filter. New evidence has to come from live or paper trading from here on, or from ES/MES data and pre-2021 history.
4. **Standing rule for any new signal:** decide the test in advance, split the data, report net t-stats, compare with the opposite-side control and the zero-edge pass rate, and require t ≥ 3 before believing a result from a large search.

## Appendix: how to reproduce

```bash
/usr/bin/python3 -c "import importlib.util as u; s=u.spec_from_file_location('p','Prop Firm Scalping backtest.py'); m=u.module_from_spec(s); s.loader.exec_module(m); m.main('MNQ')"
```

Use `main('GBPUSD')`, `main('MNQ_ALL_SESSIONS')` or `main('NQ')` for the other instruments.

```bash
/usr/bin/python3 "Prop Firm Intraday Momentum backtest.py"   # section 7
/usr/bin/python3 "Prop Firm Strategy Search.py"              # sections 5-6
```
