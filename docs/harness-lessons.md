# 하네스 교훈

하네스 회고에서 승인된 것만 한 줄씩 남긴다. 형식: 날짜 | 상황 | 교훈(어느 파일에 무엇을) | 근거(턴·커밋) | 확신

- 2026-10-20 | v6 메인 전환·차트 확대 검증 때 매번 http.server 를 손으로 띄우고 `pkill -f` 로 닫다가 자기 셸까지 죽어 세 번 실패(exit 144) | `uicheck.py` 추가, `.claude/rules/web.md`·`WEEKLY.md` 4-2 에 "빌드 뒤 uicheck.py" | 10/19 PR #21·#22 검증 턴 | 높음
- 2026-10-20 | VM 반영 여부를 다른 세션 기록으로 추정. 사람이 할 일의 완료 확인 방법이 문서에 없었다 | `HANDOFF.md` 머리말에 "사람 작업 줄엔 확인 명령·기대값", `relay/README.md` 확인 절에 키 없는 `/v1/live` 200/401 | 10/19 PR #23 뒤 "vm 갱신 완료" 확인 턴 | 중간
- 2026-10-21 | 지식인 조간 세션이 PR 머지를 매번 사용자에게 요청함. 원인은 머지 규칙 부재 + 공통 블록의 "배포 전 확인" | 세 저장소 공통 블록에 "PR 머지"(바로 머지, 예외는 "머지 예외:" 줄)·"세션 마무리"(끝나면 새 세션 안내 문장) 추가, 지식인 조간 CLAUDE.md 에 작업 규칙(HOLD 브랜치만 예외) | 사용자 지적 10/21 | 높음
- 2026-10-22 | 루틴용 스크립트(fetch_relay.py) 출력 문구가 RUNBOOK 우선순위와 어긋났고, 회차가 출력 문구를 따라 미국 종가를 토스 값으로 씀. 루틴 변경 뒤 결과 확인도 사용자가 요청해야 했다 | `.claude/rules/routine-scripts.md`(paths: fetch_*.py·score.py·render.py·datacheck.py·sources.json): 출력 지시 문구와 RUNBOOK·sources.json 대조, 머지 뒤 다음 회차 08:15 결과 확인 send_later | PR #27 → 10/22 확인 턴 → PR #30(da3456c) | 높음
- 2026-10-22 | 10/16 반폭 규칙 변경 뒤에도 옛 기준(0.8 고정)의 롤백 판정 예약이 다른 세션에 남아 있었고, 지시문은 그 세션에서만 고칠 수 있었다 | `CALIBRATION.md` 규칙 변경 절차에 "list_triggers 로 관련 예약 맞추기, 다른 세션 것은 끄고 다시 걸기", `HANDOFF.md` 2절 표에 실측 행 | 모델 추천 턴의 list_triggers, 롤백 예약 수정 턴의 update_trigger 거부 | 중간
- 2026-10-22 | 화면 손질 검증 때 uicheck.py 가 열지 않는 상태(브리핑 전부 펼치기·의견 창·차트 크게 보기·다크·장중 선)를 보려고 일회용 캡처 스크립트 3개를 새로 짰고, playwright 가 없어 두 번 실패했다. 장중 선은 로컬에서 중계기 CORS 로 안 그려져 응답을 가짜로 바꿔 끼웠다 | `uishots.py`(상태별 사진, `--intraday` 가짜 장중 봉) 추가, `.claude/rules/web.md` 에 "일회용 스크립트 대신 uishots.py"·playwright 설치 한 줄, `check.yml` py_compile 에 추가 | 10/22 세션 턴 1(PR #34 검증: shots.py·livetest.py·shots2.py) | 중간
- 2026-10-22 | v5 화면 삭제 때 `template-v5.html`·`style.css` 가 브리핑 본문·4,000자 게이트·archive 의 원본이라는 의존 관계가 문서에 없어 render.py·publish.py 를 다시 읽어 찾았다. README 표는 둘을 '첫 화면 대시보드' 뼈대로 설명해 잔재로 읽힐 수 있었다 | `README.md` 구조 표 행 고침, `.claude/rules/web.md` 에 "이름에 v5 가 남았지만 지우지 않는다(brief_m·게이트·archive)" | 10/22 세션 턴 2(PR #35 조사) | 중간
- 2026-10-28 | 주간 점검 절차(WEEKLY.md)에 문구 조건 규칙을 넣은 PR 이 다음 회차를 따라가 보지 않고 머지돼, 같은 문구가 남은 끝난 안건 줄과 결정 뒤 정리 단계가 빠졌다 | `.claude/rules/routine-scripts.md` paths 에 RUNBOOK.md·WEEKLY.md, "조건 문구 grep · 직전 회차 기록 옆에 두고 다음 회차 따라가기 · 지우는 시점까지 같은 PR" | #41(9bc9713) → 이 세션 턴 1 시뮬레이션 → #44(776792c) | 높음
- 2026-10-28 | DESIGN.md 1절을 코인 집사와 대조하려다 add_repo 가 auto mode 에 한 번 막혀 사용자 허용 턴까지 미뤄졌다. DESIGN.md 만 고치는 세션은 web.md 를 읽지 않았다 | `.claude/rules/web.md` paths 에 DESIGN.md, 1절 줄에 "코인 집사는 기본으로 안 붙어 있음 — 첫 턴에 add_repo 허용 받기" | 이 세션 턴 1 거부 → "허용" 턴 성공(diff 0), PR #45 | 중간
