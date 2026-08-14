# Task 2e: 서버 API 표면 통합 (C7+C14 · C25 · C17)

- **에이전트**: kit-scripts
- **모델**: heavy (⚠️ 설치 스크립트 도메인 + 보안 항목 C14 포함)
- **대상 파일**: `core/scripts/opencode-serve-ctl.sh`, `core/scripts/run-delegation.sh`(호출부만),
  `tests/test_serve_ctl.py`, `tests/test_run_delegation.py`
- **선행**: 없음 (2d 커밋 `c7fd42b` 기준)
- **재사용**: **개선 후 재사용** — `core/scripts/opencode-serve-ctl.sh:74` `health_check()` 의
  `curl --config -` 관용구를 공용 요청 헬퍼로 승격해 새 액션이 공유한다.
  **신규 스크립트 파일 금지.** 서버 API 표면은 ctl 이 단독 소유한다(Task 1 제약).

## 범위 — 이 라운드는 "서버 API 축"만

> C18(프리플라이트 부모 검증)·C21·C23·C24 는 **Task 2f 소관**이다. 이번에 건드리지 말 것.
> 발견해도 보고만 하라. 프리플라이트 절(`run-delegation.sh` 117~145행)은 **읽기만** 한다.

| 항목 | 요지 | 심각도 |
|---|---|---|
| **C7+C14** | `run-delegation.sh` 의 curl basic-auth **3중 복제**(168·195·212행 = `server_sessions`·`server_progress`·`abort_server_session`)를 ctl 액션 호출로 교체. ctl `health_check`(79행)까지 합쳐 4번째 사본이던 관용구를 ctl 안 **단일 헬퍼**로 통합. **PW·PORT 형식 검증(ctl 63·69행)을 새 액션도 반드시 통과**하게 만든다 — 현재 run-delegation 은 같은 `serve.env` 를 재소싱하면서(31·60~63행) **비어있음 검사만** 해 curl config 주입이 가능하다 | 🟠 |
| **C25** | `run-delegation.sh:242` `: > "$LOG_FILE"` → 별도 `chmod 600`(243행) 사이에 TOCTOU 창. 그 창에 fd 를 잡으면 600 이 된 뒤에도 계속 읽힌다(2d 리뷰 PoC 재현). `(umask 0177; : > "$LOG_FILE")` 또는 `install -m 600 /dev/null "$LOG_FILE"` 로 **생성·권한을 한 번의 open() 으로 원자화**. `LOCK_DIR` 은 고치지 말 것(민감 내용 없음 — 실익 없는 변경 금지) | 🟠 |
| **C17** | 세션 매칭이 `RUN_DIR=$(pwd -P)` 와 서버 `.directory` 의 **문자열 정확 일치**에 의존 — 심링크 경로가 개입하면 attach 가 영구 exit 2. 실측 1회로 확인하거나, 불가하면 **근거 주석**을 남길 것(추측 주석 금지) | 🟡 |

## 순서

1. ctl 에 공용 요청 헬퍼 + 신규 액션 추가 (검증 경로를 반드시 통과하도록 배선)
2. `run-delegation.sh` 의 curl 3곳을 ctl 액션 호출로 교체 — **워치독 판정 로직은 그대로**,
   호출부만 옮긴다 (2b·2c 가 확정한 판정 기준을 바꾸면 이 라운드는 반려다)
3. C25 원자화
4. C17 실측 또는 근거 주석

## 실패 테스트 (RED 먼저 — 작성·실패 확인 후 구현)

- `tests/test_serve_ctl.py::test_session_actions_happy_path` — 신규 액션의 세션 목록·단건 조회·abort
  정상 경로 (stdout·exit 계약)
- `tests/test_serve_ctl.py::test_session_actions_reject_invalid_credentials` — `serve.env` 의 PW 에
  개행·따옴표·역슬래시가 있으면 **새 액션도** exit 64 로 거부한다
- `tests/test_run_delegation.py::test_serve_env_injection_is_rejected` — `serve.env` PW 에 개행이
  있을 때 curl config 에 **두 번째 `url =` 가 주입되지 않는다** (C14, 2d 에서 이월)
- `tests/test_run_delegation.py::test_log_file_is_600_from_creation` — 로그 파일이 **생성 시점부터**
  600 이다. 변이 기준: 원자 생성을 `: >` + `chmod` 2단계로 되돌리면 이 테스트가 죽어야 한다 (C25)

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED |
|---|---|---|
| 새 ctl 액션이 검증 분기 앞에서 dispatch 됨 | PW·PORT 검증 우회 (C14 미충족) | `test_session_actions_reject_invalid_credentials` |
| run-delegation 에 basic-auth 문자열이 남음 | "통합했다"는 주장과 코드 불일치 | 완료 조건의 `grep -c` 단정 (0 이어야 함) |
| C25 를 chmod 순서 변경으로만 처리 | TOCTOU 창 잔존 | `test_log_file_is_600_from_creation` + 되돌림 변이 |

## 필수 규칙

- bash 3.2 호환 · **CLI 인터페이스 불변** · **exit 코드 의미 불변**(0/2/3/4/5/6/7/64/66, 신규 금지)
- ctl 의 기존 exit 계약(0/1/64)·stdout 계약(`up`/`down`/`started`/`stopped`)을 깨지 말 것.
  **새 액션의 stdout·exit 계약을 정의해 보고에 남길 것** (Task 5 전파 때 필요)
- Task 2b·2c 가 확정한 워치독 판정 로직 변경 금지 — 호출부만 ctl 경유로 이동
- 금지사항 주석·근거 주석 삭제 금지
- 테스트는 임시 디렉터리 주입. 실제 `~/.local/state/orchestrate`·실제 serve 기동 금지
- **변이 검증은 `.orchestrate/mutation/` 에서** 수행한다. `/tmp` 사용 금지 —
  opencode 가 external_directory 로 거부해 그 자리에서 멈춘다 (이 페이즈 2c 1차 위임 실측)

## 완료 조건

- `python3 -m unittest discover -s tests -v` 전건 PASS (**신규 RED 선행 출력 첨부**, 기준선 181 이상)
- `bash -n core/scripts/run-delegation.sh core/scripts/opencode-serve-ctl.sh` 통과
- `grep -c 'user = "opencode:' core/scripts/run-delegation.sh` → **0**
- flock 을 PATH 에서 제거한 환경에서도 전체 스위트 통과 (출력 첨부)
- 변이 검증 3건 이상 (C14·C25 + 자체 고안 1건) — **수행 주체를 명시**할 것 (위임/검수자, C27 규칙)
- 전체 스위트 2회 연속 실행 후 잔여 `opencode run` 프로세스 없음

## 공통 금지

대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
새 파일을 만들었다면 보고에 이유를 명시할 것
