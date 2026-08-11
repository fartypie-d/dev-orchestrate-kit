#!/usr/bin/env bash
# dev-orchestrate-kit 전역 설치 (멱등) — macOS / Linux
#
# 사용법: ./install.sh [--claude] [--codex] [--containers=browser] \
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
ECC_LANG_REJECTED=0
CLAUDE_INSTALL_FAILED=0
HARNESS_FROM_FLAG=0

add_ecc_lang() { # <언어> [cli]
  _ecc_lang_arg=$1
  _ecc_lang_source=${2:-menu}
  case "$_ecc_lang_arg" in
    ""|-*) _ecc_lang_valid=0 ;;
    *[!a-zA-Z0-9_-]*) _ecc_lang_valid=0 ;;
    *) _ecc_lang_valid=1 ;;
  esac
  if [ "$_ecc_lang_valid" = "1" ]; then
    ECC_LANGS[${#ECC_LANGS[@]}]="$_ecc_lang_arg"
    return 0
  fi
  ECC_LANG_REJECTED=$((ECC_LANG_REJECTED + 1))
  if [ "$_ecc_lang_source" = "cli" ]; then
    printf '유효하지 않은 ECC 언어: %s (허용: 영문자·숫자·_·-)\n' "${_ecc_lang_arg:-(빈 값)}" >&2
  else
    printf "   ⚠️ 무시: 유효하지 않은 언어 값 '%s'\n" "$_ecc_lang_arg" >&2
  fi
  return 1
}

for arg in "$@"; do
  case "$arg" in
    --claude)       HARNESSES="${HARNESSES:+$HARNESSES }claude"; HARNESS_FROM_FLAG=1 ;;
    --codex)        HARNESSES="${HARNESSES:+$HARNESSES }codex"; HARNESS_FROM_FLAG=1 ;;
    --providers=*)  PROVIDERS="${arg#--providers=}" ;;
    --containers=*) CONTAINERS="${arg#--containers=}" ;;
    # --plan 은 Task 11(apply-plan-profile)이 소비한다
    --plan=*)       PLAN="${arg#--plan=}" ;;
    -*)             echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *)
      if ! add_ecc_lang "$arg" cli; then
        exit 64
      fi
      ;;
  esac
done
if [ "${INSTALL_SELFTEST_MENU:-0}" != "1" ]; then
  [ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)" || exit 64
fi

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

# 설치 동의는 놓치면 안 되어 /dev/tty를 보조로 쓰지만, 선택 메뉴는 파이프 입력을
# 소비하지 않고 안전한 기본값으로 진행해야 하므로 표준 입력이 터미널일 때만 연다.
is_interactive_menu() { if [ -t 0 ]; then return 0; fi; return 1; }

read_line_interactive() { # <결과 변수명>
  _line_var=$1
  _line_answer=""
  if [ "${INSTALL_SELFTEST_MENU:-0}" = "1" ]; then
    case "${_interactive_selftest_inputs:-}" in
      *'|'*)
        _line_answer=${_interactive_selftest_inputs%%|*}
        _interactive_selftest_inputs=${_interactive_selftest_inputs#*|}
        ;;
      *)
        _line_answer=${_interactive_selftest_inputs:-}
        _interactive_selftest_inputs=""
        ;;
    esac
    if [ "$_line_answer" = "__READ_FAILURE__" ]; then
      _interactive_selftest_inputs=""
      return 1
    fi
    printf -v "$_line_var" '%s' "$_line_answer"
    return 0
  fi
  if [ -t 0 ]; then
    if ! read -r "$_line_var"; then
      return 1
    fi
  elif [ -r /dev/tty ]; then
    if ! read -r "$_line_var" </dev/tty; then
      return 1
    fi
  else
    return 2
  fi
}

prompt_yes_no() { # <프롬프트> <기본값: yes|no>
  _prompt=$1
  _default=$2
  _answer=""
  case "$_default" in
    yes) _hint="Y/n" ;;
    no)  _hint="y/N" ;;
    *) echo "잘못된 기본 동의값: $_default" >&2; return 2 ;;
  esac
  printf '%s [%s] ' "$_prompt" "$_hint" >&2
  if read_line_interactive _answer; then
    :
  else
    _read_status=$?
    if [ "$_read_status" = "2" ]; then
      echo "대화형 입력이 없어 동의를 받지 못했다." >&2
    else
      echo "동의 입력을 읽지 못했다." >&2
    fi
    return 1
  fi
  case "$_answer" in
    "") [ "$_default" = "yes" ] ;;
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

choose_one() { # <프롬프트> <기본값> <값:힌트>...
  _choose_prompt=$1
  _choose_default=$2
  shift 2
  _choose_count=$#
  _choose_items=()
  _choose_index=1
  for _choose_item in "$@"; do
    _choose_items[${#_choose_items[@]}]=$_choose_item
    _choose_value=${_choose_item%%:*}
    _choose_hint=${_choose_item#*:}
    printf '   %s) %s — %s\n' "$_choose_index" "$_choose_value" "$_choose_hint" >&2
    _choose_index=$((_choose_index + 1))
  done
  _choose_attempt=0
  while [ "$_choose_attempt" -lt 3 ]; do
    printf '   %s [%s] ' "$_choose_prompt" "${_choose_default:-없음}" >&2
    if ! read_line_interactive _choose_answer; then
      echo "   입력을 읽지 못해 기본값(\"$_choose_default\")으로 진행한다." >&2
      printf '%s' "$_choose_default"
      return 0
    fi
    [ -n "$_choose_answer" ] || { printf '%s' "$_choose_default"; return 0; }
    case "$_choose_answer" in
      *[!0-9]*) _choose_valid=0 ;;
      *)
        if [ "$_choose_answer" -ge 1 ] 2>/dev/null && [ "$_choose_answer" -le "$_choose_count" ] 2>/dev/null; then
          _choose_valid=1
        else
          _choose_valid=0
        fi
        ;;
    esac
    if [ "$_choose_valid" = "1" ]; then
      _choose_index=1
      for _choose_item in "$@"; do
        if [ "$_choose_index" = "$_choose_answer" ]; then
          printf '%s' "${_choose_item%%:*}"
          return 0
        fi
        _choose_index=$((_choose_index + 1))
      done
    fi
    echo "   1부터 $_choose_count 사이의 번호를 입력할 것" >&2
    _choose_attempt=$((_choose_attempt + 1))
  done
  echo "   입력 3회 실패 — 기본값(\"$_choose_default\")으로 진행한다." >&2
  printf '%s' "$_choose_default"
}

choose_many() { # <프롬프트> <기본값> <직접 값 허용: 0|1> <값:힌트>...
  _choose_prompt=$1
  _choose_default=$2
  _choose_allow_values=$3
  shift 3
  _choose_count=$#
  _choose_items=()
  _choose_index=1
  for _choose_item in "$@"; do
    _choose_items[${#_choose_items[@]}]=$_choose_item
    _choose_value=${_choose_item%%:*}
    _choose_hint=${_choose_item#*:}
    printf '   %s) %s — %s\n' "$_choose_index" "$_choose_value" "$_choose_hint" >&2
    _choose_index=$((_choose_index + 1))
  done
  _choose_attempt=0
  while [ "$_choose_attempt" -lt 3 ]; do
    printf '   %s [%s] ' "$_choose_prompt" "${_choose_default:-없음}" >&2
    if ! read_line_interactive _choose_answer; then
      echo "   입력을 읽지 못해 기본값(\"$_choose_default\")으로 진행한다." >&2
      printf '%s' "$_choose_default"
      return 0
    fi
    [ -n "$_choose_answer" ] || { printf '%s' "$_choose_default"; return 0; }
    _choose_words=$(printf '%s' "$_choose_answer" | tr ',' ' ')
    _choose_result=""
    _choose_valid=1
    _choose_old_ifs=$IFS
    IFS=' '
    set -f
    set -- $_choose_words
    set +f
    IFS=$_choose_old_ifs
    for _choose_token in "$@"; do
      if [ -z "$_choose_token" ]; then
        _choose_valid=0
        break
      fi
      case "$_choose_token" in
        *[!0-9]*)
          if [ "$_choose_allow_values" = "1" ]; then
            _choose_value=$_choose_token
          else
            _choose_valid=0
            break
          fi
          ;;
        *)
          if [ "$_choose_token" -lt 1 ] 2>/dev/null || [ "$_choose_token" -gt "$_choose_count" ] 2>/dev/null; then
            _choose_valid=0
            break
          fi
          _choose_value=${_choose_items[$((_choose_token - 1))]%%:*}
          ;;
      esac
      if [ -z "$_choose_value" ]; then
        _choose_valid=0
        break
      fi
      case ",$_choose_result," in
        *,"$_choose_value",*) ;;
        *) _choose_result="${_choose_result:+$_choose_result,}$_choose_value" ;;
      esac
    done
    if [ "$_choose_valid" = "1" ] && [ -n "$_choose_result" ]; then
      printf '%s' "$_choose_result"
      return 0
    fi
    echo "   유효한 번호를 입력할 것" >&2
    _choose_attempt=$((_choose_attempt + 1))
  done
  echo "   입력 3회 실패 — 기본값(\"$_choose_default\")으로 진행한다." >&2
  printf '%s' "$_choose_default"
}

notify_noninteractive_harness() {
  note "비대화형 실행 — 하네스 자동 감지값($HARNESSES)을 사용한다. 명시하려면 --claude 또는 --codex." >&2
}

report_plan_skip() {
  note "요금제 미선택 — 모델·토큰 설정을 건드리지 않는다. 지정하려면 --plan=pro|max5|max20." >&2
}

report_ecc_lang_skip() {
  if [ "$ECC_LANG_REJECTED" -gt 0 ]; then
    note "입력한 언어가 모두 무효하여 ECC 설치를 건너뛴다 (허용: 영문자·숫자·_·-)" >&2
  else
    note "언어 인자 없음 — ECC 설치 스킵 (예: ./install.sh --claude typescript python)" >&2
  fi
}

detect_pm() {
  PM="none"
  PM_INSTALL=""
  PM_SYNC=""
  PM_SUDO=0
  _uname=$(uname -s)
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_UNAME:-}" ]; then
    _uname=$INSTALL_TEST_UNAME
  fi
  case "$_uname" in
    Linux)
      _os_id=""
      if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_OS_ID:-}" ]; then
        _os_id=$INSTALL_TEST_OS_ID
      elif [ -f /etc/os-release ]; then
        . /etc/os-release
        _os_id=${ID:-}
      fi
      case "$_os_id" in
        ubuntu|debian) PM="apt-get"; PM_SYNC="update"; PM_INSTALL="install -y"; PM_SUDO=1 ;;
        fedora|rhel|centos) PM="dnf"; PM_INSTALL="install -y"; PM_SUDO=1 ;;
        arch|manjaro) PM="pacman"; PM_INSTALL="-Sy --needed --noconfirm"; PM_SUDO=1 ;;
        alpine) PM="apk"; PM_SYNC="update"; PM_INSTALL="add"; PM_SUDO=1 ;;
        opensuse*|sles) PM="zypper"; PM_INSTALL="--non-interactive install"; PM_SUDO=1 ;;
      esac
      ;;
    Darwin)
      if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_UNAME:-}" ]; then
        PM="brew"
        PM_INSTALL="install"
      elif command -v brew >/dev/null 2>&1; then
        PM="brew"
        PM_INSTALL="install"
      fi
      ;;
  esac
}

install_command() {
  if [ "$PM" = "none" ] || [ -z "$MISSING" ]; then
    printf '없음'
  else
    printf '%s %s %s' "$PM" "$PM_INSTALL" "$MISSING"
  fi
}

sync_command() {
  if [ -z "$PM_SYNC" ] || [ "$PM" = "none" ] || [ -z "$MISSING" ]; then
    printf '없음'
  else
    printf '%s %s' "$PM" "$PM_SYNC"
  fi
}

print_manual_install() {
  if [ "$PM" = "none" ]; then
    echo "수동 설치 명령: 사용하는 패키지 관리자로 $MISSING 를 설치한 뒤 다시 실행할 것" >&2
  else
    echo "수동 설치 명령: $(install_command)" >&2
  fi
}

privilege_method() {
  if [ "$(id -u)" = "0" ]; then
    printf 'root'
  elif command -v sudo >/dev/null 2>&1 && sudo -n true; then
    printf 'sudo-nopass'
  else
    printf 'sudo-consent'
  fi
}

run_privileged() {
  case "$(privilege_method)" in
    root) "$@" ;;
    sudo-nopass) sudo "$@" ;;
    sudo-consent)
      if prompt_yes_no "관리자 권한으로 도구를 설치할까요?" no; then
        sudo "$@"
      else
        echo "관리자 권한 동의를 받지 못해 설치를 중단한다." >&2
        return 1
      fi
      ;;
  esac
}

dry_run_privilege() {
  if [ "$PM" = "none" ] || [ -z "$MISSING" ] || [ "$PM_SUDO" = "0" ]; then
    printf 'none'
  else
    privilege_method
  fi
}

is_claude_harness() {
  case " $HARNESSES " in
    *" claude "*) return 0 ;;
    *) return 1 ;;
  esac
}

claude_is_available() {
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_NO_CLAUDE:-0}" = "1" ]; then
    return 1
  fi
  command -v claude >/dev/null 2>&1
}

npm_is_available() {
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_NO_NPM:-0}" = "1" ]; then
    return 1
  fi
  command -v npm >/dev/null 2>&1
}

node_download_url() {
  _node_os=$(uname -s)
  _node_arch=$(uname -m)
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_NODE_UNAME:-}" ]; then
    _node_os=$INSTALL_TEST_NODE_UNAME
  fi
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_NODE_ARCH:-}" ]; then
    _node_arch=$INSTALL_TEST_NODE_ARCH
  fi
  case "$_node_os" in
    Linux) _node_os=linux ;;
    Darwin) _node_os=darwin ;;
    *) printf '미지원 운영체제: %s' "$_node_os"; return 1 ;;
  esac
  case "$_node_arch" in
    x86_64) _node_arch=x64 ;;
    aarch64|arm64) _node_arch=arm64 ;;
    *) printf '미지원 아키텍처: %s' "$_node_arch"; return 1 ;;
  esac
  printf 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-%s-%s.tar.xz' \
    "$_node_os" "$_node_arch"
}

node_bootstrap_plan() {
  if ! _node_url=$(node_download_url); then
    printf '%s' "$_node_url"
    return 0
  fi
  printf 'curl -fsSL %s → %s/.local/opt/node' "$_node_url" "$HOME"
}

prepare_claude_dry_run_plan() {
  CLAUDE_STATE=skipped
  CLAUDE_INSTALL_PLAN=없음
  NODE_BOOTSTRAP_PLAN=없음
  if ! is_claude_harness; then
    return 0
  fi
  if claude_is_available; then
    CLAUDE_STATE=present
    return 0
  fi
  CLAUDE_STATE=missing
  CLAUDE_INSTALL_PLAN='npm i -g @anthropic-ai/claude-code'
  if ! npm_is_available; then
    NODE_BOOTSTRAP_PLAN=$(node_bootstrap_plan)
  fi
}

print_claude_manual_install() {
  _claude_manual_reason=${1:-npm}
  case "$_claude_manual_reason" in
    node)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — Node.js/npm을 먼저 설치: https://nodejs.org/"
      note "   설치 후 실행: npm i -g @anthropic-ai/claude-code"
      ;;
    unsupported)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — 현재 OS/아키텍처용 Node.js를 https://nodejs.org/ 에서 설치할 것"
      note "   Node.js/npm 설치 후 실행: npm i -g @anthropic-ai/claude-code"
      ;;
    *)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — 수동 설치: npm i -g @anthropic-ai/claude-code"
      ;;
  esac
}

bootstrap_user_node() {
  NODE_BOOTSTRAP_FAILURE_REASON=node
  _node_dir="$HOME/.local/opt/node"
  if [ -x "$_node_dir/bin/node" ] && "$_node_dir/bin/node" --version >/dev/null 2>&1; then
    PATH="$_node_dir/bin:$PATH"
    export PATH
    NODE_PATH_ADDED=1
    note "기존 유저공간 Node 확인됨: $_node_dir"
    return 0
  fi
  if ! _node_url=$(node_download_url); then
    note "⚠️ $_node_url — Node.js를 설치한 뒤 다시 실행할 것"
    NODE_BOOTSTRAP_FAILURE_REASON=unsupported
    return 1
  fi
  _node_dir="$HOME/.local/opt/node"
  _node_parent=$(dirname "$_node_dir")
  _node_tmp=$(mktemp -d "${TMPDIR:-/tmp}/orchestrate-node.XXXXXX") || {
    note "⚠️ Node 임시 디렉터리를 만들지 못했다" >&2
    return 1
  }
  _node_archive="$_node_tmp/node.tar.xz"
  _node_name=${_node_url##*/}
  _node_name=${_node_name%.tar.xz}
  note "npm 없음 — 유저공간 Node를 내려받는다: $_node_url"
  if ! curl -fsSL "$_node_url" -o "$_node_archive"; then
    note "⚠️ Node 다운로드 실패: $_node_url" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if ! tar -xJf "$_node_archive" -C "$_node_tmp"; then
    note "⚠️ Node 압축 해제 실패: $_node_archive" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if [ ! -x "$_node_tmp/$_node_name/bin/node" ] || [ ! -x "$_node_tmp/$_node_name/bin/npm" ]; then
    note "⚠️ 압축 해제한 Node에서 node 또는 npm 바이너리를 찾지 못했다" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if ! mkdir -p "$_node_parent"; then
    note "⚠️ 유저공간 Node 상위 디렉터리를 만들지 못했다: $_node_parent" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if [ -e "$_node_dir" ]; then
    if ! mv "$_node_dir" "$_node_dir.bak-$STAMP"; then
      note "⚠️ 기존 유저공간 Node 백업 실패: $_node_dir" >&2
      rm -rf "$_node_tmp"
      return 1
    fi
    note "백업: $_node_dir → $_node_dir.bak-$STAMP"
  fi
  if ! mv "$_node_tmp/$_node_name" "$_node_dir"; then
    note "⚠️ 유저공간 Node 배치 실패: $_node_dir" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  rm -rf "$_node_tmp"
  PATH="$_node_dir/bin:$PATH"
  export PATH
  NODE_PATH_ADDED=1
  return 0
}

ensure_claude_cli() {
  NODE_PATH_ADDED=0
  CLAUDE_INSTALL_FAILED=0
  if ! is_claude_harness; then
    return 0
  fi
  if claude_is_available; then
    note "claude CLI 확인됨"
    return 0
  fi
  printf '   \033[1m⚠️ claude 하네스가 선택되었지만 Claude CLI가 없다 — 스킬과 훅이 동작하지 않는다.\033[0m\n'
  if ! prompt_yes_no "지금 설치할까요?" yes; then
    CLAUDE_INSTALL_FAILED=1
    print_claude_manual_install
    return 0
  fi
  if ! npm_is_available; then
    if ! bootstrap_user_node; then
      CLAUDE_INSTALL_FAILED=1
      print_claude_manual_install "$NODE_BOOTSTRAP_FAILURE_REASON"
      return 0
    fi
  fi
  note "Claude CLI 설치: npm i -g @anthropic-ai/claude-code"
  if ! npm i -g @anthropic-ai/claude-code; then
    CLAUDE_INSTALL_FAILED=1
    note "⚠️ Claude CLI npm 설치 실패"
    print_claude_manual_install
    return 0
  fi
  if claude_is_available; then
    note "Claude CLI 설치 후 확인됨"
  else
    CLAUDE_INSTALL_FAILED=1
    note "⚠️ npm 설치 후에도 claude CLI를 찾지 못했다"
    print_claude_manual_install
  fi
  return 0
}

ensure_tools() {
  MISSING=""
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_MISSING+x}" = "x" ]; then
    MISSING=$INSTALL_TEST_MISSING
  else
    for c in git curl python3 jq; do
      command -v "$c" >/dev/null 2>&1 || MISSING="${MISSING:+$MISSING }$c"
    done
  fi

  detect_pm
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ]; then
    echo "DRY_RUN PM=$PM"
    echo "DRY_RUN MISSING=$MISSING"
    echo "DRY_RUN SYNC_CMD=$(sync_command)"
    echo "DRY_RUN INSTALL_CMD=$(install_command)"
    echo "DRY_RUN PRIVILEGE=$(dry_run_privilege)"
    prepare_claude_dry_run_plan
    echo "DRY_RUN CLAUDE=$CLAUDE_STATE"
    echo "DRY_RUN CLAUDE_INSTALL=$CLAUDE_INSTALL_PLAN"
    echo "DRY_RUN NODE_BOOTSTRAP=$NODE_BOOTSTRAP_PLAN"
    if [ "$PM" = "none" ] && [ -n "$MISSING" ]; then
      print_manual_install
    fi
    return 0
  fi

  [ -n "$MISSING" ] || return 0
  echo "누락: $MISSING" >&2
  if [ "$PM" = "none" ]; then
    echo "지원하는 패키지 관리자를 찾지 못했다." >&2
    print_manual_install
    exit 1
  fi
  echo "설치 명령: $(install_command)" >&2
  # 새 이미지의 패키지 목록은 비어 있을 수 있다. 실패해도 기존 인덱스로 설치를 시도한다.
  if [ -n "$PM_SYNC" ]; then
    echo "인덱스 동기화 명령: $(sync_command)" >&2
    if [ "$PM_SUDO" = "1" ]; then
      if ! run_privileged "$PM" $PM_SYNC; then
        echo "패키지 인덱스 동기화 실패 — 기존 인덱스로 설치를 시도한다." >&2
      fi
    elif ! "$PM" $PM_SYNC; then
      echo "패키지 인덱스 동기화 실패 — 기존 인덱스로 설치를 시도한다." >&2
    fi
  fi
  if [ "$PM_SUDO" = "1" ]; then
    if ! run_privileged "$PM" $PM_INSTALL $MISSING; then
      echo "필수 도구 설치에 실패했다." >&2
      print_manual_install
      exit 1
    fi
  elif ! "$PM" $PM_INSTALL $MISSING; then
    echo "필수 도구 설치에 실패했다." >&2
    print_manual_install
    exit 1
  fi
  for c in $MISSING; do
    if ! command -v "$c" >/dev/null 2>&1; then
      echo "설치 후에도 필수 도구를 찾지 못했다: $c" >&2
      print_manual_install
      exit 1
    fi
  done
}

backup_and_copy() { # <src> <dst>
  if [ -f "$2" ] && ! cmp -s "$1" "$2"; then
    cp "$2" "$2.bak-$STAMP"
    note "백업: $2 → $2.bak-$STAMP"
  fi
  mkdir -p "$(dirname "$2")"
  cp "$1" "$2"
  note "배치: $2"
}

if [ "${INSTALL_SELFTEST_MENU:-0}" = "1" ]; then
  if is_interactive_menu; then
    echo "SELFTEST INTERACTIVE=1"
  else
    echo "SELFTEST INTERACTIVE=0"
  fi
  _interactive_selftest_inputs='1,3'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1 3'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1,3,'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1,3,1'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs=''
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='9|9|9'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='x|x|x'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='2'
  _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음")
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs=''
  _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음")
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='9|9|9'
  _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음")
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='x|x|x'
  _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음")
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='__READ_FAILURE__'
  _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독")
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='__READ_FAILURE__'
  _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음")
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='typescript,--config,/tmp/evil.json'
  _ecc_choices=$(choose_many "ECC 언어" "" 1 "typescript:TypeScript")
  _ecc_old_ifs=$IFS
  IFS=,
  set -f
  for _ecc_lang in $_ecc_choices; do
    if ! add_ecc_lang "$_ecc_lang"; then
      :
    fi
  done
  set +f
  IFS=$_ecc_old_ifs
  echo "SELFTEST ECC=${ECC_LANGS[*]:-}"
  notify_noninteractive_harness
  report_plan_skip
  ECC_LANGS=()
  ECC_LANG_REJECTED=0
  report_ecc_lang_skip
  if ! add_ecc_lang '--config'; then
    :
  fi
  if ! add_ecc_lang '/tmp/evil.json'; then
    :
  fi
  report_ecc_lang_skip
  exit 0
fi

if [ "$HARNESS_FROM_FLAG" = "0" ] && [ "${INSTALL_DRY_RUN:-0}" != "1" ] && is_interactive_menu; then
  case "$HARNESSES" in
    "claude codex") _harness_default=both ;;
    *) _harness_default=$HARNESSES ;;
  esac
  _harness_choice=$(choose_one "하네스를 고른다" "$_harness_default" \
    "claude:Claude Code" "codex:Codex" "both:둘 다")
  case "$_harness_choice" in
    both) HARNESSES="claude codex" ;;
    *) HARNESSES=$_harness_choice ;;
  esac
elif [ "$HARNESS_FROM_FLAG" = "0" ] && [ "${INSTALL_DRY_RUN:-0}" != "1" ]; then
  notify_noninteractive_harness
fi

say "1/7 필수 도구 확인"
ensure_tools
if [ "${INSTALL_DRY_RUN:-0}" = "1" ]; then
  exit 0
fi
ensure_claude_cli
if [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
  note "Claude CLI 설치 실패 — 아래 남은 수동 단계를 확인할 것"
else
  note "OK"
fi

say "2/7 opencode"
if [ -x "$HOME/.opencode/bin/opencode" ]; then
  note "이미 설치됨: $("$HOME/.opencode/bin/opencode" --version 2>/dev/null || echo '?')"
else
  curl -fsSL https://opencode.ai/install | bash
fi

say "3/7 ECC (everything-claude-code)"
if [ "${#ECC_LANGS[@]}" -eq 0 ]; then
  if [ "${INSTALL_DRY_RUN:-0}" != "1" ] && is_interactive_menu; then
    _ecc_choices=$(choose_many "ECC 언어를 고른다 (직접 입력도 가능)" "" 1 \
      "typescript:TypeScript" "python:Python" "golang:Go" "vue:Vue" "react-native:React Native")
    if [ -n "$_ecc_choices" ]; then
      _ecc_old_ifs=$IFS
      IFS=,
      set -f
      for _ecc_lang in $_ecc_choices; do
        if ! add_ecc_lang "$_ecc_lang"; then
          :
        fi
      done
      set +f
      IFS=$_ecc_old_ifs
    fi
  fi
  if [ "${#ECC_LANGS[@]}" -eq 0 ]; then
    report_ecc_lang_skip
  fi
fi
if [ "${#ECC_LANGS[@]}" -gt 0 ]; then
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
  if is_interactive_menu; then
    PROVIDERS=$(choose_many "프로바이더를 고른다" "" 0 \
      "openai:구독 또는 키" "xai:구독" "qwen:키" "antigravity:키+로컬프록시")
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
      # browser 는 서브모듈(insane-cloak)이다 — 빈 디렉터리면 먼저 init 안내
      if [ "$c" = "browser" ] && [ ! -f "$KIT_DIR/containers/browser/docker-compose.yml" ]; then
        note "browser: 서브모듈 미초기화 — git submodule update --init containers/browser 먼저 실행할 것"
      fi
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
      echo "   토큰 예산(사고 10000 · 압축 75%)은 세 프로파일 공통이다 — 요금제는 모델만 가른다."
      if is_interactive_menu; then
        PLAN=$(choose_one "요금제를 고른다" skip \
          "pro:메인 sonnet · worker haiku" "max5:메인 opus · worker haiku" \
          "max20:메인 유지 · worker sonnet" "skip:건드리지 않음")
      fi
    fi
    [ "$PLAN" = "skip" ] && PLAN=""
    if [ -n "$PLAN" ]; then
      bash "$KIT_DIR/adapters/claude/global/apply-plan-profile.sh" "$PLAN" \
        || note "⚠️ 프로파일 적용 실패 (위 stderr 참조)"
    else
      report_plan_skip
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
if [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
  cat <<'EOF'
    6) Claude CLI 수동 설치: npm i -g @anthropic-ai/claude-code
       npm이 없다면 Node.js/npm을 먼저 설치: https://nodejs.org/
EOF
fi
if [ "${NODE_PATH_ADDED:-0}" = "1" ]; then
  cat <<EOF
    7) 유저공간 Node 경로를 셸 rc 파일에 영구 등록:
       export PATH="$HOME/.local/opt/node/bin:\$PATH"
EOF
fi
echo
if [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
  echo "설치 완료 (일부 항목 수동 조치 필요)."
else
  echo "설치 완료."
fi
