#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_relay.py — 중계기(토스 Open API)에서 직전 영업일 국내 시세·수급과 미국 종가를 받아 relay.json 에 둔다

루틴 턴 0 에서 fetch_perp.py 와 같이 돌린다. LLM 이 아니라 이 스크립트가 받는다. 회차 토큰을 쓰지 않는다.
score.py·render.py 는 fill.json 을 읽은 뒤 merge_into() 로 relay.json 값을 합친다. 그래서 회차가 fill.json 에
값을 옮겨 적지 않아도 빈칸이 채워지고, 회차가 적은 값과 다르면 경고가 나온다(2026-10-21 도입).

  python3 fetch_relay.py                    relay.json 을 쓴다 (실패해도 종료 코드 0 — 발행을 막지 않는다)
  python3 fetch_relay.py --date 2026-10-21  발행일 지정 (기본 오늘 KST). 직전 영업일은 holidays.json 으로 정한다
  python3 fetch_relay.py --print            relay.json 을 쓰지 않고 출력만

환경 변수 JJ_RELAY_URL · JJ_RELAY_TOKEN(루틴 키). 키는 헤더로만 보내고 파일·출력에 남기지 않는다.

합치는 규칙 (merge_into)
  - fill 값이 비어 있으면 중계기 값으로 채운다.
  - 둘 다 있고 다르면: 국내 종목 종가·시가(KRX 1분봉, complete)·코스피·코스닥 지수·수급(18시 뒤 확정치)은 중계기 값을 쓴다.
    미국 종가·환율은 회차 값을 둔다. 어느 쪽이든 경고로 알린다.
  - relay.json 의 issue_date 가 fill 과 다르면(어제 파일) 쓰지 않는다.
"""
import io, json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone, date

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
OUT = 'relay.json'
KR = ['005930', '000660', '402340', '009150', '0167A0', '442580']
US = ['NVDA', 'MU', 'EWY', 'SKHY']
OPEN_KEYS = ['KOSPI', '005930', '000660']   # 채점에 쓰는 시가
FLOW_KEYS = ['foreign', 'inst', 'retail', 'other']

def prev_business_day(d):
    from render import holiday_of
    x = d - timedelta(days=1)
    while holiday_of(x): x -= timedelta(days=1)
    return x

def get(base, key, path, timeout=60):
    req = urllib.request.Request(base.rstrip('/') + path, headers={'X-Relay-Key': key, 'Accept': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def normalize(daily, cal, issue, p):
    """중계기 응답 → fill.json 과 같은 이름의 값. 못 받은 항목은 넣지 않는다."""
    out = {'schema': 1, 'ok': True, 'issue_date': issue.isoformat(), 'date': p.isoformat(),
           'fetched_at': datetime.now(KST).strftime('%Y-%m-%dT%H:%M:%S+09:00'), 'prices': {}, 'errors': list(daily.get('errors') or [])}
    P = out['prices']
    for k in ('KOSPI', 'KOSDAQ'):
        c = (daily.get('index') or {}).get(k)
        if c and c.get('close') is not None:
            P[k] = {'close': c['close'], 'open': c.get('open'), 'open_date': p.isoformat(), 'high': c.get('high'), 'low': c.get('low'), 'src': 'toss-index'}
    for k in KR:
        c = (daily.get('kr') or {}).get(k)
        if c and c.get('close') is not None:
            P[k] = {'close': c['close'], 'open': c.get('open'), 'open_date': p.isoformat(), 'high': c.get('high'), 'low': c.get('low'),
                    'src': c.get('src'), 'complete': c.get('complete')}
    for k in US:   # 발행일 전날까지의 마지막 미국 거래일 봉
        rows = [r for r in (daily.get('us') or {}).get(k) or [] if str(r.get('date', ''))[:10] < issue.isoformat()]
        if rows:
            r = max(rows, key=lambda r: r['date'])
            P[k] = {'close': r['close'], 'date': r['date'][:10], 'src': 'toss-1d'}
    fc = daily.get('fx_close')
    if fc and fc.get('mid'):
        P['USDKRW'] = {'close': fc['mid'], 'asof': (fc.get('from') or '')[:16], 'src': 'toss-fx-1530', 'approx': True}
    f = daily.get('flow')
    if f and str(daily.get('date')) == p.isoformat():
        upd = str(f.get('updatedAt') or '')
        final = upd[:10] > p.isoformat() or (upd[:10] == p.isoformat() and upd[11:13] >= '18')   # 18시 뒤 갱신이면 확정치
        out['flow'] = dict({k: f.get(k) for k in FLOW_KEYS}, updatedAt=upd, final=final)
    if daily.get('stock_flow'): out['stock_flow'] = daily['stock_flow']
    if cal: out['calendar'] = cal
    return out

def calendar_notes(rel, issue):
    """토스 장 달력과 holidays.json 이 다르면 알린다. 미국 휴장 여부도 적는다."""
    from render import holiday_of
    cal, notes = rel.get('calendar') or {}, []
    kr = (cal.get('kr') or {}).get('today') or {}
    if kr.get('date') == issue.isoformat():
        hol = holiday_of(issue)
        if kr.get('open') is False and not hol: notes.append('토스 달력은 오늘(%s) 국내 휴장인데 holidays.json 에 없음 — 확인 후 holidays.json 에 추가' % issue)
        if kr.get('open') and hol: notes.append('holidays.json 은 오늘 휴장(%s)인데 토스 달력은 개장 — holidays.json 확인' % hol)
    # 발행일 아침에 끝난 미국장 = 발행일 전날(주말이면 금요일). 토스 달력의 직전 영업일이 그보다 이르면 그날 미국 휴장
    exp = issue - timedelta(days=1)
    while exp.weekday() >= 5: exp -= timedelta(days=1)
    pb = ((cal.get('us') or {}).get('previousBusinessDay') or {}).get('date')
    if pb and pb < exp.isoformat(): notes.append('미국 %s 휴장(토스 달력) — 미국 종가는 %s 값이 그대로다. render.py 가 EWY·ADR 시사 갭을 뺀다' % (exp, pb))
    return notes

def fetch(issue):
    base, key = os.environ.get('JJ_RELAY_URL', '').strip(), os.environ.get('JJ_RELAY_TOKEN', '').strip()
    p = prev_business_day(issue)
    if not (base and key):
        return {'schema': 1, 'ok': False, 'issue_date': issue.isoformat(), 'date': p.isoformat(), 'reason': 'JJ_RELAY_URL/JJ_RELAY_TOKEN 없음'}
    try:
        daily = get(base, key, '/v1/daily?date=%s&us_until=%s' % (p.isoformat(), issue.isoformat()))
    except Exception as e:
        return {'schema': 1, 'ok': False, 'issue_date': issue.isoformat(), 'date': p.isoformat(), 'reason': '중계기 /v1/daily 실패 — %s' % str(e)[:120]}
    try: cal = get(base, key, '/v1/calendar?date=%s' % issue.isoformat(), timeout=20)
    except Exception: cal = None   # VM 이 옛 코드면 404. 달력 대조만 건너뛴다
    return normalize(daily, cal, issue, p)

def sg(v):
    return '—' if v is None else '{:+,.0f}'.format(v)

def fmt(v, dec=2):
    if v is None: return '—'
    return '{:,.0f}'.format(v) if dec == 0 else '{:,.{d}f}'.format(v, d=dec)

def report(rel):
    if not rel.get('ok'):
        print('중계기 실패 — %s. RUNBOOK 2단계 기존 경로(웹)로 받는다' % rel.get('reason')); return
    P, d = rel['prices'], rel['date']
    print('중계기 OK — %s 기준 (발행 %s)' % (d, rel['issue_date']))
    ix = ['%s 종가 %s 시가 %s' % (k, fmt(P[k]['close']), fmt(P[k].get('open'))) for k in ('KOSPI', 'KOSDAQ') if k in P]
    print('  지수 ' + ' · '.join(ix) if ix else '  지수 없음')
    kr = ['%s %s%s' % (k, fmt(P[k]['close'], 0), (' (시가 %s)' % fmt(P[k]['open'], 0)) if k in OPEN_KEYS else '') +
          ('' if P[k].get('complete') is not False else '*') for k in KR if k in P]
    print('  국내(KRX 1분봉) ' + ' · '.join(kr) + ('  * complete=false — 시가·종가 봉이 비었던 종목' if any(P[k].get('complete') is False for k in KR if k in P) else ''))
    us = ['%s %s' % (k, fmt(P[k]['close'])) for k in US if k in P]
    if us: print('  미국(%s) ' % P[[k for k in US if k in P][0]]['date'] + ' · '.join(us))
    if 'USDKRW' in P: print('  환율 %s (%s 매매기준율 — 서울 종가 근사, 웹 종가가 있으면 그쪽)' % (fmt(P['USDKRW']['close']), P['USDKRW']['asof'][11:16] or '15:30'))
    f = rel.get('flow')
    if f: print('  수급(억원) 외국인 %s · 기관 %s · 개인 %s · 기타법인 %s — %s %s' % (
        *[sg(f.get(k)) for k in FLOW_KEYS], '확정' if f.get('final') else '잠정', f.get('updatedAt', '')[5:16]))
    sf = rel.get('stock_flow') or {}
    for k, v in sorted(sf.items()):
        print('  %s 순매수(주) 외국인 %s · 기관 %s · 개인 %s' % (k, *[sg(v.get(x)) for x in ('foreign', 'inst', 'retail')]))
    for n in calendar_notes(rel, date.fromisoformat(rel['issue_date'])): print('  달력 ' + n)
    for e in rel.get('errors') or []: print('  일부 실패 — %s' % e)
    print('  → 위 값은 score.py·render.py 가 fill.json 빈칸에 자동으로 채운다. fill.json 에 적을 때는 이 값을 1순위로 쓴다.')

def covered(rel):
    """중계기가 이번에 받은 필드 (datalog 의 필드 이름)"""
    if not rel.get('ok'): return set()
    out = set()
    for k, r in (rel.get('prices') or {}).items():
        out.add('prices.%s.close' % k)
        if k in OPEN_KEYS and r.get('open') is not None: out.add('prices.%s.open' % k)
    out |= {'flow.%s' % k for k in FLOW_KEYS if (rel.get('flow') or {}).get(k) is not None}
    return out

# ---------- 합치기 (score.py·render.py 가 부른다) ----------
def load(path=OUT):
    try: return json.load(io.open(path, encoding='utf-8'))
    except Exception: return None

def _num(v):
    try: return None if v is None or isinstance(v, bool) else float(str(v).replace(',', ''))
    except Exception: return None

def merge_into(fill, rel=None):
    """fill(dict)을 제자리에서 보완. 반환 (상태, 채운 항목, 다른 항목). 상태 = ok | absent | fail | stale"""
    rel = load() if rel is None else rel
    if not rel: return 'absent', [], []
    if not rel.get('ok'): return 'fail', [], []
    if str(rel.get('issue_date')) != str(fill.get('issue_date')): return 'stale', [], []
    filled, diff = [], []
    prices = fill.setdefault('prices', {})
    for k, r in (rel.get('prices') or {}).items():
        p = prices.setdefault(k, {})
        official = (k in ('KOSPI', 'KOSDAQ')) or (k in KR and r.get('complete') is not False)
        fields = ['close'] + (['open', 'open_date'] if k in OPEN_KEYS and r.get('open') is not None else [])
        for fld in fields:
            rv = r.get(fld)
            if rv is None: continue
            fv = p.get(fld) if fld == 'open_date' else _num(p.get(fld))
            if fv in (None, ''):
                p[fld] = rv; filled.append('prices.%s.%s' % (k, fld))
                if fld == 'open' and not p.get('open_date'): p['open_date'] = r.get('open_date'); filled.append('prices.%s.open_date' % k)
                if k == 'USDKRW' and fld == 'close': p.setdefault('asof', 'toss %s' % r.get('asof', '')[11:16])
            elif fld == 'open_date':
                if fv != rv and official: diff.append('prices.%s.open_date 회차 %s / 중계기 %s → 중계기' % (k, fv, rv)); p[fld] = rv
            elif abs(fv - rv) > max(abs(rv) * 0.0005, 0.005):
                use = official and k != 'USDKRW'
                diff.append('prices.%s.%s 회차 %s / 중계기 %s → %s' % (k, fld, fv, rv, '중계기' if use else '회차 값 유지'))
                if use: p[fld] = rv
    f = rel.get('flow')
    if f:
        fl = fill.setdefault('flow', {})
        for k in FLOW_KEYS:
            rv, fv = f.get(k), _num(fl.get(k))
            if rv is None: continue
            if fv is None: fl[k] = rv; filled.append('flow.%s' % k)
            elif abs(fv - rv) > max(abs(rv) * 0.05, 300) and f.get('final'):
                diff.append('flow.%s 회차 %s / 중계기 %s(KRX 확정) → 중계기' % (k, sg(fv), sg(rv))); fl[k] = rv
    return 'ok', filled, diff

def main():
    issue = date.fromisoformat(sys.argv[sys.argv.index('--date') + 1]) if '--date' in sys.argv else datetime.now(KST).date()
    rel = fetch(issue)
    report(rel)
    try:
        from datacheck import streak_lines
        for line in streak_lines(covered(rel)): print(line)
    except Exception:
        pass
    if '--print' not in sys.argv:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(rel, ensure_ascii=False, indent=1) + '\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
