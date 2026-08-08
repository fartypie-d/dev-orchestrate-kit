"""model-doctor.sh 테스트 — 임시 가짜 opencode 바이너리로 외부 호출을 격리한다."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
DOCTOR = KIT / "core/opencode/model-doctor.sh"

REGISTERED = "qwencloud/qwen3.7-plus\nqwencloud/qwen3.7-max\nopenai/gpt-5.6-luna\n"


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.policy = self.work / "policy.json"
        self.secrets = self.work / "secrets.env"
        self.opencode = self.work / "opencode"
        self.opencode.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            "  models) printf '%s' \"${FAKE_MODELS_OUT-}\"; exit \"${FAKE_MODELS_EXIT-0}\" ;;\n"
            "  auth) printf '%s' \"${FAKE_AUTH_OUT-}\"; exit \"${FAKE_AUTH_EXIT-0}\" ;;\n"
            "  run) printf '%s' \"${FAKE_RUN_OUT-}\"; exit \"${FAKE_RUN_EXIT-0}\" ;;\n"
            "  *) exit 64 ;;\n"
            "esac\n"
        )
        self.opencode.chmod(0o755)

    def write_policy(self, default, heavy):
        self.policy.write_text(json.dumps({"tiers": {"default": default, "heavy": heavy}}))

    def run_doctor(self, *args, env=None):
        command = [
            "bash", str(DOCTOR), "--policy", str(self.policy),
            "--opencode-bin", str(self.opencode), "--secrets", str(self.secrets),
            *args,
        ]
        run_env = os.environ.copy()
        run_env.update({"FAKE_MODELS_OUT": REGISTERED, "FAKE_AUTH_OUT": "OpenAI oauth\n"})
        if env:
            run_env.update(env)
        return subprocess.run(command, capture_output=True, text=True, env=run_env)

    def test_all_entries_registered_passes(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_unregistered_entry_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus", "qwencloud/typo-model"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("qwencloud/typo-model", result.stdout)
        self.assertIn("MISSING", result.stdout)

    def test_tier_with_no_valid_entry_fails(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["xai/not-registered"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("heavy", result.stdout)

    def test_missing_policy_file_exits_66(self):
        result = subprocess.run(
            ["bash", str(DOCTOR), "--policy", str(self.policy) + ".nope",
             "--opencode-bin", str(self.opencode), "--skip-smoke"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 66)

    def test_empty_tiers_object_fails(self):
        self.policy.write_text('{"tiers": {}}')
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("정책에 tier 가 하나도 없다", result.stderr)

    def test_missing_tiers_fails(self):
        self.policy.write_text("{}")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("정책에 tier 가 하나도 없다", result.stderr)

    def test_scalar_tiers_exits_66(self):
        for tiers in ("oops", 5):
            with self.subTest(tiers=tiers):
                self.policy.write_text(json.dumps({"tiers": tiers}))
                result = self.run_doctor("--skip-smoke")
                self.assertEqual(result.returncode, 66, result.stdout + result.stderr)
                self.assertIn("객체가 아니다", result.stderr)

    def test_invalid_policy_json_exits_66(self):
        self.policy.write_text("{")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 66)
        self.assertIn("정책 JSON 손상", result.stderr)

    def test_models_command_failure_rejects_partial_output(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke", env={"FAKE_MODELS_EXIT": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("opencode models 실패 (exit 1)", result.stderr)

    def test_auth_command_failure_is_reported_separately(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke", env={"FAKE_AUTH_EXIT": "7"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("auth list 실행 실패 (exit 7)", result.stderr)

    def test_missing_key_credential_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertIn("인증 누락: qwen (QWEN_API_KEY 미설정)", result.stdout)

    def test_skip_smoke_reports_that_real_calls_were_not_verified(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 생략됨 (--skip-smoke)", result.stdout)
        self.assertIn("스모크 생략", result.stdout)

    def test_secret_values_are_never_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.secrets.write_text("QWEN_API_KEY=sk-FAKE123\nEMPTY_KEY=\n")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("인증 OK: qwen (key)", result.stdout)
        self.assertNotIn("sk-FAKE123", result.stdout + result.stderr)

    def test_smoke_success_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 통과", result.stdout)

    def test_smoke_failure_includes_exit_code(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor(env={"FAKE_RUN_EXIT": "9"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 실패 (exit 9)", result.stdout)


if __name__ == "__main__":
    unittest.main()
