# 운영 핸드오프 (Claude Code 기준)

**새 세션이 먼저 읽을 파일.** 이 문서와 저장소(main), 루틴 조회(list_triggers)만 있으면 상태를 복원할 수 있다.
2026-09-28 에 관리 주체를 코워크에서 Claude Code(클라우드 세션, 저장소 부착)로 옮겼다. 코워크 시절 핸드오프의 사실은 여기로 옮겼고, 로컬 윈도우 폴더·device_bash 경로는 더 쓰지 않는다.
사람이 해야 할 작업 줄에는 확인 명령과 기대값을 같이 적는다. 다음 세션은 그 명령으로 확인하고 줄을 고친다(다른 세션 기록을 뒤지지 않는다).

## 0-5. 2026-10-21 중계기 루틴 연동 + 데이터 누락 점검 고리
- 루틴 턴 0 에 `fetch_relay.py` 추가. 토스 중계기 `/v1/daily` 로 직전 영업일 국내 6종 종가·시가(KRX 1분봉), 코스피·코스닥, 코스피 수급 4분류(확정치), 미국 4종, 15:30 환율을 `relay.json` 에 받는다. score.py·render.py 가 fill.json 빈칸을 채우고(입력 파일은 안 고침), 회차 값과 다르면 경고한다. 중계기가 죽으면 예전 웹 경로 그대로.
- 근거: 9/15~10/21 회차 기록에서 기타법인 수급은 23회 모두, 개인 수급 4회, 코스닥 2회, 종목 시가 2회 빠졌다. 중계기는 이 전부를 준다. 10/21 회차 입력에 합쳐 재현하면 누락 0건, 빠졌던 10/20 종목 채점도 된다.
- 사후 채점: 10/16·10/20 종목 전망(시가 누락으로 빠짐)을 중계기 KRX 시가로 `stock_records` 에 넣었다(`source` 에 사후 채점 표시).
- 기록·점검: render.py 가 회차마다 `datalog.json` 에 누락·중계기 보완·불일치를 한 줄 남긴다(9/15 이후 23회는 backfill). 다음 회차 턴 0 에 연속 누락 필드와 다음 경로(`sources.json`)를 출력하고 회차가 1회 더 시도한다. 토요일 주간 점검 2-1 이 `datacheck.py` 로 반복 누락 필드를 골라 대안 경로를 시험하고 제안한다(사용자 승인 뒤 반영).
- **VM 갱신 완료(2026-10-21 14:23 KST 확인)**: 루틴 키로 `/v1/calendar` 200(키 없이는 401), `/v1/daily` 에 `fx_close`·`stock_flow` 가 붙고 미국 일봉이 `us_until` 전날까지 온다(10/16 NVDA 214.13 회차 값과 일치). 키 없는 `/v1/live` 는 그대로 200.
- 미국 일봉 종가(10/22 확인): 애프터마켓 가격은 아니다. 다만 공식 종가와 소수점 차이가 난다 — 10/21 NVDA 221.86(공식 221.97)·MU 913.62(913.67), EWY·SKHY 는 일치. 10/22 회차가 fetch_relay 출력의 "1순위로 쓴다" 문구를 따라 미국 종가도 토스 값을 썼다. 문구를 "미국·환율은 대조용" 으로 고쳤고, state.json 의 NVDA·MU 기준값을 공식 종가로 바로잡았다(10/23 등락률 계산용).
- 10/22 첫 연동 회차: 중계기 OK · 데이터 누락 0건 · 경고 0건 · GATE PASS. 10/21 코스피·삼전·하닉 시가 채점 모두 구간 안. 회차가 중계기 값을 fill.json 에 직접 적어 `relay_filled` 는 0건.
- 미해결: 토스 수급 확정치와 기사 수급이 10/20 에 크게 갈렸다. KRX 정보데이터시스템 한 날 대조 [검증필요]. 토스 15:30 매매기준율이 서울 외환시장 종가와 얼마나 다른지 [검증필요] — 그래서 환율은 빈칸일 때만 채운다.

## 0-1. v5 화면 (2026-10-15)
- 첫 화면이 대시보드다. 전망·결론 3줄(TL;DR 제목) → 예측 → 실시간(코스피·삼전·하닉) → 코스피 20거래일 예측 기록 → 간밤 시장. 브리핑은 두 번째 탭(`#brief`)이고 본문은 v4 와 글자까지 같다.
- 새 파일: `fetch_perp.py`(해외 24시간 추종가 → `perp.json`, .gitignore) · `template-v5.html`. render.py 의 TEMPLATE 이 v5 를 가리킨다. **되돌리기: render.py 의 TEMPLATE 한 줄을 template-v4.html 로.** v4 템플릿·로직은 그대로 남아 있다(대시보드용 값은 v4 템플릿에 자리가 없어 무시된다).
- 실시간 값은 브라우저가 Hyperliquid info API 를 직접 15초마다 부른다(서버 없음). 장중 값은 KRX 연동 추종가라 실제가와 ±0.5% 안팎 차이(CONTEXT.md). 지난 회차 페이지는 그날 기록을 한 번만 다시 받는다(1분봉 3일·5분봉 16일·15분봉 50일 보관).
- 종목 예측 구간(삼전·하닉)은 `calibration.json` `stock_rule` 로 render.py 가 계산, 다음 회차 score.py 가 `stock_records` 에 채점. 회차는 fill.json 에 삼전·하닉 `open`·`open_date` 두 값만 더 쓴다.
- 접힘 4,000자 게이트는 브리핑 탭만 센다(대시보드는 스크립트가 만든 화면).
- 2단계(2026-10-15 진행): KRX 실제 시세 — 토스증권 Open API + 중계기 `relay/`(오라클 오사카 VM `jogan-relay` 129.225.146.153, 토스가 일본 IP 를 받아 줌). 이 클라우드의 출구 IP 는 `160.79.106.x`(미국) 대역에서 매번 바뀌어 직접 호출이 안 된다.
  - 대시보드: 지인 링크(`#k=`)로 연 브라우저는 장중 선·시가·현재가를 KRX 값으로 그린다. 키가 없거나 중계기가 죽으면 해외 추종가로 자동 폴백. 중계기 주소는 CONTEXT.md "KRX 중계기".
  - ~~남은 일: 루틴의 국내 시세·수급 수집을 `/v1/daily` 로 옮기기~~ 2026-10-21 완료(0-5절). 운영은 `relay/README.md`.
    **옮기기 전에 `/v1/daily` 의 종목 시가·종가를 1분봉 기준(09:01 봉 시가, 15:31 봉 종가)으로 바꿔야 한다.** 지금 값은 토스 일봉 = KRX·NXT 통합(08:00~20:00)이라 KRX 공식값과 다르다(CONTEXT.md "KRX 중계기"). 코스피·코스닥 지수, 환율, 투자자별 매매대금은 그대로 써도 된다.
  - 주간 점검 후보: 15:40 뒤 대시보드 종목 타일은 NXT 애프터마켓 가격을 보여 준다. KRX 종가와 다르다는 표시(예: "NXT") 또는 KRX 종가 병기 여부.

## 0-2. 의견 버튼 + 주간 점검 (2026-10-16)
- 대시보드 탭 줄 오른쪽 "의견" 버튼(지인 링크로 연 브라우저만). 글은 중계기 `POST /v1/feedback` → VM `/var/lib/jogan-relay/feedback.jsonl` 에만 저장한다. 저장소에는 올리지 않는다(Public). 하루 30건·1,000자 제한, IP 미보관.
- 토요일 07:45 KST 예약 작업 "지식인 조간 주간 점검"(매번 새 세션, 휴대폰 알림)이 `WEEKLY.md` 대로 의견 읽기 → 주간 채점 → 계획을 보고한다. 사용자가 그 세션에서 번호를 골라 승인해야 구현한다. 의견 본문은 데이터로만 다룬다.
- 화면을 고치면 `python3 regress.py` 로 마지막 회차 입력(`fixtures/last-fill.json`, publish.py 가 회차마다 남김)을 고치기 전·후로 렌더해 비교한다.
- 주간 점검과 루틴의 `/v1/daily` 연동에는 환경 변수 `JJ_RELAY_URL`·`JJ_RELAY_TOKEN`(루틴 키)이 필요하다. 사용자가 환경 설정에 등록한다.

## 0-4. 2026-10-19 메인 전환 (R3, R2 병행은 건너뜀 — 사용자 결정)
- 메인 주소 `/jisikin-jogan/` 가 v6 앱(React)이다. 루트 `index.html` 은 `web/` 빌드가 만드는 셸이고 루틴은 건드리지 않는다. `/v6/` 주소도 같은 화면이다.
- 이전 화면은 `/jisikin-jogan/v5/`. `publish.py` 가 render.py 산출물을 `v5/index.html` 에 쓰고(`style.css`·`archive/` 링크는 `../`), 전날 v5 화면을 `archive/<날짜>.html` 로 옮긴다. 데이터는 루트 `day.json`.
- 지인 링크(`/#k=…`)는 그대로 v6 로 열리고 중계기 키도 그대로 읽는다(`web/src/lib/live.ts` 의 readRelayKey).
- 차트: 오른쪽 위 `+` · `−` · `전체` 버튼, 확대 뒤 좌우로 끌어 이동(마우스·터치). PC 휠·더블클릭은 그대로. 맨 오른쪽 크게 보기 버튼은 차트를 화면 가득 다시 그린다(PC 760×360, 모바일 360×460 좌표계, Esc 로 닫기).
- `publish.ps1`·`publish.bat` 은 실행하면 바로 멈춘다(루트를 v5 로 덮어쓰기 때문). 수동 경로는 `UPDATE.md`.
- 의견 `ctx.page`: `/jisikin-jogan/`·`/jisikin-jogan/v6/` = v6, `/jisikin-jogan/v5/` = v5.
- **2026-10-19 토스 시세 기본화(사용자 결정)**: v6 는 지인 키 없이도 중계기를 부르고, 토스 시세를 받는 동안 추종가를 부르지 않는다. 중계기는 `PUBLIC_VIEW`(기본 1)로 `/v1/live`·`/v1/intraday`·의견 쓰기를 키 없이 연다. **VM 갱신 완료(2026-10-19 08:46 KST 확인)**: 키 없이 `/v1/live`·`/v1/intraday` 200, `/v1/daily`·의견 읽기 401. 새 브라우저(키 없음)로 메인을 열면 상태 KRX, Hyperliquid 호출 0건. 다시 잠그기: env 에 `PUBLIC_VIEW=0`.
- 되돌리기: 전환 PR 을 revert(`web/README.md`).

## 0-3. 2026-10-17 주간 점검 반영
- 대시보드 차트 PC 휠 확대·드래그·더블클릭 초기화(의견 1건). 장 마감 뒤 종목 종가가 KRX 기준임을 문구로 표시.
- 중계기 `/v1/daily` 국내 종목 시가·종가를 1분봉 기준 KRX 값으로 변경(`src`·`complete`·`nxt_open`·`nxt_close`). **VM 갱신 완료(2026-10-18, PR #19 `complete` 수정 포함).** 주간 점검 세션이 `/v1/daily` 로 10/16 값을 받아 6종 시가·종가가 KRX 1분봉 기준과 맞는 것을 확인했다. `complete` 는 4종 true, ETF 2종(0167A0·442580)은 false — 시가·종가 1분봉에 체결이 없던 것으로 추정 [검증필요], 값은 통합 일봉과 같았다. 이제 루틴 연동(남은 일)을 시작할 수 있다. 연동 때 `complete: false` 종목은 Google Finance 와 대조한 뒤 쓴다.
- R0: render.py 가 `out/day.json` 도 쓰고 publish.py 가 루트 `day.json` 으로 반영(첫 반영은 다음 평일 회차). R1: `web/` 앱을 빌드해 `v6/` 에 커밋(`web/README.md`). 병행(R2)은 `/jisikin-jogan/v6/` 를 지인에게 같이 보내며 시작, 의견 `ctx.page` 로 v5·v6 구분. `regress.py` 는 `fixtures/` 가 없어 이번엔 합성 입력으로 시험했다. 10/19 발행부터 `fixtures/last-fill.json` 이 저장소에 있다. 루트 `day.json` 첫 반영도 10/19 회차(제42호).

## 0. 현재 상태 (2026-09-28)
- 루틴 정상 가동. 9/15~9/23 대부분 main 직접 반영. 9/21(PR #1)·9/28(PR #2)은 브랜치로 올라가 사람이 머지했다.
- PR #3 머지(`3848092`). 9/28 HOLD 원인(연휴 뒤 야간선물 부재)은 render.py `night_session_skipped()` 로 고쳤다. 9/14 에 고쳤다고 기록된 미국 휴장 시사 갭(`signals.us_holiday`)은 실제로 main 에 없어서 같이 넣었다. 10/6 회차부터 적용된다.
- 윈도우 로컬의 미push 커밋 `9474bce` 는 같은 수정이다. 로컬 폴더에서 `git fetch origin && git reset --hard origin/main` 으로 버린다(push 하면 충돌).

## 1. 루틴
| 항목 | 값 |
|---|---|
| 현행 | `trig_017rnKLpNdYfD3c61DqqmLPP` · enabled · 웹에서 생성(`created_via http_api`) |
| cron | `45 22 * * 0-4` UTC = 평일 07:45 KST (stagger 로 몇 분 늦을 수 있음) |
| 설정 | 저장소 charismak89/jisikin-jogan 부착 · 환경 Default, Network access **Full** · 커넥터 없음 · 모델 **claude-opus-5-5 고정**(2026-10-22 사용자 — 평일 회차·토요일 주간 점검 모두). 10/16~10/22 사이 기본값이었고 그때 10/21·10/22 회차는 Sonnet 5.5 로 돌았다 |
| 프롬프트 | 부트스트랩 5줄 = `TRIGGER-PROMPT.md`. 절차는 `RUNBOOK.md` |
| 비용 | 9/28 회차(Opus) 약 $2.1 · 5분 · 10/21(Sonnet) $0.67 · 약 2분 · 10/22(Sonnet) $0.49 · 약 1.5분 (get_session usage 기준) |
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
- score.py 채점: hit = 실제 시초가가 구간 안(목표 80%). **2026-10-21 방향 3분류(갭상승·보합·갭하락) 폐지** — 전망에서도 `dir` 를 뺐고 기존 records 39건을 다시 계산했다(miss→hit 8건, `CALIBRATION.md`·`calibration.json` `metric.history`)
- **2026-10-02 후보 2 적용**: 구간 중심 = 야간선물. 첫 적용 10/7. 반폭은 10/16 회차까지 0.8% 고정, **10/19 회차부터 비례 0.44 × (1 + |야간|)**(2026-10-16 사용자 결정, `rule.half_width_mode="scaled"`). 휴장 뒤 회차(10/12·12/28·1/4)는 score.py 가 강제 폴백(10/6 묵은 야간선물 실측). 롤백 기준은 `CALIBRATION.md` 지금 상태(고정 0.8 반사실보다 낮으면 fixed 로)
- **롤백 판정 예약**: 2026-11-06(금) 16:00 KST, 이 관리 세션에 `send_later`(`trig_01DUKEdCqsSk46dk5AVGpyqD`). 기준은 위 비례 반폭 롤백 기준(10/19~10/30 10회, 비례 커버 vs 고정 0.8 반사실). 옛 예약 `trig_01Ucfe3tE4bWZmjxELUhf6YA`(반폭 0.8 고정·8/10 기준, 다른 세션)는 지시문을 이 세션에서 고칠 수 없어 꺼 두었다(삭제 안 함).
- 진단·재계산: `python3 analyze.py`. 변경은 금요일 마감 뒤, 한 번에 한 변수. 다음 후보는 야간 ×0.8, 그다음 미국 지수선물(10/2 부터 기록)

## 6. 데이터 소스
- 한국경제·stockanalysis·kr.investing·sonmul.co.kr 은 루틴(Network Full)에서 WebFetch 가능
- Google Finance 는 9/21 부터 WebFetch 에 `Your device isn't supported` 가 나온 적이 있다 → RUNBOOK 2단계 curl 폴백(`gf_*.html` 은 .gitignore)
- 미국 지수선물(ES·NQ): kr.investing.com 선물 페이지, WebFetch 로만 된다(curl 403). 2026-10-02 회차부터 `signals.es_pct`·`nq_pct` 기록 전용. 전망·게이트에 쓰지 않는다(CALIBRATION 후보 3)
- 야간선물(sonmul): 18:00 이전엔 주간 종가가 0.00% 로 찍힘 → null. 휴장 전날 밤에는 세션 자체가 없음
- 증권사 Open API 불가. 네이버·KRX·야후·stooq·FnGuide 차단
- 재배포 제약(미해결, 판단 보류): public GitHub Pages. KRX 이용약관 제12조 제2항. 완화책 noindex · "개인 학습용" · 출처 명시

## 7. 남은 할 일
1. ~~10/6 회차가 PASS 로 main 에 올라가는지 확인~~ 2026-10-06 완료: GATE PASS · main 직접 반영(`54db032`) · 사이트 반영 · ES/NQ 수집 확인. 휴장 뒤 묵은 야간선물 문제는 score.py 강제 폴백으로 처리
2. 윈도우 로컬 `9474bce` 버리기(0절) — 사용자 수행, 세션에서 확인 불가 [검증필요]
3. ~~원격 claude/* 브랜치 정리 + "Automatically delete head branches"~~ 2026-09-28 완료(원격은 main 만, `delete_branch_on_merge: true`). 이후 월 1회 정리는 UPDATE.md
4. 임시공휴일 지정 시 `holidays.json` 에 추가. 2026-10-21 부터 fetch_relay.py 가 토스 장 달력과 holidays.json 이 다르면 `달력` 줄로 알린다(VM 갱신 뒤)
5. `template.html` · `fill.py`(v1 잔재) 삭제. v5 가 안정되면 `template-v4.html` 도 같은 처리. 모델 변경 시험은 금요일 한 변수 규칙
6. 9/21 PR #1 이 main 거부 폴백이었는지 [검증필요]. 9/22·9/23 은 main 직접 push 가 됐으므로 "클라우드 세션은 main push 불가" 규칙(7ab4fbc)은 반영하지 않았다
7. ~~첫 주간 점검(10/17)에서 코스피 반폭 판단~~ 2026-10-16 사용자 결정 — 비례 반폭(`DIRECTION.md` A1). `calibration.json` rule `half_width_mode=scaled`·`half_width_q=0.44`, `score.py` 의 `half_width()`. 고정 0.8 은 적용 뒤 5회(폴백 10/12 제외) 중 3회 구간 밖이었다. 주간 점검은 `analyze.py` "현행 규칙 점검" 줄만 보고, 10회 쌓이기 전에는 판정하지 않는다
8. **개선 백로그는 `DIRECTION.md` 6절**(2026-10-16 벤치마킹: 나박AI·PRISM-INSIGHT·유사 서비스). 주간 점검이 계획을 쓸 때 이 번호(A1·B1·C1 …)로 후보를 고른다. 정체성·안 하는 일은 같은 문서 4·7절. 결정된 것은 같은 문서 0절 "결정 기록"(A1 비례 반영, E3 지인 KRX 실시간 유지)
9. **10/17 주간 점검 안건 — UI 개편.** 사용자 요청: 토스결·업비트결, PC 브라우저 대응, TDS·shadcn/ui·StyleSeed 검토. 검토 결과와 단계안은 `DIRECTION.md` 9절. 추천은 React 전환 R안(R0 `render.py` 가 `out/day.json` 추가 출력 → R1 `web/` v6 앱을 `/v6/` 에 → R2 병행 2주 → R3 루트 전환, 루틴은 그대로). **R0·R1 10/17, R3 10/19 완료(R2 건너뜀, 0-4절).** 대안은 U안(정적 유지 + 토큰 교체). TDS 는 라이선스상 불가. 지인 의견의 UI 건과 `ctx.w`(1024px 이상 비율)를 같이 보고 계획에 올린다. 지난 회차 HTML 이 `../style.css` 를 공유하니 새 화면은 새 클래스·새 스타일시트로

## 8. 작업지시 방법
- 절차 → `RUNBOOK.md`. 사실·표기·금지 표현·이슈 범위 → `CONTEXT.md`. 휴장일 → `holidays.json`. 예측 규칙 → `calibration.json` 의 `rule`
- Claude Code 세션에 "RUNBOOK 에 X 반영해줘" 라고 지시 → 지정 브랜치 커밋 → PR → 머지. 루틴은 다음 회차에 main 을 clone 하므로 프롬프트를 고칠 필요 없다
- 급한 수동 발행은 여전히 윈도우 `publish.bat`(UPDATE.md)

## 이력
- 2026-09-14 v2 전환. 1차 Run now 는 환경 Trusted 라 EGRESS_BLOCKED, Network Full 로 바꾼 2차는 정상(기록상 last_run FAILED 17초는 불일치). 미국 휴장일 허위 시사 갭 결함을 찾았으나 수정이 main 에 들어가지 않았다(09-28 확인) → PR #3 에서 구현
- 2026-09-21 Google Finance WebFetch 차단 → 회차가 curl 우회, PR #1
- 2026-09-28 연휴 뒤 야간선물 null → HOLD → PR #2. 게이트 예외·curl 폴백을 main 반영(PR #3). 관리 주체 Claude Code 로 이전
