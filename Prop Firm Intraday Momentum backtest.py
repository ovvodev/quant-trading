# coding: utf-8

# ---------------------------------------------------------------------------
# PROP FIRM INTRADAY MOMENTUM (NOISE AREA) STRATEGY
# ---------------------------------------------------------------------------
# this is what came out of searching for the best short-term strategy for a
# futures prop firm evaluation on 5 years of MNQ 1 minute data (see
# 'Prop Firm Scalping review.md'). the short answer of that search is that
# nothing which holds a trade for minutes survives costs on MNQ - every
# true scalp tested (bollinger pullback, vwap reversion, vwap trend
# pullback) loses after commission and slippage. the one idea that held up
# in and out of sample, with direction mattering and costs barely
# mattering, is intraday MOMENTUM held for 1-2 hours.
#
# the rules are taken unchanged from Zarattini, Aziz & Barbon (2024),
# "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF
# (SPY)", which is exactly why they are credible here: the parameters were
# published on a different instrument before this data was looked at, so
# there was nothing for us to overfit.
#   1. the "noise area": for every minute of the day, sigma(t) = average,
#      over the last 14 days, of |close(t) / today's open - 1|, i.e. how
#      far price usually wanders from the open by that time of day.
#   2. bands: upper = max(open, prev close) * (1 + sigma(t)),
#             lower = min(open, prev close) * (1 - sigma(t)).
#      using the previous close as well as the open absorbs overnight gaps.
#   3. only at 10:00, 10:30, ... 15:30 New York: if price closes above the
#      upper band go long, below the lower band go short. inside the band
#      is noise - do nothing.
#   4. trailing exit, checked at the same half hours: close a long when
#      price falls back below max(upper band, session vwap), a short when
#      it rises above min(lower band, session vwap). flat at 16:00.
# one addition, chosen on 2021-09..2024-03 data only and confirmed on
# 2024-04..2026-09: a protective stop one noise-band width (sigma * open)
# from entry, checked every minute. it barely changes the average trade
# but cuts the worst single trade from -$648 to -$438 per MNQ contract,
# which is what matters against a $2,000 prop firm max loss.
#
# results on MNQ, 2021-09 to 2026-09, rolls back-adjusted, $0.70 round trip
# commission + 1 tick slippage per fill (see main() output):
#   - ~225 trades a year, ~40% winners, winners ~2x the size of losers
#   - about +$18 per contract per trade net, t-stat ~2.7, positive in
#     both the in-sample and out-of-sample halves and in every year
#   - trading the OPPOSITE side loses about the same amount (t -3.2), so
#     the direction call is real, not just the Nasdaq's upward drift
#   - doubling costs still leaves ~+$17 per trade
#   - 50k evaluation, end-of-day trailing $2k, 2 MNQ: passes ~48% of
#     repeated evaluations vs ~23% for a zero-edge strategy, median ~7 weeks
# caveats:
#   - out of sample alone it is t ~1.4: consistent with in sample, but not
#     independently significant. 5 years of one instrument is one sample.
#   - it is a trend strategy: it gives back open profit before exiting.
#     under INTRADAY-trailing prop rules that open profit ratchets the
#     drawdown floor up; pass rates are lower there, and the gap to END-OF-
#     DAY trailing widens as size grows (without the protective stop it
#     fell below the zero-edge baseline). prefer end-of-day trailing rules.
#   - max drawdown ~$3,600 per contract over 5 years: a 2 MNQ evaluation
#     will fail outright in the bad stretches - the edge shows up as a
#     better-than-luck pass RATE, not as every attempt passing.
#   - profit is concentrated in volatile stretches: the top 3 months made
#     38% of it, April 2025 alone 19%, and from May 2025 to September 2026
#     it made ~$0 per trade. momentum earns in trending markets and chops in
#     quiet ones - paper trade it before paying for an evaluation.
#   - not a scalp - average hold ~2 hours.
#   - this is an educational backtest, not investment advice.
# ---------------------------------------------------------------------------

import os
import importlib.util
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# the prop firm rule simulators, cost model and roll adjustment are shared
# with the scalping backtest rather than duplicated here
_base = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('pfs', os.path.join(_base, 'Prop Firm Scalping backtest.py'))
pfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pfs)

LOOKBACK_DAYS = 14        # days averaged for the noise area (published value)
CHECK_EVERY = 30          # minutes between entry/exit checks (published value)
FIRST_CHECK = '10:00'
STOP_BAND_MULT = 1.0      # protective stop = 1 noise-band width from entry
RTH_OPEN, RTH_CLOSE = 570, 960   # 09:30 / 16:00 in minutes after midnight

POINT_VALUE, TICK_SIZE = 2.0, 0.25              # MNQ
COMMISSION_RT, SLIPPAGE_TICKS = 0.70, 1.0       # per contract, per market fill
SPLIT_DAY = pd.Timestamp('2024-04-01').date()   # in sample before, out of sample after


def build_days(df, tz='America/New_York'):
    """cut a 1 minute futures series into complete regular-hours sessions,
    each with a session vwap anchored at 09:30 (not the 18:00 globex open)."""

    ny = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(tz)
    d = df.assign(day=ny.dt.date.values, mod=(ny.dt.hour * 60 + ny.dt.minute).values)
    rth = d[(d['mod'] >= RTH_OPEN) & (d['mod'] < RTH_CLOSE)]

    days = []
    for day, x in rth.groupby('day', sort=True):
        # full sessions only - half days (early close) and data gaps skipped
        if len(x) < 370 or x['mod'].iloc[0] != RTH_OPEN:
            continue
        h, l, c = x['high'].values, x['low'].values, x['close'].values
        v = np.maximum(x['volume'].values.astype(float), 1.0)
        tp = (h + l + c) / 3
        days.append(dict(day=day, mod=x['mod'].values, open=x['open'].values, high=h, low=l, close=c,
                         volume=v, vwap=np.cumsum(v * tp) / np.cumsum(v)))
    for i, s in enumerate(days):
        s['prev_close'] = days[i - 1]['close'][-1] if i > 0 else np.nan
    return days


def resample_days(days, minutes):
    """turn 1 minute sessions into `minutes`-minute bars, the way a TradingView
    chart of that timeframe sees them - to test the Pine script's timeframe.

    each bar is labelled by its LAST minute (a 5 minute bar 09:55-09:59 is
    labelled 599, like the 1 minute bar that closes at 10:00), so the half
    hour checks in signal_generation() land on the same closes as long as
    `minutes` divides 30. vwap is rebuilt from the bars' own hlc3 and volume,
    as Pine computes it, and the protective stop is checked against each
    bar's high/low - one bar is the finest resolution the chart has.
    """
    if 30 % minutes:
        raise ValueError('bar size must divide 30 minutes')
    out = []
    for s in days:
        b = (s['mod'] - RTH_OPEN) // minutes
        g = pd.DataFrame(dict(b=b, o=s['open'], h=s['high'], l=s['low'], c=s['close'], v=s['volume'])).groupby('b')
        a = g.agg(o=('o', 'first'), h=('h', 'max'), l=('l', 'min'), c=('c', 'last'), v=('v', 'sum'))
        tp = (a['h'] + a['l'] + a['c']).values / 3
        out.append(dict(day=s['day'], mod=RTH_OPEN + (a.index.values + 1) * minutes - 1,
                        open=a['o'].values, high=a['h'].values, low=a['l'].values, close=a['c'].values,
                        volume=a['v'].values, vwap=np.cumsum(a['v'].values * tp) / np.cumsum(a['v'].values),
                        prev_close=s['prev_close']))
    return out


def evaluation_starts(tr, rule, contracts, every='W-MON', **cost):
    """start ONE evaluation on each start date (default: every Monday) and
    follow it to pass or fail - "if I had bought an evaluation that week,
    what would have happened?". returns one row per start."""
    fixed = tr.copy()
    fixed['stop_dist'] = 1.0
    fixed['r_multiple'] = fixed['pnl_price']
    kw = dict(rule, risk_usd=contracts * POINT_VALUE, point_value=POINT_VALUE, tick_size=TICK_SIZE, **cost)
    rows = []
    for start in pd.date_range(fixed['day'].min(), fixed['day'].max(), freq=every).date:
        cyc = pfs.backtesting_futures_prop(fixed[fixed['day'] >= start], **kw)
        if len(cyc) == 0:
            continue
        first = cyc.iloc[0]
        rows.append(dict(start=start, outcome=first['outcome'],
                         days=(pd.Timestamp(first['end_day']) - pd.Timestamp(start)).days
                         if first['outcome'] != 'in_progress' else np.nan))
    return pd.DataFrame(rows)


def signal_generation(days, lookback=LOOKBACK_DAYS, check_every=CHECK_EVERY,
                      first_check=FIRST_CHECK, stop_band_mult=STOP_BAND_MULT, flip=False):
    """return one row per trade. flip=True takes the OPPOSITE side of every
    signal - a control: if the edge were just market drift, flipping would
    not turn it into a loss."""

    h0, m0 = (int(v) for v in first_check.split(':'))
    # a check "at 10:00" acts on the close of the 09:59 bar
    marks = set(range(h0 * 60 + m0 - 1, RTH_CLOSE - 1, check_every))

    # |close / open - 1| at every minute of every day, for the noise area
    move = np.full((len(days), RTH_CLOSE - RTH_OPEN), np.nan)
    for i, s in enumerate(days):
        move[i, s['mod'] - RTH_OPEN] = np.abs(s['close'] / s['open'][0] - 1)

    trades = []
    for i, s in enumerate(days):
        if i < lookback or np.isnan(s['prev_close']):
            continue
        sigma = np.nanmean(move[i - lookback:i], axis=0)
        mod, o, h, l, c, vwap = s['mod'], s['open'], s['high'], s['low'], s['close'], s['vwap']
        top, bot = max(o[0], s['prev_close']), min(o[0], s['prev_close'])

        pos = 0
        for j in range(len(c)):
            exit_px = reason = None
            if pos != 0:
                # protective stop, every bar; a gap through it fills at the open
                if pos == 1 and l[j] <= stop:
                    exit_px, reason = min(o[j], stop), 'stop'
                elif pos == -1 and h[j] >= stop:
                    exit_px, reason = max(o[j], stop), 'stop'
                elif mod[j] >= RTH_CLOSE - 1:
                    exit_px, reason = c[j], 'session_end'
                if exit_px is None:
                    mae = max(mae, (entry - l[j]) if pos == 1 else (h[j] - entry))
                    mfe = max(mfe, (h[j] - entry) if pos == 1 else (entry - l[j]))

            if exit_px is None and mod[j] in marks and not np.isnan(sigma[mod[j] - RTH_OPEN]):
                sg = sigma[mod[j] - RTH_OPEN]
                upper, lower = top * (1 + sg), bot * (1 - sg)
                # (if the same-side entry would fire again on this bar - price
                # between the band and vwap - just stay in rather than paying
                # for a pointless exit and re-entry)
                if pos == 1 and c[j] < max(upper, vwap[j]) and not c[j] > upper:
                    exit_px, reason = c[j], 'trail'
                elif pos == -1 and c[j] > min(lower, vwap[j]) and not c[j] < lower:
                    exit_px, reason = c[j], 'trail'

            if exit_px is not None:
                side = -pos if flip else pos
                if reason == 'stop':
                    mae = abs(exit_px - entry)
                trades.append(dict(day=s['day'], side=side, entry_idx=k, exit_idx=j, entry_mod=mod[k],
                                   entry_price=entry, exit_price=exit_px, reason=reason,
                                   stop_dist=stop_dist, pnl_price=(exit_px - entry) * side,
                                   mae_price=mae if not flip else mfe, mfe_price=mfe if not flip else mae))
                pos = 0
                if reason == 'stop' or mod[j] >= RTH_CLOSE - 1:
                    continue

            if pos == 0 and mod[j] in marks and mod[j] < RTH_CLOSE - 1:
                sg = sigma[mod[j] - RTH_OPEN]
                if np.isnan(sg):
                    continue
                upper, lower = top * (1 + sg), bot * (1 - sg)
                if c[j] > upper or c[j] < lower:
                    pos = 1 if c[j] > upper else -1
                    entry, k, mae, mfe = c[j], j, 0.0, 0.0
                    stop_dist = stop_band_mult * sg * o[0]
                    stop = entry - pos * stop_dist

    tr = pd.DataFrame(trades)
    tr['r_multiple'] = tr['pnl_price'] / tr['stop_dist']
    return tr


def net_usd(tr, commission_rt=COMMISSION_RT, slippage_ticks=SLIPPAGE_TICKS):
    """net $ per ONE contract per trade. every order in this strategy is a
    market (or stop) order, so both fills pay slippage."""
    return tr['pnl_price'] * POINT_VALUE - (commission_rt + 2 * slippage_ticks * TICK_SIZE * POINT_VALUE)


def _t(x):
    return x.mean() / (x.std() / np.sqrt(len(x)))


def statistics(tr, control, days):

    n = net_usd(tr)
    ins = tr['day'] < SPLIT_DAY
    daily = pd.Series(0.0, index=[s['day'] for s in days[LOOKBACK_DAYS:]])
    daily = daily.add(n.groupby(tr['day']).sum(), fill_value=0.0)
    curve = daily.cumsum()

    print('=' * 64)
    print('INTRADAY MOMENTUM (NOISE AREA) - per 1 MNQ contract, net of cost')
    print('=' * 64)
    print(f"trades                    : {len(tr)}  (~{len(tr) / (len(daily) / 252):.0f} a year)")
    print(f"win rate                  : {(n > 0).mean():.1%}   avg win ${n[n > 0].mean():.0f}, avg loss ${n[n < 0].mean():.0f}")
    print(f"net $ per trade           : {n.mean():+.2f}  (t-stat {_t(n):.2f})")
    print(f"  in sample  (< {SPLIT_DAY}) : {n[ins].mean():+.2f}  (t-stat {_t(n[ins]):.2f})")
    print(f"  out of sample           : {n[~ins].mean():+.2f}  (t-stat {_t(n[~ins]):.2f})")
    print(f"  longs / shorts          : {n[tr['side'] == 1].mean():+.2f} / {n[tr['side'] == -1].mean():+.2f}")
    nc = net_usd(control)
    print(f"CONTROL, opposite side    : {nc.mean():+.2f}  (t-stat {_t(nc):.2f}) - must be clearly negative")
    print(f"double costs              : {net_usd(tr, 2 * COMMISSION_RT, 2 * SLIPPAGE_TICKS).mean():+.2f}")
    print(f"exits                     : {tr['reason'].value_counts().to_dict()}")
    print(f"worst trade / worst day   : ${n.min():.0f} / ${daily.min():.0f}")
    print(f"daily sharpe (annualized) : {daily.mean() / daily.std() * np.sqrt(252):.2f}")
    print(f"max drawdown              : ${(curve.cummax() - curve).max():,.0f} per contract")
    yearly = n.groupby(pd.to_datetime(tr['day']).dt.year).sum()
    print('net $ per contract by year: ' + ', '.join(f'{y}: {v:+,.0f}' for y, v in yearly.items()))
    return daily


def prop_evaluation(tr):
    """repeated evaluation cycles under the generic futures prop templates,
    at a fixed number of MNQ contracts, versus a zero-edge baseline with the
    same payoff shape (see the scalping backtest for both simulators)."""

    fixed = tr.copy()
    # stop_dist = 1 point makes risk_usd / (1 * point value) = contracts
    fixed['stop_dist'] = 1.0
    fixed['r_multiple'] = fixed['pnl_price']

    print()
    print('=' * 64)
    print('FUTURES PROP EVALUATIONS (repeated cycles, net of cost, 5 years)')
    print('=' * 64)
    for name, rule in pfs.FUTURES_PROP_TEMPLATES.items():
        sizes = (1, 2, 3) if rule['account'] <= 50000 else (3, 6, 9)
        for contracts in sizes:
            kw = dict(rule, risk_usd=contracts * POINT_VALUE, point_value=POINT_VALUE, tick_size=TICK_SIZE)
            cyc = pfs.backtesting_futures_prop(fixed, commission_round_trip=COMMISSION_RT,
                                               slippage_ticks=SLIPPAGE_TICKS, **kw)
            n_c, p = pfs.pass_rate(cyc)
            zero = np.nanmean([pfs.pass_rate(pfs.backtesting_futures_prop(pfs.zero_edge_trades(fixed, s), **kw))[1]
                               for s in range(20)])
            done = cyc[cyc['outcome'] != 'in_progress']
            med = (pd.to_datetime(done['end_day']) - pd.to_datetime(done['start_day'])).dt.days.median()
            print(f"{name}\n    {contracts} MNQ: pass {p:.0%} of {n_c} cycles (zero-edge {zero:.0%}), "
                  f"median {med:.0f} calendar days per cycle")


def plot(days, tr, daily, equity_path, session_path):

    fig = plt.figure()
    ax = fig.add_subplot(111)
    daily.cumsum().plot(ax=ax)
    plt.title('Intraday Momentum (MNQ) - Cumulative Net $ per Contract')
    plt.ylabel('$ per contract')
    plt.xlabel('date')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(equity_path)
    plt.close(fig)

    # one sample day with trades, bands and vwap
    s = next(x for x in days[len(days) // 2:] if (tr['day'] == x['day']).any())
    i = days.index(s)
    move = np.array([np.abs(np.interp(np.arange(RTH_OPEN, RTH_CLOSE), x['mod'], x['close']) / x['open'][0] - 1)
                     for x in days[i - LOOKBACK_DAYS:i]])
    sigma = move.mean(axis=0)[s['mod'] - RTH_OPEN]
    t = pd.to_datetime([f"{s['day']} {m // 60:02d}:{m % 60:02d}" for m in s['mod']])
    top, bot = max(s['open'][0], s['prev_close']), min(s['open'][0], s['prev_close'])
    fig = plt.figure()
    bx = fig.add_subplot(111)
    bx.plot(t, s['close'], label='price', zorder=1)
    bx.plot(t, top * (1 + sigma), linestyle=':', c='#BC8F8F', label='upper noise band')
    bx.plot(t, bot * (1 - sigma), linestyle=':', c='#FF4500', label='lower noise band')
    bx.plot(t, s['vwap'], c='gray', lw=0.8, label='vwap')
    day_tr = tr[tr['day'] == s['day']]
    for _, r in day_tr.iterrows():
        bx.scatter(t[r['entry_idx']], r['entry_price'], marker='^' if r['side'] == 1 else 'v',
                   c='g' if r['side'] == 1 else 'r', s=80, zorder=2)
        bx.scatter(t[r['exit_idx']], r['exit_price'], marker='x', c='k', s=50, zorder=2)
    plt.title(f"Intraday Momentum - Sample Session ({s['day']})")
    plt.legend(loc='best')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(session_path)
    plt.close(fig)


def timeframe_test(bar_minutes=(3, 5), start='2024-09-23', parquet_path=None):
    """recent-period test on the bar sizes a TradingView chart would use
    (TradingView itself cannot load this much 3/5 minute history). prints the
    trade statistics and the outcome of an evaluation started every Monday,
    under a few common futures prop rule shapes, next to a zero-edge
    baseline computed the same way."""

    if parquet_path is None:
        parquet_path = os.path.join(_base, 'data', 'MNQ_1m_v2_clean.parquet')
    days_1m = build_days(pfs.back_adjust_rolls(pd.read_parquet(parquet_path)))
    start = pd.Timestamp(start).date()
    rules = {
        'EOD $2k + $1k daily': dict(account=50000, target=3000, max_loss=2000, trailing='eod', daily_loss=1000),
        'EOD $2k, no daily': dict(account=50000, target=3000, max_loss=2000, trailing='eod', daily_loss=None),
        'EOD $2.5k, no daily': dict(account=50000, target=3000, max_loss=2500, trailing='eod', daily_loss=None),
        'intraday $2.5k': dict(account=50000, target=3000, max_loss=2500, trailing='intraday', daily_loss=None),
    }
    for minutes in bar_minutes:
        tr = signal_generation(resample_days(days_1m, minutes))
        tr = tr[tr['day'] >= start].reset_index(drop=True)
        n = net_usd(tr)
        pnl2 = (2 * n).cumsum()
        print('=' * 64)
        print(f'{minutes}-MINUTE BARS, {start} .. {tr["day"].max()} - {len(tr)} trades')
        print('=' * 64)
        print(f"net $ per contract per trade: {n.mean():+.2f} (t-stat {_t(n):.2f}), win rate {(n > 0).mean():.0%}")
        print(f"2 MNQ: total ${pnl2.iloc[-1]:+,.0f}, max drawdown ${(pnl2.cummax() - pnl2).max():,.0f}")
        q = (2 * n).groupby(pd.to_datetime(tr['day']).dt.to_period('Q')).sum()
        print('2 MNQ by quarter: ' + ', '.join(f'{k}: {v:+,.0f}' for k, v in q.items()))
        fixed = tr.assign(stop_dist=1.0, r_multiple=tr['pnl_price'])
        for name, rule in rules.items():
            for contracts in (1, 2):
                ev = evaluation_starts(tr, rule, contracts, commission_round_trip=COMMISSION_RT,
                                       slippage_ticks=SLIPPAGE_TICKS)
                done = ev[ev['outcome'] != 'in_progress']
                zero = []
                for seed in range(10):
                    z = evaluation_starts(pfs.zero_edge_trades(fixed, seed), rule, contracts)
                    z = z[z['outcome'] != 'in_progress']
                    zero.append((z['outcome'] == 'passed').mean())
                print(f"  weekly evaluations, {name:20s} {contracts} MNQ: pass {(done['outcome'] == 'passed').mean():.0%} "
                      f"of {len(done)} (zero-edge {np.mean(zero):.0%}), median "
                      f"{done.loc[done['outcome'] == 'passed', 'days'].median():.0f} days to pass")


def main(parquet_path=None):

    if parquet_path is None:
        parquet_path = os.path.join(_base, 'data', 'MNQ_1m_v2_clean.parquet')
    days = build_days(pfs.back_adjust_rolls(pd.read_parquet(parquet_path)))

    tr = signal_generation(days)
    control = signal_generation(days, flip=True)
    daily = statistics(tr, control, days)
    prop_evaluation(tr)
    plot(days, tr, daily,
         equity_path=os.path.join(_base, 'preview', 'prop firm intraday momentum equity curve.png'),
         session_path=os.path.join(_base, 'preview', 'prop firm intraday momentum sample session.png'))


if __name__ == '__main__':
    main()
