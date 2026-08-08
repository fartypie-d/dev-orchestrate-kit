#!/usr/bin/env bash
# dev-orchestrate-kit 전역 설치 (멱등) — macOS / Linux
#
# 사용법: ./install.sh [--claude] [--codex] [--containers=browser,antigravity] \
#                     [--providers=qwen,openai,xai,antigravity] [--plan=<이름>] [ECC 언어 ...]
#
# 기존 파일은 .bak-<날짜>로 백업 후 교체한다 (secrets.env는 절대 덮어쓰지 않음).
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
ECC_REPO="https://github.com/affaan-m/everything-claude-code.git"
ECC_DIR="$HOME/everything-claude-code"
STAMP=$(date +%Y%m%d-%H%M%S)
. "$KIT_DIR/lib/stamp.sh"

HARNESSES=""
PROVIDERS=""
CONTAINERS=""
PLAN=""
ECC_LANGS=()
for arg in "$@"; do
  case "$arg" in
    --claude)       HARNESSES="${HARNESSES:+$HARNESSES }claude" ;;
    --codex)        HARNESSES="${HARNESSES:+$HARNESSES }codex" ;;
    --providers=*)  PROVIDERS="${arg#--providers=}" ;;
    --containers=*) CONTAINERS="${arg#--containers=}" ;;
    # --plan 은 Task 11(apply-plan-profile)이 소비한다
    --plan=*)       PLAN="${arg#--plan=}" ;;
    -*)             echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *)              ECC_LANGS[${#ECC_LANGS[@]}]="$arg" ;;
  esac
done
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)" || exit 64

if [ "${INSTALL_PARSE_ONLY:-0}" = "1" ]; then
  echo "HARNESSES=$HARNESSES"
  echo "PROVIDERS=$PROVIDERS"
  echo "CONTAINERS=$CONTAINERS"
  echo "PLAN=$PLAN"
  echo "ECC_LANGS=${ECC_LANGS[*]:-}"
  exit 0
fi

say()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }
note() { printf '   %s\n' "$1"; }

backup_and_copy() { # <src> <dst>
  if [ -f "$2" ] && ! cmp -s "$1" "$2"; then
    cp "$2" "$2.bak-$STAMP"
    note "백업: $2 → $2.bak-$STAMP"
  fi
  mkdir -p "$(dirname "$2")"
  cp "$1" "$2"
  note "배치: $2"
}

say "1/7 필수 도구 확인"
MISSING=""
for c in git curl python3 jq; do
  command -v "$c" >/dev/null 2>&1 || MISSING="$MISSING $c"
done
if [ -n "$MISSING" ]; then
  echo "누락:$MISSING" >&2
  if [ "$(uname)" = "Darwin" ]; then
    echo "  → brew install$MISSING" >&2
  fi
  exit 1
fi
command -v claude >/dev/null 2>&1 || note "⚠️ claude CLI 미설치 — https://claude.com/claude-code 참조" >&2
note "OK"

say "2/7 opencode"
if [ -x "$HOME/.opencode/bin/opencode" ]; then
  note "이미 설치됨: $("$HOME/.opencode/bin/opencode" --version 2>/dev/null || echo '?')"
else
  curl -fsSL https://opencode.ai/install | bash
fi

say "3/7 ECC (everything-claude-code)"
if [ "${#ECC_LANGS[@]}" -eq 0 ]; then
  note "언어 인자 없음 — ECC 설치 스킵 (예: ./install.sh --claude typescript python)"
else
  if [ -d "$ECC_DIR/.git" ]; then
    git -C "$ECC_DIR" pull --ff-only || note "⚠️ ECC pull 실패 — 기존 체크아웃으로 진행" >&2
  else
    git clone "$ECC_REPO" "$ECC_DIR"
  fi
  ( cd "$ECC_DIR" && ./install.sh "${ECC_LANGS[@]}" )
fi

say "4/7 superpowers 플러그인"
case " $HARNESSES " in
  *" claude "*)
    if command -v claude >/dev/null 2>&1; then
      if claude plugin list 2>/dev/null | grep -q 'superpowers@superpowers-dev'; then
        note "이미 설치됨 — 스킵"
      else
        if claude plugin marketplace list 2>/dev/null | grep -q 'superpowers-dev'; then
          note "마켓플레이스 이미 등록됨 — 스킵"
        else
          if claude plugin marketplace add obra/superpowers; then
            note "마켓플레이스 등록: superpowers-dev"
          else
            note "⚠️ superpowers 마켓플레이스 등록 실패 — 수동 설치: claude plugin install superpowers@superpowers-dev" >&2
          fi
        fi
        if claude plugin install superpowers@superpowers-dev; then
          note "설치됨"
        else
          note "⚠️ superpowers 플러그인 설치 실패 — 수동 설치: claude plugin install superpowers@superpowers-dev" >&2
        fi
      fi
    else
      note "claude CLI 없음 — 스킵"
    fi
    ;;
  *) note "claude 하네스 미선택 — 스킵" ;;
esac

say "5/7 전역 자산 배치 (하네스: $HARNESSES)"

# v1 레이아웃 잔재 정리 — 구 경로에서 설치된 스킬은 그대로 두되 안내만 한다.
if [ -d "$KIT_DIR/global" ]; then
  note "⚠️ 구 global/ 디렉터리가 남아 있다 — v2 는 adapters/ 를 쓴다" >&2
fi

for h in $HARNESSES; do
  case "$h" in
    claude)
      mkdir -p "$HOME/.claude/skills"
      for d in "$KIT_DIR"/adapters/claude/global/skills/*/; do
        [ -d "$d" ] || continue
        name=$(basename "$d")
        rm -rf "$HOME/.claude/skills/$name"
        cp -R "$d" "$HOME/.claude/skills/$name"
        note "스킬: ~/.claude/skills/$name"
      done
      ;;
    codex)
      mkdir -p "$HOME/.codex/prompts"
      for f in "$KIT_DIR"/adapters/codex/global/prompts/*.md; do
        [ -f "$f" ] || continue
        backup_and_copy "$f" "$HOME/.codex/prompts/$(basename "$f")"
      done
      note "codex config.toml 권장 설정은 자동 병합하지 않는다 — 남은 수동 단계 안내 참조"
      ;;
  esac
done

# 온보딩 절차 본문은 하네스 무관 — 두 어댑터의 래퍼가 모두 이 경로를 읽는다.
backup_and_copy "$KIT_DIR/core/onboard/ONBOARD-PROCEDURE.md" \
                "$HOME/.config/orchestrate/ONBOARD-PROCEDURE.md"
backup_and_copy "$KIT_DIR/core/opencode/opencode.json" "$HOME/.config/opencode/opencode.json"
backup_and_copy "$KIT_DIR/core/opencode/model-doctor.sh" "$HOME/.config/opencode/model-doctor.sh"
backup_and_copy "$KIT_DIR/core/opencode/provider-models.json" "$HOME/.config/opencode/provider-models.json"
chmod +x "$HOME/.config/opencode/model-doctor.sh"

if [ ! -f "$HOME/.config/opencode/secrets.env" ]; then
  cp "$KIT_DIR/core/opencode/secrets.env.example" "$HOME/.config/opencode/secrets.env"
  chmod 600 "$HOME/.config/opencode/secrets.env"
  note "생성: ~/.config/opencode/secrets.env (키 입력 필요)"
else
  note "유지: ~/.config/opencode/secrets.env (덮어쓰지 않음)"
fi

say "6/7 모델 프로바이더"
if [ -z "$PROVIDERS" ]; then
  if [ -t 0 ]; then
    echo "   자격증명(키 또는 구독)을 가진 프로바이더를 쉼표로 입력한다."
    echo "   선택지: qwen(키) openai(구독/키) xai(구독) antigravity(키+로컬프록시)"
    printf '   > '
    read -r PROVIDERS
  else
    echo "   비대화형 실행 — --providers= 로 명시하거나 나중에 gen-policy.sh 를 직접 실행할 것" >&2
  fi
fi
if [ -n "$PROVIDERS" ]; then
  POLICY="$HOME/.config/opencode/model-policy.json"
  if [ -f "$POLICY" ]; then
    cp "$POLICY" "$POLICY.bak-$STAMP" || {
      echo "백업 실패 — 정책 덮어쓰기를 중단한다" >&2
      exit 73
    }
    note "백업: $POLICY.bak-$STAMP"
  fi
  bash "$KIT_DIR/core/opencode/gen-policy.sh" "$PROVIDERS" "$POLICY" || {
    note "⚠️ 체인 생성 실패 — core/opencode/gen-policy.sh 를 직접 실행해 원인을 확인할 것" >&2
  }
else
  note "프로바이더 미선택 — model-policy.json 을 건드리지 않는다"
fi

if [ -n "$CONTAINERS" ]; then
  say "컨테이너 설치"
  old_ifs="$IFS"
  IFS=','
  set -f
  for c in $CONTAINERS; do
    if [ -d "$KIT_DIR/containers/$c" ]; then
      note "$c: cd $KIT_DIR/containers/$c && docker compose up -d 를 직접 실행할 것"
      note "     (설치 위치·권한은 머신마다 다르므로 자동 실행하지 않는다 — README 참조)"
    else
      note "⚠️ 알 수 없는 컨테이너: $c" >&2
    fi
  done
  set +f
  IFS="$old_ifs"
fi

case " $HARNESSES " in
  *" claude "*)
    say "Claude 요금제 프로파일"
    if [ -z "$PLAN" ]; then
      echo "   요금제를 고른다 (엔터 = 건너뛰기, 현재 설정 유지)"
      echo "   토큰 예산(사고 10000 · 압축 75%)은 세 프로파일 공통이다 — 요금제는 모델만 가른다."
      echo "   pro   — 메인 sonnet · worker haiku"
      echo "   max5  — 메인 opus   · worker haiku"
      echo "   max20 — 메인 유지   · worker sonnet"
      printf '   > '
      read -r PLAN
    fi
    if [ -n "$PLAN" ]; then
      bash "$KIT_DIR/adapters/claude/global/apply-plan-profile.sh" "$PLAN" \
        || note "⚠️ 프로파일 적용 실패 (위 stderr 참조)"
    else
      note "요금제 미선택 — 모델·토큰 설정을 건드리지 않는다"
    fi
    ;;
esac

say "7/7 검증"
if [ -f "$HOME/.config/opencode/model-policy.json" ]; then
  # 설치 직후 인증 미완은 정상이라 model-doctor 실패를 종료 코드에 전파하지 않는다.
  bash "$HOME/.config/opencode/model-doctor.sh" --skip-smoke || \
    note "⚠️ 체인 검증 실패 — 인증을 완료한 뒤 ~/.config/opencode/model-doctor.sh 를 다시 실행할 것" >&2
fi

say "남은 수동 단계"
cat <<'EOF'
   1) 키 기반 프로바이더: ~/.config/opencode/secrets.env 에 값 입력 (chmod 600)
   2) 구독 기반 프로바이더 로그인 (대화형 — 스크립트가 대신할 수 없다):
      xai:    ~/.opencode/bin/opencode auth login -p xai
      openai: ~/.opencode/bin/opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"
              → auth.openai.com/codex/device 에 출력된 코드 입력 (원격·헤드리스 서버용)
    3) 인증 후 재검증: ~/.config/opencode/model-doctor.sh
   3-1) ECC 를 갱신했다면 요금제 프로파일을 재적용한다 (ECC 가 에이전트 파일을 덮는다):
        bash adapters/claude/global/apply-plan-profile.sh <pro|max5|max20>
    4) codex 사용자: ~/.codex/config.toml 권장 설정을 adapters/codex/project/.codex/config.toml
      에서 확인해 수동 병합 (자동 병합하지 않는다)
   5) 프로젝트 온보딩:
      신규: ./new-project.sh <경로> [이름]
      기존: ./adopt-project.sh <경로>
      → 이후 하네스에서 /orchestrate-onboard 실행
EOF
echo
echo "설치 완료."
