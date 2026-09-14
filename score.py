#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score.py — 직전 회차 전망 채점 + calibration.json append

읽는 것 : state.json (직전 회차의 forecast·signals), fill.json (prices.KOSPI.open = 직전 영업일 실제 시초가), calibration.json
쓰는 것 : calibration.json (records 끝에 1건 append. rule 블록은 절대 손대지 않는다)

규칙 (CALIBRATION.md 와 같다)
  방향 판정 : |갭| <= 0.5% 는 보합, +0.5% 초과 갭상승, -0.5% 미만 갭하락
  hit       : 방향이 맞고 동시에 실제 시초가가 [low, high] 안. 그 외 전부 miss
  sign_hit  : 구간 중심(low·high 평균)의 부호와 실제 갭 부호가 같은가 (참고용, 판정에 안 씀)

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

def direction(gap):
    if gap > 0.5: return '갭상승'
    if gap < -0.5: return '갭하락'
    return '보합'

def norm_dir(s):
    s = str(s or '')
    for d in ('갭상승', '갭하락', '보합'):
        if s.startswith(d): return d
    return s

def pctl(xs, p):
    xs = sorted(xs)
    if not xs: return None
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[int(k)] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)

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
    fill = json.load(io.open('fill.json', encoding='utf-8'))

    fc = state.get('forecast') or {}
    fdate, fdir = fc.get('date'), norm_dir(fc.get('dir'))
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
    adir = direction(gap)
    dir_hit = (adir == fdir)
    verdict = 'hit' if (dir_hit and in_range) else 'miss'
    center = ((low + high) / 2 / prev_close - 1) * 100 if in_range is not None else None
    sign_hit = (None if center is None else ((center > 0) == (gap > 0)) if abs(gap) > 0.005 else None)
    rec = {
        'date': fdate, 'forecast_dir': fdir,
        'low': low, 'high': high,
        'band_width_pct': round((high - low) / prev_close * 100, 2) if in_range is not None else None,
        'prev_close': prev_close, 'actual_open': actual,
        'gap_pct': round(gap, 2),
        'in_range': in_range, 'dir_hit': dir_hit, 'verdict': verdict,
        'sign_hit': sign_hit,
        'center_pct': round(center, 2) if center is not None else None,
        'center_err_pct': round(gap - center, 2) if center is not None else None,
        'signals': state.get('signals'),
        'source': '%s 회차 채점 (score.py, %s)' % (str(fill.get('issue_date') or ''), src),
    }
    if abs(gap) > 15:
        print('경고 갭 %+.1f%% — 시초가나 기준 종가가 잘못됐을 가능성. 기록은 남기되 사람이 확인할 것' % gap)
    recs.append(rec)
    print('%s 회차 — %s (전망 %s %s~%s / 실제 시초가 %s, 갭 %+.2f%%, 실제 방향 %s, 구간 %s)' % (
        fdate, '적중' if verdict == 'hit' else '빗나감', fdir,
        '{:,.0f}'.format(low) if low is not None else '—', '{:,.0f}'.format(high) if high is not None else '—',
        '{:,.2f}'.format(actual), gap, adir, '안' if in_range else '밖'))
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
    dirh = sum(1 for r in recs if r.get('dir_hit')) / len(recs)
    bws = [r['band_width_pct'] for r in recs if r.get('band_width_pct') is not None]
    print('누적 %d회차 — 구간 커버리지 %.1f%% (%d/%d) · 방향 적중 %.1f%% · 평균 구간폭 %.2f%%p' % (
        len(recs), cov * 100, sum(1 for r in sc if r['in_range']), len(sc), dirh * 100, sum(bws) / len(bws) if bws else 0))
    gaps = [abs(r['gap_pct']) for r in recs[-10:] if r.get('gap_pct') is not None]
    if gaps:
        print('참고 — 최근 %d회 |갭| 중앙 %.2f%% · 80퍼센타일 %.2f%%' % (len(gaps), pctl(gaps, 0.5), pctl(gaps, 0.8)))

def print_rule(cal, fill):
    rule = cal.get('rule') or {}
    cs = rule.get('center_signal')
    hw = num(rule.get('half_width_pct'))
    if not cs:
        print('규칙 상태 — rule.applied=%s, center_signal 없음 → 전망은 기존 방식(사람 판단)대로. 야간선물·시사 갭은 기록만 한다.' % rule.get('applied'))
        return
    k200n = num(((fill.get('prices') or {}).get('K200N') or {}).get('pct_screen'))
    prev = num(((fill.get('prices') or {}).get('KOSPI') or {}).get('close'))
    if cs == 'k200n' and k200n is not None and prev and hw is not None:
        lo, hi = prev * (1 + (k200n - hw) / 100), prev * (1 + (k200n + hw) / 100)
        d = '갭상승' if k200n > 0.5 else ('갭하락' if k200n < -0.5 else '보합')
        print('규칙 적용 — 구간 중심 = 야간선물 %+.2f%%, 반폭 %.2f%% → %s %s ~ %s (이 값을 forecast 에 그대로 쓴다)' % (
            k200n, hw, d, '{:,.0f}'.format(round(lo, -1)), '{:,.0f}'.format(round(hi, -1))))
    else:
        print('규칙 적용 실패 — center_signal=%s 인데 야간선물 값 또는 반폭이 없음. 기존 방식으로 전망하고 세션 응답에 밝힌다.' % cs)

if __name__ == '__main__':
    sys.exit(main())
