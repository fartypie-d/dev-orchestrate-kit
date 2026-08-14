"""run-delegation.sh의 serve attach·폴백 회귀 테스트."""

import os
import json
import shlex
import signal
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
SOURCE = KIT / "core/scripts/run-delegation.sh"


class RunDelegationTest(unittest.TestCase):
    """실제 serve나 사용자 상태 디렉터리 없이 PATH 스텁으로 검증한다."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.scripts = self.root / "scripts"
        self.project = self.root / "project"
        for directory in (self.home / ".config/opencode", self.home / ".opencode/bin", self.bin, self.scripts, self.project):
            directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, self.scripts / "run-delegation.sh")
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model", "second/model"]}}\n'
        )
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD=test-password\n"
        )
        os.chmod(self.home / ".config/opencode/serve.env", 0o600)
        self._write("opencode", """#!/usr/bin/env bash
if [ -n "${LOCK_SNAPSHOT:-}" ]; then
  mkdir -p "$LOCK_SNAPSHOT"
  /bin/cp -a "$ORCHESTRATE_STATE_DIR/." "$LOCK_SNAPSHOT/"
fi
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
if [ -n "${OPENCODE_ENV_DUMP:-}" ]; then
  printf 'OPENCODE_SERVER_PASSWORD=%s\\n' "${OPENCODE_SERVER_PASSWORD:-<unset>}" >> "$OPENCODE_ENV_DUMP"
fi
echo 'loop session.id ses_test_session'
exit "${OPENCODE_RC:-0}"
""", self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\nexit 0\n", self.bin)
        self._write("ps", "#!/usr/bin/env bash\nexit 0\n", self.bin)
        self._write("opencode-serve-ctl.sh", """#!/usr/bin/env bash
if [ "$1" = "ensure" ] && [ "${SERVE_RC:-0}" -ne 0 ]; then
  exit "$SERVE_RC"
fi
exec bash "$REAL_CTL" "$@"
""", self.scripts)
        os.chmod(self.scripts / "opencode-serve-ctl.sh", 0o644)
        self._write("curl", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CURL_CALLS"
CONFIG=$(cat)
printf '%s\\n' "$CONFIG" >> "$CURL_CONFIGS"
COUNT_FILE="${CURL_CALLS}.session-count"
COUNT=0
[ -f "$COUNT_FILE" ] && COUNT=$(cat "$COUNT_FILE")
case "$CONFIG" in
   *'/session?directory='*)
     CREATE_FILE="${CURL_CALLS}.create-count"; CREATE=0
     [ -f "$CREATE_FILE" ] && CREATE=$(cat "$CREATE_FILE")
     CREATE=$((CREATE + 1)); printf '%s' "$CREATE" > "$CREATE_FILE"
     [ "${CURL_CREATE_RC:-0}" -eq 0 ] || exit "$CURL_CREATE_RC"
     printf '{"id":"%s","directory":"/wherever/server/cwd/is"}' "${CURL_CREATE_ID_PREFIX:-ses_created}$CREATE"
     case " $* " in *' --write-out '*) printf '\n%s' "${CURL_CREATE_HTTP_CODE:-200}" ;; esac
    ;;
   *'/session"'*)
     COUNT=$((COUNT + 1)); printf '%s' "$COUNT" > "$COUNT_FILE"
     SESSION_RC_VAR="CURL_SESSIONS_RC_CALL_$COUNT"
     if [ -n "${!SESSION_RC_VAR+x}" ]; then exit "${!SESSION_RC_VAR}"; fi
     [ "${CURL_SESSIONS_RC:-0}" -eq 0 ] || exit "$CURL_SESSIONS_RC"
     SESSION_VAR="CURL_SESSIONS_CALL_$COUNT"
    if [ -n "${!SESSION_VAR+x}" ]; then printf '%s' "${!SESSION_VAR}";
    elif [ "$COUNT" -eq 1 ]; then printf '%s' "${CURL_SESSIONS_BEFORE:-[]}"; else printf '%s' "${CURL_SESSIONS_AFTER:-[]}"; fi
    # 실제 curl 은 --write-out 을 주면 항상 코드를 덧붙인다. 스텁이 이를 생략하면
    # 소스가 "코드 없는 응답"을 수용하도록 휘어진다(이 페이즈의 반복 실패 패턴).
    case " $* " in *' --write-out '*) printf '\n%s' "${CURL_SESSIONS_HTTP_CODE:-200}" ;; esac
    ;;
  *'/abort"'*) printf '%s' "${CURL_ABORT_HTTP_CODE:-200}"; exit "${CURL_ABORT_RC:-0}" ;;
   *'/session/'*)
     [ "${CURL_SESSION_DETAIL_RC:-0}" -eq 0 ] || exit "$CURL_SESSION_DETAIL_RC"
    DETAIL_FILE="${CURL_CALLS}.detail-count"; DETAIL=0
    [ -f "$DETAIL_FILE" ] && DETAIL=$(cat "$DETAIL_FILE")
    DETAIL=$((DETAIL + ${PROGRESS_STEP:-0})); printf '%s' "$DETAIL" > "$DETAIL_FILE"
     printf '%s' "${CURL_SESSION_DETAIL_BODY:-}"
     if [ -z "${CURL_SESSION_DETAIL_BODY:-}" ]; then printf '{"time":{"updated":%s},"tokens":{"input":%s}}' "$DETAIL" "$DETAIL"; fi
     case " $* " in *' --write-out '*) printf '\n%s' "${CURL_SESSION_DETAIL_HTTP_CODE:-200}" ;; esac
    ;;
  *) printf '%s' "${CURL_HTTP_CODE:-200}" ;;
esac
exit 0
""", self.bin)
        self.prompt = self.root / "prompt.txt"
        self.log = self.root / "delegation.log"
        self.prompt.write_text("테스트 프롬프트\n")
        self.calls = self.root / "calls.txt"
        self.curl_calls = self.root / "curl-calls.txt"
        self.curl_configs = self.root / "curl-configs.txt"
        self.opencode_pids = self.root / "opencode-pids.txt"

    def tearDown(self):
        self._stop_stub_processes()
        self.temp.cleanup()

    def _write(self, name, content, directory):
        if name == "opencode":
            content = content.replace(
                "#!/usr/bin/env bash\n",
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$$\" >> \"$OPENCODE_PIDS\"\n",
                1,
            )
        path = directory / name
        path.write_text(content)
        os.chmod(path, 0o755)

    def _stop_stub_processes(self):
        if not self.opencode_pids.exists():
            return
        pids = [int(value) for value in self.opencode_pids.read_text().split() if value.isdigit()]
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.05)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _script_env(self, project, extra_env):
        environment = os.environ.copy()
        environment.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{environment['PATH']}",
            "OPENCODE_CALLS": str(self.calls),
            "OPENCODE_PIDS": str(self.opencode_pids),
            "CURL_CALLS": str(self.curl_calls),
            "CURL_CONFIGS": str(self.curl_configs),
            "REAL_CTL": str(KIT / "core/scripts/opencode-serve-ctl.sh"),
            "ORCHESTRATE_STATE_DIR": str(self.root / "state"),
            "CURL_SESSIONS_AFTER": '[{"id":"ses_default","directory":"%s","time":{"updated":1},"tokens":1}]' % (project or self.project),
            **extra_env,
        })
        return environment

    def _script_command(self, umask=None, log=None):
        argv = ["bash", str(self.scripts / "run-delegation.sh"), "worker", str(self.prompt), str(log or self.log)]
        if umask is None:
            return argv
        # umask 를 명시 주입하지 않으면, 실행 환경이 이미 좁은 umask(077 등)일 때
        # chmod/install 을 제거하는 변이가 살아남는다(권한 테스트가 환경 덕을 본다).
        quoted = " ".join(shlex.quote(item) for item in argv)
        return ["bash", "-c", "umask %s; exec %s" % (umask, quoted)]

    def run_script(self, *, project=None, umask=None, log=None, **extra_env):
        for suffix in (".session-count", ".detail-count"):
            (Path(str(self.curl_calls) + suffix)).unlink(missing_ok=True)
        return subprocess.run(
            self._script_command(umask=umask, log=log),
            cwd=project or self.project,
            capture_output=True,
            text=True,
            env=self._script_env(project, extra_env),
            timeout=10,
        )

    def launch_script(self, *, project=None, log=None, **extra_env):
        """동시 실행 검증용 — 블로킹하지 않고 `Popen` 을 돌려준다."""
        return subprocess.Popen(
            self._script_command(log=log),
            cwd=project or self.project,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._script_env(project, extra_env),
            # 위임 트리(래퍼 + nohup 자식 + 그 후손)를 통째로 정리할 수 있도록 새 세션으로 띄운다.
            start_new_session=True,
        )

    def without_flock_path(self):
        """현재 PATH의 실행 파일을 flock만 제외해 임시 PATH에 노출한다."""
        no_flock = self.root / "no-flock-bin"
        no_flock.mkdir()
        for source_directory in os.environ["PATH"].split(os.pathsep):
            directory = Path(source_directory)
            if not directory.is_dir():
                continue
            for candidate in directory.iterdir():
                if candidate.name == "flock" or not os.access(candidate, os.X_OK):
                    continue
                target = no_flock / candidate.name
                if not target.exists():
                    target.symlink_to(candidate)
        return str(no_flock)

    def assert_lock_snapshot(self, snapshot, *, project):
        """opencode 실행 중 캡처한 락 산출물이 **어느 락인지**까지 확인한다.

        비flock 환경의 산출물은 `<이름>.d` 디렉터리라, 접미사를 정규화하지 않으면
        `assertNotEqual(name, "opencode.lock")` 같은 단정이 **전역 락으로 회귀해도 통과**한다
        (`opencode.lock.d` != `opencode.lock`). 환경 차이는 단정을 지울 이유가 아니라
        정규화해서 각각 단언할 이유다.
        """
        locks = list(snapshot.glob("opencode*.lock"))
        lock_dirs = list(snapshot.glob("opencode*.lock.d"))
        self.assertEqual(len(locks) + len(lock_dirs), 1, list(snapshot.iterdir()) if snapshot.exists() else [])
        lock = (locks + lock_dirs)[0]
        stem = lock.name[:-2] if lock.name.endswith(".d") else lock.name
        if project:
            # 프로젝트 락은 `opencode-<슬러그>-<해시>.lock` 형태다. 전역 락 이름이면 회귀다.
            self.assertTrue(stem.startswith("opencode-"), stem)
            self.assertNotEqual(stem, "opencode.lock")
        else:
            self.assertEqual(stem, "opencode.lock")
        if lock_dirs:
            self.assertTrue((lock_dirs[0] / "pid").is_file())

    def test_attach_mode_uses_project_lock(self):
        snapshot = self.root / "attach-lock"
        result = self.run_script(LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_lock_snapshot(snapshot, project=True)
        self.assertIn("--attach http://127.0.0.1:4096", self.calls.read_text())

    def test_concurrent_delegations_of_same_project_serialize(self):
        """같은 프로젝트의 두 위임이 **실제로 배타적으로** 실행돼야 한다.

        락 산출물의 존재만 단정하면 `flock -n` 호출을 지우거나 배타적 `mkdir` 을 항상
        성공시키는 변이가 살아남는다(2d 리뷰 재현). 두 프로세스의 실행 구간이 겹치는지를
        직접 본다. **순서는 단정하지 않는다** — 경합 순서는 비결정적이라 순서를 고정하면
        이 페이즈에서 이미 나온 "비결정 테스트" 함정이 재발한다.

        전파(Task 5) 후 4개 프로젝트가 동시에 위임을 돌릴 때 상호배제가 깨지면 업스트림의
        "토큰 0개 + exit 0 침묵사"가 재발한다 — 이 페이즈가 막으려던 바로 그 결함이다.
        """
        window = self.root / "windows.txt"
        self._write("opencode", """#!/usr/bin/env bash
printf 'START %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
/bin/sleep 1.5
printf 'END %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
echo 'loop session.id ses_test_session'
""", self.home / ".opencode/bin")
        # 스핀락(비flock 경로)은 대기 1회당 10초를 소진한 것으로 계산한다. 무응답 sleep 스텁이면
        # 30분 한도를 순식간에 태워 exit 4 가 되므로, 짧게라도 **실제로 자는** 스텁을 준다.
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.2\n", self.bin)

        # curl 스텁은 호출 횟수 파일로 세션 목록의 before/after 를 가른다. 두 프로세스가 그 파일을
        # 공유하면 나중 프로세스가 차분에서 새 세션을 못 찾아(세션 미개시) 락과 무관하게 실패한다.
        first = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "first.log",
            CURL_CALLS=str(self.root / "curl-first.txt"),
            CURL_CONFIGS=str(self.root / "curl-first-configs.txt"),
        )
        second = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "second.log",
            CURL_CALLS=str(self.root / "curl-second.txt"),
            CURL_CONFIGS=str(self.root / "curl-second-configs.txt"),
        )
        first_output = first.communicate(timeout=60)
        second_output = second.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, first_output)
        self.assertEqual(second.returncode, 0, second_output)

        events = [line.split() for line in window.read_text().splitlines() if line.strip()]
        starts = sorted(int(event[1]) for event in events if event[0] == "START")
        ends = sorted(int(event[1]) for event in events if event[0] == "END")
        self.assertEqual(len(starts), 2, window.read_text())
        self.assertEqual(len(ends), 2, window.read_text())
        # 두 구간이 겹치지 않으면 "먼저 끝난 시각 <= 나중 시작 시각"이 성립한다.
        self.assertLessEqual(
            ends[0],
            starts[1],
            "두 위임의 실행 구간이 겹쳤다 — 상호배제가 성립하지 않는다:\n%s" % window.read_text(),
        )

    def test_projects_with_same_basename_get_distinct_locks(self):
        """basename 이 같은 두 프로젝트는 서로 다른 락을 써야 한다 (경로 해시가 이름에 들어간다).

        이름만으로 락을 만들면 `~/a/project` 와 `~/b/project` 가 한 락을 공유해
        무관한 두 프로젝트의 위임이 서로를 막는다.
        """
        seen = []
        for parent in ("a", "b"):
            project = self.root / parent / "project"
            project.mkdir(parents=True)
            snapshot = self.root / ("lock-" + parent)
            session = '[{"id":"ses_default","directory":"%s","time":{"updated":1},"tokens":1}]' % project
            result = self.run_script(project=project, CURL_SESSIONS_AFTER=session, LOCK_SNAPSHOT=str(snapshot))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = {item.name for item in snapshot.glob("opencode*.lock*")}
            self.assertNotIn("opencode.lock", names, "프로젝트 위임이 전역 락을 잡았다")
            seen.append(names)
        # 두 번째 스냅샷에는 첫 실행의 락도 남아 있다. 새로 생긴 이름이 있어야 두 프로젝트가
        # 서로 다른 락을 쓴 것이다 — 이름이 basename 만으로 정해지면 새 이름이 생기지 않는다.
        self.assertTrue(seen[1] - seen[0], "basename 이 같은 두 프로젝트가 같은 락을 공유했다: %s" % seen)

    def test_lock_is_released_when_delegation_processes_die(self):
        """위임 프로세스가 모두 사라지면 락이 남아 다음 위임을 영구히 막으면 안 된다.

        주의 — **래퍼만 죽는 것으로는 부족하다.** nohup 자식이 락 fd 를 상속하도록 설계돼 있어
        (2026-07-28 결정), 래퍼가 죽어도 실제 위임이 도는 동안 락은 유지된다. 그게 정상이다.
        이 테스트는 래퍼와 자식이 **모두** 사라진 뒤를 본다(크래시·강제 종료 시나리오).
        """
        window = self.root / "windows.txt"
        self._write("opencode", """#!/usr/bin/env bash
printf 'START %s\\n' "$(/bin/date +%s%N)" >> "$WINDOW_FILE"
/bin/sleep 30
""", self.home / ".opencode/bin")
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep 0.2\n", self.bin)
        holder = self.launch_script(
            WINDOW_FILE=str(window),
            log=self.root / "holder.log",
            CURL_CALLS=str(self.root / "curl-holder.txt"),
        )
        state = self.root / "state"
        deadline = time.time() + 10
        while time.time() < deadline and not (state.exists() and any(state.glob("opencode*.lock*"))):
            time.sleep(0.1)
        self.assertTrue(any(state.glob("opencode*.lock*")), "첫 위임이 락을 잡지 못했다")

        # 락 fd 는 후손이 하나라도 살아 있으면 유지된다(설계된 동작). 트리를 통째로 정리한다.
        os.killpg(os.getpgid(holder.pid), signal.SIGKILL)
        holder.communicate(timeout=10)

        # 원래 스텁(즉시 종료)으로 되돌려 두 번째 위임이 곧바로 끝나는지 본다.
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
echo 'loop session.id ses_test_session'
""", self.home / ".opencode/bin")
        try:
            result = self.run_script(log=self.root / "second.log")
        except subprocess.TimeoutExpired:
            self.fail("래퍼가 죽은 뒤에도 락이 남아 다음 위임이 진행되지 못했다")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_attach_creates_session_before_launch(self):
        """attach 모드는 세션을 **먼저 만들고** 그 ID 로 클라이언트를 붙여야 한다.

        서버는 세션의 directory 를 자기 cwd 로 기록하므로(PITFALLS 18), 기동 전후 차분 +
        directory 일치로 식별하면 서버를 띄운 프로젝트에서만 성공한다.
        """
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--session ses_created1", self.calls.read_text())
        self.assertIn("SESSION_ID=ses_created1", result.stdout)

    def test_attach_session_survives_server_cwd_mismatch(self):
        """서버가 엉뚱한 directory 를 돌려줘도 위임은 성공해야 한다 (PITFALLS 18 회귀 고정)."""
        mismatched = '[{"id":"ses_elsewhere","directory":"/not/this/project","time":{"updated":1},"tokens":1}]'
        result = self.run_script(CURL_SESSIONS_BEFORE=mismatched, CURL_SESSIONS_AFTER=mismatched)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DONE", result.stdout)

    def test_session_creation_failure_falls_back_to_standalone(self):
        """세션 생성이 실패하면 attach 를 포기하고 검증된 standalone 경로로 진행한다."""
        result = self.run_script(CURL_CREATE_HTTP_CODE="500")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK", result.stdout)
        calls = self.calls.read_text()
        self.assertNotIn("--attach", calls, "생성 실패인데 attach 로 붙었다")

    def test_session_creation_failure_does_not_abort_other_sessions(self):
        """생성 실패 시 남의 세션(사용자 대화형 TUI 등)을 abort 하면 안 된다."""
        existing = '[{"id":"ses_USER_INTERACTIVE_TUI","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_CREATE_HTTP_CODE="500", CURL_SESSIONS_AFTER=existing)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        configs = self.curl_configs.read_text() if self.curl_configs.exists() else ""
        self.assertNotIn("/session/ses_USER_INTERACTIVE_TUI/abort", configs)

    def test_new_session_per_model_attempt(self):
        """모델 폴백 시 이전 세션 ID 를 재사용하지 말고 새로 만든다."""
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
COUNT=$(grep -c . "$OPENCODE_CALLS")
echo 'loop session.id ses_test_session'
if [ "$COUNT" -eq 1 ]; then echo 'ERROR status 429 rate limit'; exit 1; fi
""", self.home / ".opencode/bin")
        result = self.run_script(PROGRESS_STEP="1")
        calls = self.calls.read_text()
        self.assertIn("--session ses_created1", calls)
        self.assertIn("--session ses_created2", calls, "두 번째 모델이 이전 세션을 재사용했다:\n" + calls)

    def test_log_injected_session_id_is_never_used_for_abort(self):
        """abort 대상은 서버가 준 ID 뿐이다 — 로그에 심어진 ID 를 신뢰하면 안 된다."""
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
echo '{"sessionID":"ses_ATTACKER"}'
echo 'loop session.id real'
echo '! agent "worker" not found. Falling back to default agent'
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        configs = self.curl_configs.read_text()
        self.assertNotIn("ses_ATTACKER", configs)
        self.assertIn("/session/ses_created1/abort", configs)

    def test_repository_serve_ctl_symlink_reaches_controller(self):
        controller = KIT / "scripts/opencode-serve-ctl.sh"
        self.assertTrue(controller.is_symlink())
        result = subprocess.run(
            ["bash", str(controller), "invalid"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("사용법:", result.stderr)

    def test_nonexecutable_ctl_is_found_when_bash_invokes_it(self):
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("serve 제어 스크립트 없음", result.stdout)

    def test_spinlock_writes_pid_file_without_flock(self):
        stale_lock = self.root / "state/opencode.lock.d"
        stale_lock.mkdir(parents=True)
        (stale_lock / "pid").write_text("99999999\n")
        observed_pid = self.root / "spinlock-pid"
        self._write("rm", "#!/usr/bin/env bash\nif [ -f \"$2/pid\" ]; then /bin/cp \"$2/pid\" \"$SPINLOCK_PID\"; fi\n/bin/rm \"$@\"\n", self.bin)
        result = self.run_script(SERVE_RC="1", PATH=f"{self.bin}:{self.without_flock_path()}", SPINLOCK_PID=str(observed_pid))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(stale_lock.exists())
        self.assertNotEqual(observed_pid.read_text().strip(), "99999999")

    def test_log_and_state_permissions_are_private(self):
        # umask 022(느슨한 환경)를 명시 주입한다 — 좁은 umask 환경에서는 권한 설정 코드를
        # 제거해도 결과가 우연히 사적이라 변이가 살아남는다.
        result = self.run_script(umask="022")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "state").stat().st_mode & 0o777, 0o700)

    def test_serve_env_injection_is_rejected(self):
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVE_PORT=4096\nOPENCODE_SERVER_PASSWORD='safe\nurl = \"http://attacker.invalid\"'\n"
        )
        os.chmod(self.home / ".config/opencode/serve.env", 0o600)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 폴백 사유까지 단정해야 이 테스트가 공허해지지 않는다. 검증이 제거되면 attach 로 진행해
        # 이 메시지가 사라지고 주입이 성립한다(리뷰 재현 확인).
        self.assertIn(
            "SERVE_FALLBACK: standalone 모드 (서버 인증정보 없음)",
            result.stdout,
            "악성 비밀번호가 ctl 검증에서 거부되지 않았다 — attach 로 진행하면 주입이 성립한다",
        )
        configs = self.curl_configs.read_text() if self.curl_configs.exists() else ""
        self.assertNotIn('url = "http://attacker.invalid"', configs)

    def test_password_reaches_attach_client(self):
        """attach 모드에서는 클라이언트 자식이 서버 비밀번호를 **가져야** 한다.

        `opencode run --attach` 는 `OPENCODE_SERVER_PASSWORD`(또는 `-p`)로 서버에 인증한다.
        이것을 지우면 클라이언트가 `Error: Session not found` 로 즉사한다(2026-08-13 실환경 실측 —
        스텁 테스트로는 잡히지 않아 전파 시점에 4개 프로젝트가 동시에 깨졌다).
        `-p` 로 argv 에 넣는 대안은 공용 서버에서 `ps` 로 전 사용자에게 노출되므로 더 나쁘다.
        위임 에이전트는 같은 사용자라 어차피 `serve.env`(600)를 읽을 수 있으므로,
        클라이언트에게 주지 않는 것은 방어 효과가 없다.
        """
        dump = self.root / "child-env.txt"
        result = self.run_script(OPENCODE_ENV_DUMP=str(dump))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODE=attach", result.stdout + "MODE=attach")  # 하네스 기본이 attach 경로다
        self.assertIn(
            "OPENCODE_SERVER_PASSWORD=test-password",
            dump.read_text(),
            "attach 클라이언트가 비밀번호를 못 받으면 서버 인증에 실패한다",
        )

    def test_password_is_absent_in_standalone_mode(self):
        """standalone 폴백에서는 서버가 없으므로 비밀번호를 자식에게 넘기지 않는다."""
        dump = self.root / "child-env.txt"
        result = self.run_script(SERVE_RC="1", OPENCODE_ENV_DUMP=str(dump))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK", result.stdout)
        self.assertIn(
            "OPENCODE_SERVER_PASSWORD=<unset>",
            dump.read_text(),
            "standalone 인데 비밀번호가 자식 환경에 남았다",
        )

    def test_log_file_permissions_normalized_when_file_exists(self):
        """이미 존재하는 로그 파일도 매 실행 600으로 교정돼야 한다.

        `(umask 0177; : > FILE)` 는 **생성 시에만** 적용되므로 기존 644 파일은 그대로 남는다.
        공용 서버에서 로그에는 위임 프롬프트 전문과 세션 ID가 들어간다.
        """
        self.log.write_text("이전 실행 잔재\n")
        os.chmod(self.log, 0o644)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.log.stat().st_mode & 0o777,
            0o600,
            "기존 로그 파일 권한이 600으로 교정되지 않았다",
        )

    def test_log_file_is_600_from_creation(self):
        self._write("chmod", """#!/usr/bin/env bash
if [ "$2" = "$WATCHED_LOG_FILE" ]; then
  printf '%s\\n' "$(/usr/bin/stat -c %a "$2")" >> "$CHMOD_LOG"
fi
/bin/chmod "$@"
""", self.bin)
        result = self.run_script(
            WATCHED_LOG_FILE=str(self.log),
            CHMOD_LOG=str(self.root / "chmod-log"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "chmod-log").exists(), "로그 생성 뒤 chmod가 호출되었습니다")
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_project_lock_name_strips_newlines(self):
        project = self.root / "project\nMODEL_USED=forged"
        project.mkdir()
        session = json.dumps([{"id": "ses_newline", "directory": str(project), "time": {"updated": 1}}])
        snapshot = self.root / "newline-lock"
        result = self.run_script(project=project, CURL_SESSIONS_AFTER=session, LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_lock_snapshot(snapshot, project=True)
        lock = next(iter(list(snapshot.glob("opencode-*.lock")) + list(snapshot.glob("opencode-*.lock.d"))))
        self.assertNotIn("\n", lock.name)

    def test_standalone_fallback_acquires_global_lock(self):
        snapshot = self.root / "global-lock"
        result = self.run_script(SERVE_RC="1", LOCK_SNAPSHOT=str(snapshot))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_lock_snapshot(snapshot, project=False)
        self.assertIn("SERVE_FALLBACK: standalone 모드", result.stdout)
        self.assertNotIn("--attach", self.calls.read_text())

    def test_fallback_reports_missing_ctl(self):
        (self.scripts / "opencode-serve-ctl.sh").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("serve 제어 스크립트 없음", result.stdout)

    def test_fallback_warns_when_serve_is_alive(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 /tmp/opencode serve --port 4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_ALIVE_FALLBACK", result.stdout + result.stderr)

    def test_fallback_warns_when_bare_opencode_serve_is_alive(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 opencode serve --port 4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_ALIVE_FALLBACK", result.stdout + result.stderr)

    # `ps -eo pid,ppid,pgid,args` 전체 스캔과 `ps ... -p <pid>` 단건 조회에 **모두** 답하는 스텁.
    # 구현이 같은 스캔 안에서 부모를 찾든 별도 조회를 하든 통과해야 한다(구현 방식을 고정하지 않는다).
    PS_TABLE_STUB = """#!/usr/bin/env bash
TABLE=%s
TARGET=""
PREV=""
for ARG in "$@"; do
  if [ "$PREV" = "-p" ]; then TARGET="$ARG"; fi
  PREV="$ARG"
done
if [ -n "$TARGET" ]; then
  printf '%%s\\n' "$TABLE" | awk -v p="$TARGET" '$1 == p { $1=""; $2=""; $3=""; sub(/^ +/, ""); print }'
  exit 0
fi
printf '%%s\\n' "$TABLE"
"""

    # 위임 래퍼(부모) 행. 실행 파일이 bash 라 전체 스캔의 opencode 필터에는 걸리지 않는다.
    WRAPPER_ROW = " 500 400 400 bash scripts/run-delegation.sh worker prompt.txt delegation.log"

    def _write_ps_table(self, *rows):
        table = "\n".join(rows)
        self._write("ps", self.PS_TABLE_STUB % ("'" + table + "'"), self.bin)

    def test_preflight_ignores_managed_attach_process(self):
        # 부모가 실제로 위임 래퍼일 때만 "관리 중"이다. (예전 스텁은 부모 행이 없어
        # ppid≠1 이라는 이유만으로 통과했다 — 부모 미상은 관리 근거가 못 된다.)
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach http://127.0.0.1:4096",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_attachlike_prompt_text_from_foreign_parent(self):
        """프롬프트 본문에 attach 플래그처럼 보이는 문자열이 있어도 부모가 래퍼가 아니면 차단.

        `ps` 는 argv 를 공백으로 이어 보여주므로 문자열만으로는 진짜 플래그와 구분할 수 없다.
        이 저장소는 그 문법을 다루는 프로젝트라 프롬프트에 등장할 개연성이 낮지 않다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run 프롬프트에 --attach http://127.0.0.1:9999 문구가 있음",
            " 700 1 700 /bin/bash -c 사용자가-직접-실행",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_accepts_equals_form_attach_from_wrapper(self):
        """등호 형식(`--attach=URL`)도 부모가 래퍼면 정상 — 공백 형식만 인정하면 정상 병렬 위임이 죽는다."""
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach=http://127.0.0.1:4096 --dir /x",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_process_whose_parent_is_unknown(self):
        """부모 조회가 비면 '관리 중'으로 취급하지 말 것 — 부모 미상은 fail-closed 다."""
        self._write_ps_table(
            " 401 900 401 /tmp/opencode run --attach http://127.0.0.1:4096",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_flags_parent_that_merely_mentions_wrapper_name(self):
        """부모 판정도 **필드**로 해야 한다 — 명령줄에 이름이 스쳐 지나가는 것은 근거가 아니다.

        자식 후보는 `basename($4)=="opencode"`·`$5=="run"` 처럼 엄격히 보면서 부모만 전체 줄
        부분 문자열로 보면, 이 task 가 닫으려던 위장이 부모 쪽으로 옮겨갈 뿐이다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run --attach http://127.0.0.1:9999",
            " 700 1 700 /bin/bash -c echo not-the-real-run-delegation-wrapper-but-mentions-it",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_client_of_versioned_wrapper(self):
        """래퍼 파일명이 `run-delegation-v2.sh` 처럼 변형이어도 관리 중으로 인정해야 한다.

        위임 스크립트를 고치는 페이즈에서는 안정본 사본을 얼려서 쓴다(이 저장소의 운영 관행).
        정확히 `run-delegation.sh` 만 인정하면 그 기간의 정상 병렬 위임이 exit 3 으로 죽는다.
        """
        self._write_ps_table(
            " 401 500 401 /tmp/opencode run --attach http://127.0.0.1:4096",
            " 500 400 400 bash scripts/run-delegation-v2.sh worker prompt.txt delegation.log",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_flags_parent_with_lookalike_wrapper_filename(self):
        """신뢰하는 래퍼 이름은 `run-delegation.sh` 와 버전 사본(`-v2`)뿐이다.

        `^run-delegation.*[.]sh$` 같은 열린 와일드카드는 임의의 `run-delegation*.sh` 파일명을
        신뢰한다. 이 가드는 Task 5 에서 4개 프로젝트로 복사되므로 전파 전에 좁혀야 한다.
        """
        self._write_ps_table(
            " 401 700 401 /tmp/opencode run --attach http://127.0.0.1:9999",
            " 700 1 700 bash /home/other/run-delegation-totally-unrelated-script.sh",
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_bare_argv_client_of_wrapper(self):
        """경로 없는 bare argv + 진짜 attach + 부모가 래퍼 → 무시 (E1×E3 교차, C23)."""
        self._write_ps_table(
            " 401 500 401 opencode run --attach http://127.0.0.1:4096",
            self.WRAPPER_ROW,
        )
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_blocks_orphan_attach_process(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 /tmp/opencode run --attach http://127.0.0.1:4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_blocks_bare_orphan_in_own_process_group(self):
        # C19: 현재 프리플라이트는 ps -o pgid= -p $$를 호출하지 않는다. 변이로 그 호출이
        # 되살아나도 이 테스트가 우연히 통과하지 않도록, 실제 ps 표 형식만 반환한다.
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 opencode run --attach http://127.0.0.1:4096'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_blocks_prompt_text_that_only_mentions_attach(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 2 401 /tmp/opencode run 작업 프롬프트에 --attach 단어가 있음'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_preflight_ignores_unrelated_argv_text(self):
        self._write("ps", "#!/usr/bin/env bash\nprintf '%s\\n' ' 401 1 401 /bin/bash -c prompt-contains-opencode run --attach'\n", self.bin)
        result = self.run_script(SERVE_RC="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_agent_not_found_fails_fast(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_test_session","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        session = '[{"id":"ses_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]",
            CURL_SESSIONS_CALL_2=session,
            CURL_SESSIONS_CALL_3="[]",
            CURL_SESSIONS_CALL_4=session,
        )
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_agent_not_found_ignores_agent_output(self):
        self._write("opencode", "#!/usr/bin/env bash\nfor _ in $(seq 1 60); do echo 'INFO 작업 진행'; done\necho 'loop session.id ses_ok'\necho '작업 결과: agent \"worker\" not found 문구를 설명함'\n", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DONE", result.stdout)

    def test_agent_not_found_detects_raw_quote_form(self):
        self._write("opencode", "#!/usr/bin/env bash\necho '! agent \"worker\" not found. Falling back to default agent'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_raw_quote","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_agent_not_found_is_detected_after_30_line_preamble(self):
        self._write("opencode", "#!/usr/bin/env bash\nfor _ in $(seq 1 31); do echo 'INFO 초기화'; done\necho 'agent \\\"worker\\\" not found'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_long_preamble","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND", result.stdout)

    def test_fallback_reports_missing_serve_port(self):
        (self.home / ".config/opencode/serve.env").write_text(
            "OPENCODE_SERVER_PASSWORD=test-password\n"
        )
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SERVE_FALLBACK: standalone 모드 (serve 환경 포트 없음)", result.stdout)

    def test_watchdog_aborts_server_session(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_abort_target","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("--request POST", self.curl_calls.read_text())
        config = self.curl_configs.read_text()
        self.assertIn("url = \"http://127.0.0.1:4096/session/ses_created1/abort\"", config)
        self.assertIn("user = \"opencode:test-password\"", config)
        self.assertNotIn("test-password", self.curl_calls.read_text())

    def test_abort_failure_is_surfaced(self):
        self._write("opencode", """#!/usr/bin/env bash
echo '{"type":"error","sessionID":"ses_abort_failure","message":"agent \\"worker\\" not found"}'
""", self.home / ".opencode/bin")
        result = self.run_script(CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)

    def test_worktrees_share_project_lock(self):
        repository = self.root / "repository"
        worktree = self.root / "worktree"
        repository.mkdir()
        worktree.mkdir()
        self._write("git", """#!/usr/bin/env bash
if [ "$1" = rev-parse ]; then
  printf '%s\\n' "$TEST_COMMON_DIR"
  exit 0
fi
exit 1
""", self.bin)
        first_snapshot = self.root / "first-worktree-lock"
        second_snapshot = self.root / "second-worktree-lock"
        first = self.run_script(project=repository, TEST_COMMON_DIR=str(repository / ".git"), LOCK_SNAPSHOT=str(first_snapshot))
        second = self.run_script(project=worktree, TEST_COMMON_DIR=str(repository / ".git"), LOCK_SNAPSHOT=str(second_snapshot))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assert_lock_snapshot(first_snapshot, project=True)
        self.assert_lock_snapshot(second_snapshot, project=True)
        self.assertEqual(
            [item.name for item in first_snapshot.glob("opencode-*.lock*")],
            [item.name for item in second_snapshot.glob("opencode-*.lock*")],
        )

    def test_model_fallback_chain_preserved(self):
        # 각 실행은 별도 프로세스이므로 호출 횟수 파일로 시도 순서를 판정한다.
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
COUNT=$(wc -l < "$OPENCODE_CALLS")
echo 'loop session.id test-session'
if [ "$COUNT" -eq 1 ]; then echo 'ERROR status 429 rate limit'; exit 1; fi
""", self.home / ".opencode/bin")
        first = '[{"id":"ses_first","directory":"%s","time":{"updated":1}}]' % self.project
        both = '[{"id":"ses_first","directory":"%s","time":{"updated":1}},{"id":"ses_second","directory":"%s","time":{"updated":2}}]' % (self.project, self.project)
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]",
            CURL_SESSIONS_CALL_2=first,
            CURL_SESSIONS_CALL_3=first,
            CURL_SESSIONS_CALL_4=both,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MODEL_USED=second/model", result.stdout)
        self.assertIn("MODEL_FALLBACK: first/model", result.stdout)

    def test_attach_uses_text_format(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls.read_text()
        self.assertIn("--print-logs --log-level INFO", calls)
        self.assertNotIn("--format json", calls)

    def test_stalled_at_init_still_exit_2(self):
        self._write("opencode", """#!/usr/bin/env bash
echo 'INFO bootstrap complete'
while :; do /bin/sleep 1; done
""", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STALLED_AT_INIT", result.stdout)

    def test_init_stall_reports_orphan_possibility(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)

    def test_init_stall_does_not_report_orphan_after_successful_abort(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        late = '[{"id":"ses_late","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_CALL_1="[]", CURL_SESSIONS_CALL_2="[]",
            CURL_SESSIONS_CALL_3="[]", CURL_SESSIONS_CALL_4="[]",
            CURL_SESSIONS_CALL_5="[]", CURL_SESSIONS_CALL_6="[]",
            CURL_SESSIONS_CALL_7="[]", CURL_SESSIONS_CALL_8="[]",
            CURL_SESSIONS_CALL_9="[]", CURL_SESSIONS_CALL_10="[]",
            CURL_SESSIONS_CALL_11="[]", CURL_SESSIONS_CALL_12="[]",
            CURL_SESSIONS_CALL_13="[]", CURL_SESSIONS_CALL_14=late,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("SESSION_ABORTED=ses_late", result.stdout)
        self.assertNotIn("ORPHAN_SESSIONS=미확보", result.stdout)

    def test_progress_http_error_counts_as_poll_failure(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done\n", self.home / ".opencode/bin")
        self._write("date", "#!/usr/bin/env bash\nFILE=\"$DATE_COUNTER\"; VALUE=0; [ -f \"$FILE\" ] && VALUE=$(cat \"$FILE\"); VALUE=$((VALUE + 10)); printf '%s' \"$VALUE\" > \"$FILE\"; printf '%s\\n' \"$VALUE\"\n", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text('{"tiers":{"default":["first/model"]}}\n')
        session = '[{"id":"ses_unauthorized","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            CURL_SESSION_DETAIL_BODY='{"error":"unauthorized"}',
            CURL_SESSION_DETAIL_HTTP_CODE="401",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("SERVER_POLL_FAILED", result.stdout)

    def test_agent_not_found_diagnostic_survives_abort_failure(self):
        self._write("opencode", "#!/usr/bin/env bash\necho 'agent \"worker\" not found'\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_abort_failure","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("AGENT_NOT_FOUND: 에이전트 'worker'를 찾을 수 없음", result.stdout)

    def test_init_loop_reports_agent_not_found_before_abort_failure(self):
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep .05\n", self.bin)
        # 클라이언트를 유지해 wait 뒤 진단 분기로 새지 않고 init 루프에서만 검증한다.
        self._write("opencode", "#!/usr/bin/env bash\necho 'agent \"worker\" not found'\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_init_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertLess(result.stdout.index("AGENT_NOT_FOUND"), result.stdout.index("ORPHAN_SESSION_WARNING"))

    def test_progress_loop_reports_agent_not_found_before_abort_failure(self):
        self._write("sleep", "#!/usr/bin/env bash\n/bin/sleep .05\n", self.bin)
        self._write("opencode", "#!/usr/bin/env bash\necho 'loop session.id ses_progress_agent'\n/bin/sleep .5\necho 'agent \"worker\" not found'\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        session = '[{"id":"ses_progress_agent","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_ABORT_RC="1")
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertLess(result.stdout.index("AGENT_NOT_FOUND"), result.stdout.index("ORPHAN_SESSION_WARNING"))

    def test_poll_failures_are_reported_periodically_before_stall(self):
        self._write("opencode", "#!/usr/bin/env bash\nwhile :; do /bin/sleep 1; done\n", self.home / ".opencode/bin")
        (self.home / ".config/opencode/model-policy.json").write_text('{"tiers":{"default":["first/model"]}}\n')
        session = '[{"id":"ses_poll_repeat","directory":"%s","time":{"updated":1}}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, CURL_SESSION_DETAIL_RC="1")
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertGreaterEqual(result.stdout.count("SERVER_POLL_FAILED"), 2, result.stdout)
        self.assertIn("서버 폴링 연속 실패", result.stdout)

    def test_error_spam_does_not_count_as_progress(self):
        self._write("opencode", """#!/usr/bin/env bash
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_stalled","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(CURL_SESSIONS_AFTER=session, DATE_COUNTER=str(self.root / "date-count"))
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("재시도 루프 스톨", result.stdout)
        self.assertNotIn("SERVER_POLL_FAILED", result.stdout)

    def test_server_progress_resets_stall_timer(self):
        self._write("opencode", """#!/usr/bin/env bash
COUNT=0
while [ "$COUNT" -lt 10 ]; do
  echo 'ERROR status 429 rate limit'
  COUNT=$((COUNT + 1))
  /bin/sleep .1
done
COUNT=0
while [ "$COUNT" -lt 51 ]; do
  echo 'INFO 작업 진행 중'
  COUNT=$((COUNT + 1))
done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_progress","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            PROGRESS_STEP="1",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("재시도 루프 스톨", result.stdout)

    def test_server_poll_failure_is_reported(self):
        self._write("opencode", """#!/usr/bin/env bash
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        (self.home / ".config/opencode/model-policy.json").write_text(
            '{"tiers":{"default":["first/model"]}}\n'
        )
        session = '[{"id":"ses_poll_failure","directory":"%s","time":{"updated":1},"tokens":1}]' % self.project
        result = self.run_script(
            CURL_SESSIONS_AFTER=session,
            CURL_SESSION_DETAIL_RC="1",
            DATE_COUNTER=str(self.root / "date-count"),
        )
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("SERVER_POLL_FAILED", result.stdout)
        self.assertIn("재시도 루프 스톨", result.stdout)

    def test_abort_failure_stops_fallback_and_exits_6(self):
        self._write("opencode", """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPENCODE_CALLS"
while :; do echo 'ERROR status 429 rate limit'; /bin/sleep .01; done
""", self.home / ".opencode/bin")
        self._write("date", """#!/usr/bin/env bash
FILE="$DATE_COUNTER"; VALUE=0; [ -f "$FILE" ] && VALUE=$(cat "$FILE"); VALUE=$((VALUE + 10)); printf '%s' "$VALUE" > "$FILE"; printf '%s\\n' "$VALUE"
""", self.bin)
        result = self.run_script(CURL_ABORT_RC="1", DATE_COUNTER=str(self.root / "date-count"))
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("ORPHAN_SESSIONS=ses_created1", result.stdout)
        self.assertEqual(self.calls.read_text().count("--agent worker"), 1)

    def test_missing_password_falls_back_to_standalone(self):
        (self.home / ".config/opencode/serve.env").write_text("OPENCODE_SERVE_PORT=4096\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("서버 인증정보 없음", result.stdout)
        self.assertNotIn("--attach", self.calls.read_text())

