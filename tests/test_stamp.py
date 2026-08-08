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

    def test_placeholders_do_not_touch_preexisting_files(self):
        """대상 저장소가 __PROJECT__ 를 정당하게 포함하는 파일을 이미 갖고 있어도
        (예: 키트 자신에게 adopt 할 때의 core/project-template/ 원본, 문서
        코드블록 등) stamp_placeholders 는 이번에 새로 복사된 파일만 건드려야
        한다. 실측 결함: 예전 구현은 대상 트리 전체를 grep -rl 로 훑어서
        기존 파일까지 치환했다."""
        preexisting = self.target / "existing-doc.md"
        preexisting_text = "이 문서는 예시로 __PROJECT__ 를 코드블록에 남겨둔다.\n"
        preexisting.write_text(preexisting_text)
        run_bash(f'stamp_copy "{KIT}" "{self.target}" "claude"')
        run_bash(f'stamp_placeholders "{self.target}" "myproj"')
        self.assertEqual(preexisting.read_text(), preexisting_text)
        # 새로 복사된 파일은 여전히 정상적으로 치환되어야 한다.
        roster = (self.target / ".claude/orchestrate.md").read_text()
        self.assertIn("myproj", roster)
        self.assertNotIn("__PROJECT__", roster)


if __name__ == "__main__":
    unittest.main()
