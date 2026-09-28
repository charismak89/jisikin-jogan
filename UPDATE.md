# 매일 아침 갱신하는 법 (v2)

2026-09-28 부터 저장소 관리는 Claude Code 세션이 맡는다. 운영 상태·루틴 설정은 `HANDOFF.md`.

## 평소 — 아무것도 안 함
예약 세션이 검증을 통과하면 알아서 커밋·push 합니다. 세션 응답에 `push 완료` 와 커밋 SHA 가 찍힙니다.
1~2분 뒤 https://charismak89.github.io/jisikin-jogan/ 에 반영됩니다.

## Claude Code 에 맡기는 일 / 사람만 하는 일
| 일 | 누가 |
|---|---|
| RUNBOOK·CONTEXT·holidays.json 수정 (임시공휴일은 날짜만 알려 주면 됨) | Claude Code 세션 — 수정 → PR → 머지 |
| 회차 결과 확인·HOLD 원인 분석 ("오늘 회차 봐줘") | Claude Code 세션 |
| 브랜치로 올라온 회차 PR 머지 | Claude Code 세션 또는 사람(아래) |
| 루틴 편집·Run now·저장소 부착·Network access | **사람, 웹 UI(claude.ai/code/routines)에서만** |
| 원격 브랜치 삭제 | **사람** (세션 권한으로 막혀 있음, 아래) |
| 윈도우 로컬 폴더 정리·publish.bat | **사람** |

루틴 보고에 `not in this session's authorized repository set` 이 보이면 루틴의 저장소 부착이 풀린 것입니다. 루틴 편집 화면 → Repositories 에서 `charismak89/jisikin-jogan` 을 다시 붙이세요.

## 회차가 브랜치로 올라왔을 때 — PR 머지
세션 보고 첫 줄이 `브랜치 claude/publish-<날짜> — GitHub 에서 main 으로 merge 필요` 또는 `GATE HOLD — … claude/hold-<날짜>` 인 경우입니다. 브랜치에만 있는 동안 사이트는 직전 회차를 보여 줍니다.
1. https://github.com/charismak89/jisikin-jogan 을 열면 노란 띠에 **Compare & pull request** 가 보입니다. 누르고 **Create pull request**
2. HOLD 면 Files changed 탭에서 `state.json` 의 `signals` 와 HOLD 사유를 보고 괜찮을 때만 진행
3. **Merge pull request** → **Confirm merge**. 브랜치는 자동으로 지워집니다(저장소 설정 "Automatically delete head branches" 켜짐)
- Claude Code 세션에 "오늘 회차 브랜치 머지해줘" 라고 해도 됩니다.

## 세션이 "publish.bat 을 실행하면 반영됩니다" 라고 하면 — 수동 발행
자동 발행 게이트(`GATE HOLD`)에 걸렸거나 push 가 전부 실패했을 때입니다. publish.bat 전에 아래 "로컬 폴더를 main 에 맞추기" 의 1~2단계로 폴더 상태부터 확인하세요.
1. 세션이 보낸 `index.html` · `calibration.json` · `state.json` 세 개를 **다운로드 폴더에 저장**
2. 리포 폴더의 **`publish.bat` 더블클릭** → `발행 완료!`
   - 세션이 자동 발행에 성공한 날에는 publish.bat 을 돌리지 마세요. 돌려도 발행일 검사와 원격 pull 이 막아 주지만, 같은 회차가 두 번 커밋될 수 있습니다.

스크립트가 대신 해주는 일: 어제 `index.html` 을 `archive/<어제날짜>.html` 로 복사(CSS 경로 수정), 목록 갱신, 새 파일 교체, 커밋 + 푸시.

## 잘못 발행됐을 때 — 롤백
리포 폴더에서 `git revert HEAD` 한 줄이면 직전 상태로 돌아갑니다(아카이브는 git 이력에 그대로 있습니다). 터미널이 없으면 VS Code 소스 제어에서 마지막 커밋을 되돌리세요.

## 아카이브가 빠졌을 때 (복구 모드)
다운로드 폴더에 새 `index.html` 이 없는 상태로 `publish.bat` 을 실행하면 **"아카이브 점검/복구만 실행할까요?"** 라고 묻습니다. `y` 를 누르면 git 이력을 훑어 빠진 회차를 되살리고 목록을 다시 만듭니다. 저장소 파일(CONTEXT.md 등)만 고쳐 올릴 때도 이 모드를 씁니다.

## 로컬 폴더를 main 에 맞추기
윈도우 폴더에 push 안 된 커밋이 남아 main 과 갈라졌을 때 씁니다(예: 2026-09-28 의 `9474bce`). 이 상태로 publish.bat·`git push` 를 돌리면 충돌합니다.
1. PowerShell 에서 `cd "$HOME\Documents\jisikin-jogan"`
2. `git status` — `nothing to commit, working tree clean` 이 아니면 멈추고 Claude Code 세션에 화면을 보여 줄 것
3. `git branch backup-<오늘날짜>` — 지금 상태를 백업 브랜치로 남긴다
4. `git fetch origin --prune` 다음 `git reset --hard origin/main`
5. `git log --oneline -1` 이 GitHub main 의 최신 커밋과 같으면 끝. 백업 브랜치는 다음 회차가 정상이면 `git branch -D backup-<날짜>`

## 브랜치 정리 — 한 달에 한 번
루틴은 main 에 직접 발행한 날에도 `claude/<이름>-<접미사>` 브랜치를 하나씩 남깁니다. PR 로 머지한 브랜치만 자동 삭제되므로 가끔 모아서 지웁니다. **머지 대기 중인 publish·hold 브랜치가 없을 때만** 하세요.
- 웹: https://github.com/charismak89/jisikin-jogan/branches → `claude/` 로 시작하는 브랜치의 휴지통 아이콘
- PowerShell 한 번에:
```
git fetch origin --prune
git branch -r | Select-String 'origin/claude/' | ForEach-Object { git push origin --delete ($_.ToString().Trim() -replace '^origin/','') }
git fetch origin --prune; git branch -r
```
마지막 줄 결과가 `origin/main` 하나면 끝입니다.

## 규칙·사실을 고칠 때
Claude Code 세션에 말로 지시하면 수정·PR·머지까지 합니다. 파일 위치는 아래와 같습니다.
- 종목 사실·표기·소스·금지 표현·이슈 범위 → `CONTEXT.md`
- 절차 → `RUNBOOK.md` (예약작업 프롬프트를 바꿀 필요 없음)
- 휴장일 → `holidays.json`
- 예측 규칙 → `calibration.json` 의 `rule` (금요일에만, 한 변수만, `CALIBRATION.md` 절차대로)

## 호수
2026-08-21 을 제1호로 둔 **평일 일련번호**입니다. 휴장일도 번호를 차지하므로 연휴 뒤에는 번호가 건너뜁니다. `render.py` 와 `publish.py` 가 같은 식으로 계산합니다.
