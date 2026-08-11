"""bash-guard fail-closed 단어 경계 판정 테스트."""
import filecmp
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
GUARD = KIT / ".claude/hooks/bash-guard.sh"
DEPLOYED_GUARD = KIT / "adapters/claude/project/.claude/hooks/bash-guard.sh"


def run_guard(command, env=None):
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(GUARD)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=run_env,
    )


class BashGuardTest(unittest.TestCase):
    def test_dangerous_commands_are_blocked(self):
        for command, expected_reason in (
            ("sudo ls", "sudo"),
            ("apt-get install -y jq && sudo true", "sudo"),
            ("echo x | sudo tee /etc/f", "sudo"),
            ('bash -c "sudo ls"', "sudo"),
            ('sh -c "sudo ls"', "sudo"),
            ('eval "sudo ls"', "sudo"),
            ("SUDO_ASKPASS=x sudo ls", "sudo"),
            ("command sudo ls", "sudo"),
            ("time sudo ls", "sudo"),
            ("xargs sudo ls", "sudo"),
            ("xargs -n1 sudo", "sudo"),
            ("find . | xargs sudo rm", "sudo"),
            ("echo x | xargs sudo ls", "sudo"),
            ("/usr/bin/sudo ls", "sudo"),
            ("/bin/sudo ls", "sudo"),
            # git commit 메시지 이외의 인용문은 fail-closed 정책상 그대로 검사한다.
            ('echo "no sudo here"', "sudo"),
            ("rm -rf /tmp/x", "rm -rf"),
            ("git push origin main", "main 직접 push"),
            ("git push --force", "force push"),
            ('git commit -m "x" && sudo ls', "sudo"),
            ("git status\nsudo ls", "sudo"),
            ("sudo;ls", "sudo"),
            ("sudo|ls", "sudo"),
            ("sudo&ls", "sudo"),
            ("(sudo)ls", "sudo"),
            ("$(which sudo) ls", "sudo"),
            ("rm -rf;ls", "rm -rf"),
            ("git push origin main;ls", "main 직접 push"),
            ("git push --force;ls", "force push"),
            ('git commit -m "$(sudo rm -rf /tmp/x)"', "sudo"),
            ('git commit -m "$(rm -rf /)"', "rm -rf"),
            ('git commit --message "`sudo id`"', "sudo"),
            ('git commit -m "safe" -m "$(sudo ls)"', "sudo"),
        ):
            with self.subTest(command=command):
                result = run_guard(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(expected_reason, result.stderr)

    def test_git_commit_messages_and_safe_commands_are_allowed(self):
        for command in (
            'git commit -m "docs: sudo 자동 설치 설계"',
            'git commit -m "fix: rm -rf 가드"',
            "git commit -m 'feat: sudo 3단계 동의'",
            'git commit --message "docs: sudo 언급"',
            'git commit -m "fix: docker compose down loop bug"',
            'git commit -m "x" && ls',
            "git status",
            "ls -la",
            "pseudo ls",
            "sudoedit /etc/hosts",
            "git log --oneline -5",
            "git push origin main2",
        ):
            with self.subTest(command=command):
                result = run_guard(command)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_jq_failure_blocks_defensively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)
            for name in ("bash", "grep"):
                target = shutil.which(name)
                self.assertIsNotNone(target)
                (bin_dir / name).symlink_to(target)
            result = run_guard("sudo ls", {"PATH": str(bin_dir)})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("jq 실행 실패", result.stderr)

    def test_sed_failure_scans_original_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)
            for name in ("bash", "grep", "jq"):
                target = shutil.which(name)
                self.assertIsNotNone(target)
                (bin_dir / name).symlink_to(target)
            result = run_guard("git status && sudo ls", {"PATH": str(bin_dir)})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("sed 실행 실패", result.stderr)
        self.assertIn("sudo", result.stderr)

    def test_deployed_and_dogfooding_guards_are_identical(self):
        self.assertTrue(filecmp.cmp(GUARD, DEPLOYED_GUARD, shallow=False))


if __name__ == "__main__":
    unittest.main()
