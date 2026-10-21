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
    print('%-4s n=%2d  MAE %.2f  중앙 %.2f  최대 %.2f  부호 %d/%d  r=%.2f' % (
        name, len(p), st.mean(e), st.median(e), max(e), sum((g > 0) == (v > 0) for g, v in p), len(p),
        st.correlation([v for _, v in p], [g for g, _ in p])))

print('\n신호별 오차 (전체)')
for name, key in SIG: line(name, S, key)
print('\n같은 날 비교 (야간선물 있는 날만)')
for name, key in SIG: line(name, N, key)

def loo(name, cf):
    errs, cov, w = [], 0, []
    for i, r in enumerate(N):
        o = N[:i] + N[i + 1:]
        half = q80([abs(x['gap_pct'] - cf(x)) for x in o])
        c, g = cf(r), r['gap_pct']
        errs.append(abs(g - c)); w.append(2 * half)
        cov += c - half <= g <= c + half
    print('%-12s MAE %.2f  폭 %.2f  커버 %d/%d' % (name, st.mean(errs), st.mean(w), cov, len(N)))

if len(N) >= 5:
    print('\n규칙 후보 leave-one-out (반폭 = 나머지 날 잔차 80퍼센타일)')
    loo('야간 그대로', lambda r: r['signals']['k200n_pct'])
    loo('야간 x0.8', lambda r: 0.8 * r['signals']['k200n_pct'])
    print('%-12s MAE %.2f  폭 %.2f  커버 %d/%d   (실제 기록)' % (
        '사람', st.mean(abs(r['gap_pct'] - r['center_pct']) for r in N), st.mean(r['band_width_pct'] for r in N),
        sum(bool(r['in_range']) for r in N), len(N)))
    res = [abs(r['gap_pct'] - r['signals']['k200n_pct']) for r in N]
    print('\n후보 2 반폭 제안 = |갭 − 야간| 80퍼센타일 %.2f%% (n=%d)' % (q80(res), len(N)))

    # 비례 반폭 — 반폭 = q × (1 + |야간|), q 는 나머지 날의 |갭 − 야간| / (1 + |야간|) 80퍼센타일. 2026-10-16 적용(CALIBRATION.md)
    def sc(r): return 1 + abs(r['signals']['k200n_pct'])
    cov, w = 0, []
    for i, r in enumerate(N):
        o = N[:i] + N[i + 1:]
        h = q80([abs(x['gap_pct'] - x['signals']['k200n_pct']) / sc(x) for x in o]) * sc(r)
        cov += abs(r['gap_pct'] - r['signals']['k200n_pct']) <= h; w.append(2 * h)
    print('비례 반폭 LOO   폭 %.2f  커버 %d/%d · q 재추정(전체) = %.2f' % (
        st.mean(w), cov, len(N), q80([abs(r['gap_pct'] - r['signals']['k200n_pct']) / sc(r) for r in N])))

# 현행 규칙 점검 — 마지막 규칙 변경 뒤 회차(휴장 뒤 폴백 제외)를 현행 규칙과 고정 0.8 반사실로 채점. 롤백 판단용
rule = json.load(io.open('calibration.json', encoding='utf-8')).get('rule') or {}
since = ((rule.get('history') or [{}])[-1]).get('date') or ''
A = [r for r in N if r['date'] > since and not r['signals'].get('night_skipped')]
if rule.get('half_width_mode') == 'scaled':
    q, b = rule.get('half_width_q'), rule.get('half_width_base')
    cur = sum(abs(r['gap_pct'] - r['signals']['k200n_pct']) <= q * (b + abs(r['signals']['k200n_pct'])) for r in A)
    fix = sum(abs(r['gap_pct'] - r['signals']['k200n_pct']) <= 0.8 for r in A)
    print('\n현행 규칙 점검 (%s 변경 뒤 %d회, 폴백 제외) — 비례 q=%s 커버 %d/%d · 고정 0.8 반사실 %d/%d · 실제 기록 구간 안 %d/%d' % (
        since, len(A), q, cur, len(A), fix, len(A), sum(bool(r['in_range']) for r in A), len(A)))
    if len(A) >= 10: print('  → 10회 도달. 비례 < 고정이면 half_width_mode 를 fixed 로 되돌린다. 비례 < 8/10 이면 q 재추정을 금요일 후보로')

# 후보 3 — 미국 지수선물(야간 마감 뒤 움직임)이 야간선물 잔차를 설명하는가. 2026-10-02 회차부터 기록
E = [r for r in N if r['signals'].get('es_pct') is not None]
print('\n미국 지수선물 기록 %d건' % len(E))
if len(E) >= 5:
    xs = [r['signals']['es_pct'] for r in E]; ys = [r['gap_pct'] - r['signals']['k200n_pct'] for r in E]
    print('잔차(갭 − 야간) vs ES 상관 r=%.2f' % st.correlation(xs, ys))
    for k in (0.5, 1.0):
        e = [abs(r['gap_pct'] - r['signals']['k200n_pct'] - k * r['signals']['es_pct']) for r in E]
        print('야간 + %.1f×ES  MAE %.2f  (야간 단독 %.2f)' % (k, st.mean(e), st.mean(abs(y) for y in ys)))

# 기록 전용 — 야간선물 마감 뒤(05:00 → 스냅샷) 코스피200 추종가 움직임. 2026-10-16 회차부터 기록 (CALIBRATION.md)
P = [r for r in N if ((r['signals'].get('perp') or {}).get('KOSPI') or {}).get('snap') is not None
     and r['signals']['perp']['KOSPI'].get('p0500') is not None]
print('\n추종가(KR200) 기록 %d건' % len(P))
if len(P) >= 5:
    def post(r):
        k = r['signals']['perp']['KOSPI']; return ((1 + k['snap'] / 100) / (1 + k['p0500'] / 100) - 1) * 100
    ys = [r['gap_pct'] - r['signals']['k200n_pct'] for r in P]
    print('잔차(갭 − 야간) vs KR200 사후 변화 상관 r=%.2f' % st.correlation([post(r) for r in P], ys))
    for k in (0.5, 1.0):
        print('야간 + %.1f×KR200 사후  MAE %.2f  (야간 단독 %.2f)' % (k, st.mean(abs(y - k * post(r)) for y, r in zip(ys, P)), st.mean(abs(y) for y in ys)))

# 종목 채점 (stock_records)
SR = json.load(io.open('calibration.json', encoding='utf-8')).get('stock_records') or []
for code in sorted({r['code'] for r in SR}):
    rr = [r for r in SR if r['code'] == code]
    print('종목 %s %d회 — 구간 안 %d · 중심 오차 MAE %.2f · 평균 폭 %.2f%%p' % (code, len(rr), sum(r['in_range'] for r in rr),
          st.mean(abs(r['center_err_pct']) for r in rr if r.get('center_err_pct') is not None) if any(r.get('center_err_pct') is not None for r in rr) else 0,
          st.mean(r['band_width_pct'] for r in rr)))
