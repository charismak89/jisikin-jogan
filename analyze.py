#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze.py — calibration.json 진단 (읽기 전용, 회차는 쓰지 않는다)

신호별로 시초가 갭을 얼마나 설명했는지, 규칙 후보를 leave-one-out 으로 돌리면 어땠는지 출력한다.
규칙 변경(금요일) 전에 사람이 돌려 보고 CALIBRATION.md 에 결과를 남긴다.

  python3 analyze.py
"""
import io, json, statistics as st
from datetime import date

recs = json.load(io.open('calibration.json', encoding='utf-8'))['records']
X = [r for r in recs if r.get('exclude')]   # 개장 왜곡 등 채점 예외(2026-11-07, CALIBRATION.md) — 모든 통계·롤백 집계에서 뺀다
S = [r for r in recs if r.get('signals') and not r.get('exclude')]
N = [r for r in S if r['signals'].get('k200n_pct') is not None]
SIG = [('사람', None), ('야간', 'k200n_pct'), ('EWY', 'ewy_implied_pct'), ('ADR', 'adr_implied_pct')]

def val(r, key): return r['center_pct'] if key is None else r['signals'].get(key)
def q80(v):
    v = sorted(v); i = 0.8 * (len(v) - 1); lo = int(i)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)
def f(v): return '   -  ' if v is None else '%+6.2f' % v

print('신호 기록 %d건 (야간선물 있는 날 %d건)\n' % (len(S), len(N)))
for r in X: print('제외 %s — %s' % (r['date'], (r['exclude'] or {}).get('detail') or (r['exclude'] or {}).get('why')))
if X: print()
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
since = next((h['date'] for h in reversed(rule.get('history') or []) if h.get('changed') == 'half_width_mode'), '')   # 반폭 방식 마지막 변경(월요일 확장 H5 는 따로 본다)
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

# 기록 전용 — 야간선물 마감 뒤(pnight → 스냅샷) 코스피200 추종가 움직임 (CALIBRATION.md H2).
# 2026-11-09 측정 수정: 마감 시각을 발행일 05:00 에서 실제 마감(평일 발행일 06:00, 월요일 토 06:00)으로. 10/16 이후 기록은 pnight 를 다시 받아 채웠다
P = [r for r in N if ((r['signals'].get('perp') or {}).get('KOSPI') or {}).get('snap') is not None
     and r['signals']['perp']['KOSPI'].get('pnight') is not None]
def post(r):
    k = r['signals']['perp']['KOSPI']; return ((1 + k['snap'] / 100) / (1 + k['pnight'] / 100) - 1) * 100
def h2(rs, label):
    if len(rs) < 3: print('%s %d건 — 3건 미만' % (label, len(rs))); return
    ys = [r['gap_pct'] - r['signals']['k200n_pct'] for r in rs]
    print('%s %d건 — 야간 단독 MAE %.2f · 야간 + 0.5×사후 %.2f · 야간 + 1.0×사후 %.2f' % (label, len(rs), st.mean(abs(y) for y in ys),
          st.mean(abs(y - 0.5 * post(r)) for y, r in zip(ys, rs)), st.mean(abs(y - post(r)) for y, r in zip(ys, rs))))
print('\n추종가(KR200) 기록 %d건 — 야간선물 마감 뒤 변화' % len(P))
if len(P) >= 5:
    ys = [r['gap_pct'] - r['signals']['k200n_pct'] for r in P]
    print('잔차(갭 − 야간) vs KR200 사후 변화 상관 r=%.2f' % st.correlation([post(r) for r in P], ys))
    h2(P, '전체')
    h2([r for r in P if r['date'] > '2026-10-31'], 'H2 등록(10/31) 뒤')
    h2([r for r in P if date.fromisoformat(r['date']).weekday() == 0], '월요일만(참고)')

# H5 — 월요일 반폭 + |주말 추종가 변화| (2026-11-09 사용자 결정). 적용 뒤 월요일을 확장 없는 반사실과 비교
if rule.get('monday_widen'):
    since5 = next((h['date'] for h in reversed(rule.get('history') or []) if 'monday_widen' in (h.get('changed') or '')), '')
    M = [r for r in N if r['date'] > since5 and date.fromisoformat(r['date']).weekday() == 0 and not r['signals'].get('night_skipped')]
    if rule.get('half_width_mode') == 'scaled':
        base = lambda r: rule['half_width_q'] * (rule['half_width_base'] + abs(r['signals']['k200n_pct']))
        nowid = sum(abs(r['gap_pct'] - r['signals']['k200n_pct']) <= base(r) for r in M)
        extra = [r['band_width_pct'] / 2 - base(r) for r in M if r.get('band_width_pct') is not None]
        print('\nH5 월요일 확장 점검 (%s 적용 뒤 월요일 %d회, 폴백 제외) — 실제 구간 안 %d/%d · 확장 없었으면 %d/%d · 평균 추가 반폭 %s' % (
            since5, len(M), sum(bool(r['in_range']) for r in M), len(M), nowid, len(M), ('%.2f%%p' % st.mean(extra)) if extra else '-'))
        if len(M) >= 8: print('  → 8회 도달. 실제 구간 안이 확장 없는 반사실보다 많지 않으면 monday_widen 을 지운다(CALIBRATION.md H5)')

# 종목 채점 (stock_records)
SR = json.load(io.open('calibration.json', encoding='utf-8')).get('stock_records') or []

# H6 — 종목 월요일 반폭 + |주말 그 종목 추종가 변화| (2026-11-09 사용자 결정). 종목별로 확장 없는 반사실과 비교
srule = json.load(io.open('calibration.json', encoding='utf-8')).get('stock_rule') or {}
if srule.get('monday_widen'):
    since6 = next((h['date'] for h in reversed(srule.get('history') or []) if 'monday_widen' in (h.get('changed') or '')), '')
    for code in ('005930', '000660'):
        M6 = [r for r in SR if r['code'] == code and r['date'] > since6 and date.fromisoformat(r['date']).weekday() == 0 and r.get('monday_widen_pct') is not None]
        if not M6: print('H6 %s 월요일 확장 점검 (%s 적용 뒤 0회)' % (code, since6)); continue
        nowid = sum(abs(r['gap_pct'] - r['center_pct']) <= r['half_width_pct'] - r['monday_widen_pct'] for r in M6)
        print('H6 %s 월요일 확장 점검 (%s 적용 뒤 %d회) — 실제 구간 안 %d/%d · 확장 없었으면 %d/%d · 평균 추가 반폭 %.2f%%p' % (
            code, since6, len(M6), sum(bool(r['in_range']) for r in M6), len(M6), nowid, len(M6), st.mean(r['monday_widen_pct'] for r in M6)))
        if len(M6) >= 8: print('  → 8회 도달. 실제 구간 안이 반사실보다 많지 않으면 이 종목은 확장을 뺀다(CALIBRATION.md H6)')

for code in sorted({r['code'] for r in SR}):
    rr = [r for r in SR if r['code'] == code]
    print('종목 %s %d회 — 구간 안 %d · 중심 오차 MAE %.2f · 평균 폭 %.2f%%p' % (code, len(rr), sum(r['in_range'] for r in rr),
          st.mean(abs(r['center_err_pct']) for r in rr if r.get('center_err_pct') is not None) if any(r.get('center_err_pct') is not None for r in rr) else 0,
          st.mean(r['band_width_pct'] for r in rr)))
