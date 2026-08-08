#!/usr/bin/env bash
# 모델 체인 실측 검증 — 설치 마지막 단계이자 언제든 재실행 가능.
#
# 확인 항목:
#   1. model-policy.json 의 각 항목이 `opencode models` 등록분에 실재하는가
#   2. 체인 프로바이더의 키/OAuth 인증 상태를 보고하는가 (인증 누락만으로는 실패하지 않음)
#   3. tier 당 1회 스모크 호출 (--skip-smoke 로 생략 가능)
#
# 이 검증이 없으면 오타 난 모델 ID 가 조용히 폴백만 소모한다.
set -uo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
POLICY="$HOME/.config/opencode/model-policy.json"
SECRETS="$HOME/.config/opencode/secrets.env"
OPENCODE_BIN="$HOME/.opencode/bin/opencode"
MAPPING="$SCRIPT_DIR/provider-models.json"
SKIP_SMOKE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --policy)       POLICY="$2"; shift 2 ;;
    --secrets)      SECRETS="$2"; shift 2 ;;
    --opencode-bin) OPENCODE_BIN="$2"; shift 2 ;;
    --skip-smoke)   SKIP_SMOKE=1; shift ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
done

[ -x "$OPENCODE_BIN" ] || { echo "opencode 바이너리 없음: $OPENCODE_BIN" >&2; exit 69; }
[ -f "$POLICY" ] || { echo "정책 파일 없음: $POLICY" >&2; exit 66; }
command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }

if ! jq empty "$POLICY" >/dev/null 2>&1; then
  echo "정책 JSON 손상: $POLICY" >&2
  exit 66
fi

TIER_TYPE=$(jq -r '(.tiers // {}) | type' "$POLICY")
[ "$TIER_TYPE" = "object" ] || { echo "정책의 tiers 가 객체가 아니다 ($TIER_TYPE): $POLICY" >&2; exit 66; }

TIER_COUNT=$(jq -r '(.tiers // {}) | length' "$POLICY")
if [ "$TIER_COUNT" -eq 0 ]; then
  echo "정책에 tier 가 하나도 없다: $POLICY" >&2
  exit 1
fi

echo "== 모델 체인 검증 ($POLICY)"

REGISTERED=$("$OPENCODE_BIN" models 2>/dev/null)
MODELS_STATUS=$?
if [ "$MODELS_STATUS" -ne 0 ]; then
  echo "opencode models 실패 (exit $MODELS_STATUS) — 인증·설치를 확인할 것" >&2
  exit 1
fi
if [ -z "$REGISTERED" ]; then
  echo "   ⚠️ 등록 모델 목록이 비어 있다 — opencode 설치·인증을 먼저 확인할 것" >&2
  exit 1
fi

FAILED_TIERS=""
SEEN_PREFIXES=""
while IFS= read -r tier; do
  echo
  echo "-- tier: $tier"
  valid=0
  first_valid=""
  while IFS= read -r model; do
    prefix=${model%%/*}
    if ! printf '%s\n' "$SEEN_PREFIXES" | grep -qxF "$prefix"; then
      SEEN_PREFIXES="${SEEN_PREFIXES}
$prefix"
    fi
    if printf '%s\n' "$REGISTERED" | grep -qxF "$model"; then
      echo "   OK      $model"
      valid=$((valid + 1))
      [ -n "$first_valid" ] || first_valid="$model"
    else
      echo "   MISSING $model   ← opencode models 에 없다 (오타이거나 인증 미완료)"
    fi
  done < <(jq -r --arg tier "$tier" '.tiers[$tier][]' "$POLICY")

  if [ "$valid" -eq 0 ]; then
    echo "   ❌ 이 tier 에 사용 가능한 모델이 하나도 없다"
    FAILED_TIERS="${FAILED_TIERS:+$FAILED_TIERS }$tier"
  elif [ "$SKIP_SMOKE" -eq 0 ]; then
    echo "   스모크 호출: $first_valid"
    "$OPENCODE_BIN" run -m "$first_valid" "Reply with exactly: OK" >/dev/null 2>&1
    RUN_STATUS=$?
    if [ "$RUN_STATUS" -eq 0 ]; then
      echo "   OK      스모크 통과"
    else
      echo "   ⚠️ 스모크 실패 (exit $RUN_STATUS) — 인증·레이트리밋을 확인할 것 (체인 폴백은 여전히 동작한다)"
    fi
  fi
done < <(jq -r '.tiers | keys[]' "$POLICY")

echo
echo "-- 인증 수단"
AUTH_OUT=$("$OPENCODE_BIN" auth list 2>/dev/null)
AUTH_STATUS=$?
if [ "$AUTH_STATUS" -ne 0 ]; then
  echo "auth list 실행 실패 (exit $AUTH_STATUS)" >&2
fi

# 값은 읽거나 출력하지 않고, 키 이름과 빈 값 여부만 판별한다.
SECRET_KEYS=""
if [ -f "$SECRETS" ]; then
  SECRET_KEYS=$(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$SECRETS" 2>/dev/null | sed 's/=$//')
fi

while IFS= read -r prefix; do
  [ -n "$prefix" ] || continue
  PROVIDER=$(jq -r --arg prefix "$prefix" '.providers | to_entries[] | select(.value.prefix == $prefix) | .key' "$MAPPING")
  if [ -z "$PROVIDER" ]; then
    echo "   인증 확인 불가: $prefix (매핑표에 없음)"
    continue
  fi
  AUTH_TYPE=$(jq -r --arg provider "$PROVIDER" '.providers[$provider].auth' "$MAPPING")
  CREDENTIAL=$(jq -r --arg provider "$PROVIDER" '.providers[$provider].credential' "$MAPPING")
  if [ "$AUTH_TYPE" = "key" ]; then
    if printf '%s\n' "$SECRET_KEYS" | grep -qxF "$CREDENTIAL"; then
      if grep -qxF "$CREDENTIAL=" "$SECRETS" 2>/dev/null; then
        echo "   인증 누락: $PROVIDER ($CREDENTIAL 이름 있음, 값 비어있음)"
      else
        echo "   인증 OK: $PROVIDER (key)"
      fi
    else
      echo "   인증 누락: $PROVIDER ($CREDENTIAL 미설정)"
    fi
  elif [ "$AUTH_TYPE" = "oauth" ]; then
    if [ "$AUTH_STATUS" -ne 0 ]; then
      echo "   인증 확인 불가: $PROVIDER (auth list 실행 실패)"
    elif printf '%s\n' "$AUTH_OUT" | grep -qiF "$PROVIDER"; then
      echo "   인증 OK: $PROVIDER (oauth)"
    else
      echo "   인증 누락: $PROVIDER (OAuth 인증 미확인)"
    fi
  else
    echo "   인증 확인 불가: $PROVIDER (알 수 없는 인증 방식: $AUTH_TYPE)"
  fi
done <<EOF
$SEEN_PREFIXES
EOF

echo
if [ -n "$FAILED_TIERS" ]; then
  echo "❌ 사용 불가 tier: $FAILED_TIERS — model-policy.json 을 고치거나 인증을 완료할 것"
  exit 1
fi
if [ "$SKIP_SMOKE" -eq 1 ]; then
  echo "⏭ 스모크 생략됨 (--skip-smoke) — 모델 ID 존재만 확인, 실제 호출 미검증"
  echo "✅ 모든 tier 에 사용 가능한 모델이 있다 (스모크 생략)"
else
  echo "✅ 모든 tier 에 사용 가능한 모델이 있다 (스모크 수행)"
fi
exit 0
