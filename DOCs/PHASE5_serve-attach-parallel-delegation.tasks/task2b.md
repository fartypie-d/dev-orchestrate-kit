# Task 2b: v3 워치독 계층 재설계 — 세션 식별·진행 판정·abort 를 서버 API 기반으로

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/run-delegation.sh`, `tests/test_run_delegation.py`
- **선행**: Task 2 (`098c14f`)
- **재사용**: 개선 후 재사용 `core/scripts/run-delegation.sh` — 신규 파일 금지. 서버 호출은
  `core/scripts/opencode-serve-ctl.sh:health_check()` 의 `curl --config -` heredoc 패턴을
  **그대로 따를 것**(PW 를 `ps` 에 노출하지 않는 유일한 승인 방식). 새 curl 관용구를 발명하지 말 것.

## 배경 — 왜 이 task 가 생겼나

Task 2(`098c14f`)는 커밋됐지만 리뷰어 3종이 **🔴 8건으로 반려**했다. 지적들이 하나의 뿌리로
수렴한다: **v3 가 v2 의 검증된 신호(`loop session.id` 카운트)를 잃고 로그 문자열 추측으로
대체했다.** 오케스트레이터 실측(2026-08-13)으로 서버 API 가 그 신호를 정확히 제공함이
확인됐으므로, 이 task 는 워치독 계층을 API 기반으로 되돌린다.

이 task 는 **워치독 계층만** 다룬다. exit 7 스코프·프리플라이트·권한·심링크·스핀락은
**Task 2c** 다 — 건드리지 말 것.

## 전제 실측 (2026-08-13, 오케스트레이터 직접 — 재조사 금지)

`opencode serve` 를 임시 포트로 띄워 `/doc` 과 실제 응답을 확인했다:

| 사실 | 근거 |
|---|---|
| `GET /session` 은 세션 **배열**을 반환하고, 각 원소에 `id`·`directory`·`time`·`tokens`·`cost`·`title` 필드가 있다 | 실제 조회에서 이 워크트리 절대경로가 `directory` 로 확인됨 |
| `POST /session/{id}/abort` 존재 | `/doc` paths |
| `GET /session/{id}` 단건 조회 존재 | `/doc` paths |
| `GET /session/status` 는 빈 객체 `{}` 를 반환 | 실제 조회 — **쓰지 말 것** |
| 인증 = basic auth `opencode:$OPENCODE_SERVER_PASSWORD` | Task 1 실측 |

## 목표

attach 모드에서 (1) 세션을 **서버가 알려준 사실**로 식별하고, (2) 진행 여부를 **서버측 지표**로
판정하며, (3) abort 실패를 **삼키지 않는다**. 출력 포맷은 스펙대로 텍스트로 되돌린다.

## 고쳐야 할 결함 (전부 재현 있음)

### 🔴 B1. 세션 ID 추출이 조작 가능 — 교차 프로젝트 abort (security-reviewer)
현재 `record_session_id()` 는 로그 전체에서 `"sessionID":"[^"]*"` 를 raw grep 해 **마지막 매치**를
쓴다. 위임 에이전트가 다루는 외부 콘텐츠에 그 문자열이 섞이면 실제 ID 를 덮어쓴다.
재현에서 정상 ID 가 공격자 지정 값으로 바뀌었고, 래퍼가 **유효 인증으로 그 세션에 abort 를 호출**했다.
→ **로그 파싱을 폐기하고 서버 API 차분으로 확보**한다 (아래 스펙 1).

### 🔴 B2. `--format json` 이 스펙 위반이며 FAIL_RE 를 죽였다 (bash-reviewer / 기존 결함 d)
task2.md:29 는 "출력 포맷은 기존과 같은 default(텍스트) 유지"를 명시했다. JSON 으로 바꾼 탓에
`grep -a 'ERROR'` 전치 필터가 이벤트를 못 잡아 **모델 폴백·스톨 가드가 attach 에서 통째로 죽었다**.
B1 을 API 로 해결하면 JSON 이 더 이상 필요 없다. → **텍스트로 되돌린다**.

### 🔴 B3. init 판정(exit 2)이 도달 불가 (bash-reviewer)
`log_size > 0` 으로 바꾼 탓에, `--print-logs` 부트스트랩 INFO 가 즉시 쌓여 워치독이 1회차에
무조건 통과한다. 실측: 실제 v2 로그에서 첫 `loop session.id` 는 2913 바이트째다.
대조 재현 — 같은 스텁에 v3 는 `rc=124`(무한 대기), v2 는 `rc=2`.
→ **v2 의 판정 기준을 복원**한다 (아래 스펙 3).

### 🔴 B4. 진행 판정이 로그 바이트 증가라 스톨 가드가 무력화 (silent-failure-hunter)
429 재시도 스팸이 계속 타이머를 리셋한다. 실측: 106초간 429 만 뿜었는데 90초 스톨킬이 발화하지 않았고,
프로세스가 자발 종료할 때까지 락을 쥔 채 대기했다. 이 가드는 "12분+ 행"을 90초로 묶으려고
만든 것이다. → **바이트가 아닌 실제 진행 지표**로 바꾼다 (스펙 4).

### 🔴 B5. abort 반환값을 전부 버린다 → 고아 세션이 성공에 묻힌다 (silent-failure-hunter)
4개 호출부 전부 rc 를 안 본다. 스톨 경로에서 abort 가 실패해도 그대로 다음 모델로 넘어가
**같은 디렉터리에서 두 세션이 동시에 파일을 수정**하고, 최종 출력은 `DONE`/exit 0 이다.
변이 검증: 스톨 경로의 abort 호출을 지워도 **7개 테스트 전원 통과**(무커버리지 실증).
→ rc 를 확인하고 실패를 **치명적으로** 다룬다 (스펙 5).

### 🔴 B6. 무인증 serve 에서 abort 가 통째로 죽고 원인을 오표기 (silent-failure-hunter)
`$OPENCODE_SERVER_PASSWORD` 를 `set -u` 아래 raw 로 참조해 curl 실행 **전에** 서브셸이 죽는다.
그런데 메시지는 `curl=1` 로 네트워크 실패인 척한다. 전제표에 "미설정 시 unsecured" 가 지원 상태로
적혀 있고, `ensure` 는 이미 떠 있는 무인증 서버에 health_check 만으로 성공을 반환할 수 있다.
→ `${OPENCODE_SERVER_PASSWORD:-}` 로 받고 **attach 진입 전에 재검증**한다 (스펙 6).

### 🟠 B7. 모델 폴백 시 stale SESSION_ID (bash-reviewer)
`SESSION_ID` 가 for 루프 **밖**에서 한 번만 초기화된다. 모델 1 실패로 로그를 비워도 값이 남아,
**이미 끝난 이전 모델의 세션**에 abort 를 날리고 "성공"으로 보고한다. 진짜 고아는 방치된다.
→ 루프 진입부에서 리셋한다.

## 스펙

### 1. 세션 ID = 서버 API 차분 (B1 해결)
- 클라이언트 기동 **직전**에 `GET /session` 을 호출해, `directory` 가 `$RUN_DIR` 와 **정확히 일치**하는
  세션 ID 집합을 스냅샷한다.
- 기동 **후** 같은 조회를 폴링(2초 간격, 최대 60초)해 **스냅샷에 없던 새 ID** 가 나타나면 그것을 채택한다.
  둘 이상이면 `time` 이 가장 최근인 것.
- 로그에서 sessionID 를 읽는 코드(`record_session_id`)는 **삭제**한다.
- 프로젝트별 락이 같은 `--dir` 의 동시 위임을 직렬화하므로 차분은 모호해지지 않는다.
- 60초 안에 새 세션이 안 보이면 `SESSION_ID` 를 빈 값으로 두되 **경고를 남긴다**
  (`SESSION_ID_UNRESOLVED`) — 이후 abort 가 필요해지면 스펙 5의 실패 경로를 탄다.
- JSON 파싱은 `jq` 를 쓴다 (이미 필수 의존성 — 스크립트가 모델 정책 파싱에 쓰고 있다).

### 2. 출력 포맷 텍스트 복귀 (B2 해결)
- attach 호출에서 `--format json` 을 제거하고 **v2 와 동일하게 `--print-logs --log-level INFO`** 를 쓴다.
- 기존 `FAIL_RE`·`model_error_in_log` 전치 필터를 **원형 그대로** 되살린다 (말미 50줄 + ERROR 라인 스코프 포함).

### 3. init 판정 복원 (B3 해결)
- **standalone**: v2 그대로 — 로그에 `loop session.id` 가 나타나는지를 120초(12×10초) 안에 확인.
- **attach**: 스펙 1의 차분으로 **새 세션 ID 가 확보되는지**를 같은 시간창 안에 확인.
- 어느 쪽도 실패하면 기존과 같이 `STALLED_AT_INIT` + **exit 2** (의미 불변).

### 4. 진행 판정 (B4 해결)
- **standalone**: v2 그대로 — `loop session.id` **발생 횟수 증가**를 진행으로 본다.
- **attach**: `GET /session/{id}` 를 10초 주기로 조회해 `time.updated` **또는** `tokens` 합계가
  증가하면 진행으로 본다. 로그 바이트 크기는 **진행 신호로 쓰지 않는다**.
- 90초 무진행 + 기존 스톨 가드 조건은 그대로 유지한다.
- 서버 조회가 실패하면(네트워크·인증) 그 자체를 무진행으로 취급하지 말고, 연속 3회 실패 시
  `SERVER_POLL_FAILED` 를 출력하고 스톨 가드 판정을 **보수적으로**(=진행 없음) 적용한다.

### 5. abort 실패를 삼키지 않는다 (B5 해결)
- `abort_server_session` 은 성공 0 / 실패 비0 을 반환하고, **모든 호출부가 rc 를 확인**한다.
- 실패했으면:
  - `ORPHAN_SESSION: <id>` 를 출력하고,
  - **모델 폴백을 중단**한다 (다음 모델로 넘어가지 않는다 — 같은 디렉터리에서 두 세션이 도는 것을 막는 것이 목적).
  - 최종 종료 직전에 `ORPHAN_SESSIONS=<id[,id...]>` 요약 줄을 **반드시** 출력하고 **exit 6** 으로 끝낸다.
- **exit 6 은 이 task 가 추가하는 유일한 신규 코드**다 (0/2/3/4/5/7/64/66 의미 불변).
  의미: "고아 세션 가능성 있음 — 사람 확인 필요".

### 6. 인증 미설정 처리 (B6 해결)
- `PASSWORD="${OPENCODE_SERVER_PASSWORD:-}"` 로 받는다 (`set -u` 안전).
- **attach 진입 조건에 PW 비어있지 않음을 추가**한다. 비었으면 `SERVE_FALLBACK: standalone 모드
  (서버 인증정보 없음)` 을 출력하고 standalone 으로 명시 강등한다.
- abort 실패 메시지는 원인을 구분한다 — 인증정보 없음 / 세션 ID 미확보 / HTTP 코드 / curl rc.

### 7. stale SESSION_ID 리셋 (B7 해결)
- `for MODEL` 루프 진입부에서 `SESSION_ID=""` 로 리셋한다 (`: > "$LOG_FILE"` 하는 자리).

## 실패 테스트 (RED 먼저 — 전부 `tests/test_run_delegation.py`)

기존 7건을 깨뜨리지 말 것. 아래를 **추가**한다:

- `::test_session_id_comes_from_server_not_log` — 로그 본문에 `"sessionID":"ses_ATTACKER"` 를 심어도
  abort 대상이 **서버 API 가 준 ID** 여야 한다 (B1 회귀 가드)
- `::test_attach_uses_text_format` — attach 호출 인자에 `--format json` 이 **없고** `--print-logs` 가 있어야 한다 (B2)
- `::test_stalled_at_init_still_exit_2` — 부트스트랩 INFO 만 쌓고 세션이 안 생기면 exit 2 (B3)
- `::test_error_spam_does_not_count_as_progress` — 로그가 계속 커져도 서버측 지표가 그대로면 스톨로 판정 (B4)
- `::test_abort_failure_stops_fallback_and_exits_6` — abort 실패 시 다음 모델로 넘어가지 않고 exit 6 + `ORPHAN_SESSIONS=` 출력 (B5)
- `::test_missing_password_falls_back_to_standalone` — PW 없으면 attach 로 진입하지 않는다 (B6)
- `::test_session_id_reset_between_models` — 모델 1 세션 ID 가 모델 2 경로에서 abort 대상이 되지 않는다 (B7)

## 필수 규칙
- **bash 3.2 호환** — `mapfile`·`declare -A`·`${var^^}`·`sed -i`·`readlink -f`·`date -d`·`echo -e` 금지
- CLI 인터페이스 불변. exit 의미 불변 + **신규는 6 하나만**
- 금지사항 3종 주석(timeout 래핑·파이프 수신·프롬프트 인라인) 유지
- v2 가 코드에 남긴 **근거 주석을 삭제하지 말 것** — 이 저장소는 실측 근거를 코드에 남기는 게 규칙이다.
  Task 2 가 지운 주석(파일 고정 이유·말미 50줄 스캔 이유·스톨 가드 근거) 중 되살린 로직에 해당하는 것은 복원한다
- 테스트는 임시 디렉터리 주입 (`HOME`·`ORCHESTRATE_STATE_DIR`) — 실제 `~/.local/state/orchestrate`·
  실제 serve 를 절대 건드리지 말 것. 서버 호출은 PATH curl 스텁으로 흉내낸다

## 완료 조건
- `python3 -m unittest discover -s tests -v` 전건 PASS (신규 7건 RED 선행 출력 첨부)
- `bash -n core/scripts/run-delegation.sh` 통과
- **변이 검증 3건 이상**을 저장소 **밖 사본**에서 수행하고 결과를 보고에 첨부:
  ① 서버 API 세션 조회를 로그 grep 으로 되돌리면 B1 테스트가 죽는가
  ② abort rc 확인을 제거하면 B5 테스트가 죽는가
  ③ 진행 판정을 로그 바이트로 되돌리면 B4 테스트가 죽는가
  (하나라도 **생존**하면 그 테스트는 무의미하므로 다시 쓸 것)

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
`scripts/run-delegation-v2.sh`(오케스트레이터가 위임 실행용으로 둔 임시 파일)를 **읽지도 고치지도 말 것** ·
Task 2c 범위(exit 7 스코프·PREFLIGHT·심링크·권한·스핀락·폴백 사유 문구)를 건드리지 말 것 ·
작업 전 skill 툴로 `karpathy-guidelines` 로드

## 보고 형식
수정 파일 목록 / 신규 테스트 RED·GREEN 출력 전문 / 변이 검증 3건 결과 /
B1~B7 각각에 대해 "어떻게 닫았는지" 한 줄 / v3 대비 변경점 표(세션식별·포맷·init·진행·abort·인증) /
Task 2c 로 넘길 사항
