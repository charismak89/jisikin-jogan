#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uicheck.py — 화면 검사. 저장소를 GitHub Pages 와 같은 주소(/jisikin-jogan/)로 잠깐 띄우고 브라우저로 연다.

  python3 uicheck.py                     루트(v6) · v6/ · archive/(지난 회차 목록) 를 390px·1440px 로
  python3 uicheck.py --out <폴더>        스크린샷을 둘 곳 (기본: 임시 폴더, 경로를 출력한다)
  python3 uicheck.py --path '#k=test'    검사할 주소를 하나 더 (루트 기준, 여러 번 써도 된다)

결과: 화면마다 h1, 가로 넘침(px), 콘솔 오류, 저장소 파일 4xx·실패. 하나라도 있으면 종료 코드 1, 없으면 0,
      playwright 가 없으면 2. 글꼴(jsdelivr) 말고 외부 요청은 막는다 — 실시간 칸은 비어 보이는 게 정상이다.
      (중계기는 Pages 주소만 받아서 로컬에서 부르면 CORS 오류만 난다.)
web/ 을 고쳤으면 먼저 `cd web && npm run build`. 이 스크립트는 빌드하지 않고 커밋될 산출물(v6/, index.html)을 연다.
서버는 이 프로세스 안에서 돌고 끝나면 같이 닫힌다(pkill 이 필요 없다). 저장소 파일을 바꾸지 않는다.
"""
import functools, http.server, os, subprocess, sys, tempfile, threading
from urllib.parse import urlsplit

BASE = '/jisikin-jogan/'
PAGES = ['', 'v6/', 'archive/']   # v5/ 는 2026-10-22 삭제
WIDTHS = [(390, 844), (1440, 900)]
CHROMIUM = '/opt/pw-browsers/chromium'  # 클라우드 세션에 깔린 브라우저. playwright install 로 받지 않는다
ALLOW = ('https://cdn.jsdelivr.net/',)  # Pretendard 글꼴. 글꼴이 바뀌면 줄바꿈·넘침이 달라져서 받는다

def args(name):
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == name]

class Handler(http.server.SimpleHTTPRequestHandler):
    # /jisikin-jogan/ 아래만 저장소 파일로 연결한다. Pages 와 같은 상대 경로(../style.css 등)를 그대로 시험하려고
    def translate_path(self, path):
        p = urlsplit(path).path
        if not p.startswith(BASE): return os.path.join(self.directory, '.uicheck-없음')  # 404
        return super().translate_path('/' + p[len(BASE):])
    def log_message(self, *a): pass

def check(page, url, w, h, out, origin):
    con, bad, fail, blocked = [], [], [], [0]
    page.on('console', lambda m: m.type == 'error' and con.append(m))
    page.on('pageerror', lambda e: con.append(e))
    page.on('response', lambda r: r.url.startswith(origin) and r.status >= 400 and bad.append('%d %s' % (r.status, r.url[len(origin):])))
    page.on('requestfailed', lambda r: r.url.startswith(origin) and fail.append(r.url[len(origin):]))
    def route(r):
        if r.request.url.startswith((origin,) + ALLOW): return r.continue_()
        blocked[0] += 1; r.abort()
    page.route('**/*', route)
    page.set_viewport_size({'width': w, 'height': h})
    page.goto(url, wait_until='load')
    try: page.wait_for_load_state('networkidle', timeout=5000)
    except Exception: pass
    page.wait_for_timeout(500)
    h1 = page.evaluate("() => (document.querySelector('h1') || {}).innerText || ''").strip().replace('\n', ' ')
    over = page.evaluate('() => document.documentElement.scrollWidth - document.documentElement.clientWidth')
    # 막은 외부 요청의 'Failed to load resource' 는 오류로 치지 않는다
    errs = []
    for m in con:
        if isinstance(m, Exception): errs.append('pageerror: %s' % str(m)[:200]); continue
        src = (m.location or {}).get('url', '')
        if src and not src.startswith(origin) and 'Failed to load resource' in m.text: continue
        errs.append(m.text[:200])
    name = (url[len(origin) + len(BASE):] or 'root').strip('/#').replace('/', '_').replace('#', '_').replace('=', '-') or 'root'
    shot = os.path.join(out, '%s-%d.png' % (name, w))
    page.screenshot(path=shot, full_page=True)
    problems = (['가로 넘침 %dpx' % over] if over > 0 else []) + errs + ['응답 ' + b for b in bad] + ['실패 ' + f for f in fail]
    print('%s %-14s %5dpx  h1=%r' % ('ok  ' if not problems else 'FAIL', url[len(origin):] or '/', w, h1[:40]))
    for p in problems: print('       - ' + p)
    if blocked[0]: print('       (외부 요청 %d건 막음)' % blocked[0])
    return not problems

def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('playwright 가 없음 — pip install playwright (playwright install 은 하지 말 것. %s 를 쓴다)' % CHROMIUM); return 2
    root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip() or os.getcwd()
    out = (args('--out') or [tempfile.mkdtemp(prefix='uicheck-')])[0]
    os.makedirs(out, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:%d' % srv.server_address[1]
    ok = True
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(**({'executable_path': CHROMIUM} if os.path.exists(CHROMIUM) else {}))
            for p in PAGES + args('--path'):
                for w, h in WIDTHS:
                    page = b.new_page()
                    try: ok = check(page, origin + BASE + p, w, h, out, origin) and ok
                    finally: page.close()
            b.close()
    finally:
        srv.shutdown(); srv.server_close()
    print('UICHECK %s · 스크린샷 %s' % ('PASS' if ok else 'FAIL', out))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
