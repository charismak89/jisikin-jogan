---
paths:
  - "web/**"
  - "v6/**"
  - "index.html"
  - "style.css"
  - "style-v2.css"
  - "template-v5.html"
  - "render.py"
  - "DESIGN.md"
---

# 화면을 고칠 때

- 색, 글자, 숫자 표기, 배치 규칙은 루트 `DESIGN.md`. 토큰이나 `fmt.ts` 를 바꾸면 그 표와 대비 값을 같은 PR 에서 고친다. 1절(공통)은 표준 A 글로, 모의투자 봇(원본)과 코인 집사 `DESIGN.md` 1절과 같은 글이다(2026-11-26). 두 저장소는 세션에 기본으로 붙어 있지 않다. 1절을 대조하거나 고칠 일이면 첫 턴에 add_repo 허용을 사용자에게 받는다(2026-10-28, 2026-11-26 모두 첫 시도는 auto mode 가 거부, 사용자가 채팅으로 허용한 뒤 성공).
- 실험실은 표준 A(몽타주)다. 실험실 소스에 옛 토큰 이름(`text-tx*`, `bg-card2`, `text-dn`, `brand-soft`)과 공용 `dir()` 을 쓰지 않는다. 토큰 생성 파일(`web/src/styles/montage.css`, `web/src/labs/montage-night.css`)은 `npm run tokens` 로만 고친다.
- `v6/` 와 루트 `index.html` 은 `web/` 빌드 산출물이다. 직접 고치지 않는다. `cd web && npm ci && npm run build` 후 `v6/`, `index.html` 을 소스와 같은 커밋에 넣는다. PR 의 `check / web` 잡이 둘이 맞는지 본다.
- 실험실 `labs/`(2026-11-26, 처음 이름 stg): `web/labs.html` 과 `web/src/labs/` 를 `vite build --mode labs` 로 빌드한 산출물이다. 메인 탭 줄의 `실험실 BETA` 버튼으로 누구나 들어온다. `npm run build` 가 v6 와 labs 를 같이 낸다. 메인 화면은 `web/src/labs/` 를 고쳐도 바뀌지 않는다. 공용 파일(`components/`, `lib/`, `types.ts`, `index.css`)을 고치면 두 화면이 같이 바뀐다. 다 보면 `web/index.html` 의 진입점을 실험실 앱으로 바꿔 전환한다. 시간대별 사진은 `python3 uishots.py --page labs/ --clock 23:00`.
- 메인 화면 클래스는 `web/src/index.css` 의 `@source`(App.tsx, components, lib, index.html)에서만 찾는다(2026-11-26, 실험실 클래스가 섞여 메인 산출물이 바뀌던 문제). 메인 화면 코드를 새 폴더에 두면 `@source` 를 더한다. 빠지면 그 클래스가 메인 CSS 에서 조용히 사라지고 CI 는 통과한다. 실험실은 `web/src/labs/labs.css` 가 범위를 더한다. 실험실만 고친 PR 은 빌드 뒤 `git status --porcelain -- v6 index.html` 이 비어야 한다.
- 화면 버전 `web/versions.json`(main, labs): 메인이나 공용 파일을 바꾸면 main, 실험실이나 공용 파일을 바꾸면 labs 를 올린다. `python3 versioncheck.py` 로 확인하고 `check / web` 이 같은 검사를 돈다. 메인 맨 아래와 실험실 띠에 보인다. 두 값이 같으면 실험실 띠가 '메인과 같은 화면'이라고 쓴다(실험실을 메인으로 전환할 때 같게 둔다).
- 지난 회차 HTML(`archive/`)은 `../style.css` 를 공유한다. 기존 클래스 이름을 새 뜻으로 쓰지 않는다. 새 화면은 새 클래스, 새 스타일시트로(2026-10-15 `.hv/.hr` 충돌).
- `template-v5.html`, `style.css` 는 이름에 v5 가 남았지만 지우지 않는다. `/v5/` 화면은 2026-10-22 삭제했어도, render.py 가 이 템플릿으로 만든 HTML 에서 브리핑 본문(`day.json.brief_html`, `brief_m`)을 잘라내고 접힘 4,000자 게이트도 이 HTML 로 잰다. `archive/<날짜>.html` 도 이 HTML 이다.
- `render.py`, `template-v5.html` 을 바꾸면 `python3 regress.py` 로 고치기 전, 후 GATE 와 바뀐 줄 수를 확인한다. PR 의 `check / render` 잡이 같은 검사를 돈다.
- 화면을 고쳤으면(빌드 뒤) `python3 uicheck.py --width 360` 으로 루트, `v6/`, `labs/`, `archive/` 를 390, 1440px 와 360px 로 연다(2026-11-26 실험실이 360px 에서만 8px 넘쳤다. 넘치면 넘친 요소를 적는다). 가로 넘침, 콘솔 오류, 4xx 가 0 이어야 한다. 서버를 따로 띄우거나 `pkill` 하지 않는다(2026-10-19 `pkill -f` 가 자기 셸까지 죽여 세 번 실패).
- 상태별 사진(브리핑 전부 펼치기, 의견 창, 차트 크게 보기, 다크)은 일회용 스크립트를 짜지 말고 `python3 uishots.py` 로 찍는다. 로컬에서는 중계기가 Pages 주소만 받아 장중 선이 안 그려지니 장중 화면은 `--intraday`(가짜 장중 봉). 두 스크립트 모두 playwright 가 없으면 `python3 -m pip install playwright` 만 한다. `pip install` 은 다른 파이썬에 깔리고(CLAUDE.md 설치 교훈), `playwright install` 은 하지 않는다. 지난 회차 띠, 월요일 야간 표식처럼 오늘 데이터로 안 나오는 상태는 `--day <다른 day.json>` 으로, 주소 뒤 값은 `--hash` 로 연다 — 가짜 데이터를 넣으려고 node 스크립트를 짜거나 `http.server` 를 따로 띄우지 않는다(2026-11-10 일회용 스크립트 4개, 서버 종료 실패 1회).
- 루틴(07:45)은 `web/` 을 빌드하지 않는다. 루틴이 쓰는 데이터 계약은 루트 `day.json` 이다. `day.json` 필드를 바꾸면 `render.py` 와 `web/src/types.ts` 를 같이 고친다.
