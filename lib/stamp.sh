#!/usr/bin/env bash
# 프로젝트 스캐폴드 공통 함수 — new-project.sh 와 adopt-project.sh 가 공유한다.
# macOS 기본 bash 3.2 호환: mapfile·연관배열 미사용.

# 설치된 하네스 CLI 를 감지한다. stdout: "claude" | "codex" | "claude codex"
stamp_detect_harness() {
  _found=""
  command -v claude >/dev/null 2>&1 && _found="claude"
  command -v codex  >/dev/null 2>&1 && _found="${_found:+$_found }codex"
  if [ -z "$_found" ]; then
    echo "claude·codex CLI 를 찾을 수 없다 — --claude 또는 --codex 로 명시할 것" >&2
    return 1
  fi
  echo "$_found"
}

# core/project-template + 선택 하네스의 adapters/<h>/project 를 TARGET 에 복사한다.
# 기존 파일은 절대 덮지 않는다 (rsync --ignore-existing 과 동일 의미).
# 이번 호출에서 "실제로 새로 복사된" 파일 목록을 TARGET/.orchestrate/.stamp-copied
# 에 기록한다 (매 호출마다 덮어써 초기화). stamp_placeholders 가 이 목록만 치환
# 대상으로 삼아, 대상 저장소가 원래부터 갖고 있던 파일은 절대 건드리지 않는다 —
# 키트 자신을 대상(adopt)으로 실행하면 core/project-template/ 원본, 문서 코드블록
# 등에 __PROJECT__ 문자열이 정당하게 존재할 수 있으므로 전체 트리 grep 은 위험하다.
stamp_copy() { # <KIT_DIR> <TARGET> <HARNESSES>
  _kit="$1"; _target="$2"; _harnesses="$3"
  mkdir -p "$_target/.orchestrate"
  _stamp_manifest="$_target/.orchestrate/.stamp-copied"
  : > "$_stamp_manifest"
  _stamp_copy_tree "$_kit/core/project-template" "$_target"
  _stamp_copy_tree "$_kit/core/scripts" "$_target/scripts"
  for _h in $_harnesses; do
    [ -d "$_kit/adapters/$_h/project" ] && _stamp_copy_tree "$_kit/adapters/$_h/project" "$_target"
  done
}

# cp -R 은 기존 파일을 덮으므로 파일 단위로 존재 여부를 확인하며 복사한다.
# 실제로 복사한 파일만 $_stamp_manifest 에 append 한다 ($_stamp_manifest 는
# stamp_copy 가 미리 설정해 둔 전역 변수 — while 이 파이프의 서브셸에서 돌아도
# 파일 append 는 서브셸 경계와 무관하게 디스크에 그대로 반영된다).
_stamp_copy_tree() { # <SRC_DIR> <DST_DIR>
  _src="$1"; _dst="$2"
  [ -d "$_src" ] || return 0
  mkdir -p "$_dst"
  ( cd "$_src" && find . -type d ) | while IFS= read -r _d; do
    mkdir -p "$_dst/$_d"
  done
  ( cd "$_src" && find . -type f ) | while IFS= read -r _f; do
    if [ ! -e "$_dst/$_f" ]; then
      cp "$_src/$_f" "$_dst/$_f"
      echo "$_dst/$_f" >> "$_stamp_manifest"
    fi
  done
}

# __PROJECT__ 플레이스홀더를 프로젝트명으로 치환한다 (perl 은 macOS/Linux 공통).
# 치환 범위는 stamp_copy 가 방금 실제로 복사한 파일(.orchestrate/.stamp-copied
# 목록)로 한정한다 — 대상 트리 전체를 grep 하지 않으므로, 대상이 원래부터
# 가지고 있던 __PROJECT__ 포함 파일은 절대 건드리지 않는다.
stamp_placeholders() { # <TARGET> <NAME>
  _target="$1"; _name="$2"
  _stamp_manifest="$_target/.orchestrate/.stamp-copied"
  [ -f "$_stamp_manifest" ] || return 0
  while IFS= read -r _f; do
    [ -f "$_f" ] || continue
    grep -q '__PROJECT__' "$_f" 2>/dev/null || continue
    perl -pi -e "s/__PROJECT__/$_name/g" "$_f"
  done < "$_stamp_manifest"
  return 0
}

# 실행 권한·작업 디렉터리·gitignore 를 정리한다. 중복 없이 append 하므로 멱등이다.
stamp_finalize() { # <TARGET>
  _target="$1"
  chmod +x "$_target"/scripts/*.sh 2>/dev/null || true
  chmod +x "$_target"/.claude/hooks/*.sh 2>/dev/null || true
  mkdir -p "$_target/.orchestrate"
  touch "$_target/.gitignore"
  for _line in ".orchestrate/" ".claude/settings.local.json" ".DS_Store"; do
    grep -qxF "$_line" "$_target/.gitignore" || echo "$_line" >> "$_target/.gitignore"
  done
}
