#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uishots.py — 화면 상태별 사진. uicheck.py 가 열지 않는 상태(브리핑 전부 펼치기·의견 창·차트 크게 보기·다크·장중 선)를 찍는다.

  python3 uishots.py                     대시보드·차트 크게 보기·의견 창·브리핑(전부 펼치기)을 390·1440px, 라이트·다크로
  python3 uishots.py --intraday          + 중계기 /v1/intraday·/v1/live 응답을 가짜 장중 봉으로 바꿔 장중 선을 그린다
  python3 uishots.py --width 820         폭을 바꾼다 (여러 번 써도 된다)
  python3 uishots.py --out <폴더>        사진을 둘 곳 (기본: 임시 폴더, 경로를 출력한다)

판정은 하지 않는다. 가로 넘침·콘솔 오류·4xx 는 uicheck.py 로 본다. 이 스크립트는 눈으로 볼 사진만 만든다.
web/ 을 고쳤으면 먼저 `cd web && npm run build`. 커밋될 산출물(루트 index.html·v6/)을 연다. 저장소 파일을 바꾸지 않는다.
로컬에서는 중계기가 Pages 주소만 받아서 장중 선이 그려지지 않는다. --intraday 는 그 응답을 가짜로 채운다:
day.json 의 종목마다 09:01~15:31 5분 봉, 전일 종가 −1.2% ± 0.6% 사인파. 실제 값이 아니다.
"""
import functools, http.server, json, math, os, sys, tempfile, threading
from uicheck import ALLOW, BASE, CHROMIUM, Handler, args

ROOT = os.path.dirname(os.path.abspath(__file__))

def fake_intraday(day):
    """중계기 /v1/intraday·/v1/live 와 같은 모양({items: {종목: {bars, open, last}}})의 가짜 응답"""
    items = {}
    for e in day['ent']:
        bars, t, i = [], day['t_open'] + 60000, 0
        while t <= day['t_close'] + 60000:
            bars.append([t, e['prev'] * (1 - 0.012 + 0.006 * math.sin(i / 9))]); t += 300000; i += 1
        items[e['key']] = {'bars': bars, 'open': bars[0][1], 'last': bars[-1][1]}
    return json.dumps({'items': items})

def shoot(b, origin, w, h, dark, out, relay, body):
    ctx = b.new_context(viewport={'width': w, 'height': h}, color_scheme='dark' if dark else 'light')
    p = ctx.new_page()
    def route(r):
        u = r.request.url
        if body and relay and u.startswith(relay):
            return r.fulfill(status=200, content_type='application/json', body=body, headers={'Access-Control-Allow-Origin': '*'})
        if u.startswith((origin,) + ALLOW): return r.continue_()
        r.abort()
    p.route('**/*', route)
    p.on('pageerror', lambda e: print('       pageerror: %s' % str(e)[:200]))
    p.goto(origin + BASE, wait_until='load'); p.wait_for_timeout(1500)
    sfx, shots = '%d%s' % (w, '-dark' if dark else ''), []
    def snap(name, full):
        f = os.path.join(out, '%s-%s.png' % (name, sfx)); p.screenshot(path=f, full_page=full); shots.append(os.path.basename(f))
    snap('dash', True)
    live = p.locator('section[aria-label="예측과 실시간"]')
    if live.count():
        live.get_by_role('button', name='차트 크게 보기').click(); p.wait_for_timeout(400)
        snap('chart-exp', False); p.keyboard.press('Escape'); p.wait_for_timeout(200)
    fb = p.get_by_role('button', name='의견')
    if fb.count():
        fb.click(); p.wait_for_timeout(500)
        snap('feedback', False); p.keyboard.press('Escape'); p.wait_for_timeout(200)
    p.get_by_role('tab', name='브리핑 전문').click(); p.wait_for_timeout(800)
    p.get_by_role('button', name='전부 펼치기').click(); p.wait_for_timeout(300)
    snap('brief-open', True)
    ctx.close()
    print('%5dpx %-5s %s' % (w, 'dark' if dark else 'light', ' · '.join(shots)))

def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('playwright 가 없음 — pip install playwright (playwright install 은 하지 말 것. %s 를 쓴다)' % CHROMIUM); return 2
    out = (args('--out') or [tempfile.mkdtemp(prefix='uishots-')])[0]
    os.makedirs(out, exist_ok=True)
    widths = [(int(x), 900) for x in args('--width')] or [(390, 844), (1440, 900)]
    day = json.load(open(os.path.join(ROOT, 'day.json'), encoding='utf-8'))['day']
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
                for dark in (False, True): shoot(b, origin, w, h, dark, out, relay, body)
            b.close()
    finally:
        srv.shutdown(); srv.server_close()
    print('UISHOTS %s사진 %s' % ('가짜 장중 봉 · ' if body else '', out))
    return 0

if __name__ == '__main__':
    sys.exit(main())
