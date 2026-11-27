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
- **실험실 먼저(사용자 결정 2026-11-27 '실험실에만 먼저 반영 후 승인하면 메인 전환')**: 메인과 실험실이 같은 `web/src/labs` 를 빌드하므로 새 기능은 `LAB`(`web/src/labs/lab.ts`, 빌드 때 상수라 메인 산출물에서 빠진다) 뒤에 둔다. labs 버전만 올린다(versioncheck 가 web/src/labs 변경에 labs 만 요구한다). 사진은 `python3 uishots.py --page labs/`, 메인이 그대로인지는 같은 명령을 `--page` 없이. 승인 뒤 메인 전환 PR: `LAB` 조건 삭제, versions.json main = labs, HANDOFF 에 전환 기록. 중계기(`relay/`)는 응답에 필드를 더하는 쪽으로만 바꿔 메인이 그대로 돌게 한다.
- **2026-11-27 메인 전환(사용자 결정 '지금 전환'):** 메인(`web/index.html` → `v6/`, 루트 `index.html`)도 실험실 앱 `web/src/labs/main.tsx` 를 빌드한다. 두 화면은 같고 빌드 모드만 다르다(`IS_LABS`: 실험실은 위 띠와 '메인으로', 메인은 '실험실 BETA' 버튼과 맨 아래 '화면 vX'). 옛 메인 소스(`web/src/App.tsx`, `main.tsx`, `components/`, `index.css`)는 빌드에 안 쓰이지만 지우지 않았다(삭제는 사용자 확인). 새 기능은 위 '실험실 먼저' 줄대로 `LAB` 뒤에 둔다.
- 실험실 `labs/`(2026-11-26, 처음 이름 stg): `web/labs.html` 과 `web/src/labs/` 를 `vite build --mode labs` 로 빌드한 산출물이다. 메인 탭 줄의 `실험실 BETA` 버튼으로 누구나 들어온다. `npm run build` 가 v6 와 labs 를 같이 낸다. 메인 전환(11/27) 뒤에는 `web/src/labs/` 를 고치면 메인도 바뀌니 새 기능은 `LAB` 뒤에 둔다(위 줄). 시간대별 사진은 `python3 uishots.py --page labs/ --clock 23:00`.
- Tailwind 클래스 탐색 범위는 CSS 입구마다 `@source` 로 정한다. 메인, 실험실 모두 지금은 `web/src/labs/labs.css` 다(옛 메인의 `web/src/index.css` 는 11/27 전환 뒤 안 쓰인다). 화면 코드를 새 폴더에 두면 그 입구에 `@source` 를 더한다. 빠지면 그 클래스가 CSS 에서 조용히 사라지고 CI 는 통과한다(2026-11-26 교훈). 다음 실험을 새 폴더에서 시작하면 그 폴더의 CSS 입구가 메인 산출물을 바꾸지 않는지 빌드 뒤 `git status --porcelain -- v6 index.html` 로 본다.
- 화면 버전 `web/versions.json`(main, labs): `web/src/labs`, 공용 파일은 labs 를 올리고, main 은 메인 전환 PR(또는 `web/index.html` 변경)에서 올린다. `python3 versioncheck.py` 로 확인하고 `check / web` 이 같은 검사를 돈다. 메인 맨 아래와 실험실 띠에 보인다. 두 값이 같으면 실험실 띠가 '메인과 같은 화면'이라고 쓴다(실험실을 메인으로 전환할 때 같게 둔다).
- 지난 회차 HTML(`archive/`)은 `../style.css` 를 공유한다. 기존 클래스 이름을 새 뜻으로 쓰지 않는다. 새 화면은 새 클래스, 새 스타일시트로(2026-10-15 `.hv/.hr` 충돌).
- `template-v5.html`, `style.css` 는 이름에 v5 가 남았지만 지우지 않는다. `/v5/` 화면은 2026-10-22 삭제했어도, render.py 가 이 템플릿으로 만든 HTML 에서 브리핑 본문(`day.json.brief_html`, `brief_m`)을 잘라내고 접힘 4,000자 게이트도 이 HTML 로 잰다. `archive/<날짜>.html` 도 이 HTML 이다.
- `render.py`, `template-v5.html` 을 바꾸면 `python3 regress.py` 로 고치기 전, 후 GATE 와 바뀐 줄 수를 확인한다. PR 의 `check / render` 잡이 같은 검사를 돈다.
- 브리핑 본문(`day.json.brief_html`)과 `day.json` 은 07:45 회차가 만든다. render.py, template-v5.html 변경은 머지해도 다음 회차부터 사이트에 나오니 보고에 그 날짜를 적는다(화면 코드 변경은 머지 1~2분 뒤). 2026-11-27 #101 뒤 사용자가 '주간선물 줄이 아직 안 빠졌다'고 다시 물었다.
- 화면을 고쳤으면(빌드 뒤) `python3 uicheck.py` 로 루트, `v6/`, `labs/`, `archive/` 를 360, 390, 1440px 로 연다(360 은 2026-11-26 실험실이 360px 에서만 8px 넘쳐서 기본에 넣었다. 넘치면 넘친 요소를 적는다). 가로 넘침이 아닌 줄바꿈(카드 제목과 숫자가 끊김)은 uicheck 가 못 잡으니 uishots 대시보드 전체 사진을 본다. 가로 넘침, 콘솔 오류, 4xx 가 0 이어야 한다. 서버를 따로 띄우거나 `pkill` 하지 않는다(2026-10-19 `pkill -f` 가 자기 셸까지 죽여 세 번 실패).
- 상태별 사진(브리핑 전부 펼치기, 의견 창, 차트 크게 보기, 다크)은 일회용 스크립트를 짜지 말고 `python3 uishots.py` 로 찍는다. 로컬에서는 중계기가 Pages 주소만 받아 장중 선이 안 그려지니 장중 화면은 `--intraday`(가짜 장중 봉). 두 스크립트 모두 playwright 가 없으면 `python3 -m pip install playwright` 만 한다. `pip install` 은 다른 파이썬에 깔리고(CLAUDE.md 설치 교훈), `playwright install` 은 하지 않는다. 지난 회차 띠, 월요일 야간 표식처럼 오늘 데이터로 안 나오는 상태는 `--day <다른 day.json>` 으로, 주소 뒤 값은 `--hash` 로 연다 — 가짜 데이터를 넣으려고 node 스크립트를 짜거나 `http.server` 를 따로 띄우지 않는다(2026-11-10 일회용 스크립트 4개, 서버 종료 실패 1회).
- 루틴(07:45)은 `web/` 을 빌드하지 않는다. 루틴이 쓰는 데이터 계약은 루트 `day.json` 이다. `day.json` 필드를 바꾸면 `render.py` 와 `web/src/types.ts` 를 같이 고친다.
