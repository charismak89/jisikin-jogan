# web/ — v6 앱 (R1)

대시보드·브리핑 두 탭의 새 화면. Vite + React 18 + TypeScript + Tailwind v4 + Radix(Tabs·Dialog), shadcn/ui 방식의 작은 컴포넌트(`src/components/ui`).
루틴(매일 07:45)은 이 앱을 빌드하지 않는다. 화면을 바꿀 때만 빌드해 `v6/` 산출물을 커밋한다.

- 데이터: 루트 `day.json`(render.py 가 `out/day.json` 으로 쓰고 publish.py 가 반영). 앱은 스크립트 위치 기준으로 루트 `day.json` 을 읽는다(`src/lib/site.ts`). 루트에서 열든 `/v6/` 에서 열든 같다.
- 브리핑 탭: `day.json.brief_html`(v5 와 글자까지 같은 본문)을 Shadow DOM 안에서 `src/brief.css`(대시보드와 같은 토스풍 토큰)로 그린다. 2026-10-22 전에는 v5 의 `style.css` 를 불러 썼다. v5·archive 는 지금도 `style.css` 를 쓴다.
- 실시간: `src/lib/live.ts` — 토스(KRX·NXT) 중계기만 15초마다 부른다(키 없이도, 키가 있으면 같이). 토스 시세가 오면 Hyperliquid 는 부르지 않고, 중계기 실패 때만 추종가로 폴백. 코스피는 09:00 전 '개장 전'으로 표시(지수는 장 전 거래가 없다).
- 빌드: `cd web && npm ci && npm run build` → `../v6/` 산출물 + 루트 `../index.html`(자산 경로만 `./v6/assets/` 로 바꾼 셸, `vite.config.ts` 의 rootShell). 주소: 메인 `/jisikin-jogan/`(2026-10-19 부터), `/jisikin-jogan/v6/` 도 같은 화면.
- 되돌리기(메인을 v5 로): 이 전환 PR 을 revert 한다. 손으로 하려면 `v5/index.html` 을 루트로 복사하면서 `../style.css`→`style.css`, `../archive/`→`./archive/` 로 바꾸고 `publish.py` 의 V5 경로를 루트로 되돌린다.
- 디자인 토큰은 `src/index.css`. StyleSeed toss 스킨은 아직 적용하지 않았다(직접 만든 토스풍 토큰).
