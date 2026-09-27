# coding: utf-8

# ---------------------------------------------------------------------------
# PROP FIRM SCALPING STRATEGY
# ---------------------------------------------------------------------------
# most retail scalping systems chase a high number of trades and end up
# fighting the spread. the goal of a prop firm evaluation is different from
# the goal of maximizing raw return: the account fails the moment a daily
# loss limit or an overall drawdown limit is breached, no matter how good
# the long run edge is. so the strategy below is built backwards from the
# risk rules rather than forwards from an indicator.
#
# the trading idea itself is deliberately simple, because simple + high
# win rate + strict filtering survives an evaluation far better than a
# clever but fragile edge:
#   1. only trade the London/New York overlap (roughly 08:00-12:00 EST),
#      the single most liquid window in FX, where spreads are tightest
#      and price behaves the most "textbook".
#   2. only trade WITH the prevailing short term trend (fast ema above/
#      below slow ema), never against it. a scalp is not a reversal bet.
#   3. only enter on a short term overextension back towards the trend,
#      i.e. buy a dip in an uptrend, sell a rip in a downtrend, using a
#      Bollinger Band as the overextension gauge and requiring price to
#      snap back inside the band as confirmation (no falling knives).
#   4. skip dead markets (nothing to scalp) and skip abnormal volatility
#      spikes (news events), using a rolling volatility percentile filter.
#   5. size the stop/target off recent volatility instead of a fixed pip
#      value, so the risk taken is consistent across calm and choppy days.
#
# none of this is new alpha, it is the same pullback-with-trend logic as
# 'Bollinger Bands Pattern Recognition backtest.py' and the session logic
# of 'London Breakout backtest.py' in this repository, recombined and
# wrapped with money management that a prop firm evaluation actually
# requires:
#   - fixed fractional risk per trade (default 0.5% of current equity)
#   - a daily loss circuit breaker well inside the typical 5% daily limit
#   - a max drawdown circuit breaker well inside the typical 10% overall
#     limit
#   - a profit target lock so the system stops taking on fresh risk once
#     the evaluation target is reached instead of giving back the payout
#   - a per day trade cap to prevent revenge trading / overtrading
#
# caveats (read before trading real money):
#   - the sample data is one month of 1 minute GBPUSD mid price with no
#     bid/ask spread, no commission and no slippage. real execution costs
#     will eat into the edge, especially on a strategy with a sub 1:1
#     average win. re-validate with your broker's own spread/commission
#     schedule and a much longer history before risking a live evaluation.
#   - one month of data is a single volatility regime. the parameters
#     below were checked to stay profitable on both halves of the sample
#     independently, but they are not immune to regime change.
#   - this is an educational backtest, not investment advice.
# ---------------------------------------------------------------------------

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# strategy parameters
# ---------------------------------------------------------------------------

EMA_FAST = 90            # ~1.5 hour trend filter on 1 min bars
EMA_SLOW = 300           # ~5 hour trend filter on 1 min bars
BB_WINDOW = 30           # bollinger band lookback for the pullback entry
BB_K = 1.3               # bollinger band width in standard deviations
VOL_WINDOW = 60          # rolling window used as an atr-like vol proxy
STOP_MULT = 3.0          # stop loss = STOP_MULT * rolling vol
TARGET_MULT = 2.0        # take profit = TARGET_MULT * rolling vol
MIN_VOL_PCT = 0.30       # skip the quietest 30% of volatility (nothing to scalp)
MAX_VOL_PCT = 0.97       # skip the wildest 3% of volatility (news spikes)
SESSION_START = '08:00'  # est, london/new york overlap begins
SESSION_END = '12:00'    # est, session hard close, flatten any open trade
MAX_HOLD_MINUTES = 45    # time stop, a scalp that stalls is not a scalp
MAX_TRADES_PER_DAY = 5   # trade cap to avoid overtrading

# ---------------------------------------------------------------------------
# instrument presets
# ---------------------------------------------------------------------------
# point_value = dollars earned per 1.0 unit of price movement per contract/
# unit (1 for a spot fx unit, 2 for MNQ - the Micro E-mini Nasdaq-100 future,
# whose multiplier is $2/index point). session times are the window judged
# most liquid/tradable for the instrument. futures need whole_contracts=True
# since you cannot buy 4.3 contracts.

INSTRUMENT_PRESETS = {
    'GBPUSD': dict(point_value=1.0, tick_size=0.0001, whole_contracts=False,
                    session_start='08:00', session_end='12:00', stop_mult=3.0, target_mult=2.0,
                    commission_round_trip=0.0, slippage_ticks=0.0,
                    tz_note='EST fixed (histdata.com convention)'),
    # session/stop/target below are the config that actually held up out of
    # sample on 5 years of real MNQ 1-min data - see the "MNQ findings" note
    # further down. commission/slippage are a low-cost-broker estimate
    # ($0.35/side + 1 tick/side): re-validate against your own broker.
    'MNQ': dict(point_value=2.0, tick_size=0.25, whole_contracts=True,
                 session_start='09:30', session_end='16:00', stop_mult=3.0, target_mult=1.5,
                 commission_round_trip=0.70, slippage_ticks=2.0,
                 tz_note='America/New_York (full RTH - see note below on why NOT just the open)'),
}

# ---------------------------------------------------------------------------
# MNQ findings (from backtesting on data/MNQ_1m_v2_clean.parquet, 5 years,
# 2021-09 to 2026-09, real OHLC bars with stop/target checked against bar
# high/low rather than close only)
# ---------------------------------------------------------------------------
# porting the FX parameters and session as-is (09:30-11:30 NY "open" window,
# stop=3x/target=2x vol) produces a profit factor of 0.98 and a slightly
# negative average R - i.e. no edge, not "less profitable", actually a
# loser. widening the session to the full RTH (09:30-16:00) and shortening
# the target relative to the stop (3x/1.5x) turns up a small, statistically
# consistent edge: ~56-59% win rate and profit factor ~1.02-1.05, holding up
# across every year 2021-2026 including a genuine out-of-sample 2024-2026
# test split. HOWEVER that gross edge averages only about $0.25-0.50 per
# micro contract per trade, which is smaller than a realistic round trip
# cost (commission + 1-2 ticks of slippage, roughly $1.50-2.00/contract on
# ~1,200 trades/year for this config). net of costs this specific
# architecture (1 minute bars, mean-reversion pullback against a slow ema
# trend filter) is NOT a tradeable scalp on MNQ - the edge is real but too
# thin to survive execution costs at this trade frequency. see
# statistics(..., label=) output for the gross-vs-net comparison main()
# prints for MNQ. widening the stop/target further (holding longer, trading
# less often) would dilute per-trade cost drag but stops being a "scalp";
# a different edge (breakout/momentum rather than mean-reversion) was not
# exhaustively tested and remains the most promising next step.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# prop firm evaluation parameters (buffered well inside typical rules)
# ---------------------------------------------------------------------------

INITIAL_EQUITY = 100000.0
RISK_PCT = 0.005           # risk 0.5% of current equity per trade
DAILY_LOSS_LIMIT_PCT = 0.02   # stop trading for the day at -2% (typical rule: -5%)
MAX_DRAWDOWN_LIMIT_PCT = 0.08 # stop trading altogether at -8% (typical rule: -10%)
PROFIT_TARGET_PCT = 0.10      # typical 1-step evaluation target: +10%

# two commonly used evaluation templates to check the results against
# (generic, illustrative numbers, not any specific firm's trademarked rules)
EVAL_TEMPLATES = {
    '1-step evaluation (10% target / 5% daily / 10% max loss)': dict(
        target=0.10, daily_loss=0.05, max_loss=0.10, min_days=4),
    '2-step verification (5% target / 5% daily / 10% max loss)': dict(
        target=0.05, daily_loss=0.05, max_loss=0.10, min_days=4),
}


def signal_generation(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW,
                       bb_win=BB_WINDOW, bb_k=BB_K, vol_win=VOL_WINDOW,
                       stop_mult=STOP_MULT, target_mult=TARGET_MULT,
                       min_vol_pct=MIN_VOL_PCT, max_vol_pct=MAX_VOL_PCT,
                       session_start=SESSION_START, session_end=SESSION_END,
                       max_hold=MAX_HOLD_MINUTES, max_trades_day=MAX_TRADES_PER_DAY):
    """scan 1 minute price data and return one row per completed trade.

    this only produces the trade list (side, entry/exit price, reason).
    position sizing and prop firm risk limits are applied afterwards in
    backtesting(), the same separation of concerns used elsewhere in this
    repository (signal generation is agnostic of account size).
    """

    d = df.copy()
    d['date'] = pd.to_datetime(d['date'])

    # trend filter, fast ema vs slow ema
    d['ema_fast'] = d['price'].ewm(span=ema_fast, adjust=False).mean()
    d['ema_slow'] = d['price'].ewm(span=ema_slow, adjust=False).mean()
    d['trend'] = np.where(d['ema_fast'] > d['ema_slow'], 1, -1)

    # bollinger band used purely as an overextension/pullback gauge
    d['bb_mid'] = d['price'].rolling(bb_win).mean()
    d['bb_std'] = d['price'].rolling(bb_win).std()
    d['bb_upper'] = d['bb_mid'] + bb_k * d['bb_std']
    d['bb_lower'] = d['bb_mid'] - bb_k * d['bb_std']

    # rolling std of price as a lightweight atr proxy (data has no high/low)
    d['vol'] = d['price'].rolling(vol_win).std().bfill()
    vol_lo, vol_hi = d['vol'].quantile(min_vol_pct), d['vol'].quantile(max_vol_pct)

    def _to_minutes(hhmm):
        h, m = str(hhmm).split(':')
        return int(h) * 60 + int(m)

    session_start_min = _to_minutes(session_start)
    session_end_min = _to_minutes(session_end)

    d['minute_of_day'] = d['date'].dt.hour * 60 + d['date'].dt.minute
    d['day'] = d['date'].dt.date
    in_session = ((d['minute_of_day'] >= session_start_min) & (d['minute_of_day'] < session_end_min)).values

    prices, lower, upper = d['price'].values, d['bb_lower'].values, d['bb_upper'].values
    trend, vol, minute_of_day, days = d['trend'].values, d['vol'].values, d['minute_of_day'].values, d['day'].values

    trades = []
    position = 0                  # 0 flat, 1 long, -1 short
    entry_price = entry_idx = stop_price = target_price = None
    trades_today = 0
    current_day = None
    was_below = was_above = False   # tracks whether price already poked outside the band

    n = len(d)
    for i in range(n):

        # new trading day, reset the daily trade counter and flatten
        # any position left open overnight (should not normally happen
        # given the hard session close below, kept as a safety net)
        if current_day != days[i]:
            current_day = days[i]
            trades_today = 0
            if position != 0:
                trades.append((entry_idx, i - 1, position, entry_price,
                                prices[i - 1], 'day_end', vol[entry_idx]))
                position = 0

        if position == 0:
            ok_vol = (not np.isnan(vol[i])) and (vol_lo <= vol[i] <= vol_hi) and vol[i] > 0
            can_trade = in_session[i] and trades_today < max_trades_day and \
                not np.isnan(lower[i]) and ok_vol

            if can_trade:
                # uptrend: wait for price to poke below the lower band,
                # then enter long once it snaps back inside (the pullback
                # is over, trend resumes)
                if trend[i] == 1 and prices[i] < lower[i]:
                    was_below = True
                elif trend[i] == 1 and was_below and prices[i] >= lower[i]:
                    position = 1
                    entry_price, entry_idx = prices[i], i
                    stop_price = entry_price - stop_mult * vol[i]
                    target_price = entry_price + target_mult * vol[i]
                    trades_today += 1
                    was_below = False
                else:
                    was_below = False

                # downtrend: mirror image
                if trend[i] == -1 and prices[i] > upper[i]:
                    was_above = True
                elif trend[i] == -1 and was_above and prices[i] <= upper[i]:
                    position = -1
                    entry_price, entry_idx = prices[i], i
                    stop_price = entry_price + stop_mult * vol[i]
                    target_price = entry_price - target_mult * vol[i]
                    trades_today += 1
                    was_above = False
                else:
                    was_above = False

        else:
            exit_reason = None
            if position == 1:
                if prices[i] <= stop_price:
                    exit_reason = 'stop'
                elif prices[i] >= target_price:
                    exit_reason = 'target'
            else:
                if prices[i] >= stop_price:
                    exit_reason = 'stop'
                elif prices[i] <= target_price:
                    exit_reason = 'target'

            # a scalp that neither hits target nor stop within the time
            # limit is no longer a scalp, get out
            if exit_reason is None and (i - entry_idx) >= max_hold:
                exit_reason = 'time'

            # hard flatten at the end of the liquid session
            if exit_reason is None and not in_session[i] and minute_of_day[i] >= session_end_min:
                exit_reason = 'session_end'

            if exit_reason is not None:
                trades.append((entry_idx, i, position, entry_price,
                                prices[i], exit_reason, vol[entry_idx]))
                position = 0

    if position != 0:
        trades.append((entry_idx, n - 1, position, entry_price,
                        prices[n - 1], 'eof', vol[entry_idx]))

    tr = pd.DataFrame(trades, columns=['entry_idx', 'exit_idx', 'side', 'entry_price',
                                        'exit_price', 'reason', 'entry_vol'])
    tr['pnl_price'] = (tr['exit_price'] - tr['entry_price']) * tr['side']
    tr['stop_dist'] = stop_mult * tr['entry_vol']
    tr['r_multiple'] = tr['pnl_price'] / tr['stop_dist']
    tr['entry_date'] = d['date'].values[tr['entry_idx']]
    tr['exit_date'] = d['date'].values[tr['exit_idx']]
    tr['day'] = tr['entry_date'].dt.date

    return tr, d


def signal_generation_ohlc(df, tz='America/New_York', ema_fast=EMA_FAST, ema_slow=EMA_SLOW,
                            bb_win=BB_WINDOW, bb_k=BB_K, vol_win=VOL_WINDOW,
                            vol_pctrank_lookback=500,
                            stop_mult=STOP_MULT, target_mult=TARGET_MULT,
                            min_vol_pct=MIN_VOL_PCT, max_vol_pct=MAX_VOL_PCT,
                            session_start=SESSION_START, session_end=SESSION_END,
                            max_hold=MAX_HOLD_MINUTES, max_trades_day=MAX_TRADES_PER_DAY):
    """same strategy as signal_generation(), adapted for real OHLC bars
    (futures data) instead of a single mid-price series:

      - stop/target are checked against the bar's high/low, not just its
        close, matching how a real stop/limit order (and TradingView's
        strategy tester) actually fills - this is a stricter, more
        realistic test than the fx prototype's close-only approximation.
      - the volatility filter uses a CAUSAL rolling percentile
        (pandas .rolling().rank(pct=True), the exact same thing as Pine's
        ta.percentrank) instead of signal_generation()'s whole-sample
        quantile. that whole-sample quantile is fine for a one-month
        sample where the price barely moves, but it both peeks at future
        data and silently assumes a stable volatility regime - neither
        holds over a multi-year sample where the instrument's price (and
        therefore its point-denominated volatility) can move several
        multiples, so it would misjudge "quiet" vs "wild" using a
        regime from years away.
      - day/session boundaries are computed in the instrument's own
        session timezone (tz), not the raw timestamp column's timezone.
    """

    d = df.copy()
    ts_utc = pd.to_datetime(d['timestamp'], utc=True)
    if tz.startswith('UTC') and (len(tz) == 3 or tz[3] in '+-'):
        # fixed offset, no daylight saving (matches Pine's "UTC-5" session
        # timezone convention exactly) - tz_convert would apply a real,
        # DST-shifting IANA zone instead, which is a different thing.
        offset_hours = int(tz[3:]) if len(tz) > 3 else 0
        d['date'] = ts_utc.dt.tz_localize(None) + pd.Timedelta(hours=offset_hours)
    else:
        d['date'] = ts_utc.dt.tz_convert(tz)
    d['price'] = d['close']

    d['ema_fast'] = d['close'].ewm(span=ema_fast, adjust=False).mean()
    d['ema_slow'] = d['close'].ewm(span=ema_slow, adjust=False).mean()
    d['trend'] = np.where(d['ema_fast'] > d['ema_slow'], 1, -1)

    d['bb_mid'] = d['close'].rolling(bb_win).mean()
    d['bb_std'] = d['close'].rolling(bb_win).std()
    d['bb_upper'] = d['bb_mid'] + bb_k * d['bb_std']
    d['bb_lower'] = d['bb_mid'] - bb_k * d['bb_std']

    d['vol'] = d['close'].rolling(vol_win).std()
    d['vol_pctrank'] = d['vol'].rolling(vol_pctrank_lookback).rank(pct=True)

    def _to_minutes(hhmm):
        h, m = str(hhmm).split(':')
        return int(h) * 60 + int(m)

    session_start_min = _to_minutes(session_start)
    session_end_min = _to_minutes(session_end)

    d['minute_of_day'] = d['date'].dt.hour * 60 + d['date'].dt.minute
    d['day'] = d['date'].dt.date
    in_session = ((d['minute_of_day'] >= session_start_min) & (d['minute_of_day'] < session_end_min)).values
    ok_vol_arr = ((d['vol'] > 0) & (d['vol_pctrank'] >= min_vol_pct) & (d['vol_pctrank'] <= max_vol_pct)).values

    opens, highs, lows, closes = d['open'].values, d['high'].values, d['low'].values, d['close'].values
    lower, upper, trend, vol = d['bb_lower'].values, d['bb_upper'].values, d['trend'].values, d['vol'].values
    minute_of_day, days = d['minute_of_day'].values, d['day'].values
    bb_ready = ~np.isnan(lower)

    trades = []
    position = 0
    entry_price = entry_idx = stop_price = target_price = None
    trades_today = 0
    current_day = None
    was_below = was_above = False

    n = len(d)
    for i in range(n):
        if current_day != days[i]:
            current_day = days[i]
            trades_today = 0
            if position != 0:
                trades.append((entry_idx, i - 1, position, entry_price, opens[i], 'day_end', vol[entry_idx]))
                position = 0

        if position == 0:
            can_trade = in_session[i] and trades_today < max_trades_day and bb_ready[i] and ok_vol_arr[i]
            if can_trade:
                if trend[i] == 1 and closes[i] < lower[i]:
                    was_below = True
                elif trend[i] == 1 and was_below and closes[i] >= lower[i]:
                    position = 1
                    entry_price, entry_idx = closes[i], i
                    stop_price = entry_price - stop_mult * vol[i]
                    target_price = entry_price + target_mult * vol[i]
                    trades_today += 1
                    was_below = False
                else:
                    was_below = False

                if trend[i] == -1 and closes[i] > upper[i]:
                    was_above = True
                elif trend[i] == -1 and was_above and closes[i] <= upper[i]:
                    position = -1
                    entry_price, entry_idx = closes[i], i
                    stop_price = entry_price + stop_mult * vol[i]
                    target_price = entry_price - target_mult * vol[i]
                    trades_today += 1
                    was_above = False
                else:
                    was_above = False
        else:
            exit_reason = None
            exit_price = None
            if position == 1:
                if lows[i] <= stop_price:
                    exit_reason, exit_price = 'stop', stop_price
                elif highs[i] >= target_price:
                    exit_reason, exit_price = 'target', target_price
            else:
                if highs[i] >= stop_price:
                    exit_reason, exit_price = 'stop', stop_price
                elif lows[i] <= target_price:
                    exit_reason, exit_price = 'target', target_price

            if exit_reason is None and (i - entry_idx) >= max_hold:
                exit_reason, exit_price = 'time', closes[i]
            if exit_reason is None and not in_session[i] and minute_of_day[i] >= session_end_min:
                exit_reason, exit_price = 'session_end', closes[i]

            if exit_reason is not None:
                trades.append((entry_idx, i, position, entry_price, exit_price, exit_reason, vol[entry_idx]))
                position = 0

    if position != 0:
        trades.append((entry_idx, n - 1, position, entry_price, closes[n - 1], 'eof', vol[entry_idx]))

    tr = pd.DataFrame(trades, columns=['entry_idx', 'exit_idx', 'side', 'entry_price',
                                        'exit_price', 'reason', 'entry_vol'])
    tr['pnl_price'] = (tr['exit_price'] - tr['entry_price']) * tr['side']
    tr['stop_dist'] = stop_mult * tr['entry_vol']
    tr['r_multiple'] = tr['pnl_price'] / tr['stop_dist']
    # index straight off d['date'] (already in the right local time/tz from
    # above) rather than round-tripping through pd.to_datetime(utc=True),
    # which would silently mis-handle the tz-naive fixed-offset branch.
    d_date_reset = d['date'].reset_index(drop=True)
    tr['entry_date'] = d_date_reset.loc[tr['entry_idx']].values
    tr['exit_date'] = d_date_reset.loc[tr['exit_idx']].values
    tr['day'] = pd.DatetimeIndex(tr['entry_date']).date

    return tr, d


def backtesting(tr, initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT,
                 daily_loss_pct=DAILY_LOSS_LIMIT_PCT,
                 max_dd_pct=MAX_DRAWDOWN_LIMIT_PCT,
                 profit_target_pct=PROFIT_TARGET_PCT,
                 point_value=1.0, whole_contracts=False,
                 commission_round_trip=0.0, slippage_ticks=0.0, tick_size=0.0):
    """apply fixed fractional position sizing and prop firm risk limits
    to the trade list produced by signal_generation().

    every trade risks a fixed % of CURRENT equity (so the account can
    never lose more than that % on a single trade, win or lose big is
    always scaled the same way). three circuit breakers sit on top:
      - daily_loss_pct   : stop taking new trades for the rest of the day
      - max_dd_pct        : stop taking new trades for good (would-be
                             evaluation failure, the whole point of the
                             conservative RISK_PCT default is to make
                             this basically unreachable)
      - profit_target_pct : once hit, stop taking on fresh risk, lock in
                             the pass/payout instead of giving it back

    point_value converts a price move into a dollar move per unit/contract
    (1.0 for a spot fx unit, 2.0 for MNQ). whole_contracts=True floors the
    computed size to a whole number and SKIPS the trade if that rounds to
    zero, since futures cannot be sized fractionally the way fx units can.

    commission_round_trip (dollars/contract) and slippage_ticks (round trip,
    e.g. 2 = 1 tick each way) model real execution cost per contract per
    trade. both default to 0 (frictionless), matching every other backtest
    in this repository unless you explicitly opt in.
    """
    cost_per_unit = commission_round_trip + slippage_ticks * tick_size * point_value

    equity = initial_equity
    peak_equity = initial_equity
    max_dd = 0.0
    day_start_equity = initial_equity
    current_day = None
    halted = False
    day_halted = False
    target_hit_day = None
    rows = []

    for _, row in tr.iterrows():
        day = row['day']
        if current_day != day:
            current_day = day
            day_start_equity = equity
            day_halted = False

        if halted or day_halted or target_hit_day is not None:
            rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': equity})
            continue

        risk_amount = equity * risk_pct
        units = risk_amount / (row['stop_dist'] * point_value)
        if whole_contracts:
            units = np.floor(units)
            if units < 1:
                rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': equity})
                continue

        trade_pnl = units * (row['pnl_price'] * point_value - cost_per_unit)
        equity += trade_pnl

        peak_equity = max(peak_equity, equity)
        dd = (peak_equity - equity) / peak_equity
        max_dd = max(max_dd, dd)

        if (day_start_equity - equity) / day_start_equity >= daily_loss_pct:
            day_halted = True
        if dd >= max_dd_pct:
            halted = True
        if target_hit_day is None and (equity - initial_equity) / initial_equity >= profit_target_pct:
            target_hit_day = day

        rows.append({**row, 'executed': True, 'trade_pnl': trade_pnl, 'equity': equity})

    out = pd.DataFrame(rows)
    summary = dict(initial_equity=initial_equity, final_equity=equity,
                    max_dd=max_dd, halted=halted, target_hit_day=target_hit_day)
    return out, summary


def backtesting_v5_legacy(tr, initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT,
                           daily_loss_pct=DAILY_LOSS_LIMIT_PCT,
                           max_dd_pct=MAX_DRAWDOWN_LIMIT_PCT,
                           profit_target_pct=PROFIT_TARGET_PCT,
                           point_value=1.0):
    """faithfully reproduces the position sizing of the ORIGINAL v5 Pine
    script (the one attached and re-tested by hand in TradingView), bug
    and all, purely so its reported result can be checked against real
    MNQ data rather than argued about.

    the v5 script computes qty = riskAmount / stopDist with NO division by
    point_value, and allows fractional qty (no whole-contract floor). on a
    spot fx pair (point_value == 1) that is exactly correct. on MNQ
    (point_value == 2) it is not: TradingView still multiplies the
    realized profit of every filled contract by the instrument's real
    point value automatically, so this sizing formula silently asks for
    2x the number of contracts the intended risk_pct implies - i.e. every
    trade actually risks 2x the configured risk_pct. commission and
    slippage are 0, matching that script's defaults. see backtesting() for
    the corrected sizing (divides by point_value, floors to whole
    contracts) used everywhere else in this file.
    """
    equity = initial_equity
    peak_equity = initial_equity
    max_dd = 0.0
    day_start_equity = initial_equity
    current_day = None
    halted = False
    day_halted = False
    target_hit_day = None
    rows = []

    for _, row in tr.iterrows():
        day = row['day']
        if current_day != day:
            current_day = day
            day_start_equity = equity
            day_halted = False

        if halted or day_halted or target_hit_day is not None:
            rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': equity})
            continue

        risk_amount = equity * risk_pct
        units = risk_amount / row['stop_dist']            # <- no point_value division (the bug)
        if units <= 0:
            rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': equity})
            continue

        trade_pnl = units * row['pnl_price'] * point_value  # TradingView still applies it here
        equity += trade_pnl

        peak_equity = max(peak_equity, equity)
        dd = (peak_equity - equity) / peak_equity
        max_dd = max(max_dd, dd)

        if (day_start_equity - equity) / day_start_equity >= daily_loss_pct:
            day_halted = True
        if dd >= max_dd_pct:
            halted = True
        if target_hit_day is None and (equity - initial_equity) / initial_equity >= profit_target_pct:
            target_hit_day = day

        rows.append({**row, 'executed': True, 'trade_pnl': trade_pnl, 'equity': equity})

    out = pd.DataFrame(rows)
    summary = dict(initial_equity=initial_equity, final_equity=equity,
                    max_dd=max_dd, halted=halted, target_hit_day=target_hit_day)
    return out, summary


def backtesting_cycles(tr, initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT,
                        daily_loss_pct=DAILY_LOSS_LIMIT_PCT,
                        max_dd_pct=MAX_DRAWDOWN_LIMIT_PCT,
                        profit_target_pct=PROFIT_TARGET_PCT,
                        point_value=1.0, whole_contracts=False,
                        commission_round_trip=0.0, slippage_ticks=0.0, tick_size=0.0,
                        legacy_sizing=False):
    """same money management as backtesting(), but over a multi-year trade
    list a single continuous run is the wrong lens: the first time the
    account fails its drawdown limit, backtesting() locks it forever and
    the rest of the history just sits idle, which answers "would this one
    attempt survive" rather than the question that actually matters for
    "steady payouts" - if you kept re-entering a fresh evaluation (or a
    fresh funded round) after every pass or fail, how often would you
    actually pass, and how long does a pass or a fail typically take?

    this resets equity/peak/day-tracking back to initial_equity every time
    a cycle ends (profit target hit = pass, max drawdown breached = fail),
    and returns one row per cycle instead of one frozen equity curve.
    """
    cost_per_unit = commission_round_trip + slippage_ticks * tick_size * point_value

    def _new_cycle_state(start_day):
        return dict(equity=initial_equity, peak_equity=initial_equity, max_dd=0.0,
                    day_start_equity=initial_equity, current_day=None, day_halted=False,
                    n_trades=0, start_day=start_day)

    cycles = []
    rows = []
    state = _new_cycle_state(None)

    for _, row in tr.iterrows():
        day = row['day']
        if state['start_day'] is None:
            state['start_day'] = day
        if state['current_day'] != day:
            state['current_day'] = day
            state['day_start_equity'] = state['equity']
            state['day_halted'] = False

        if state['day_halted']:
            rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': state['equity']})
            continue

        risk_amount = state['equity'] * risk_pct
        # legacy_sizing replicates the original v5 script's formula, which
        # omits the point_value division (see backtesting_v5_legacy()) -
        # only meaningful when point_value != 1.
        units = risk_amount / row['stop_dist'] if legacy_sizing else risk_amount / (row['stop_dist'] * point_value)
        if whole_contracts:
            units = np.floor(units)
            if units < 1:
                rows.append({**row, 'executed': False, 'trade_pnl': 0.0, 'equity': state['equity']})
                continue

        trade_pnl = units * (row['pnl_price'] * point_value - cost_per_unit)
        state['equity'] += trade_pnl
        state['n_trades'] += 1

        state['peak_equity'] = max(state['peak_equity'], state['equity'])
        dd = (state['peak_equity'] - state['equity']) / state['peak_equity']
        state['max_dd'] = max(state['max_dd'], dd)

        if (state['day_start_equity'] - state['equity']) / state['day_start_equity'] >= daily_loss_pct:
            state['day_halted'] = True

        rows.append({**row, 'executed': True, 'trade_pnl': trade_pnl, 'equity': state['equity']})

        outcome = None
        if dd >= max_dd_pct:
            outcome = 'failed_drawdown'
        elif (state['equity'] - initial_equity) / initial_equity >= profit_target_pct:
            outcome = 'passed'

        if outcome is not None:
            cycles.append(dict(outcome=outcome, start_day=state['start_day'], end_day=day,
                                n_trades=state['n_trades'], final_equity=state['equity'],
                                max_dd=state['max_dd']))
            state = _new_cycle_state(None)

    # an in-progress cycle at the end of the data isn't a pass or a fail yet
    if state['n_trades'] > 0:
        cycles.append(dict(outcome='in_progress', start_day=state['start_day'], end_day=None,
                            n_trades=state['n_trades'], final_equity=state['equity'],
                            max_dd=state['max_dd']))

    out = pd.DataFrame(rows)
    cycles_df = pd.DataFrame(cycles)
    return out, cycles_df


def summarize_cycles(cycles_df, label='MNQ - REPEATED EVALUATION CYCLES'):

    finished = cycles_df[cycles_df['outcome'] != 'in_progress']
    passed = finished[finished['outcome'] == 'passed']
    failed = finished[finished['outcome'] == 'failed_drawdown']

    print('=' * 60)
    print(label)
    print('=' * 60)
    print(f"cycles completed          : {len(finished)}  (passed: {len(passed)}, failed: {len(failed)})")
    if len(finished) > 0:
        print(f"pass rate                 : {len(passed)/len(finished):.1%}")
        print(f"avg trades per cycle      : {finished['n_trades'].mean():.1f}")
        print(f"avg trading days per cycle: {finished.apply(lambda r: (r['end_day']-r['start_day']).days, axis=1).mean():.1f}")
    if len(passed) > 0:
        print(f"avg trades to pass        : {passed['n_trades'].mean():.1f}")
    if len(failed) > 0:
        print(f"avg trades to fail        : {failed['n_trades'].mean():.1f}")
    still_running = cycles_df[cycles_df['outcome'] == 'in_progress']
    if len(still_running) > 0:
        row = still_running.iloc[0]
        print(f"final (unfinished) cycle  : {row['n_trades']} trades in, "
              f"equity {row['final_equity']:,.0f} ({(row['final_equity']/INITIAL_EQUITY-1):+.2%}), "
              f"drawdown so far {row['max_dd']:.2%}")
    return dict(n_cycles=len(finished), pass_rate=len(passed)/len(finished) if len(finished) else np.nan)


def statistics(out, summary, label='PROP FIRM SCALPING - BACKTEST RESULTS'):

    executed = out[out['executed']]
    skipped = (~out['executed']).sum()

    win_rate = (executed['trade_pnl'] > 0).mean()
    gross_win = executed.loc[executed['trade_pnl'] > 0, 'trade_pnl'].sum()
    gross_loss = -executed.loc[executed['trade_pnl'] < 0, 'trade_pnl'].sum()
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf

    daily_pnl = executed.groupby('day')['trade_pnl'].sum()
    total_profit = executed['trade_pnl'].sum()
    total_return_pct = (summary['final_equity'] / summary['initial_equity'] - 1) * 100
    days_traded = out['day'].nunique()

    print('=' * 60)
    print(label)
    print('=' * 60)
    print(f"trades generated          : {len(out)}")
    print(f"trades executed           : {int(executed.shape[0])} (skipped by risk limits: {skipped})")
    print(f"win rate                  : {win_rate:.1%}")
    print(f"profit factor             : {profit_factor:.2f}")
    print(f"average R multiple        : {executed['r_multiple'].mean():.3f}")
    print(f"total return              : {total_return_pct:.2f}%")
    print(f"max drawdown              : {summary['max_dd']:.2%}")
    print(f"trading days              : {days_traded}")
    print(f"best day                  : ${daily_pnl.max():,.2f}  ({daily_pnl.max()/summary['initial_equity']:.2%} of equity)")
    print(f"worst day                 : ${daily_pnl.min():,.2f}  ({daily_pnl.min()/summary['initial_equity']:.2%} of equity)")

    # consistency check: no single day should dominate total profit, a
    # rule many prop firms enforce explicitly (e.g. no day > 30-50% of
    # total profit at time of payout)
    consistency_pct = daily_pnl.max() / total_profit if total_profit > 0 else np.nan
    print(f"best day as % of profit   : {consistency_pct:.1%}  (lower is more consistent)")
    print(f"account halted on dd limit: {summary['halted']}")
    print(f"profit target reached on  : {summary['target_hit_day']}")

    print('-' * 60)
    print('evaluation template check (illustrative, generic rule sets)')
    print('-' * 60)
    worst_day_pct = -daily_pnl.min() / summary['initial_equity']
    for name, rule in EVAL_TEMPLATES.items():
        passed_target = total_return_pct / 100 >= rule['target']
        passed_daily = worst_day_pct <= rule['daily_loss']
        passed_maxloss = summary['max_dd'] <= rule['max_loss']
        passed_days = days_traded >= rule['min_days']
        verdict = 'PASS' if all([passed_target, passed_daily, passed_maxloss, passed_days]) else 'not yet'
        print(f"{name}: {verdict}")
        print(f"    target   {total_return_pct/100:.2%} >= {rule['target']:.0%}  -> {passed_target}")
        print(f"    daily dd {worst_day_pct:.2%} <= {rule['daily_loss']:.0%}  -> {passed_daily}")
        print(f"    max dd   {summary['max_dd']:.2%} <= {rule['max_loss']:.0%}  -> {passed_maxloss}")
        print(f"    days     {days_traded} >= {rule['min_days']}       -> {passed_days}")

    return dict(win_rate=win_rate, profit_factor=profit_factor,
                total_return_pct=total_return_pct, max_dd=summary['max_dd'],
                consistency_pct=consistency_pct)


def plot(d, out, summary, title_prefix='Prop Firm Scalping',
         equity_path='preview/prop firm scalping equity curve.png',
         session_path='preview/prop firm scalping sample session.png'):

    executed = out[out['executed']].copy()

    # equity curve
    fig = plt.figure()
    ax = fig.add_subplot(111)
    equity_curve = pd.concat([
        pd.Series([summary['initial_equity']], index=[executed['entry_date'].iloc[0]]),
        executed.set_index('exit_date')['equity']
    ])
    equity_curve.plot(ax=ax)
    plt.title(f'{title_prefix} - Equity Curve')
    plt.ylabel('equity ($)')
    plt.xlabel('date')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(equity_path)
    plt.close(fig)

    # zoom into a single sample day to visualize entries/exits against price
    sample_day = executed['day'].iloc[len(executed) // 2]
    day_prices = d[d['day'] == sample_day]
    day_trades = executed[executed['day'] == sample_day]

    fig = plt.figure()
    bx = fig.add_subplot(111)
    bx.plot(day_prices['date'], day_prices['price'], label='price', zorder=1)
    bx.plot(day_prices['date'], day_prices['bb_upper'], linestyle=':', c='#BC8F8F', label='upper band')
    bx.plot(day_prices['date'], day_prices['bb_lower'], linestyle=':', c='#FF4500', label='lower band')

    longs = day_trades[day_trades['side'] == 1]
    shorts = day_trades[day_trades['side'] == -1]
    bx.scatter(longs['entry_date'], longs['entry_price'], marker='^', c='g', s=80, label='LONG', zorder=2)
    bx.scatter(shorts['entry_date'], shorts['entry_price'], marker='v', c='r', s=80, label='SHORT', zorder=2)
    bx.scatter(day_trades['exit_date'], day_trades['exit_price'], marker='x', c='k', s=50, label='exit', zorder=2)

    plt.title(f'{title_prefix} - Sample Session ({sample_day})')
    plt.ylabel('price')
    plt.xlabel('time')
    plt.legend(loc='best')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(session_path)
    plt.close(fig)


def main(instrument='GBPUSD', csv_path=None):

    preset = INSTRUMENT_PRESETS[instrument]
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if instrument == 'MNQ':
        if csv_path is None:
            csv_path = os.path.join(base_dir, 'data', 'MNQ_1m_v2_clean.parquet')
        df = pd.read_parquet(csv_path)

        tr, d = signal_generation_ohlc(df, tz='America/New_York',
                                        stop_mult=preset['stop_mult'], target_mult=preset['target_mult'],
                                        session_start=preset['session_start'], session_end=preset['session_end'])

        # gross (frictionless, like every other backtest in this repo) vs
        # net of a realistic commission+slippage estimate - see the "MNQ
        # findings" note above for why this comparison is the whole point.
        out_gross, summary_gross = backtesting(tr, point_value=preset['point_value'],
                                                 whole_contracts=preset['whole_contracts'])
        statistics(out_gross, summary_gross, label='MNQ - GROSS (frictionless, no commission/slippage)')

        print()
        out_net, summary_net = backtesting(tr, point_value=preset['point_value'],
                                            whole_contracts=preset['whole_contracts'],
                                            commission_round_trip=preset['commission_round_trip'],
                                            slippage_ticks=preset['slippage_ticks'],
                                            tick_size=preset['tick_size'])
        statistics(out_net, summary_net,
                   label=f"MNQ - NET (commission ${preset['commission_round_trip']:.2f}/contract "
                         f"+ {preset['slippage_ticks']:.0f} ticks slippage per round trip)")

        # a single continuous run halts forever at the first drawdown
        # breach - see backtesting_cycles()'s docstring for why that isn't
        # the right way to read 5 years of "would this pass evaluation
        # after evaluation" data.
        print()
        _, cycles_gross = backtesting_cycles(tr, point_value=preset['point_value'],
                                              whole_contracts=preset['whole_contracts'])
        summarize_cycles(cycles_gross, label='MNQ - REPEATED CYCLES, GROSS (frictionless)')
        print()
        _, cycles_net = backtesting_cycles(tr, point_value=preset['point_value'],
                                            whole_contracts=preset['whole_contracts'],
                                            commission_round_trip=preset['commission_round_trip'],
                                            slippage_ticks=preset['slippage_ticks'],
                                            tick_size=preset['tick_size'])
        summarize_cycles(cycles_net, label='MNQ - REPEATED CYCLES, NET of commission/slippage')

        plot(d, out_net, summary_net, title_prefix='Prop Firm Scalping (MNQ, net of cost)',
             equity_path=os.path.join(base_dir, 'preview', 'prop firm scalping mnq equity curve.png'),
             session_path=os.path.join(base_dir, 'preview', 'prop firm scalping mnq sample session.png'))
        return

    if csv_path is None:
        csv_path = os.path.join(base_dir, 'data', 'gbpusd.csv')
    df = pd.read_csv(csv_path)

    tr, d = signal_generation(df, session_start=preset['session_start'],
                               session_end=preset['session_end'])
    out, summary = backtesting(tr, point_value=preset['point_value'],
                                whole_contracts=preset['whole_contracts'])
    statistics(out, summary)
    plot(d, out, summary)


if __name__ == '__main__':
    main()
