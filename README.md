# 지식인 조간

반도체·메모리 모닝 대시보드. GitHub Pages로 서빙합니다. 평일 07:45 KST 예약작업이 만듭니다.

배포 주소: https://charismak89.github.io/jisikin-jogan/

## 구조 (v2 · 2026-09-15)

| 경로 | 역할 | 손대는 사람 |
|---|---|---|
| `RUNBOOK.md` | 회차 절차. 예약작업 프롬프트는 이 파일을 clone 해 읽는다 | 사람 |
| `CONTEXT.md` | 종목 사실·표기명·소스 우선순위·금지 표현·이슈 수집 범위 | 사람 |
| `CALIBRATION.md` / `calibration.json` | 채점 규칙·기록. records 는 score.py 가 append | score.py |
| `holidays.json` | 휴장일. 임시공휴일이 생기면 한 줄 추가 | 사람 |
| `template-v4.html` / `style.css` | 뼈대와 디자인 (인라인 CSS 와 style.css 는 같은 내용) | 사람 |
| `render.py` | fill.json → `out/index.html` · `out/state.json` · `out/calibration.json` | — |
| `score.py` | 직전 전망 채점 → calibration.json append | — |
| `publish.py` | 아카이브·목록·링크 정리 + 커밋 + push (예약 세션용) | — |
| `publish.bat` / `publish.ps1` | 수동 발행 (다운로드 폴더의 세 파일을 반영) | — |
| `state.json` | 회차 간 인수인계 (직전 전망·직전 종가·신호) | render.py |
| `index.html` / `archive/` | 오늘자 · 지난 회차 | publish |
| `template.html` / `fill.py` | v1 잔재. v2 가 안정되면 삭제 | — |

## 발행 경로
- 자동: 예약 세션이 `render.py` 검증(`GATE PASS`)을 통과하면 `publish.py --push` 로 바로 올린다. 토큰은 비공개 Notion 페이지 `jisikin-jogan deploy token` 에서 읽는다.
- 수동(폴백): 세션이 보낸 `index.html` · `calibration.json` · `state.json` 을 다운로드 폴더에 두고 `publish.bat` 실행.

## 최초 1회 설정
```bash
git init -b main
git remote add origin https://github.com/charismak89/jisikin-jogan.git
git add -A && git commit -m "init"
git push -u origin main
```
GitHub → Settings → Pages → Source: `Deploy from a branch`, Branch: `main` / `(root)`.

## 주의
이 저장소는 Public 입니다. 대시보드 외의 파일(작업 파일·토큰)은 두지 마세요. `fill.json` 과 `out/` 은 .gitignore 로 막혀 있습니다.
