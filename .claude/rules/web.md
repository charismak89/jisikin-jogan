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
- 지난 회차 HTML(`archive/`, `v5/`)은 `../style.css` 를 공유한다. 기존 클래스 이름을 새 뜻으로 쓰지 않는다. 새 화면은 새 클래스·새 스타일시트로(2026-10-15 `.hv/.hr` 충돌).
- `render.py`·`template-v5.html` 을 바꾸면 `python3 regress.py` 로 고치기 전·후 GATE 와 바뀐 줄 수를 확인한다. PR 의 `check / render` 잡이 같은 검사를 돈다.
- 화면을 고쳤으면(빌드 뒤) `python3 uicheck.py` 로 루트·`v5/`·`v6/` 를 390·1440px 로 연다. 가로 넘침·콘솔 오류·4xx 가 0 이어야 한다. 서버를 따로 띄우거나 `pkill` 하지 않는다(2026-10-19 `pkill -f` 가 자기 셸까지 죽여 세 번 실패).
- 루틴(07:45)은 `web/` 을 빌드하지 않는다. 루틴이 쓰는 데이터 계약은 루트 `day.json` 이다. `day.json` 필드를 바꾸면 `render.py` 와 `web/src/types.ts` 를 같이 고친다.
