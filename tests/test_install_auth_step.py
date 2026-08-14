"""설치 마법사의 구독 프로바이더 인증 동의 계약을 검증한다."""
import re
import tempfile
import unittest
from pathlib import Path

from _install_helpers import RUN_TIMEOUT, run_install, run_install_with_fake_tools, temporary_directory


class InstallAuthStepTest(unittest.TestCase):
    def run_auth_install(self, *, login_rc=0, login_rcs=None, include_opencode=True,
                         providers="1"):
        """선택한 구독 인증을 프로바이더별 종료 코드로 실행한다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "opencode-argv.log"
            fake_tools = {
                "git": "#!/bin/bash\nexit 0\n", "python3": "#!/bin/bash\nexit 0\n",
                "jq": "#!/bin/bash\nexit 0\n", "curl": "#!/bin/bash\nprintf 'exit 0\\n'\n",
                "claude": "#!/bin/bash\nexit 0\n",
            }
            if include_opencode:
                fake_home_tools = {".opencode/bin/opencode": "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$OPENCODE_ARGV_LOG\"\nprintf '\\n' >> \"$OPENCODE_ARGV_LOG\"\n[ \"$1\" = --version ] && exit 0\nprovider=\nwhile [ \"$#\" -gt 0 ]; do\n  [ \"$1\" = -p ] && { provider=$2; break; }\n  shift\ndone\ncase \"$provider\" in\n  openai) exit \"${OPENCODE_LOGIN_RC_OPENAI:-${OPENCODE_LOGIN_RC:-0}}\";;\n  xai) exit \"${OPENCODE_LOGIN_RC_XAI:-${OPENCODE_LOGIN_RC:-0}}\";;\nesac\nexit \"${OPENCODE_LOGIN_RC:-0}\"\n"}
            else:
                fake_home_tools = {}
            provider_rc_env = {
                f"OPENCODE_LOGIN_RC_{provider.upper()}": str(rc)
                for provider, rc in (login_rcs or {}).items()
            }
            result = run_install_with_fake_tools(
                fake_tools=fake_tools, pseudo_tty=True,
                stdin=f"\n\n{providers}\n\n\n4\n1\n",
                INSTALL_PLAIN_MENU="1", OPENCODE_ARGV_LOG=str(argv_log),
                OPENCODE_LOGIN_RC=str(login_rc),
                **provider_rc_env,
                fake_home_tools=fake_home_tools,
            )
            return result, argv_log.read_text() if argv_log.exists() else ""

    def test_auth_step_skipped_without_subscription_provider(self):
        """키 기반 프로바이더만 선택하면 인증 단계와 선택값이 없다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||3||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=qwen\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers containers plan summary\n",
            details,
        )

    def test_auth_step_collects_subscription_providers(self):
        """선택한 구독 프로바이더는 기본 인증 동의값과 단계에 반영된다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||1|||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=openai\n"
            "SELFTEST WIZARD AUTH=openai\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth containers plan summary\n",
            details,
        )

    def test_auth_step_back_returns_to_providers(self):
        """인증 단계의 뒤로가기는 프로바이더 질문을 다시 표시한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||1|b|1|||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=openai\n"
            "SELFTEST WIZARD AUTH=openai\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth providers auth containers plan summary\n",
            details,
        )

    def test_auth_default_covers_subscription_providers_in_providers_order(self):
        """기본 인증값은 프로바이더 선택 순서의 구독형만 공백으로 담는다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||3 1 2|||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=qwen,openai,xai\n"
            "SELFTEST WIZARD AUTH=openai xai\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth containers plan summary\n",
            details,
        )

    def test_auth_selection_follows_providers_order(self):
        """인증 기본값은 카탈로그 순서가 아니라 프로바이더 선택 순서를 따른다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||2 1|||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=xai,openai\n"
            "SELFTEST WIZARD AUTH=xai openai\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth containers plan summary\n",
            details,
        )

    def test_back_to_providers_clears_auth_when_subscription_dropped(self):
        """구독형을 키 기반만으로 바꾸면 이전 인증 선택을 비운다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||1|b|3||4|1",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=qwen\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth providers containers plan summary\n",
            details,
        )

    def test_auth_step_read_failure_is_fail_closed(self):
        """인증 입력을 읽지 못하면 기본값 대신 빈 인증 목록으로 확정한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_WIZARD": "1",
                    "INSTALL_SELFTEST_INPUTS": "1||1|__READ_FAILURE__",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "SELFTEST WIZARD HARNESSES=claude\n"
            "SELFTEST WIZARD ECC=\n"
            "SELFTEST WIZARD PROVIDERS=openai\n"
            "SELFTEST WIZARD AUTH=\n"
            "SELFTEST WIZARD CONTAINERS=\n"
            "SELFTEST WIZARD MCP=0\n"
            "SELFTEST WIZARD PLAN=skip\n"
            "SELFTEST WIZARD STEPS=harness ecc providers auth\n",
            details,
        )

    def test_auth_selftest_reports_would_run_without_executing(self):
        """인증 셀프테스트는 실제 로그인 대신 실행 예정 명령만 보고한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_AUTH": "1",
                    "INSTALL_AUTH_LOGIN": "xai openai",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "AUTH_LOGIN_WOULD_RUN=xai ~/.opencode/bin/opencode auth login -p xai\n"
            "AUTH_LOGIN_WOULD_RUN=openai ~/.opencode/bin/opencode auth login -p openai -m \"ChatGPT Pro/Plus (headless)\"\n",
            details,
        )

    def test_auth_failure_does_not_abort_install(self):
        """실패 주입된 로그인 뒤에도 다음 프로바이더를 계속 처리한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_AUTH": "1",
                    "INSTALL_AUTH_LOGIN": "xai openai",
                    "INSTALL_AUTH_FAIL": "xai",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(
            result.stdout,
            "AUTH_LOGIN_FAILED=xai\n"
            "AUTH_LOGIN_WOULD_RUN=openai ~/.opencode/bin/opencode auth login -p openai -m \"ChatGPT Pro/Plus (headless)\"\n",
            details,
        )

    def test_actual_auth_login_runs_selected_provider(self):
        """선택한 OpenAI 구독 인증은 설치된 실행 파일로 로그인한다."""
        result, argv = self.run_auth_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<auth><login><-p><openai>", argv)

    def test_actual_auth_login_failure_warns_and_continues(self):
        """실제 로그인 거부는 경고만 내고 설치를 성공 종료한다."""
        result, argv = self.run_auth_install(login_rc=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<auth><login><-p><openai>", argv)
        self.assertIn("openai 로그인 실패", result.stdout)

    def test_partial_auth_failure_retries_only_failed_provider(self):
        """부분 로그인 실패는 실패한 xai에 대해서만 재시도를 안내한다."""
        result, argv = self.run_auth_install(
            providers="1 2", login_rcs={"openai": 0, "xai": 1},
        )
        details = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\nargv:\n{argv}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("<auth><login><-p><openai>", argv, details)
        self.assertIn("<auth><login><-p><xai>", argv, details)
        manual_steps = result.stdout[result.stdout.index("== 남은 수동 단계") :]
        self.assertIn("xai 로그인 재시도:", manual_steps, details)
        self.assertNotIn(
            "openai 로그인 재시도:", manual_steps,
            f"성공한 프로바이더의 재시도 안내가 출력됐다.\n{details}",
        )
        self.assertIn("설치 완료 (일부 항목 수동 조치 필요).", result.stdout, details)

    def test_auth_failure_does_not_suggest_claude_install_or_duplicate_steps(self):
        """인증 실패만 있을 때 Claude 설치 안내와 수동 단계 번호는 정상이다."""
        result, _ = self.run_auth_install(login_rc=1)
        details = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertNotIn("Claude CLI 수동 설치", result.stdout, details)
        manual_steps = result.stdout[result.stdout.index("== 남은 수동 단계") :]
        numbers = [int(value) for value in re.findall(r"(?m)^\s+(\d+)\)", manual_steps)]
        self.assertEqual(numbers, sorted(numbers), details)
        self.assertEqual(len(numbers), len(set(numbers)), details)

    def test_auth_container_and_mcp_failures_change_final_summary(self):
        """6b: 보조 실행 실패도 기존 실패 집계와 마감 문구에 반영해야 한다."""
        result, _ = self.run_auth_install(login_rc=1)
        self.assertIn("설치 완료 (일부 항목 수동 조치 필요).", result.stdout)

    def test_missing_opencode_binary_has_distinct_warning(self):
        """6b: 실행 파일 부재와 로그인 거부 경고는 구분되어야 한다."""
        result, _ = self.run_auth_install(include_opencode=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("opencode 실행 파일이 없어", result.stdout)
        self.assertNotIn("openai 로그인 실패", result.stdout)


if __name__ == "__main__":
    unittest.main()
