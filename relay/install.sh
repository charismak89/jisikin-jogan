#!/usr/bin/env bash
# jogan-relay 설치·갱신 스크립트 (Ubuntu 22.04/24.04, 오라클 VM 기준)
#   처음 설치:  sudo bash relay/install.sh        → 토스 client_id/secret 을 묻고, 키를 만들고, Caddy(HTTPS)까지 세팅
#   코드 갱신:  git pull && sudo bash relay/install.sh   → 키 파일은 그대로 두고 코드만 바꿔 재시작
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "sudo 로 실행하세요: sudo bash relay/install.sh"; exit 1; }

REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
APP=/opt/jogan-relay
ENVF=/etc/jogan-relay.env
STATE=/var/lib/jogan-relay
IP=$(curl -s --max-time 10 https://api.ipify.org || true)
[ -n "$IP" ] || { echo "공인 IP 를 확인하지 못했습니다"; exit 1; }
HOST="${IP//./-}.sslip.io"
echo "== 공인 IP $IP → 주소 https://$HOST"

# 1) 서비스 계정과 폴더
id jogan >/dev/null 2>&1 || useradd --system --home "$STATE" --shell /usr/sbin/nologin jogan
install -d -o jogan -g jogan -m 700 "$STATE"
install -d -m 755 "$APP"
install -m 644 "$REPO_DIR/relay/jogan_relay.py" "$APP/jogan_relay.py"

# 2) 키 파일 — 이미 있으면 건드리지 않는다
NEW_KEYS=0
if [ ! -f "$ENVF" ]; then
  echo "== 토스 Open API 키 입력 (화면에 표시되지 않음)"
  read -rp  '  client_id: '     TID
  read -rsp '  client_secret: ' TSEC; echo
  VK=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')
  RK=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
  ( umask 077
    printf 'TOSS_CLIENT_ID=%s\nTOSS_CLIENT_SECRET=%s\nVIEW_KEYS=%s\nROUTINE_KEY=%s\nALLOW_ORIGINS=https://charismak89.github.io\n' \
      "$TID" "$TSEC" "$VK" "$RK" > "$ENVF" )
  chmod 600 "$ENVF"; unset TID TSEC
  NEW_KEYS=1
fi

# 3) systemd 서비스
cat > /etc/systemd/system/jogan-relay.service <<'UNIT'
[Unit]
Description=jogan relay (Toss Open API)
After=network-online.target
Wants=network-online.target

[Service]
User=jogan
Group=jogan
EnvironmentFile=/etc/jogan-relay.env
Environment=STATE_DIR=/var/lib/jogan-relay
Environment=PORT=8787
ExecStart=/usr/bin/python3 /opt/jogan-relay/jogan_relay.py
Restart=always
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/jogan-relay
MemoryMax=150M

[Install]
WantedBy=multi-user.target
UNIT

# 4) Caddy (HTTPS 인증서 자동) — 없을 때만 설치
if ! command -v caddy >/dev/null 2>&1; then
  echo "== Caddy 설치"
  apt-get update -qq
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
	encode gzip
	header -Server
	reverse_proxy 127.0.0.1:8787
}
CADDY

systemctl daemon-reload
systemctl enable --now jogan-relay >/dev/null
systemctl restart jogan-relay
systemctl enable caddy >/dev/null; systemctl restart caddy
sleep 4

echo "== 상태"
systemctl is-active jogan-relay caddy | paste -sd' ' || true
curl -s http://127.0.0.1:8787/healthz || echo '중계기 응답 없음 — sudo journalctl -u jogan-relay -n 30 --no-pager'; echo

# 키는 처음 설치할 때만 이 터미널에 보여 준다. 갱신 때 출력은 캡처해 공유해도 되게 키를 찍지 않는다
. "$ENVF"
VK1=${VIEW_KEYS%%,*}
echo
echo "== 확인 명령 (1~2분 뒤 인증서가 붙으면 성공)"
echo "  curl -s https://$HOST/healthz"
if [ "$NEW_KEYS" = 1 ]; then
  echo "  curl -s 'https://$HOST/v1/live?k=$VK1'"
  echo
  echo "== 지인 공유 링크 (이 링크로 처음 연 브라우저는 키를 기억한다)"
  echo "  https://charismak89.github.io/jisikin-jogan/#k=$VK1"
  echo
  echo "== 루틴용 키 — Claude 환경 설정의 Network secrets(또는 환경 변수)에 넣는다"
  echo "  JJ_RELAY_URL=https://$HOST"
  echo "  JJ_RELAY_TOKEN=$ROUTINE_KEY"
fi
echo
echo "로그: sudo journalctl -u jogan-relay -n 50 --no-pager · 키 다시 보기: sudo cat $ENVF"
