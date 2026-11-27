#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uishots.py — 화면 상태별 사진. uicheck.py 가 열지 않는 상태(브리핑 전부 펼치기·의견 창·차트 크게 보기(첫 카드, 20거래일)·다크·장중 선)를 찍는다.

  python3 uishots.py                     대시보드·차트 크게 보기·의견 창·브리핑(전부 펼치기)을 390·1440px, 라이트·다크로
  python3 uishots.py --intraday          + 중계기 /v1/intraday·/v1/live 응답을 가짜 장중 봉으로 바꿔 장중 선을 그린다
  python3 uishots.py --width 820         폭을 바꾼다 (여러 번 써도 된다)
  python3 uishots.py --day <파일>        day.json 대신 그 파일을 화면에 준다 — 지난 회차 띠·월요일 야간 표식처럼 오늘 데이터로는 안 나오는 상태를 볼 때.
                                         예: git show <월요일 brief 커밋>:day.json > /tmp/day-mon.json (2026-11-10 — 이 옵션이 없어 일회용 스크립트를 네 개 짰다)
  python3 uishots.py --hash '#brief'     주소 뒤에 붙인다 (옛 지인 링크 '#k=…' 가 정리되는지 볼 때 등)
  python3 uishots.py --out <폴더>        사진을 둘 곳 (기본: 임시 폴더, 경로를 출력한다)
  python3 uishots.py --perp              해외 추종가(Hyperliquid candleSnapshot)와 중계기 /v1/night(야간선물) 응답을 가짜 봉으로 채운다 — 밤 카드를 볼 때. 실제 값이 아니다.
  python3 uishots.py --watch             중계기 /v1/stocks, /v1/quotes, /v1/kospi-daily 를 가짜로 채우고 관심 탭(#w=)도 찍는다 — 실험실 관심종목, 20거래일 캔들(2026-11-27). 실제 값이 아니다.
  python3 uishots.py --top               첫 화면(스크롤 전)만 찍는다. 시간대별 첫 카드를 빨리 볼 때
  python3 uishots.py --tap 삼성전자        찍기 전에 그 이름의 탭이나 버튼을 누른다(첫 카드 종목 선택 등). 파일 이름에 붙는다
  python3 uishots.py --page labs/        루트 대신 그 주소를 연다 (실험실 labs/ 등)
  python3 uishots.py --clock 23:00       브라우저 시계를 그 시각(KST)으로 놓고 연다. HH:MM 은 day.json 발행일, 날짜는 2026-11-28T12:00 처럼.
                                         여러 번 쓰면 시각마다 찍는다. 첫 카드가 시간대마다 바뀌는지 볼 때(2026-11-26). 시세 응답은 지금 값 그대로다.

판정은 하지 않는다. 가로 넘침·콘솔 오류·4xx 는 uicheck.py 로 본다. 이 스크립트는 눈으로 볼 사진만 만든다.
web/ 을 고쳤으면 먼저 `cd web && npm run build`. 커밋될 산출물(루트 index.html·v6/)을 연다. 저장소 파일을 바꾸지 않는다.
로컬에서는 중계기가 Pages 주소만 받아서 장중 선이 그려지지 않는다. --intraday 는 그 응답을 가짜로 채운다:
day.json 의 종목마다 09:01~15:31 5분 봉, 전일 종가 −1.2% ± 0.6% 사인파. 실제 값이 아니다.
"""
import datetime as dt, functools, http.server, json, math, os, sys, tempfile, threading
from uicheck import ALLOW, BASE, CHROMIUM, Handler, args

ROOT = os.path.dirname(os.path.abspath(__file__))

def fake_intraday(day):
    """중계기 /v1/intraday·/v1/live 와 같은 모양({items: {종목: {bars, ohlc, open, last}}})의 가짜 응답. 1분봉, ohlc 는 캔들용(2026-11-27)"""
    items = {}
    for e in day['ent']:
        bars, ohlc, t, i = [], [], day['t_open'] + 60000, 0
        while t <= day['t_close'] + 60000:
            f = lambda k: e['prev'] * (1 - 0.012 + 0.006 * math.sin(k / 45) + 0.0012 * math.sin(k * 1.7))
            o, c = f(i - 1), f(i)
            ohlc.append([t, o, max(o, c) * 1.0004, min(o, c) * 0.9996, c]); bars.append([t, c]); t += 60000; i += 1
        items[e['key']] = {'bars': bars, 'ohlc': ohlc, 'open': bars[0][1], 'last': bars[-1][1]}
    return json.dumps({'items': items})

WATCH = [['005930', '삼성전자', 'KOSPI'], ['000660', 'SK하이닉스', 'KOSPI'], ['066570', 'LG전자', 'KOSPI'], ['010120', 'LS ELECTRIC', 'KOSPI'],
         ['035420', 'NAVER', 'KOSPI'], ['247540', '에코프로비엠', 'KOSDAQ'], ['034730', 'SK', 'KOSPI'], ['016360', '삼성증권', 'KOSPI']]

def fake_watch(path, dj):
    """관심종목, 코스피 일봉 가짜 응답(2026-11-27). 실제 값이 아니다"""
    if path == '/v1/stocks': return json.dumps({'items': WATCH})
    if path == '/v1/quotes':
        items = {}
        for i, (c, n, m) in enumerate(WATCH):
            base = [171300, 1053000, 135200, 113400, 160200, 98700, 430000, 69400][i]
            pct = [4.14, 4.65, 5.77, 6.44, 1.62, -2.31, 8.84, 0.0][i]
            last = round(base * (1 + pct / 100), -2)
            items[c] = {'last': last, 'base': base, 'base_src': 'krx', 'vol': [12553942, 2745141, 818664, 470942, 345292, 1204331, 66792, 378369][i],
                        'ref': dj['issue'], 'chg': last - base, 'pct': round((last / base - 1) * 100, 2)}
        return json.dumps({'items': items})
    if path == '/v1/kospi-daily':
        out, prev = [], None
        for r in dj['k20']['rows']:
            c = r.get('close')
            if c is None: continue
            o = r.get('open') or prev or c
            out.append([r['date'], o, max(o, c) * 1.006, min(o, c) * 0.994, c]); prev = c
        return json.dumps({'items': out})
    return None

KST = dt.timezone(dt.timedelta(hours=9))

def clock_at(v, issue):
    """'23:00' → 발행일 23:00 KST, '2026-11-28T12:00' → 그 시각 KST"""
    t = dt.datetime.fromisoformat(v if 'T' in v else '%sT%s' % (issue, v))
    return t.replace(tzinfo=KST) if t.tzinfo is None else t

IV = {'1m': 6e4, '5m': 3e5, '15m': 9e5, '1h': 36e5}

def fake_perp(day, req_body):
    """Hyperliquid candleSnapshot 과 같은 모양의 가짜 봉. 기준가(ent.base) ± 사인파, 시각은 요청 범위 그대로"""
    try: req = json.loads(req_body or '{}').get('req', {})
    except ValueError: return '[]'
    e = next((x for x in day['ent'] if x['coin'] == req.get('coin')), None)
    if not e or not e.get('base'): return '[]'
    ms = IV.get(req.get('interval'), 6e4)
    t, end, out = int(req['startTime'] // ms * ms), int(req['endTime']), []
    while t <= end:
        k = (t - day['t_prev']) / 36e5
        f = lambda k: e['base'] * (1 + 0.006 * math.sin(k / 2.5) + 0.002 * math.sin(k * 3))
        o, c = f(k - ms / 36e5), f(k)
        out.append({'t': t, 'T': t + ms - 1, 's': e['coin'], 'i': req.get('interval'), 'o': str(o), 'c': str(c), 'h': str(max(o, c) * 1.0003), 'l': str(min(o, c) * 0.9997), 'v': '1', 'n': 1})
        t += int(ms)
    return json.dumps(out)

def fake_night(day, issue, clock):
    """중계기 /v1/night 와 같은 모양의 가짜 야간선물(발행일 18:00 ~ min(시계, 다음날 06:00), 1분봉). 실제 값이 아니다"""
    t0 = int(dt.datetime.fromisoformat(issue + 'T18:00:00+09:00').timestamp() * 1000)
    end = t0 + 12 * 3600 * 1000
    now = int(clock.timestamp() * 1000) if clock else end
    base, bars, ohlc, t = 726.75, [], [], t0 + 60000
    f = lambda k: round(base * (1 + 0.004 * math.sin(k / 1.7) - 0.002 * math.sin(k * 2.3) + 0.0006 * math.sin(k * 40)), 2)
    while t <= min(now, end):
        k = (t - t0) / 36e5
        o, c = f(k - 1 / 60), f(k)
        bars.append([t, c]); ohlc.append([t, o, round(max(o, c) + 0.15, 2), round(min(o, c) - 0.15, 2), c])
        t += 60000
    st = 'none' if not bars else ('live' if now < end else 'closed')
    last = bars[-1][1] if bars else None
    return json.dumps({'session': issue, 'code': 'A01612', 'name': 'F 202612', 'state': st, 'base': base, 'last': last,
                       'pct': round((last / base - 1) * 100, 2) if last else None, 'asof': bars[-1][0] if bars else None, 'bars': bars, 'ohlc': ohlc, 'error': None})

def shoot(b, origin, w, h, dark, out, relay, body, day_body=None, frag='', page='', clock=None, perp=None, issue=None, watch=None):
    ctx = b.new_context(viewport={'width': w, 'height': h}, color_scheme='dark' if dark else 'light', timezone_id='Asia/Seoul', locale='ko-KR')
    p = ctx.new_page()
    if clock: p.clock.install(time=clock)
    def route(r):
        u = r.request.url
        if day_body and u.split('?')[0].endswith('/day.json'):
            return r.fulfill(status=200, content_type='application/json', body=day_body)
        if perp and relay and issue and u.split('?')[0] == relay + '/v1/night':
            return r.fulfill(status=200, content_type='application/json', body=fake_night(perp[1], issue, clock), headers={'Access-Control-Allow-Origin': '*'})
        if perp and u.startswith(perp[0]) and r.request.method == 'POST':
            return r.fulfill(status=200, content_type='application/json', body=fake_perp(perp[1], r.request.post_data), headers={'Access-Control-Allow-Origin': '*'})
        if watch and relay and u.startswith(relay):
            wb = fake_watch(u[len(relay):].split('?')[0], watch)
            if wb: return r.fulfill(status=200, content_type='application/json', body=wb, headers={'Access-Control-Allow-Origin': '*'})
        if body and relay and u.startswith(relay):
            return r.fulfill(status=200, content_type='application/json', body=body, headers={'Access-Control-Allow-Origin': '*'})
        if u.startswith((origin,) + ALLOW): return r.continue_()
        r.abort()
    p.route('**/*', route)
    p.on('pageerror', lambda e: print('       pageerror: %s' % str(e)[:200]))
    p.goto(origin + BASE + page + frag, wait_until='load'); p.wait_for_timeout(1500)
    tap = (args('--tap') or [None])[0]
    if tap:
        p.get_by_role('tab', name=tap).or_(p.get_by_role('button', name=tap)).first.click(); p.wait_for_timeout(300)
    sfx = '%s%d%s%s%s' % (page.strip('/').replace('/', '_') + '-' if page else '', w, '-dark' if dark else '', clock.strftime('-%m%d%H%M') if clock else '', '-' + tap if tap else '')
    shots = []
    def snap(name, full):
        f = os.path.join(out, '%s-%s.png' % (name, sfx)); p.screenshot(path=f, full_page=full); shots.append(os.path.basename(f))
    if '--top' in sys.argv:
        snap('top', False); ctx.close()
        print('%5dpx %-5s %s%s' % (w, 'dark' if dark else 'light', (clock.strftime('%m/%d %H:%M ') if clock else ''), ' · '.join(shots))); return
    snap('dash', True)
    # 차트 크게 보기(2026-11-27 Lightweight Charts): 첫 카드와 20거래일 카드. 라이브러리를 열 때 불러오니 조금 기다린다
    for nm, sel in (('chart-exp', 'section[aria-label="지금 시장"]'), ('chart-exp-k20', '[aria-label="코스피 최근 20거래일과 예측 기록"]')):
        box = p.locator(sel).first
        if box.count() and box.get_by_role('button', name='차트 크게 보기').count():
            box.get_by_role('button', name='차트 크게 보기').click(); p.wait_for_timeout(1200)
            snap(nm, False)
            five = p.get_by_role('dialog').get_by_role('button', name='5분')   # 실험실 캔들(2026-11-27): 5분봉도 한 장
            if five.count():
                five.click(); p.wait_for_timeout(400); snap(nm + '-5m', False)
            p.keyboard.press('Escape'); p.wait_for_timeout(300)
    fb = p.get_by_role('button', name='의견')
    if fb.count():
        fb.click(); p.wait_for_timeout(500)
        snap('feedback', False); p.keyboard.press('Escape'); p.wait_for_timeout(200)
    if watch and p.get_by_role('tab', name='관심').count():   # 실험실 관심 탭: 링크(#w=)로 목록을 넣고 찍는다
        p.goto(origin + BASE + page + '#w=' + ','.join(x[0] for x in WATCH), wait_until='load'); p.reload(wait_until='load'); p.wait_for_timeout(1500)   # 해시만 바뀌면 다시 읽지 않아 reload
        snap('watch', True)
        p.get_by_role('button', name='편집').click(); p.wait_for_timeout(200); snap('watch-edit', False)
        p.get_by_role('textbox').fill('하이'); p.wait_for_timeout(200); snap('watch-search', False)
        p.evaluate("localStorage.removeItem('jj-watch')")
    p.get_by_role('tab', name='브리핑 전문').click(); p.wait_for_timeout(800)
    p.get_by_role('button', name='전부 펼치기').click(); p.wait_for_timeout(300)
    snap('brief-open', True)
    ctx.close()
    print('%5dpx %-5s %s%s' % (w, 'dark' if dark else 'light', (clock.strftime('%m/%d %H:%M ') if clock else ''), ' · '.join(shots)))

def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('playwright 가 없음 — python3 -m pip install playwright (playwright install 은 하지 말 것. %s 를 쓴다)' % CHROMIUM); return 2
    out = (args('--out') or [tempfile.mkdtemp(prefix='uishots-')])[0]
    os.makedirs(out, exist_ok=True)
    widths = [(int(x), 900) for x in args('--width')] or [(390, 844), (1440, 900)]
    day_file = (args('--day') or [None])[0]
    day_body = open(day_file, encoding='utf-8').read() if day_file else None
    frag = (args('--hash') or [''])[0]
    page = (args('--page') or [''])[0]
    dj = json.loads(day_body or open(os.path.join(ROOT, 'day.json'), encoding='utf-8').read())
    day = dj['day']
    clocks = [clock_at(v, dj['issue']) for v in args('--clock')] or [None]
    perp = (day['api'], day) if '--perp' in sys.argv and day.get('api') else None
    relay, body = day.get('relay'), None
    if '--intraday' in sys.argv:
        if relay: body = fake_intraday(day)
        else: print('day.json 에 중계기 주소(day.relay)가 없어 --intraday 를 건너뛴다')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:%d' % srv.server_address[1]
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(**({'executable_path': CHROMIUM} if os.path.exists(CHROMIUM) else {}))
            for w, h in widths:
                for clock in clocks:
                    for dark in (False, True): shoot(b, origin, w, h, dark, out, relay, body, day_body, frag, page, clock, perp, dj['issue'], dj if '--watch' in sys.argv else None)
            b.close()
    finally:
        srv.shutdown(); srv.server_close()
    print('UISHOTS %s%s%s사진 %s' % ('가짜 장중 봉 · ' if body else '', '가짜 추종가 · ' if perp else '', ('day=%s · ' % day_file) if day_file else '', out))
    return 0

if __name__ == '__main__':
    sys.exit(main())
