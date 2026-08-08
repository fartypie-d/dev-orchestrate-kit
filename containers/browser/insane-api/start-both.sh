#!/bin/bash
# 한 컨테이너에서 브라우저(cloakserve)와 우회 엔진 API(server.py)를 함께 띄운다.
#
# 컨테이너에는 프로세스 관리자가 없다. 둘 중 하나라도 죽으면 나머지가 좀비로 남아
# "포트는 열려 있는데 기능은 죽은" 상태가 되므로, 어느 쪽이 먼저 끝나든 컨테이너를
# 통째로 내려 docker 의 restart 정책이 복구를 맡게 한다.
#
# 이 스크립트는 베이스 이미지의 /entrypoint.sh 가 Xvfb + openbox 를 띄운 뒤
# `exec "$@"` 로 실행한다. 따라서 X 서버는 이미 준비된 상태다.
set -uo pipefail

CDP_PORT="${CLOAKSERVE_PORT:-9222}"
API_PORT="${INSANE_API_PORT:-9223}"
READY_TIMEOUT="${CLOAKSERVE_READY_TIMEOUT:-300}"

log() { printf '%s [start-both] %s\n' "$(date -u '+%H:%M:%S')" "$*" >&2; }

cloakserve --port="$CDP_PORT" &
CLOAK_PID=$!

# 최초 실행은 Chromium(~200MB) 다운로드가 있어 오래 걸린다. 준비될 때까지 대기하되,
# 그 사이 cloakserve 가 죽으면 즉시 실패시킨다(무한 대기 방지).
for _ in $(seq 1 "$READY_TIMEOUT"); do
  if python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:${CDP_PORT}/json/version',timeout=2)" 2>/dev/null; then
    log "cloakserve 준비 완료 (:$CDP_PORT)"
    break
  fi
  if ! kill -0 "$CLOAK_PID" 2>/dev/null; then
    log "cloakserve 기동 실패 — 컨테이너를 내린다"
    exit 1
  fi
  sleep 1
done

python3 /srv/server.py &
API_PID=$!
log "insane-api 기동 (:$API_PORT)"

terminate() { kill "$CLOAK_PID" "$API_PID" 2>/dev/null; }
trap terminate TERM INT

wait -n "$CLOAK_PID" "$API_PID"
STATUS=$?
log "구성 프로세스 중 하나가 종료됨 (status=$STATUS) — 컨테이너를 내린다"
terminate
exit "$STATUS"
