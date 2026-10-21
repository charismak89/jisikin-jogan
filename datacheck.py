#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""datacheck.py — 회차 데이터 누락 점검 (datalog.json + sources.json, 읽기 전용)

render.py 가 회차마다 datalog.json 에 한 줄을 남긴다: 무엇이 비었는지(missing), 중계기가 무엇을 채웠는지(relay_filled),
회차 값과 중계기 값이 어디서 갈렸는지(mismatch). 이 스크립트는 최근 N회를 세어 자주 빠지는 필드와 그 필드의 다음 경로를 보여 준다.

  python3 datacheck.py           최근 10회 점검 (토요일 주간 점검 WEEKLY.md 2-1)
  python3 datacheck.py --n 20

자가개선 고리 (2026-10-21 도입)
  매 회차  render.py 가 datalog.json 기록 → 다음 회차 턴 0 에 fetch_relay.py 가 '연속 누락' 필드와 다음 경로를 출력 → 회차가 그 경로를 1회 시도
  토요일   이 스크립트로 점검 대상(최근 10회 3회 이상, 또는 2회 연속)을 고르고, candidate 경로를 시험해 sources.json·RUNBOOK 변경을 제안 → 사용자 승인 뒤 반영
  다음 주  같은 점검으로 바꾼 경로가 누락을 줄였는지 본다
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
LOG = os.path.join(HERE, 'datalog.json')
SOURCES = os.path.join(HERE, 'sources.json')
CLOSE_KEYS = ['KOSPI', 'KOSDAQ', 'SOX', 'NVDA', 'MU', 'EWY', 'SKHY', 'K200F', 'USDKRW', 'K200N',
              '005930', '000660', '402340', '009150', '0167A0', '442580']

def missing_fields(fill, signals, open_date=None):
    """렌더 직전(중계기 보완 뒤) fill 에서 비어 있는 추적 필드. open_date 가 있으면 시가 날짜가 다른 것도 누락으로 센다."""
    P, out = fill.get('prices') or {}, []
    for k in CLOSE_KEYS:
        if (P.get(k) or {}).get('close') in (None, ''): out.append('prices.%s.close' % k)
    for k in ('KOSPI', '005930', '000660'):
        p = P.get(k) or {}
        if p.get('open') in (None, '') or (open_date and p.get('open_date') and p.get('open_date') != open_date):
            out.append('prices.%s.open' % k)
    fl = fill.get('flow') or {}
    out += ['flow.%s' % k for k in ('foreign', 'inst', 'retail', 'other') if fl.get(k) is None]
    if (signals or {}).get('es_pct') is None: out.append('signals.us_fut.es_pct')
    if (signals or {}).get('nq_pct') is None: out.append('signals.us_fut.nq_pct')
    if not (signals or {}).get('perp_asof'): out.append('signals.perp_asof')
    return out

def load_log(path=LOG):
    try: return json.load(io.open(path, encoding='utf-8'))
    except Exception: return {'schema': 1, 'entries': []}

def append_entry(entry, path=LOG, keep=250):
    """같은 날짜는 바꿔 쓴다(render.py 를 여러 번 돌려도 한 줄). 반환은 새 로그(dict) — 쓰기는 호출한 쪽이 정한다."""
    log = load_log(path)
    ent = [e for e in log.get('entries') or [] if e.get('date') != entry.get('date')] + [entry]
    ent.sort(key=lambda e: e.get('date') or '')
    log['entries'] = ent[-keep:]
    log.setdefault('schema', 1)
    log['note'] = 'render.py 가 회차마다 한 줄 남긴다. 점검은 datacheck.py. 사람이 고치지 않는다.'
    return log

def routes_for(field):
    try: src = json.load(io.open(SOURCES, encoding='utf-8'))
    except Exception: return None, []
    for g in src.get('groups') or []:
        if field in (g.get('fields') or []): return g, g.get('routes') or []
    return None, []

def next_route(field, skip=('relay',)):
    """primary 다음으로 시도할 경로(fallback → candidate 순). 없으면 None. 중계기는 fetch_relay.py 가 이미 시도했으니 뺀다."""
    _, rs = routes_for(field)
    for st in ('fallback', 'candidate'):
        for r in rs:
            if r.get('status') == st and r.get('id') not in skip: return r
    return None

def streaks(entries):
    """필드별로 끝에서부터 연속 누락 횟수."""
    out = {}
    for f in sorted({m for e in entries for m in e.get('missing') or []}):
        n = 0
        for e in reversed(entries):
            if f in (e.get('missing') or []): n += 1
            else: break
        if n: out[f] = n
    return out

def streak_lines(covered=(), min_streak=2):
    """fetch_relay.py 가 턴 0 에 출력한다 — 직전 회차까지 연속으로 빈 필드와 이번에 더 시도할 경로.
    covered = 이번에 중계기가 받은 필드. 그 필드는 이번엔 채워지므로 뺀다."""
    ent = load_log().get('entries') or []
    lines = []
    for f, n in sorted(streaks(ent).items(), key=lambda x: -x[1]):
        if n < min_streak or f in covered: continue
        r = next_route(f)
        lines.append('연속 누락 %d회 — %s → 이번 회차에 시도: %s' % (n, f, ('[%s] %s' % (r['id'], r['how'])) if r else '등록된 대안 없음(주간 점검 대상)'))
    return lines

def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 10
    ent = (load_log().get('entries') or [])[-n:]
    if not ent:
        print('datalog.json 기록 없음 — render.py 가 회차마다 남긴다'); return 0
    print('최근 %d회 (%s ~ %s)' % (len(ent), ent[0]['date'], ent[-1]['date']))
    rs = {}
    for e in ent: rs[e.get('relay') or '?'] = rs.get(e.get('relay') or '?', 0) + 1
    print('중계기 — ' + ' · '.join('%s %d' % kv for kv in sorted(rs.items())))
    cnt, fill_cnt, mis_cnt = {}, {}, {}
    for e in ent:
        for f in e.get('missing') or []: cnt[f] = cnt.get(f, 0) + 1
        for f in e.get('relay_filled') or []: fill_cnt[f] = fill_cnt.get(f, 0) + 1
        for m in e.get('mismatch') or []:
            k = m.split(' ')[0]; mis_cnt[k] = mis_cnt.get(k, 0) + 1
    st = streaks(ent)
    flagged = sorted([f for f in cnt if cnt[f] >= 3 or st.get(f, 0) >= 2], key=lambda f: (-cnt[f], f))
    print('\n누락 (필드 · 횟수 · 끝 연속)')
    for f in sorted(cnt, key=lambda f: (-cnt[f], f)):
        print('  %-26s %2d/%d  연속 %d%s' % (f, cnt[f], len(ent), st.get(f, 0), '  ← 점검 대상' if f in flagged else ''))
    if not cnt: print('  없음')
    if fill_cnt: print('\n중계기가 채운 필드 — ' + ' · '.join('%s %d' % kv for kv in sorted(fill_cnt.items(), key=lambda x: -x[1])))
    if mis_cnt: print('회차 값과 중계기 값이 갈린 필드 — ' + ' · '.join('%s %d' % kv for kv in sorted(mis_cnt.items(), key=lambda x: -x[1])))
    print('\n점검 대상과 경로 (sources.json)')
    if not flagged: print('  없음 — 이번 주는 경로를 바꿀 이유가 없다')
    for f in flagged:
        g, routes = routes_for(f)
        print('  %s (%s)' % (f, g['label'] if g else '등록부에 없음 — sources.json 에 그룹을 만든다'))
        for r in routes:
            print('    - [%s] %-9s %s%s' % (r.get('id'), r.get('status'), r.get('how'), ('  · ' + r['note']) if r.get('note') else ''))
        if routes and not any(r.get('status') in ('fallback', 'candidate') for r in routes):
            print('    → 대안 경로 없음: WebSearch 로 후보를 찾아 candidate 로 등록할 것을 제안')
    return 0

if __name__ == '__main__':
    sys.exit(main())
