#!/usr/bin/env bash
# 훅 생존 점검 — 훅을 실제 페이로드로 직접 실행해 기대 동작(차단/통과)을 확인한다.
# 근거: ECC 실측 사고(2026-07-28) — 훅이 조용히 죽으면 가드가 사라진 채 경고가 없다.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
FAIL=0
check() { # <설명> <기대exit> <실제exit>
  if [ "$2" -eq "$3" ]; then echo "OK   $1"; else echo "FAIL $1 (기대 exit $2, 실제 $3)"; FAIL=1; fi
}

echo '{"tool_input":{"command":"sudo ls"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: sudo 차단" 2 $?
echo '{"tool_input":{"command":"rm -rf /tmp/x"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: rm -rf 차단" 2 $?
echo '{"tool_input":{"command":"git status"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: git status 통과" 0 $?

T_OK=$(mktemp /tmp/hookcheck-ok-XXXXXX.py); echo 'x = 1' > "$T_OK"
printf '{"tool_input":{"file_path":"%s"}}' "$T_OK" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: 정상 py 통과" 0 $?
T_BAD=$(mktemp /tmp/hookcheck-bad-XXXXXX.py); echo 'def broken(:' > "$T_BAD"
printf '{"tool_input":{"file_path":"%s"}}' "$T_BAD" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: 문법 오류 py 차단" 2 $?
T_DOCS=$(mktemp -d /tmp/hookcheck-docs-XXXXXX)
mkdir -p "$T_DOCS/docs/phases"
echo 'def broken(:' > "$T_DOCS/docs/phases/skip.py"
printf '{"tool_input":{"file_path":"%s"}}' "$T_DOCS/docs/phases/skip.py" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: docs/phases 하위 py 검사 제외" 0 $?
echo 'def broken(:' > "$T_DOCS/docs/check.py"
printf '{"tool_input":{"file_path":"%s"}}' "$T_DOCS/docs/check.py" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: docs 직하 py 문법 오류 차단" 2 $?
rm -f "$T_OK" "$T_BAD"
rm -rf "$T_DOCS"

if [ "$FAIL" -ne 0 ]; then
  echo "HOOK_SELFCHECK_FAIL: 훅이 기대대로 동작하지 않는다 — 원인 확인 전 위임 금지" >&2
  exit 1
fi
echo "HOOK_SELFCHECK_PASS"
