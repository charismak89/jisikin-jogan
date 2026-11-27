#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jogan_relay.py — 토스증권 Open API 중계기 (지식인 조간 대시보드·루틴용)

토스 Open API 는 허용 IP 에서만 부를 수 있고, 토큰은 클라이언트당 1개만 유효하다(새로 발급하면 직전 토큰 즉시 무효).
그래서 토큰은 이 중계기 한 곳에서만 발급하고, 대시보드(지인 브라우저)와 07:45 루틴은 모두 여기를 거친다.
표준 라이브러리만 쓴다. 127.0.0.1 에만 열고 TLS 는 앞단 Caddy 가 맡는다.

엔드포인트 (루틴용은 루틴 키를 ?k= 또는 X-Relay-Key 헤더로. 화면용은 키가 없다)
  /healthz                       키 없이. 토큰 상태만
  /v1/live                       코스피·삼전·하닉 현재가 (5초 캐시)                     — 키 없이
  /v1/intraday?date=YYYY-MM-DD   그날 1분봉 종가 (코스피 정규장 — 평소 09:00~15:30, 수능일 10:00~16:30 — 두 종목 08:00~20:00) — 키 없이
  /v1/daily?date=YYYY-MM-DD[&us_until=YYYY-MM-DD]
                                 그날 일봉(시고저종)·환율·코스피 투자자별 매매대금 (루틴용) — 루틴 키
                                 2026-10-21 추가: 미국 일봉은 us_until(발행일) 전날까지 5개, 수급은 그날 것(until=date),
                                 fx_close(그날 15:30 매매기준율), stock_flow(삼전·하닉 투자자별 순매수 주식 수)
  /v1/calendar?date=YYYY-MM-DD   국내·미국 장 운영(전·당·익 영업일, 국내 정규장 시각 hours) — 휴장일, 장 시간 대조용 — 루틴 키
  POST /v1/feedback              대시보드 '의견' 버튼. 본문 JSON {cat, text, nick, ctx} → STATE_DIR/feedback.jsonl — 키 없이
  2026-11-10 지인 키를 없앴다(사용자 결정). 화면용 셋(live·intraday·의견 쓰기)은 공개 주소에서 누구나 쓴다. 키는 루틴 키 하나만 남는다.
  의견 쓰기는 대시보드 주소(ALLOW_ORIGINS)에서 온 요청만 받는다 — 브라우저는 Origin 을 늘 붙인다. 직접 호출을 막는 장치는 아니다(헤더는 흉내 낼 수 있다).
  이 글은 토요일 주간 점검 세션(Claude)이 읽는다. 누구나 쓸 수 있으니 읽는 쪽이 데이터로만 다룬다(WEEKLY.md 1절). IP 당 하루 5건·전체 하루 30건.
  업스트림 호출은 캐시가 묶는다(live 5초, intraday 오늘 20초·지난날 1시간, 날짜는 30일 안). 같은 키로 동시에 온 요청은 한 번만 업스트림을 부른다.
  IP 당 분당 120회 제한은 그대로다.
  GET  /v1/feedback?since=YYYY-MM-DD   그날부터 쌓인 의견 (토요일 주간 점검용)        — 루틴 키
  /v1/night                      코스피200 야간선물 근월물(한국투자증권 REST, 10초마다) 이번 또는 직전 야간 세션 — 키 없이(사용자 결정 2026-11-26)
                                 {session, code, name, state(live|waiting|closed), base(직전 주간 종가), last, pct, asof, open, high, low, bars[[1분봉 끝 ms, 값]],
                                  ohlc[[1분봉 끝 ms, 시, 고, 저, 종]](2026-11-27, 10초마다 받은 값으로 만든다. 그 전 세션 파일에는 없다)}
  /v1/stocks                     코스피, 코스닥 상장 종목 [코드, 이름, 시장] (관심종목 검색용, 6시간 캐시)        — 키 없이(2026-11-27 실험실)
  /v1/quotes?symbols=A,B         관심종목 시세, 최대 QUOTE_MAX 종목. 현재가(KRX+NXT 통합), 전일 대비(직전 세션 KRX 종가 기준),
                                 거래량(통합 일봉) — 키 없이(2026-11-27 실험실)
  /v1/stocks?mk=us               미국(NYSE, NASDAQ, AMEX) 종목 [티커, 이름, 거래소] (2026-11-27 실험실)               — 키 없이
  /v1/events?symbols=A,B         국내 종목의 DART 공시 일정(IR 개최, 잠정실적, 배당 기준일과 지급일), 최대 30종목 — 키 없이(DART_KEY 필요, 2026-11-27 실험실)
  /v1/kospi-daily                코스피 일봉 시, 고, 저, 종 최근 30개 (20거래일 캔들용, 1분 캐시)                  — 키 없이(2026-11-27 실험실)

환경 변수 (/etc/jogan-relay.env)
  TOSS_CLIENT_ID, TOSS_CLIENT_SECRET   토스 WTS 설정 > Open API 에서 받은 값
  PUBLIC_VIEW                          1(기본)이면 live·intraday·의견 쓰기를 키 없이 연다. 0 이면 닫는다(루틴 키만 통한다 — 대시보드는 해외 추종가로 그린다)
  ROUTINE_KEY                          루틴용 키 (/v1/daily 와 나머지 전부 허용)
  ALLOW_ORIGINS                        CORS 허용 Origin, 콤마 구분 (기본 https://charismak89.github.io)
  STATE_DIR                            토큰·의견 보관 (기본 /var/lib/jogan-relay)
  PORT                                 기본 8787
  TOSS_API                             기본 https://openapi.tossinvest.com (시험용으로만 바꾼다)
  KIS_APPKEY, KIS_APPSECRET            한국투자증권 실전 앱 키(야간선물). 없으면 /v1/night 는 503
  DART_KEY                             금감원 OpenDART 인증키(일정). 없으면 /v1/events 는 503
"""
import hmac, json, logging, os, re, secrets, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KST = timezone(timedelta(hours=9))
API = os.environ.get('TOSS_API', 'https://openapi.tossinvest.com').rstrip('/')
CID = os.environ.get('TOSS_CLIENT_ID', '')
CSECRET = os.environ.get('TOSS_CLIENT_SECRET', '')
ROUTINE_KEY = os.environ.get('ROUTINE_KEY', '').strip()
PUBLIC_VIEW = os.environ.get('PUBLIC_VIEW', '1').strip().lower() not in ('0', 'false', 'no', 'off')
PUBLIC_PATHS = ('/v1/live', '/v1/intraday', '/v1/night', '/v1/stocks', '/v1/quotes', '/v1/kospi-daily', '/v1/events', '/v1/flow')   # 화면용 조회. /v1/daily·의견 읽기는 언제나 루틴 키
ORIGINS = [o.strip() for o in os.environ.get('ALLOW_ORIGINS', 'https://charismak89.github.io').split(',') if o.strip()]
STATE_DIR = os.environ.get('STATE_DIR', '/var/lib/jogan-relay')
PORT = int(os.environ.get('PORT', '8787'))
KIS_AK = os.environ.get('KIS_APPKEY', '').strip().strip('"\'')
KIS_SK = os.environ.get('KIS_APPSECRET', '').strip().strip('"\'')
DART_KEY = os.environ.get('DART_KEY', '').strip().strip('"\'')

STOCKS = ['005930', '000660']            # 대시보드 종목
INDEX = 'KOSPI'
DAILY_KR = ['005930', '000660', '402340', '009150', '0167A0', '442580']   # 루틴 국내 6종
DAILY_US = ['NVDA', 'MU', 'EWY', 'SKHY', 'TSM', 'DRAM', 'ANT']             # 루틴 미국 4종 + 참고 시세 3종(2026-11-27, TSMC ADR, Roundhill 메모리 ETF, 앤트로픽)
DAILY_IDX = ['KOSPI', 'KOSDAQ']

log = logging.getLogger('jogan-relay')

class Upstream(Exception):
    def __init__(self, status, code, msg=''):
        super().__init__('%s %s %s' % (status, code, msg)); self.status, self.code = status, code

# ---------- 토큰: 이 프로세스만 발급한다 ----------
class Token:
    def __init__(self):
        self.lock = threading.Lock()
        self.value, self.exp, self.last_issue, self.fail_until = None, 0.0, 0.0, 0.0
        self.path = os.path.join(STATE_DIR, 'token.json')
        try:
            d = json.load(open(self.path))
            if d.get('exp', 0) > time.time() + 300: self.value, self.exp = d['value'], d['exp']
        except Exception:
            pass

    def get(self, force=False):
        with self.lock:
            if not force and self.value and time.time() < self.exp - 300:
                return self.value
            # 다른 곳에서 발급해 무효화된 경우 바로 다시 받되, 10초 안에 또 무효화되면(서로 무효화하는 싸움) 기다린다
            if self.value and time.time() - self.last_issue < 10:
                return self.value
            if time.time() < self.fail_until:   # 발급 실패(키 오류·IP 미허용) 직후 30초는 다시 두드리지 않는다
                raise Upstream(503, 'token-backoff')
            body = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': CID, 'client_secret': CSECRET}).encode()
            req = urllib.request.Request(API + '/oauth2/token', data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            try:
                d = json.load(urllib.request.urlopen(req, timeout=10))
            except urllib.error.HTTPError as e:
                self.fail_until = time.time() + 30
                try: err = json.load(e)
                except Exception: err = {}
                raise Upstream(e.code, err.get('error') or 'token', err.get('error_description', ''))
            self.last_issue = time.time()
            self.value, self.exp = d['access_token'], time.time() + int(d.get('expires_in', 86400))
            try:
                os.makedirs(STATE_DIR, exist_ok=True)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w') as f: json.dump({'value': self.value, 'exp': self.exp}, f)
            except Exception as e:
                log.warning('토큰 저장 실패: %s', e)
            log.info('토큰 발급 (만료 %s)', datetime.fromtimestamp(self.exp, KST).strftime('%m-%d %H:%M'))
            return self.value

TOKEN = Token()

def toss(path, params=None, retry=True):
    url = API + path + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + TOKEN.get(), 'Accept': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=10)).get('result')
    except urllib.error.HTTPError as e:
        try: err = (json.load(e) or {}).get('error') or {}
        except Exception: err = {}
        code = err.get('code', '')
        if e.code == 401 and retry and code in ('expired-token', 'token-revoked', 'invalid-token'):
            TOKEN.get(force=True)
            return toss(path, params, retry=False)
        if e.code == 429 and retry:
            time.sleep(1.0); return toss(path, params, retry=False)
        raise Upstream(e.code, code, err.get('message', ''))

# ---------- 캐시 ----------
# 같은 키로 동시에 온 요청은 하나만 업스트림을 부르고 나머지는 그 결과를 기다린다. 전에는 캐시가 빈 순간에 온 요청이
# 저마다 토스를 불러, 한 IP 가 캐시에 없는 날짜를 몰아 요청하면 토스 호출이 요청 수 × 18 로 늘었다(2026-11-10).
# 실패도 ERR_TTL 초 동안 기억한다 — 업스트림이 죽었을 때 줄 선 요청이 차례로 10초씩 기다리지 않게.
_cache, _clock, _klocks = {}, threading.Lock(), {}
ERR_TTL, CACHE_MAX = 3, 300
# 관심종목 시세(2026-11-27)는 종목 조합마다 키가 생겨서 따로 둔다 — 공용 캐시의 intraday, stocks 를 밀어내지 않게(검수)
_qcache, _qklocks = {}, {}
def cached(key, ttl, fn, store=None):
    _cache, _klocks = store or (globals()['_cache'], globals()['_klocks'])
    def fresh():
        hit = _cache.get(key)
        return hit if hit and time.time() - hit[0] < (ttl if hit[2] is None else min(ttl, ERR_TTL)) else None
    with _clock:
        hit = fresh()
        lk = None if hit else _klocks.setdefault(key, threading.Lock())
    if not hit:
        with lk:
            with _clock: hit = fresh()
            if not hit:
                try: hit = (time.time(), fn(), None)
                except Exception as e: hit = (time.time(), None, e)
                with _clock:
                    _cache[key] = hit
                    lim = CACHE_MAX if store is None else 2000
                    if len(_cache) > lim:   # 오래된 것부터 버린다(루틴 키 요청은 날짜가 제각각이라 끝없이 쌓일 수 있다)
                        for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[:len(_cache) - lim]:
                            _cache.pop(k, None); _klocks.pop(k, None)
    if hit[2] is not None: raise hit[2]
    return hit[1]

def iso_ms(s):
    return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000)

def ms(d, h, m):
    return int(datetime(d.year, d.month, d.day, h, m, tzinfo=KST).timestamp() * 1000)

# ---------- 데이터 ----------
def live():
    out = {'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': {}}
    for r in toss('/api/v1/prices', {'symbols': ','.join(STOCKS)}) or []:
        out['items'][r['symbol']] = {'last': float(r['lastPrice']), 't': r.get('timestamp')}
    for r in toss('/api/v1/market-indicators/prices', {'symbols': INDEX}) or []:
        out['items'][r['symbol']] = {'last': float(r['lastPrice']), 't': r.get('timestamp')}
    return out

def flow_now():
    """코스피 투자자별 순매수(억원) 최신 1건 — 첫 카드 수급 줄(2026-11-27 실험실). 장중 갱신 여부는 [검증 필요]: updatedAt 으로 본다."""
    out = {'asof': datetime.now(KST).isoformat(timespec='seconds')}
    res = toss('/api/v1/market-indicators/KOSPI/investor-trading', {'interval': '1d', 'count': 1}) or {}
    for r in (res.get('records') or [])[:1]:
        net = lambda x: None if not x else round((float(x['buyAmount']) - float(x['sellAmount'])) / 1e8)   # 억원
        out.update(date=r.get('date'), foreign=net(r.get('foreigner')), inst=net(r.get('institution')), retail=net(r.get('individual')),
                   other=net(r.get('otherCorporation')), updatedAt=r.get('updatedAt'))
    return out

def candles_1m(path, params, start_ms, end_ms):
    """최신순 200개씩 받아 start_ms 이전까지 거슬러 간다. 반환은 [봉 종료 ms, 시, 종, 고, 저] 오름차순(고, 저는 2026-11-27 캔들용으로 뒤에 붙였다)."""
    out, before, pages = {}, None, 0
    while pages < 6:
        q = dict(params, interval='1m', count=200)
        if before: q['before'] = before
        res = toss(path, q) or {}
        cs = res.get('candles') or []
        pages += 1
        for c in cs:
            # 종목·지수 모두 봉 종료 시각. 명세는 지수 봉을 '시작 시각'이라 적었지만 10/15 실측 코스피는 09:01~15:30 390봉이다
            t = iso_ms(c['timestamp'])
            if start_ms < t <= end_ms + 60000:
                o, cl = float(c['openPrice']), float(c['closePrice'])
                out[t] = [t, o, cl, float(c.get('highPrice') or max(o, cl)), float(c.get('lowPrice') or min(o, cl))]
        if not cs or not res.get('nextBefore') or iso_ms(cs[-1]['timestamp']) <= start_ms: break
        before = res['nextBefore']
    return [out[k] for k in sorted(out)]

def intraday(d):
    end = ms(d, 20, 0)
    if d == datetime.now(KST).date(): end = min(end, int(time.time() * 1000))
    before = (datetime(d.year, d.month, d.day, 20, 0, tzinfo=KST)).isoformat()
    hrs = kr_hours(d)
    t_open, t_close = hm_ms(d, hrs['open']), hm_ms(d, hrs['close'])
    items = {}
    for s in STOCKS:
        bars = candles_1m('/api/v1/candles', {'symbol': s, 'before': before}, ms(d, 8, 0), end)
        items[s] = {'bars': [[b[0], b[2]] for b in bars], 'ohlc': [[b[0], b[1], b[3], b[4], b[2]] for b in bars],
                    'open': next((b[1] for b in bars if b[0] > t_open), None)}
    bars = candles_1m('/api/v1/market-indicators/%s/candles' % INDEX, {'before': before}, t_open - 60000, min(end, t_close + 60000))   # 개장 1분 전부터 — 명세대로 개장 시각 봉이 와도 첫 봉을 잃지 않게
    items[INDEX] = {'bars': [[b[0], b[2]] for b in bars], 'ohlc': [[b[0], b[1], b[3], b[4], b[2]] for b in bars], 'open': bars[0][1] if bars else None}
    return {'date': d.isoformat(), 'asof': datetime.now(KST).isoformat(timespec='seconds'), 'hours': hrs, 'items': items}

def day_candle(path, params, d):
    res = toss(path, dict(params, interval='1d', count=10)) or {}
    for c in res.get('candles') or []:
        if c['timestamp'][:10] == d.isoformat():
            return {k: float(c[k + 'Price']) for k in ('open', 'high', 'low', 'close')}
    return None

def krx_day(s, d, hrs=None):
    """KRX 공식 시가·종가. 토스 종목 일봉은 KRX·NXT 통합(08:00~20:00)이라 1분봉에서 뽑는다.
    시가 = 개장 시각 +1분 봉(평소 09:01 봉)의 시가, 종가 = 종가 시각 +1분 봉(평소 15:31 봉, 종가 단일가)의 종가. 그 봉이 없으면 그 전 마지막 봉.
    개장, 종가 시각은 토스 달력(kr_hours)을 따른다 — 수능일은 10:01 봉, 16:31 봉(2026-11-19)."""
    hrs = hrs or kr_hours(d)
    t_open, t_last = hm_ms(d, hrs['open']), hm_ms(d, hrs['close'], 1)
    end = t_last
    if d == datetime.now(KST).date(): end = min(end, int(time.time() * 1000))
    before = datetime.fromtimestamp((t_last + 60000) / 1000, KST).isoformat()
    bars = [b for b in candles_1m('/api/v1/candles', {'symbol': s, 'before': before}, t_open, end) if t_open < b[0] <= t_last]   # candles_1m 은 끝 시각 뒤 1분 봉까지 주므로 잘라 낸다
    if not bars: return None
    return {'open': bars[0][1], 'close': bars[-1][2], 'src': 'krx-1m',
            'complete': bars[0][0] == t_open + 60000 and bars[-1][0] == t_last}   # False 면 시가·종가 봉이 비었다 — 쓰기 전에 확인

def daily(d, us_until=None):
    hrs = kr_hours(d)
    out = {'date': d.isoformat(), 'asof': datetime.now(KST).isoformat(timespec='seconds'), 'hours': hrs, 'kr': {}, 'us': {}, 'index': {}, 'errors': []}
    for s in DAILY_KR:
        try:
            c = day_candle('/api/v1/candles', {'symbol': s}, d)   # 통합 일봉: 고가·저가·거래 범위 참고용
            k = krx_day(s, d, hrs)
            if c and k: c = dict(c, nxt_open=c['open'], nxt_close=c['close'], open=k['open'], close=k['close'], src=k['src'], complete=k['complete'])
            elif c: c['src'] = 'toss-1d'   # 1분봉이 없는 날(보관 기간 지남) — 시가·종가는 NXT 통합값이라 KRX 공식값과 다를 수 있다
            out['kr'][s] = c
        except Exception as e: out['errors'].append('%s %s' % (s, str(e)[:120]))
    # 미국 일봉의 날짜는 미국 거래일 (현지 자정을 KST 로 표기 — 10/20 봉이 2026-10-20T13:00+09:00).
    # us_until(발행일) 00:00 KST 이전 봉만 받는다 — 발행일 아침에는 그 전날 미국 거래일 봉이 마지막이다. 없으면 date 다음 날
    ub = us_until or (d + timedelta(days=1))
    for s in DAILY_US:
        try:
            res = toss('/api/v1/candles', {'symbol': s, 'interval': '1d', 'count': 5,
                                           'before': datetime(ub.year, ub.month, ub.day, tzinfo=KST).isoformat()}) or {}
            cs = res.get('candles') or []
            out['us'][s] = [{'date': c['timestamp'], 'close': float(c['closePrice'])} for c in cs]
        except Exception as e: out['errors'].append('%s %s' % (s, str(e)[:120]))
    for s in DAILY_IDX:
        try: out['index'][s] = day_candle('/api/v1/market-indicators/%s/candles' % s, {}, d)
        except Exception as e: out['errors'].append('%s %s' % (s, str(e)[:120]))
    try:
        fx = toss('/api/v1/exchange-rate', {'baseCurrency': 'USD', 'quoteCurrency': 'KRW'}) or {}
        out['fx'] = {'mid': float(fx['midRate']), 'from': fx.get('validFrom')}
    except Exception as e: out['errors'].append('fx %s' % e)
    try:   # 그날 15:30 매매기준율 — 서울 외환시장 종가의 근사값(공식 종가 아님)
        fx = toss('/api/v1/exchange-rate', {'baseCurrency': 'USD', 'quoteCurrency': 'KRW',
                                            'dateTime': datetime(d.year, d.month, d.day, 15, 30, tzinfo=KST).isoformat()}) or {}
        out['fx_close'] = {'mid': float(fx['midRate']), 'from': fx.get('validFrom')}
    except Exception as e: out['errors'].append('fx_close %s' % e)
    for s in STOCKS:   # 종목별 투자자 순매수(주식 수, KRX·NXT 통합). 외국인은 등록외국인 기준이라 시장 수급과 기준이 다르다
        try:
            res = toss('/api/v1/stocks/%s/investor-trading' % s, {'count': 1, 'until': d.isoformat()}) or {}
            for r in res.get('records') or []:
                if r.get('date') == d.isoformat():
                    nv = lambda x: None if not x else int(float(x['netBuyVolume']))
                    out.setdefault('stock_flow', {})[s] = {'foreign': nv(r.get('foreigner')), 'inst': nv(r.get('institution')),
                                                          'retail': nv(r.get('individual')), 'other': nv(r.get('otherCorporation')),
                                                          'updatedAt': r.get('updatedAt')}
        except Exception as e: out['errors'].append('stock_flow %s %s' % (s, e))
    try:
        res = toss('/api/v1/market-indicators/KOSPI/investor-trading', {'interval': '1d', 'count': 1, 'until': d.isoformat()}) or {}
        for r in res.get('records') or []:
            if r.get('date') == d.isoformat():
                net = lambda x: None if not x else round((float(x['buyAmount']) - float(x['sellAmount'])) / 1e8)   # 억원
                out['flow'] = {'foreign': net(r.get('foreigner')), 'inst': net(r.get('institution')), 'retail': net(r.get('individual')),
                               'other': net(r.get('otherCorporation')), 'updatedAt': r.get('updatedAt')}
    except Exception as e: out['errors'].append('flow %s' % e)
    return out

def _hm(iso):
    """'2026-11-19T10:00:00+09:00' → '10:00'. 못 읽으면 None."""
    try: return datetime.fromisoformat(str(iso).replace('Z', '+00:00')).astimezone(KST).strftime('%H:%M')
    except Exception: return None

def kr_session(day):
    """토스 국내 달력 하루치 → 정규장 시각 {'open', 'close', 'auction', 'pre'} 또는 None(휴장, 정보 없음, 이상한 값).
    open 은 KRX, NXT 정규장 합집합의 시작, auction 은 KRX 종가단일가 시작이다. close 는 KRX 종가 = auction + 10분이다.
    합집합 종료(endTime)는 NXT 가 더 늦게 닫는 날 KRX 종가가 아니라 쓰지 않는다. auction 이 없거나 시각이
    08:30~11:00 개장, 15:00~17:00 종가 밖이면 None 이라 호출한 쪽이 09:00~15:30 으로 돌아간다(2026-11-19 수능일)."""
    reg = ((day or {}).get('integrated') or {}).get('regularMarket') or {}
    op, au = _hm(reg.get('startTime')), _hm(reg.get('singlePriceAuctionStartTime'))
    if not (op and au): return None
    h, m = (int(x) for x in au.split(':')); m += 10; cl = '%02d:%02d' % (h + m // 60, m % 60)
    if not ('08:30' <= op <= '11:00' and '15:00' <= cl <= '17:00'): return None
    return {'open': op, 'close': cl, 'auction': au,
            'pre': bool(((day or {}).get('integrated') or {}).get('preMarket'))}

def calendar(d):
    """국내·미국 장 운영. 각 시장의 전·당·익 영업일과 그날 열리는지(open). 미국 date 는 현지 날짜.
    국내는 정규장 시각(hours: open, close, auction, pre)도 싣는다 — 수능일, 새해 첫 거래일처럼 늦게 여는 날(2026-11-19)."""
    out = {'date': d.isoformat(), 'errors': []}
    for mk, key in (('KR', 'integrated'), ('US', 'regularMarket')):
        try:
            r = toss('/api/v1/market-calendar/%s' % mk, {'date': d.isoformat()}) or {}
            out[mk.lower()] = {k: {'date': (r.get(k) or {}).get('date'), 'open': bool((r.get(k) or {}).get(key))}
                               for k in ('previousBusinessDay', 'today', 'nextBusinessDay')}
            if mk == 'KR':
                for k, v in out['kr'].items(): v['hours'] = kr_session(r.get(k))
        except Exception as e: out['errors'].append('%s %s' % (mk, e))
    return out

DEFAULT_HOURS = {'open': '09:00', 'close': '15:30', 'auction': '15:20', 'pre': True, 'src': 'default'}

def _kr_today_session(d):
    r = toss('/api/v1/market-calendar/KR', {'date': d.isoformat()}) or {}
    t = r.get('today') or {}
    if not t.get('date'): raise ValueError('market-calendar 빈 응답')   # 빈 응답을 1시간 기억하지 않게 실패로 돌린다(ERR_TTL)
    return kr_session(t) if t.get('date') == d.isoformat() else None

def kr_hours(d):
    """그날 KRX 정규장 시각. 토스 달력(1시간 캐시)이 그날을 정규장으로 답하면 그 값, 못 받으면 09:00~15:30(src default).
    /v1/calendar 캐시와 키를 나눴다 — 그쪽은 실패도 응답(errors)으로 1시간 남지만 여기는 실패를 ERR_TTL 초만 기억한다."""
    try:
        h = cached(('kr_hours', d), 3600, lambda: _kr_today_session(d))
        if h and h.get('open') and h.get('close'): return dict(h, src='toss-calendar')
    except Exception:
        pass
    return dict(DEFAULT_HOURS)

def hm_ms(d, hm, add_min=0):
    h, m = (int(x) for x in hm.split(':'))
    return ms(d, h, m) + add_min * 60000

# ---------- 관심종목, 코스피 일봉(2026-11-27 실험실, 사용자 결정 "관심종목 계획대로 실험실에, 20거래일 캔들") ----------
QUOTE_MAX = 20
SYM_RE = re.compile(r'^[0-9A-Z][0-9A-Z.\-]{0,9}$')   # 국내 6자리, 미국 티커(BRK.B 등)
is_kr = lambda x: len(x) == 6 and x[0].isdigit()
US_MK = ('NYSE', 'NASDAQ', 'AMEX')

def stock_list(mks=('KOSPI', 'KOSDAQ')):
    """상장(ACTIVE) 종목. 토스 명세가 하루 1회 받아 캐싱하라고 권한다. 미국은 따로 부른다(화면이 미국 검색 때만 받게)."""
    out = []
    for mk in mks:
        for r in toss('/api/v1/stocks/all', {'market': mk}) or []:
            if r.get('symbol') and r.get('name'): out.append([r['symbol'], r['name'], mk])
    if not out: raise ValueError('stocks/all 빈 응답')
    return {'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': out}

_base, _blk = {}, threading.Lock()
def krx_base(s, ref):
    """ref(최근 세션) 직전 세션의 KRX 종가. 종목, 날짜마다 한 번만 1분봉을 읽는다(실패는 기억하지 않는다).
    직전 세션 날짜는 일봉 목록에서 ref 바로 앞 날짜다. 1분봉이 없으면 None — 호출한 쪽이 통합 일봉 종가로 대신한다."""
    k = (s, ref)
    with _blk:
        if k in _base: return _base[k]
    try:
        d = date.fromisoformat(ref)
        v = krx_day(s, d)
        val = v['close'] if v else None
    except Exception as e:
        log.warning('KRX 종가 %s %s 실패: %s', s, ref, e); return None
    if val is None: return None   # 빈 응답은 기억하지 않는다(일시적일 수 있다)
    with _blk:
        if len(_base) > 3000: _base.clear()
        _base[k] = val
    return val

_ckeys_logged = False
def quote_one(s):
    """일봉 3개 → 최근 세션(ref)의 거래량과 그 전 세션 날짜. 전일 대비 기준은 그 전 세션의 KRX 종가.
    미국 종목은 그 전 세션 일봉 종가(base_src us-1d). 정규장 종가인지는 실측으로 확인할 것 [검증 필요]."""
    res = toss('/api/v1/candles', {'symbol': s, 'interval': '1d', 'count': 3}) or {}
    cs = res.get('candles') or []   # 최신순
    if not cs: return None
    ref, prev = cs[0], (cs[1] if len(cs) > 1 else None)
    out = {'ref': ref['timestamp'][:10], 'vol': float(ref.get('volume') or 0), 'base': None, 'base_src': None, 'amt': None}
    # 거래대금(2026-11-27 실험실). 토스 일봉의 필드 이름을 확인하지 못해 후보를 차례로 본다 [검증 필요]. 없으면 화면이 거래량 × 현재가로 어림한다
    global _ckeys_logged
    if not _ckeys_logged: _ckeys_logged = True; log.info('토스 일봉 필드: %s', sorted(ref))   # VM 에서 거래대금 필드 이름 확인용
    for k in ('amount', 'tradingValue', 'tradeAmount', 'tradingAmount', 'accTradePrice'):
        try:
            if ref.get(k) is not None: out['amt'] = float(ref[k]); break
        except (TypeError, ValueError): pass
    if prev and not is_kr(s):
        out['base'], out['base_src'] = float(prev['closePrice']), 'us-1d'
    elif prev:
        b = krx_base(s, prev['timestamp'][:10])
        out['base'], out['base_src'] = (b, 'krx') if b is not None else (float(prev['closePrice']), 'nxt-1d')
    return out

QSTORE = (_qcache, _qklocks)
def quotes(syms):
    out = {'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': {}, 'errors': []}
    # 상장 목록에 없는 코드(상장폐지 등)는 빼고 부른다 — 하나가 prices 전체를 실패시키지 않게(검수)
    try:
        listed = {x[0] for x in cached('stocks', 6 * 3600, stock_list)['items']}
        if any(not is_kr(x) for x in syms): listed |= {x[0] for x in cached('stocks-us', 6 * 3600, lambda: stock_list(US_MK))['items']}
        bad = [x for x in syms if x not in listed]
        if bad: out['errors'].append('목록에 없음 %s' % ','.join(bad)); syms = [x for x in syms if x in listed]
    except Exception as e:   # 목록을 못 받으면 국내 6자리 코드만 부른다(검증 안 된 티커가 prices 를 통째로 실패시키지 않게)
        log.warning('종목 목록 실패: %s', e)
        syms = [x for x in syms if re.fullmatch(r'\d{5}[0-9A-Z]', x)]
    if not syms: return out
    px = {}
    for grp in ([x for x in syms if is_kr(x)], [x for x in syms if not is_kr(x)]):   # 국내, 미국을 따로 부른다(섞어 부를 수 있는지 명세에 없다)
        if grp: px.update({r['symbol']: r for r in (toss('/api/v1/prices', {'symbols': ','.join(grp)}) or [])})
    def one(s):
        try: return s, cached(('q1', s), 30, lambda: quote_one(s), QSTORE), None
        except Exception as e: return s, None, e
    with ThreadPoolExecutor(max_workers=5) as ex:   # 처음 보는 종목은 1분봉을 몇 쪽 읽어 순서대로면 수십 초 걸린다(검수)
        qs = {s: (q, e) for s, q, e in ex.map(one, syms)}
    for s in syms:
        q, e = qs[s]
        if e is not None: out['errors'].append('%s %s' % (s, e))
        p = px.get(s)
        if not p and not q: continue
        last = float(p['lastPrice']) if p else None
        base = (q or {}).get('base')
        it = {'last': last, 't': (p or {}).get('timestamp'), 'cur': (p or {}).get('currency'), 'base': base, 'base_src': (q or {}).get('base_src'),
              'vol': (q or {}).get('vol'), 'amt': (q or {}).get('amt'), 'ref': (q or {}).get('ref')}
        if last is not None and base:
            it['chg'] = round(last - base, 4); it['pct'] = round((last / base - 1) * 100, 2)
        out['items'][s] = it
    return out

# ---------- DART 공시 일정(2026-11-27 실험실, 사용자 결정 "캘린더 1단계 계획대로") ----------
# 공시 목록(list.json)은 종목마다 6시간, 문서(document.xml)는 접수번호마다 한 번만 받아 STATE_DIR/dart 에 남긴다.
# 일정 날짜는 문서 본문에서 '일시', '배당기준일', '지급 예정일' 뒤 첫 날짜를 뽑는다. 못 뽑으면 공시일로 두고 approx 를 붙인다.
DART = 'https://opendart.fss.or.kr/api'
DATE_RE = re.compile(r'(20\d\d)\s*[.\-년/]\s*(\d{1,2})\s*[.\-월/]\s*(\d{1,2})')

def dart_get(path, params, raw=False):
    url = DART + path + '?' + urllib.parse.urlencode(dict(params, crtfc_key=DART_KEY))
    body = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'jogan-relay'}), timeout=20).read()
    if raw: return body
    j = json.loads(body.decode('utf-8'))
    if j.get('status') not in ('000', '013'): raise Upstream(502, 'dart-' + str(j.get('status')), j.get('message', ''))   # 013 = 조회된 데이터 없음
    return j

def corp_map():
    """종목코드 → DART 고유번호. corpCode.xml(zip)을 하루 한 번 받는다."""
    import io, zipfile
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(dart_get('/corpCode.xml', {}, raw=True)))
    out = {}
    # 풀면 수십 MB 라 통째로 읽지 않고 흘려 읽는다(무료 VM 메모리)
    with z.open(z.namelist()[0]) as f:
        for _, el in ET.iterparse(f):
            if el.tag != 'list': continue
            sc = (el.findtext('stock_code') or '').strip()
            if sc: out[sc] = (el.findtext('corp_code') or '').strip()
            el.clear()
    if not out: raise ValueError('corpCode 빈 응답')
    return out

def _d(m): 
    try: return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError: return None

def date_after(text, label, span=120):
    """label 뒤 첫 날짜. 다음 번호 항목('7. ', '10. ') 앞에서 멈춘다 — 칸이 '-'(미정)이면 다음 항목의 날짜를 잡았다
    (2026-11-27 SK하이닉스 배당 공시: 지급 예정일자 '-' 뒤 '10. 이사회결의일 2026-10-28' 을 지급일로 읽음)"""
    m = re.search(label, text)
    if not m: return None
    seg = text[m.end():m.end() + span]
    d, nx = DATE_RE.search(seg), re.search(r'\s\d{1,2}\.\s', seg)
    if d and nx and nx.start() < d.start(): d = None   # 날짜보다 다음 항목이 먼저면 이 칸은 비었다('2026. 12. 2.' 안의 '12. ' 는 날짜 뒤라 상관없다)
    return _d(d) if d else None

def doc_text(rno):
    """공시 문서 본문(태그를 지운 글). 접수번호마다 한 번만 받는다."""
    import io, zipfile
    fn = os.path.join(STATE_DIR, 'dart', rno + '.txt')
    try:
        with open(fn, encoding='utf-8') as f: return f.read()
    except OSError: pass
    body = dart_get('/document.xml', {'rcept_no': rno}, raw=True)
    if body[:2] != b'PK': raise ValueError('document.xml zip 아님: %r' % body[:80])
    z = zipfile.ZipFile(io.BytesIO(body))
    raw = b''.join(z.read(n) for n in z.namelist())
    for enc in ('utf-8', 'cp949'):
        try: txt = raw.decode(enc); break
        except UnicodeDecodeError: txt = raw.decode('utf-8', 'replace')
    txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', txt))
    try:
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, 'w', encoding='utf-8') as f: f.write(txt)
    except OSError as e: log.warning('DART 문서 저장 실패 %s', e)
    return txt

KINDS = (('IR', re.compile(r'기업설명회\(IR\)개최')), ('EARN', re.compile(r'영업\(잠정\)실적')),
         ('DIV', re.compile(r'현금ㆍ현물배당결정|현금배당결정')))

def events_one(code):
    cm = cached('dart-corp', 24 * 3600, corp_map)
    cc = cm.get(code)
    if not cc: return []
    today = datetime.now(KST).date()
    j = dart_get('/list.json', {'corp_code': cc, 'bgn_de': (today - timedelta(days=90)).strftime('%Y%m%d'),
                                'end_de': today.strftime('%Y%m%d'), 'pblntf_ty': 'I', 'page_count': 100})   # I = 거래소공시(IR, 잠정실적, 배당결정이 여기)
    out, seen = [], set()
    for r in j.get('list') or []:   # 최신순 — 정정 공시가 먼저 오니 같은 종류, 같은 날짜는 처음 것만 둔다
        nm, rno = r.get('report_nm', ''), r.get('rcept_no', '')
        if not re.fullmatch(r'\d{14}', rno or '') or not re.fullmatch(r'\d{8}', r.get('rcept_dt') or ''): continue   # 파일 이름, 링크에 쓰니 형식을 확인한다
        kind = next((k for k, rx in KINDS if rx.search(nm)), None)
        if not kind: continue
        rd = '%s-%s-%s' % (r['rcept_dt'][:4], r['rcept_dt'][4:6], r['rcept_dt'][6:8])
        base = {'code': code, 'name': r.get('stock_name') or r.get('corp_name'), 'rcept_no': rno, 'report': nm.strip()}
        evs = []
        if kind == 'EARN':
            evs.append(dict(base, kind='EARN', date=rd, title='잠정실적 정정 공시' if '정정' in nm else '잠정실적 공시'))
        else:
            try: t = doc_text(rno)
            except Exception as e:
                log.warning('DART 문서 %s 실패: %s', rno, e); t = ''
            if kind == 'IR':
                # '일시적', '일 시작' 같은 낱말에 걸리지 않게 뒤에 한글이 오지 않는 '일시'만. 접수일 앞이거나 1년 넘게 뒤면 버린다
                d = date_after(t, r'개최\s*일\s*시(?![가-힣])') or date_after(t, r'일\s*시(?![가-힣])')
                if d and not (rd <= d <= (date.fromisoformat(rd) + timedelta(days=365)).isoformat()): d = None
                evs.append(dict(base, kind='IR', date=d or rd, approx=not d, title='IR 개최' if d else 'IR 개최 공시'))
            else:
                amt = re.search(r'1주당\s*배당금\s*\(원\)\s*보통주식\s*([\d,]+)', t)
                a = (' 주당 %s원' % amt.group(1)) if amt else ''
                d1, d2 = date_after(t, r'배당기준일'), date_after(t, r'지급\s*예정\s*일')
                if d1 and d2 and d2 < d1: d2 = None   # 지급일이 기준일보다 앞이면 잘못 읽은 것
                if d1: evs.append(dict(base, kind='DIV', date=d1, title='배당 기준일' + a))
                if d2: evs.append(dict(base, kind='DIV', date=d2, title='배당 지급일' + a))
                if not (d1 or d2): evs.append(dict(base, kind='DIV', date=rd, approx=True, title='배당 결정 공시' + a))
        for e in evs:
            k = (e['kind'], e['title'][:5], e['date'])
            if k not in seen: seen.add(k); out.append(e)
    return out

def events(syms):
    out = {'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': [], 'errors': []}
    # 국내 상장 목록에 있는 종목만 DART 를 부른다(공개 경로라 아무 코드나 돌려 부르면 하루 2만 회 한도를 쓴다)
    listed = {x[0] for x in cached('stocks', 6 * 3600, stock_list)['items']}
    syms = [x for x in syms if x in listed]
    def one(s):
        try: return cached(('ev', s), 6 * 3600, lambda: events_one(s), QSTORE), None
        except Exception as e: return None, '%s %s' % (s, e)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for evs, err in ex.map(one, [x for x in syms if is_kr(x)]):
            if err: out['errors'].append(err)
            out['items'].extend(evs or [])
    out['items'].sort(key=lambda e: (e['date'], e['code']))
    return out

def kospi_daily():
    res = toss('/api/v1/market-indicators/%s/candles' % INDEX, {'interval': '1d', 'count': 30}) or {}
    rows = {}
    for c in res.get('candles') or []:
        rows[c['timestamp'][:10]] = [c['timestamp'][:10]] + [float(c[k + 'Price']) for k in ('open', 'high', 'low', 'close')]
    return {'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': [rows[k] for k in sorted(rows)]}

# ---------- 야간선물: 한국투자증권 REST (2026-11-26) ----------
# 근월물 현재가 FHMIF10000000 에 시장 코드 CM 을 주면 KRX 야간선물이다(VM 실측 11/26: 18:02 727.50 +0.10%, 등락률은 직전 주간 종가 대비).
# 18:00~06:05 사이에만 10초마다 부르고, 1분봉(봉 끝 시각)으로 모아 STATE_DIR/night-<세션 시작일>.json 에 둔다(재시작해도 그 밤 기록 유지).
# 18:00 직후 첫 체결 전에는 지난밤 값이 그대로 오므로, 세션 시작 뒤 값이 한 번이라도 바뀌어야 live 로 본다(휴장일 밤은 waiting 으로 남는다).
# 세션 시작 뒤 첫 값이 이미 새 체결이면 다음 체결까지(보통 수 초) 기다렸다가 시작한다.
KIS = 'https://openapi.koreainvestment.com:9443'
KIS_MASTER = 'https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip'
NIGHT_POLL = 10

class KisToken:
    """접근토큰. relay/kis_probe.py 와 같은 파일(kis_token.json)을 쓴다. 발급은 분당 1회라 실패 뒤 65초는 다시 부르지 않는다"""
    def __init__(self):
        self.lock, self.value, self.exp, self.wait_until = threading.Lock(), None, 0.0, 0.0
        self.path = os.path.join(STATE_DIR, 'kis_token.json')
        try:
            d = json.load(open(self.path))
            if d.get('exp', 0) > time.time() + 600: self.value, self.exp = d['access_token'], d['exp']
        except Exception:
            pass
    def get(self, force=False):
        with self.lock:
            if not force and self.value and time.time() < self.exp - 3600: return self.value
            if time.time() < self.wait_until:
                if self.value and not force: return self.value
                raise Upstream(503, 'kis-token-backoff')
            self.wait_until = time.time() + 65
            old_ok = self.value and time.time() < self.exp - 60
            req = urllib.request.Request(KIS + '/oauth2/tokenP', method='POST', headers={'Content-Type': 'application/json; charset=utf-8'},
                                         data=json.dumps({'grant_type': 'client_credentials', 'appkey': KIS_AK, 'appsecret': KIS_SK}).encode())
            try:
                d = json.load(urllib.request.urlopen(req, timeout=10))
            except (urllib.error.URLError, OSError, ValueError) as e:
                if old_ok and not force: return self.value   # 미리 갱신하다 실패하면 아직 유효한 옛 토큰을 쓴다
                raise Upstream(getattr(e, 'code', 502), 'kis-token')
            self.value, self.exp = d['access_token'], time.time() + int(d.get('expires_in', 86400))
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w') as f: json.dump({'access_token': self.value, 'exp': self.exp}, f)
            except Exception as e:
                log.warning('한투 토큰 저장 실패: %s', e)
            log.info('한투 토큰 발급 (만료 %s)', datetime.fromtimestamp(self.exp, KST).strftime('%m-%d %H:%M'))
            return self.value

KTOKEN = KisToken()

def kis_front():
    """지수선물옵션 마스터의 '구분 1(코스피200 선물), 순서 1(근월물)' 줄 → (단축코드, 이름). 예 ('A01612', 'F 202612')"""
    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(KIS_MASTER, timeout=20).read()))
    for n in z.namelist():
        for line in z.read(n).decode('cp949', 'replace').splitlines():
            f = line.split('|')
            if len(f) > 8 and f[0] == '1' and f[8].strip() == 'KOSPI200' and f[6].strip() == '1':
                return f[1].strip(), f[3].strip()
    raise Upstream(502, 'kis-master')

def kis_price(code, mkt='CM', retry=True):
    """근월물 현재가와 등락률. mkt CM = KRX 야간, F = 주간(야간 중에는 그날 주간 종가)"""
    q = urllib.parse.urlencode({'FID_COND_MRKT_DIV_CODE': mkt, 'FID_INPUT_ISCD': code})
    req = urllib.request.Request(KIS + '/uapi/domestic-futureoption/v1/quotations/inquire-price?' + q, headers={
        'authorization': 'Bearer ' + KTOKEN.get(), 'appkey': KIS_AK, 'appsecret': KIS_SK, 'tr_id': 'FHMIF10000000', 'custtype': 'P'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=10))
    except urllib.error.HTTPError as e:
        try: r = json.load(e)
        except Exception: raise Upstream(e.code, 'kis')
    if r.get('rt_cd') != '0':
        m = (r.get('msg1') or '') + ' ' + (r.get('msg_cd') or '')
        if retry and (r.get('msg_cd') in ('EGW00121', 'EGW00123') or '토큰' in m or 'token' in m.lower()):   # 무효, 만료 토큰(코드는 2차 자료 기준)
            KTOKEN.get(force=True); return kis_price(code, mkt, retry=False)
        raise Upstream(502, 'kis', (r.get('msg_cd') or '') + ' ' + (r.get('msg1') or '').strip())
    o = r.get('output1') or {}
    return float(o['futs_prpr']), float(o['futs_prdy_ctrt'])

def night_session(now):
    """지금이 속한(또는 막 끝난) 야간 세션 시작일. 18:00 이후는 오늘, 06:05 전은 어제. 그 밖은 None(낮)"""
    t = now.hour * 60 + now.minute
    if t >= 18 * 60: return now.date()
    if t < 6 * 60 + 5: return now.date() - timedelta(days=1)
    return None

class Night:
    def __init__(self):
        self.lock, self.cur, self.err = threading.Lock(), None, None
        self.code = self.name = None; self.code_at = 0.0
        latest = sorted(f for f in os.listdir(STATE_DIR) if f.startswith('night-') and f.endswith('.json')) if os.path.isdir(STATE_DIR) else []
        if latest:
            try: self.cur = json.load(open(os.path.join(STATE_DIR, latest[-1])))
            except Exception: pass
    def save(self):
        p = os.path.join(STATE_DIR, 'night-%s.json' % self.cur['session'])
        tmp = p + '.tmp'
        with open(tmp, 'w') as f: json.dump(self.cur, f, separators=(',', ':'))
        os.replace(tmp, p)
        old = sorted(f for f in os.listdir(STATE_DIR) if f.startswith('night-') and f.endswith('.json'))
        for f in old[:-10]:   # 열흘 치만 남긴다
            try: os.remove(os.path.join(STATE_DIR, f))
            except OSError: pass
    def tick(self):
        now = datetime.now(KST); sess = night_session(now)
        if sess is None or sess.weekday() >= 5: return   # 낮, 토, 일 저녁은 세션이 없다(금요일 밤은 토 06:00 까지)
        if not self.code or time.time() - self.code_at > 6 * 3600:   # 만기(둘째 목요일) 뒤 근월물이 바뀐다
            try: self.code, self.name = kis_front()
            except Exception as e:
                if not self.code: raise
                log.warning('마스터 실패, 옛 코드 %s 유지: %s', self.code, e)
            self.code_at = time.time()   # 실패해도 6시간 뒤에 다시(10초마다 마스터를 받지 않게)
        # 네트워크 호출은 잠금 밖에서 한다(view 와 HTTP 스레드를 막지 않게)
        px, pct = kis_price(self.code)
        need_base = not self.cur or self.cur.get('session') != sess.isoformat() or self.cur.get('base') is None
        base = None
        if need_base and now.hour >= 18:
            try: base = kis_price(self.code, 'F')[0]   # 그날 주간 종가 = 야간 등락률 기준
            except Exception as e: log.warning('주간 종가 실패: %s', e)
        with self.lock:
            c = self.cur
            if not c or c.get('session') != sess.isoformat():
                c = self.cur = {'session': sess.isoformat(), 'code': self.code, 'name': self.name, 'state': 'waiting',
                                'first': px, 'base': None, 'last': px, 'pct': pct, 'asof': None, 'bars': [], 'ohlc': []}
            if c['base'] is None and base is not None: c['base'] = base
            if c['state'] == 'waiting' and px == c['first']:
                return   # 첫 체결 전(지난밤 값). 값이 바뀌어야 시작한다 — 휴장일 밤은 waiting 으로 남는다
            c['state'] = 'live' if now.hour >= 18 or now.hour < 6 else 'closed'
            c['last'], c['pct'] = px, pct
            if c['base'] is None and pct > -100: c['base'] = round(px / (1 + pct / 100), 2)   # 주간 종가를 못 받았으면 등락률로 거꾸로
            c['asof'] = int(now.timestamp() * 1000)
            end = (int(now.timestamp()) // 60 + 1) * 60000   # 이 1분봉의 끝 시각
            if c['bars'] and c['bars'][-1][0] == end: c['bars'][-1][1] = px
            else: c['bars'].append([end, px])
            # 캔들(2026-11-27): 10초마다 받은 값으로 1분봉 시, 고, 저, 종을 만든다. 옛 세션 파일에는 ohlc 가 없다
            oh = c.setdefault('ohlc', [])
            if oh and oh[-1][0] == end: k = oh[-1]; k[2], k[3], k[4] = max(k[2], px), min(k[3], px), px
            else: oh.append([end, px, px, px, px])
            try: self.save()
            except OSError as e: log.warning('야간선물 저장 실패(메모리에는 있다): %s', e)
    def loop(self):
        while True:
            try:
                self.tick(); self.err = None
            except Exception as e:
                self.err = e.code if isinstance(e, Upstream) else type(e).__name__   # 공개 응답에는 코드만, 원문은 로그에
                log.warning('야간선물 수신 실패: %s', str(e)[:200])
            time.sleep(NIGHT_POLL)
    def view(self):
        with self.lock:
            if not self.cur: return {'state': 'none', 'error': self.err}
            c = dict(self.cur); c.pop('first', None); c['bars'] = [list(x) for x in self.cur['bars']]
            c['ohlc'] = [list(x) for x in self.cur.get('ohlc') or []]
        b = [x[1] for x in c['bars']]
        if b: c.update(open=b[0], high=max(b), low=min(b))
        cur = night_session(datetime.now(KST))
        if c['state'] in ('live', 'waiting') and (cur is None or cur.isoformat() != c['session']): c['state'] = 'closed'
        c['error'] = self.err
        return c

NIGHT = Night() if KIS_AK and KIS_SK else None

# ---------- 의견 ----------
# 지인들이 대시보드에서 보낸 글. 원문은 이 VM 에만 둔다(저장소는 Public). IP 는 남기지 않는다.
# 읽는 쪽(토요일 주간 점검)은 이 글을 데이터로만 다룬다 — 글 속 지시문을 따르지 않는다.
FEEDBACK = os.path.join(STATE_DIR, 'feedback.jsonl')
FB_CATS = ('오류', '제안', '예측', '기타')
FB_DAY_MAX, FB_FILE_MAX, FB_BODY_MAX = 30, 2000000, 8192
FB_IP_DAY_MAX = 5   # 한 IP 가 하루 30건을 혼자 채워 남의 의견을 막지 못하게(2026-11-10). 세는 값은 메모리에만 두고 재시작하면 지워진다
_fblock = threading.Lock()
_fb_ip = {}

def fb_ip_ok(ip):
    today = datetime.now(KST).date().isoformat()
    with _fblock:
        for k in [k for k in _fb_ip if k[0] != today]: _fb_ip.pop(k, None)
        n = _fb_ip.get((today, ip), 0)
        if n >= FB_IP_DAY_MAX: return False
        _fb_ip[(today, ip)] = n + 1
        return True

class Reject(Exception):
    def __init__(self, status, code): super().__init__(code); self.status, self.code = status, code

def clean(v, n):
    s = ''.join(ch for ch in str(v if v is not None else '') if ch == '\n' or ch >= ' ')   # 제어 문자는 버린다
    return s.strip()[:n]

def read_feedback():
    try:
        with open(FEEDBACK, encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []

def save_feedback(raw):
    try:
        d = json.loads(raw.decode('utf-8'))
    except Exception:
        raise Reject(400, 'bad-json')
    if not isinstance(d, dict): raise Reject(400, 'bad-json')
    text = clean(d.get('text'), 1000)
    if not text: raise Reject(400, 'empty')
    ctx = d.get('ctx') if isinstance(d.get('ctx'), dict) else {}
    now = datetime.now(KST)
    rec = {'id': now.strftime('%m%d-%H%M') + '-' + secrets.token_hex(2), 'ts': now.isoformat(timespec='seconds'),
           'cat': d.get('cat') if d.get('cat') in FB_CATS else '기타', 'nick': clean(d.get('nick'), 20), 'text': text,
           'ctx': {k: clean(ctx[k], 40) for k in ('issue', 'tab', 'mode', 'w', 'page') if ctx.get(k) not in (None, '')}}
    with _fblock:
        try: size = os.path.getsize(FEEDBACK)
        except OSError: size = 0
        if size > FB_FILE_MAX: raise Reject(507, 'store-full')
        today = now.date().isoformat()
        if sum(1 for r in read_feedback() if r.get('ts', '')[:10] == today) >= FB_DAY_MAX: raise Reject(429, 'daily-limit')
        fd = os.open(FEEDBACK, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    log.info('의견 저장 %s (%s, %d자)', rec['id'], rec['cat'], len(text))   # 본문은 로그에 남기지 않는다
    return rec

# ---------- HTTP ----------
_hits, _hlock = {}, threading.Lock()
def rate_ok(ip, limit=120):
    now = int(time.time() // 60)
    with _hlock:
        k = (ip, now); _hits[k] = _hits.get(k, 0) + 1
        if len(_hits) > 5000:
            for kk in [kk for kk in _hits if kk[1] < now]: _hits.pop(kk, None)
        return _hits[k] <= limit

def key_ok(given, keys):
    return bool(given) and any(hmac.compare_digest(given, k) for k in keys if k)

class Handler(BaseHTTPRequestHandler):
    server_version = 'jogan-relay/1'
    def log_message(self, fmt, *a):   # 키가 든 쿼리스트링은 남기지 않는다
        log.info('%s %s %s', self.headers.get('X-Forwarded-For', self.client_address[0]), self.command, self.path.split('?')[0])

    def send_json(self, status, obj, ttl=0):
        body = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if not ttl else 'max-age=%d' % ttl)
        o = self.headers.get('Origin')
        if o and o in ORIGINS:
            self.send_header('Access-Control-Allow-Origin', o); self.send_header('Vary', 'Origin')
        self.end_headers(); self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        o = self.headers.get('Origin')
        if o and o in ORIGINS:
            self.send_header('Access-Control-Allow-Origin', o)
            self.send_header('Access-Control-Allow-Headers', 'X-Relay-Key, Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST')
            self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        if u.path == '/healthz':
            return self.send_json(200, {'ok': True, 'token': bool(TOKEN.value), 'token_exp': TOKEN.exp and datetime.fromtimestamp(TOKEN.exp, KST).isoformat(timespec='minutes')})
        if not rate_ok(ip):
            return self.send_json(429, {'error': 'rate-limited'})
        k = q.get('k') or self.headers.get('X-Relay-Key', '')
        is_routine = key_ok(k, [ROUTINE_KEY])
        if not (is_routine or (PUBLIC_VIEW and u.path in PUBLIC_PATHS)):
            return self.send_json(401, {'error': 'bad-key'})
        try:
            d = date.fromisoformat(q['date']) if q.get('date') else datetime.now(KST).date()
        except ValueError:
            return self.send_json(400, {'error': 'bad-date'})
        today = datetime.now(KST).date()
        try:
            if u.path == '/v1/live':
                return self.send_json(200, cached('live', 5, live))
            if u.path == '/v1/night':
                if not NIGHT: return self.send_json(503, {'error': 'kis-not-configured'})
                return self.send_json(200, NIGHT.view())
            if u.path == '/v1/intraday':
                if d > today or (today - d).days > 30: return self.send_json(400, {'error': 'date-out-of-range'})
                return self.send_json(200, cached(('intraday', d), 20 if d == today else 3600, lambda: intraday(d)))
            if u.path == '/v1/stocks':
                if q.get('mk') == 'us': return self.send_json(200, cached('stocks-us', 6 * 3600, lambda: stock_list(US_MK)), ttl=3600)
                return self.send_json(200, cached('stocks', 6 * 3600, stock_list), ttl=3600)
            if u.path == '/v1/events':
                if not DART_KEY: return self.send_json(503, {'error': 'dart-not-configured'})
                syms = list(dict.fromkeys(x.strip().upper() for x in q.get('symbols', '').split(',') if x.strip()))
                if not syms or len(syms) > 30 or not all(SYM_RE.match(x) for x in syms):
                    return self.send_json(400, {'error': 'bad-symbols', 'max': 30})
                return self.send_json(200, cached(('events', tuple(sorted(syms))), 300, lambda: events(syms), QSTORE))
            if u.path == '/v1/quotes':
                syms = list(dict.fromkeys(x.strip().upper() for x in q.get('symbols', '').split(',') if x.strip()))
                if not syms or len(syms) > QUOTE_MAX or not all(SYM_RE.match(x) for x in syms):
                    return self.send_json(400, {'error': 'bad-symbols', 'max': QUOTE_MAX})
                return self.send_json(200, cached(('quotes', tuple(sorted(syms))), 5, lambda: quotes(syms), QSTORE))
            if u.path == '/v1/flow':
                return self.send_json(200, cached('flow', 60, flow_now))
            if u.path == '/v1/kospi-daily':
                return self.send_json(200, cached('kospi-daily', 60, kospi_daily))
            if u.path == '/v1/daily':
                if not is_routine: return self.send_json(403, {'error': 'routine-key-required'})
                try: uu = date.fromisoformat(q['us_until']) if q.get('us_until') else None
                except ValueError: return self.send_json(400, {'error': 'bad-date'})
                return self.send_json(200, cached(('daily', d, uu), 300, lambda: daily(d, uu)))
            if u.path == '/v1/calendar':
                if not is_routine: return self.send_json(403, {'error': 'routine-key-required'})
                return self.send_json(200, cached(('calendar', d), 3600, lambda: calendar(d)))
            if u.path == '/v1/feedback':
                if not is_routine: return self.send_json(403, {'error': 'routine-key-required'})
                since = q.get('since') or (today - timedelta(days=7)).isoformat()
                with _fblock: items = [r for r in read_feedback() if r.get('ts', '')[:10] >= since]
                return self.send_json(200, {'since': since, 'count': len(items), 'items': items})
        except Upstream as e:
            log.warning('업스트림 %s', e)
            return self.send_json(502, {'error': 'upstream', 'status': e.status, 'code': e.code})
        except Exception as e:
            log.exception('처리 실패')
            return self.send_json(500, {'error': 'internal'})
        return self.send_json(404, {'error': 'not-found'})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        if u.path != '/v1/feedback':
            return self.send_json(404, {'error': 'not-found'})
        if not rate_ok(('fb', ip), 10):
            return self.send_json(429, {'error': 'rate-limited'})
        k = q.get('k') or self.headers.get('X-Relay-Key', '')
        if not key_ok(k, [ROUTINE_KEY]):   # 키 없는 의견은 대시보드 주소에서 온 것만 받는다
            if not PUBLIC_VIEW: return self.send_json(401, {'error': 'bad-key'})
            if self.headers.get('Origin') not in ORIGINS: return self.send_json(403, {'error': 'bad-origin'})
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n <= 0 or n > FB_BODY_MAX:
            return self.send_json(413 if n > FB_BODY_MAX else 400, {'error': 'bad-length'})
        try:
            raw = self.rfile.read(n)
            if not fb_ip_ok(ip): raise Reject(429, 'daily-limit')
            rec = save_feedback(raw)
        except Reject as e:
            return self.send_json(e.status, {'error': e.code})
        except Exception:
            log.exception('의견 저장 실패')
            return self.send_json(500, {'error': 'internal'})
        return self.send_json(200, {'ok': True, 'id': rec['id']})

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not (CID and CSECRET): sys.exit('TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 없음 (/etc/jogan-relay.env)')
    if not ROUTINE_KEY: sys.exit('ROUTINE_KEY 없음 (/etc/jogan-relay.env)')
    if NIGHT: threading.Thread(target=NIGHT.loop, name='night', daemon=True).start()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    log.info('jogan-relay 127.0.0.1:%d · 업스트림 %s · Origin %s · 화면용(시세·의견) %s', PORT, API, ORIGINS, '열림' if PUBLIC_VIEW else '닫힘')
    log.info('야간선물(한투) %s', '켜짐' if NIGHT else '꺼짐 — KIS_APPKEY 없음')
    srv.serve_forever()

if __name__ == '__main__':
    main()
