# Prop Firm Scalping: Strategy Review

*Review date: 27 September 2026. Data: 5 years of MNQ 1-minute bars (Sep 2021 – Sep 2026) and one month of GBPUSD 1-minute prices (June 2018).*

## Verdict

- **The scalping strategy has no edge on MNQ.** In its best configuration it makes +0.007R per trade before costs (t-stat 0.93, which can't be told apart from zero) and loses −0.007R per trade after costs.
- **It is worse than luck in prop firm evaluations.** After costs it passes 14–25% of simulated evaluations. A strategy with the same payoff shape and zero edge passes 27–34%.
- **Use MNQ, not NQ, for prop accounts.** One NQ contract risks about $1,400 at a typical stop, so on a 50k evaluation 94–99% of trades can't be sized at all.
- **The best lead is not the scalp.** A 30-minute opening range breakout on MNQ beat the zero-edge pass rate (42–52% vs 26–30% on a 50k account). It is still not statistically proven and is weakening in 2025–26, so treat it as the next thing to research, not something to trade.

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

## 5. The opening range breakout (research lead, not a strategy yet)

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

Before any money goes into it:
- test on ES/MES and at least one non-equity market;
- test a short-only or trend-neutral version, to separate the breakout from the bull market;
- walk-forward it with the range length and target chosen only on past data.

## 6. Recommendations

1. **Do not trade the scalping strategy or buy evaluations for it.** Keep it as a well-instrumented test harness; that's what it's good for now.
2. **If you do take a futures evaluation:** MNQ, 50k size, end-of-day trailing drawdown, fixed $400–500 risk per trade, New York hours only.
3. **Next research step:** build the opening range breakout properly (Python plus Pine, reusing `backtesting_futures_prop()` and `zero_edge_trades()`), then run the checks in section 5.
4. **Standing rule for any new signal:** report t-stat and costs from the first run, compare pass rates with the zero-edge baseline, and given how many configurations this repo has already tried, require t ≥ 3 before believing it.

## Appendix: how to reproduce

```bash
/usr/bin/python3 -c "import importlib.util as u; s=u.spec_from_file_location('p','Prop Firm Scalping backtest.py'); m=u.module_from_spec(s); s.loader.exec_module(m); m.main('MNQ')"
```

Use `main('GBPUSD')`, `main('MNQ_ALL_SESSIONS')` or `main('NQ')` for the other instruments. The opening range breakout numbers came from a one-off research script that is not yet in the repo.
