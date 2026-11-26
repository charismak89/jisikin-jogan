#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kis_probe.py — 한국투자증권(KIS) Open API 로 코스피200 야간선물을 받을 수 있는지 VM 에서 한 번 시험한다(2026-11-26).

  sudo python3 relay/kis_probe.py            토큰, 승인키, 근월물 코드 후보, REST 현재가, 야간 체결(WebSocket) 25초
  sudo python3 relay/kis_probe.py --ws 60     WebSocket 을 60초 듣는다

키(KIS_APPKEY, KIS_APPSECRET)는 /etc/jogan-relay.env 에서 읽고 화면에 찍지 않는다. sudo 는 그 파일을 읽으려고 쓴다.
근월물 코드는 지수선물옵션 마스터에서 읽는다(A01612 = 2026년 12월물). 공식 문서로 확인하지 못한 것(H0MFCNT0 의 tr_key 형식, 야간 REST 시장 코드)은 후보를 모두 시도해 결과만 보여 준다.
접속 주소와 TR 은 2차 자료(알고랩 블로그, 2026)를 따랐다: REST https://openapi.koreainvestment.com:9443,
WebSocket ws://ops.koreainvestment.com:21000, 야간선물 체결 H0MFCNT0.
토큰은 STATE_DIR/kis_token.json(600, jogan 소유)에 남겨 24시간 안에는 다시 쓴다(발급을 줄이려고). 중계기도 나중에 같은 파일을 쓴다.
표준 라이브러리만 쓴다. 저장소 파일을 바꾸지 않는다.
"""
import base64, io, json, os, pwd, socket, struct, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone

ENVF = '/etc/jogan-relay.env'
REST = 'https://openapi.koreainvestment.com:9443'
WS_HOST, WS_PORT = 'ops.koreainvestment.com', 21000
STATE_DIR = os.environ.get('STATE_DIR', '/var/lib/jogan-relay')
KST = timezone(timedelta(hours=9))
MASTER = 'https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip'   # 2026-11-26 받아 형식 확인

def env():
    d = {}
    try:
        for line in open(ENVF, encoding='utf-8'):
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.rstrip('\n').split('=', 1); d[k.strip()] = v.strip().strip('"\'')
    except PermissionError:
        sys.exit('%s 를 못 읽음 — sudo 로 실행' % ENVF)
    return d

def post(path, body, hdr=None):
    req = urllib.request.Request(REST + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8', **(hdr or {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {'msg1': '접속 실패: %s' % str(e)[:80]}

def get(path, params, hdr):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request('%s%s?%s' % (REST, path, q), headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {'msg1': '접속 실패: %s' % str(e)[:80]}

def safe(r):
    """실패 응답에서 원인 필드만 고른다(응답 전체를 찍으면 값이 샐 수 있다)"""
    return {k: r.get(k) for k in ('rt_cd', 'msg_cd', 'msg1', 'error_code', 'error_description') if r.get(k) not in (None, '')}

def token(ak, sk):
    f = os.path.join(STATE_DIR, 'kis_token.json')
    try:
        t = json.load(open(f))
        if t.get('exp', 0) - time.time() > 3600: return t['access_token'], '저장된 토큰 재사용(%s 까지)' % datetime.fromtimestamp(t['exp'], KST).strftime('%m/%d %H:%M')
    except Exception: pass
    st, r = post('/oauth2/tokenP', {'grant_type': 'client_credentials', 'appkey': ak, 'appsecret': sk})
    if st != 200 or 'access_token' not in r:
        return None, '실패 HTTP %s %s' % (st, safe(r))
    exp = time.time() + int(r.get('expires_in', 86400))
    if not os.path.isdir(STATE_DIR):   # root 로 만들면 중계기(jogan)가 못 쓴다. install.sh 가 만든다
        return r['access_token'], '새로 발급(%s 가 없어 저장 안 함 — relay/install.sh 를 먼저)' % STATE_DIR
    try:
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 처음부터 600
        with os.fdopen(fd, 'w') as fp: json.dump({'access_token': r['access_token'], 'exp': exp}, fp)
        os.chmod(f, 0o600)
        try: u = pwd.getpwnam('jogan'); os.chown(f, u.pw_uid, u.pw_gid)
        except KeyError: pass
        note = '새로 발급, %s 에 저장' % f
    except OSError as e:
        note = '새로 발급(저장 못 함: %s)' % e
    return r['access_token'], note + ', 만료 %s' % datetime.fromtimestamp(exp, KST).strftime('%m/%d %H:%M')

def front_month(now):
    """코스피200 선물 근월물 계산(보조값. 마스터의 순서 1 을 먼저 쓴다): 3, 6, 9, 12월물, 만기 둘째 목요일.
    공휴일로 만기가 밀리는 경우는 모른다. 15:45 는 최종거래일 마감(15:20 무렵)보다 늦게 잡은 안전 쪽 값"""
    y, m = now.year, now.month
    while True:
        qm = ((m - 1) // 3 + 1) * 3
        d = datetime(y, qm, 1, tzinfo=KST); thu = 0
        while True:
            if d.weekday() == 3:
                thu += 1
                if thu == 2: break
            d += timedelta(days=1)
        if now < d.replace(hour=15, minute=45): return y, qm
        m = qm + 1
        if m > 12: y, m = y + 1, 1

def candidates(y, m):
    """확인 못 한 코드 형식들. KRX 단축코드는 '1'+'01'(코스피200)+연도 문자+월 문자(+'000') 로 알려져 있다"""
    mon = '123456789ABC'[m - 1]
    yl = chr(ord('W') + (y - 2025))      # 2025=W 로 가정(공식 예제 '101W9000' = 2025년 9월물로 추정)
    yd = str(y % 10)
    return ['101%s%s000' % (yl, mon), '101%s%s' % (yl, mon), '101%s%s000' % (yd, mon), 'A01%s%s000' % (yd, mon)]

def master_front():
    """지수선물옵션 마스터(fo_idx_code_mts.mst, 2026-11-26 실측): '구분|단축코드|표준코드|이름|…|순서|…|기초자산'.
    구분 1 = 코스피200 선물, 순서 1 = 근월물. 예: '1|A01612|KR4A016C0004|F 202612| |00000.00|1|2001|KOSPI200'"""
    try:
        with urllib.request.urlopen(MASTER, timeout=20) as r: z = zipfile.ZipFile(io.BytesIO(r.read()))
        for n in z.namelist():
            for l in z.read(n).decode('cp949', 'replace').splitlines():
                f = l.split('|')
                if len(f) > 8 and f[0] == '1' and f[8].strip() == 'KOSPI200' and f[6].strip() == '1':
                    return {'shrn': f[1].strip(), 'std': f[2].strip(), 'name': f[3].strip()}, None
        return None, '코스피200 근월물 줄 없음'
    except Exception as e:
        return None, str(e)[:120]

# ---- 최소 WebSocket 클라이언트(ws://, 텍스트 프레임) ----
def ws_open():
    s = socket.create_connection((WS_HOST, WS_PORT), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(('GET / HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
               'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (WS_HOST, WS_PORT, key)).encode())
    head = b''
    while b'\r\n\r\n' not in head:
        c = s.recv(1024)
        if not c: raise ConnectionError('핸드셰이크 중 끊김')
        head += c
    if b' 101 ' not in head.split(b'\r\n')[0]: raise ConnectionError(head.split(b'\r\n')[0].decode(errors='replace'))
    return s, head.split(b'\r\n\r\n', 1)[1]

def ws_send(s, text, op=1):
    p = text.encode() if isinstance(text, str) else text
    hdr = bytes([0x80 | op]); mk = os.urandom(4); n = len(p)
    hdr += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536 else bytes([0x80 | 127]) + struct.pack('>Q', n))
    s.sendall(hdr + mk + bytes(b ^ mk[i % 4] for i, b in enumerate(p)))

def ws_frames(s, buf):
    """프레임을 하나씩 낸다. 소켓 타임아웃이면 None 을 내고 계속한다(제너레이터 안에서 예외가 나면 제너레이터가 끝난다)"""
    def fill(k):
        nonlocal buf
        while len(buf) < k:
            try: c = s.recv(65536)
            except socket.timeout: return False
            if not c: raise ConnectionError('서버가 끊음')
            buf += c
        return True
    while True:
        if not fill(2): yield None; continue
        n = buf[1] & 0x7F; i = 2
        if n == 126:
            if not fill(4): yield None; continue
            n = struct.unpack('>H', buf[2:4])[0]; i = 4
        elif n == 127:
            if not fill(10): yield None; continue
            n = struct.unpack('>Q', buf[2:10])[0]; i = 10
        if not fill(i + n): yield None; continue
        op = buf[0] & 0x0F; data = buf[i:i + n]; buf = buf[i + n:]
        if op == 9: ws_send(s, data, 10); continue
        if op == 8: raise ConnectionError('서버가 닫음')
        if op not in (1, 2): continue   # pong, 연속 프레임은 버린다
        yield data.decode('utf-8', 'replace')

def main():
    E = env(); ak, sk = E.get('KIS_APPKEY', ''), E.get('KIS_APPSECRET', '')
    if not (ak and sk): sys.exit('KIS_APPKEY / KIS_APPSECRET 없음 (%s)' % ENVF)
    wait = int(sys.argv[sys.argv.index('--ws') + 1]) if '--ws' in sys.argv else 25
    now = datetime.now(KST); night = now.hour >= 18 or now.hour < 6
    print('시각 %s KST — %s' % (now.strftime('%m/%d %H:%M'), '야간 시간(18:00~06:00)' if night else '야간 시간이 아님: 체결은 안 들어오는 게 정상'))

    tok, note = token(ak, sk); print('1) 접근토큰: %s' % ('OK, ' + note if tok else note))
    st, r = post('/oauth2/Approval', {'grant_type': 'client_credentials', 'appkey': ak, 'secretkey': sk})
    apv = r.get('approval_key'); print('2) WebSocket 승인키: %s' % ('OK' if apv else '실패 HTTP %s %s' % (st, safe(r))))

    y, m = front_month(now); fm, err = master_front()
    cands = ([fm['shrn'], fm['std'][3:11]] if fm else []) + [c for c in candidates(y, m)[:1]]
    print('3) 근월물(계산) %d년 %d월물 / 마스터: %s' % (y, m, '%s %s %s' % (fm['name'], fm['shrn'], fm['std']) if fm else '못 받음(%s)' % err))
    print('   시도할 코드: %s' % ', '.join(cands))
    if tok:
        hdr = {'authorization': 'Bearer ' + tok, 'appkey': ak, 'appsecret': sk, 'tr_id': 'FHMIF10000000', 'custtype': 'P'}
        print('4) REST 선물 현재가(FHMIF10000000) — 시장 코드 x 코드 후보')
        for mk in ('F', 'CM'):
            for c in cands:
                st, r = get('/uapi/domestic-futureoption/v1/quotations/inquire-price', {'FID_COND_MRKT_DIV_CODE': mk, 'FID_INPUT_ISCD': c}, hdr)
                o = r.get('output1') or r.get('output') or {}
                px = {k: o.get(k) for k in ('futs_prpr', 'futs_prdy_ctrt', 'hts_kor_isnm', 'futs_prdy_clpr') if o.get(k) not in (None, '')} if isinstance(o, dict) else {}
                print('   %-3s %-9s HTTP %s rt_cd=%s %s %s' % (mk, c, st, r.get('rt_cd'), (r.get('msg1') or '').strip()[:40], px or ''))
                time.sleep(0.3)

    if not apv: return
    print('5) WebSocket 야간선물 체결(H0MFCNT0) %d초 듣기' % wait)
    try:
        s, rest = ws_open()
    except Exception as e:
        print('   접속 실패: %s' % e); return
    for c in cands:
        ws_send(s, json.dumps({'header': {'approval_key': apv, 'custtype': 'P', 'tr_type': '1', 'content-type': 'utf-8'},
                               'body': {'input': {'tr_id': 'H0MFCNT0', 'tr_key': c}}}))
    s.settimeout(3); end = time.time() + wait; ticks = 0; shown = 0
    try:
        gen = ws_frames(s, rest)
        while time.time() < end and ticks < 5:
            msg = next(gen)
            if msg is None: continue
            if msg[:1] in '01' and '|' in msg[:20]:
                parts = msg.split('|', 3); f = parts[3].split('^') if len(parts) > 3 else []
                ticks += 1
                if shown < 2:   # 필드 순서를 모르니 앞 20개를 번호와 같이 찍는다
                    print('   체결 %s: ' % parts[1] + ' '.join('[%d]%s' % (i, v) for i, v in enumerate(f[:20]))); shown += 1
                else:
                    print('   체결 %s: [0]%s [1]%s ... (%d개 필드)' % (parts[1], f[0] if f else '', f[1] if len(f) > 1 else '', len(f)))
                continue
            try: j = json.loads(msg)
            except ValueError: print('   알 수 없는 메시지: %s' % msg[:80]); continue
            h, b = j.get('header', {}), j.get('body', {})
            if h.get('tr_id') == 'PINGPONG': ws_send(s, msg); continue
            print('   응답 %s %s: rt_cd=%s %s' % (h.get('tr_id'), h.get('tr_key'), b.get('rt_cd'), (b.get('msg1') or '').strip()))
    except Exception as e:
        print('   연결 끊김: %s' % e)
    finally:
        try: s.close()
        except Exception: pass
    print('   받은 체결 %d건%s' % (ticks, '' if ticks or night else ' (야간 시간이 아니라 정상)'))

if __name__ == '__main__':
    main()
