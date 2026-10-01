#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze.py — calibration.json 진단 (읽기 전용, 회차는 쓰지 않는다)

신호별로 시초가 갭을 얼마나 설명했는지, 규칙 후보를 leave-one-out 으로 돌리면 어땠는지 출력한다.
규칙 변경(금요일) 전에 사람이 돌려 보고 CALIBRATION.md 에 결과를 남긴다.

  python3 analyze.py
"""
import io, json, statistics as st

recs = json.load(io.open('calibration.json', encoding='utf-8'))['records']
S = [r for r in recs if r.get('signals')]
N = [r for r in S if r['signals'].get('k200n_pct') is not None]
SIG = [('사람', None), ('야간', 'k200n_pct'), ('EWY', 'ewy_implied_pct'), ('ADR', 'adr_implied_pct')]

def dirof(g): return 1 if g > 0.5 else -1 if g < -0.5 else 0
def val(r, key): return r['center_pct'] if key is None else r['signals'].get(key)
def q80(v):
    v = sorted(v); i = 0.8 * (len(v) - 1); lo = int(i)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)
def f(v): return '   -  ' if v is None else '%+6.2f' % v

print('신호 기록 %d건 (야간선물 있는 날 %d건)\n' % (len(S), len(N)))
print('날짜   실제갭   사람   야간    EWY    ADR | 구간 안')
for r in S:
    print(r['date'][5:], f(r['gap_pct']), *[f(val(r, k)) for _, k in SIG], '|', r['in_range'])

def line(name, rs, key):
    p = [(r['gap_pct'], val(r, key)) for r in rs if val(r, key) is not None]
    if len(p) < 3: return
    e = [abs(g - v) for g, v in p]
    print('%-4s n=%2d  MAE %.2f  중앙 %.2f  최대 %.2f  부호 %d/%d  3분류 %d/%d  r=%.2f' % (
        name, len(p), st.mean(e), st.median(e), max(e), sum((g > 0) == (v > 0) for g, v in p), len(p),
        sum(dirof(g) == dirof(v) for g, v in p), len(p), st.correlation([v for _, v in p], [g for g, _ in p])))

print('\n신호별 오차 (전체)')
for name, key in SIG: line(name, S, key)
print('\n같은 날 비교 (야간선물 있는 날만)')
for name, key in SIG: line(name, N, key)

def loo(name, cf):
    errs, cov, hit, w = [], 0, 0, []
    for i, r in enumerate(N):
        o = N[:i] + N[i + 1:]
        half = q80([abs(x['gap_pct'] - cf(x)) for x in o])
        c, g = cf(r), r['gap_pct']
        errs.append(abs(g - c)); w.append(2 * half)
        inr = c - half <= g <= c + half; cov += inr; hit += inr and dirof(c) == dirof(g)
    print('%-12s MAE %.2f  폭 %.2f  커버 %d/%d  hit %d/%d' % (name, st.mean(errs), st.mean(w), cov, len(N), hit, len(N)))

if len(N) >= 5:
    print('\n규칙 후보 leave-one-out (반폭 = 나머지 날 잔차 80퍼센타일)')
    loo('야간 그대로', lambda r: r['signals']['k200n_pct'])
    loo('야간 x0.8', lambda r: 0.8 * r['signals']['k200n_pct'])
    print('%-12s MAE %.2f  폭 %.2f  커버 %d/%d  hit %d/%d   (실제 기록)' % (
        '사람', st.mean(abs(r['gap_pct'] - r['center_pct']) for r in N), st.mean(r['band_width_pct'] for r in N),
        sum(bool(r['in_range']) for r in N), len(N), sum(r['verdict'] == 'hit' for r in N), len(N)))
    res = [abs(r['gap_pct'] - r['signals']['k200n_pct']) for r in N]
    print('\n후보 2 반폭 제안 = |갭 − 야간| 80퍼센타일 %.2f%% (n=%d)' % (q80(res), len(N)))

# 후보 3 — 미국 지수선물(야간 마감 뒤 움직임)이 야간선물 잔차를 설명하는가. 2026-10-02 회차부터 기록
E = [r for r in N if r['signals'].get('es_pct') is not None]
print('\n미국 지수선물 기록 %d건' % len(E))
if len(E) >= 5:
    xs = [r['signals']['es_pct'] for r in E]; ys = [r['gap_pct'] - r['signals']['k200n_pct'] for r in E]
    print('잔차(갭 − 야간) vs ES 상관 r=%.2f' % st.correlation(xs, ys))
    for k in (0.5, 1.0):
        e = [abs(r['gap_pct'] - r['signals']['k200n_pct'] - k * r['signals']['es_pct']) for r in E]
        print('야간 + %.1f×ES  MAE %.2f  (야간 단독 %.2f)' % (k, st.mean(e), st.mean(abs(y) for y in ys)))
