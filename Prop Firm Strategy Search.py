# coding: utf-8

# ---------------------------------------------------------------------------
# PROP FIRM STRATEGY SEARCH (MNQ, pre-registered in-sample / out-of-sample)
# ---------------------------------------------------------------------------
# reproduces sections 5-6 of 'Prop Firm Scalping review.md': the search for
# the best short-term strategy on 5 years of MNQ 1 minute data.
#
# protocol, fixed BEFORE looking at results:
#   - in sample 2021-09-23..2024-03-31, out of sample 2024-04-01..2026-09-22
#   - the best config of each idea is picked on in-sample net t-stat only,
#     then looked at out of sample once
#   - costs: $0.70 round trip + 1 tick slippage per market fill; limit
#     targets need a 1-tick trade-through; stops gapped through fill at the
#     bar open
# round 1 = 62 configs of 7 ideas, round 2 = published rules with their
# published parameters (the winner, noise-area momentum, lives in
# 'Prop Firm Intraday Momentum backtest.py').
# ---------------------------------------------------------------------------

import os
import importlib.util
import json
import datetime as dt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('pfs', os.path.join(ROOT, 'Prop Firm Scalping backtest.py'))
pfs = importlib.util.module_from_spec(spec); spec.loader.exec_module(pfs)
TICK, PV, COMM, SLIP = 0.25, 2.0, 0.70, 1.0
SPLIT = dt.date(2024, 4, 1)
EXIT = 959  # 15:59 bar close = 16:00

# ------------------------------------------------------------------ data
if True:
    df_adj = pfs.back_adjust_rolls(pd.read_parquet(f'{ROOT}/data/MNQ_1m_v2_clean.parquet'))
    ny = pd.to_datetime(df_adj['timestamp'], utc=True).dt.tz_convert('America/New_York')
    df_adj['day'] = ny.dt.date; df_adj['mod'] = (ny.dt.hour * 60 + ny.dt.minute).values
    rth = df_adj[(df_adj['mod'] >= 570) & (df_adj['mod'] < 960)]
    days = []
    for day, x in rth.groupby('day', sort=True):
        if len(x) < 370 or x['mod'].iloc[0] != 570:
            continue
        M = x['mod'].values; O, H, L, C = (x[c].values for c in ['open', 'high', 'low', 'close'])
        V = np.maximum(x['volume'].values.astype(float), 1.0)
        tp = (H + L + C) / 3
        cv = np.cumsum(V)
        vwap = np.cumsum(V * tp) / cv
        vsd = np.sqrt(np.maximum(np.cumsum(V * tp * tp) / cv - vwap ** 2, 0))
        days.append(dict(day=day, M=M, O=O, H=H, L=L, C=C, vwap=vwap, vsd=vsd))
    for i, d in enumerate(days):
        d['prev_close'] = days[i - 1]['C'][-1] if i > 0 else np.nan
        rg = [days[j]['H'].max() - days[j]['L'].min() for j in range(max(0, i - 20), i)]
        d['atr20'] = np.mean(rg) if len(rg) >= 10 else np.nan

# ------------------------------------------------------------------ simulator
def sim(d, k, side, stop, target, exit_mod=EXIT, max_hold=None):
    """enter at close of bar k. returns trade dict or None."""
    M, O, H, L, C = d['M'], d['O'], d['H'], d['L'], d['C']
    e = C[k]; sd = abs(e - stop)
    if sd < 1.0:
        return None
    td = abs(target - e) if target is not None else None
    mae = mfe = 0.0
    for j in range(k + 1, len(C)):
        if side == 1:
            if O[j] <= stop: px, why = O[j], 'stop'; mae = e - O[j]; break
            adv, fav = e - L[j], H[j] - e
        else:
            if O[j] >= stop: px, why = O[j], 'stop'; mae = O[j] - e; break
            adv, fav = H[j] - e, e - L[j]
        mae = max(mae, min(adv, sd))
        if adv >= sd: px, why = stop, 'stop'; break
        if td is not None:
            mfe = max(mfe, min(fav, td))
            if fav >= td + TICK: px, why = target, 'target'; break
        else:
            mfe = max(mfe, fav)
        if M[j] >= exit_mod or (max_hold is not None and j - k >= max_hold):
            px, why = C[j], 'time'; break
    else:
        px, why, j = C[-1], 'time', len(C) - 1
    return dict(day=d['day'], side=side, entry_price=e, exit_price=px, reason=why, stop_dist=sd,
                pnl_price=(px - e) * side, mae_price=mae, mfe_price=mfe, exit_j=j)

# ------------------------------------------------------------------ families
def fam_orb(or_min, tgt, stop_mode, last_entry=900):
    out = []
    for d in days:
        M, C = d['M'], d['C']
        m = M < 570 + or_min
        hi, lo = d['H'][m].max(), d['L'][m].min()
        for k in np.where(~m & (M < last_entry))[0]:
            side = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
            if side == 0: continue
            stop = (lo if side == 1 else hi) if stop_mode == 'range' else (hi + lo) / 2
            e = C[k]; t = e + side * tgt * abs(e - stop) if tgt else None
            tr = sim(d, k, side, stop, t)
            if tr: out.append(tr)
            break
    return out

def fam_mom(signal, entry_mod, stopk):
    out = []
    for d in days:
        M, C = d['M'], d['C']
        ks = np.where(M == entry_mod - 1)[0]; k10 = np.where(M == 599)[0]
        if not len(ks) or not len(k10) or np.isnan(d['prev_close']): continue
        k = ks[0]
        s = C[k10[0]] - d['prev_close'] if signal == 'first30' else C[k] - d['O'][0]
        if s == 0: continue
        side = 1 if s > 0 else -1
        rng = d['H'][:k + 1].max() - d['L'][:k + 1].min()
        tr = sim(d, k, side, C[k] - side * stopk * rng, None)
        if tr: out.append(tr)
    return out

def fam_vwaprev(ksd, ssd, confirm, max_trades=3):
    out = []
    for d in days:
        M, C, vw, vs = d['M'], d['C'], d['vwap'], d['vsd']
        dev = np.where(vs > 0, (C - vw) / np.where(vs > 0, vs, 1), 0)
        i, n = 0, 0
        idx = np.where((M >= 600) & (M < 900))[0]
        while n < max_trades:
            idx = idx[idx > i]
            if not len(idx): break
            hit = None
            for k in idx:
                if confirm == 'touch':
                    if dev[k] > ksd: hit = (k, -1)
                    elif dev[k] < -ksd: hit = (k, 1)
                else:
                    if dev[k - 1] > ksd and dev[k] <= ksd: hit = (k, -1)
                    elif dev[k - 1] < -ksd and dev[k] >= -ksd: hit = (k, 1)
                if hit: break
            if not hit: break
            k, side = hit
            e = C[k]; tr = sim(d, k, side, e - side * ssd * vs[k], vw[k], max_hold=60)
            if tr and (vw[k] - e) * side >= 1.0:
                out.append(tr); n += 1; i = tr['exit_j']
            else:
                i = k
    return out

def fam_vwaptrend(tgt, stop_sd, max_trades=2):
    out = []
    for d in days:
        M, L, H, C, vw, vs = d['M'], d['L'], d['H'], d['C'], d['vwap'], d['vsd']
        i, n = 0, 0
        for k in range(len(C)):
            if n >= max_trades: break
            if k <= i or M[k] < 630 or M[k] >= 900 or k < 30: continue
            above = (C[k - 30:k] > vw[k - 30:k]).mean(); slope = vw[k] - vw[k - 30]
            side = 0
            if above >= 0.8 and slope > 0 and L[k] <= vw[k] < C[k]: side = 1
            elif above <= 0.2 and slope < 0 and H[k] >= vw[k] > C[k]: side = -1
            if not side: continue
            stop = vw[k] - side * stop_sd * vs[k]
            e = C[k]; tr = sim(d, k, side, stop, e + side * tgt * abs(e - stop))
            if tr: out.append(tr); n += 1; i = tr['exit_j']
    return out

def fam_gap(g, exit_mod, mode):
    out = []
    for d in days:
        if np.isnan(d['atr20']) or np.isnan(d['prev_close']): continue
        gap = d['O'][0] - d['prev_close']
        if abs(gap) < g * d['atr20']: continue
        e = d['C'][0]
        if mode == 'fade':
            side = -1 if gap > 0 else 1
            if (d['prev_close'] - e) * side <= 1.0: continue
            tr = sim(d, 0, side, e - side * abs(gap), d['prev_close'], exit_mod=exit_mod)
        else:
            side = 1 if gap > 0 else -1
            tr = sim(d, 0, side, e - side * abs(gap), None, exit_mod=exit_mod)
        if tr: out.append(tr)
    return out

def fam_mr(start, hold):
    tr, _ = pfs.signal_generation_ohlc(df_adj, tz='America/New_York', session_start=start, session_end='16:00',
                                       stop_mult=3.0, target_mult=1.5, max_hold=hold,
                                       target_through_ticks=1, tick_size=TICK)
    return tr.to_dict('records')

configs = []
configs += [('MR pullback', dict(start=s, hold=h), fam_mr) for s, h in [('09:30', 45), ('10:00', 90)]]
configs += [('ORB', dict(or_min=o, tgt=t, stop_mode=s), fam_orb) for o in (5, 15, 30, 60) for t in (1, 2, None) for s in ('range', 'mid')]
configs += [('Late-day momentum', dict(signal=s, entry_mod=e, stopk=k), fam_mom) for s in ('first30', 'day') for e in (900, 930) for k in (0.25, 0.5)]
configs += [('VWAP reversion', dict(ksd=k, ssd=s, confirm=c), fam_vwaprev) for k in (2.0, 2.5, 3.0) for s in (1.0, 2.0) for c in ('touch', 'reentry')]
configs += [('VWAP trend pullback', dict(tgt=t, stop_sd=s), fam_vwaptrend) for t in (1, 2) for s in (0.5, 1.0)]
configs += [('Gap fade', dict(g=g, exit_mod=x, mode='fade'), fam_gap) for g in (0.1, 0.2, 0.3) for x in (660, EXIT)]
configs += [('Gap and go', dict(g=g, exit_mod=x, mode='go'), fam_gap) for g in (0.1, 0.2, 0.3) for x in (660, EXIT)]

def stats(tr):
    if len(tr) < 2: return dict(n=len(tr))
    c = np.array([pfs.trade_cost(w, COMM, SLIP, TICK, PV) for w in tr.reason]) / (tr.stop_dist * PV)
    net = tr.r_multiple - c
    return dict(n=len(tr), win=(net > 0).mean(), gross=tr.r_multiple.mean(), net=net.mean(),
                t=net.mean() / (net.std() / np.sqrt(len(net))), cost=c.mean())

def net_r(tr):
    c = np.array([pfs.trade_cost(w, COMM, SLIP, TICK, PV) for w in tr.reason]) / (tr.stop_dist * PV)
    return tr.r_multiple - c


def tstat(x):
    return x.mean() / (x.std() / np.sqrt(len(x))) if len(x) > 2 else np.nan


def to_frame(rows):
    tr = pd.DataFrame(rows)
    tr['r_multiple'] = tr['pnl_price'] / tr['stop_dist']
    tr['day'] = pd.to_datetime(tr['day']).dt.date
    return tr


def round1():
    rows, trades = [], {}
    for fam, kw, fn in configs:
        tr = to_frame(fn(**kw))
        trades[(fam, json.dumps(kw))] = tr
        is_, oos = stats(tr[tr.day < SPLIT]), stats(tr[tr.day >= SPLIT])
        rows.append(dict(family=fam, config=json.dumps(kw), **{f'IS_{k}': v for k, v in is_.items()},
                         **{f'OOS_{k}': v for k, v in oos.items()}))
    res = pd.DataFrame(rows)
    print('=' * 100); print('ROUND 1 - all configs (net R per trade)'); print('=' * 100)
    print(res[['family', 'config', 'IS_n', 'IS_net', 'IS_t', 'OOS_n', 'OOS_net', 'OOS_t']].round(3).to_string())
    ok = res[res.IS_n >= 150]
    best = ok.loc[ok.groupby('family')['IS_t'].idxmax()]
    print('\nin-sample winner of each family, and the same config out of sample:')
    print(best[['family', 'config', 'IS_net', 'IS_t', 'OOS_net', 'OOS_t']].round(3).to_string(index=False))
    return res, trades


def orb_drift_control(trades, or_min=30):
    """same entry bar and stop distance as the 30-min ORB, but ALWAYS long:
    if that earns about as much, the breakout's profit is market drift."""
    real = trades[('ORB', json.dumps(dict(or_min=or_min, tgt=None, stop_mode='range')))]
    out = []
    for d in days:
        M, C = d['M'], d['C']
        m = M < 570 + or_min
        hi, lo = d['H'][m].max(), d['L'][m].min()
        for k in np.where(~m & (M < 900))[0]:
            side = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
            if side == 0: continue
            tr = sim(d, k, 1, C[k] - abs(C[k] - (lo if side == 1 else hi)), None)
            if tr: out.append(tr)
            break
    long_only = to_frame(out)
    print(f'\nORB {or_min} min drift control: breakout direction {net_r(real).mean():+.3f}R '
          f'vs always long on the same bar {net_r(long_only).mean():+.3f}R')


def round2(trades):
    print('\n' + '=' * 100); print('ROUND 2 - published rules, published parameters'); print('=' * 100)
    # 5-minute ORB, Zarattini & Aziz (2023)
    out = []
    for d in days:
        o5, c5 = d['O'][0], d['C'][4]
        if c5 == o5: continue
        side = 1 if c5 > o5 else -1
        stop = d['L'][:5].min() if side == 1 else d['H'][:5].max()
        tr = sim(d, 4, side, stop, c5 + side * 10 * abs(c5 - stop))
        if tr: out.append(tr)
    z = to_frame(out); n = net_r(z)
    print(f"5-min ORB (Zarattini-Aziz): IS {n[z.day < SPLIT].mean():+.3f}R (t {tstat(n[z.day < SPLIT]):.2f}) "
          f"| OOS {n[z.day >= SPLIT].mean():+.3f}R (t {tstat(n[z.day >= SPLIT]):.2f})")
    # Crabel narrow-range filter on the 30-min ORB: tercile cut points and choice from IS only
    b = trades[('ORB', json.dumps(dict(or_min=30, tgt=None, stop_mode='range')))].copy()
    dmap = {d['day']: d for d in days}
    b['or_atr'] = [(dmap[x]['H'][:30].max() - dmap[x]['L'][:30].min()) / dmap[x]['atr20'] for x in b.day]
    b['net'] = net_r(b)
    b = b.dropna(subset=['or_atr'])
    q = b[b.day < SPLIT].or_atr.quantile([1 / 3, 2 / 3]).values
    print('Crabel filter (opening range / 20-day range terciles, cut points from IS):')
    for lo, hi, lab in [(0, q[0], 'narrow'), (q[0], q[1], 'middle'), (q[1], 99, 'wide')]:
        sel = (b.or_atr >= lo) & (b.or_atr < hi)
        i, o = b[sel & (b.day < SPLIT)].net, b[sel & (b.day >= SPLIT)].net
        print(f'  {lab:7s}: IS {i.mean():+.3f}R (t {tstat(i):+.2f}) | OOS {o.mean():+.3f}R (t {tstat(o):+.2f})')
    print("noise-area momentum: run 'Prop Firm Intraday Momentum backtest.py'")


if __name__ == '__main__':
    res, trades = round1()
    orb_drift_control(trades)
    round2(trades)
