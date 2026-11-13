---
paths:
  - "fetch_*.py"
  - "score.py"
  - "render.py"
  - "datacheck.py"
  - "sources.json"
  - "RUNBOOK.md"
  - "WEEKLY.md"
  - "calibration.json"
  - "analyze.py"
---

# 회차 스크립트, 절차 문서를 고칠 때 (관리 세션 전용 — 07:45 회차는 이 파일을 따르지 않는다)

- 회차(LLM)는 스크립트가 출력하는 지시 문구를 RUNBOOK 보다 먼저 따른다. 출력에 "1순위", "쓴다", "시도" 같은 지시를 넣거나 바꾸면 `RUNBOOK.md` 2, 4절과 `sources.json` 의 같은 항목 순서와 맞는지 대조한다. 2026-10-22 회차가 `fetch_relay.py` 의 "이 값을 1순위로 쓴다" 를 미국 종가에도 적용해 공식 종가와 다른 값(NVDA 221.86 vs 221.97)을 썼다(PR #30).
- 이 파일들이나 `RUNBOOK.md` 를 바꾼 PR 을 머지하면 다음 평일 08:15 KST 에 결과 확인을 `send_later` 로 건다. 볼 것: `get_trigger trig_017rnKLpNdYfD3c61DqqmLPP` 의 `last_run`, `datalog.json` 마지막 줄, 회차 보고(`list_events`, `kinds=["assistant"]`, `limit` 20 — HANDOFF 2절)의 중계기, 데이터 누락, 경고, GATE 줄, 바꾼 항목 1건 이상을 웹 원값과 대조. 10/22 확인이 위 미국 종가 차이를 잡았다.
  - 예외: 토요일 주간 점검 세션에는 `send_later` 가 없다(루틴에 커넥터를 붙일 수 없음, 2026-10-31). 주말 변경은 매주 월요일 08:15 예약 작업 `trig_01966XhBzHkZbYHr2Pg3ecif` 가 저장소, 웹만으로 확인한다(`WEEKLY.md` 4절 9번). 평일에 관리 세션이 바꾼 것은 그 세션이 `send_later` 를 건다.
- `WEEKLY.md`, `RUNBOOK.md` 에 조건 규칙(예: "HANDOFF 7절에 X 가 남아 있으면")을 넣으면, 그 문구를 저장소 전체에서 grep 해 이미 걸리는 줄을 정리한다. 직전 회차 기록(`list_events`)을 옆에 두고 다음 회차를 첫 단계부터 따라가 보고, 규칙을 언제 지우는지까지 같은 PR 에 넣는다. 2026-10-28 #41 이 끝난 안건 줄(HANDOFF 9번)과 결정 뒤 정리 단계를 빠뜨려 #44 로 다시 고쳤다.
- 중계기 값과 회차 값의 불일치 경고 기준은 `fetch_relay.merge_into` 의 0.05% 다. 이보다 작은 차이(10/21 NVDA 0.0496%)는 경고 없이 지나가니 대조는 숫자로 직접 한다.
- `calibration.json` 의 규칙(`rule`, `stock_rule`)만 바꾼 변경은 `regress.py` 로 확인되지 않는다. regress 는 발행 당시 `calibration.json`, `state.json` 을 써서 전, 후가 같게 나온다(+0 −0 줄). 2026-11-09 PR #54 가 이 숫자를 월요일 확장 검증으로 적었다. 새 규칙은 마지막 회차 입력으로 재연한다(저장소 루트에서, 2026-11-09 실측):
  ```bash
  B=$(git log -1 --format=%h --grep='^brief:') && T=$(mktemp -d) && cp *.py *.json CONTEXT.md template-v5.html $T/ && git show $B~1:state.json > $T/state.json && cp fixtures/last-fill.json $T/fill.json && cp fixtures/last-perp.json $T/perp.json && cp fixtures/last-relay.json $T/relay.json && cd $T && python3 score.py --dry-run && python3 render.py
  ```
  `score.py` 의 `규칙 적용` 줄과 `render.py` 의 `종목 예측` 줄, GATE 를 본다. 규칙이 갈리는 경로(해당 요일, 추종가 없음 = `perp.json` 치우기, 규칙 키 삭제 = 롤백)를 각각 한 번씩 돌린다.
