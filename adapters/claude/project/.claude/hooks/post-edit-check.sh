#!/usr/bin/env bash
# PostToolUse(Edit|Write) 훅 — 수정 파일 문법 검증. exit 2 = 실패 피드백을 claude에 전달
set -uo pipefail
FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE" ] || [ ! -f "$FILE" ] && exit 0
case "$FILE" in
  */DOCs/*|*/.agents/*|*/.claude/*|*/.opencode/*) exit 0;;
esac
case "${FILE##*.}" in
  py)
    if ! python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$FILE" 2>&1; then
      echo "post-edit-check: Python 문법 오류 — $FILE" >&2; exit 2
    fi;;
  yml|yaml)
    if ! python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$FILE" 2>/dev/null; then
      echo "post-edit-check: YAML 문법 오류 — $FILE" >&2; exit 2
    fi;;
esac
exit 0
