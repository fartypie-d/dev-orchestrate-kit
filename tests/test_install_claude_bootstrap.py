"""install.sh Claude CLI 부트스트랩 드라이런 테스트 — 실제 설치를 하지 않는다."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from _install_helpers import KIT, RUN_TIMEOUT, dry_run


def run_install_with_fake_tools(*args, fake_tools, pseudo_tty=False,
                                minimal_path=False, **overrides):
    """실제 홈·네트워크 없이 설치 실패 경로를 끝까지 실행한다."""
    with tempfile.TemporaryDirectory() as home:
        bin_dir = Path(home) / "bin"
        bin_dir.mkdir()
        for name, content in fake_tools.items():
            path = bin_dir / name
            path.write_text(content)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        if minimal_path:
            for name in (
                "basename", "bash", "cat", "chmod", "cmp", "cp", "date", "dirname",
                "grep", "id", "mkdir", "mktemp", "mv", "rm", "sed", "tar", "uname",
            ):
                path = bin_dir / name
                if not path.exists():
                    path.write_text(f"#!/bin/bash\nexec /bin/{name} \"$@\"\n")
                    path.chmod(path.stat().st_mode | stat.S_IXUSR)
        env = {
            **os.environ,
            "HOME": home,
            # 사용자 셸의 claude/npm을 보지 않되 표준 도구는 사용할 수 있게 한다.
            "PATH": str(bin_dir) if minimal_path else str(bin_dir) + ":/usr/bin:/bin",
        }
        env.update(overrides)
        command = ["/bin/bash", str(KIT / "install.sh"), *args]
        if pseudo_tty:
            command = ["/usr/bin/script", "-q", "-c", " ".join(command), "/dev/null"]
        return subprocess.run(
            command, capture_output=True, text=True,
            input="y\n\n" if pseudo_tty else "\n", env=env,
            timeout=RUN_TIMEOUT,
        )


class InstallClaudeBootstrapTest(unittest.TestCase):
    def test_missing_claude_plans_npm_install(self):
        result = dry_run("--claude", INSTALL_TEST_NO_CLAUDE="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN CLAUDE=missing", result.stdout)
        self.assertIn("@anthropic-ai/claude-code", result.stdout)

    def test_missing_npm_plans_user_space_node_bootstrap(self):
        result = dry_run(
            "--claude",
            INSTALL_TEST_NO_CLAUDE="1",
            INSTALL_TEST_NO_NPM="1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN CLAUDE=missing", result.stdout)
        self.assertIn("DRY_RUN NODE_BOOTSTRAP=", result.stdout)
        self.assertNotIn("DRY_RUN NODE_BOOTSTRAP=없음", result.stdout)
        self.assertIn("nodejs.org/dist/", result.stdout)

    def test_unsupported_node_platform_is_reported_by_dry_run_hook(self):
        result = dry_run(
            "--claude",
            INSTALL_TEST_NO_CLAUDE="1",
            INSTALL_TEST_NO_NPM="1",
            INSTALL_TEST_NODE_UNAME="FreeBSD",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN NODE_BOOTSTRAP=미지원 운영체제: FreeBSD", result.stdout)

    def test_claude_npm_failure_is_visible_in_stdout_summary(self):
        result = run_install_with_fake_tools(
            "--claude", "--plan=pro",
            fake_tools={
                "git": "#!/usr/bin/env bash\nexit 0\n",
                "python3": "#!/usr/bin/env bash\nexit 0\n",
                "jq": "#!/usr/bin/env bash\nexit 0\n",
                "npm": "#!/usr/bin/env bash\nexit 1\n",
                "curl": "#!/usr/bin/env bash\nprintf 'exit 0\\n'\n",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Claude CLI 설치 실패", result.stdout)
        self.assertIn("npm i -g @anthropic-ai/claude-code", result.stdout)
        self.assertIn("일부 항목 수동 조치 필요", result.stdout)
        self.assertNotIn("\n   OK\n", result.stdout)

    def test_existing_user_node_is_reused_without_download(self):
        with tempfile.TemporaryDirectory() as home:
            node_bin = Path(home) / ".local/opt/node/bin"
            node_bin.mkdir(parents=True)
            for name, exit_code in (("node", 0), ("npm", 1)):
                path = node_bin / name
                path.write_text(f"#!/bin/bash\nexit {exit_code}\n")
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            result = run_install_with_fake_tools(
                "--claude", "--plan=pro",
                fake_tools={
                "git": "#!/bin/bash\nexit 0\n",
                "python3": "#!/bin/bash\nexit 0\n",
                "jq": "#!/bin/bash\nexit 0\n",
                "curl": "#!/bin/bash\nprintf 'exit 0\\n'\n",
            },
            pseudo_tty=True,
            minimal_path=True,
            HOME=home,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("기존 유저공간 Node 확인됨", result.stdout)
        self.assertNotIn("nodejs.org/dist/", result.stdout)
        self.assertNotIn(".local/opt/node.bak-", result.stdout)

    def test_codex_only_skips_claude_check(self):
        result = dry_run("--codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN CLAUDE=skipped", result.stdout)
        self.assertIn("DRY_RUN CLAUDE_INSTALL=없음", result.stdout)
        self.assertIn("DRY_RUN NODE_BOOTSTRAP=없음", result.stdout)

    @unittest.skipUnless(shutil.which("claude"), "claude CLI가 설치된 환경에서만 검증")
    def test_present_claude_is_reported(self):
        result = dry_run("--claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN CLAUDE=present", result.stdout)

    def test_claude_test_override_is_ignored_outside_dry_run(self):
        with tempfile.TemporaryDirectory() as home:
            bin_dir = Path(home) / "bin"
            bin_dir.mkdir()
            for name, content in {
                "git": "#!/usr/bin/env bash\nexit 0\n",
                "python3": "#!/usr/bin/env bash\nexit 0\n",
                "jq": "#!/usr/bin/env bash\nexit 0\n",
                "claude": "#!/usr/bin/env bash\nexit 0\n",
                "curl": "#!/usr/bin/env bash\necho '의도적인 2/7 중단' >&2\nexit 99\n",
            }.items():
                path = bin_dir / name
                path.write_text(content)
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            env = {
                **os.environ,
                "HOME": home,
                "INSTALL_TEST_NO_CLAUDE": "1",
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            }
            result = subprocess.run(
                ["bash", str(KIT / "install.sh"), "--claude"],
                capture_output=True, text=True, env=env,
                timeout=RUN_TIMEOUT,
            )
        self.assertEqual(result.returncode, 99, result.stderr)
        self.assertIn("claude CLI 확인됨", result.stdout)
        self.assertNotIn(
            "claude 하네스가 선택되었지만 Claude CLI가 없다", result.stderr
        )


if __name__ == "__main__":
    unittest.main()
