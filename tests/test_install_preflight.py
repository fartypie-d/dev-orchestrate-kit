"""install.sh 프리플라이트 드라이런 테스트 — 실제 설치나 홈 디렉터리 변경은 하지 않는다."""
import os
import stat
import tempfile
import unittest
from pathlib import Path

from _install_helpers import dry_run, run_install


class InstallPreflightTest(unittest.TestCase):
    def test_linux_package_managers_are_detected(self):
        cases = {
            "ubuntu": "apt-get",
            "fedora": "dnf",
            "arch": "pacman",
            "alpine": "apk",
            "opensuse-leap": "zypper",
        }
        for os_id, pm in cases.items():
            with self.subTest(os_id=os_id):
                result = dry_run("--claude", INSTALL_TEST_UNAME="Linux",
                                 INSTALL_TEST_OS_ID=os_id)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("DRY_RUN PM=" + pm, result.stdout)

    def test_darwin_uses_brew(self):
        result = dry_run("--claude", INSTALL_TEST_UNAME="Darwin")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN PM=brew", result.stdout)

    def test_unsupported_distribution_shows_manual_guidance(self):
        result = dry_run("--claude", INSTALL_TEST_UNAME="Linux",
                         INSTALL_TEST_OS_ID="nosuchdistro", INSTALL_TEST_MISSING="jq")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN PM=none", result.stdout)
        self.assertIn("수동 설치 명령", result.stderr)

    def test_missing_tools_are_in_install_plan(self):
        result = dry_run("--claude", INSTALL_TEST_UNAME="Linux",
                         INSTALL_TEST_OS_ID="ubuntu", INSTALL_TEST_MISSING="jq")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN MISSING=jq", result.stdout)
        self.assertIn("DRY_RUN INSTALL_CMD=", result.stdout)
        self.assertIn("jq", result.stdout)

    def test_package_index_sync_is_in_install_plan(self):
        cases = {
            "ubuntu": "apt-get update",
            "arch": "pacman -Sy --needed --noconfirm jq",
            "alpine": "apk update",
        }
        for os_id, command in cases.items():
            with self.subTest(os_id=os_id):
                result = dry_run("--claude", INSTALL_TEST_UNAME="Linux",
                                 INSTALL_TEST_OS_ID=os_id, INSTALL_TEST_MISSING="jq")
                self.assertEqual(result.returncode, 0, result.stderr)
                if os_id == "arch":
                    self.assertIn("DRY_RUN INSTALL_CMD=" + command, result.stdout)
                else:
                    self.assertIn("DRY_RUN SYNC_CMD=" + command, result.stdout)

    def test_no_missing_tools_have_no_install_plan(self):
        result = dry_run("--claude", INSTALL_TEST_UNAME="Linux",
                         INSTALL_TEST_OS_ID="ubuntu", INSTALL_TEST_MISSING="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN MISSING=", result.stdout)
        self.assertIn("DRY_RUN INSTALL_CMD=없음", result.stdout)

    def test_dry_run_reports_passwordless_sudo(self):
        with tempfile.TemporaryDirectory() as home:
            bin_dir = Path(home) / "bin"
            bin_dir.mkdir()
            for name, content in {
                "id": "#!/usr/bin/env bash\nprintf '1000\\n'\n",
                "sudo": "#!/usr/bin/env bash\n[ \"$1\" = \"-n\" ] && [ \"$2\" = \"true\" ]\n",
            }.items():
                path = bin_dir / name
                path.write_text(content)
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            env = {
                **os.environ,
                "INSTALL_DRY_RUN": "1",
                "INSTALL_TEST_UNAME": "Linux",
                "INSTALL_TEST_OS_ID": "ubuntu",
                "INSTALL_TEST_MISSING": "jq",
                "HOME": home,
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            }
            result = run_install(("--claude",), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY_RUN PRIVILEGE=sudo-nopass", result.stdout)

    def test_parse_only_exits_before_preflight(self):
        with tempfile.TemporaryDirectory() as home:
            env = {
                **os.environ,
                "INSTALL_PARSE_ONLY": "1",
                "INSTALL_TEST_UNAME": "Darwin",
                "INSTALL_TEST_OS_ID": "nosuchdistro",
                "INSTALL_TEST_MISSING": "jq",
                "HOME": home,
            }
            result = run_install(("--claude",), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HARNESSES=claude", result.stdout)
        self.assertNotIn("DRY_RUN PM=", result.stdout)

    def test_test_overrides_are_ignored_before_real_preflight(self):
        with tempfile.TemporaryDirectory() as home:
            bin_dir = Path(home) / "bin"
            bin_dir.mkdir()
            scripts = {
                "git": "#!/usr/bin/env bash\nexit 0\n",
                "curl": "#!/usr/bin/env bash\necho '의도적인 2/7 중단' >&2\nexit 99\n",
                "python3": "#!/usr/bin/env bash\nexit 0\n",
                "jq": "#!/usr/bin/env bash\nexit 0\n",
                "apt-get": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "dnf": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "pacman": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "apk": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "zypper": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "brew": "#!/usr/bin/env bash\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
                "sudo": "#!/usr/bin/env bash\nif [ \"$1\" = \"-n\" ] && [ \"$2\" = \"true\" ]; then exit 0; fi\necho '패키지 관리자 호출됨' >&2\nexit 99\n",
            }
            for name, content in scripts.items():
                path = bin_dir / name
                path.write_text(content)
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            env = {
                **os.environ,
                "INSTALL_TEST_UNAME": "Darwin",
                "INSTALL_TEST_OS_ID": "nosuchdistro",
                "INSTALL_TEST_MISSING": "not-a-real-tool",
                "HOME": home,
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            }
            result = run_install(("--claude",), env=env)
        self.assertEqual(result.returncode, 99, result.stderr)
        self.assertIn("== 1/7 필수 도구 확인", result.stdout)
        self.assertIn("== 2/7 opencode", result.stdout)
        self.assertIn("의도적인 2/7 중단", result.stderr)
        self.assertNotIn("패키지 관리자 호출됨", result.stderr)

    def test_dry_run_does_not_create_files_under_home(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            before = sorted(path.relative_to(home_path) for path in home_path.rglob("*"))

            result = run_install(
                ("--claude",),
                env={
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_TEST_UNAME": "Linux",
                    "INSTALL_TEST_OS_ID": "ubuntu",
                    "INSTALL_TEST_MISSING": "jq",
                    "HOME": home,
                },
            )

            after = sorted(path.relative_to(home_path) for path in home_path.rglob("*"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, before)

    def test_parse_only_ignores_test_overrides_without_dry_run(self):
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                ("--claude",),
                env={
                    "INSTALL_PARSE_ONLY": "1",
                    "INSTALL_TEST_UNAME": "Darwin",
                    "INSTALL_TEST_OS_ID": "nosuchdistro",
                    "INSTALL_TEST_MISSING": "not-a-real-tool",
                    "HOME": home,
                },
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DRY_RUN PM=", result.stdout)


if __name__ == "__main__":
    unittest.main()
