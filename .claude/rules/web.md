---
paths:
  - "web/**"
  - "v6/**"
  - "index.html"
  - "style.css"
  - "style-v2.css"
  - "template-v5.html"
  - "render.py"
---

# 화면을 고칠 때

- `v6/` 와 루트 `index.html` 은 `web/` 빌드 산출물이다. 직접 고치지 않는다. `cd web && npm ci && npm run build` 후 `v6/`·`index.html` 을 소스와 같은 커밋에 넣는다. PR 의 `check / web` 잡이 둘이 맞는지 본다.
- 지난 회차 HTML(`archive/`)은 `../style.css` 를 공유한다. 기존 클래스 이름을 새 뜻으로 쓰지 않는다. 새 화면은 새 클래스·새 스타일시트로(2026-10-15 `.hv/.hr` 충돌).
- `template-v5.html`·`style.css` 는 이름에 v5 가 남았지만 지우지 않는다. `/v5/` 화면은 2026-10-22 삭제했어도, render.py 가 이 템플릿으로 만든 HTML 에서 브리핑 본문(`day.json.brief_html`, `brief_m`)을 잘라내고 접힘 4,000자 게이트도 이 HTML 로 잰다. `archive/<날짜>.html` 도 이 HTML 이다.
- `render.py`·`template-v5.html` 을 바꾸면 `python3 regress.py` 로 고치기 전·후 GATE 와 바뀐 줄 수를 확인한다. PR 의 `check / render` 잡이 같은 검사를 돈다.
- 화면을 고쳤으면(빌드 뒤) `python3 uicheck.py` 로 루트·`v6/`·`archive/` 를 390·1440px 로 연다. 가로 넘침·콘솔 오류·4xx 가 0 이어야 한다. 서버를 따로 띄우거나 `pkill` 하지 않는다(2026-10-19 `pkill -f` 가 자기 셸까지 죽여 세 번 실패).
- 상태별 사진(브리핑 전부 펼치기·의견 창·차트 크게 보기·다크)은 일회용 스크립트를 짜지 말고 `python3 uishots.py` 로 찍는다. 로컬에서는 중계기가 Pages 주소만 받아 장중 선이 안 그려지니 장중 화면은 `--intraday`(가짜 장중 봉). 두 스크립트 모두 playwright 가 없으면 `pip install playwright` 만 한다(`playwright install` 은 하지 않는다).
- 루틴(07:45)은 `web/` 을 빌드하지 않는다. 루틴이 쓰는 데이터 계약은 루트 `day.json` 이다. `day.json` 필드를 바꾸면 `render.py` 와 `web/src/types.ts` 를 같이 고친다.
