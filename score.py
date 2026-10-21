#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score.py — 직전 회차 전망 채점 + calibration.json append

읽는 것 : state.json (직전 회차의 forecast·signals), fill.json (prices.KOSPI.open = 직전 영업일 실제 시초가), calibration.json
쓰는 것 : calibration.json (records 끝에 1건 append. rule 블록은 절대 손대지 않는다)

규칙 (CALIBRATION.md 와 같다)
  hit       : 실제 시초가가 [low, high] 안. 그 외 전부 miss. 방향 3분류(갭상승·보합·갭하락)는 2026-10-21 폐지
  sign_hit  : 구간 중심(low·high 평균)의 부호와 실제 갭 부호가 같은가 (참고용, 판정에 안 씀)

종목 채점 (2026-10-15 v5 추가)
  state.stock_forecast(직전 회차 삼전·하닉 예측 구간)를 fill.json prices.<코드>.open(직전 영업일 시초가)과 대조해
  calibration.json 의 stock_records 에 append 한다. 코스피 채점(records·rule)과 섞지 않는다. 같은 (날짜, 코드)는 두 번 기록하지 않는다.

중계기 보완 (2026-10-21)
  fill.json 을 읽은 뒤 relay.json(fetch_relay.py)으로 빈 시가를 채운다. 회차가 시가를 못 구해도 중계기가 받았으면 채점된다.

사용법
  python3 score.py            채점하고 calibration.json 에 기록
  python3 score.py --dry-run  기록하지 않고 결과만 출력
같은 날짜가 이미 기록돼 있으면 다시 기록하지 않는다(멱등).
"""
import io, json, sys, math

def num(v):
    if v is None: return None
    if isinstance(v, bool): return None
    try:
        return float(str(v).replace(',', ''))
    except Exception:
        return None

def pctl(xs, p):
    xs = sorted(xs)
    if not xs: return None
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)

def load_fill(say=False):
    fill = json.load(io.open('fill.json', encoding='utf-8'))
    try:
        from fetch_relay import merge_into
        st, filled, _ = merge_into(fill)
        if say and filled: print('중계기 보완(시가) — %s' % ', '.join(f for f in filled if f.endswith('.open')))
    except Exception as e:
        if say: print('중계기 보완 건너뜀 — %s' % e)
    return fill

def main():
    dry = '--dry-run' in sys.argv
    try:
        state = json.load(io.open('state.json', encoding='utf-8'))
    except Exception:
        print('채점 불가 — state.json 없음 (직전 전망 없음). 기록하지 않는다.'); return 0
    try:
        cal = json.load(io.open('calibration.json', encoding='utf-8'))
    except Exception:
        print('채점 불가 — calibration.json 을 읽지 못함. 새로 만들지 않는다.'); return 0
    fill = load_fill(say=True)

    fc = state.get('forecast') or {}
    fdate = fc.get('date')
    low, high, prev_close = num(fc.get('low')), num(fc.get('high')), num(fc.get('prev_close'))
    if not fdate or prev_close is None:
        print('채점 불가 — state.forecast 에 date/prev_close 없음'); return 0

    recs = cal.setdefault('records', [])
    if recs and recs[-1].get('date') == fdate:
        r = recs[-1]
        print('이미 채점됨 — %s %s (시초가 %s, 갭 %+.2f%%)' % (fdate, r.get('verdict'), r.get('actual_open'), r.get('gap_pct') or 0))
        print_summary(cal); print_rule(cal, fill); return 0

    kospi = (fill.get('prices') or {}).get('KOSPI') or {}
    sc = fill.get('score') or {}
    actual, src = None, None
    od = kospi.get('open_date')
    if num(kospi.get('open')) is not None and (not od or od == fdate):
        actual, src = num(kospi.get('open')), 'prices.KOSPI.open'
        if not od: print('참고 — KOSPI.open_date 가 없어 %s 시초가로 간주한다' % fdate)
    elif num(sc.get('actual_open')) is not None and (sc.get('actual_open_date') in (None, fdate)):
        actual, src = num(sc.get('actual_open')), 'score.actual_open'
    if actual is None:
        why = ('시초가 날짜 %s 가 전망 날짜 %s 와 다름' % (od, fdate)) if (od and od != fdate) else '직전 영업일 코스피 시초가(prices.KOSPI.open)를 확보하지 못함'
        print('채점 불가 — %s. 기록하지 않는다.' % why)
        print_summary(cal); print_rule(cal, fill); return 0

    gap = (actual / prev_close - 1) * 100
    in_range = (low <= actual <= high) if (low is not None and high is not None) else None
    verdict = 'hit' if in_range else 'miss'
    center = ((low + high) / 2 / prev_close - 1) * 100 if in_range is not None else None
    sign_hit = (None if center is None else ((center > 0) == (gap > 0)) if abs(gap) > 0.005 else None)
    rec = {
        'date': fdate,
        'low': low, 'high': high,
        'band_width_pct': round((high - low) / prev_close * 100, 2) if in_range is not None else None,
        'prev_close': prev_close, 'actual_open': actual,
        'gap_pct': round(gap, 2),
        'in_range': in_range, 'verdict': verdict,
        'sign_hit': sign_hit,
        'center_pct': round(center, 2) if center is not None else None,
        'center_err_pct': round(gap - center, 2) if center is not None else None,
        'signals': state.get('signals'),
        'source': '%s 회차 채점 (score.py, %s)' % (str(fill.get('issue_date') or ''), src),
    }
    if abs(gap) > 15:
        print('경고 갭 %+.1f%% — 시초가나 기준 종가가 잘못됐을 가능성. 기록은 남기되 사람이 확인할 것' % gap)
    recs.append(rec)
    print('%s 회차 — %s (전망 %s~%s / 실제 시초가 %s, 갭 %+.2f%%, 구간 %s)' % (
        fdate, '적중' if verdict == 'hit' else '빗나감',
        '{:,.0f}'.format(low) if low is not None else '—', '{:,.0f}'.format(high) if high is not None else '—',
        '{:,.2f}'.format(actual), gap, '안' if in_range else '밖'))
    if not dry:
        io.open('calibration.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(cal, ensure_ascii=False, indent=1) + '\n')
        print('calibration.json 기록 %d건' % len(recs))
    else:
        print('(dry-run) calibration.json 은 쓰지 않음')
    print_summary(cal); print_rule(cal, fill)
    return 0

def print_summary(cal):
    recs = cal.get('records') or []
    sc = [r for r in recs if r.get('in_range') is not None]
    if not recs: print('누적 기록 없음'); return
    cov = sum(1 for r in sc if r['in_range']) / len(sc) if sc else 0
    bws = [r['band_width_pct'] for r in recs if r.get('band_width_pct') is not None]
    print('누적 %d회차 — 적중(구간 안) %.1f%% (%d/%d, 목표 80%%) · 평균 구간폭 %.2f%%p' % (
        len(recs), cov * 100, sum(1 for r in sc if r['in_range']), len(sc), sum(bws) / len(bws) if bws else 0))
    gaps = [abs(r['gap_pct']) for r in recs[-10:] if r.get('gap_pct') is not None]
    if gaps:
        print('참고 — 최근 %d회 |갭| 중앙 %.2f%% · 80퍼센타일 %.2f%%' % (len(gaps), pctl(gaps, 0.5), pctl(gaps, 0.8)))

def holidays_between(fill):
    """직전 영업일~발행일 사이 휴장일(render.night_session_skipped 와 같은 판정). 판정 못 하면 []."""
    try:
        from datetime import date, datetime, timedelta, timezone
        from render import night_session_skipped
        d = fill.get('issue_date') or datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        return night_session_skipped(date.fromisoformat(str(d)))
    except Exception:
        return []

def half_width(rule, k200n):
    """반폭(%). scaled = q × (base + |야간선물|), fixed = half_width_pct. 2026-10-16 scaled 로 전환(CALIBRATION.md)"""
    if (rule.get('half_width_mode') or 'fixed') == 'scaled':
        q, b = num(rule.get('half_width_q')), num(rule.get('half_width_base'))
        return None if (q is None or b is None or k200n is None) else q * (b + abs(k200n))
    return num(rule.get('half_width_pct'))

def print_rule(cal, fill):
    rule = cal.get('rule') or {}
    cs = rule.get('center_signal')
    if not cs:
        print('규칙 상태 — rule.applied=%s, center_signal 없음 → 전망은 기존 방식(사람 판단)대로. 야간선물·시사 갭은 기록만 한다.' % rule.get('applied'))
        return
    k200n = num(((fill.get('prices') or {}).get('K200N') or {}).get('pct_screen'))
    prev = num(((fill.get('prices') or {}).get('KOSPI') or {}).get('close'))
    hw = half_width(rule, k200n)
    how = ('= %s × (%s + |야간|)' % (rule.get('half_width_q'), rule.get('half_width_base'))) if (rule.get('half_width_mode') or 'fixed') == 'scaled' else '고정'
    hol = holidays_between(fill)
    if cs == 'k200n' and hol:
        # 휴장일에도 미국장은 열리는 게 보통이다. 야간선물(연휴 전 밤 세션)은 그 미국장을 담지 못한다 — 2026-10-06 회차 실측
        print('규칙 적용 실패 — 휴장(%s) 뒤 회차라 야간선물이 휴장 중 미국장을 반영하지 못한다(값이 있어도 묵은 값). RUNBOOK 4절 폴백(사람 판단, 반폭 1.5%% 이상, EWY·ADR 단독 방향 금지)으로 전망하고 세션 응답에 "규칙 폴백" 이라고 밝힌다.' % ', '.join(hol))
    elif cs == 'k200n' and k200n is not None and prev and hw is not None:
        lo, hi = prev * (1 + (k200n - hw) / 100), prev * (1 + (k200n + hw) / 100)
        print('규칙 적용 — 구간 중심 = 야간선물 %+.2f%%, 반폭 %.2f%% (%s) → %s ~ %s (이 값을 forecast 에 그대로 쓴다)' % (
            k200n, hw, how, '{:,.0f}'.format(round(lo, -1)), '{:,.0f}'.format(round(hi, -1))))
    else:
        print('규칙 적용 실패 — center_signal=%s 인데 야간선물 값 또는 반폭이 없음. RUNBOOK 4절 폴백(사람 판단, 반폭 1.5%% 이상, EWY·ADR 단독 방향 금지)으로 전망하고 세션 응답에 "규칙 폴백" 이라고 밝힌다.' % cs)

def score_stocks(dry):
    """삼전·하닉 시초가 채점 → calibration.json stock_records. 코스피 채점이 끝난 뒤 파일을 다시 읽어 붙인다."""
    try:
        state = json.load(io.open('state.json', encoding='utf-8'))
        fill = load_fill()
        cal = json.load(io.open('calibration.json', encoding='utf-8'))
    except Exception as e:
        print('종목 채점 불가 — %s' % e); return
    sf = state.get('stock_forecast') or {}
    items, fdate = sf.get('items') or {}, sf.get('date')
    if not items or not fdate:
        print('종목 채점 — 직전 회차에 종목 전망 없음 (v5 이전 회차)'); return
    recs = cal.setdefault('stock_records', [])
    done = {(r.get('date'), r.get('code')) for r in recs}
    added = []
    for code, f in sorted(items.items()):
        if (fdate, code) in done:
            print('종목 채점 — %s %s 이미 기록됨' % (fdate, code)); continue
        p = (fill.get('prices') or {}).get(code) or {}
        op, od = num(p.get('open')), p.get('open_date')
        low, high, pc = num(f.get('low')), num(f.get('high')), num(f.get('prev_close'))
        if op is None or od != fdate or not pc:
            print('종목 채점 불가 — %s 시초가(prices.%s.open, open_date=%s) 없음 또는 날짜 불일치' % (code, code, fdate)); continue
        gap = (op / pc - 1) * 100
        center = num(f.get('center_pct'))
        rec = {'date': fdate, 'code': code, 'low': low, 'high': high, 'prev_close': pc, 'actual_open': op,
               'gap_pct': round(gap, 2), 'in_range': bool(low <= op <= high), 'center_pct': center,
               'center_err_pct': None if center is None else round(gap - center, 2),
               'band_width_pct': round((high - low) / pc * 100, 2), 'inputs': f.get('inputs'),
               'source': '%s 회차 채점 (score.py, prices.%s.open)' % (fill.get('issue_date') or '', code)}
        recs.append(rec); added.append(rec)
        print('종목 %s %s — 예측 %s~%s / 실제 시초가 %s (갭 %+.2f%%) → 구간 %s' % (code, fdate, '{:,.0f}'.format(low), '{:,.0f}'.format(high),
              '{:,.0f}'.format(op), gap, '안' if rec['in_range'] else '밖'))
    for code in sorted({r['code'] for r in recs}):
        rr = [r for r in recs if r['code'] == code]
        print('종목 %s 누적 %d회 — 구간 안 %d' % (code, len(rr), sum(1 for r in rr if r['in_range'])))
    if added and not dry:
        io.open('calibration.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(cal, ensure_ascii=False, indent=1) + '\n')
        print('calibration.json stock_records %d건' % len(recs))

if __name__ == '__main__':
    rc = main()
    score_stocks('--dry-run' in sys.argv)
    sys.exit(rc)
