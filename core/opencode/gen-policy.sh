#!/usr/bin/env bash
# 선택된 프로바이더에서 model-policy.json 의 tier 체인을 생성한다.
#
# 사용법: gen-policy.sh <PROVIDERS_CSV> <OUT_PATH>       예: gen-policy.sh qwen,openai ~/.config/opencode/model-policy.json
#
# 매핑표는 provider-models.json 이며, 거기 tier_order 가 체인 내 우선순위를 정한다.
# 생성 결과는 시드일 뿐이다 — 실제 가용성 검증은 model-doctor.sh 가 한다.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TABLE="$HERE/provider-models.json"
PROVIDERS_CSV="${1:?usage: gen-policy.sh <PROVIDERS_CSV> <OUT_PATH>}"
OUT="${2:?usage: gen-policy.sh <PROVIDERS_CSV> <OUT_PATH>}"

command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }
[ -f "$TABLE" ] || { echo "매핑표 없음: $TABLE" >&2; exit 66; }
jq empty "$TABLE" 2>/dev/null || { echo "매핑표 JSON 손상: $TABLE" >&2; exit 66; }

# 선택분 중 매핑표에 있는 것만 남긴다 (bash 3.2 호환 — 배열 인덱스 추가 방식).
SELECTED=()
old_ifs="$IFS"
IFS=','
set -f
for p in $PROVIDERS_CSV; do
  if jq -e --arg p "$p" '.providers[$p]' "$TABLE" >/dev/null 2>&1; then
    SELECTED[${#SELECTED[@]}]="$p"
  else
    echo "경고: 알 수 없는 프로바이더 '$p' — 무시한다 (매핑표: $TABLE)" >&2
  fi
done
set +f
IFS="$old_ifs"

if [ ${#SELECTED[@]} -eq 0 ]; then
  echo "유효한 프로바이더가 하나도 없다 — 체인을 만들 수 없다" >&2
  exit 65
fi

# tier_order 순서대로 선택된 프로바이더의 모델을 이어 붙인다.
# GPT 우선 정책은 tier_order 의 첫 항목(openai)이 담보한다 — 이 함수는 표 순서를 따를 뿐이다.
SELECTED_JSON=$(printf '%s\n' "${SELECTED[@]}" | jq -R . | jq -s .)
build_tier() { # <tier 이름>
  local _tier
  local _sel_json
  _tier="$1"
  _sel_json="$SELECTED_JSON"
  jq --arg t "$_tier" --argjson sel "$_sel_json" '
    [ .tier_order[] as $p
      | select($sel | index($p))
      | .providers[$p][$t]
      | if . == null then empty elif type == "array" then .[] else error("providers.\($p).\($t) 는 배열이어야 한다") end
    ]
  ' "$TABLE"
}

DEFAULT_CHAIN=$(build_tier default)
HEAVY_CHAIN=$(build_tier heavy)

for tier in default heavy; do
  if [ "$tier" = "default" ]; then
    chain="$DEFAULT_CHAIN"
  else
    chain="$HEAVY_CHAIN"
  fi
  if [ "$(printf '%s' "$chain" | jq 'length')" -eq 0 ]; then
    echo "경고: $tier tier 체인이 비었다 — 선택한 프로바이더(${SELECTED[*]})에 $tier 모델이 없다. model-doctor.sh 로 확인하라" >&2
  fi
done

mkdir -p "$(dirname "$OUT")"
jq -n --argjson d "$DEFAULT_CHAIN" --argjson h "$HEAVY_CHAIN" '{
  _comment: "위임 모델 폴백 체인 — scripts/run-delegation.sh 가 읽는다. 순서 = 시도 순서. gen-policy.sh 가 생성했으며 손으로 고쳐도 된다. 모델 ID 는 `opencode models` 등록분만 유효하다 — 검증은 model-doctor.sh.",
  _quota_note: "서로 다른 구독(xai·openai 등)은 별개 할당량 풀이다. 체인에 섞어두면 한쪽 한도에서 다른 쪽으로 넘어간다.",
  tiers: { default: $d, heavy: $h }
}' > "$OUT"

echo "생성: $OUT"
if [ "$(printf '%s' "$DEFAULT_CHAIN" | jq 'length')" -eq 0 ]; then
  echo "  default: (비어있음 — 경고 참고)"
else
  echo "  default: $(printf '%s' "$DEFAULT_CHAIN" | jq -r 'join(" → ")')"
fi
if [ "$(printf '%s' "$HEAVY_CHAIN" | jq 'length')" -eq 0 ]; then
  echo "  heavy:   (비어있음 — 경고 참고)"
else
  echo "  heavy:   $(printf '%s' "$HEAVY_CHAIN" | jq -r 'join(" → ")')"
fi
