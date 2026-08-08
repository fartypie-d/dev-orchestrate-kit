#!/bin/bash
# x11vnc 로 공유된 Xvfb 화면에 붙고, noVNC(websockify)로 웹 뷰어를 연다.
# 어느 한쪽이 죽으면 컨테이너를 내려 restart 정책이 복구하게 한다.
set -uo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-99}"
SOCK="/tmp/.X11-unix/X${DISPLAY_NUM}"

log() { printf '%s [novnc] %s\n' "$(date -u '+%H:%M:%S')" "$*" >&2; }

# 메인 컨테이너가 X 소켓을 만들 때까지 대기 (최초 기동은 Chromium 다운로드로 오래 걸린다).
for _ in $(seq 1 300); do
  [ -S "$SOCK" ] && break
  sleep 1
done
[ -S "$SOCK" ] || { log "X 소켓 없음: $SOCK — 메인 컨테이너가 떴는지 확인"; exit 1; }

# -localhost: 5900 을 컨테이너 내부 루프백에만 바인딩한다. 이게 없으면 x11vnc 는
#   0.0.0.0 에 바인딩해, 같은 docker 네트워크(browser_default — README 가 외부 컨테이너를
#   조인하라고 안내하는 그 네트워크)의 누구나 무인증 VNC(5900)에 직접 붙을 수 있다.
#   websockify 는 어차피 localhost:5900 으로만 붙으므로 흐름은 그대로다.
# -viewonly: 기본은 보기 전용이다. 수동 로그인·CAPTCHA 로 제어가 필요하면 이 플래그를 뺀다.
x11vnc -display ":${DISPLAY_NUM}" -forever -shared -nopw -localhost -viewonly -rfbport 5900 -bg -o /tmp/x11vnc.log
log "x11vnc → :${DISPLAY_NUM} (localhost 전용, 보기 전용)"

# websockify + noVNC 정적 파일 (debian 패키지 경로).
exec websockify --web=/usr/share/novnc 6080 localhost:5900
