# 운영 핸드오프 (Claude Code 기준)

**새 세션이 먼저 읽을 파일.** 이 문서와 저장소(main), 루틴 조회(list_triggers)만 있으면 상태를 복원할 수 있다.
2026-09-28 에 관리 주체를 코워크에서 Claude Code(클라우드 세션, 저장소 부착)로 옮겼다. 코워크 시절 핸드오프의 사실은 여기로 옮겼고, 로컬 윈도우 폴더·device_bash 경로는 더 쓰지 않는다.

## 0. 현재 상태 (2026-09-28)
- 루틴 정상 가동. 9/15~9/23 대부분 main 직접 반영. 9/21(PR #1)·9/28(PR #2)은 브랜치로 올라가 사람이 머지했다.
- PR #3 머지(`3848092`). 9/28 HOLD 원인(연휴 뒤 야간선물 부재)은 render.py `night_session_skipped()` 로 고쳤다. 9/14 에 고쳤다고 기록된 미국 휴장 시사 갭(`signals.us_holiday`)은 실제로 main 에 없어서 같이 넣었다. 10/6 회차부터 적용된다.
- 윈도우 로컬의 미push 커밋 `9474bce` 는 같은 수정이다. 로컬 폴더에서 `git fetch origin && git reset --hard origin/main` 으로 버린다(push 하면 충돌).

## 1. 루틴
| 항목 | 값 |
|---|---|
| 현행 | `trig_017rnKLpNdYfD3c61DqqmLPP` · enabled · 웹에서 생성(`created_via http_api`) |
| cron | `45 22 * * 0-4` UTC = 평일 07:45 KST (stagger 로 몇 분 늦을 수 있음) |
| 설정 | 저장소 charismak89/jisikin-jogan 부착 · 환경 Default, Network access **Full** · 커넥터 없음 · 모델 claude-opus-5-5 (9/22 변경) |
| 프롬프트 | 부트스트랩 5줄 = `TRIGGER-PROMPT.md`. 절차는 `RUNBOOK.md` |
| 비용 | 9/28 회차 약 $2.1 · 5분 (get_session usage 기준) |
| 구버전 | `trig_016XYcHaC8zkUPzByGAm4Eq7` 비활성. 이력 보존용, 삭제 금지 |
| BTC·ENA | `trig_01HPT262n5YqbxF94hEcZ2N7` 2026-09-01부터 비활성 |

결과물은 `out/index.html` · `out/state.json` · `out/calibration.json`. `GATE PASS` 면 `publish.py --push`(main, 거부 시 `claude/publish-<날짜>`), HOLD 면 `claude/hold-<날짜>`. 하니스가 붙인 `claude/<이름>-<접미사>` 브랜치에도 같은 커밋이 올라간다(머지 뒤 삭제 가능).
발행 주소: https://charismak89.github.io/jisikin-jogan/

## 2. Claude Code 에서 되는 것 / 안 되는 것
| 작업 | 방법 |
|---|---|
| 루틴 상태·최근 실행 | `list_triggers` → `last_run.session_id`(cse_…) |
| 회차 세션 상세 | `get_session` 에 `cse_…` 를 넣으면 된다(상태·브랜치·비용). 대화 본문은 웹 UI |
| 저장소 수정 | 세션 지정 브랜치에 커밋·push → PR → 머지(GitHub MCP) |
| 루틴 편집·Run now·저장소 부착·환경 | **웹 UI(claude.ai/code/routines)만.** `update_trigger`·`fire_trigger` 는 http_api 루틴에 안 먹힌다 |
| 원격 브랜치 삭제 | 세션에서 `git push --delete` 는 auto mode 권한 판정에 막힘(09-28 실측). 사람이 월 1회 정리(UPDATE.md). PR 머지 브랜치는 자동 삭제 |
| 코워크 세션 대화 | 여기서 조회 불가(세션 목록에서 빠짐) |

## 3. 회차 판독법
- `push 완료 (프록시 자격증명, main)` + SHA → 성공. 할 일 없음
- `브랜치 claude/publish-<날짜> — GitHub 에서 main 으로 merge 필요` → PR 만들어 머지
- `GATE HOLD — …` + `claude/hold-<날짜>` → diff 보고 머지 여부 결정. HOLD 사유는 `state.json` 의 `signals` 에 대부분 보인다
- push 전부 실패, 문구가 `not in this session's authorized repository set` → 루틴의 저장소 부착이 풀림. 웹 UI 에서 다시 붙인다
- 원인 추적: `git log origin/main --graph` 와 해당 커밋의 `state.json`

## 4. 게이트 (render.py 마지막 줄)
HOLD 조건: FAIL · 금지 표현/글자 초과 · 접힘 4,000자 초과 · 야간선물 미확보 · `data_note.diverged` > 2 · 발행일 ≠ 오늘.
시사 갭 예외 — EWY·SKHY 종가가 `state.closes` 와 똑같으면 미국 휴장으로 보고 그 시사 갭을 null 로 둔다(둘 다면 `signals.us_holiday: true`). 다음 해당일 11/27(추수감사절 다음 날).
야간선물 예외 — 직전 영업일과 발행일 사이에 `holidays.json` 휴장일이 끼면(`signals.night_skipped`) 경고만 남긴다. 해당 회차: 10/6 · 10/12 · 12/28 · 2027-01-04. 평범한 월요일은 금요일 밤 세션이 있어 예외 아님.

## 5. 예측 캘리브레이션
- score.py 규칙 고정: 보합 = |갭| ≤ 0.5%, hit = 방향 AND 구간. 09-01 기록 불일치(보합 −0.52% 가 hit)는 사람이 결정
- **규칙 동결.** 후보 `rule.center_signal="k200n"`, `half_width_pct`(잔차 p80, 없으면 1.5). 절차 `CALIBRATION.md`. 변경은 금요일 마감 뒤, 한 번에 한 변수

## 6. 데이터 소스
- 한국경제·stockanalysis·kr.investing·sonmul.co.kr 은 루틴(Network Full)에서 WebFetch 가능
- Google Finance 는 9/21 부터 WebFetch 에 `Your device isn't supported` 가 나온 적이 있다 → RUNBOOK 2단계 curl 폴백(`gf_*.html` 은 .gitignore)
- 야간선물(sonmul): 18:00 이전엔 주간 종가가 0.00% 로 찍힘 → null. 휴장 전날 밤에는 세션 자체가 없음
- 증권사 Open API 불가. 네이버·KRX·야후·stooq·FnGuide 차단
- 재배포 제약(미해결, 판단 보류): public GitHub Pages. KRX 이용약관 제12조 제2항. 완화책 noindex · "개인 학습용" · 출처 명시

## 7. 남은 할 일
1. 10/6 회차가 PASS 로 main 에 올라가는지 확인 — 10/6 08:30 KST 자동 확인 예약(`send_later`, `trig_01FMVJVNnpdG6wHou3GXPuds`)
2. 윈도우 로컬 `9474bce` 버리기(0절) — 사용자 수행, 세션에서 확인 불가 [검증필요]
3. ~~원격 claude/* 브랜치 정리 + "Automatically delete head branches"~~ 2026-09-28 완료(원격은 main 만, `delete_branch_on_merge: true`). 이후 월 1회 정리는 UPDATE.md
4. 임시공휴일 지정 시 `holidays.json` 에 추가
5. `template.html` · `fill.py`(v1 잔재) 삭제. 모델 변경 시험은 금요일 한 변수 규칙
6. 9/21 PR #1 이 main 거부 폴백이었는지 [검증필요]. 9/22·9/23 은 main 직접 push 가 됐으므로 "클라우드 세션은 main push 불가" 규칙(7ab4fbc)은 반영하지 않았다

## 8. 작업지시 방법
- 절차 → `RUNBOOK.md`. 사실·표기·금지 표현·이슈 범위 → `CONTEXT.md`. 휴장일 → `holidays.json`. 예측 규칙 → `calibration.json` 의 `rule`
- Claude Code 세션에 "RUNBOOK 에 X 반영해줘" 라고 지시 → 지정 브랜치 커밋 → PR → 머지. 루틴은 다음 회차에 main 을 clone 하므로 프롬프트를 고칠 필요 없다
- 급한 수동 발행은 여전히 윈도우 `publish.bat`(UPDATE.md)

## 이력
- 2026-09-14 v2 전환. 1차 Run now 는 환경 Trusted 라 EGRESS_BLOCKED, Network Full 로 바꾼 2차는 정상(기록상 last_run FAILED 17초는 불일치). 미국 휴장일 허위 시사 갭 결함을 찾았으나 수정이 main 에 들어가지 않았다(09-28 확인) → PR #3 에서 구현
- 2026-09-21 Google Finance WebFetch 차단 → 회차가 curl 우회, PR #1
- 2026-09-28 연휴 뒤 야간선물 null → HOLD → PR #2. 게이트 예외·curl 폴백을 main 반영(PR #3). 관리 주체 Claude Code 로 이전
