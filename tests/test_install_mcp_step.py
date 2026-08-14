"""설치 마법사의 chrome-devtools MCP 등록 계약을 검증한다."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from _install_helpers import (
    KIT, RUN_TIMEOUT, run_install, run_install_with_fake_tools, temporary_directory,
)


README = KIT / "README.md"
INSTALL = KIT / "install.sh"


class InstallMcpStepTest(unittest.TestCase):
    def run_mcp_install(self, *, list_mode="missing", add_rc=0):
        """MCP 선택 마법사를 거쳐 실제 등록 함수를 실행한다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "claude-argv.log"
            result = run_install_with_fake_tools(
                "--claude",
                fake_tools={
                    "git": "#!/bin/bash\nexit 0\n",
                    "python3": "#!/bin/bash\nexit 0\n",
                    "jq": "#!/bin/bash\nexit 0\n",
                    "curl": "#!/bin/bash\nprintf 'exit 0\\n'\n",
                    "docker": "#!/bin/bash\nexit 0\n",
                    "claude": "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$MCP_ARGV_LOG\"\nprintf '\\n' >> \"$MCP_ARGV_LOG\"\ncase \"$1 $2\" in\n  'mcp list') case \"$MCP_LIST_MODE\" in registered) printf 'chrome-devtools\\n';; failed) exit 1;; esac;;\n  'mcp add') exit \"${MCP_ADD_RC:-0}\";;\nesac\n",
                },
                fake_home_tools={".opencode/bin/opencode": "#!/bin/bash\n[ \"$1\" = --version ] && printf 'test\\n'\nexit 0\n"},
                pseudo_tty=True,
                stdin="\n1\n\n1 2\n4\n1\n",
                INSTALL_PLAIN_MENU="1",
                MCP_ARGV_LOG=str(argv_log),
                MCP_LIST_MODE=list_mode,
                MCP_ADD_RC=str(add_rc),
            )
            return result, argv_log.read_text() if argv_log.exists() else ""

    def test_mcp_item_shown_only_for_claude_harness(self):
        """MCP 항목은 Claude 선택에서만 마커 경로로 노출된다."""
        with tempfile.TemporaryDirectory() as claude_home:
            claude = run_install(env={"HOME": claude_home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3||4|1"})
        with tempfile.TemporaryDirectory() as codex_home:
            codex = run_install(env={"HOME": codex_home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "2||3||1"})
        details = (
            f"제한 시간: {RUN_TIMEOUT}초\n"
            f"claude stdout:\n{claude.stdout}\nclaude stderr:\n{claude.stderr}\n"
            f"codex stdout:\n{codex.stdout}\ncodex stderr:\n{codex.stderr}"
        )
        self.assertEqual(claude.returncode, 0, details)
        self.assertEqual(codex.returncode, 0, details)
        self.assertRegex(claude.stdout, r"(?m)^SELFTEST WIZARD MCP=0$", details)
        self.assertNotRegex(codex.stdout, r"(?m)^SELFTEST WIZARD MCP=", details)
        self.assertNotIn("mcp", next(line for line in codex.stdout.splitlines() if line.startswith("SELFTEST WIZARD STEPS=")), details)

    def test_mcp_marker_when_selected(self):
        """browser와 MCP를 함께 고르면 MCP 선택값이 분리된 마커에 남는다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|1 2|4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^SELFTEST WIZARD CONTAINERS=browser$", details)
        self.assertRegex(result.stdout, r"(?m)^SELFTEST WIZARD MCP=1$", details)
        steps = next(line for line in result.stdout.splitlines() if line.startswith("SELFTEST WIZARD STEPS="))
        self.assertEqual(steps, "SELFTEST WIZARD STEPS=harness ecc providers containers plan summary", details)
        self.assertNotIn("mcp", steps, details)
        self.assertLess(result.stdout.index("SELFTEST WIZARD CONTAINERS="), result.stdout.index("SELFTEST WIZARD MCP="), details)

    def test_mcp_downgraded_without_browser(self):
        """MCP만 고르면 브라우저 의존성 경고와 함께 등록 요청을 해제한다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|2|4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^SELFTEST WIZARD CONTAINERS=$", details)
        self.assertRegex(result.stdout, r"(?m)^SELFTEST WIZARD MCP=0$", details)
        self.assertRegex(result.stderr, r"(?i)browser", details)

    def test_wizard_marker_lines_are_eight(self):
        """Claude 마커 여덟 줄은 MCP를 컨테이너와 계획 사이에 둔다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3||4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        markers = [line for line in result.stdout.splitlines() if line.startswith("SELFTEST WIZARD ")]
        self.assertEqual(len(markers), 8, details)
        expected = ["HARNESSES", "ECC", "PROVIDERS", "AUTH", "CONTAINERS", "MCP", "PLAN", "STEPS"]
        self.assertEqual([line.split("=", 1)[0].removeprefix("SELFTEST WIZARD ") for line in markers], expected, details)
        for earlier, later in zip(markers, markers[1:]):
            self.assertLess(result.stdout.index(earlier), result.stdout.index(later), details)

    def test_mcp_register_would_run(self):
        """MCP 셀프테스트는 실제 등록 대신 chrome-devtools 실행 예정만 남긴다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_MCP": "1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^MCP_REGISTER_WOULD_RUN=chrome-devtools .+$", details)
        self.assertRegex(result.stdout, r"(?m)^MCP_REGISTER_WOULD_RUN=chrome-devtools .*-s\s+user(?:\s|$)", details)

    def test_mcp_skipped_without_cli(self):
        """Claude CLI가 없으면 정해진 비치명 이유로 등록을 건너뛴다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_MCP": "1", "INSTALL_MCP_FAKE": "no_cli"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^MCP_REGISTER_SKIPPED=chrome-devtools reason=no_cli$", details)

    def test_mcp_skipped_when_exists(self):
        """기존 등록이 있으면 정해진 비치명 이유로 등록을 건너뛴다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_MCP": "1", "INSTALL_MCP_FAKE": "exists"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^MCP_REGISTER_SKIPPED=chrome-devtools reason=exists$", details)

    def test_mcp_register_failed(self):
        """등록 명령 실패도 설치 자체는 중단하지 않는다."""
        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_MCP": "1", "INSTALL_MCP_FAKE": "fail"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(result.stdout, r"(?m)^MCP_REGISTER_FAILED=chrome-devtools$", details)

    def test_actual_mcp_skips_when_claude_cli_is_absent(self):
        """실행 경로는 PATH에 Claude CLI가 없으면 등록하지 않는다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "claude-argv.log"
            result = run_install_with_fake_tools(
                "--claude",
                fake_tools={
                    "git": "#!/bin/bash\nexit 0\n", "python3": "#!/bin/bash\nexit 0\n",
                    "jq": "#!/bin/bash\nexit 0\n", "curl": "#!/bin/bash\nprintf 'exit 0\\n'\n",
                    "docker": "#!/bin/bash\nexit 0\n",
                },
                fake_home_tools={".opencode/bin/opencode": "#!/bin/bash\nexit 0\n"},
                pseudo_tty=True, stdin="\n\n1 2\n4\n1\nn\n",
                INSTALL_PLAIN_MENU="1", MCP_ARGV_LOG=str(argv_log),
            )
            logged = argv_log.exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claude CLI가 없어 chrome-devtools MCP 등록을 건너뜀", result.stdout)
        self.assertFalse(logged, "claude가 없으므로 argv 로그도 생기면 안 된다.")

    def test_actual_mcp_list_failure_attempts_registration(self):
        """목록 확인 실패는 미등록으로 보고 실제 add를 시도한다."""
        result, argv = self.run_mcp_install(list_mode="failed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<mcp><list>", argv)
        self.assertIn("<mcp><add>", argv)

    def test_actual_mcp_add_records_expected_argv(self):
        """미등록 MCP는 사용자 범위와 CDP 주소를 포함해 등록한다."""
        result, argv = self.run_mcp_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<mcp><add><-s><user><chrome-devtools>", argv)
        self.assertIn("<--browserUrl><http://127.0.0.1:9222>", argv)

    def test_actual_mcp_add_failure_warns_and_continues(self):
        """등록 실패는 경고만 내고 설치 프로세스를 끝까지 진행한다."""
        result, argv = self.run_mcp_install(add_rc=1)
        details = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\nargv:\n{argv}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("<mcp><add>", argv)
        self.assertIn("chrome-devtools MCP 등록 실패", result.stdout, details)
        self.assertIn("설치 완료 (일부 항목 수동 조치 필요).", result.stdout, details)
        retry = next(
            (line for line in result.stdout.splitlines()
             if "chrome-devtools MCP 등록 재시도:" in line),
            None,
        )
        self.assertIsNotNone(retry, details)
        self.assertIn("-s user", retry, details)
        self.assertIn("--browserUrl", retry, details)
        self.assertNotIn("Claude CLI 수동 설치", result.stdout, details)
        manual_steps = result.stdout[result.stdout.index("== 남은 수동 단계") :]
        numbers = [int(value) for value in re.findall(r"(?m)^\s+(\d+)\)", manual_steps)]
        self.assertEqual(numbers, sorted(numbers), details)
        self.assertEqual(len(numbers), len(set(numbers)), details)

    def test_actual_mcp_skips_when_already_registered(self):
        """목록에 서버명이 있으면 add argv가 기록되지 않는다."""
        result, argv = self.run_mcp_install(list_mode="registered")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<mcp><list>", argv)
        self.assertNotIn("<mcp><add>", argv)

    def test_mcp_add_command_single_source(self):
        """MCP 등록 argv와 렌더링은 한 원천을 공유한다."""
        source = INSTALL.read_text()
        self.assertIn("MCP_ADD_ARGV=()", source)
        build_start = source.find("build_mcp_add_argv() {")
        self.assertNotEqual(build_start, -1, "build_mcp_add_argv 함수가 없다.")
        build_end = source.find("\n}", build_start)
        self.assertNotEqual(build_end, -1, "build_mcp_add_argv 함수의 닫는 중괄호를 찾지 못했다.")
        build_body = source[build_start:build_end + 2]

        self.assertIn("mcp_add_command()", source)
        self.assertIn('"${MCP_ADD_ARGV[@]}"', source)
        marker_idx = source.find("MCP_REGISTER_WOULD_RUN=")
        self.assertNotEqual(marker_idx, -1, "실행 예정 마커 출력부가 없다.")
        window = source[max(0, marker_idx - 400):marker_idx + 400]
        self.assertIn(
            "mcp_add_command",
            window,
            "실행 예정 마커는 mcp_add_command 렌더링을 거쳐야 한다.",
        )
        self.assertIn("browserUrl", build_body, "browserUrl 지식은 argv 구성 함수 안에 있어야 한다.")
        self.assertNotIn(
            "browserUrl",
            source[:build_start] + source[build_end + 2:],
            "browserUrl 지식은 argv 구성 함수 밖에 중복되면 안 된다.",
        )

    def test_mcp_registration_does_not_use_eval(self):
        """MCP 등록은 argv 배열을 실행하므로 eval을 사용하지 않는다."""
        self.assertIsNone(re.search(r"\beval\b", INSTALL.read_text()))

    def test_mcp_registration_does_not_use_shell_reinterpretation(self):
        """MCP 등록 명령을 셸 문자열로 재해석하지 않는다."""
        self.assertIsNone(re.search(r"\b(?:bash|sh)\s+-c\b", INSTALL.read_text()))

    def test_mcp_registration_does_not_edit_claude_json(self):
        """Claude 소유 설정 파일인 ~/.claude.json을 직접 편집하지 않는다."""
        # 연속 리터럴만 잡는다 — 변수로 조립해 쪼개면 못 잡는다(정적 검사의 한계, 의도적 수용).
        self.assertNotIn(".claude.json", INSTALL.read_text())

    def test_mcp_args_match_readme(self):
        """렌더링한 등록 명령은 README MCP 예시의 명령·인자와 같다."""
        readme = README.read_text()
        section = readme[readme.index("### Using it over MCP"):readme.index("## Token profiles per Claude plan")]
        config = json.loads(re.search(r"```json\n(.*?)\n```", section, re.DOTALL).group(1))
        server_name, server = next(iter(config["mcpServers"].items()))
        command = server["command"]
        package_args = server["args"][:2]
        browser_url = server["args"][server["args"].index("--browserUrl") + 1]

        with tempfile.TemporaryDirectory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_MCP": "1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        marker = re.search(r"(?m)^MCP_REGISTER_WOULD_RUN=([^ ]+) (.+)$", result.stdout)
        self.assertIsNotNone(marker, details)
        self.assertEqual(marker.group(1), server_name, details)
        self.assertIn(command, marker.group(2), details)
        for argument in package_args:
            self.assertIn(argument, marker.group(2), details)
        self.assertIn("--browserUrl", marker.group(2), details)
        self.assertIn(browser_url, marker.group(2), details)


if __name__ == "__main__":
    unittest.main()
