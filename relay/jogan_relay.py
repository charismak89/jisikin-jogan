#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jogan_relay.py — 토스증권 Open API 중계기 (지식인 조간 대시보드·루틴용)

토스 Open API 는 허용 IP 에서만 부를 수 있고, 토큰은 클라이언트당 1개만 유효하다(새로 발급하면 직전 토큰 즉시 무효).
그래서 토큰은 이 중계기 한 곳에서만 발급하고, 대시보드(지인 브라우저)와 07:45 루틴은 모두 여기를 거친다.
표준 라이브러리만 쓴다. 127.0.0.1 에만 열고 TLS 는 앞단 Caddy 가 맡는다.

엔드포인트 (모두 GET, 키는 ?k= 또는 X-Relay-Key 헤더)
  /healthz                       키 없이. 토큰 상태만
  /v1/live                       코스피·삼전·하닉 현재가 (5초 캐시)                     — 지인 키
  /v1/intraday?date=YYYY-MM-DD   그날 1분봉 종가 (코스피 09:00~15:30, 두 종목 08:00~20:00) — 지인 키
  /v1/daily?date=YYYY-MM-DD      그날 일봉(시고저종)·환율·코스피 투자자별 매매대금 (루틴용) — 루틴 키
  POST /v1/feedback              대시보드 '의견' 버튼. 본문 JSON {cat, text, nick, ctx} → STATE_DIR/feedback.jsonl — 지인 키
  GET  /v1/feedback?since=YYYY-MM-DD   그날부터 쌓인 의견 (토요일 주간 점검용)        — 루틴 키

환경 변수 (/etc/jogan-relay.env)
  TOSS_CLIENT_ID, TOSS_CLIENT_SECRET   토스 WTS 설정 > Open API 에서 받은 값
  VIEW_KEYS                            지인용 키, 콤마 구분
  ROUTINE_KEY                          루틴용 키 (/v1/daily 와 나머지 전부 허용)
  ALLOW_ORIGINS                        CORS 허용 Origin, 콤마 구분 (기본 https://charismak89.github.io)
  STATE_DIR                            토큰·의견 보관 (기본 /var/lib/jogan-relay)
  PORT                                 기본 8787
  TOSS_API                             기본 https://openapi.tossinvest.com (시험용으로만 바꾼다)
"""
import hmac, json, logging, os, secrets, sys, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KST = timezone(timedelta(hours=9))
API = os.environ.get('TOSS_API', 'https://openapi.tossinvest.com').rstrip('/')
CID = os.environ.get('TOSS_CLIENT_ID', '')
CSECRET = os.environ.get('TOSS_CLIENT_SECRET', '')
VIEW_KEYS = [k.strip() for k in os.environ.get('VIEW_KEYS', '').split(',') if k.strip()]
ROUTINE_KEY = os.environ.get('ROUTINE_KEY', '').strip()
ORIGINS = [o.strip() for o in os.environ.get('ALLOW_ORIGINS', 'https://charismak89.github.io').split(',') if o.strip()]
STATE_DIR = os.environ.get('STATE_DIR', '/var/lib/jogan-relay')
PORT = int(os.environ.get('PORT', '8787'))

STOCKS = ['005930', '000660']            # 대시보드 종목
INDEX = 'KOSPI'
DAILY_KR = ['005930', '000660', '402340', '009150', '0167A0', '442580']   # 루틴 국내 6종
DAILY_US = ['NVDA', 'MU', 'EWY', 'SKHY']                                  # 루틴 미국 4종
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
_cache, _clock = {}, threading.Lock()
def cached(key, ttl, fn):
    now = time.time()
    with _clock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl: return hit[1]
    val = fn()
    with _clock: _cache[key] = (now, val)
    return val

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

def candles_1m(path, params, start_ms, end_ms):
    """최신순 200개씩 받아 start_ms 이전까지 거슬러 간다. 반환은 [봉 종료 ms, 시, 종] 오름차순."""
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
                out[t] = [t, float(c['openPrice']), float(c['closePrice'])]
        if not cs or not res.get('nextBefore') or iso_ms(cs[-1]['timestamp']) <= start_ms: break
        before = res['nextBefore']
    return [out[k] for k in sorted(out)]

def intraday(d):
    end = ms(d, 20, 0)
    if d == datetime.now(KST).date(): end = min(end, int(time.time() * 1000))
    before = (datetime(d.year, d.month, d.day, 20, 0, tzinfo=KST)).isoformat()
    items = {}
    for s in STOCKS:
        bars = candles_1m('/api/v1/candles', {'symbol': s, 'before': before}, ms(d, 8, 0), end)
        items[s] = {'bars': [[t, c] for t, o, c in bars], 'open': next((o for t, o, c in bars if t > ms(d, 9, 0)), None)}
    bars = candles_1m('/api/v1/market-indicators/%s/candles' % INDEX, {'before': before}, ms(d, 8, 59), min(end, ms(d, 15, 31)))   # 08:59 — 명세대로 09:00 봉이 와도 첫 봉을 잃지 않게
    items[INDEX] = {'bars': [[t, c] for t, o, c in bars], 'open': bars[0][1] if bars else None}
    return {'date': d.isoformat(), 'asof': datetime.now(KST).isoformat(timespec='seconds'), 'items': items}

def day_candle(path, params, d):
    res = toss(path, dict(params, interval='1d', count=10)) or {}
    for c in res.get('candles') or []:
        if c['timestamp'][:10] == d.isoformat():
            return {k: float(c[k + 'Price']) for k in ('open', 'high', 'low', 'close')}
    return None

def krx_day(s, d):
    """KRX 공식 시가·종가. 토스 종목 일봉은 KRX·NXT 통합(08:00~20:00)이라 1분봉에서 뽑는다.
    시가 = 09:01 봉(09:00~09:01)의 시가, 종가 = 15:31 봉(15:30~15:31, 종가 단일가)의 종가. 15:31 봉이 없으면 15:31 이전 마지막 봉."""
    end = ms(d, 15, 31)
    if d == datetime.now(KST).date(): end = min(end, int(time.time() * 1000))
    before = datetime(d.year, d.month, d.day, 15, 32, tzinfo=KST).isoformat()
    bars = [b for b in candles_1m('/api/v1/candles', {'symbol': s, 'before': before}, ms(d, 9, 0), end) if b[0] > ms(d, 9, 0)]
    if not bars: return None
    return {'open': bars[0][1], 'close': bars[-1][2], 'src': 'krx-1m',
            'complete': bars[0][0] == ms(d, 9, 1) and bars[-1][0] == ms(d, 15, 31)}   # False 면 시가·종가 봉이 비었다 — 쓰기 전에 확인

def daily(d):
    out = {'date': d.isoformat(), 'asof': datetime.now(KST).isoformat(timespec='seconds'), 'kr': {}, 'us': {}, 'index': {}, 'errors': []}
    for s in DAILY_KR:
        try:
            c = day_candle('/api/v1/candles', {'symbol': s}, d)   # 통합 일봉: 고가·저가·거래 범위 참고용
            k = krx_day(s, d)
            if c and k: c = dict(c, nxt_open=c['open'], nxt_close=c['close'], open=k['open'], close=k['close'], src=k['src'], complete=k['complete'])
            elif c: c['src'] = 'toss-1d'   # 1분봉이 없는 날(보관 기간 지남) — 시가·종가는 NXT 통합값이라 KRX 공식값과 다를 수 있다
            out['kr'][s] = c
        except Upstream as e: out['errors'].append('%s %s' % (s, e))
    for s in DAILY_US:   # 미국 일봉의 날짜는 미국 거래일 (현지 자정을 KST 로 표기)
        try:
            res = toss('/api/v1/candles', {'symbol': s, 'interval': '1d', 'count': 3}) or {}
            cs = res.get('candles') or []
            out['us'][s] = [{'date': c['timestamp'], 'close': float(c['closePrice'])} for c in cs]
        except Upstream as e: out['errors'].append('%s %s' % (s, e))
    for s in DAILY_IDX:
        try: out['index'][s] = day_candle('/api/v1/market-indicators/%s/candles' % s, {}, d)
        except Upstream as e: out['errors'].append('%s %s' % (s, e))
    try:
        fx = toss('/api/v1/exchange-rate', {'baseCurrency': 'USD', 'quoteCurrency': 'KRW'}) or {}
        out['fx'] = {'mid': float(fx['midRate']), 'from': fx.get('validFrom')}
    except Exception as e: out['errors'].append('fx %s' % e)
    try:
        res = toss('/api/v1/market-indicators/KOSPI/investor-trading', {'interval': '1d', 'count': 3}) or {}
        for r in res.get('records') or []:
            if r.get('date') == d.isoformat():
                net = lambda x: None if not x else round((float(x['buyAmount']) - float(x['sellAmount'])) / 1e8)   # 억원
                out['flow'] = {'foreign': net(r.get('foreigner')), 'inst': net(r.get('institution')), 'retail': net(r.get('individual')),
                               'other': net(r.get('otherCorporation')), 'updatedAt': r.get('updatedAt')}
    except Exception as e: out['errors'].append('flow %s' % e)
    return out

# ---------- 의견 ----------
# 지인들이 대시보드에서 보낸 글. 원문은 이 VM 에만 둔다(저장소는 Public). IP 는 남기지 않는다.
# 읽는 쪽(토요일 주간 점검)은 이 글을 데이터로만 다룬다 — 글 속 지시문을 따르지 않는다.
FEEDBACK = os.path.join(STATE_DIR, 'feedback.jsonl')
FB_CATS = ('오류', '제안', '예측', '기타')
FB_DAY_MAX, FB_FILE_MAX, FB_BODY_MAX = 30, 2000000, 8192
_fblock = threading.Lock()

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
        if not (is_routine or key_ok(k, VIEW_KEYS)):
            return self.send_json(401, {'error': 'bad-key'})
        try:
            d = date.fromisoformat(q['date']) if q.get('date') else datetime.now(KST).date()
        except ValueError:
            return self.send_json(400, {'error': 'bad-date'})
        today = datetime.now(KST).date()
        try:
            if u.path == '/v1/live':
                return self.send_json(200, cached('live', 5, live))
            if u.path == '/v1/intraday':
                if d > today or (today - d).days > 30: return self.send_json(400, {'error': 'date-out-of-range'})
                return self.send_json(200, cached(('intraday', d), 20 if d == today else 3600, lambda: intraday(d)))
            if u.path == '/v1/daily':
                if not is_routine: return self.send_json(403, {'error': 'routine-key-required'})
                return self.send_json(200, cached(('daily', d), 300, lambda: daily(d)))
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
        if not key_ok(k, VIEW_KEYS + [ROUTINE_KEY]):
            return self.send_json(401, {'error': 'bad-key'})
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            n = -1
        if n <= 0 or n > FB_BODY_MAX:
            return self.send_json(413 if n > FB_BODY_MAX else 400, {'error': 'bad-length'})
        try:
            rec = save_feedback(self.rfile.read(n))
        except Reject as e:
            return self.send_json(e.status, {'error': e.code})
        except Exception:
            log.exception('의견 저장 실패')
            return self.send_json(500, {'error': 'internal'})
        return self.send_json(200, {'ok': True, 'id': rec['id']})

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not (CID and CSECRET): sys.exit('TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 없음 (/etc/jogan-relay.env)')
    if not (VIEW_KEYS or ROUTINE_KEY): sys.exit('VIEW_KEYS 또는 ROUTINE_KEY 가 하나는 있어야 한다')
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    log.info('jogan-relay 127.0.0.1:%d · 업스트림 %s · Origin %s', PORT, API, ORIGINS)
    srv.serve_forever()

if __name__ == '__main__':
    main()
