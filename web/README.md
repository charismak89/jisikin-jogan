# web/ — v6 앱 (R1)

대시보드·브리핑 두 탭의 새 화면. Vite + React 18 + TypeScript + Tailwind v4 + Radix(Tabs·Dialog), shadcn/ui 방식의 작은 컴포넌트(`src/components/ui`).
루틴(매일 07:45)은 이 앱을 빌드하지 않는다. 화면을 바꿀 때만 빌드해 `v6/` 산출물을 커밋한다.

- 데이터: 루트 `day.json`(render.py 가 `out/day.json` 으로 쓰고 publish.py 가 반영). 앱은 `../day.json` 을 읽는다. 첫 회차 전에는 안내 문구가 뜬다.
- 브리핑 탭: `day.json.brief_html`(v5 와 글자까지 같은 본문)을 Shadow DOM 안에서 기존 `style.css` 로 그린다.
- 실시간: `src/lib/live.ts` — v5 스크립트와 같은 규칙(Hyperliquid 15초, KRX 중계기, 폴백).
- 빌드: `cd web && npm ci && npm run build` → `../v6/`. 주소: `/jisikin-jogan/v6/`.
- 되돌리기: `v6/` 와 `web/` 를 지워도 루트(v5)에는 영향이 없다.
- 디자인 토큰은 `src/index.css`. StyleSeed toss 스킨은 아직 적용하지 않았다(직접 만든 토스풍 토큰).
