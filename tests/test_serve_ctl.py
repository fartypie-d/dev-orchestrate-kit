"""opencode serve 제어 스크립트의 격리 실행 테스트."""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / "core/scripts/opencode-serve-ctl.sh"


class ServeCtlTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.env_file = self.root / "serve.env"
        self.state_dir = self.root / "state"
        self.health_file = self.root / "healthy"
        self.write_stub("curl", """#!/usr/bin/env bash
cat >/dev/null
if [ -f \"$FAKE_HEALTH_FILE\" ]; then
  printf '200'
else
  printf '000'
  exit 7
fi
""")
        self.write_stub("opencode", """#!/usr/bin/env bash
printf '%s\\n' \"$*\" >> \"$FAKE_OPENCODE_LOG\"
touch \"$FAKE_HEALTH_FILE\"
""")
        self.env_file.write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD=test-secret\n"
        )
        self.env_file.chmod(0o600)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_stub(self, name, content):
        path = self.bin_dir / name
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_ctl(self, action, extra_env=None):
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{self.bin_dir}:{env['PATH']}",
                "OPENCODE_SERVE_ENV_FILE": str(self.env_file),
                "OPENCODE_SERVE_STATE_DIR": str(self.state_dir),
                "OPENCODE_SERVE_START_TIMEOUT": "2",
                "OPENCODE_SERVE_POLL_INTERVAL": "0",
                "FAKE_HEALTH_FILE": str(self.health_file),
                "FAKE_OPENCODE_LOG": str(self.root / "opencode.log"),
            }
        )
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPT), action], capture_output=True, text=True, env=env, timeout=10
        )

    def test_ensure_starts_server_when_down(self):
        result = self.run_ctl("ensure")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.health_file.exists())
        self.assertIn("serve --port 4096", (self.root / "opencode.log").read_text())

    def test_ensure_noop_when_healthy(self):
        self.health_file.touch()
        result = self.run_ctl("ensure")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "opencode.log").exists())

    def test_status_reports_down_without_password_leak(self):
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 1)
        self.assertIn("down", result.stdout)
        self.assertNotIn("test-secret", result.stdout + result.stderr)

    def test_start_fails_without_password(self):
        self.env_file.write_text("OPENCODE_SERVE_PORT=4096\n")
        result = self.run_ctl("start")
        self.assertEqual(result.returncode, 64)
        self.assertIn("OPENCODE_SERVER_PASSWORD", result.stderr)

    def test_password_with_quote_rejected(self):
        curl_calls = self.root / "curl.calls"
        self.write_stub("curl", """#!/usr/bin/env bash
printf 'called\\n' >> "$FAKE_CURL_CALLS"
cat >/dev/null
printf '200'
""")
        self.env_file.write_text(
            'OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD=bad\\"password\n'
        )
        self.env_file.chmod(0o600)
        result = self.run_ctl("status", {"FAKE_CURL_CALLS": str(curl_calls)})
        self.assertEqual(result.returncode, 64)
        self.assertIn("OPENCODE_SERVER_PASSWORD", result.stderr)
        self.assertFalse(curl_calls.exists())

    def test_password_with_backslash_rejected(self):
        curl_calls = self.root / "curl.calls"
        self.write_stub("curl", """#!/usr/bin/env bash
printf 'called\\n' >> "$FAKE_CURL_CALLS"
cat >/dev/null
printf '200'
""")
        self.env_file.write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD='trail\\'\n"
        )
        self.env_file.chmod(0o600)
        result = self.run_ctl("status", {"FAKE_CURL_CALLS": str(curl_calls)})
        self.assertEqual(result.returncode, 64)
        self.assertIn("OPENCODE_SERVER_PASSWORD", result.stderr)
        self.assertFalse(curl_calls.exists())

    def test_session_actions_happy_path(self):
        # 스텁은 curl 의 출력 모드(code / bodycode / body)를 구분해야 한다.
        # 모드를 뭉뚱그리면 abort 응답 코드가 무시되어(뒤에 붙는 조각만 살아남아)
        # 엔드포인트가 500을 줘도 통과하는 공허한 happy-path 가 된다.
        self.write_stub("curl", """#!/usr/bin/env bash
CONFIG=$(cat)
case "$CONFIG" in
  *'/session/ses_test/abort"'*) BODY=''; CODE=204 ;;
  *'/session/ses_test"'*) BODY='{"id":"ses_test"}'; CODE=200 ;;
  *'/session"'*) BODY='[{"id":"ses_test"}]'; CODE=200 ;;
  *) BODY=''; CODE=200 ;;
esac
case " $* " in
  *' --output /dev/null '*) printf '%s' "$CODE" ;;
  *' --write-out '*) printf '%s' "$BODY"; printf '\\n%s' "$CODE" ;;
  *) printf '%s' "$BODY" ;;
esac
""")
        listed = self.run_ctl("sessions")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(listed.stdout, '[{"id":"ses_test"}]')
        detail = self.run_ctl("session", {"OPENCODE_SERVE_ACTION_ID": "ses_test"})
        self.assertEqual(detail.returncode, 0, detail.stderr)
        self.assertEqual(detail.stdout, '{"id":"ses_test"}')
        aborted = self.run_ctl("abort", {"OPENCODE_SERVE_ACTION_ID": "ses_test"})
        self.assertEqual(aborted.returncode, 0, aborted.stderr)
        self.assertEqual(aborted.stdout, "aborted\n")

    def test_session_actions_reject_invalid_credentials(self):
        curl_calls = self.root / "curl.calls"
        self.write_stub("curl", """#!/usr/bin/env bash
printf 'called\\n' >> "$FAKE_CURL_CALLS"
cat >/dev/null
printf '200'
""")
        for password in ("'bad\\\"password'", "'bad\\\\password'", "'bad\npassword'"):
            self.env_file.write_text(
                "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD=%s\n" % password
            )
            self.env_file.chmod(0o600)
            for action in ("sessions", "session", "abort"):
                result = self.run_ctl(action, {"FAKE_CURL_CALLS": str(curl_calls), "OPENCODE_SERVE_ACTION_ID": "ses_test"})
                self.assertEqual(result.returncode, 64, result.stderr)
                self.assertIn("OPENCODE_SERVER_PASSWORD", result.stderr)
        self.assertFalse(curl_calls.exists())

    def test_sessions_action_fails_on_error_http_code(self):
        """`sessions` 도 HTTP 코드를 봐야 한다 — 401 본문이 세션 목록으로 흐르면 안 된다.

        health_check(code)·session(bodycode)·abort(code)는 코드를 검사하는데 sessions 만
        본문을 그대로 stdout 으로 흘리고 exit 0 이었다. 하류 `snapshot_server_sessions()` 가
        jq 파싱 실패로 걸러지는 것은 설계된 방어가 아니라 우연이다.
        """
        self.write_stub("curl", """#!/usr/bin/env bash
cat >/dev/null
printf '{"error":"unauthorized"}'
case " $* " in *' --write-out '*) printf '\\n401' ;; esac
""")
        result = self.run_ctl("sessions")
        self.assertNotEqual(result.returncode, 0, "401 응답이 성공으로 처리됐다: %r" % result.stdout)
        self.assertNotIn("unauthorized", result.stdout)

    def test_abort_action_fails_when_http_code_missing(self):
        """빈 HTTP 코드는 실패로 처리돼야 한다.

        `[ "" -lt 200 ]` 는 exit 2(정수 아님)라 `||` 체인 전체가 거짓이 되어
        `aborted` 를 출력하고 exit 0 으로 빠진다. session 액션은 `case ... 2??` 라 안전하다.
        """
        self.write_stub("curl", """#!/usr/bin/env bash
cat >/dev/null
""")
        result = self.run_ctl("abort", {"OPENCODE_SERVE_ACTION_ID": "ses_test"})
        self.assertNotEqual(result.returncode, 0, "빈 HTTP 코드가 성공으로 처리됐다")
        self.assertNotIn("aborted", result.stdout)

    def test_world_readable_env_rejected(self):
        self.env_file.chmod(0o644)
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 64)
        self.assertIn("권한", result.stderr)
        self.env_file.chmod(0o600)
        self.health_file.touch()
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_group_writable_env_rejected(self):
        self.health_file.touch()
        self.env_file.chmod(0o622)
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 64)
        self.assertIn("권한", result.stderr)
        self.env_file.chmod(0o600)
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unrecognized_ls_format_fails_closed(self):
        self.health_file.touch()
        self.write_stub("ls", """#!/usr/bin/env bash
printf '%s\\n' '인식할 수 없는 권한 형식'
""")
        result = self.run_ctl("status")
        self.assertEqual(result.returncode, 64)
        self.assertIn("권한 형식 인식 실패", result.stderr)

    def test_env_permission_suffix_rejected(self):
        curl_calls = self.root / "curl.calls"
        self.write_stub("curl", """#!/usr/bin/env bash
printf 'called\\n' >> "$FAKE_CURL_CALLS"
cat >/dev/null
printf '200'
""")
        self.write_stub("ls", """#!/usr/bin/env bash
printf '%s\\n' '-rw-r--r--@ 1 test test 0 Jan 1 00:00 serve.env'
""")
        result = self.run_ctl("status", {"FAKE_CURL_CALLS": str(curl_calls)})
        self.assertEqual(result.returncode, 64)
        self.assertIn("권한", result.stderr)
        self.assertFalse(curl_calls.exists())

    def test_start_fails_when_server_dies(self):
        self.write_stub("opencode", """#!/usr/bin/env bash
printf '즉사 로그\\n' >&2
exit 1
""")
        result = self.run_ctl("start")
        self.assertEqual(result.returncode, 1)
        self.assertIn("즉사 로그", result.stderr)

    def test_stop_verifies_termination(self):
        self.write_stub("opencode", """#!/usr/bin/env bash
touch "$FAKE_HEALTH_FILE"
trap '' TERM
while :; do sleep 1; done
""")
        started = self.run_ctl("start")
        self.assertEqual(started.returncode, 0, started.stderr)
        result = self.run_ctl("stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stopped", result.stdout)
        self.assertFalse((self.state_dir / "serve.pid").exists())


if __name__ == "__main__":
    unittest.main()
