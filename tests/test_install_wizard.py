"""install.sh 설치 마법사 계약의 통합 테스트."""
import os
import select
import signal
import subprocess
import tempfile
import time
import unittest

from _install_helpers import KIT, RUN_TIMEOUT, run_install

INSTALL = KIT / "install.sh"


class InstallWizardTest(unittest.TestCase):
    def test_back_navigation_resets_dependent_steps(self):
        """하네스를 바꾸고 뒤로 가면 Claude 전용 선택을 초기화한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1|b|2||||1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=codex\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD PLAN=\n"
            "SELFTEST WIZARD STEPS=harness ecc harness ecc providers containers summary\n",
            details,
        )

    def test_wizard_forward_flow_collects_all_choices(self):
        """정방향 마법사는 각 선택값과 표시 순서를 확정한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1|typescript|1|||2|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=typescript\n"
            "SELFTEST WIZARD PROVIDERS=openai\n"
            "SELFTEST WIZARD AUTH=openai\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=max5\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth containers plan summary\n",
            details,
        )

    def test_full_wizard_flow_keeps_auth_container_and_mcp_choices_consistent(self):
        """한 번의 정방향 실행은 인증·컨테이너·MCP 선택을 함께 보존한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1|typescript|1||1 2|4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=typescript\n"
            "SELFTEST WIZARD PROVIDERS=openai\n"
            "SELFTEST WIZARD AUTH=openai\n"
            "SELFTEST WIZARD CONTAINERS=browser\n"
            "SELFTEST WIZARD MCP=1\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth containers plan summary\n",
            details,
        )

    def test_ecc_step_back_returns_to_harness_and_recollects_choices(self):
        """ECC 단계의 뒤로가기도 앞 단계 상태를 다시 일관되게 확정한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1|b|1|typescript|3||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD ECC=typescript\n", result.stdout, details)
        self.assertIn(
            "STEPS=harness ecc harness ecc providers containers plan summary\n",
            result.stdout,
            details,
        )

    def test_wizard_read_failure_returns_rc11_contract(self):
        """입력 불가 선택은 안내·기본값과 rc=11 경로로 마법사를 마친다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "__READ_FAILURE__",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn('입력을 읽지 못해 기본값("")으로 진행한다.', result.stderr, details)
        self.assertIn("최종 확인(요약) 단계를 건너뛰고 설치를 진행한다.", result.stderr, details)
        self.assertEqual(result.stdout.splitlines()[-1], "SELFTEST WIZARD STEPS=harness", details)

    def test_wizard_summary_back_returns_to_last_visible_step(self):
        """요약의 뒤로가기는 마지막으로 표시한 plan 단계로 돌아간다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||||1|2|4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers containers plan summary plan summary\n",
            details,
        )

    def test_wizard_skips_steps_fixed_by_flags(self):
        """CLI 플래그로 고정한 선택의 단계는 표시하지 않는다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                ("--claude", "--providers=qwen", "--plan=pro", "typescript"),
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=typescript\n"
            "SELFTEST WIZARD PROVIDERS=qwen\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=pro\n"
            "SELFTEST WIZARD STEPS=containers summary\n",
            details,
        )

    def test_wizard_marker_lines_are_eight(self):
        """Claude 마법사 셀프테스트 마커는 여덟 줄이며 MCP가 컨테이너 다음이다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        markers = [line for line in result.stdout.splitlines() if line.startswith("SELFTEST WIZARD ")]
        self.assertEqual(
            markers,
            [
                "SELFTEST WIZARD HARNESSES=claude",
                "SELFTEST WIZARD ECC=",
                "SELFTEST WIZARD PROVIDERS=",
                "SELFTEST WIZARD AUTH=",
                "SELFTEST WIZARD CONTAINERS=",
                "SELFTEST WIZARD MCP=0",
                "SELFTEST WIZARD PLAN=skip",
                "SELFTEST WIZARD STEPS=harness ecc providers containers plan summary",
            ],
            details,
        )

    def test_wizard_has_no_side_effects(self):
        """마법사 함수는 변수 확정 외 설치 부작용을 포함하지 않는다."""
        source = INSTALL.read_text()
        start = source.find("run_install_wizard() {")
        self.assertNotEqual(start, -1, "run_install_wizard 함수가 없다.")
        end = source.find("\n}", start)
        self.assertNotEqual(end, -1, "run_install_wizard 함수의 닫는 중괄호를 찾지 못했다.")
        wizard_body = source[start:end + 2]

        for forbidden in ("git clone", "gen-policy.sh", "apply-plan-profile.sh", "docker", "auth login"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, wizard_body)

    def test_menu_read_has_no_default_idle_timeout(self):
        """일반 메뉴 입력은 유휴 상한을 지정하지 않으면 첫 선택을 끝내지 않는다."""
        source = INSTALL.read_text()
        forbidden = "${INSTALL_MENU_IDLE_LIMIT:-"
        self.assertNotIn(
            forbidden,
            source,
            f"기본 메뉴 유휴 상한 패턴이 발견됐다: {forbidden}",
        )

        start = source.find("read_line_interactive() {")
        self.assertNotEqual(start, -1, "read_line_interactive 함수가 없다.")
        end = source.find("\n}", start)
        self.assertNotEqual(end, -1, "read_line_interactive 함수의 닫는 중괄호를 찾지 못했다.")
        reader_body = source[start:end + 2]
        self.assertIn(
            'elif ! read -r "$_line_var"; then',
            reader_body,
            "상한 미설정 시 타임아웃 없는 표준 입력 read -r 분기가 없다.",
        )
        self.assertIn(
            'elif ! read -r "$_line_var" </dev/tty; then',
            reader_body,
            "상한 미설정 시 타임아웃 없는 /dev/tty read -r 분기가 없다.",
        )

        home = tempfile.TemporaryDirectory()
        master_fd, slave_fd = os.openpty()
        process = subprocess.Popen(
            ["/bin/bash", str(INSTALL)],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env={
                **os.environ,
                "INSTALL_SELFTEST_TUI": "1",
                "INSTALL_PLAIN_MENU": "1",
                "TERM": "xterm",
                "HOME": home.name,
            },
            start_new_session=True,
        )
        os.close(slave_fd)
        try:
            # 첫 choose_one만 관측한다. 5초 기본 상한 회귀는 이 기간 안에
            # SELFTEST TUI ONE 마커를 출력하지만, 상한이 없으면 출력하지 않는다.
            output = b""
            deadline = time.monotonic() + 6.5
            while time.monotonic() < deadline:
                remaining = max(0, deadline - time.monotonic())
                ready, _, _ = select.select([master_fd], [], [], remaining)
                if not ready:
                    break
                output += os.read(master_fd, 4096)
                self.assertNotIn(
                    b"SELFTEST TUI ONE=",
                    output,
                    "유휴 상한 미지정 메뉴가 첫 선택을 자동으로 완료했다.",
                )
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=RUN_TIMEOUT)
            os.close(master_fd)
            home.cleanup()

    def test_tui_sigint_exits_within_three_seconds(self):
        """TUI 대기 중 Ctrl-C는 프로세스 그룹 전체를 3초 안에 종료한다."""
        master_fd, slave_fd = os.openpty()
        process = subprocess.Popen(
            ["/bin/bash", str(INSTALL)],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env={
                **os.environ,
                "INSTALL_SELFTEST_TUI": "1",
                "TERM": "xterm",
            },
            start_new_session=True,
        )
        os.close(slave_fd)
        try:
            # 트랩을 설치한 첫 TUI 렌더링 뒤에만 신호를 보낸다.
            ready, _, _ = select.select([master_fd], [], [], 2)
            self.assertTrue(ready, "TUI 첫 화면이 2초 안에 출력되지 않았다.")
            os.read(master_fd, 4096)
            os.killpg(process.pid, signal.SIGINT)
            self.assertIsNotNone(process.wait(timeout=3), "SIGINT 뒤 TUI가 종료하지 않았다.")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=RUN_TIMEOUT)
            os.close(master_fd)


if __name__ == "__main__":
    unittest.main()
