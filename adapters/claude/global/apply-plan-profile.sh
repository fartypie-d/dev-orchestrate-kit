#!/usr/bin/env bash
# Claude 요금제에 맞춰 모델·토큰 설정을 적용한다 (멱등).
#
# 사용법: apply-plan-profile.sh <pro|max5|max20> [--agents-dir DIR] [--settings PATH]
#
# ECC install 은 ~/.claude/agents/*.md 를 덮어쓴다. 이 스크립트는 반드시 ECC 단계 뒤에
# 돌려야 하며, ECC 를 갱신할 때마다 다시 돌려야 한다.
#
# CLAUDE_CODE_SUBAGENT_MODEL 은 절대 쓰지 않는다. 이 환경 변수는 frontmatter 와 명시적
# model 파라미터를 덮어써 worker·품질 게이트의 모델 차등을 무력화한다.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROLES="${APPLY_PLAN_PROFILE_ROLES:-$HERE/agent-roles.json}"
PROFILES="${APPLY_PLAN_PROFILE_PROFILES:-$HERE/plan-profiles.json}"
AGENTS_DIR="$HOME/.claude/agents"
SETTINGS="$HOME/.claude/settings.json"

PROFILE="${1:-}"
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --agents-dir)
      [ $# -ge 2 ] || { echo "--agents-dir 에 경로가 필요하다" >&2; exit 64; }
      AGENTS_DIR="$2"
      shift 2
      ;;
    --settings)
      [ $# -ge 2 ] || { echo "--settings 에 경로가 필요하다" >&2; exit 64; }
      SETTINGS="$2"
      shift 2
      ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }
[ -f "$ROLES" ] || { echo "역할 표 없음: $ROLES" >&2; exit 66; }
[ -f "$PROFILES" ] || { echo "프로파일 표 없음: $PROFILES" >&2; exit 66; }
jq empty "$ROLES" 2>/dev/null || { echo "역할표 JSON 손상: $ROLES" >&2; exit 66; }
jq empty "$PROFILES" 2>/dev/null || { echo "프로파일표 JSON 손상: $PROFILES" >&2; exit 66; }

if [ -z "$PROFILE" ] || ! jq -e --arg p "$PROFILE" '.profiles[$p]' "$PROFILES" >/dev/null 2>&1; then
  echo "알 수 없는 프로파일: '${PROFILE:-(없음)}' — 사용 가능: $(jq -r '.profiles | keys | join(", ")' "$PROFILES")" >&2
  exit 64
fi

echo "== 요금제 프로파일 적용: $PROFILE"
DESIGN_MODEL=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.design' "$PROFILES")
QUALITY_MODEL=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.quality' "$PROFILES")
WORKER_MODEL=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.worker' "$PROFILES")

classify() {
  if jq -e --arg name "$1" '.design | index($name)' "$ROLES" >/dev/null; then
    printf '%s\n' "$DESIGN_MODEL"
    return 0
  else
    status=$?
  fi
  if [ "$status" -ne 1 ]; then
    echo "역할표 조회 실패: $ROLES" >&2
    return "$status"
  fi

  if jq -e --arg name "$1" '.quality | index($name)' "$ROLES" >/dev/null; then
    printf '%s\n' "$QUALITY_MODEL"
    return 0
  else
    status=$?
  fi
  if [ "$status" -ne 1 ]; then
    echo "역할표 조회 실패: $ROLES" >&2
    return "$status"
  fi

  printf '%s\n' "$WORKER_MODEL"
}

if [ -d "$AGENTS_DIR" ]; then
  changed=0
  for file in "$AGENTS_DIR"/*.md; do
    [ -f "$file" ] || continue
    name=$(basename "$file" .md)
    wanted=$(classify "$name")
    has_model=$(perl -ne 'if ($. == 1 && /^---\s*$/) { $front = 1; next } if ($front && /^---\s*$/) { exit } if ($front && /^model:/) { print "yes"; exit }' "$file")
    if [ "$has_model" != "yes" ]; then
      echo "주의: $file 에 model: 필드 없음 — 건너뜀" >&2
      continue
    fi
    temp="$file.tmp.$$"
    perl -pe 'if ($. == 1 && /^---\s*$/) { $front = 1; } elsif ($front && /^---\s*$/) { $front = 0; } elsif ($front && !$done && /^model:/) { s/^model:.*/model: '"$wanted"'/; $done = 1; }' "$file" > "$temp"
    if ! cmp -s "$file" "$temp"; then
      backup="$file.bak-$(date +%Y%m%d-%H%M%S)"
      cp "$file" "$backup"
      mv "$temp" "$file"
      changed=$((changed + 1))
    else
      rm -f "$temp"
    fi
  done
  echo "   에이전트: $changed 개 변경 (design=$DESIGN_MODEL quality=$QUALITY_MODEL worker=$WORKER_MODEL)"
else
  echo "   ⚠️ 에이전트 디렉터리 없음: $AGENTS_DIR — ECC 설치 후 다시 실행할 것"
fi

mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || printf '{}\n' > "$SETTINGS"
TEMP_SETTINGS="$SETTINGS.tmp.$$"
MAIN_MODEL=$(jq -r --arg p "$PROFILE" '.profiles[$p].main_model // ""' "$PROFILES")
ENV_OBJECT=$(jq -c --arg p "$PROFILE" '.profiles[$p].env' "$PROFILES")

jq --arg main "$MAIN_MODEL" --argjson envobj "$ENV_OBJECT" '
  (if $main == "" then . else .model = $main end)
  | .env = ((.env // {}) + ($envobj | with_entries(select(.value != null))))
  | reduce ($envobj | to_entries[] | select(.value == null) | .key) as $key (. ; del(.env[$key]))
  | del(.env["CLAUDE_CODE_SUBAGENT_MODEL"])
  | if (.env | length) == 0 then del(.env) else . end
' "$SETTINGS" > "$TEMP_SETTINGS"

if ! cmp -s "$SETTINGS" "$TEMP_SETTINGS"; then
  cp "$SETTINGS" "$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)"
  mv "$TEMP_SETTINGS" "$SETTINGS"
else
  rm -f "$TEMP_SETTINGS"
fi

if [ -n "$MAIN_MODEL" ]; then
  echo "   메인 모델: $MAIN_MODEL"
else
  echo "   메인 모델: 유지 (현재 $(jq -r '.model // "(미지정)"' "$SETTINGS"))"
fi
echo "   토큰 env: $(jq -c '.env // {}' "$SETTINGS")"
echo
echo "완료. ECC 를 갱신하면 에이전트 파일이 덮이므로 이 스크립트를 다시 실행할 것."
