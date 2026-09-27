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
SESSION_START = 8        # est, london/new york overlap begins
SESSION_END = 12         # est, session hard close, flatten any open trade
MAX_HOLD_MINUTES = 45    # time stop, a scalp that stalls is not a scalp
MAX_TRADES_PER_DAY = 5   # trade cap to avoid overtrading

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

    d['hour'] = d['date'].dt.hour
    d['day'] = d['date'].dt.date
    in_session = ((d['hour'] >= session_start) & (d['hour'] < session_end)).values

    prices, lower, upper = d['price'].values, d['bb_lower'].values, d['bb_upper'].values
    trend, vol, hours, days = d['trend'].values, d['vol'].values, d['hour'].values, d['day'].values

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
            if exit_reason is None and not in_session[i] and hours[i] >= session_end:
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


def backtesting(tr, initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT,
                 daily_loss_pct=DAILY_LOSS_LIMIT_PCT,
                 max_dd_pct=MAX_DRAWDOWN_LIMIT_PCT,
                 profit_target_pct=PROFIT_TARGET_PCT):
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
        units = risk_amount / row['stop_dist']
        trade_pnl = units * row['pnl_price']
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


def statistics(out, summary):

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
    print('PROP FIRM SCALPING - BACKTEST RESULTS')
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


def plot(d, out):

    executed = out[out['executed']].copy()

    # equity curve
    fig = plt.figure()
    ax = fig.add_subplot(111)
    equity_curve = pd.concat([
        pd.Series([INITIAL_EQUITY], index=[executed['entry_date'].iloc[0]]),
        executed.set_index('exit_date')['equity']
    ])
    equity_curve.plot(ax=ax)
    plt.title('Prop Firm Scalping - Equity Curve')
    plt.ylabel('equity ($)')
    plt.xlabel('date')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('preview/prop firm scalping equity curve.png')
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

    plt.title(f'Prop Firm Scalping - Sample Session ({sample_day})')
    plt.ylabel('price')
    plt.xlabel('time')
    plt.legend(loc='best')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('preview/prop firm scalping sample session.png')
    plt.close(fig)


def main():

    base_dir = os.path.dirname(os.path.abspath(__file__))
    df = pd.read_csv(os.path.join(base_dir, 'data', 'gbpusd.csv'))

    tr, d = signal_generation(df)
    out, summary = backtesting(tr)
    statistics(out, summary)
    plot(d, out)


if __name__ == '__main__':
    main()
