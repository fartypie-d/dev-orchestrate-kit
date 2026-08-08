# dev-orchestrate-kit v2 (하네스 어댑터) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 키트를 core + adapters 구조로 재편해 claude+opencode / codex+opencode 두 하네스를 지원하고, 신규·기존 프로젝트 두 진입 경로와 자격증명 주도 모델 설정을 제공한다.

**Architecture:** 하네스 무관 자산(`core/`)과 하네스 전용 자산(`adapters/claude`, `adapters/codex`)을 분리한다. 두 진입 스크립트는 공통 `lib/stamp.sh`를 공유해 복사 로직을 단일화한다. 모델 정책은 고정 프로파일 대신 `provider-models.json` 매핑표에서 생성하고 `model-doctor.sh`로 실측 검증한다.

**Tech Stack:** bash(3.2 호환 — macOS 기본 bash), jq, python3(unittest), docker compose

## Global Constraints

이 값들은 스펙에서 그대로 옮긴 것이며, 모든 task의 요구사항에 암묵적으로 포함된다.

- **bash 3.2 호환 필수** — macOS 기본 bash. `mapfile`·연관배열 금지. 배열 추가는 `ARR[${#ARR[@]}]=x` 형식.
- **멱등성** — 모든 설치 스크립트는 재실행 시 동일 결과. 기존 파일은 `.bak-<STAMP>` 백업 후 교체.
- **`secrets.env`는 절대 덮어쓰지 않는다.** 없을 때만 생성하고 `chmod 600`.
- **로스터 경로는 `.claude/orchestrate.md` 유지** — codex 어댑터도 이 경로를 참조한다(호환성 결정).
- **`CLAUDE_CODE_SUBAGENT_MODEL` 은 어떤 settings.json 에도 넣지 않는다** — 리뷰어 모델까지 덮어쓴 사고 전례.
- **컨테이너 포트는 127.0.0.1 바인딩 고정** — CDP·antigravity 프록시 모두 무인증.
- **`CLOAKSERVE_IDLE_TIMEOUT` 값은 초 단위 숫자만** — `"30m"` 은 파싱 실패로 기동 불가.
- **모델 목록을 문서에 하드코딩하지 않는다** — `opencode models` 실측이 단일 진실 소스.
- 문서·주석·출력 메시지는 한국어. 코드 식별자는 영어.

## 진행 순서

Task 1이 모든 후속 task의 전제다(경로 재배치). Task 2~3은 Task 1에, Task 6은 Task 2~5에 의존한다.
Task 9(컨테이너)와 Task 10(문서)은 Task 1 이후 언제든 가능하다.

### 도그푸딩 — 이 키트로 이 키트를 만든다

키트 저장소 자체에는 오케스트레이션 자산이 없다(실측: `.claude/orchestrate.md`·`.opencode/agent/`·
`scripts/run-delegation.sh`·`AGENTS.md` 전부 부재). Task 12 에서 키트를 **자기 자신의 첫 사용자**로
만든다 — 팀원에게 배포하기 전에 `adopt-project.sh` 를 실제 기존 저장소에 적용해 보는 유일한 기회다.

**부트스트랩 제약**: 도그푸딩에 쓸 `adopt-project.sh` 자체가 Task 3 의 산출물이다. 따라서:

| 구간 | 실행 방식 | 이유 |
|---|---|---|
| Task 1 | 메인이 직접 | `git mv` 가 후속 전제를 만든다. 실패 시 전부 무너지는데 작업량은 최소(89줄) |
| Task 2~3 | Claude 서브에이전트 | 아직 위임 인프라가 없다 (부트스트랩 구간) |
| **Task 12** | 메인이 직접 | 도그푸딩 셋업 — 여기서 위임 인프라가 생긴다 |
| Task 4~11 | **opencode 위임 + 리뷰어** | 개선한 워크플로우를 실제로 사용 |

Task 9·10 은 Task 12 이후로 미뤄 위임 대상에 포함시킨다.

---

### Task 1: 레포 재배치 — core/adapters 구조

**Files:**
- Move: `project-template/scripts/` → `core/scripts/`
- Move: `project-template/{AGENTS.md,CLAUDE.md,opencode.json,.opencode/,DOCs/,.claude/orchestrate.md,.claude/task-templates/}` → `core/project-template/` (CLAUDE.md 제외 — 아래 참조)
- Move: `project-template/CLAUDE.md` → `adapters/claude/project/CLAUDE.md`
- Move: `project-template/.claude/{hooks/,settings.json,agents/}` → `adapters/claude/project/.claude/`
- Move: `global/claude/` → `adapters/claude/global/`
- Move: `global/opencode/{opencode.json,secrets.env.example}` → `core/opencode/`
- Move: `global/opencode/model-policy.json` → `core/opencode/profiles/antigravity.json`
- Modify: `tests/test_phase_tools.py:10`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 없음 (최초 task)
- Produces: 후속 task가 참조하는 디렉터리 배치. 정확한 경로:
  - `core/scripts/run-delegation.sh`, `core/scripts/phase-tools.py`, `core/scripts/hook-selfcheck.sh`
  - `core/project-template/.claude/orchestrate.md` (로스터, `__PROJECT__` 플레이스홀더 포함)
  - `adapters/claude/project/.claude/hooks/bash-guard.sh`
  - `adapters/claude/global/skills/orchestrate/SKILL.md`
  - `core/opencode/profiles/antigravity.json`

- [ ] **Step 1: 추적 중인 `__pycache__` 제거 + .gitignore 보강**

```bash
cd ~/dev-orchestrate-kit
git rm -r --cached project-template/scripts/__pycache__ tests/__pycache__
printf '__pycache__/\n*.pyc\n' >> .gitignore
```

- [ ] **Step 2: 디렉터리 생성 후 git mv 로 이동 (히스토리 보존)**

```bash
cd ~/dev-orchestrate-kit
mkdir -p core/scripts core/opencode/profiles core/onboard core/project-template/.claude
mkdir -p adapters/claude/global adapters/claude/project/.claude
mkdir -p adapters/codex/global/prompts adapters/codex/project/.codex

git mv project-template/scripts/run-delegation.sh      core/scripts/
git mv project-template/scripts/phase-tools.py         core/scripts/
git mv project-template/scripts/phase-claim.sh         core/scripts/
git mv project-template/scripts/phase-close.sh         core/scripts/
git mv project-template/scripts/orchestrate-janitor.sh core/scripts/
git mv project-template/scripts/hook-selfcheck.sh      core/scripts/
git mv project-template/scripts/docs-index.py          core/scripts/
git mv project-template/scripts/session-cost.py        core/scripts/

git mv project-template/AGENTS.md                  core/project-template/
git mv project-template/opencode.json              core/project-template/
git mv project-template/.opencode                  core/project-template/.opencode
git mv project-template/DOCs                       core/project-template/DOCs
git mv project-template/.claude/orchestrate.md     core/project-template/.claude/
git mv project-template/.claude/task-templates     core/project-template/.claude/task-templates

git mv project-template/CLAUDE.md                  adapters/claude/project/
git mv project-template/.claude/hooks              adapters/claude/project/.claude/hooks
git mv project-template/.claude/settings.json      adapters/claude/project/.claude/
git mv project-template/.claude/agents             adapters/claude/project/.claude/agents

git mv global/claude/skills        adapters/claude/global/skills
git mv global/claude/settings-env.md adapters/claude/global/
git mv global/opencode/opencode.json       core/opencode/
git mv global/opencode/secrets.env.example core/opencode/
git mv global/opencode/model-policy.json   core/opencode/profiles/antigravity.json

rmdir project-template/.claude project-template/scripts project-template global/claude global/opencode global 2>/dev/null || true
```

- [ ] **Step 3: 테스트가 새 경로를 보도록 수정**

`tests/test_phase_tools.py` 10번 줄을 교체한다:

```python
TOOLS = Path(__file__).resolve().parents[1] / "core/scripts/phase-tools.py"
```

- [ ] **Step 4: 테스트 실행 — 이동 후에도 통과해야 한다**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest discover -s tests -v`
Expected: PASS (기존 phase-tools 테스트 전부. 실패 시 경로 오타를 먼저 의심할 것)

- [ ] **Step 5: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add -A
git commit -m "refactor: core/adapters 구조로 자산 재배치"
```

---

### Task 2: lib/stamp.sh + new-project.sh 리팩터

**Files:**
- Create: `lib/stamp.sh`
- Modify: `new-project.sh` (전체 재작성)
- Test: `tests/test_stamp.py`

**Interfaces:**
- Consumes: Task 1의 디렉터리 배치
- Produces: 다른 스크립트가 `source`하는 함수 4개. 시그니처 고정:
  - `stamp_detect_harness()` — stdout 에 `claude`, `codex`, 또는 `claude codex` (공백 구분). 둘 다 없으면 빈 문자열 + exit 1
  - `stamp_copy <KIT_DIR> <TARGET> <HARNESSES>` — `core/project-template/` + 각 하네스의 `adapters/<h>/project/` 를 TARGET 에 복사. **기존 파일 절대 미덮음**
  - `stamp_placeholders <TARGET> <NAME>` — `__PROJECT__` → NAME 치환
  - `stamp_finalize <TARGET>` — 실행 권한 + `.orchestrate/` 생성 + .gitignore 보강

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_stamp.py` 생성:

```python
"""lib/stamp.sh 테스트 — 임시 디렉터리에 스캐폴드를 찍고 결과를 검증."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def run_bash(snippet, cwd=None):
    """lib/stamp.sh 를 source 한 뒤 snippet 을 실행한다."""
    script = f'set -eu\n. "{KIT}/lib/stamp.sh"\n{snippet}\n'
    return subprocess.run(
        ["bash", "-c", script], cwd=cwd, capture_output=True, text=True
    )


class StampTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "proj"
        self.target.mkdir()

    def test_copies_core_template_and_claude_adapter(self):
        r = run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertTrue((self.target / ".claude/orchestrate.md").exists())
        self.assertTrue((self.target / "CLAUDE.md").exists())
        self.assertTrue((self.target / ".claude/hooks/bash-guard.sh").exists())
        self.assertTrue((self.target / "scripts/run-delegation.sh").exists())

    def test_codex_harness_omits_claude_only_files(self):
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "codex"')
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / "CLAUDE.md").exists())
        self.assertFalse((self.target / ".claude/hooks").exists())

    def test_never_overwrites_existing_files(self):
        (self.target / "AGENTS.md").write_text("사용자 원본\n")
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        self.assertEqual((self.target / "AGENTS.md").read_text(), "사용자 원본\n")

    def test_placeholders_replaced(self):
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        run_bash(f'stamp_placeholders "{self.target}" "myproj"')
        roster = (self.target / ".claude/orchestrate.md").read_text()
        self.assertIn("myproj", roster)
        self.assertNotIn("__PROJECT__", roster)

    def test_finalize_sets_exec_bits_and_gitignore(self):
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        run_bash(f'stamp_finalize "{self.target}"')
        self.assertTrue(os.access(self.target / "scripts/run-delegation.sh", os.X_OK))
        self.assertTrue((self.target / ".orchestrate").is_dir())
        self.assertIn(".orchestrate/", (self.target / ".gitignore").read_text())

    def test_finalize_gitignore_is_idempotent(self):
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        run_bash(f'stamp_finalize "{self.target}"')
        run_bash(f'stamp_finalize "{self.target}"')
        lines = (self.target / ".gitignore").read_text().splitlines()
        self.assertEqual(lines.count(".orchestrate/"), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_stamp -v`
Expected: FAIL — `lib/stamp.sh: No such file or directory`

- [ ] **Step 3: lib/stamp.sh 구현**

`lib/stamp.sh` 생성:

```bash
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
stamp_copy() { # <KIT_DIR> <TARGET> <HARNESSES>
  _kit="$1"; _target="$2"; _harnesses="$3"
  _stamp_copy_tree "$_kit/core/project-template" "$_target"
  _stamp_copy_tree "$_kit/core/scripts" "$_target/scripts"
  for _h in $_harnesses; do
    [ -d "$_kit/adapters/$_h/project" ] && _stamp_copy_tree "$_kit/adapters/$_h/project" "$_target"
  done
}

# cp -R 은 기존 파일을 덮으므로 파일 단위로 존재 여부를 확인하며 복사한다.
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
    fi
  done
}

# __PROJECT__ 플레이스홀더를 프로젝트명으로 치환한다 (perl 은 macOS/Linux 공통).
stamp_placeholders() { # <TARGET> <NAME>
  _target="$1"; _name="$2"
  grep -rl '__PROJECT__' "$_target" 2>/dev/null | while IFS= read -r _f; do
    perl -pi -e "s/__PROJECT__/$_name/g" "$_f"
  done
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_stamp -v`
Expected: PASS (6개 테스트 전부)

- [ ] **Step 5: new-project.sh 를 공통 함수 기반으로 재작성**

`new-project.sh` 전체를 교체:

```bash
#!/usr/bin/env bash
# 새 프로젝트에 오케스트레이션 스캐폴드를 stamp — macOS / Linux
#
# 사용법: ./new-project.sh <프로젝트경로> [프로젝트명] [--claude|--codex|--both]
#   프로젝트명 생략 시 디렉터리 이름 사용. 하네스 생략 시 설치된 CLI 자동 감지.
#   기존 파일은 절대 덮어쓰지 않는다.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_DIR/lib/stamp.sh"

TARGET=""
NAME=""
HARNESSES=""
for arg in "$@"; do
  case "$arg" in
    --claude) HARNESSES="claude" ;;
    --codex)  HARNESSES="codex" ;;
    --both)   HARNESSES="claude codex" ;;
    -*) echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *) if [ -z "$TARGET" ]; then TARGET="$arg"; elif [ -z "$NAME" ]; then NAME="$arg"; fi ;;
  esac
done

[ -n "$TARGET" ] || { echo "usage: ./new-project.sh <프로젝트경로> [프로젝트명] [--claude|--codex|--both]" >&2; exit 64; }
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"
[ -n "$NAME" ] || NAME="$(basename "$TARGET")"
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)"

echo "== 스캐폴드: $TARGET (프로젝트명: $NAME, 하네스: $HARNESSES)"
stamp_copy "$KIT_DIR" "$TARGET" "$HARNESSES"
stamp_placeholders "$TARGET" "$NAME"
stamp_finalize "$TARGET"

cat <<EOF

스캐폴드 완료.

다음 단계: 프로젝트 루트에서 하네스를 열고 \`/orchestrate-onboard\` 를 실행한다.
  → 스택 감지·로스터 작성·에이전트 생성·스킬 제안을 자동으로 수행한다.
  → 반드시 사용 가능한 가장 똑똑한 모델로 실행할 것 (명령이 모델을 확인하고 미달 시 중단한다).

수동으로 채우려면: $TARGET/.claude/orchestrate.md 의 [TODO] 를 전부 채울 것 (로스터 없이 위임 금지).
EOF
```

- [ ] **Step 6: 스크립트 실전 실행 확인**

```bash
cd ~/dev-orchestrate-kit
rm -rf /tmp/np-test && ./new-project.sh /tmp/np-test testproj --claude
grep -c '__PROJECT__' /tmp/np-test/.claude/orchestrate.md || true
```
Expected: 스캐폴드 완료 메시지 출력. `grep -c` 는 `0` (치환 완료 — grep 이 0건이면 exit 1 이므로 `|| true` 필요)

- [ ] **Step 7: 커밋**

```bash
cd ~/dev-orchestrate-kit
rm -rf /tmp/np-test
git add lib/stamp.sh new-project.sh tests/test_stamp.py
git commit -m "feat: lib/stamp.sh 공통 스캐폴드 함수 + new-project.sh 하네스 선택"
```

---

### Task 3: adopt-project.sh — 기존 프로젝트 진입 경로

**Files:**
- Create: `adopt-project.sh`
- Test: `tests/test_adopt.py`

**Interfaces:**
- Consumes: `lib/stamp.sh` 의 `stamp_detect_harness`/`stamp_copy`/`stamp_placeholders`/`stamp_finalize` (Task 2)
- Produces: 없음 (말단 스크립트)

**동작 규칙 (스펙 §2):** 기존 `.claude/settings.json`·`opencode.json` 이 이미 있으면 덮지 않고 `<파일>.kit-suggested` 로 나란히 배치한 뒤 병합 안내를 출력한다.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_adopt.py` 생성:

```python
"""adopt-project.sh 테스트 — 기존 프로젝트 비파괴 stamp 검증."""
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def adopt(target, *args):
    return subprocess.run(
        [str(KIT / "adopt-project.sh"), str(target), *args],
        capture_output=True, text=True,
    )


class AdoptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = Path(self.tmp.name) / "existing"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.proj)],
                       check=True, capture_output=True)
        (self.proj / "README.md").write_text("기존 프로젝트\n")

    def test_stamps_without_touching_existing_files(self):
        r = adopt(self.proj, "--claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / "README.md").read_text(), "기존 프로젝트\n")
        self.assertTrue((self.proj / ".claude/orchestrate.md").exists())
        self.assertTrue((self.proj / "scripts/run-delegation.sh").exists())

    def test_existing_settings_json_is_preserved_and_suggested(self):
        (self.proj / ".claude").mkdir()
        (self.proj / ".claude/settings.json").write_text('{"mine": true}\n')
        r = adopt(self.proj, "--claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / ".claude/settings.json").read_text(), '{"mine": true}\n')
        self.assertTrue((self.proj / ".claude/settings.json.kit-suggested").exists())
        self.assertIn("병합", r.stdout)

    def test_no_suggested_file_when_none_existed(self):
        adopt(self.proj, "--claude")
        self.assertTrue((self.proj / ".claude/settings.json").exists())
        self.assertFalse((self.proj / ".claude/settings.json.kit-suggested").exists())

    def test_warns_on_dirty_worktree_but_succeeds(self):
        (self.proj / "dirty.txt").write_text("uncommitted\n")
        r = adopt(self.proj, "--claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("커밋되지 않은 변경", r.stdout)

    def test_non_git_directory_is_reported(self):
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        r = adopt(plain, "--claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("git 저장소가 아니다", r.stdout)

    def test_rerun_is_idempotent(self):
        adopt(self.proj, "--claude")
        first = (self.proj / ".claude/orchestrate.md").read_text()
        r = adopt(self.proj, "--claude")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / ".claude/orchestrate.md").read_text(), first)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_adopt -v`
Expected: FAIL — `adopt-project.sh` 가 없어 `FileNotFoundError`

- [ ] **Step 3: adopt-project.sh 구현**

`adopt-project.sh` 생성 (`chmod +x` 필요):

```bash
#!/usr/bin/env bash
# 이미 작업 중인 프로젝트에 오케스트레이션 스캐폴드를 stamp — macOS / Linux
#
# 사용법: ./adopt-project.sh <프로젝트경로> [--claude|--codex|--both]
#   기존 파일은 절대 덮어쓰지 않는다. 충돌하는 설정 파일은 *.kit-suggested 로 나란히 둔다.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_DIR/lib/stamp.sh"

TARGET=""
HARNESSES=""
for arg in "$@"; do
  case "$arg" in
    --claude) HARNESSES="claude" ;;
    --codex)  HARNESSES="codex" ;;
    --both)   HARNESSES="claude codex" ;;
    -*) echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *) [ -z "$TARGET" ] && TARGET="$arg" ;;
  esac
done

[ -n "$TARGET" ] || { echo "usage: ./adopt-project.sh <프로젝트경로> [--claude|--codex|--both]" >&2; exit 64; }
[ -d "$TARGET" ] || { echo "디렉터리 없음: $TARGET" >&2; exit 66; }
TARGET="$(cd "$TARGET" && pwd)"
NAME="$(basename "$TARGET")"
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)"

echo "== 기존 프로젝트 온보딩: $TARGET (하네스: $HARNESSES)"

# 저장소 상태 보고 — 진행을 막지는 않는다 (기존 파일을 덮지 않으므로 안전).
if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  if [ -n "$(git -C "$TARGET" status --porcelain)" ]; then
    echo "   ⚠️ 커밋되지 않은 변경이 있다 — stamp 결과와 섞이지 않게 먼저 커밋하길 권한다."
  fi
else
  echo "   ⚠️ git 저장소가 아니다 — 되돌리기가 어려우므로 백업을 권한다."
fi

# 충돌 가능한 설정 파일은 먼저 .kit-suggested 로 빼둔다. stamp_copy 는 기존 파일을
# 건드리지 않으므로, 이렇게 해야 키트 권장본을 사용자가 비교할 수 있다.
SUGGESTED=""
for rel in ".claude/settings.json" "opencode.json"; do
  for h in $HARNESSES core; do
    case "$h" in
      core) src="$KIT_DIR/core/project-template/$rel" ;;
      *)    src="$KIT_DIR/adapters/$h/project/$rel" ;;
    esac
    if [ -f "$src" ] && [ -f "$TARGET/$rel" ]; then
      cp "$src" "$TARGET/$rel.kit-suggested"
      SUGGESTED="$SUGGESTED $rel"
    fi
  done
done

stamp_copy "$KIT_DIR" "$TARGET" "$HARNESSES"
stamp_placeholders "$TARGET" "$NAME"
stamp_finalize "$TARGET"

echo
echo "기본 설치 완료."
if [ -n "$SUGGESTED" ]; then
  echo
  echo "다음 파일은 기존 것을 유지했다. 키트 권장본이 .kit-suggested 로 함께 있으니 병합할 것:"
  for rel in $SUGGESTED; do echo "   $rel  ←  $rel.kit-suggested"; done
fi
cat <<EOF

다음 단계: 프로젝트 루트에서 하네스를 열고 \`/orchestrate-onboard\` 를 실행한다.
  → 프로젝트를 분석해 로스터·에이전트·가드 등급을 채우고, 필요한 스킬을 제안한다.
  → 반드시 사용 가능한 가장 똑똑한 모델로 실행할 것 (명령이 모델을 확인하고 미달 시 중단한다).
EOF
```

- [ ] **Step 4: 실행 권한 부여 후 테스트 통과 확인**

```bash
cd ~/dev-orchestrate-kit && chmod +x adopt-project.sh
python3 -m unittest tests.test_adopt -v
```
Expected: PASS (6개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add adopt-project.sh tests/test_adopt.py
git commit -m "feat: adopt-project.sh — 기존 프로젝트 비파괴 온보딩 경로"
```

---

### Task 4: provider-models.json + gen-policy.sh — 체인 생성기

**Files:**
- Create: `core/opencode/provider-models.json`
- Create: `core/opencode/gen-policy.sh`
- Create: `core/opencode/profiles/local.json`
- Modify: `core/opencode/profiles/antigravity.json` (Task 1에서 이동해 온 파일 — 주석 갱신)
- Test: `tests/test_gen_policy.py`

**Interfaces:**
- Consumes: 없음
- Produces: `core/opencode/gen-policy.sh <PROVIDERS_CSV> <OUT_PATH>` — 매핑표에서 tier 체인을 생성해 OUT_PATH 에 JSON 을 쓴다. 알 수 없는 프로바이더는 stderr 경고 후 무시. 선택 프로바이더가 하나도 유효하지 않으면 exit 65.
  생성 JSON 스키마: `{"_comment": str, "tiers": {"default": [str], "heavy": [str]}}`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_gen_policy.py` 생성:

```python
"""gen-policy.sh 테스트 — 프로바이더 조합에서 tier 체인이 생성되는지 검증."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
GEN = KIT / "core/opencode/gen-policy.sh"


def gen(providers, out):
    return subprocess.run(
        ["bash", str(GEN), providers, str(out)], capture_output=True, text=True
    )


class GenPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "model-policy.json"

    def load(self):
        return json.loads(self.out.read_text())

    def test_single_provider_produces_both_tiers(self):
        r = gen("qwen", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        policy = self.load()
        self.assertTrue(policy["tiers"]["default"])
        self.assertTrue(policy["tiers"]["heavy"])

    def test_only_selected_providers_appear(self):
        gen("qwen", self.out)
        chains = self.load()["tiers"]
        for entry in chains["default"] + chains["heavy"]:
            self.assertTrue(entry.startswith("qwencloud/"), entry)

    def test_multiple_providers_are_mixed(self):
        gen("qwen,openai,xai", self.out)
        chains = self.load()["tiers"]
        joined = " ".join(chains["default"] + chains["heavy"])
        self.assertIn("qwencloud/", joined)
        self.assertIn("openai/", joined)
        self.assertIn("xai/", joined)

    def test_gpt_is_first_in_every_tier_when_openai_selected(self):
        """GPT 우선 정책 — openai 를 고르면 두 tier 모두 1순위여야 한다."""
        gen("qwen,openai,xai", self.out)
        chains = self.load()["tiers"]
        self.assertTrue(chains["default"][0].startswith("openai/"), chains["default"])
        self.assertTrue(chains["heavy"][0].startswith("openai/"), chains["heavy"])

    def test_fallback_after_gpt_is_a_different_provider(self):
        """같은 프로바이더를 연달아 두면 한도에 함께 막혀 폴백이 무의미하다."""
        gen("qwen,openai,xai", self.out)
        heavy = self.load()["tiers"]["heavy"]
        self.assertGreater(len(heavy), 1, heavy)
        self.assertFalse(heavy[1].startswith("openai/"), heavy)

    def test_unknown_provider_warns_but_succeeds(self):
        r = gen("qwen,nosuchprovider", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nosuchprovider", r.stderr)

    def test_all_unknown_providers_fail(self):
        r = gen("nosuch,alsonope", self.out)
        self.assertEqual(r.returncode, 65)

    def test_output_is_valid_json_with_comment(self):
        gen("openai", self.out)
        policy = self.load()
        self.assertIn("_comment", policy)
        self.assertIsInstance(policy["tiers"]["default"], list)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_gen_policy -v`
Expected: FAIL — `gen-policy.sh` 없음

- [ ] **Step 3: provider-models.json 매핑표 작성**

`core/opencode/provider-models.json` 생성:

```json
{
  "_comment": "프로바이더 → 권장 모델 매핑. gen-policy.sh 가 이 표에서 tier 체인을 만든다. 모델 목록은 시드일 뿐이며 실제 가용성은 `opencode models` 로 확인한다 (model-doctor.sh). 구독 인증은 열리는 모델이 API 가격표와 다르므로 하드코딩을 신뢰하지 말 것.",
  "providers": {
    "antigravity": {
      "prefix": "antigravity",
      "credential": "ANTIGRAVITY_API_KEY",
      "auth": "key",
      "needs_provider_block": true,
      "default": ["antigravity/gemini-3.6-flash-high"],
      "heavy": ["antigravity/gemini-3.1-pro-high"]
    },
    "qwen": {
      "prefix": "qwencloud",
      "credential": "QWEN_API_KEY",
      "auth": "key",
      "needs_provider_block": true,
      "default": ["qwencloud/qwen3.7-plus", "qwencloud/deepseek-v4-pro", "qwencloud/deepseek-v4-flash-0731"],
      "heavy": ["qwencloud/qwen3.7-max"]
    },
    "openai": {
      "prefix": "openai",
      "credential": "opencode auth login -p openai",
      "auth": "oauth",
      "needs_provider_block": false,
      "default": ["openai/gpt-5.6-luna"],
      "heavy": ["openai/gpt-5.6-terra"]
    },
    "xai": {
      "prefix": "xai",
      "credential": "opencode auth login -p xai",
      "auth": "oauth",
      "needs_provider_block": false,
      "default": [],
      "heavy": ["xai/grok-4.5"]
    }
  },
  "_tier_order_note": "체인 내 우선순위. GPT(openai) 우선 정책이므로 openai 가 맨 앞이다. 그 뒤는 서로 다른 할당량 풀 순서 — openai 가 한도에 걸렸을 때 실제로 넘어갈 곳이 되도록 배치한다.",
  "tier_order": ["openai", "xai", "antigravity", "qwen"]
}
```

- [ ] **Step 4: gen-policy.sh 구현**

`core/opencode/gen-policy.sh` 생성:

```bash
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

# 선택분 중 매핑표에 있는 것만 남긴다 (bash 3.2 호환 — 배열 인덱스 추가 방식).
SELECTED=""
for p in $(echo "$PROVIDERS_CSV" | tr ',' ' '); do
  if jq -e --arg p "$p" '.providers[$p]' "$TABLE" >/dev/null 2>&1; then
    SELECTED="${SELECTED:+$SELECTED }$p"
  else
    echo "경고: 알 수 없는 프로바이더 '$p' — 무시한다 (매핑표: $TABLE)" >&2
  fi
done

if [ -z "$SELECTED" ]; then
  echo "유효한 프로바이더가 하나도 없다 — 체인을 만들 수 없다" >&2
  exit 65
fi

# tier_order 순서대로 선택된 프로바이더의 모델을 이어 붙인다.
# GPT 우선 정책은 tier_order 의 첫 항목(openai)이 담보한다 — 이 함수는 표 순서를 따를 뿐이다.
build_tier() { # <tier 이름>
  _tier="$1"
  _sel_json=$(printf '%s\n' $SELECTED | jq -R . | jq -s .)
  jq --arg t "$_tier" --argjson sel "$_sel_json" '
    [ .tier_order[] as $p
      | select($sel | index($p))
      | .providers[$p][$t][]?
    ]
  ' "$TABLE"
}

DEFAULT_CHAIN=$(build_tier default)
HEAVY_CHAIN=$(build_tier heavy)

mkdir -p "$(dirname "$OUT")"
jq -n --argjson d "$DEFAULT_CHAIN" --argjson h "$HEAVY_CHAIN" '{
  _comment: "위임 모델 폴백 체인 — scripts/run-delegation.sh 가 읽는다. 순서 = 시도 순서. gen-policy.sh 가 생성했으며 손으로 고쳐도 된다. 모델 ID 는 `opencode models` 등록분만 유효하다 — 검증은 model-doctor.sh.",
  _quota_note: "서로 다른 구독(xai·openai 등)은 별개 할당량 풀이다. 체인에 섞어두면 한쪽 한도에서 다른 쪽으로 넘어간다.",
  tiers: { default: $d, heavy: $h }
}' > "$OUT"

echo "생성: $OUT"
echo "  default: $(echo "$DEFAULT_CHAIN" | jq -r 'join(" → ")')"
echo "  heavy:   $(echo "$HEAVY_CHAIN" | jq -r 'join(" → ")')"
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd ~/dev-orchestrate-kit && chmod +x core/opencode/gen-policy.sh
python3 -m unittest tests.test_gen_policy -v
```
Expected: PASS (8개 테스트 전부 — GPT 우선·폴백 프로바이더 분리 테스트 포함)

- [ ] **Step 6: 시드 프로파일 2종 정리**

`core/opencode/profiles/local.json` 생성:

```json
{
  "_comment": "시드 프로파일 — antigravity 프록시가 없는 머신용. GPT 우선 정책에 따라 openai 가 두 tier 모두 1순위다. gen-policy.sh 결과 대신 이 파일을 그대로 쓸 수도 있다.",
  "tiers": {
    "default": ["openai/gpt-5.6-luna", "qwencloud/qwen3.7-plus", "qwencloud/deepseek-v4-pro", "qwencloud/deepseek-v4-flash-0731"],
    "heavy": ["openai/gpt-5.6-terra", "xai/grok-4.5", "qwencloud/qwen3.7-max"]
  }
}
```

`core/opencode/profiles/antigravity.json` 의 `_comment` 를 다음으로 교체:

```json
  "_comment": "시드 프로파일 — antigravity 프록시(:8045)를 쓰는 머신용. gen-policy.sh 결과 대신 이 파일을 그대로 쓸 수도 있다.",
```

- [ ] **Step 7: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add core/opencode/ tests/test_gen_policy.py
git commit -m "feat: provider-models 매핑표 + gen-policy.sh 체인 생성기 (GPT 우선)"
```

---

### Task 5: model-doctor.sh — 체인 실측 검증

**Files:**
- Create: `core/opencode/model-doctor.sh`
- Test: `tests/test_model_doctor.py`

**Interfaces:**
- Consumes: Task 4 가 만든 `model-policy.json` 스키마 (`.tiers.<name>[]`)
- Produces: `model-doctor.sh [--policy PATH] [--models-cmd CMD] [--auth-cmd CMD] [--skip-smoke]`
  - `--models-cmd` / `--auth-cmd` 는 **테스트 주입용**(기본값은 실제 opencode 호출)
  - exit 0 = 모든 tier 에 유효 항목 1개 이상, exit 1 = 유효 항목이 0인 tier 존재

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_model_doctor.py` 생성:

```python
"""model-doctor.sh 테스트 — 가짜 opencode 출력으로 체인 검증 로직만 확인."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
DOCTOR = KIT / "core/opencode/model-doctor.sh"

REGISTERED = "qwencloud/qwen3.7-plus\nqwencloud/qwen3.7-max\nopenai/gpt-5.6-luna\n"
AUTH = "OpenAI oauth\n"


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.policy = Path(self.tmp.name) / "policy.json"

    def write_policy(self, default, heavy):
        self.policy.write_text(json.dumps({"tiers": {"default": default, "heavy": heavy}}))

    def run_doctor(self):
        return subprocess.run(
            ["bash", str(DOCTOR),
             "--policy", str(self.policy),
             "--models-cmd", f"printf '{REGISTERED}'",
             "--auth-cmd", f"printf '{AUTH}'",
             "--skip-smoke"],
            capture_output=True, text=True,
        )

    def test_all_entries_registered_passes(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        r = self.run_doctor()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_unregistered_entry_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus", "qwencloud/typo-model"], ["qwencloud/qwen3.7-max"])
        r = self.run_doctor()
        self.assertEqual(r.returncode, 0, r.stdout)   # tier 에 유효 항목이 남아 있으므로 통과
        self.assertIn("qwencloud/typo-model", r.stdout)
        self.assertIn("MISSING", r.stdout)

    def test_tier_with_no_valid_entry_fails(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["xai/not-registered"])
        r = self.run_doctor()
        self.assertEqual(r.returncode, 1)
        self.assertIn("heavy", r.stdout)

    def test_missing_policy_file_exits_66(self):
        r = subprocess.run(
            ["bash", str(DOCTOR), "--policy", str(self.policy) + ".nope", "--skip-smoke"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 66)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_model_doctor -v`
Expected: FAIL — `model-doctor.sh` 없음

- [ ] **Step 3: model-doctor.sh 구현**

`core/opencode/model-doctor.sh` 생성:

```bash
#!/usr/bin/env bash
# 모델 체인 실측 검증 — 설치 마지막 단계이자 언제든 재실행 가능.
#
# 확인 항목:
#   1. model-policy.json 의 각 항목이 `opencode models` 등록분에 실재하는가
#   2. 인증 수단이 있는가 — 키(secrets.env) 또는 구독(`opencode auth list`)
#   3. tier 당 1회 스모크 호출 (--skip-smoke 로 생략 가능)
#
# 이 검증이 없으면 오타 난 모델 ID 가 조용히 폴백만 소모한다.
set -uo pipefail

POLICY="$HOME/.config/opencode/model-policy.json"
OPENCODE="$HOME/.opencode/bin/opencode"
MODELS_CMD=""
AUTH_CMD=""
SKIP_SMOKE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --policy)     POLICY="$2"; shift 2 ;;
    --models-cmd) MODELS_CMD="$2"; shift 2 ;;
    --auth-cmd)   AUTH_CMD="$2"; shift 2 ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
done

[ -f "$POLICY" ] || { echo "정책 파일 없음: $POLICY" >&2; exit 66; }
command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }

[ -n "$MODELS_CMD" ] || MODELS_CMD="$OPENCODE models"
[ -n "$AUTH_CMD" ]   || AUTH_CMD="$OPENCODE auth list"

echo "== 모델 체인 검증 ($POLICY)"

REGISTERED=$(eval "$MODELS_CMD" 2>/dev/null)
if [ -z "$REGISTERED" ]; then
  echo "   ⚠️ 등록 모델 목록이 비어 있다 — opencode 설치·인증을 먼저 확인할 것" >&2
fi

FAILED_TIERS=""
for tier in $(jq -r '.tiers | keys[]' "$POLICY"); do
  echo
  echo "-- tier: $tier"
  valid=0
  for m in $(jq -r --arg t "$tier" '.tiers[$t][]' "$POLICY"); do
    if echo "$REGISTERED" | grep -qxF "$m"; then
      echo "   OK      $m"
      valid=$((valid + 1))
    else
      echo "   MISSING $m   ← opencode models 에 없다 (오타이거나 인증 미완료)"
    fi
  done
  if [ "$valid" -eq 0 ]; then
    echo "   ❌ 이 tier 에 사용 가능한 모델이 하나도 없다"
    FAILED_TIERS="${FAILED_TIERS:+$FAILED_TIERS }$tier"
  elif [ "$SKIP_SMOKE" -eq 0 ]; then
    first=$(jq -r --arg t "$tier" '.tiers[$t][0]' "$POLICY")
    if echo "$REGISTERED" | grep -qxF "$first"; then
      echo "   스모크 호출: $first"
      if "$OPENCODE" run -m "$first" "Reply with exactly: OK" >/dev/null 2>&1; then
        echo "   OK      스모크 통과"
      else
        echo "   ⚠️ 스모크 실패 — 인증·레이트리밋을 확인할 것 (체인 폴백은 여전히 동작한다)"
      fi
    fi
  fi
done

echo
echo "-- 인증 수단"
AUTH_OUT=$(eval "$AUTH_CMD" 2>/dev/null)
echo "$AUTH_OUT" | grep -iE "oauth|api" | sed 's/^/   구독·키: /' || echo "   (auth list 출력 없음)"
if [ -f "$HOME/.config/opencode/secrets.env" ]; then
  # 값은 절대 출력하지 않는다 — 키 이름만 보고한다.
  grep -oE '^[A-Z_]+=.' "$HOME/.config/opencode/secrets.env" 2>/dev/null \
    | sed 's/=.$//' | sed 's/^/   키 설정됨: /'
fi

echo
if [ -n "$FAILED_TIERS" ]; then
  echo "❌ 사용 불가 tier: $FAILED_TIERS — model-policy.json 을 고치거나 인증을 완료할 것"
  exit 1
fi
echo "✅ 모든 tier 에 사용 가능한 모델이 있다"
exit 0
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd ~/dev-orchestrate-kit && chmod +x core/opencode/model-doctor.sh
python3 -m unittest tests.test_model_doctor -v
```
Expected: PASS (4개 테스트 전부)

- [ ] **Step 5: 이 호스트의 실제 정책으로 실행 확인**

Run: `bash ~/dev-orchestrate-kit/core/opencode/model-doctor.sh --skip-smoke`
Expected: `✅ 모든 tier 에 사용 가능한 모델이 있다` (현재 체인 8개 항목 전부 OK)

- [ ] **Step 6: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add core/opencode/model-doctor.sh tests/test_model_doctor.py
git commit -m "feat: model-doctor.sh — 체인 실측 검증(등록·인증·스모크)"
```

---

### Task 6: install.sh v2 — 하네스·프로바이더·컨테이너 선택

**Files:**
- Modify: `install.sh` (전체 재작성)
- Test: `tests/test_install_args.py`

**Interfaces:**
- Consumes: `lib/stamp.sh`(하네스 감지), `core/opencode/gen-policy.sh`, `core/opencode/model-doctor.sh`
- Produces: 없음 (최상위 진입점)

**인자 형식:** `./install.sh [--claude] [--codex] [--containers=browser,antigravity] [--providers=qwen,openai,xai,antigravity] [ECC 언어...]`

- [ ] **Step 1: 인자 파싱 실패 테스트 작성**

`tests/test_install_args.py` 생성 — 파싱만 검증하기 위해 `INSTALL_PARSE_ONLY=1` 환경변수를 쓴다:

```python
"""install.sh 인자 파싱 테스트 — INSTALL_PARSE_ONLY=1 로 부작용 없이 파싱 결과만 확인."""
import os
import subprocess
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def parse(*args):
    env = {**os.environ, "INSTALL_PARSE_ONLY": "1"}
    return subprocess.run(
        ["bash", str(KIT / "install.sh"), *args],
        capture_output=True, text=True, env=env,
    )


class InstallArgsTest(unittest.TestCase):
    def test_explicit_harness_flags(self):
        r = parse("--claude", "--codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("HARNESSES=claude codex", r.stdout)

    def test_providers_csv_parsed(self):
        r = parse("--claude", "--providers=qwen,openai")
        self.assertIn("PROVIDERS=qwen,openai", r.stdout)

    def test_containers_csv_parsed(self):
        r = parse("--claude", "--containers=browser,antigravity")
        self.assertIn("CONTAINERS=browser,antigravity", r.stdout)

    def test_ecc_languages_collected(self):
        r = parse("--claude", "typescript", "python")
        self.assertIn("ECC_LANGS=typescript python", r.stdout)

    def test_unknown_flag_exits_64(self):
        r = parse("--nosuchflag")
        self.assertEqual(r.returncode, 64)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_install_args -v`
Expected: FAIL — 현재 install.sh 는 `--claude` 를 ECC 언어로 취급하며 `HARNESSES=` 를 출력하지 않는다

- [ ] **Step 3: install.sh 상단(인자 파싱 + 파싱 전용 종료) 교체**

`install.sh` 의 `set -euo pipefail` 다음부터 `say "1/6 필수 도구 확인"` 직전까지를 다음으로 교체:

```bash
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
ECC_REPO="https://github.com/affaan-m/everything-claude-code.git"
ECC_DIR="$HOME/everything-claude-code"
STAMP=$(date +%Y%m%d-%H%M%S)
. "$KIT_DIR/lib/stamp.sh"

HARNESSES=""
PROVIDERS=""
CONTAINERS=""
ECC_LANGS=""
for arg in "$@"; do
  case "$arg" in
    --claude)        HARNESSES="${HARNESSES:+$HARNESSES }claude" ;;
    --codex)         HARNESSES="${HARNESSES:+$HARNESSES }codex" ;;
    --providers=*)   PROVIDERS="${arg#--providers=}" ;;
    --containers=*)  CONTAINERS="${arg#--containers=}" ;;
    -*)              echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *)               ECC_LANGS="${ECC_LANGS:+$ECC_LANGS }$arg" ;;
  esac
done
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)" || exit 64

if [ "${INSTALL_PARSE_ONLY:-0}" = "1" ]; then
  echo "HARNESSES=$HARNESSES"
  echo "PROVIDERS=$PROVIDERS"
  echo "CONTAINERS=$CONTAINERS"
  echo "ECC_LANGS=$ECC_LANGS"
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
```

> 주의: `say`/`note` 정의가 파싱 블록보다 뒤로 갔으므로, 파싱 블록에서는 이 함수를 쓰지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_install_args -v`
Expected: PASS (5개 테스트 전부)

- [ ] **Step 5: ECC 단계가 새 변수를 쓰도록 수정**

`install.sh` 의 ECC 블록에서 `"$#"`·`"$@"` 를 `$ECC_LANGS` 로 교체:

```bash
say "3/7 ECC (everything-claude-code)"
if [ -z "$ECC_LANGS" ]; then
  note "언어 인자 없음 — ECC 설치 스킵 (예: ./install.sh --claude typescript python)"
else
  if [ -d "$ECC_DIR/.git" ]; then
    git -C "$ECC_DIR" pull --ff-only || note "⚠️ ECC pull 실패 — 기존 체크아웃으로 진행"
  else
    git clone "$ECC_REPO" "$ECC_DIR"
  fi
  ( cd "$ECC_DIR" && ./install.sh $ECC_LANGS )
fi
```

- [ ] **Step 6: 전역 자산 배치 단계를 어댑터별로 교체**

`say "5/6 전역 자산 배치"` 블록 전체를 다음으로 교체:

```bash
say "5/7 전역 자산 배치 (하네스: $HARNESSES)"

# v1 레이아웃 잔재 정리 — 구 경로에서 설치된 스킬은 그대로 두되 안내만 한다.
[ -d "$KIT_DIR/global" ] && note "⚠️ 구 global/ 디렉터리가 남아 있다 — v2 는 adapters/ 를 쓴다"

for h in $HARNESSES; do
  case "$h" in
    claude)
      mkdir -p "$HOME/.claude/skills"
      for d in "$KIT_DIR"/adapters/claude/global/skills/*/; do
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
      note "codex config.toml 권장 설정은 자동 병합하지 않는다 — 6/7 안내 참조"
      ;;
  esac
done

# 온보딩 절차 본문은 하네스 무관 — 두 어댑터의 래퍼가 모두 이 경로를 읽는다.
backup_and_copy "$KIT_DIR/core/onboard/ONBOARD-PROCEDURE.md" \
                "$HOME/.config/orchestrate/ONBOARD-PROCEDURE.md"

backup_and_copy "$KIT_DIR/core/opencode/opencode.json"     "$HOME/.config/opencode/opencode.json"
backup_and_copy "$KIT_DIR/core/opencode/model-doctor.sh"   "$HOME/.config/opencode/model-doctor.sh"
chmod +x "$HOME/.config/opencode/model-doctor.sh"

if [ ! -f "$HOME/.config/opencode/secrets.env" ]; then
  cp "$KIT_DIR/core/opencode/secrets.env.example" "$HOME/.config/opencode/secrets.env"
  chmod 600 "$HOME/.config/opencode/secrets.env"
  note "생성: ~/.config/opencode/secrets.env (키 입력 필요)"
else
  note "유지: ~/.config/opencode/secrets.env (덮어쓰지 않음)"
fi

# 토큰 절약 env를 전역 ~/.claude/settings.json 에 병합 (claude 하네스일 때만).
# ⚠️ CLAUDE_CODE_SUBAGENT_MODEL 은 절대 넣지 않는다 — 리뷰어 모델까지 덮어쓴 사고 전례.
case "$HARNESSES" in
  *claude*)
    GS="$HOME/.claude/settings.json"
    mkdir -p "$HOME/.claude"
    [ -f "$GS" ] || echo '{}' > "$GS"
    if jq -e '.env.MAX_THINKING_TOKENS and .env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE' "$GS" >/dev/null 2>&1; then
      note "전역 settings.json 토큰 절약 env 이미 설정됨 — 스킵"
    else
      cp "$GS" "$GS.bak-$STAMP"
      jq '.env = ({"MAX_THINKING_TOKENS":"10000","CLAUDE_AUTOCOMPACT_PCT_OVERRIDE":"75"} + (.env // {}))' \
        "$GS.bak-$STAMP" > "$GS"
      note "전역 settings.json 에 토큰 절약 env 병합 (백업: $GS.bak-$STAMP)"
    fi
    ;;
esac
```

- [ ] **Step 7: 프로바이더·컨테이너 단계 추가**

Step 6 블록 다음에 삽입:

```bash
say "6/7 모델 프로바이더"
if [ -z "$PROVIDERS" ]; then
  echo "   자격증명(키 또는 구독)을 가진 프로바이더를 쉼표로 입력한다."
  echo "   선택지: qwen(키) openai(구독/키) xai(구독) antigravity(키+로컬프록시)"
  printf '   > '
  read -r PROVIDERS
fi
if [ -n "$PROVIDERS" ]; then
  POLICY="$HOME/.config/opencode/model-policy.json"
  [ -f "$POLICY" ] && cp "$POLICY" "$POLICY.bak-$STAMP" && note "백업: $POLICY.bak-$STAMP"
  bash "$KIT_DIR/core/opencode/gen-policy.sh" "$PROVIDERS" "$POLICY"
else
  note "프로바이더 미선택 — model-policy.json 을 건드리지 않는다"
fi

if [ -n "$CONTAINERS" ]; then
  say "컨테이너 설치"
  for c in $(echo "$CONTAINERS" | tr ',' ' '); do
    if [ -d "$KIT_DIR/containers/$c" ]; then
      note "$c: cd $KIT_DIR/containers/$c && docker compose up -d 를 직접 실행할 것"
      note "     (설치 위치·권한은 머신마다 다르므로 자동 실행하지 않는다 — README 참조)"
    else
      note "⚠️ 알 수 없는 컨테이너: $c"
    fi
  done
fi

say "7/7 검증"
if [ -f "$HOME/.config/opencode/model-policy.json" ]; then
  bash "$HOME/.config/opencode/model-doctor.sh" --skip-smoke || \
    note "⚠️ 체인 검증 실패 — 인증을 완료한 뒤 ~/.config/opencode/model-doctor.sh 를 다시 실행할 것"
fi
```

- [ ] **Step 8: 마지막 수동 단계 안내 갱신**

`say "6/6 남은 수동 단계"` 로 시작하는 마지막 블록 전체를 교체:

```bash
say "남은 수동 단계"
cat <<'EOF'
   1) 키 기반 프로바이더: ~/.config/opencode/secrets.env 에 값 입력 (chmod 600)
   2) 구독 기반 프로바이더 로그인 (대화형 — 스크립트가 대신할 수 없다):
      xai:    ~/.opencode/bin/opencode auth login -p xai
      openai: ~/.opencode/bin/opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"
              → auth.openai.com/codex/device 에 출력된 코드 입력 (원격·헤드리스 서버용)
   3) 인증 후 재검증: ~/.config/opencode/model-doctor.sh
   4) codex 사용자: ~/.codex/config.toml 권장 설정을 adapters/codex/project/.codex/config.toml
      에서 확인해 수동 병합 (자동 병합하지 않는다)
   5) 프로젝트 온보딩:
      신규: ./new-project.sh <경로> [이름]
      기존: ./adopt-project.sh <경로>
      → 이후 하네스에서 /orchestrate-onboard 실행
EOF
echo
echo "설치 완료."
```

- [ ] **Step 9: 전체 테스트 + 파싱 스모크**

```bash
cd ~/dev-orchestrate-kit
python3 -m unittest discover -s tests -v
INSTALL_PARSE_ONLY=1 bash install.sh --claude --providers=qwen,openai typescript
```
Expected: 모든 테스트 PASS. 파싱 출력에 `HARNESSES=claude`, `PROVIDERS=qwen,openai`, `ECC_LANGS=typescript`

- [ ] **Step 10: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add install.sh tests/test_install_args.py
git commit -m "feat: install.sh v2 — 하네스·프로바이더·컨테이너 선택 + 체인 검증"
```

---

### Task 7: ONBOARD-PROCEDURE.md + claude 스킬 래퍼

**Files:**
- Create: `core/onboard/ONBOARD-PROCEDURE.md`
- Create: `adapters/claude/global/skills/orchestrate-onboard/SKILL.md`

**Interfaces:**
- Consumes: `core/project-template/.claude/orchestrate.md` 의 [TODO] 구조, `adapters/claude/project/.claude/hooks/bash-guard.sh` 의 `FORBIDDEN`/`RESTART_ONLY`/`FOREIGN` 변수명
- Produces: 절차 본문 경로 `~/.config/orchestrate/ONBOARD-PROCEDURE.md` (install.sh 가 배치) — Task 8 의 codex 프롬프트도 이 경로를 읽는다

- [ ] **Step 1: 절차 본문 작성**

`core/onboard/ONBOARD-PROCEDURE.md` 생성:

```markdown
# /orchestrate-onboard 절차 (하네스 공통)

> 이 파일이 절차의 단일 소스다. claude 스킬과 codex 프롬프트는 이 파일을 읽는 얇은 래퍼일 뿐이다.
> 설치 위치: `~/.config/orchestrate/ONBOARD-PROCEDURE.md`

## 0. 모델 게이트 — 미달이면 여기서 중단한다

이 명령은 프로젝트 전체를 읽고 로스터·에이전트·스킬을 설계한다. **사용 가능한 가장 똑똑한
모델로 실행해야 한다.** 현재 모델을 확인하고, 미달이면 전환 방법을 안내한 뒤 **작업을 시작하지 말 것**.

- claude: opus 이상(fable 포함)이 아니면 → `/model` 로 전환 후 재실행하도록 안내하고 중단.
- codex: 설치본에서 선택 가능한 최상위 모델 + `model_reasoning_effort = "high"` 이상이
  아니면 → 설정 방법을 안내하고 중단.

## 1. 스택 감지 (실측만 — 추측 금지)

다음을 **파일을 읽어서** 확인한다. 없으면 "없음"으로 기록하고 넘어간다.

- 언어·프레임워크: 매니페스트(`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml` 등)
- 빌드·테스트·린트 명령: 매니페스트의 scripts 섹션, `Makefile`, CI 워크플로
- **러너의 절대경로**: `.venv/bin/pytest` 처럼 PATH 에 없을 수 있다 — bare 명령을 로스터에 쓰지 말 것
- 컨테이너: `docker-compose.yml`, `Dockerfile`, 실행 중이면 `docker ps`
- 디렉터리 경계: 최상위 디렉터리와 각각의 책임

## 2. 로스터 작성 — `.claude/orchestrate.md`

파일 안의 `[TODO]` 를 1단계 실측값으로 전부 채운다. 채울 표는 5개다:

1. 에이전트 로스터 (에이전트명 · 담당 디렉터리 · 위험도)
2. 리뷰어 매핑 (구현 에이전트 → ECC 리뷰어). **새 리뷰어를 만들기 전에 ECC 대응물을 먼저 확인**하고,
   프로젝트 리뷰어를 만들었다면 근거를 한 줄 남긴다.
3. TDD 게이트 (도메인 · 테스트 위치 · 러너 절대경로)
4. 도메인별 검증 명령
5. 커밋 scope · 프로젝트 주의사항

에이전트 분할 기준: **디렉터리·모듈 경계**를 따른다. 하나의 에이전트가 두 언어를 담당하면
리뷰어 매핑이 모호해지므로 나눈다.

## 3. opencode 에이전트 생성 — `.opencode/agent/*.md`

`_example.md` 를 규격으로 삼아 2단계 로스터의 에이전트마다 파일을 만든다. frontmatter 필수 필드:
`description`, `mode: primary`, `model`(수동 실행용 기본값), `temperature`, `permission.bash`.

`permission.bash` 의 deny 목록(`git commit*`, `git push*`, `docker *` 등)은 `_example.md` 에서
그대로 가져온다 — 위임 에이전트가 커밋·인프라를 건드리지 못하게 하는 안전선이다.

전부 만든 뒤 `_example.md` 를 삭제하고 로드를 확인한다:

    ~/.opencode/bin/opencode agent list

## 4. 가드 등급 채우기 (claude 하네스에만 해당)

`.claude/hooks/bash-guard.sh` 상단의 세 변수를 채운다. **`docker ps` 실측으로 후보를 만들고,
반드시 사용자 확인을 받은 뒤 기입한다** — 잘못 넣으면 정상 작업이 차단된다.

- `FORBIDDEN` — 조작 절대 금지 (터널·VPN·시크릿 저장소·공용 인프라 컨테이너)
- `RESTART_ONLY` — `restart` 만 허용, `stop`/`rm` 금지 (상태 보유 DB 등)
- `FOREIGN` — 타 프로젝트 컨테이너

값은 `|` 구분 정규식이다. 예: `FORBIDDEN='my-vpn|my-vault'`. 비우면 해당 규칙은 무시된다.

## 5. 스킬 갭 분석 → 제안 → 승인 → 생성

먼저 **이미 있는 것을 확인한다**: ECC 언어 룰(`~/.claude/rules/ecc/<언어>/`)과 ECC 스킬이
프로젝트 스택을 이미 커버하는지. 커버되면 스킬을 만들지 않는다.

커스텀 스킬 후보는 **프로젝트에만 있는 반복 절차**로 한정한다:
배포·릴리스 절차, 도메인 특유의 함정, 손이 많이 가는 반복 워크플로.

후보를 목록으로 **제안하고 사용자 승인을 받는다**. 승인된 것만 생성한다:

- claude: `.claude/skills/<name>/SKILL.md`
- codex: `.agents/skills/<name>/SKILL.md` + `.agents/skills/<name>/agents/openai.yaml` (ECC 패턴)

## 6. 검증

- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS` (claude 하네스)
- `~/.opencode/bin/opencode agent list` → 2단계 로스터의 에이전트가 전부 보이는지
- `grep -c '\[TODO' .claude/orchestrate.md` → `0`

## 7. 온보딩 보고서

마지막 메시지에 다음을 담는다:

- 감지된 스택 (언어·프레임워크·러너 절대경로)
- 생성·수정한 파일 목록
- 생성한 에이전트와 담당 범위
- 제안했으나 사용자가 거절한 스킬 (있으면)
- 남은 수동 단계 (secrets 입력, 구독 로그인 등)
```

- [ ] **Step 2: claude 스킬 래퍼 작성**

`adapters/claude/global/skills/orchestrate-onboard/SKILL.md` 생성:

```markdown
---
name: orchestrate-onboard
description: Use when 프로젝트에 오케스트레이션 스캐폴드를 찍은 직후(new-project.sh·adopt-project.sh 실행 후), 또는 사용자가 "프로젝트 분석해서 로스터·에이전트·스킬 만들어줘"를 요청할 때. 스택을 실측해 .claude/orchestrate.md 로스터와 .opencode/agent/*.md 를 채우고 필요한 커스텀 스킬을 제안한다.
---

# orchestrate-onboard (claude)

## 0단계: 모델 확인 — 미달이면 중단

이 명령은 프로젝트 전체를 읽고 설계한다. **opus 이상(fable 포함)이 아니면 진행하지 말 것.**

현재 모델이 미달이면 다음만 답하고 종료한다:

> 이 명령은 가장 똑똑한 모델이 필요합니다. `/model` 로 opus 이상으로 전환한 뒤 다시 실행해 주세요.

## 1단계: 절차 본문을 읽는다

`~/.config/orchestrate/ONBOARD-PROCEDURE.md` 를 Read 로 읽고, 거기 적힌 1~7 단계를 순서대로 수행한다.
절차의 단일 소스는 그 파일이다 — 이 스킬에 절차를 복제하지 않는다.

파일이 없으면 키트 설치가 안 된 것이다. 다음을 안내하고 종료한다:

> `~/.config/orchestrate/ONBOARD-PROCEDURE.md` 가 없습니다. dev-orchestrate-kit 의 `./install.sh` 를 먼저 실행해 주세요.

## 2단계: 절차 수행 시 claude 전용 사항

- 4단계(가드 등급)는 이 하네스에서 **수행한다** — `.claude/hooks/bash-guard.sh` 가 실제로 동작한다.
- 5단계 스킬 생성 위치는 `.claude/skills/<name>/SKILL.md` 다.
- 각 단계를 TodoWrite 항목으로 만들어 진행 상황을 보이게 한다.
- 사용자 승인이 필요한 지점(4단계 가드 등급, 5단계 스킬 목록)에서는 **반드시 멈추고 확인**한다.
```

- [ ] **Step 3: 스킬 frontmatter 형식 확인**

Run: `head -5 ~/dev-orchestrate-kit/adapters/claude/global/skills/orchestrate/SKILL.md`
Expected: `---` 로 시작하고 `name:`·`description:` 필드가 있는 형식 — 새 스킬이 같은 형식인지 눈으로 대조한다

- [ ] **Step 4: 절차 본문의 참조 경로가 실제와 맞는지 확인**

```bash
cd ~/dev-orchestrate-kit
ls core/project-template/.claude/orchestrate.md
ls core/project-template/.opencode/agent/_example.md
grep -n "FORBIDDEN=\|RESTART_ONLY=\|FOREIGN=" adapters/claude/project/.claude/hooks/bash-guard.sh
grep -n "HOOK_SELFCHECK_PASS" core/scripts/hook-selfcheck.sh
```
Expected: 4개 경로·변수명이 모두 존재. 없으면 절차 본문의 해당 서술을 실제 이름으로 고친다

- [ ] **Step 5: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add core/onboard/ adapters/claude/global/skills/orchestrate-onboard/
git commit -m "feat: /orchestrate-onboard 절차 본문 + claude 스킬 래퍼"
```

---

### Task 8: codex 어댑터

**Files:**
- Create: `adapters/codex/global/prompts/orchestrate.md`
- Create: `adapters/codex/global/prompts/orchestrate-onboard.md`
- Create: `adapters/codex/project/.codex/AGENTS.md`
- Create: `adapters/codex/project/.codex/config.toml`
- Create: `adapters/codex/project/.codex/agents/reviewer.toml`
- Create: `adapters/codex/project/scripts/codex-review.sh`

**Interfaces:**
- Consumes: `~/.config/orchestrate/ONBOARD-PROCEDURE.md`(Task 7), 로스터 경로 `.claude/orchestrate.md`
- Produces: `scripts/codex-review.sh <BASE_REF>` — 지정 diff 범위를 리뷰해 심각도별 findings 를 stdout 에 출력. 🔴 Critical 이 있으면 exit 1

- [ ] **Step 1: codex 진입 프롬프트 작성**

`adapters/codex/global/prompts/orchestrate.md` 생성:

```markdown
# orchestrate (codex)

오케스트레이션 파이프라인 진입점. **절차의 단일 소스는 프로젝트 루트의 `AGENTS.md` 와
`.codex/AGENTS.md` 다** — 여기에 절차를 복제하지 않는다.

## 시작 전 확인

1. 프로젝트 루트에 `.claude/orchestrate.md`(로스터)가 있고 `[TODO]` 가 0건인가?
   - 아니면 먼저 `/orchestrate-onboard` 를 실행한다. **로스터 없이 위임 금지.**
2. `~/.opencode/bin/opencode` 가 실행 가능한가?

## 역할 경계

codex 는 **오케스트레이터**다. 소스 코드를 직접 고치지 않는다.

- 기획·작업 분해·지시서 작성 → codex
- 구현 → `bash scripts/run-delegation.sh <에이전트> <프롬프트파일> <로그경로> [tier]`
- 리뷰 → `bash scripts/codex-review.sh <BASE_REF>`
- 커밋 → 리뷰 통과 후 codex 가 수행

직접 수정해도 되는 경로: `DOCs/`, `.codex/`, 지시서 파일.

## 위임 규칙

- tier 는 `default` 가 기본이다. large 등급·위험 도메인 task 는 처음부터 `heavy`,
  🔴 반려 재위임도 `heavy` 로 승격한다.
- 실사용 모델은 스크립트 출력의 `MODEL_USED=` 로 확인한다.
- 위임 프롬프트에 **프로젝트 밖 절대경로를 "읽어라"고 쓰지 않는다** — opencode 가
  external_directory 로 차단한다. 외부 파일은 오케스트레이터가 읽어서 인라인한다.

## 리뷰 게이트

리뷰에서 🔴 Critical 이 하나라도 나오면 **반려**다. 같은 에이전트에 `heavy` tier 로
재위임한다(최대 2회). 게이트를 통과하기 전에는 커밋하지 않는다.
```

- [ ] **Step 2: codex 온보딩 프롬프트 작성**

`adapters/codex/global/prompts/orchestrate-onboard.md` 생성:

```markdown
# orchestrate-onboard (codex)

## 0단계: 모델 확인 — 미달이면 중단

이 명령은 프로젝트 전체를 읽고 설계한다. **설치본에서 선택 가능한 최상위 모델 +
`model_reasoning_effort = "high"` 이상이 아니면 진행하지 말 것.**

미달이면 다음만 답하고 종료한다:

> 이 명령은 가장 똑똑한 모델이 필요합니다. `~/.codex/config.toml` 에서 최상위 모델과
> `model_reasoning_effort = "high"` 를 설정한 뒤 다시 실행해 주세요.

## 1단계: 절차 본문을 읽는다

`~/.config/orchestrate/ONBOARD-PROCEDURE.md` 를 읽고 1~7 단계를 순서대로 수행한다.
절차의 단일 소스는 그 파일이다.

파일이 없으면 `dev-orchestrate-kit` 의 `./install.sh --codex` 를 먼저 실행하도록 안내하고 종료한다.

## 2단계: 절차 수행 시 codex 전용 사항

- **4단계(가드 등급)는 건너뛴다** — bash-guard 훅은 claude 전용이다. 대신 조작 금지 컨테이너
  목록을 `.codex/AGENTS.md` 의 "인프라 주의" 절에 **지침으로** 기록한다(강제되지 않음을 명시).
- 5단계 스킬 생성 위치는 `.agents/skills/<name>/` 이며 `SKILL.md` 와 `agents/openai.yaml` 을 함께 만든다.
- 6단계 검증에서 `hook-selfcheck.sh` 는 생략하고, `opencode agent list` 와 로스터 [TODO] 0건만 확인한다.
- 사용자 승인이 필요한 지점(5단계 스킬 목록)에서는 반드시 멈추고 확인한다.
```

- [ ] **Step 3: 프로젝트 .codex 계층 작성**

`adapters/codex/project/.codex/AGENTS.md` 생성:

```markdown
# 이 저장소에서의 codex 오케스트레이션

루트 `AGENTS.md`(하네스 중립 규칙)를 보완한다. 절차 진입은 `~/.codex/prompts/orchestrate.md`.

## 로스터 경로

에이전트 로스터·리뷰어 매핑·검증 명령은 **`.claude/orchestrate.md`** 에 있다.
디렉터리 이름이 `.claude` 인 것은 호환성 때문이다 — claude 하네스와 같은 파일을 공유해
두 하네스가 하나의 로스터를 쓴다. codex 도 이 파일을 읽고 갱신한다.

## 위임

    bash scripts/run-delegation.sh <에이전트> <프롬프트파일> <로그경로> [default|heavy]

에이전트 정의는 `.opencode/agent/*.md`. 로스터에 없는 에이전트에는 위임하지 않는다.

## 리뷰

    bash scripts/codex-review.sh <BASE_REF>

🔴 Critical 이 있으면 exit 1 이며 커밋해서는 안 된다. 같은 에이전트에 `heavy` tier 로
재위임한다(최대 2회).

`features.multi_agent` 를 켠 머신은 `.codex/agents/reviewer.toml` 역할로 대화 내 `/agent`
리뷰도 쓸 수 있다 — **실험 기능이므로 실패해도 위 스크립트 경로가 정답이다.**

## 훅이 없다는 점

claude 하네스의 `bash-guard.sh`·`post-edit-check.sh` 같은 **강제 훅이 codex 에는 없다.**
등가 안전선은 `.codex/config.toml` 의 sandbox·approval 설정이다.

## 인프라 주의 (지침 — 강제되지 않음)

아래 컨테이너·리소스는 조작하지 않는다. 훅이 막아주지 않으므로 스스로 지켜야 한다.

- 조작 절대 금지: [온보딩 시 채울 것 — 터널·VPN·시크릿 저장소 등]
- restart 만 허용: [온보딩 시 채울 것 — 상태 보유 DB 등]
- 타 프로젝트 소유: [온보딩 시 채울 것]
```

`adapters/codex/project/.codex/config.toml` 생성:

```toml
# 이 저장소 권장 codex 설정. ~/.codex/config.toml 과 자동 병합되지 않는다 — 필요한 값을 직접 옮길 것.

# 오케스트레이터는 워크스페이스 밖을 쓰지 않는다. 위임 에이전트가 소스를 고치므로
# codex 자신은 문서·지시서만 쓰면 된다.
sandbox_mode = "workspace-write"

# 되돌리기 어려운 명령은 사람이 확인한다 — codex 에는 bash-guard 등가물이 없다.
approval_policy = "on-request"

# 온보딩·설계 단계에서는 최상위 모델 + 높은 추론을 쓴다.
model_reasoning_effort = "high"

# 선택: 대화 내 /agent 리뷰 (실험 기능). 꺼져 있어도 scripts/codex-review.sh 가 동작한다.
# [features]
# multi_agent = true
#
# [agents.reviewer]
# layer = ".codex/agents/reviewer.toml"
```

`adapters/codex/project/.codex/agents/reviewer.toml` 생성:

```toml
# 선택적 리뷰어 역할 — features.multi_agent 를 켠 머신에서만 쓰인다.
# 정식 리뷰 경로는 scripts/codex-review.sh 이며, 이 파일은 대화 내 /agent 편의용이다.

instructions = """
너는 코드 리뷰어다. 구현하지 말고 리뷰만 한다.

각 발견을 심각도로 분류한다:
  🔴 Critical — 보안 취약점·데이터 손실·명백한 버그. 하나라도 있으면 반려다.
  🟡 Major    — 설계 결함·누락된 에러 처리·테스트 공백
  🟢 Minor    — 스타일·가독성

반드시 확인할 것:
- 조용한 실패(silent fallback): 부재 필드에 무경고 디폴트를 넣거나 예외를 삼키는가
- 중복 구현: 기존 함수를 복사해 고친 흔적이 있는가 (원본 개선 + 호출부 갱신이 옳다)
- 테스트: 실패 테스트가 먼저 있었는가, 동작을 실제로 검증하는가

마지막 줄에 판정을 쓴다: VERDICT: PASS 또는 VERDICT: REJECT
"""
```

- [ ] **Step 4: codex-review.sh 작성**

`adapters/codex/project/scripts/codex-review.sh` 생성:

```bash
#!/usr/bin/env bash
# codex 자체 리뷰 — 비대화형 `codex exec` 로 diff 를 리뷰한다.
#
# 사용법: bash scripts/codex-review.sh <BASE_REF> [대상경로 ...]
#   예:   bash scripts/codex-review.sh HEAD~1
#         bash scripts/codex-review.sh main backend/
#
# 실험 플래그(features.multi_agent)에 의존하지 않는다 — 이것이 정식 리뷰 경로다.
# 🔴 Critical 이 하나라도 있으면 exit 1 (커밋 금지 신호).
set -uo pipefail

BASE_REF="${1:?usage: codex-review.sh <BASE_REF> [대상경로 ...]}"
shift || true

command -v codex >/dev/null 2>&1 || { echo "codex CLI 가 없다" >&2; exit 69; }

DIFF=$(git diff "$BASE_REF"...HEAD -- "$@" 2>/dev/null)
if [ -z "$DIFF" ]; then
  echo "리뷰할 변경이 없다 ($BASE_REF...HEAD)"
  exit 0
fi

ROSTER=""
[ -f ".claude/orchestrate.md" ] && ROSTER=$(cat .claude/orchestrate.md)

PROMPT=$(cat <<EOF
너는 코드 리뷰어다. 아래 diff 를 리뷰만 하고 코드를 고치지 마라.

각 발견을 심각도로 분류한다:
  🔴 Critical — 보안 취약점·데이터 손실·명백한 버그
  🟡 Major    — 설계 결함·누락된 에러 처리·테스트 공백
  🟢 Minor    — 스타일·가독성

반드시 확인할 것:
- 조용한 실패: 부재 필드에 무경고 디폴트를 넣거나 예외를 삼키는가
- 중복 구현: 기존 함수를 복사해 고쳤는가 (원본 개선 + 호출부 갱신이 옳다)
- 테스트: 동작을 실제로 검증하는가

--- 프로젝트 로스터 (검증 명령·주의사항) ---
$ROSTER

--- diff ($BASE_REF...HEAD) ---
$DIFF

마지막 줄에 판정을 써라: VERDICT: PASS 또는 VERDICT: REJECT
EOF
)

OUT=$(codex exec "$PROMPT" 2>&1)
echo "$OUT"

if echo "$OUT" | grep -q "VERDICT: REJECT" || echo "$OUT" | grep -q "🔴"; then
  echo
  echo "❌ 반려 — 🔴 Critical 이 있다. heavy tier 로 재위임할 것 (커밋 금지)"
  exit 1
fi
echo
echo "✅ 리뷰 통과"
exit 0
```

- [ ] **Step 5: 스캐폴드에 codex 자산이 실리는지 확인**

```bash
cd ~/dev-orchestrate-kit
chmod +x adapters/codex/project/scripts/codex-review.sh
rm -rf /tmp/cx-test && ./new-project.sh /tmp/cx-test cxproj --codex
ls /tmp/cx-test/.codex/AGENTS.md /tmp/cx-test/scripts/codex-review.sh
ls /tmp/cx-test/CLAUDE.md 2>&1 | grep -q "No such file" && echo "claude 전용 파일 미포함 OK"
```
Expected: `.codex/AGENTS.md` 와 `scripts/codex-review.sh` 존재, `CLAUDE.md` 부재

- [ ] **Step 6: 커밋**

```bash
cd ~/dev-orchestrate-kit
rm -rf /tmp/cx-test
git add adapters/codex/
git commit -m "feat: codex 어댑터 — 프롬프트·프로젝트 계층·codex-review.sh"
```

---

### Task 9: 컨테이너 계층 번들

**Files:**
- Create: `containers/browser/` (호스트 `/opt/chrome-cdp` 에서 복사)
- Create: `containers/antigravity/docker-compose.yml`
- Create: `containers/antigravity/README.md`

**Interfaces:**
- Consumes: 없음
- Produces: 없음 (독립 자산)

- [ ] **Step 1: 브라우저 컨테이너 vendoring**

```bash
cd ~/dev-orchestrate-kit
mkdir -p containers
cp -r /opt/chrome-cdp containers/browser
rm -f containers/browser/*.bak-* containers/browser/insane-api/*.bak-*
rm -rf containers/browser/insane-api/__pycache__
find containers/browser -name '*.pyc' -delete
ls containers/browser containers/browser/insane-api
```
Expected: `docker-compose.yml`, `README.md`, `bin/`, `insane-api/`, `patches/` 존재.
`insane-api/` 안에 `Dockerfile`, `start-both.sh`, `server.py`, `cloak_executor.py`, `cdp_bridge.py`, `vendor/`

- [ ] **Step 2: compose 문법 검증**

Run: `cd ~/dev-orchestrate-kit/containers/browser && docker compose config >/dev/null && echo "compose OK"`
Expected: `compose OK`

- [ ] **Step 3: 드리프트 규약을 README 에 명시**

`containers/browser/README.md` 최상단 제목 바로 다음에 삽입:

```markdown
> **이 사본의 원본은 호스트다.** dev-orchestrate-kit 에 번들된 복사본이며, 개선은
> 호스트(`/opt/chrome-cdp`)에서 먼저 하고 키트에 반영한 뒤 push 한다. 반대 방향으로
> 키트를 먼저 고치면 호스트와 어긋난다.
```

- [ ] **Step 4: antigravity compose 작성**

`containers/antigravity/docker-compose.yml` 생성:

```yaml
# antigravity-manager — gemini 계열을 OpenAI 호환 API 로 중계하는 로컬 프록시.
#
# SECURITY: 프록시는 무인증이다. 기본 바인딩을 127.0.0.1 로 고정한다 —
# 0.0.0.0 으로 열면 같은 네트워크의 누구나 이 계정의 모델을 쓸 수 있다.
# LAN 공유가 꼭 필요할 때만 포트 바인딩을 바꾸되, 그 결정을 팀과 공유할 것.
#
# Usage:  cd containers/antigravity && docker compose up -d
# Verify: curl -s http://127.0.0.1:8045/v1/models

services:
  antigravity-manager:
    image: lbjlaq/antigravity-manager:latest
    container_name: antigravity-manager
    ports:
      - "127.0.0.1:8045:8045"      # SECURITY: localhost 전용. 위 참조.
    volumes:
      # 계정 연결·발급 키 상태가 여기 남는다. 지우면 재로그인이 필요하다.
      - ./data:/root/.antigravity_tools
    restart: unless-stopped
```

- [ ] **Step 5: antigravity README 작성**

`containers/antigravity/README.md` 생성:

```markdown
# antigravity-manager — gemini 프록시

opencode 의 `antigravity` 프로바이더가 쓰는 로컬 OpenAI 호환 엔드포인트(`:8045`)를 제공한다.
이 컨테이너 없이 `antigravity/*` 모델을 체인에 넣으면 호출마다 실패한다.

## 기동

    cd containers/antigravity
    docker compose up -d
    curl -s http://127.0.0.1:8045/v1/models

## 설치 후 수동 단계

1. 브라우저에서 `http://127.0.0.1:8045` 접속 (원격 서버면 SSH 포트포워딩 사용 —
   프록시를 LAN 에 열지 말 것)
2. 구글 계정 연결
3. API 키 발급
4. `~/.config/opencode/secrets.env` 에 `ANTIGRAVITY_API_KEY=<발급키>` 추가 (chmod 600)
5. 프로바이더 등록 확인: `~/.opencode/bin/opencode models | grep antigravity`
6. 체인에 반영: `./install.sh --providers=antigravity,...` 또는
   `core/opencode/gen-policy.sh` 를 직접 실행
7. 검증: `~/.config/opencode/model-doctor.sh`

## 데이터

`./data/` 에 계정·키 상태가 저장된다. **커밋하지 말 것** — 키트 `.gitignore` 에 등록되어 있다.
```

- [ ] **Step 6: 컨테이너 데이터 디렉터리를 gitignore 에 추가**

```bash
cd ~/dev-orchestrate-kit
printf 'containers/antigravity/data/\n' >> .gitignore
grep -n "containers/antigravity/data" .gitignore
```
Expected: 마지막 줄에 등록됨

- [ ] **Step 7: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add containers/ .gitignore
git commit -m "feat: 컨테이너 계층 번들 — 브라우저(단일 컨테이너)·antigravity 프록시"
```

---

### Task 10: 문서 갱신 — README·PORTING

**Files:**
- Modify: `README.md` (전체 재작성)
- Modify: `docs/PORTING.md`

**Interfaces:**
- Consumes: Task 1~9 의 최종 경로·명령
- Produces: 없음

- [ ] **Step 1: README 재작성**

`README.md` 전체를 교체:

```markdown
# dev-orchestrate-kit

오케스트레이터(claude 또는 codex) → opencode 위임 개발환경을 어떤 머신에든 재현하는 부트스트랩 키트.
ECC(everything-claude-code)·superpowers 위에 커스텀 오케스트레이션 계층(온보딩 명령, 모델 폴백 체인,
프로젝트 스캐폴드)을 얹는다. macOS·Linux 지원.

## 빠른 시작

```bash
git clone https://github.com/fartypie-d/dev-orchestrate-kit.git
cd dev-orchestrate-kit

# 전역 1회 — 하네스·프로바이더는 생략 시 자동 감지/대화형
./install.sh --claude --providers=qwen,openai typescript python

# 프로젝트마다 — 둘 중 하나를 고른다
./new-project.sh   ~/my-new-project      # 새로 시작하는 프로젝트
./adopt-project.sh ~/existing-project    # 이미 작업 중인 프로젝트

# 그다음 프로젝트에서 하네스를 열고 (가장 똑똑한 모델로)
/orchestrate-onboard
```

## 구성

| 경로 | 내용 |
|---|---|
| `install.sh` | 전역 설치 — 하네스·프로바이더·컨테이너 선택형, 멱등 |
| `new-project.sh` / `adopt-project.sh` | 두 진입 경로. 기존 파일 절대 미덮음 |
| `lib/stamp.sh` | 두 진입 스크립트가 공유하는 스캐폴드 함수 |
| `core/scripts/` | 하네스 무관 스크립트 — `run-delegation.sh`, `phase-tools.py` 등 |
| `core/opencode/` | 프로바이더 매핑표·체인 생성기·`model-doctor.sh`·시드 프로파일 |
| `core/onboard/` | `/orchestrate-onboard` 절차 본문 (단일 소스) |
| `core/project-template/` | 로스터·에이전트 규격·문서 체계 (하네스 무관) |
| `adapters/claude/` | 전역 스킬 + 프로젝트 훅·settings·CLAUDE.md |
| `adapters/codex/` | `~/.codex/prompts` + `.codex/` 프로젝트 계층·`codex-review.sh` |
| `containers/` | 브라우저(스텔스 CDP + 우회 API 단일 컨테이너)·antigravity 프록시 |

## 핵심 개념

- **오케스트레이터는 감독관** — 소스는 `scripts/run-delegation.sh` 로 opencode 에이전트에
  위임하고 리뷰어로 검수한다. claude 는 ECC 리뷰어 서브에이전트, codex 는 `codex-review.sh`.
- **모델은 중앙 정책** — `~/.config/opencode/model-policy.json` 의 tier 체인을
  run-delegation.sh 가 `-m` 으로 주입하고 한도·무응답 시 자동 폴백한다.
  체인은 `gen-policy.sh` 가 생성하고 `model-doctor.sh` 가 실측 검증한다.
- **서로 다른 구독을 섞는 것이 가용성 장치** — xai·openai 는 별개 할당량 풀이라
  한쪽이 한도에 걸려도 다른 쪽으로 넘어간다.
- **프로젝트 로스터** — `.claude/orchestrate.md` 가 에이전트·리뷰어 매핑·검증 명령의
  단일 소스다. 두 하네스가 이 파일을 공유한다(디렉터리 이름은 호환성 때문에 `.claude`).
  **로스터 없이 위임 금지.**

## 하네스 조합

| 조합 | 설치 | 리뷰 | 강제 훅 |
|---|---|---|---|
| claude + opencode | `./install.sh --claude` | ECC 리뷰어 서브에이전트 | bash-guard·post-edit-check |
| codex + opencode | `./install.sh --codex` | `scripts/codex-review.sh` | 없음 — sandbox·approval 로 대체 |

## 머신 간 동기화 규약

- **이 저장소가 단일 소스다.** 어느 머신에서든 오케스트레이션 자산을 개선하면:
  키트에 반영 → push → 다른 머신에서 pull 후 `./install.sh` 재실행(멱등).
- `~/.claude/skills/orchestrate` 를 직접 고치고 끝내지 말 것 — 다음 install 에서 되돌아간다.
- **예외 — 컨테이너는 호스트가 원본이다.** `/opt/chrome-cdp` 를 먼저 고치고
  `containers/browser/` 에 반영한다.
- **예외 — model-policy 는 생성물이다.** 원본은 `core/opencode/provider-models.json` 매핑표다.
- 포함하지 않는 것: 비밀(secrets.env), 구독 OAuth(머신별 로그인), 메모리·프로젝트 데이터,
  음성 단말 클라이언트·docker-ops(개발 서버 전용) 등 호스트 특화 계층.

## 테스트

```bash
python3 -m unittest discover -s tests -v
```
```

- [ ] **Step 2: PORTING.md 에 v2 항목 추가**

`docs/PORTING.md` 최상단 제목 다음에 삽입:

```markdown
## v2 변경점 (2026-08-07)

- 레이아웃이 `core/` + `adapters/<하네스>/` 로 재편됐다. 구 `global/`·`project-template/` 경로는 없다.
- 진입 경로가 둘이다: `new-project.sh`(신규) / `adopt-project.sh`(기존, 비파괴).
- 모델 정책은 고정 프로파일 대신 `gen-policy.sh` 가 생성하고 `model-doctor.sh` 가 검증한다.
- OpenAI 는 구독 인증이 기본이다 — 원격 서버는 헤드리스 디바이스 인증을 쓴다:
  `opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"`
  **구독으로 열리는 모델은 API 가격표와 다르다** — `opencode models` 로 실측할 것.
- 브라우저 컨테이너는 단일 컨테이너다(9222 CDP + 9223 우회 API). `CLOAKSERVE_IDLE_TIMEOUT` 을
  반드시 설정한다(초 단위 숫자만 — `"30m"` 은 기동 실패).
```

- [ ] **Step 3: 전체 테스트 최종 실행**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest discover -s tests -v`
Expected: 전 테스트 PASS (phase-tools, stamp, adopt, gen-policy, model-doctor, install-args)

- [ ] **Step 4: 두 진입 경로 최종 스모크**

```bash
cd ~/dev-orchestrate-kit
rm -rf /tmp/smoke-new /tmp/smoke-adopt && mkdir -p /tmp/smoke-adopt
git -C /tmp/smoke-adopt init -q -b main && echo "기존" > /tmp/smoke-adopt/README.md
./new-project.sh /tmp/smoke-new newproj --claude
./adopt-project.sh /tmp/smoke-adopt --codex
grep -c '\[TODO' /tmp/smoke-new/.claude/orchestrate.md
cat /tmp/smoke-adopt/README.md
rm -rf /tmp/smoke-new /tmp/smoke-adopt
```
Expected: `[TODO` 가 1건 이상(온보딩이 채울 자리), 기존 README 내용은 `기존` 그대로

- [ ] **Step 5: 커밋**

```bash
cd ~/dev-orchestrate-kit
git add README.md docs/PORTING.md
git commit -m "docs: v2 구조·두 진입 경로·모델 설정 반영"
```

---

### Task 11: Claude 요금제별 토큰 경량화 프로파일

**Files:**
- Create: `adapters/claude/global/agent-roles.json`
- Create: `adapters/claude/global/plan-profiles.json`
- Create: `adapters/claude/global/apply-plan-profile.sh`
- Modify: `install.sh` (`--plan=` 플래그 + ECC 뒤 적용)
- Test: `tests/test_plan_profile.py`

**Interfaces:**
- Consumes: 없음
- Produces: `apply-plan-profile.sh <pro|max5|max20> [--agents-dir DIR] [--settings PATH]`
  — `--agents-dir`/`--settings` 는 **테스트 주입용**(기본값은 `~/.claude/agents`·`~/.claude/settings.json`).
  알 수 없는 프로파일이면 exit 64.

**절대 규칙:** `CLAUDE_CODE_SUBAGENT_MODEL` 을 쓰지 않는다. 이 env 는 frontmatter 와 명시적
model 파라미터까지 덮어써서 "worker 는 haiku, 리뷰는 sonnet" 차등을 불가능하게 만든다
(2026-07-29 리뷰어 전원 haiku 사고의 원인).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_plan_profile.py` 생성:

```python
"""apply-plan-profile.sh 테스트 — 가짜 agents 디렉터리·settings 로 프로파일 적용을 검증."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
APPLY = KIT / "adapters/claude/global/apply-plan-profile.sh"

AGENTS = {
    "planner.md": "opus",              # design
    "code-reviewer.md": "claude-sonnet-5",   # quality
    "security-reviewer.md": "claude-sonnet-5",
    "task-orchestrator.md": "sonnet",  # quality (검증·커밋 경로)
    "doc-updater.md": "haiku",         # worker
    "build-error-resolver.md": "claude-sonnet-5",  # worker
    "brand-new-agent.md": "claude-sonnet-5",       # 목록에 없음 → worker 기본값
}


class PlanProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agents = Path(self.tmp.name) / "agents"
        self.agents.mkdir()
        for name, model in AGENTS.items():
            (self.agents / name).write_text(
                f"---\nname: {name[:-3]}\nmodel: {model}\ndescription: t\n---\n\n본문\n"
            )
        self.settings = Path(self.tmp.name) / "settings.json"
        self.settings.write_text(json.dumps({"model": "claude-fable-5[1m]", "theme": "auto"}))

    def apply(self, profile):
        return subprocess.run(
            ["bash", str(APPLY), profile,
             "--agents-dir", str(self.agents), "--settings", str(self.settings)],
            capture_output=True, text=True,
        )

    def model_of(self, name):
        for line in (self.agents / name).read_text().splitlines():
            if line.startswith("model:"):
                return line.split(":", 1)[1].strip()
        return None

    def settings_json(self):
        return json.loads(self.settings.read_text())

    def test_pro_downgrades_workers_but_not_reviewers(self):
        r = self.apply("pro")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_of("doc-updater.md"), "haiku")
        self.assertEqual(self.model_of("build-error-resolver.md"), "haiku")
        self.assertEqual(self.model_of("code-reviewer.md"), "sonnet")
        self.assertEqual(self.model_of("security-reviewer.md"), "sonnet")

    def test_pro_keeps_design_on_opus(self):
        self.apply("pro")
        self.assertEqual(self.model_of("planner.md"), "opus")

    def test_task_orchestrator_is_quality_class(self):
        """검증·커밋 경로이므로 pro 에서도 haiku 로 내리지 않는다."""
        self.apply("pro")
        self.assertEqual(self.model_of("task-orchestrator.md"), "sonnet")

    def test_unlisted_agent_defaults_to_worker(self):
        self.apply("pro")
        self.assertEqual(self.model_of("brand-new-agent.md"), "haiku")

    def test_pro_sets_token_env(self):
        self.apply("pro")
        env = self.settings_json()["env"]
        self.assertEqual(env["MAX_THINKING_TOKENS"], "10000")
        self.assertEqual(env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "75")

    def test_pro_sets_main_model_to_sonnet(self):
        self.apply("pro")
        self.assertEqual(self.settings_json()["model"], "sonnet")

    def test_token_env_is_identical_across_all_profiles(self):
        """토큰 예산은 요금제 구분 요소가 아니다 — x20 도 10000/75 를 쓴다."""
        for profile in ("pro", "max5", "max20"):
            r = self.apply(profile)
            self.assertEqual(r.returncode, 0, r.stderr)
            env = self.settings_json()["env"]
            self.assertEqual(env["MAX_THINKING_TOKENS"], "10000", profile)
            self.assertEqual(env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "75", profile)

    def test_max20_does_not_touch_main_model(self):
        self.apply("pro")
        r = self.apply("max20")
        self.assertEqual(r.returncode, 0, r.stderr)
        # max20 은 메인 모델을 건드리지 않는다 — pro 가 바꿔둔 값이 그대로 남는다
        self.assertEqual(self.settings_json()["model"], "sonnet")

    def test_max20_restores_workers_to_sonnet(self):
        self.apply("pro")
        self.apply("max20")
        self.assertEqual(self.model_of("doc-updater.md"), "sonnet")
        self.assertEqual(self.model_of("code-reviewer.md"), "sonnet")

    def test_never_writes_subagent_model_env(self):
        """CLAUDE_CODE_SUBAGENT_MODEL 은 frontmatter 차등을 무력화한다 — 절대 쓰지 않는다."""
        for profile in ("pro", "max5", "max20"):
            self.apply(profile)
            self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL",
                             json.dumps(self.settings_json()))

    def test_is_idempotent(self):
        self.apply("pro")
        first = (self.agents / "doc-updater.md").read_text()
        self.apply("pro")
        self.assertEqual((self.agents / "doc-updater.md").read_text(), first)

    def test_unknown_profile_exits_64(self):
        r = self.apply("nosuchplan")
        self.assertEqual(r.returncode, 64)

    def test_other_settings_keys_preserved(self):
        self.apply("pro")
        self.assertEqual(self.settings_json()["theme"], "auto")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd ~/dev-orchestrate-kit && python3 -m unittest tests.test_plan_profile -v`
Expected: FAIL — `apply-plan-profile.sh` 없음

- [ ] **Step 3: 역할 분류표 작성**

`adapters/claude/global/agent-roles.json` 생성 (목록에 없으면 worker — 새 ECC 에이전트에 안전한 기본값):

```json
{
  "_comment": "ECC 에이전트 역할 분류. apply-plan-profile.sh 가 이 표로 요금제별 모델을 배정한다. 목록에 없는 에이전트는 worker 로 떨어진다 — ECC 가 에이전트를 추가해도 안전하다.",
  "design": [
    "planner", "architect", "code-architect", "spec-miner",
    "a11y-architect", "network-architect", "homelab-architect"
  ],
  "quality": [
    "agent-evaluator", "code-reviewer", "comment-analyzer", "conversation-analyzer",
    "cpp-reviewer", "csharp-reviewer", "database-reviewer", "django-reviewer",
    "fastapi-reviewer", "flutter-reviewer", "fsharp-reviewer", "gan-evaluator",
    "go-reviewer", "healthcare-reviewer", "java-reviewer", "kotlin-reviewer",
    "mle-reviewer", "network-config-reviewer", "php-reviewer", "pr-test-analyzer",
    "python-reviewer", "react-reviewer", "rust-reviewer", "security-reviewer",
    "silent-failure-hunter", "swift-reviewer", "type-design-analyzer",
    "typescript-reviewer", "vue-reviewer",
    "task-orchestrator"
  ],
  "_quality_note": "task-orchestrator 는 리뷰어가 아니지만 검증·커밋 경로를 담당하므로 품질 등급으로 둔다 — 여기를 haiku 로 내리면 위임 산출물이 검증 없이 커밋된다."
}
```

- [ ] **Step 4: 프로파일 표 작성**

`adapters/claude/global/plan-profiles.json` 생성:

```json
{
  "_comment": "Claude 요금제별 모델 프로파일. apply-plan-profile.sh 가 적용한다. main_model 이 null 이면 ~/.claude/settings.json 의 .model 을 건드리지 않는다(사용자 선택 유지). env 값이 null 이면 해당 키를 제거한다.",
  "_env_note": "토큰 env 2개는 요금제와 무관한 공통값이다 — x20 에서도 동일하게 쓴다. 실제 운영 중인 프로젝트들과 프로젝트 템플릿이 이미 10000/75 로 운영 중이다. 요금제가 가르는 것은 메인 모델과 worker 클래스뿐이다.",
  "_forbidden": "CLAUDE_CODE_SUBAGENT_MODEL 은 어떤 프로파일에도 넣지 않는다 — frontmatter 와 명시적 model 파라미터를 전부 덮어써서 리뷰어까지 강등시킨다 (2026-07-29 사고).",
  "profiles": {
    "pro": {
      "main_model": "sonnet",
      "agents": { "design": "opus", "quality": "sonnet", "worker": "haiku" },
      "env": { "MAX_THINKING_TOKENS": "10000", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75" }
    },
    "max5": {
      "main_model": "opus",
      "agents": { "design": "opus", "quality": "sonnet", "worker": "haiku" },
      "env": { "MAX_THINKING_TOKENS": "10000", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75" }
    },
    "max20": {
      "main_model": null,
      "agents": { "design": "opus", "quality": "sonnet", "worker": "sonnet" },
      "env": { "MAX_THINKING_TOKENS": "10000", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75" }
    }
  }
}
```

- [ ] **Step 5: apply-plan-profile.sh 구현**

`adapters/claude/global/apply-plan-profile.sh` 생성:

```bash
#!/usr/bin/env bash
# Claude 요금제에 맞춰 모델·토큰 설정을 적용한다 (멱등).
#
# 사용법: apply-plan-profile.sh <pro|max5|max20> [--agents-dir DIR] [--settings PATH]
#
# ⚠️ ECC install 은 ~/.claude/agents/*.md 를 덮어쓴다. 이 스크립트는 반드시 ECC 단계 뒤에
#    돌려야 하며, ECC 를 갱신할 때마다 다시 돌려야 한다.
#
# ⚠️ CLAUDE_CODE_SUBAGENT_MODEL 은 절대 쓰지 않는다 — frontmatter 와 명시적 model 파라미터를
#    전부 덮어써서 "worker 는 haiku, 리뷰는 sonnet" 차등 자체를 불가능하게 만든다.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROLES="$HERE/agent-roles.json"
PROFILES="$HERE/plan-profiles.json"
AGENTS_DIR="$HOME/.claude/agents"
SETTINGS="$HOME/.claude/settings.json"

PROFILE="${1:-}"
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --agents-dir) AGENTS_DIR="$2"; shift 2 ;;
    --settings)   SETTINGS="$2"; shift 2 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }
[ -f "$PROFILES" ] || { echo "프로파일 표 없음: $PROFILES" >&2; exit 66; }

if [ -z "$PROFILE" ] || ! jq -e --arg p "$PROFILE" '.profiles[$p]' "$PROFILES" >/dev/null 2>&1; then
  echo "알 수 없는 프로파일: '${PROFILE:-(없음)}' — 사용 가능: $(jq -r '.profiles|keys|join(", ")' "$PROFILES")" >&2
  exit 64
fi

echo "== 요금제 프로파일 적용: $PROFILE"

# ── 1. 에이전트 frontmatter model 배정 ───────────────────────────────────
DESIGN_M=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.design' "$PROFILES")
QUALITY_M=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.quality' "$PROFILES")
WORKER_M=$(jq -r --arg p "$PROFILE" '.profiles[$p].agents.worker' "$PROFILES")

classify() { # <에이전트 basename(확장자 제외)>
  if jq -e --arg n "$1" '.design | index($n)' "$ROLES" >/dev/null 2>&1; then
    echo "$DESIGN_M"
  elif jq -e --arg n "$1" '.quality | index($n)' "$ROLES" >/dev/null 2>&1; then
    echo "$QUALITY_M"
  else
    echo "$WORKER_M"   # 목록에 없으면 worker — 새 에이전트에 안전한 기본값
  fi
}

if [ -d "$AGENTS_DIR" ]; then
  changed=0
  for f in "$AGENTS_DIR"/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .md)
    want=$(classify "$name")
    have=$(grep -m1 '^model:' "$f" 2>/dev/null | sed 's/^model:[[:space:]]*//' || true)
    if [ "$have" != "$want" ]; then
      # frontmatter 첫 model: 줄만 교체한다 (본문의 'model:' 문자열은 건드리지 않음).
      perl -pi -e "if (!\$done && s/^model:.*/model: $want/) { \$done = 1 }" "$f"
      changed=$((changed + 1))
    fi
  done
  echo "   에이전트: $changed 개 변경 (design=$DESIGN_M quality=$QUALITY_M worker=$WORKER_M)"
else
  echo "   ⚠️ 에이전트 디렉터리 없음: $AGENTS_DIR — ECC 설치 후 다시 실행할 것"
fi

# ── 2. settings.json 의 메인 모델·토큰 env ───────────────────────────────
mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
TMP="$SETTINGS.tmp.$$"

MAIN=$(jq -r --arg p "$PROFILE" '.profiles[$p].main_model // ""' "$PROFILES")
ENV_OBJ=$(jq -c --arg p "$PROFILE" '.profiles[$p].env' "$PROFILES")

jq --arg main "$MAIN" --argjson envobj "$ENV_OBJ" '
  # main_model 이 빈 문자열이면 .model 을 건드리지 않는다 (사용자 선택 유지).
  (if $main == "" then . else .model = $main end)
  # env 값이 null 인 키는 제거하고, 값이 있는 키만 병합한다.
  | .env = ((.env // {}) + ($envobj | with_entries(select(.value != null))))
  | reduce ($envobj | to_entries[] | select(.value == null) | .key) as $k (.; del(.env[$k]))
  # 방어: 이 env 는 어떤 경로로도 들어가서는 안 된다.
  | del(.env["CLAUDE_CODE_SUBAGENT_MODEL"])
  | if (.env | length) == 0 then del(.env) else . end
' "$SETTINGS" > "$TMP" && mv "$TMP" "$SETTINGS"

if [ -n "$MAIN" ]; then
  echo "   메인 모델: $MAIN"
else
  echo "   메인 모델: 유지 (현재 $(jq -r '.model // "(미지정)"' "$SETTINGS"))"
fi
echo "   토큰 env: $(jq -c '.env // {}' "$SETTINGS")"
echo
echo "완료. ECC 를 갱신하면 에이전트 파일이 덮이므로 이 스크립트를 다시 실행할 것."
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
cd ~/dev-orchestrate-kit && chmod +x adapters/claude/global/apply-plan-profile.sh
python3 -m unittest tests.test_plan_profile -v
```
Expected: PASS (12개 테스트 전부)

- [ ] **Step 7: install.sh 에 `--plan=` 플래그 추가**

인자 파싱 루프(Task 6 Step 3)에 분기를 넣는다 — `--providers=*` 줄 다음에:

```bash
    --plan=*)        PLAN="${arg#--plan=}" ;;
```

변수 초기화부에 `PLAN=""` 를 추가하고, 파싱 전용 출력에도 한 줄 추가한다:

```bash
  echo "PLAN=$PLAN"
```

- [ ] **Step 8: install.sh 에서 ECC 뒤에 프로파일 적용**

Task 6 Step 7 의 `say "7/7 검증"` **직전**에 삽입한다 (ECC·전역 자산 배치가 끝난 뒤여야 한다):

```bash
case "$HARNESSES" in
  *claude*)
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
        || note "⚠️ 프로파일 적용 실패 — 요금제 이름을 확인할 것"
    else
      note "요금제 미선택 — 모델·토큰 설정을 건드리지 않는다"
    fi
    ;;
esac
```

- [ ] **Step 9: install.sh 마지막 안내에 재적용 규칙 추가**

Task 6 Step 8 의 안내 heredoc 에서 `3) 인증 후 재검증` 줄 다음에 삽입:

```
   3-1) ECC 를 갱신했다면 요금제 프로파일을 재적용한다 (ECC 가 에이전트 파일을 덮는다):
        bash adapters/claude/global/apply-plan-profile.sh <pro|max5|max20>
```

- [ ] **Step 10: 이 호스트에서 max20 적용 확인 (현행 유지 검증)**

```bash
cd ~/dev-orchestrate-kit
cp ~/.claude/settings.json /tmp/settings-before.json
bash adapters/claude/global/apply-plan-profile.sh max20
diff <(jq -S '.model' /tmp/settings-before.json) <(jq -S '.model' ~/.claude/settings.json) && echo "메인 모델 불변 OK"
jq -c '.env' ~/.claude/settings.json
grep -h '^model:' ~/.claude/agents/*.md | sort | uniq -c
```
Expected: 메인 모델 불변. `.env` 는 `{"MAX_THINKING_TOKENS":"10000","CLAUDE_AUTOCOMPACT_PCT_OVERRIDE":"75"}`
(프로젝트들과 동일한 값이 전역에도 심긴다). 에이전트는 `opus` 7개 / `sonnet` 나머지 61개
(기존 haiku 6개가 sonnet 으로, `claude-sonnet-5` 표기가 `sonnet` 별칭으로 통일된다)

- [ ] **Step 11: 커밋**

```bash
cd ~/dev-orchestrate-kit
rm -f /tmp/settings-before.json
git add adapters/claude/global/ install.sh tests/test_plan_profile.py
git commit -m "feat: Claude 요금제별 토큰 경량화 프로파일 (pro/max5/max20)"
```

---

### Task 12: 도그푸딩 — 키트를 오케스트레이션 대상으로 전환

**전제:** Task 1~3 완료 (`adopt-project.sh` 가 존재해야 한다)

**Files:**
- Create: `.claude/orchestrate.md` (adopt-project.sh 가 스캐폴드 → 손으로 채움)
- Create: `.opencode/agent/{kit-scripts,kit-tests,kit-docs}.md`
- Create: `AGENTS.md`, `CLAUDE.md` (스캐폴드 → [TODO] 채움)
- Create: `adapters/claude/project/.claude/agents/bash-reviewer.md`
- Modify: `.gitignore` (`.orchestrate/`)

**Interfaces:**
- Consumes: Task 3 의 `adopt-project.sh`, Task 1 의 `core/scripts/`
- Produces: 위임 가능한 키트 저장소 — Task 4~11 이 `bash scripts/run-delegation.sh` 로 진행된다

**해결해야 할 문제 2가지 (실측으로 발견)**

1. **`run-delegation.sh` 가 두 벌이 된다.** stamp 하면 작업용 `scripts/run-delegation.sh` 가 생기는데,
   키트는 같은 파일을 템플릿으로 `core/scripts/run-delegation.sh` 에 들고 있다. 두 벌이 갈라지면
   "키트가 배포하는 것"과 "키트가 실제로 쓰는 것"이 달라진다 — 도그푸딩의 의미가 사라진다.
   → **작업용을 vendored 원본으로 심링크한다.** 드리프트가 물리적으로 불가능해지고,
     키트가 배포하는 바로 그 스크립트로 자기 작업을 돌리게 된다.
2. **bash 리뷰어가 ECC 에 없다.** 실측: `~/.claude/agents/` 68개 중 bash·shell 전용 리뷰어 0건.
   키트는 코드의 대부분이 bash 다(`install.sh`·`stamp.sh`·`gen-policy.sh`·`model-doctor.sh`·
   `apply-plan-profile.sh`·`codex-review.sh`). 로스터 규칙상 "새 리뷰어를 만들기 전에 ECC 대응물을
   먼저 확인"인데 대응물이 없으므로 **프로젝트 리뷰어 신설이 정당화되는 사례**다.
   → 키트 claude 어댑터에 `bash-reviewer` 를 추가해 팀원 프로젝트에도 함께 배포한다.

- [ ] **Step 1: adopt-project.sh 를 키트 자신에게 적용**

```bash
cd ~/dev-orchestrate-kit
./adopt-project.sh . --claude
git status --short
```
Expected: `.claude/orchestrate.md`·`AGENTS.md`·`CLAUDE.md`·`.opencode/agent/_example.md`·
`scripts/` 가 생성된다. 기존 `README.md`·`install.sh`·`docs/` 는 **변경 없음**
(`git status` 에 M 표시가 없어야 한다 — 있으면 stamp 로직 버그이므로 Task 3 로 돌아간다)

- [ ] **Step 2: 작업용 스크립트를 vendored 원본으로 심링크**

```bash
cd ~/dev-orchestrate-kit
for f in run-delegation.sh phase-tools.py phase-claim.sh phase-close.sh \
         orchestrate-janitor.sh hook-selfcheck.sh docs-index.py session-cost.py; do
  rm -f "scripts/$f"
  ln -s "../core/scripts/$f" "scripts/$f"
done
ls -l scripts/ | head -3
bash scripts/hook-selfcheck.sh
```
Expected: 심링크 8개(`scripts/x -> ../core/scripts/x`). `hook-selfcheck.sh` 는
`HOOK_SELFCHECK_PASS` 출력 (심링크 너머로 정상 실행되는지 확인)

- [ ] **Step 3: bash 리뷰어 신설**

`adapters/claude/project/.claude/agents/bash-reviewer.md` 생성:

```markdown
---
name: bash-reviewer
description: bash·sh 스크립트 리뷰 전문. 셸 스크립트를 추가·수정했을 때 사용한다. ECC 에 shell 전용 리뷰어가 없어 신설했다.
model: sonnet
tools: Read, Grep, Glob, Bash
---

너는 셸 스크립트 리뷰어다. 구현하지 말고 리뷰만 한다.

각 발견을 심각도로 분류한다: 🔴 Critical / 🟡 Major / 🟢 Minor.

## 반드시 확인할 것

**이식성 (이 저장소는 macOS 기본 bash 3.2 를 지원해야 한다)**
- `mapfile`·`readarray`·연관배열(`declare -A`)·`${var^^}` — bash 4+ 전용. 3.2 에서 죽는다
- GNU 전용 플래그: `sed -i` (BSD sed 는 인자 필요), `readlink -f`, `date -d`
- `echo -e` 대신 `printf` — 셸마다 동작이 다르다

**안전성**
- `set -euo pipefail` 이 있는가. 없다면 실패가 조용히 지나간다
- 인용 누락: `$var` 가 공백 있는 경로에서 깨지는가. `[ -n $x ]` 같은 비인용 테스트
- `rm -rf "$dir"` 에서 `$dir` 이 빈 값일 수 있는 경로가 있는가 (`rm -rf /` 위험)
- 비밀 값이 stdout·로그에 찍히는가 (키 이름만 출력해야 한다)

**정확성**
- 파이프라인 종료 코드: `cmd | grep -q` 의 실패가 의도대로 전파되는가
- `grep -c` 는 0건일 때 exit 1 이다 — `|| true` 없이 `set -e` 아래 쓰면 스크립트가 죽는다
- 멱등성: 두 번 실행하면 같은 결과인가. append 가 중복되지 않는가
- 기존 파일을 덮어쓰는가 — 이 저장소는 "기존 파일 절대 미덮음"이 규칙이다

**금지 사항**
- `CLAUDE_CODE_SUBAGENT_MODEL` 을 쓰는 코드는 무조건 🔴 — frontmatter 차등을 무력화한다

마지막 줄에 판정을 쓴다: VERDICT: PASS 또는 VERDICT: REJECT
```

키트 자신도 이 리뷰어를 쓰도록 복사한다:

```bash
cd ~/dev-orchestrate-kit
mkdir -p .claude/agents
cp adapters/claude/project/.claude/agents/bash-reviewer.md .claude/agents/
```

- [ ] **Step 4: opencode 에이전트 3개 작성**

`_example.md` 의 frontmatter 규격(특히 `permission.bash` deny 목록)을 그대로 따라
아래 3개를 만든 뒤 `_example.md` 를 삭제한다.

| 파일 | description | 담당 |
|---|---|---|
| `.opencode/agent/kit-scripts.md` | `설치·스캐폴드 bash 스크립트 (install.sh, lib/, core/opencode/*.sh, adapters/*/…/*.sh)` | bash 전반 |
| `.opencode/agent/kit-tests.md` | `python unittest 테스트 (tests/*.py)` | 테스트 |
| `.opencode/agent/kit-docs.md` | `README·docs/·템플릿 마크다운` | 문서 |

세 파일 모두 `model: openai/gpt-5.6-luna`(GPT 우선 정책의 수동 실행용 기본값), `mode: primary`,
`temperature: 0.1` 로 통일한다.

```bash
cd ~/dev-orchestrate-kit
rm -f .opencode/agent/_example.md
~/.opencode/bin/opencode agent list
```
Expected: `kit-scripts`·`kit-tests`·`kit-docs` 가 목록에 보인다

- [ ] **Step 5: 로스터 채우기**

`.claude/orchestrate.md` 의 `[TODO]` 를 아래 실측값으로 전부 채운다.

에이전트 로스터:

| 에이전트 | 담당 | 위험도 |
|---|---|---|
| `kit-scripts` | `install.sh`, `lib/`, `core/opencode/*.sh`, `adapters/**/*.sh` | ⚠️ — 설치 스크립트가 사용자 홈(`~/.claude`, `~/.config`)을 건드린다 |
| `kit-tests` | `tests/*.py` | 낮음 |
| `kit-docs` | `README.md`, `docs/`, `core/project-template/**/*.md` | 낮음 |

리뷰어 매핑:

| 구현 에이전트 | 리뷰어 | 출처 |
|---|---|---|
| `kit-scripts` | `bash-reviewer` + `security-reviewer` + `silent-failure-hunter` | 프로젝트 신설 + ECC |
| `kit-tests` | `python-reviewer` | ECC |
| `kit-docs` | `code-reviewer` | ECC |

> `bash-reviewer` 신설 근거: ECC 68개 에이전트에 shell 전용 리뷰어가 없음(2026-08-07 실측).
> 이 저장소는 코드의 대부분이 bash 다.

TDD 게이트 / 검증 명령:

| 도메인 | 테스트 위치 | 러너 |
|---|---|---|
| 전체 | `tests/*.py` | `python3 -m unittest discover -s tests -v` |
| bash 문법 | — | `bash -n <파일>` (실행 없이 파싱만) |

커밋 scope: `install`·`stamp`·`policy`·`profile`·`containers`·`docs`. `main` 직접 push 금지.

프로젝트 주의사항:
- `scripts/*` 는 `core/scripts/*` 로의 심링크다. **작업용을 직접 고치지 말 것** — 원본을 고친다.
- 설치 스크립트를 테스트할 때 실제 `~/.claude`·`~/.config` 를 건드리지 말 것.
  주입 플래그(`--agents-dir`·`--settings`·`--policy`)나 임시 디렉터리를 쓴다.

- [ ] **Step 6: AGENTS.md·CLAUDE.md 채우기**

`AGENTS.md` 의 아키텍처 절에 Task 1 의 디렉터리 구조(core/adapters/containers)와 각 책임을 쓴다.
검증 절에는 `python3 -m unittest discover -s tests -v` 를 절대 명령으로 쓴다.

`CLAUDE.md` 의 프로젝트 개요·검증 명령·브랜치 규칙을 채우고, **함정 절에 다음을 추가**한다:

```markdown
- **`scripts/` 는 `core/scripts/` 로의 심링크다** — 작업용을 고치면 vendored 원본과 갈라진다.
  항상 `core/scripts/` 를 고칠 것.
- **설치 스크립트 테스트가 실제 홈을 오염시킬 수 있다** — `apply-plan-profile.sh` 는 기본값이
  `~/.claude/agents` 다. 테스트에서는 반드시 `--agents-dir`·`--settings` 주입 플래그를 쓸 것.
```

- [ ] **Step 7: 검증**

```bash
cd ~/dev-orchestrate-kit
bash scripts/hook-selfcheck.sh
~/.opencode/bin/opencode agent list
grep -c '\[TODO' .claude/orchestrate.md CLAUDE.md AGENTS.md
python3 -m unittest discover -s tests -v
```
Expected: `HOOK_SELFCHECK_PASS`, 에이전트 3개 로드, `[TODO` 각 0건, 테스트 전부 통과

- [ ] **Step 8: 위임 1회 실전 확인 (Task 4 첫 위임 전 리허설)**

```bash
cd ~/dev-orchestrate-kit
mkdir -p .orchestrate
cat > .orchestrate/smoke.md <<'EOF'
core/opencode/README.md 파일을 새로 만들어라. 내용은 이 디렉터리의 각 파일이
무엇을 하는지 한 줄씩 설명하는 표 하나면 충분하다. 다른 파일은 건드리지 마라.
EOF
bash scripts/run-delegation.sh kit-docs .orchestrate/smoke.md .orchestrate/smoke.log
```
Expected: 출력에 `MODEL_USED=openai/gpt-5.6-luna` (GPT 우선 정책이 실제로 적용되는지 확인).
`core/opencode/README.md` 가 생성된다. 실패하면 로스터·에이전트 정의를 먼저 고친다.

- [ ] **Step 9: 커밋**

```bash
cd ~/dev-orchestrate-kit
rm -rf .orchestrate/smoke.md .orchestrate/smoke.log
git add -A
git commit -m "feat: 키트를 오케스트레이션 대상으로 전환 (도그푸딩)

로스터·opencode 에이전트 3종·bash-reviewer 신설. scripts/ 는 core/scripts/ 심링크라
배포본과 작업본이 갈라질 수 없다. Task 4~11 은 이 인프라로 위임 진행한다."
```

---

## 완료 기준

- [ ] `python3 -m unittest discover -s tests -v` 전부 통과
- [ ] `./new-project.sh` 와 `./adopt-project.sh` 가 claude·codex·both 각각으로 동작
- [ ] `INSTALL_PARSE_ONLY=1 bash install.sh --claude --providers=qwen,openai --plan=max20 typescript` 파싱 정상
- [ ] `bash core/opencode/model-doctor.sh --skip-smoke` 가 이 호스트에서 통과
- [ ] `grep -rn CLAUDE_CODE_SUBAGENT_MODEL adapters/ core/ install.sh` 가 **방어적 삭제 코드 외에는 0건**
- [ ] `docker compose config` 가 `containers/browser`·`containers/antigravity` 양쪽에서 통과
- [ ] `git status` 클린 (모든 변경 커밋됨)
