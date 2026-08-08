#!/usr/bin/env bash
# 위임 실행 래퍼 — /orchestrate 스킬 6단계의 실행 블록을 파일 하나로 고정한 것.
# (dev-orchestrate-kit 이식판 — macOS bash 3.2 호환: mapfile 미사용, flock 폴백 내장)
#
# 왜 파일로 고정하는가:
#   claude 권한 allowlist 는 명령 prefix 매칭이라, nohup·워치독 루프가 붙은 복합 명령을
#   매칭하지 못한다. 스크립트 한 개로 고정하면 `Bash(bash scripts/run-delegation.sh:*)`
#   규칙 하나로 위임이 통과한다.
#
# v2 (2026-08-01): 모델 폴백 체인 내장.
#   - 모델은 에이전트 frontmatter가 아니라 ~/.config/opencode/model-policy.json 의 tier 체인에서
#     골라 `-m` 으로 주입한다. frontmatter의 model: 은 수동 실행용 안전 기본값일 뿐이다.
#   - 한도·무응답(429/quota/즉시 실패/재시도 루프 스톨)을 감지하면 다음 모델로 자동 재시도한다.
#   - 성공 시 `MODEL_USED=<provider/model>` 을 출력한다 — 검수(리뷰어 강화 원칙)는 이 값 기준.
#
# 사용법: bash scripts/run-delegation.sh <에이전트> <프롬프트파일> <로그파일> [tier|provider/model]
#   4번째 인자 생략 = default tier. `heavy` = 복잡 task·반려 재위임용.
#   `provider/model` 명시 = 그 모델 우선 시도, 실패하면 default 체인으로 폴백.
# exit: 0 완료 / 2 init 경합 / 3 비관리 프로세스 / 4 락 타임아웃 / 5 모델 체인 전멸
#       / 64 사용법·정책 파일 문제 / 66 프롬프트 파일 없음
#
# 금지사항(스킬 6단계):
#   - timeout 으로 감싸지 말 것 (SIGTERM 이 opencode 세션 DB 를 오염시켜 다음 실행까지 막는다)
#   - 파이프(| tail)로 받지 말 것 (버퍼링으로 진행이 안 보인다)
#   - 프롬프트를 명령줄에 인라인하지 말 것 (따옴표 이스케이프가 깨진다)

set -uo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo "usage: bash scripts/run-delegation.sh <agent> <prompt-file> <log-file> [tier|provider/model]" >&2
  exit 64
fi

AGENT="$1"
PROMPT_FILE="$2"
LOG_FILE="$3"
TIER="${4:-default}"
POLICY="$HOME/.config/opencode/model-policy.json"
OPENCODE_BIN="$HOME/.opencode/bin/opencode"

cd "$(dirname "$0")/.." || exit 1

[ -f "$PROMPT_FILE" ] || { echo "프롬프트 파일 없음: $PROMPT_FILE" >&2; exit 66; }
[ -f "$POLICY" ] || { echo "정책 파일 없음: $POLICY" >&2; exit 64; }
[ -x "$OPENCODE_BIN" ] || { echo "opencode 없음: $OPENCODE_BIN (install.sh 실행 필요)" >&2; exit 64; }

# ── 모델 체인 구성 (bash 3.2 호환 — mapfile 미사용) ──────────────────────
CHAIN=()
if [ "${TIER#*/}" != "$TIER" ]; then
  # 명시 모델: 그 모델 먼저, 실패 시 default 체인으로 이어감 (중복 제거)
  CHAIN=("$TIER")
  while IFS= read -r m; do
    [ "$m" = "$TIER" ] || CHAIN[${#CHAIN[@]}]="$m"
  done < <(jq -r '.tiers.default[]' "$POLICY")
else
  while IFS= read -r m; do
    CHAIN[${#CHAIN[@]}]="$m"
  done < <(jq -r --arg t "$TIER" '.tiers[$t] // [] | .[]' "$POLICY")
  if [ "${#CHAIN[@]}" -eq 0 ]; then
    echo "알 수 없는 tier: $TIER (정책 파일의 tiers 키 확인: $POLICY)" >&2
    exit 64
  fi
fi

# ── 전역 락 — opencode 세션 DB는 전역 공유라 동시 위임은 프로젝트가 달라도 경합한다 ──
# flock(리눅스)이 있으면 fd 상속 방식(래퍼가 죽어도 opencode가 도는 동안 유지),
# 없으면(macOS 기본) mkdir 스핀락 + PID 스테일 감지로 폴백.
LOCK_DIR="$HOME/.local/state/orchestrate"
mkdir -p "$LOCK_DIR"
LOCK_WAIT_MAX=1800

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_DIR/opencode.lock"
  if ! flock -n 9; then
    echo "LOCK_WAIT: 다른 세션의 위임이 실행 중 — 최대 30분 대기 (락: $LOCK_DIR/opencode.lock)"
    flock -w "$LOCK_WAIT_MAX" 9 || { echo "LOCK_TIMEOUT: 30분 내 락 획득 실패 — 위임 포기" >&2; exit 4; }
  fi
else
  MLOCK="$LOCK_DIR/opencode.lock.d"
  WAITED=0
  while ! mkdir "$MLOCK" 2>/dev/null; do
    HOLDER=$(cat "$MLOCK/pid" 2>/dev/null || echo "")
    if [ -n "$HOLDER" ] && ! kill -0 "$HOLDER" 2>/dev/null; then
      rm -rf "$MLOCK"; continue   # 스테일 락 (보유 프로세스 사망)
    fi
    [ "$WAITED" -eq 0 ] && echo "LOCK_WAIT: 다른 세션의 위임이 실행 중 — 최대 30분 대기 (락: $MLOCK)"
    sleep 10; WAITED=$((WAITED + 10))
    [ "$WAITED" -ge "$LOCK_WAIT_MAX" ] && { echo "LOCK_TIMEOUT: 30분 내 락 획득 실패 — 위임 포기" >&2; exit 4; }
  done
  echo "$$" > "$MLOCK/pid"
  trap 'rm -rf "$MLOCK"' EXIT
fi

# 락은 잡았는데 opencode run 프로세스가 남아 있으면 = 래퍼 밖에서 뜬 비관리 프로세스.
if ps -eo pid,etime,args | awk '/opencode run/ && !/awk/' | grep -q .; then
  echo "PREFLIGHT_UNMANAGED: 락 없이 도는 opencode 프로세스 발견 — 세션 DB 경합 위험. 정리 후 재시도" >&2
  ps -eo pid,etime,args | awk '/opencode run/ && !/awk/' >&2
  exit 3
fi

# API 키 자가 주입 — 비대화형 셸은 secrets.env 가 셸 rc 에 추가되기 전 환경을 물려받을 수 있다.
set -a
# shellcheck disable=SC1090
[ -f "$HOME/.config/opencode/secrets.env" ] && . "$HOME/.config/opencode/secrets.env"
set +a

# ── 모델 실패 판정 ────────────────────────────────────────────────────────
# 한도·프로바이더 장애 시그니처. 두 가지로 오판을 줄인다:
#   ① ERROR 라인만 스캔 — 에이전트 산출물의 우연한 매치 배제
#   ② 마지막 50줄만 스캔 — opencode는 스트림 에러 후 내부 재시도로 회복하기도 한다.
#      회복한 실행은 말미가 정상 출력이므로 전체 스캔하면 성공을 실패로 오판한다.
FAIL_RE='status.?429|rate.?limit|quota|resource_exhausted|insufficient_quota|too.?many.?requests|overloaded|exceeded.*(limit|quota)|AI_APICallError|AI_RetryError|ProviderAuthError|ECONNREFUSED|fetch failed'

model_error_in_log() { # $1=로그 파일
  tail -n 50 "$1" | grep -a 'ERROR' | grep -qiE "$FAIL_RE"
}

# ── 시도 루프 ────────────────────────────────────────────────────────────
FALLBACK_NOTES=""
for MODEL in "${CHAIN[@]}"; do
  # antigravity 모델은 로컬 프록시(:8045) 생존 확인 — 죽어 있으면 시도 없이 스킵 (401도 정상)
  case "$MODEL" in
    antigravity/*)
      HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8045/v1/models 2>/dev/null || echo 000)
      if [ "$HTTP_CODE" = "000" ]; then
        echo "MODEL_FALLBACK: $MODEL (antigravity 프록시 :8045 다운) → 다음 모델"
        FALLBACK_NOTES="$FALLBACK_NOTES[$MODEL: proxy down] "
        continue
      fi;;
  esac

  : > "$LOG_FILE"
  nohup "$OPENCODE_BIN" run --print-logs --log-level INFO \
    --agent "$AGENT" -m "$MODEL" "$(cat "$PROMPT_FILE")" > "$LOG_FILE" 2>&1 &
  OC_PID=$!
  echo "OC_PID=$OC_PID AGENT=$AGENT MODEL=$MODEL LOG=$LOG_FILE"

  # 워치독 — 120초 내 'loop session.id' 미출현 = init 단계 세션 DB 경합.
  # init 단계는 세션 생성 전이라 kill 해도 산출물 손실이 없다.
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    sleep 10
    grep -q 'loop session.id' "$LOG_FILE" && break
    kill -0 "$OC_PID" 2>/dev/null || break
  done

  if kill -0 "$OC_PID" 2>/dev/null && ! grep -q 'loop session.id' "$LOG_FILE"; then
    kill "$OC_PID"
    echo "STALLED_AT_INIT: 세션 DB 경합 — 세션 생성 전이라 산출물 없음. 잔여 opencode 정리 후 재위임할 것"
    exit 2   # 세션 DB 문제는 모델 탓이 아니다 — 폴백하지 않고 보고
  fi

  # 완료 대기 (pgrep -f 자기 매칭 무한 루프를 피하려고 launch 시점 PID 만 본다)
  #
  # + 재시도 루프 스톨 가드 (2026-08-01 실측): 모델이 한도로 죽어 있으면 opencode는 지수
  #   백오프로 stream error 재시도를 계속하며 프로세스가 안 끝난다 (12분+ 실측).
  #   타이머는 재시도 백오프 공백에서만 누적된다 — 새 시도가 시작되면 INFO 라인이 로그 말미에
  #   붙어 즉시 리셋되므로, 회복 중인 실행을 오판할 위험은 사실상 없다. 90초 공백 = 백오프가
  #   이미 수 회 실패해 분 단위로 벌어진 상태 → 끊고 다음 모델로 (산출물 0이라 kill 안전).
  STALL_LIMIT=90
  STALL_REASON=""
  STALL_START=0
  LAST_STEPS=$(grep -c 'loop session.id' "$LOG_FILE")
  while kill -0 "$OC_PID" 2>/dev/null; do
    sleep 10
    STEPS=$(grep -c 'loop session.id' "$LOG_FILE")
    if [ "$STEPS" -ne "$LAST_STEPS" ]; then
      LAST_STEPS=$STEPS; STALL_START=0; continue
    fi
    if tail -n 3 "$LOG_FILE" | grep -a 'ERROR' | grep -qiE "$FAIL_RE" \
       && [ "$(tail -n 50 "$LOG_FILE" | grep -ac 'ERROR')" -ge 3 ]; then
      [ "$STALL_START" -eq 0 ] && STALL_START=$(date +%s)
      if [ $(( $(date +%s) - STALL_START )) -ge "$STALL_LIMIT" ]; then
        kill "$OC_PID" 2>/dev/null; sleep 3
        kill -0 "$OC_PID" 2>/dev/null && kill -9 "$OC_PID" 2>/dev/null
        STALL_REASON="재시도 루프 스톨 (${STALL_LIMIT}초 무진행, step=$STEPS)"
        break
      fi
    else
      STALL_START=0
    fi
  done
  wait "$OC_PID" 2>/dev/null
  OC_RC=$?

  SESSION_STARTED=false
  grep -q 'loop session.id' "$LOG_FILE" && SESSION_STARTED=true

  # 모델 실패 판정: ⓪ 스톨 가드 kill ① 세션도 못 열고 종료(즉시 API 거절) ② ERROR 라인에
  # 한도·장애 시그니처 ③ 비정상 종료 코드. 해당하면 실패 로그를 보존하고 다음 모델로.
  REASON=""
  if [ -n "$STALL_REASON" ]; then
    REASON="$STALL_REASON"
  elif [ "$SESSION_STARTED" = false ]; then
    REASON="세션 미개시 종료 rc=$OC_RC"
  elif model_error_in_log "$LOG_FILE"; then
    REASON="한도/프로바이더 에러 시그니처 rc=$OC_RC"
  elif [ "$OC_RC" -ne 0 ]; then
    REASON="비정상 종료 rc=$OC_RC"
  fi

  if [ -n "$REASON" ]; then
    SLUG=$(echo "$MODEL" | tr '/' '_')
    mv "$LOG_FILE" "$LOG_FILE.failed-$SLUG" 2>/dev/null || true
    echo "MODEL_FALLBACK: $MODEL ($REASON) → 다음 모델 (실패 로그: $LOG_FILE.failed-$SLUG)"
    FALLBACK_NOTES="$FALLBACK_NOTES[$MODEL: $REASON] "
    continue
  fi

  echo "DONE"
  echo "MODEL_USED=$MODEL"
  [ -n "$FALLBACK_NOTES" ] && echo "FALLBACK_HISTORY: $FALLBACK_NOTES"
  tail -5 "$LOG_FILE"
  exit 0
done

echo "MODEL_EXHAUSTED: 체인 전 모델 실패 — $FALLBACK_NOTES" >&2
echo "사용자에게 보고할 것: 프로바이더 한도 확인 필요 (~/.config/opencode/model-policy.json)" >&2
exit 5
