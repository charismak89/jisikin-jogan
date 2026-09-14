# 예약작업(루틴) 프롬프트 (부트스트랩 · v2)

루틴 「지식인 조간 — 반도체 모닝 대시보드 (평일 07:45)」 의 프롬프트는 아래 전문이다. 절차는 저장소의 `RUNBOOK.md` 에 있으므로 프롬프트를 다시 고칠 일은 거의 없다.
자동 발행(push)은 루틴에 저장소 `charismak89/jisikin-jogan` 이 붙어 있어야 된다 (claude.ai/code/routines → 루틴 편집 → Repositories). 클라우드 세션의 git 프록시는 개인 토큰을 통과시키지 않는다.

```
평일 07:45 KST 「지식인 조간」 반도체·메모리 모닝 대시보드 발행 작업이다. 확인 질문을 받아줄 사람이 없으니 애매하면 가정을 명시하고 진행한다.

1. 현재 디렉터리에 RUNBOOK.md 가 있으면 여기가 저장소다. 없으면 `git clone --depth 1 https://github.com/charismak89/jisikin-jogan.git repo && cd repo`.
   clone 도 안 되면 `curl -sSf -o RUNBOOK.md https://raw.githubusercontent.com/charismak89/jisikin-jogan/main/RUNBOOK.md`
2. RUNBOOK.md 를 읽고 그대로 수행한다. RUNBOOK.md 가 이 프롬프트보다 우선한다.
3. RUNBOOK.md 를 받지 못하면 "RUNBOOK.md 없음 — 발행 생략" 한 줄만 남기고 종료한다.
4. 토큰 규칙 — template·calibration·archive 를 열지 않는다. index.html 을 직접 쓰지 않는다(fill.json 만). 시세 WebFetch 는 한 턴에 병렬로. 스크린샷 금지.
5. routine-fire-payload 에 "테스트" 가 있으면 RUNBOOK 8단계에서 push 하지 않고 dry-run 결과만 보고한다.
```

테스트 실행: 루틴 페이지의 Run now 에 `테스트 — push 하지 말고 dry-run 결과만 보고` 를 넣거나, fire_trigger 의 text 에 같은 문장을 넣는다.
