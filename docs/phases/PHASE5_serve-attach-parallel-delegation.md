---
phase: 5
date: 2026-08-12
kind: task
domain: scripts, docs
status: done
commits: PR #7·#8·#9 (main 병합)
cost: $61.28 (오케스트레이터 세션, opencode 위임 제외)
compactions: 0
interventions: 0
summary: run-delegation v3 — opencode serve+attach 병렬 위임 (전역 직렬화 해소, 프로젝트별 직렬 유지)
---

# 작업 지시서 — 위임 병렬화: serve+attach 전환 (2026-08-12)

## 인터뷰 결과
- 스코프: `run-delegation.sh` v3(attach 모드) + serve 제어 스크립트 + 테스트 + 문서/스킬 갱신.
  호스트 전파(4개 프로젝트 사본 동기화·systemd·전역 스킬 설치)는 **키트 머지 후 오케스트레이터 직접**.
- 우선순위: Task 1→2→3→4 순차 (2는 1에 의존, 3·4는 2에 의존).
- 제약: 사용자 승인 3건 — ① serve 상주 = systemd user 서비스 + 래퍼 lazy 기동 폴백
  ② 동시성 = **프로젝트별 직렬**(프로젝트 간 병렬), 전역 상한 없음(429 모니터링만)
  ③ 전파 = 키트+호스트 전체.
- 크기 등급: **standard** (계약 변경: exit 코드·락 의미 변화 → task-orchestrator 경유)

## 배경 (근거 실측 — 2026-08-12)
- 전역 락 직렬화로 하루 50세션 겹침 0, LOCK_WAIT 14건+, 대기 하한 67분 (트랜스크립트·세션 DB 실측).
- 동시 다중 프로세스 `opencode run`은 업스트림이 "고칠 계획 없음"으로 확정한 결함
  (busy_timeout=0 → SQLITE_BUSY, **토큰 0개 + exit 0 침묵사** — anomalyco/opencode#21215, #15188).
- 공식 병렬 경로 = `opencode serve` + `run --attach` (1.18.16 지원 확인). 스모크 테스트 통과:
  3-프로젝트 동시 attach 병렬 실행·`--dir` 기준 에이전트 로딩·DB 에러 0건.

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| serve 헬스 = `GET /global/health` (basic auth `opencode:<pw>`) | 실측 24096 샌드박스: noauth=401/auth=200 | 유지 |
| `OPENCODE_SERVER_PASSWORD` 설정 시 전 엔드포인트 401 강제, 미설정 시 "unsecured" 경고 | 동일 실측 | 유지 |
| attach 클라이언트 rc는 서버측 세션 실패를 반영 (미등록 모델 → rc=1) | 실측 | 유지 |
| `--format json`은 sessionID 포함 NDJSON 이벤트 | 실측 (`{"type":"error","sessionID":"ses_..."}`) | 유지 |
| 없는 에이전트 지정 → **실패 아님**, stderr 경고 후 기본 에이전트 폴백 rc=0 | 스모크 T4 실측: `! agent "scheduler" not found. Falling back to default agent` | 유지 — **v3가 감지해야 함** |
| `loop session.id` 시그니처는 attach 모드에서 **서버 로그에만** 찍힘 | 스모크 실측 | 유지 — 클라이언트 로그 기반 워치독 재설계 필요 |
| 프로젝트별 `scripts/run-delegation.sh`는 심링크 아닌 사본 | `ls -la` 4개 프로젝트 실측 | 유지 — 전파=복사 |
| systemd --user 사용 가능 | **뒤집힘** — linger 미활성, 버스 없음 (`No medium found`) | 호스트 전파 시 `enable-linger` 선행 |
| 클라이언트 kill = 서버 세션 중단 | **뒤집힘** — kill 후에도 서버 세션 계속(step2 생성). abort 경로는 step1에서 멈춤 (`.orchestrate/killtest/` 대조 실측) | `POST /session/{id}/abort` 필수 |
| sessionID 확보에 `--format json` 이 **필요**하다 | **뒤집힘** (2026-08-13 오케스트레이터 실측) — `GET /session` 응답 Session 모델에 `directory`·`time` 필드 존재. 실제 조회로 이 워크트리 경로 확인 | **텍스트 출력 유지 가능** — 기동 전후 세션 ID 집합 차분으로 특정 |

### Task 2e·2f 착수 전 실측 (2026-08-13, 오케스트레이터)

| 전제 | 근거 | 판정 |
|---|---|---|
| curl basic-auth 관용구가 4사본이다 | `run-delegation.sh:168·195·212` + `opencode-serve-ctl.sh:79` | 유지 — 통합 대상 확정 |
| run-delegation 이 `serve.env` 를 재소싱하면서 형식 검증을 물려받지 않는다 | `run-delegation.sh:31·60~63` 은 **비어있음 검사만**. 형식 검증은 ctl `63`(PORT 숫자)·`69`(PW 따옴표·역슬래시·개행)에만 존재 | 유지 — C14 성립 |
| 로그 파일이 2단계(생성→chmod)로 만들어진다 | `run-delegation.sh:242` `: > "$LOG_FILE"` → `243` `chmod 600` | 유지 — C25 성립 |
| 프리플라이트가 여전히 argv 인접 토큰으로 관리 여부를 추측한다 | `run-delegation.sh:130~138` awk (`$i == "--attach" && $(i+1) ~ /^https?:/`) | 유지 — C18 성립 |
| ctl 액션 디스패치는 `status`/`start`/`ensure`/`stop` 4종 | `opencode-serve-ctl.sh:143~164` | 유지 — 신규 액션은 검증 뒤 dispatch 에 추가 |

### 🔴 전파 실측에서 뒤집힌 전제 (2026-08-13, 오케스트레이터 직접)

| 전제 | 실측 | 판정 |
|---|---|---|
| 클라이언트는 서버 인증정보 없이도 attach 할 수 있다(2e 의 `unset` 이 안전하다) | 비밀번호 없이 attach 하면 `Error: Session not found` 로 즉사(rc=1). 대조: 있으면 rc=0 | **뒤집힘** — Task 2g 로 수정(attach 실행 라인에만 주입) |
| 세션의 `directory` 는 클라이언트의 `--dir` 를 반영한다 | **서버 자신의 cwd** 가 기록된다. `--dir` 는 에이전트·설정 로딩에만 반영 | **뒤집힘** — 세션 식별 방식 재설계 필요(Task 5 차단) |

→ 결과: **프로젝트 간 병렬 attach 는 현재 사용 불가.** 서버를 띄운 프로젝트 하나만 성공하고
나머지는 "세션 미개시" 로 오판되어 모델 체인을 소진한다(exit 5). `serve.env` 를 두지 않는 것이
현재 안전한 상태이며, 4개 프로젝트는 v3 스크립트를 갖되 standalone 폴백(구 동작)으로 돈다.

## Task 목록

| # | 제목 | 에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 1 | `opencode-serve-ctl.sh` 신설 (ensure/status/start/stop) | kit-scripts | heavy | **완료** (리뷰 3R) | a77af80·328a84b·ab0c4ce |
| 2 | `run-delegation.sh` v3 — attach 모드 + 프로젝트별 락 + 폴백 | kit-scripts | heavy | **커밋됨·수정 라운드 필요** (잔여 결함 a~e → `.tasks/task2b.md`) | 098c14f |
| 2b | **워치독 계층 재설계** — 세션식별·진행판정·abort 를 서버 API 기반으로 (🔴 B1~B7) | kit-scripts | heavy | **마감** — B1~B7 닫힘(리뷰 3종 확인), 후속 D1~D11 중 9건 폐쇄. 재위임 한도 소진으로 잔여 2건(D5 회귀테스트·D3 오보고)은 2c 이월(사용자 승인) | 1d3957e·1409ac7 |
| 2c | **판정·진단 축** — exit 7 오탐·형식·프리플라이트·폴백 사유 + 2b 이월분 (C1·C2·C3·C4·C9·C12·C13·C16) | kit-scripts | heavy | ✅ **완료** (리뷰 3종 통과, 🔴 0) | 04573d6·1e55a64 |
| 2d | **배선·권한 축** — ctl 심링크·`-f` 게이트·스핀락 PID·로그 권한·락 파일명 (C8·C6·C5·C10·C11·C19·C22) | kit-scripts | heavy | ✅ **커밋** (반려 1회 → 통과) · 리뷰 중 | c7fd42b |
| 2e | **서버 API 축** — curl 3중 복제를 ctl 액션으로 통합 + PW·PORT 검증 상속, 로그 원자 생성 (C7·C14·C25·C17) | kit-scripts | heavy | ✅ **완료** (위임 3라운드: 초기→반려→우회로 제거, 리뷰어 3종 재검수 전원 승인) | a866795 |
| 2h | **세션 식별 재설계** — 차분 탐색 → 명시적 생성(`POST /session?directory=`) + `--session` | kit-scripts | heavy | ✅ 완료 (반려 1회: init 스톨 무한대기) | `987ac67` |
| 2g | **실환경 회귀 수정** — attach 클라이언트에 비밀번호 주입 | kit-scripts | heavy | ✅ 완료 | 44ec8c1 |
| 2f | **프리플라이트 축** — 관리 판별을 argv 추측 → 부모 검증으로 교체 (C18·C21·C23·C24·C20) | kit-scripts | heavy | ✅ **완료** (위임 3라운드: 초기→부모 우회 반려→패턴 한정, 리뷰어 2종 승인) | da96c01 |
| 3 | 회귀 테스트 보강 — 상호배제 실검증(C28)·락 이름 정규화(C29)·umask 주입(C30) | **오케스트레이터 직접** | - | ✅ **완료** (변이 4종으로 비공허 확인) | 32bb9ab |
| 4 | 문서·스킬 갱신 (스킬 위임 직렬화 절·exit 표·PORTING·PITFALLS) | kit-docs | default | ✅ **완료** (재위임 1회: 워크트리 외부경로 거부로 산출물 0, code-reviewer 승인) | 1건 |
| 5 | 호스트 전파 | **오케스트레이터 직접** | - | ✅ **완료** — 4개 프로젝트 동기화·전역 스킬 설치·`serve.env` 생성, 3개 프로젝트에서 실환경 검증 | - |

> Task 1·2는 kit-scripts가 자기 테스트 파일(`tests/test_serve_ctl.py`·`tests/test_run_delegation.py`)을
> 함께 작성한다 — 로스터상 tests/는 kit-tests 담당이지만 TDD(RED 선행)를 task 안에서 완결하기 위한
> 의도적 예외. Task 3(kit-tests)이 시나리오를 보강하고 python-reviewer가 테스트 품질을 검수한다.

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| v3 폴백 경로 (serve 다운) | 폴백이 전역 락 없이 단독 실행 → 업스트림 DB 경합 재도입 | `test_run_delegation.py::test_standalone_fallback_acquires_global_lock` (Task 2) |
| 에이전트 미발견 | stderr 경고 폴백을 성공으로 오판 → 로스터 없는 기본 에이전트가 task 실행 | `test_run_delegation.py::test_agent_not_found_fails_fast` (Task 2) |
| 워치독 kill | 클라이언트만 죽고 서버 세션이 고아로 계속 실행(파일 계속 수정) | Task 2 실측 + `test_serve_ctl.py::test_stop_aborts_active_sessions` 또는 불가 사유·대체 검증 명시 |

## 전파 제약 누적

### Task 2f → 이후 (프리플라이트 계약, 2026-08-13 확정)
- "관리되는 프로세스" = **부모가 위임 래퍼**인 것. 부모 판정은 부모 행 `$4`(실행 파일)·`$5`(셸 호출 시 스크립트)의
  basename 만 보고 `^run-delegation(-v[0-9]+)?[.]sh$` 로 한정한다. 명령줄 뒤쪽 인자는 근거가 아니다.
- **PPID=1 고아·부모 미상은 fail-closed(exit 3)**. attach 플래그 파싱은 완전히 제거됐다.
- ⚠️ **전파 시 주의**: 이 판정은 `nohup "$OPENCODE_BIN" run` 이 래퍼의 **직계 자식**이라는 전제에 의존한다
  (nohup 은 exec 치환이라 중간 계층이 없다 — 리뷰어 실측). 스폰 방식에 `env`·`setsid`·추가 셸을 끼우면
  중간 프로세스 때문에 **정상 위임이 exit 3 으로 오탐**된다.
- 잔여(문서화된 수용): 부모를 이미 통제하는 주체는 자기 래퍼 이름을 패턴에 맞춰 가드를 무력화할 수 있다.
  PID/PPID 는 커널이 강제하므로 타인 프로세스의 부모를 사칭할 수는 없다 — 계정 경계를 넘지 않는 자해적 우회다.

### Task 2e → 이후 (ctl 신규 액션·로그·인증정보, 2026-08-13 확정)
- ctl 액션이 7종으로 확장: `{ensure|status|start|stop|sessions|session|abort}` (인자 여전히 정확히 1개).
  세션 ID는 플래그가 아니라 **환경변수 `OPENCODE_SERVE_ACTION_ID`** 로 준다(`[A-Za-z0-9_-]` 화이트리스트, 위반 시 exit 64).
- stdout 계약 추가: `sessions`=세션 목록 JSON 본문, `session`=단건 JSON 본문, `abort`=`aborted`.
  **2xx 가 아니면 본문을 출력하지 않고 exit 1** (fail-closed). → Task 5 전파 시 ctl 과 run-delegation 을 **반드시 함께** 복사할 것.
- 서버 API 호출은 ctl 단독 소유 — `run-delegation.sh` 에 basic-auth 문자열이 있으면 회귀다(`grep -c 'user = "opencode:'` → 0 유지).
- 로그 파일은 `install -m 600 /dev/null` 로 생성한다. `: >` + `chmod` 2단계로 되돌리면 TOCTOU 창이 재도입되고,
  `(umask 0177; : > ...)` 로 바꾸면 **기존 파일 권한을 교정하지 못한다**(둘 다 실측 확인).
- `OPENCODE_SERVER_PASSWORD` 는 존재 확인 직후 `unset` 한다 — 위임 워커 자식 프로세스에 상속되면 안 된다(동결 테스트가 고정).
- **테스트 소유권**: 이 페이즈의 회귀 테스트 6건은 오케스트레이터가 작성·동결했다.
  위임 라운드에서 `tests/` 수정은 금지다(단정 약화 재발 방지 — 이 페이즈에서 7회 실측된 패턴).


### Task 1 → 이후 (serve-ctl 인터페이스, 실측 확정)
- 호출: `bash scripts/opencode-serve-ctl.sh {ensure|status|start|stop}` (인자 정확히 1개)
- 환경 파일: `~/.config/opencode/serve.env` — `OPENCODE_SERVE_PORT`(숫자), `OPENCODE_SERVER_PASSWORD`
  - **권한 게이트**: group/other의 읽기·쓰기 비트가 하나라도 서면 exit 64. `ls` 출력 형식 미인식도 exit 64(fail-closed). → **Task 5는 `chmod 600` 필수**
  - **PW 문자 제약**: 따옴표·백슬래시·개행 불가 (curl config 주입 차단). → **Task 5 패스워드 생성 시 영숫자로 한정**
- exit: 0 정상 / 1 실패(status는 down도 1) / 64 사용법·환경 파일·권한·PW 문제
- 오버라이드(테스트용, 플래그 아닌 **환경변수**): `OPENCODE_SERVE_ENV_FILE`, `OPENCODE_SERVE_STATE_DIR`, `OPENCODE_SERVE_START_TIMEOUT`(30), `OPENCODE_SERVE_POLL_INTERVAL`(1)
- 상태 파일: `$STATE_DIR/serve.pid`·`serve.log`, 락 `opencode-serve.lock` — **ensure·start·stop 세 액션이 락 공유**
- 헬스: `GET /global/health` basic auth — **재구현 금지, ctl 스크립트 경유**
- stdout 계약: `up`/`down`/`started`/`stopped`
- 이관됨: `test_stop_aborts_active_sessions` → Task 2의 "클라이언트 kill 서버측 효과 실측"과 함께 처리

### Task 2 라운드에서 실측된 추가 결함 (다음 수정 라운드에 포함할 것)
1. **`scripts/opencode-serve-ctl.sh` 심링크 누락** — 이 저장소의 `scripts/`는 **파일별 심링크**
   디렉터리다(`scripts/X.sh -> ../core/scripts/X.sh`, git 추적). Task 1이 `core/scripts/`에만
   파일을 만들어 `bash scripts/run-delegation.sh` 실행 시 ctl을 못 찾고 **항상 standalone 폴백**한다
   (2026-08-12 실측: `No such file or directory` → `SERVE_FALLBACK`). 심링크 추가 필요.
   - 영향 범위는 **키트 자신(도그푸딩)만**이다. `lib/stamp.sh:30`이 `core/scripts` 트리를
     통째로 복사하므로 신규 프로젝트는 정상, 기존 4개 프로젝트는 실제 사본이라 Task 5가 복사한다.
2. **폴백 사유 오표기** — ctl 스크립트 부재인데 메시지가 "serve 기동 실패"로 나온다. 원인 구분 필요.

### 🔴 Task 2 반증 실측 (2026-08-12 21:13, 오케스트레이터 직접)
클라이언트 SIGTERM 후에도 **서버 세션은 계속 실행된다** — kill 30초 후 step2 파일 생성,
58초 후 서버 로그 `loop session.id=... step=5` + 새 LLM 스트림. 위임 에이전트가 코드 주석에
남긴 "서버가 세션 실행을 계속하지 않았다"는 주장은 **거짓**. 재현 스크립트:
`.orchestrate/killtest/repro-kill-effect.sh`. 대응: `POST /session/{id}/abort` (실측 확인된
엔드포인트) 를 워치독 kill 경로에 추가.

### 오케스트레이터 결정 — 출력 포맷 스펙 모순 해소 (2026-08-13)
Task 2 구현은 abort 용 sessionID 확보를 위해 `--format json` 을 택했고, 그 결과 `grep -a 'ERROR'`
전치 필터가 JSON 이벤트를 못 잡아 **FAIL_RE 모델 폴백·스톨 가드가 죽었다**(결함 d). 위 전제 실측대로
`GET /session` 이 `directory` 를 주므로 **텍스트 출력으로 되돌리고 sessionID 는 서버 API 차분으로
확보한다** — 프로젝트별 락이 같은 `--dir` 의 동시 위임을 직렬화하므로 차분이 모호해지지 않는다.
상세 지시는 `.tasks/task2b.md`.

> 이 페이즈에서 실측된 프로세스 함정은 `.tasks/task4.md` 말미로 이관했다 (인덱스 10KB 상한).

## 자동 결정 로그
- (없음 — 일반 모드)
