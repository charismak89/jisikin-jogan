#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_news.py — 직전 영업일 장 마감부터 발행 시각까지 나온 기사 제목을 시각, 매체와 함께 news.json 에 둔다(2026-11-27)

브리핑 '밤사이 뉴스' 시각표용이다(앤트위키 장전 브리핑의 '자는 동안 나온 뉴스' 벤치마킹, 사용자 결정 2026-11-27).
LLM 이 아니라 이 스크립트가 받는다. 회차 검색 횟수를 늘리지 않는다. 실패해도 종료 코드 0 — 발행을 막지 않는다.

  python3 fetch_news.py                    news.json 을 쓴다
  python3 fetch_news.py --date 2026-11-27  발행일 지정(기본 오늘 KST)
  python3 fetch_news.py --print            news.json 을 쓰지 않고 출력만

출처: Google 뉴스 RSS 검색(키 없음, 기사 시각 pubDate, 매체 source). 링크는 Google 뉴스 주소이고 누르면 원문으로 간다.
제목은 매체가 단 그대로이며 내용 확인을 거치지 않았다. 화면에도 그렇게 적는다.
"""
import io, json, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
OUT = 'news.json'
# CONTEXT.md 이슈 수집 범위 A(메모리), B(AI), C(매크로)를 넓게 덮는 검색어. 검색어마다 한 번만 부른다
QUERIES = ['코스피', '삼성전자', 'SK하이닉스', '반도체', '엔비디아', '뉴욕증시']
# 제목에 이 말이 많을수록 앞에 둔다(같으면 최근 것)
KEYS = ['코스피', '삼성', '하이닉스', '반도체', '메모리', 'HBM', 'D램', '엔비디아', '마이크론', 'TSMC', 'AI', '나스닥', '뉴욕', 'S&P',
        '관세', '금리', '연준', 'Fed', '환율', '외국인', '야간선물']
MAX = 10
PER_SRC = 2   # 한 매체 최대 건수
# 주요 매체(통신사, 경제지, 종합지, 방송, 해외 통신). 키워드를 잔뜩 넣은 작은 매체 제목이 앞을 차지해서 가중치를 준다(2026-11-27 시험)
MAJOR = ['연합뉴스', '연합인포맥스', '연합뉴스TV', '뉴스1', '뉴시스', '한국경제', '한경', '매일경제', '매경', '머니투데이', '이데일리', '서울경제',
         '조선비즈', 'Chosunbiz', '헤럴드경제', '아시아경제', '파이낸셜뉴스', '전자신문', '디지털타임스', '이투데이', '아주경제', '뉴스핌',
         '비즈니스포스트', '더벨', '한국금융신문', '조선일보', '중앙일보', '동아일보', '한국일보', '경향신문', '한겨레', '서울신문', '국민일보',
         '세계일보', '문화일보', 'KBS', 'MBC', 'SBS', 'YTN', 'JTBC', 'MBN', '디일렉', 'ZDNet', '지디넷코리아', 'Reuters', '로이터', 'Bloomberg',
         '블룸버그', 'CNBC', 'WSJ', '인베스팅']

def rss(q, timeout=15):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': q + ' when:1d', 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (jisikin-jogan news list)', 'Accept': 'application/rss+xml'})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=timeout).read())
    for it in root.iter('item'):
        try: at = parsedate_to_datetime(it.findtext('pubDate')).astimezone(KST)
        except Exception: continue
        src = (it.findtext('source') or '').strip()
        t = (it.findtext('title') or '').strip()
        # 제목 끝의 ' - 매체' 를 뗀다(매체 이름이 두 번 붙는 경우도 있다)
        while src and t.endswith(' - ' + src): t = t[: -len(' - ' + src)].strip()
        t = re.sub(r'\s+-\s+[^-]{1,20}$', '', t) if not src else t
        yield {'at': at, 't': t, 'src': src, 'url': it.findtext('link') or '', 'q': q}

def norm(t):
    return re.sub(r'[\W_]+', '', re.sub(r'\[[^\]]*\]', '', t))[:16]

def fetch(issue, now=None):
    from render import session_of, prev_business_day
    p = prev_business_day(issue)
    s = session_of(p)
    start = datetime(p.year, p.month, p.day, *s['close'], tzinfo=KST)
    end = min(datetime(issue.year, issue.month, issue.day, 7, 45, tzinfo=KST), now or datetime.now(KST))
    out = {'schema': 1, 'issue_date': issue.isoformat(), 'fetched_at': datetime.now(KST).strftime('%Y-%m-%dT%H:%M:%S+09:00'),
           'from': start.strftime('%m/%d %H:%M'), 'to': end.strftime('%m/%d %H:%M'), 'items': [], 'errors': []}
    seen, pool = set(), []
    for q in QUERIES:
        try:
            for x in rss(q):
                if not (start <= x['at'] <= end) or not x['t']: continue
                k = norm(x['t'])
                if k in seen: continue
                seen.add(k); pool.append(x)
        except Exception as e:
            out['errors'].append('%s %s' % (q, str(e)[:100]))
    major = lambda x: any(m.lower() in x['src'].lower() for m in MAJOR)
    score = lambda x: min(3, sum(1 for k in KEYS if k.lower() in x['t'].lower())) + (2 if major(x) else 0)
    pick, per = [], {}
    for x in sorted(pool, key=lambda x: (score(x), x['at']), reverse=True):
        if per.get(x['src'], 0) >= PER_SRC: continue
        per[x['src']] = per.get(x['src'], 0) + 1; pick.append(x)
        if len(pick) >= MAX: break
    pick.sort(key=lambda x: x['at'])
    out['items'] = [{'at': x['at'].strftime('%m/%d %H:%M'), 'ms': int(x['at'].timestamp() * 1000), 't': x['t'], 'src': x['src'], 'url': x['url']} for x in pick]
    out['pool'] = len(pool)
    out['ok'] = bool(out['items'])
    return out

def report(n):
    if not n.get('ok'):
        print('밤사이 뉴스 못 받음 — %s. 브리핑 시각표만 빠진다(게이트 무관)' % ('; '.join(n.get('errors') or []) or '조회 창 안 기사 없음'))
        return
    print('밤사이 뉴스 %d건(후보 %d건, %s~%s) — 브리핑 시각표에 자동으로 들어간다. 제목 목록으로 읽고, 쓸 재료는 본문을 열어 확인한다' % (
        len(n['items']), n.get('pool', 0), n['from'], n['to']))
    for x in n['items']:
        print('  %s %s — %s' % (x['at'][-5:], x['src'] or '매체 미상', x['t']))
    for e in n.get('errors') or []: print('  일부 실패 — %s' % e)

def main():
    from datetime import date
    issue = date.fromisoformat(sys.argv[sys.argv.index('--date') + 1]) if '--date' in sys.argv else datetime.now(KST).date()
    try: n = fetch(issue)
    except Exception as e: n = {'schema': 1, 'issue_date': issue.isoformat(), 'ok': False, 'items': [], 'errors': [str(e)[:200]]}
    report(n)
    if '--print' not in sys.argv:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(n, ensure_ascii=False, indent=1) + '\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
