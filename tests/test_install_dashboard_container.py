"""usage-dashboard 컨테이너(--containers=dashboard) 계약을 검증한다.

Phase 6 동결 테스트 — 오케스트레이터가 작성·동결(PITFALLS 14). 위임의 수정 금지.
"""
import re
import socket
import unittest
from pathlib import Path

from _install_helpers import (
    KIT, RUN_TIMEOUT, run_install, run_install_with_fake_tools, temporary_directory,
)


INSTALL = KIT / "install.sh"
DASH_COMPOSE = "components/usage-dashboard/docker-compose.yml"


def available_port():
    """잠시 바인드·재바인드해 현재 비어 있는 포트를 고른다."""
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as first_socket:
            first_socket.bind(("127.0.0.1", 0))
            port = first_socket.getsockname()[1]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as second_socket:
                second_socket.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise RuntimeError("비어 있는 포트를 고르지 못했다.")


class InstallDashboardContainerTest(unittest.TestCase):
    def details(self, result, extra=""):
        return (
            f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n{extra}"
        )

    def test_dashboard_selftest_would_run(self):
        """dashboard 셀프테스트는 서브모듈 init 예정과 compose 실행 예정을 순서대로 남긴다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "dashboard"})
        details = self.details(result)
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_SUBMODULE_WOULD_INIT=dashboard\n", result.stdout, details)
        run_line = next(
            (line for line in result.stdout.splitlines() if line.startswith("CONTAINER_INSTALL_WOULD_RUN=dashboard ")),
            None,
        )
        self.assertIsNotNone(run_line, details)
        self.assertIn(DASH_COMPOSE, run_line, details)
        self.assertIn("up -d", run_line, details)
        init_idx = result.stdout.index("CONTAINER_SUBMODULE_WOULD_INIT=dashboard")
        run_idx = result.stdout.index("CONTAINER_INSTALL_WOULD_RUN=dashboard")
        self.assertLess(init_idx, run_idx, details)

    def test_both_containers_selftest(self):
        """browser,dashboard 동시 지정은 각자 자기 compose 경로로 실행 예정을 남긴다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser,dashboard"})
        details = self.details(result)
        self.assertEqual(result.returncode, 0, details)
        lines = result.stdout.splitlines()
        browser_line = next((l for l in lines if l.startswith("CONTAINER_INSTALL_WOULD_RUN=browser ")), None)
        dash_line = next((l for l in lines if l.startswith("CONTAINER_INSTALL_WOULD_RUN=dashboard ")), None)
        self.assertIsNotNone(browser_line, details)
        self.assertIsNotNone(dash_line, details)
        self.assertIn("containers/browser/docker-compose.yml", browser_line, details)
        self.assertNotIn(DASH_COMPOSE, browser_line, details)
        self.assertIn(DASH_COMPOSE, dash_line, details)
        self.assertNotIn("containers/browser", dash_line, details)

    def test_wizard_dashboard_item(self):
        """마법사 컨테이너 스텝에서 dashboard(3번 — browser·mcp 뒤)를 고를 수 있다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|3|4|1"})
        details = self.details(result)
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=dashboard\n", result.stdout, details)

    def test_wizard_both_containers_preserved(self):
        """browser+dashboard 동시 선택은 어느 쪽도 유실하지 않는다 (고정 순서 browser,dashboard)."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|1,3|4|1"})
        details = self.details(result)
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=browser,dashboard\n", result.stdout, details)

    def test_wizard_mcp_with_dashboard_only_downgrades_mcp(self):
        """mcp+dashboard(browser 미선택) 조합에서 mcp 는 경고와 함께 해제된다 (Phase 6 리뷰 🔴 고정)."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|2,3|4|1"})
        details = self.details(result)
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=dashboard\n", result.stdout, details)
        self.assertIn("SELFTEST WIZARD MCP=0\n", result.stdout, details)
        self.assertIn("browser", result.stderr, details)

    def test_manual_retry_lists_only_failed_container(self):
        """혼합 성공/실패 시 수동 재시도 목록은 실패한 컨테이너만 나열한다 (Phase 6 리뷰 🟠 고정)."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "docker-argv.log"
            cdp_port = available_port()
            dash_port = available_port()
            result = run_install_with_fake_tools(
                "--claude", "--containers=browser,dashboard",
                fake_tools={
                    "git": "#!/bin/bash\nexit 0\n",
                    "python3": "#!/bin/bash\nexit 0\n",
                    "jq": "#!/bin/bash\nexit 0\n",
                    "claude": "#!/bin/bash\nexit 0\n",
                    "docker": (
                        "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$DOCKER_ARGV_LOG\"\n"
                        "printf '\\n' >> \"$DOCKER_ARGV_LOG\"\n"
                        "if [ \"$1 $2\" = 'compose version' ]; then exit 0; fi\n"
                        "case \"$*\" in *usage-dashboard*) exit 1 ;; esac\n"
                        "exit 0\n"
                    ),
                },
                fake_home_tools={
                    ".opencode/bin/opencode": "#!/bin/bash\n[ \"$1\" = --version ] && exit 0\nexit 0\n",
                },
                pseudo_tty=True,
                stdin="\n\n\n1\ny\ny\n",
                INSTALL_PLAIN_MENU="1",
                INSTALL_CDP_PORT=str(cdp_port),
                INSTALL_DASH_PORT=str(dash_port),
                DOCKER_ARGV_LOG=str(argv_log),
            )
            argv = argv_log.read_text() if argv_log.exists() else ""
        details = self.details(result, f"docker argv:\n{argv}")
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("== 남은 수동 단계", result.stdout, details)
        manual_steps = result.stdout[result.stdout.index("== 남은 수동 단계"):]
        retry_lines = [line for line in manual_steps.splitlines() if "컨테이너 기동 재시도" in line]
        self.assertEqual(len(retry_lines), 1, details)
        self.assertIn("usage-dashboard", retry_lines[0], details)
        self.assertNotIn("containers/browser", retry_lines[0], details)

    def test_dashboard_fake_reasons(self):
        """docker 부재·포트 충돌·거절은 dashboard 를 비치명 사유로 건너뛴다."""
        cases = (
            ({"INSTALL_CONTAINER_FAKE": "docker_missing"}, "reason=docker_missing"),
            ({"INSTALL_CONTAINER_FAKE": "port_busy"}, "reason=port_busy"),
            ({"INSTALL_CONTAINER_CONSENT": "n"}, "reason=declined"),
        )
        for extra_env, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                with temporary_directory() as home:
                    result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "dashboard", **extra_env})
                details = self.details(result)
                self.assertEqual(result.returncode, 0, details)
                self.assertIn(f"CONTAINER_INSTALL_SKIPPED=dashboard {expected_reason}\n", result.stdout, details)
                self.assertNotIn("CONTAINER_INSTALL_WOULD_RUN=", result.stdout, details)

    def test_dashboard_real_startup_uses_own_port_and_compose(self):
        """실기동 경로에서 dashboard 는 자기 compose 경로와 자기 포트(INSTALL_DASH_PORT)를 쓴다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "docker-argv.log"
            port = available_port()
            result = run_install_with_fake_tools(
                "--claude", "--containers=dashboard",
                fake_tools={
                    "git": "#!/bin/bash\nexit 0\n",
                    "python3": "#!/bin/bash\nexit 0\n",
                    "jq": "#!/bin/bash\nexit 0\n",
                    "claude": "#!/bin/bash\nexit 0\n",
                    "docker": (
                        "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$DOCKER_ARGV_LOG\"\n"
                        "printf '\\n' >> \"$DOCKER_ARGV_LOG\"\n"
                        "if [ \"$1 $2\" = 'compose version' ]; then exit 0; fi\n"
                        "exit 0\n"
                    ),
                },
                fake_home_tools={
                    ".opencode/bin/opencode": "#!/bin/bash\n[ \"$1\" = --version ] && exit 0\nexit 0\n",
                },
                pseudo_tty=True,
                stdin="\n\n\n1\ny\n",
                INSTALL_PLAIN_MENU="1",
                INSTALL_DASH_PORT=str(port),
                DOCKER_ARGV_LOG=str(argv_log),
            )
            argv = argv_log.read_text() if argv_log.exists() else ""
        details = self.details(result, f"docker argv:\n{argv}")
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(
            argv,
            r"(?m)^<compose><-f><.+components/usage-dashboard/docker-compose\.yml><up><-d>$",
            details,
        )
        self.assertNotIn("containers/browser", argv, details)

    def test_dashboard_real_startup_skips_when_own_port_busy(self):
        """dashboard 포트가 점유되면 기동하지 않는다 — CDP 포트가 아니라 자기 포트를 검사해야 한다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "docker-argv.log"
            port = available_port()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
                blocker.bind(("127.0.0.1", port))
                blocker.listen(1)
                result = run_install_with_fake_tools(
                    "--claude", "--containers=dashboard",
                    fake_tools={
                        "git": "#!/bin/bash\nexit 0\n",
                        "python3": "#!/bin/bash\nexit 0\n",
                        "jq": "#!/bin/bash\nexit 0\n",
                        "claude": "#!/bin/bash\nexit 0\n",
                        "docker": (
                            "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$DOCKER_ARGV_LOG\"\n"
                            "printf '\\n' >> \"$DOCKER_ARGV_LOG\"\n"
                            "if [ \"$1 $2\" = 'compose version' ]; then exit 0; fi\n"
                            "exit 0\n"
                        ),
                    },
                    fake_home_tools={
                        ".opencode/bin/opencode": "#!/bin/bash\n[ \"$1\" = --version ] && exit 0\nexit 0\n",
                    },
                    pseudo_tty=True,
                    stdin="\n\n\n1\ny\n",
                    INSTALL_PLAIN_MENU="1",
                    INSTALL_DASH_PORT=str(port),
                    DOCKER_ARGV_LOG=str(argv_log),
                )
                argv = argv_log.read_text() if argv_log.exists() else ""
        details = self.details(result, f"docker argv:\n{argv}")
        self.assertEqual(result.returncode, 0, details)
        self.assertNotRegex(argv, r"<up><-d>", details)
        self.assertRegex(result.stdout + result.stderr, r"포트", details)


if __name__ == "__main__":
    unittest.main()
