# 지식인 조간

반도체·메모리 모닝 대시보드. GitHub Pages로 서빙합니다. 평일 07:45 KST 예약작업이 만듭니다.

배포 주소: https://charismak89.github.io/jisikin-jogan/ (v6 화면, 2026-10-19 부터) · 이전 화면: https://charismak89.github.io/jisikin-jogan/v5/

## 구조 (v2 · 2026-09-15, 화면 v5 · 2026-10-15)

| 경로 | 역할 | 손대는 사람 |
|---|---|---|
| `HANDOFF.md` | 운영 상태·루틴 설정·남은 할 일. 새 관리 세션이 먼저 읽는다 | 사람 |
| `RUNBOOK.md` | 회차 절차. 예약작업 프롬프트는 이 파일을 clone 해 읽는다 | 사람 |
| `WEEKLY.md` | 토요일 주간 점검 절차(지인 의견 + 주간 채점 → 계획 → 승인 뒤 구현) | 사람 |
| `CONTEXT.md` | 종목 사실·표기명·소스 우선순위·금지 표현·이슈 수집 범위 | 사람 |
| `CALIBRATION.md` / `calibration.json` | 채점 규칙·기록. records 는 score.py 가 append | score.py |
| `holidays.json` | 휴장일. 임시공휴일이 생기면 한 줄 추가. 휴장 다음 회차의 야간선물 게이트 면제도 이 파일로 판정 | 사람 |
| `template-v5.html` / `style.css` | 뼈대와 디자인. 첫 화면 대시보드 + 브리핑 탭 (인라인 CSS 와 style.css 는 같은 내용) | 사람 |
| `template-v4.html` | v4 뼈대. 되돌릴 때 render.py 의 TEMPLATE 한 줄만 바꾼다 | — |
| `fetch_perp.py` | 해외 24시간 추종가(Hyperliquid) → `perp.json`. 대시보드 장외 구간·종목 예측 입력 | — |
| `relay/` | 토스증권 Open API 중계기(오라클 VM 에서 돈다). 설치·운영은 `relay/README.md` | 사람(VM) |
| `render.py` | fill.json → `out/index.html` · `out/state.json` · `out/calibration.json` | — |
| `score.py` | 직전 전망 채점 → calibration.json append | — |
| `publish.py` | 아카이브·목록·링크 정리 + 커밋 + push (예약 세션용). 회차 입력을 `fixtures/` 에 남긴다 | — |
| `regress.py` / `fixtures/` | 렌더 회귀 검사. 마지막 회차 입력으로 고치기 전·후를 렌더해 비교 | — |
| `publish.bat` / `publish.ps1` | 옛 수동 발행. 2026-10-19 메인 전환 뒤 실행하면 바로 멈춘다(루트 index.html 을 v5 로 덮어쓰기 때문) | — |
| `web/` / `v6/` | v6 화면(React) 소스와 빌드 산출물. `cd web && npm ci && npm run build` 가 `v6/` 와 루트 `index.html` 을 함께 만든다(`web/README.md`) | 사람(UI 바꿀 때만) |
| `day.json` | v6 화면이 읽는 오늘자 데이터. render.py → publish.py | publish |
| `state.json` | 회차 간 인수인계 (직전 전망·직전 종가·신호) | render.py |
| `index.html` | 메인 = v6 앱 셸. 루틴은 건드리지 않는다 | web 빌드 |
| `v5/index.html` / `archive/` | 오늘자 v5 화면 · 지난 회차(v5) | publish |
| `template.html` / `fill.py` | v1 잔재. v2 가 안정되면 삭제 | — |

## 발행 경로
- 자동: 예약 세션이 `render.py` 검증(`GATE PASS`)을 통과하면 `publish.py --push` 로 바로 올린다. 토큰은 비공개 Notion 페이지 `jisikin-jogan deploy token` 에서 읽는다.
- 수동(폴백): `publish.bat` 은 2026-10-19 뒤로 쓰지 않는다. GATE HOLD 는 `claude/hold-<날짜>` 브랜치를 머지하고, push 가 전부 실패하면 루틴 저장소 부착을 고친 뒤 Run now(UPDATE.md).

## 최초 1회 설정
```bash
git init -b main
git remote add origin https://github.com/charismak89/jisikin-jogan.git
git add -A && git commit -m "init"
git push -u origin main
```
GitHub → Settings → Pages → Source: `Deploy from a branch`, Branch: `main` / `(root)`.

## 주의
이 저장소는 Public 입니다. 대시보드 외의 파일(작업 파일·토큰)은 두지 마세요. `fill.json` · `perp.json` · `out/` 은 .gitignore 로 막혀 있습니다.
