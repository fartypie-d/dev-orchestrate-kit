"""install.sh 번호 선택 메뉴의 비대화형 안전성과 입력 정규화 테스트."""
import unittest

from _install_helpers import KIT, parse_only, run_install, selftest_menu

INSTALL = KIT / "install.sh"


class InstallMenuTest(unittest.TestCase):
    def test_parse_only_exits_after_argument_parsing_before_menu_definition(self):
        """INSTALL_PARSE_ONLY는 메뉴 실행 전 인자 파싱 결과만 출력하고 종료한다."""
        result = parse_only("--claude", "--providers=qwen", "--plan=pro", "typescript")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "HARNESSES=claude\nPROVIDERS=qwen\nCONTAINERS=\nPLAN=pro\n"
            "ECC_LANGS=typescript\n",
        )
        self.assertNotIn("선택", result.stderr)

    def test_parse_only_rejects_invalid_cli_ecc_languages(self):
        """명시한 CLI ECC 언어는 메뉴 입력과 같은 문자 정책을 따른다."""
        for language in ("foo;id", "../../etc/passwd"):
            with self.subTest(language=language):
                result = parse_only("--claude", language)
                self.assertEqual(result.returncode, 64)
                self.assertIn("유효하지 않은 ECC 언어", result.stderr)

        result = parse_only("--claude", "typescript", "react-native")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ECC_LANGS=typescript react-native", result.stdout)

    def test_parse_only_rejects_empty_cli_ecc_language(self):
        """빈 CLI 언어는 유효한 ECC 언어 배열 원소가 될 수 없다."""
        result = parse_only("--claude", "", "typescript")
        self.assertEqual(result.returncode, 64)
        self.assertIn("유효하지 않은 ECC 언어", result.stderr)
        self.assertIn("(빈 값)", result.stderr)

    def test_parse_only_keeps_multiple_valid_cli_ecc_languages(self):
        """여러 CLI 언어를 처리해도 호출부 루프 값이 손상되지 않는다."""
        result = parse_only("--claude", "typescript", "react-native", "golang")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ECC_LANGS=typescript react-native golang", result.stdout)

    def test_add_ecc_lang_uses_prefixed_temporary_argument(self):
        """함수 임시 인자는 바깥 CLI 루프 변수와 이름을 공유하지 않는다."""
        source = INSTALL.read_text()
        self.assertIn("  _ecc_lang_arg=$1", source)
        self.assertIn('ECC_LANGS[${#ECC_LANGS[@]}]="$_ecc_lang_arg"', source)
        self.assertNotIn("  arg=$1", source)

    def test_selftest_reports_each_noninteractive_skip_once(self):
        """요금제·ECC 언어 미지정 상황은 각각 한 번만 안내한다."""
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertEqual(output.count("요금제 미선택 — 모델·토큰 설정을 건드리지 않는다"), 1)
        self.assertEqual(output.count("언어 인자 없음 — ECC 설치 스킵"), 1)

    def test_piped_stdin_is_not_treated_as_interactive_menu_input(self):
        result = run_install(
            stdin="1\n", env={"INSTALL_SELFTEST_MENU": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SELFTEST INTERACTIVE=0", result.stdout)

    def test_choice_input_normalization(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        choices = result.stdout.splitlines()
        self.assertEqual(choices[1:5], ["SELFTEST CHOICE=qwen,xai"] * 4)
        self.assertEqual(choices[5], "SELFTEST CHOICE=qwen")
        self.assertEqual(choices[8], "SELFTEST PLAN=max5")
        self.assertEqual(choices[9], "SELFTEST PLAN=skip")

    def test_three_invalid_attempts_falls_back_with_notice(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('입력 3회 실패 — 기본값("qwen")으로 진행한다.', result.stderr)
        self.assertIn('입력 3회 실패 — 기본값("skip")으로 진행한다.', result.stderr)
        choices = result.stdout.splitlines()
        self.assertEqual(choices[6:8], ["SELFTEST CHOICE=qwen"] * 2)
        self.assertEqual(choices[10:12], ["SELFTEST PLAN=skip"] * 2)

    def test_read_failure_falls_back_with_notice(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('입력을 읽지 못해 기본값("qwen")으로 진행한다.', result.stderr)
        self.assertIn('입력을 읽지 못해 기본값("skip")으로 진행한다.', result.stderr)
        choices = result.stdout.splitlines()
        self.assertEqual(choices[12], "SELFTEST CHOICE=qwen")
        self.assertEqual(choices[13], "SELFTEST PLAN=skip")

    def test_ecc_lang_rejects_flag_and_path_injection(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("⚠️ 무시: 유효하지 않은 언어 값 '--config'", result.stderr)
        self.assertIn("⚠️ 무시: 유효하지 않은 언어 값 '/tmp/evil.json'", result.stderr)
        self.assertIn("SELFTEST ECC=typescript", result.stdout)
        self.assertIn(
            "입력한 언어가 모두 무효하여 ECC 설치를 건너뛴다 "
            "(허용: 영문자·숫자·_·-)",
            result.stderr,
        )

    def test_noninteractive_harness_notice_is_emitted(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("비대화형 실행 — 하네스 자동 감지값(", result.stderr)
        self.assertIn("명시하려면 --claude 또는 --codex.", result.stderr)

    def test_noninteractive_plan_notice_is_emitted(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("요금제 미선택 — 모델·토큰 설정을 건드리지 않는다.", result.stderr)
        self.assertIn("지정하려면 --plan=pro|max5|max20.", result.stderr)
        self.assertNotIn("요금제 미선택 — 모델·토큰 설정을 건드리지 않는다.", result.stdout)

    def test_ecc_lang_no_input_notice_is_emitted_to_stderr(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "언어 인자 없음 — ECC 설치 스킵 (예: ./install.sh --claude typescript python)",
            result.stderr,
        )
        self.assertNotIn("언어 인자 없음 — ECC 설치 스킵", result.stdout)

    def test_notification_calls_are_wired_to_install_flow_blocks(self):
        source = INSTALL.read_text()

        harness_block = source[source.index('elif [ "$HARNESS_FROM_FLAG" = "0"'):source.index('\nsay "1/7')]
        ecc_block = source[source.index('say "3/7 ECC'):source.index('\nsay "4/7')]
        plan_end = source.index('\nsay "7/7')
        plan_start = source.rindex('case " $HARNESSES " in', 0, plan_end)
        plan_block = source[plan_start:plan_end]

        # 호출과 조건을 함께 고정해 DRY_RUN 비교 연산자 반전을 잡는다.
        # 공백·들여쓰기만 바꾼 동등한 구현은 잡지 못하는 소스 구조 검사다.
        self.assertIn(
            'elif [ "$HARNESS_FROM_FLAG" = "0" ] && [ "${INSTALL_DRY_RUN:-0}" != "1" ]; then\n'
            "  notify_noninteractive_harness",
            harness_block,
        )
        self.assertIn(
            'if [ "${#ECC_LANGS[@]}" -eq 0 ]; then\n'
            "    report_ecc_lang_skip",
            ecc_block,
        )
        self.assertRegex(
            plan_block,
            r'(?s)if \[ -n "\$PLAN" \]; then.*?\n    else\n      report_plan_skip',
        )

    def test_menu_selftest_does_not_enter_dry_run(self):
        result = selftest_menu()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DRY_RUN", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
