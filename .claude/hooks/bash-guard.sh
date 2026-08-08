#!/usr/bin/env bash
# PreToolUse(Bash) 훅 — 위험 명령 차단. exit 2 = 차단(stderr가 claude에 전달됨)
# ⚠️ 프로젝트 온보딩 시 아래 컨테이너 등급 목록을 프로젝트에 맞게 채울 것 (비우면 해당 규칙 무시).
set -uo pipefail
CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$CMD" ] && exit 0

deny() { echo "차단됨: $1 — 이 명령은 훅 정책상 금지. 필요하면 사용자에게 직접 실행을 요청할 것." >&2; exit 2; }

# 컨테이너 등급 — 프로젝트별로 수정 (| 구분 정규식. 예: 'my-vpn|my-tunnel')
FORBIDDEN=''        # 절대 조작 금지 컨테이너 (인프라·터널 등)
RESTART_ONLY=''     # restart만 허용, stop/rm 금지 (상태 보유 DB 등)
FOREIGN=''          # 타 프로젝트 컨테이너

case "$CMD" in
  *sudo*)                       deny "sudo (오케스트레이터·위임 에이전트는 권한 상승 금지)";;
  *"docker compose down"*|*"docker-compose down"*) deny "docker compose down (전면 금지 — 재빌드는 up -d --build --force-recreate <서비스명>)";;
esac
[ -n "$FORBIDDEN" ] && echo "$CMD" | grep -qE "docker +(stop|rm|kill|restart|pause|update) +[^ ]*($FORBIDDEN)" && deny "인프라 컨테이너 조작 (절대금지)"
[ -n "$RESTART_ONLY" ] && echo "$CMD" | grep -qE "docker +(stop|rm|kill|pause) +[^ ]*($RESTART_ONLY)" && deny "상태 보유 컨테이너 stop/rm (docker restart만 허용)"
[ -n "$FOREIGN" ] && echo "$CMD" | grep -qE "docker +(stop|rm|kill|restart|pause) +[^ ]*($FOREIGN)" && deny "타 프로젝트 컨테이너 조작"
# 서비스명 없는 compose 조작 (스택 전체가 걸린다 — 서비스명 명시 강제)
echo "$CMD" | tr '&|;' '\n' | grep -qE "docker +compose( +(-f +[^ ]+|--profile +[^ ]+|-p +[^ ]+))* +(restart|up|stop)( +--?[A-Za-z-]+)* *$" \
  && deny "서비스명 없는 docker compose restart/up/stop (서비스명 명시 필수)"
echo "$CMD" | grep -qE 'rm +(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)' && deny "rm -rf"
echo "$CMD" | grep -qE 'git +push +[^ ]+ +(main|master)( |$)' && deny "main 직접 push"
echo "$CMD" | grep -qE 'git +push +(-f|--force)' && deny "force push"
exit 0
