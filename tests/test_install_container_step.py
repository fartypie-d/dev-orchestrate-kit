"""설치 마법사의 컨테이너 선택·기동 계약을 검증한다."""
import re
import socket
import unittest
from pathlib import Path

from _install_helpers import (
    KIT, RUN_TIMEOUT, run_install, run_install_with_fake_tools, temporary_directory,
)


INSTALL = KIT / "install.sh"


class InstallContainerStepTest(unittest.TestCase):
    @staticmethod
    def available_cdp_port():
        """잠시 바인드·재바인드해 현재 비어 있는 CDP 포트를 고른다."""
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
        raise RuntimeError("비어 있는 CDP 포트를 고르지 못했다.")

    def test_container_step_marker_and_steps(self):
        """browser 선택은 컨테이너 마커와 단계 토큰에 남는다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|1|4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=browser\n", result.stdout, details)
        self.assertIn("STEPS=harness ecc providers containers plan summary\n", result.stdout, details)

    def test_container_step_skipped_with_flag(self):
        """컨테이너 CLI 플래그는 선택 단계를 건너뛰되 값을 보존한다."""
        with temporary_directory() as home:
            result = run_install(("--containers=browser",), env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1|||4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=browser\n", result.stdout, details)
        steps_line = next(line for line in result.stdout.splitlines() if line.startswith("SELFTEST WIZARD STEPS="))
        self.assertNotIn("containers", steps_line.split("=", 1)[1].split(), details)

    def test_container_step_back_navigation(self):
        """컨테이너 단계의 뒤로가기는 이전 단계 뒤 정방향 진행을 허용한다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3|b|3|1|4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=browser\n", result.stdout, details)
        self.assertIn(
            "STEPS=harness ecc providers containers providers containers plan summary\n",
            result.stdout,
            details,
        )

    def test_container_step_empty_selection(self):
        """빈 선택은 컨테이너 값을 비우고 기동 예정 마커를 만들지 않는다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_WIZARD": "1", "INSTALL_SELFTEST_INPUTS": "1||3||4|1"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("SELFTEST WIZARD CONTAINERS=\n", result.stdout, details)
        self.assertNotIn("CONTAINER_INSTALL_WOULD_RUN=", result.stdout, details)

    def test_container_install_empty_selection_runs_nothing(self):
        """빈 컨테이너 선택은 실행 단계에서도 아무 마커를 남기지 않는다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": ""})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(result.stdout, "", details)

    def test_container_install_would_run(self):
        """컨테이너 셀프테스트는 실제 기동 대신 browser 실행 예정만 출력한다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_SUBMODULE_WOULD_INIT=browser\n", result.stdout, details)
        self.assertRegex(result.stdout, r"(?m)^CONTAINER_INSTALL_WOULD_RUN=browser .+", details)
        init_idx = result.stdout.index("CONTAINER_SUBMODULE_WOULD_INIT=browser")
        run_idx = result.stdout.index("CONTAINER_INSTALL_WOULD_RUN=browser")
        self.assertLess(init_idx, run_idx, f"INIT 마커가 RUN 마커보다 뒤에 오면 안 된다.\n{details}")

    def test_container_install_submodule_missing_is_nonfatal(self):
        """서브모듈 초기화 실패는 실행하지 않고 허용된 비치명 사유로 남긴다."""
        with temporary_directory() as home:
            result = run_install(
                env={
                    "HOME": home,
                    "INSTALL_DRY_RUN": "1",
                    "INSTALL_SELFTEST_CONTAINERS": "1",
                    "INSTALL_CONTAINERS": "browser",
                    "INSTALL_CONTAINER_FAKE": "submodule_missing",
                },
            )
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_SUBMODULE_WOULD_INIT=browser\n", result.stdout, details)
        self.assertNotIn("CONTAINER_INSTALL_WOULD_RUN=", result.stdout, details)
        self.assertIn("CONTAINER_INSTALL_SKIPPED=browser reason=unknown\n", result.stdout, details)
        init_idx = result.stdout.index("CONTAINER_SUBMODULE_WOULD_INIT=browser")
        skip_idx = result.stdout.index("CONTAINER_INSTALL_SKIPPED=browser reason=unknown")
        self.assertLess(init_idx, skip_idx, details)

    def test_container_install_skipped_when_docker_missing(self):
        """docker 부재는 설치를 중단하지 않고 건너뜀 이유로 보고한다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser", "INSTALL_CONTAINER_FAKE": "docker_missing"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_INSTALL_SKIPPED=browser reason=docker_missing\n", result.stdout, details)

    def test_container_install_skipped_when_port_busy(self):
        """9222 포트 충돌은 기동 전에 건너뜀 이유로 보고한다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser", "INSTALL_CONTAINER_FAKE": "port_busy"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_INSTALL_SKIPPED=browser reason=port_busy\n", result.stdout, details)

    def test_container_install_declined(self):
        """동의를 거절하면 기동하지 않고 거절 이유만 출력한다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser", "INSTALL_CONTAINER_CONSENT": "n"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertIn("CONTAINER_INSTALL_SKIPPED=browser reason=declined\n", result.stdout, details)
        self.assertNotIn("CONTAINER_INSTALL_WOULD_RUN=", result.stdout, details)

    def test_unknown_container_rejected(self):
        """화이트리스트 밖 컨테이너는 stderr 경고만 남기고 실행하지 않는다."""
        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "foo"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        self.assertEqual(result.stdout, "", details)
        self.assertRegex(result.stderr, r"\bfoo\b", details)

    def test_container_up_command_single_source(self):
        """기동 argv와 렌더링은 한 원천을 공유하며 compose 서비스명을 알지 않는다."""
        source = INSTALL.read_text()
        self.assertIn("CONTAINER_UP_ARGV=()", source)
        build_start = source.find("build_container_up_argv() {")
        self.assertNotEqual(build_start, -1, "build_container_up_argv 함수가 없다.")
        build_end = source.find("\n}", build_start)
        self.assertNotEqual(build_end, -1, "build_container_up_argv 함수의 닫는 중괄호를 찾지 못했다.")
        build_body = source[build_start:build_end + 2]

        self.assertIn("container_up_command()", source)
        self.assertIn('"${CONTAINER_UP_ARGV[@]}"', source)
        self.assertIn("up -d", build_body, "up -d 지식은 argv 구성 함수 안에 있어야 한다.")
        self.assertNotIn(
            "up -d",
            source[:build_start] + source[build_end + 2:],
            "up -d 지식은 argv 구성 함수 밖에 중복되면 안 된다.",
        )
        marker_idx = source.find("CONTAINER_INSTALL_WOULD_RUN=")
        self.assertNotEqual(marker_idx, -1, "실행 예정 마커 출력부가 없다.")
        window = source[max(0, marker_idx - 400):marker_idx + 400]
        self.assertIn(
            "container_up_command",
            window,
            "실행 예정 마커는 container_up_command 렌더링을 거쳐야 한다.",
        )
        self.assertNotIn("chrome-cdp", source, "compose 서비스명은 compose 파일만 소유해야 한다.")

        with temporary_directory() as home:
            result = run_install(env={"HOME": home, "INSTALL_DRY_RUN": "1", "INSTALL_SELFTEST_CONTAINERS": "1", "INSTALL_CONTAINERS": "browser"})
        details = f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(result.returncode, 0, details)
        marker = next(
            (line for line in result.stdout.splitlines() if line.startswith("CONTAINER_INSTALL_WOULD_RUN=browser ")),
            None,
        )
        self.assertIsNotNone(marker, details)
        self.assertIn("up -d", marker, details)

    def test_actual_container_up_failure_marks_manual_step(self):
        """실제 compose 기동 실패는 컨테이너 재시도만 수동 단계로 남긴다."""
        with temporary_directory() as scratch:
            argv_log = Path(scratch) / "docker-argv.log"
            port = self.available_cdp_port()
            result = run_install_with_fake_tools(
                "--claude", "--containers=browser",
                fake_tools={
                    "git": "#!/bin/bash\nexit 0\n",
                    "python3": "#!/bin/bash\nexit 0\n",
                    "jq": "#!/bin/bash\nexit 0\n",
                    "claude": "#!/bin/bash\nexit 0\n",
                    "docker": (
                        "#!/bin/bash\nprintf '<%s>' \"$@\" >> \"$DOCKER_ARGV_LOG\"\n"
                        "printf '\\n' >> \"$DOCKER_ARGV_LOG\"\n"
                        "if [ \"$1 $2\" = 'compose version' ]; then exit 0; fi\n"
                        "exit 1\n"
                    ),
                },
                fake_home_tools={
                    ".opencode/bin/opencode": "#!/bin/bash\n[ \"$1\" = --version ] && exit 0\nexit 0\n",
                },
                pseudo_tty=True,
                stdin="\n\n\n1\ny\n",
                INSTALL_PLAIN_MENU="1",
                INSTALL_CDP_PORT=str(port),
                DOCKER_ARGV_LOG=str(argv_log),
            )
            argv = argv_log.read_text() if argv_log.exists() else ""

        details = (
            f"제한 시간: {RUN_TIMEOUT}초\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\ndocker argv:\n{argv}"
        )
        self.assertEqual(result.returncode, 0, details)
        self.assertRegex(argv, r"(?m)^<compose><-f><.+><up><-d>$", details)
        self.assertIn("설치 완료 (일부 항목 수동 조치 필요).", result.stdout, details)
        self.assertNotIn("Claude CLI 수동 설치", result.stdout, details)
        manual_steps = result.stdout[result.stdout.index("== 남은 수동 단계"):]
        retry = next(
            (line for line in manual_steps.splitlines() if "컨테이너 기동 재시도:" in line),
            None,
        )
        self.assertIsNotNone(retry, details)
        self.assertIn("compose", retry, details)
        self.assertIn("up -d", retry, details)
        numbers = [int(value) for value in re.findall(r"(?m)^\s+(\d+)\)", manual_steps)]
        self.assertEqual(numbers, sorted(numbers), details)
        self.assertEqual(len(numbers), len(set(numbers)), details)


if __name__ == "__main__":
    unittest.main()
