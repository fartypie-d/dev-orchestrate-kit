"""install.sh 인자 파싱 테스트 — INSTALL_PARSE_ONLY=1 로 부작용 없이 파싱 결과만 확인."""
import os
import subprocess
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def parse(*args):
    env = {**os.environ, "INSTALL_PARSE_ONLY": "1"}
    return subprocess.run(
        ["bash", str(KIT / "install.sh"), *args],
        capture_output=True, text=True, env=env,
    )


class InstallArgsTest(unittest.TestCase):
    def test_explicit_harness_flags(self):
        r = parse("--claude", "--codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("HARNESSES=claude codex", r.stdout)

    def test_providers_csv_parsed(self):
        r = parse("--claude", "--providers=qwen,openai")
        self.assertIn("PROVIDERS=qwen,openai", r.stdout)

    def test_containers_csv_parsed(self):
        r = parse("--claude", "--containers=browser,antigravity")
        self.assertIn("CONTAINERS=browser,antigravity", r.stdout)

    def test_ecc_languages_collected(self):
        r = parse("--claude", "typescript", "python")
        self.assertIn("ECC_LANGS=typescript python", r.stdout)

    def test_ecc_language_arguments_are_preserved_as_array(self):
        source = (KIT / "install.sh").read_text()
        self.assertIn('ECC_LANGS[${#ECC_LANGS[@]}]="$arg"', source)
        self.assertIn('./install.sh "${ECC_LANGS[@]}"', source)

    def test_noninteractive_provider_prompt_is_skipped(self):
        source = (KIT / "install.sh").read_text()
        self.assertIn('if [ -t 0 ]; then', source)
        self.assertIn('비대화형 실행 — --providers= 로 명시하거나 나중에 gen-policy.sh 를 직접 실행할 것', source)

    def test_plan_option_is_accepted(self):
        r = parse("--claude", "--plan=max20", "typescript")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PLAN=max20", r.stdout)

    def test_unknown_flag_exits_64(self):
        r = parse("--nosuchflag")
        self.assertEqual(r.returncode, 64)


if __name__ == "__main__":
    unittest.main()
