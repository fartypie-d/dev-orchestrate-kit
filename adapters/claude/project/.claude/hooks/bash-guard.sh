#!/usr/bin/env bash
# PreToolUse(Bash) 훅 — 위험 명령 차단. exit 2 = 차단(stderr가 claude에 전달됨)
# ⚠️ 프로젝트 온보딩 시 아래 컨테이너 등급 목록을 프로젝트에 맞게 채울 것 (비우면 해당 규칙 무시).
set -uo pipefail
if ! CMD=$(jq -r '.tool_input.command // empty'); then
  echo "차단됨: jq 실행 실패 — 방어적으로 차단" >&2
  exit 2
fi
[ -z "$CMD" ] && exit 0

deny() { echo "차단됨: $1 — 이 명령은 훅 정책상 금지. 필요하면 사용자에게 직접 실행을 요청할 것." >&2; exit 2; }

# 컨테이너 등급 — 프로젝트별로 수정 (| 구분 정규식. 예: 'my-vpn|my-tunnel')
FORBIDDEN=''        # 절대 조작 금지 컨테이너 (인프라·터널 등)
RESTART_ONLY=''     # restart만 허용, stop/rm 금지 (상태 보유 DB 등)
FOREIGN=''          # 타 프로젝트 컨테이너

# 일반 인용문은 실행 경로일 수 있으므로 그대로 검사한다. 어느 줄이든 첫 토큰이 git이면 커밋 메시지의
# 인용된 값만 제거해 메시지 언급 때문에 정상 커밋이 막히지 않게 한다. 단, 큰따옴표 메시지 안의 셸 확장은
# 실행 경로이므로 제거하지 않는다.
SCAN_CMD=$CMD
if printf '%s\n' "$CMD" | grep -qE '^[[:space:]]*git([[:space:]]|$)'; then
  if ! printf '%s\n' "$CMD" | grep -qE '(^|[[:space:]])(-m|--message)[[:space:]]*"[^"]*(\$[(]|`|\$\{)'; then
    if ! SCAN_CMD=$(printf '%s\n' "$CMD" | sed -E \
      -e ':double' -e 's/(^|[[:space:]])(-m|--message)[[:space:]]*"[^"]*"/\1\2/; t double' \
      -e ':single' -e "s/(^|[[:space:]])(-m|--message)[[:space:]]*'[^']*'/\\1\\2/; t single"); then
      echo "경고: sed 실행 실패 — 원문 명령을 검사합니다." >&2
      SCAN_CMD=$CMD
    fi
  fi
fi

case "$SCAN_CMD" in
  *"docker compose down"*|*"docker-compose down"*) deny "docker compose down (전면 금지 — 재빌드는 up -d --build --force-recreate <서비스명>)";;
esac
printf '%s\n' "$SCAN_CMD" | grep -qE '(^|[^[:alnum:]_.-])(/[^[:space:]]*/)?sudo([^[:alnum:]_.-]|$)' && deny "sudo (오케스트레이터·위임 에이전트는 권한 상승 금지)"
[ -n "$FORBIDDEN" ] && echo "$SCAN_CMD" | grep -qE "docker +(stop|rm|kill|restart|pause|update) +[^ ]*($FORBIDDEN)" && deny "인프라 컨테이너 조작 (절대금지)"
[ -n "$RESTART_ONLY" ] && echo "$SCAN_CMD" | grep -qE "docker +(stop|rm|kill|pause) +[^ ]*($RESTART_ONLY)" && deny "상태 보유 컨테이너 stop/rm (docker restart만 허용)"
[ -n "$FOREIGN" ] && echo "$SCAN_CMD" | grep -qE "docker +(stop|rm|kill|restart|pause) +[^ ]*($FOREIGN)" && deny "타 프로젝트 컨테이너 조작"
# 서비스명 없는 compose 조작 (스택 전체가 걸린다 — 서비스명 명시 강제)
echo "$CMD" | tr '&|;' '\n' | grep -qE "docker +compose( +(-f +[^ ]+|--profile +[^ ]+|-p +[^ ]+))* +(restart|up|stop)( +--?[A-Za-z-]+)* *$" \
  && deny "서비스명 없는 docker compose restart/up/stop (서비스명 명시 필수)"
printf '%s\n' "$SCAN_CMD" | grep -qE '(^|[^[:alnum:]_.-])rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)([^[:alnum:]_.-]|$)' && deny "rm -rf"
printf '%s\n' "$SCAN_CMD" | grep -qE '(^|[^[:alnum:]_.-])git[[:space:]]+push[[:space:]]+[^[:space:];|&(){}]+[[:space:]]+(main|master)([^[:alnum:]_.-]|$)' && deny "main 직접 push"
printf '%s\n' "$SCAN_CMD" | grep -qE '(^|[^[:alnum:]_.-])git[[:space:]]+push([[:space:]]+[^[:space:];|&(){}]+)*[[:space:]]+(-f|--force)([^[:alnum:]_.-]|$)' && deny "force push"
exit 0
