#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_perp.py — 해외 24시간 추종가(Hyperliquid 무기한선물) 스냅샷 → perp.json

대시보드 "예측 → 실시간" 차트의 장외 구간(직전 영업일 15:30 ~ 지금)과 종목 예측 구간의 입력을 받는다.
LLM 이 아니라 이 스크립트가 받는다. 회차 토큰을 쓰지 않는다.

  python3 fetch_perp.py            perp.json 을 쓴다 (실패해도 종료 코드 0 — 발행을 막지 않는다)
  python3 fetch_perp.py --print    받은 값만 출력

대상 코드는 CONTEXT.md "해외 24시간 추종 상품" 표가 우선이고, 표가 없으면 아래 DEFAULT 를 쓴다.
Hyperliquid info API 는 인증이 없고 CORS 가 열려 있다. 바이낸스는 이 클라우드에서 지역 차단이라 쓰지 않는다(2026-10-15 실측).
"""
import io, json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone, date

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__)) or '.'
API = 'https://api.hyperliquid.xyz/info'
DEFAULT = {'KOSPI': 'xyz:KR200', '005930': 'xyz:SMSN', '000660': 'xyz:SKHX'}

def load_codes():
    """CONTEXT.md '해외 24시간 추종 상품' 절의 '| 대상 | 키 | 코드 |' 표에서 키→코드."""
    try:
        txt = io.open(os.path.join(HERE, 'CONTEXT.md'), encoding='utf-8').read()
    except Exception:
        return dict(DEFAULT)
    m = re.search(r'^##\s*해외 24시간 추종 상품[^\n]*\n(.*?)(?=^##\s|\Z)', txt, re.M | re.S)
    out = {}
    if m:
        for r in re.finditer(r'^\|\s*[^|]+?\s*\|\s*([A-Z0-9]+)\s*\|\s*(\w+:\w+)\s*\|', m.group(1), re.M):
            out[r.group(1)] = r.group(2)
    return out or dict(DEFAULT)

def prev_business_day(d):
    from render import holiday_of
    x = d - timedelta(days=1)
    while holiday_of(x): x -= timedelta(days=1)
    return x

def ms(d, h, m):
    return int(datetime(d.year, d.month, d.day, h, m, tzinfo=KST).timestamp() * 1000)

def post(body, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last

def main():
    now = datetime.now(KST)
    d = now.date()
    p = prev_business_day(d)
    t_prev = ms(p, 15, 30)
    start, end = ms(p, 15, 0), int(now.timestamp() * 1000)
    out = {'fetched_at': now.strftime('%Y-%m-%dT%H:%M:%S+09:00'), 'fetched_ms': end, 'issue_date': d.isoformat(),
           'prev_day': p.isoformat(), 't_prev': t_prev, 'source': 'Hyperliquid xyz 15분봉 종가', 'items': {}, 'errors': []}
    for key, coin in load_codes().items():
        try:
            cs = post({'type': 'candleSnapshot', 'req': {'coin': coin, 'interval': '15m', 'startTime': start, 'endTime': end}})
            pts = [[c['t'] + 900000, float(c['c'])] for c in cs if c['t'] + 900000 <= end]   # 봉 마감 시각 기준, 아직 안 닫힌 봉은 뺀다
            base = [c for t, c in pts if t <= t_prev]
            if not pts or not base:
                raise ValueError('15:30 기준 봉 없음 (%d봉)' % len(pts))
            out['items'][key] = {'coin': coin, 'base': base[-1], 'candles': [x for x in pts if x[0] >= t_prev]}
        except Exception as e:
            out['errors'].append('%s(%s): %s' % (key, coin, str(e)[:120]))
    for key, it in out['items'].items():
        last = it['candles'][-1]
        print('%-7s %s 기준 %.4g → %s %+.2f%% (%d봉)' % (key, it['coin'], it['base'],
              datetime.fromtimestamp(last[0] / 1000, KST).strftime('%m/%d %H:%M'), (last[1] / it['base'] - 1) * 100, len(it['candles'])))
    for e in out['errors']: print('실패', e)
    if '--print' not in sys.argv:
        io.open('perp.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False) + '\n')
        print('perp.json — %d개 받음, 실패 %d' % (len(out['items']), len(out['errors'])))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:   # 어떤 경우에도 발행을 막지 않는다
        print('fetch_perp 실패 — %s. 대시보드는 07:45 스냅샷 없이 렌더된다' % e)
        sys.exit(0)
