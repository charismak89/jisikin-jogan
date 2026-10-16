# jogan-relay — 토스증권 Open API 중계기

대시보드(지인 브라우저)와 07:45 루틴이 KRX 실제 시세를 받도록 토스 Open API 를 대신 부른다.
토스는 허용 IP 에서만 호출되고, 토큰은 클라이언트당 1개만 유효하다(새로 발급하면 직전 토큰 즉시 무효). 그래서 토큰은 여기서만 발급한다.

- 서버: 오라클 오사카 VM `jogan-relay` (129.225.146.153), Ubuntu, 상시 무료 E2.1.Micro
- 주소: `https://129-225-146-153.sslip.io` (Caddy 가 인증서 자동 발급)
- 코드: `jogan_relay.py` (표준 라이브러리만, 127.0.0.1:8787) · 설치: `install.sh`

## 설치 (처음 한 번)
VM 에 SSH 로 접속해서:
```bash
git clone https://github.com/charismak89/jisikin-jogan.git ~/jisikin-jogan
cd ~/jisikin-jogan && sudo bash relay/install.sh
```
- 토스 `client_id`·`client_secret` 을 묻는다(화면에 안 보임). 키는 `/etc/jogan-relay.env`(root, 600)에만 저장된다.
- 지인 키·루틴 키를 새로 만들고, 마지막에 **지인 공유 링크**와 **루틴용 값**을 출력한다. 이 화면에서만 보여 준다. 채팅·저장소에 붙이지 않는다.
- 포트 80·443 이 열려 있어야 인증서가 붙는다(NSG `relay-web` + VM iptables).

## 확인
```bash
curl -s https://129-225-146-153.sslip.io/healthz          # {"ok":true,"token":true,...} 면 정상 (토큰은 첫 시세 요청 때 받는다)
curl -s "https://129-225-146-153.sslip.io/v1/live?k=<지인 키>"
sudo journalctl -u jogan-relay -n 50 --no-pager          # 로그 (키는 남기지 않는다)
```

## 엔드포인트
| 경로 | 키 | 내용 | 캐시 |
|---|---|---|---|
| `/healthz` | 없음 | 토큰 상태 | — |
| `/v1/live` | 지인 | 코스피·삼전·하닉 현재가 | 5초 |
| `/v1/intraday?date=YYYY-MM-DD` | 지인 | 그날 1분봉 종가(코스피 09:00~15:30, 두 종목 08:00~20:00 — NXT 포함), 시가 | 오늘 20초 · 지난날 1시간 |
| `/v1/daily?date=YYYY-MM-DD` | 루틴 | 국내 6종(시가·종가는 1분봉 기준 KRX 공식값 — `src`·`complete` 필드, `nxt_open`·`nxt_close` 는 통합 일봉 값)·코스피·코스닥 일봉, 미국 4종 일봉, 환율, 코스피 투자자별 매매대금(억원) | 5분 |
| `POST /v1/feedback` | 지인 | 대시보드 "의견" 버튼. JSON `{cat, text, nick, ctx}` → `feedback.jsonl` (1,000자, 하루 30건, IP 당 분당 10회) | — |
| `/v1/feedback?since=YYYY-MM-DD` | 루틴 | 그날부터 쌓인 의견 (토요일 주간 점검용) | — |

키는 `?k=` 또는 `X-Relay-Key` 헤더. 지인 키는 여러 개(콤마) 둘 수 있다. IP 당 분당 120회 제한. CORS 는 `ALLOW_ORIGINS`(기본 GitHub Pages 주소)만.

## 의견 보기
```bash
sudo cat /var/lib/jogan-relay/feedback.jsonl        # 한 줄에 하나(JSON). IP 는 남기지 않는다
```
지울 때는 `sudo truncate -s 0 /var/lib/jogan-relay/feedback.jsonl`. 원문은 이 VM 에만 둔다(저장소는 Public).

## 운영
- 코드 갱신: `cd ~/jisikin-jogan && git pull && sudo bash relay/install.sh` (키 파일은 그대로)
- 지인 키 추가·교체: `sudo nano /etc/jogan-relay.env` 의 `VIEW_KEYS` 수정 → `sudo systemctl restart jogan-relay`
- 지인 키 새로 만들기(이전 링크는 무효, 새 링크는 터미널에만 출력):
  ```bash
  NK=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))') && sudo sed -i "s/^VIEW_KEYS=.*/VIEW_KEYS=$NK/" /etc/jogan-relay.env && sudo systemctl restart jogan-relay && echo "새 지인 링크: https://charismak89.github.io/jisikin-jogan/#k=$NK"; unset NK
  ```
- 토스 키 교체: 같은 파일의 `TOSS_CLIENT_*` 수정 → 재시작
- 멈춤: `sudo systemctl stop jogan-relay` (대시보드는 자동으로 해외 추종가로 그린다)
- **다른 곳에서 토스 토큰을 발급하지 않는다.** 로컬 시험 스크립트를 돌리면 중계기 토큰이 무효가 된다(10초 안에 다시 받지만, 시험은 중계기를 거쳐서 한다).

## 보안 메모
- 중계기는 시세 조회 엔드포인트만 부른다. 계좌·주문 API 는 코드에 없다. 토스 WTS 에 조회 전용 권한 설정이 있으면 그쪽을 쓴다 [검증필요].
- 코인집사 VM 과 분리된 별도 VM 이다. 매매 키가 있는 서버에 인터넷 HTTPS 문을 열지 않기 위해서다.
