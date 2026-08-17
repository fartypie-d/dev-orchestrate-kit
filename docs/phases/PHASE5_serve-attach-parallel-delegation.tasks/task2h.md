# Task 2h: 세션 식별을 차분 탐색 → **명시적 생성**으로 교체

- **에이전트**: kit-scripts
- **모델**: heavy (⚠️ 위임 경로의 핵심 — 깨지면 전 프로젝트 위임이 멈춘다)
- **대상 파일**: `core/scripts/opencode-serve-ctl.sh`, `core/scripts/run-delegation.sh`
- **선행**: 없음 (2g 커밋 `44ec8c1` 기준)
- **재사용**: 개선 후 재사용 — ctl 의 `server_request()` 헬퍼와 검증 경로를 그대로 쓴다. 신규 스크립트 금지.

## 왜 (전제 뒤집힘 — 실측 2026-08-13)

서버는 세션의 `directory` 를 **클라이언트의 `--dir` 가 아니라 서버 자신의 cwd** 로 기록한다.
그래서 v3 의 식별 방식("기동 전후 세션 ID 집합 차분 + `directory` 정확 일치")은 **서버를 띄운
프로젝트에서만** 성공하고, 다른 프로젝트는 전부 "세션 미개시"로 오판되어 모델 체인을 소진한다
(전파 직후 usage-dashboard 에서 exit 5 실측). `DOCs/PITFALLS.md` 18번.

## 해법 (오케스트레이터가 실측으로 확정)

**세션을 먼저 만들고 그 ID 로 클라이언트를 붙인다.** 실측 근거:

    POST /session?directory=~/usage-dashboard   → {"id":"ses_...","directory":"~/usage-dashboard",...}
    GET  /session/<id>                                  → directory = ~/usage-dashboard  (정확히 기록됨)
    opencode run --attach <url> --session <id> --dir ~/usage-dashboard --agent dash-ui -m <모델> "..."
      → 서버 cwd 가 다른 프로젝트여도 정상 실행. 에이전트도 그 프로젝트 로스터에서 로드됨. rc=0

이 방식은 차분·디렉터리 일치 의존을 통째로 없앤다(C17 도 함께 소멸).

## 변경 1 — ctl 에 세션 생성 액션 추가

- 신규 액션 `create` : `POST /session?directory=<디렉터리>` 를 호출하고 **생성된 세션 ID 만 stdout 에** 출력.
- 디렉터리는 플래그가 아니라 **환경변수 `OPENCODE_SERVE_ACTION_DIR`** 로 받는다
  (ctl 은 인자가 정확히 1개라는 기존 계약 유지). 값 검증: 비어 있거나 `/` 로 시작하지 않으면 exit 64.
- 응답이 2xx 가 아니거나 JSON 에 `id` 가 없으면 **본문을 출력하지 말고 exit 1** (fail-closed).
- 기존 액션(`ensure|status|start|stop|sessions|session|abort`)의 계약을 바꾸지 말 것.
- PW·PORT 형식 검증은 지금처럼 dispatch 보다 먼저 적용돼야 한다.

## 변경 2 — `run-delegation.sh` 의 세션 식별 교체

- **모델 시도마다** 클라이언트 기동 **직전에** ctl `create` 로 세션을 만들고 `SESSION_ID` 에 담는다.
  출력 예: `SESSION_ID=<id> (서버에 생성)`.
- 클라이언트 실행에 **`--session "$SESSION_ID"`** 를 추가한다. `--dir` 는 그대로 유지한다.
- 생성 실패 시: attach 를 포기하고 **standalone 폴백**으로 그 실행을 진행한다
  (메시지 예: `SERVE_FALLBACK: standalone 모드 (서버 세션 생성 실패)`). exit 로 죽이지 말 것 —
  폴백은 검증된 경로다.
- **제거 대상**: `snapshot_server_sessions`·`discover_server_session`·`SESSION_SNAPSHOT`·`SNAPSHOT_OK`·
  `DISCOVER_FAILURES` 와 워치독 루프 안의 탐색 호출. 진행 판정은 `server_progress`(세션 단건 조회)만 쓴다.
- `abort_server_session`·exit 6 경로는 유지한다 — 이제 `SESSION_ID` 가 항상 확정돼 있으므로
  "ID 를 확보하지 못해 abort 못 함" 분기는 생성 실패(=standalone) 때만 의미가 있다.
- 모델 폴백으로 재시도할 때는 **새 세션을 만든다**(이전 세션 ID 재사용 금지).

## 🔴 `tests/` 는 읽기 전용

오케스트레이터가 계약을 고쳐 동결한다. 아래가 RED 이며 소스 수정만으로 GREEN 이 되어야 한다:

- `::test_attach_creates_session_before_launch` — ctl `create` 로 만든 ID 가 클라이언트 argv 의
  `--session` 에 그대로 전달된다
- `::test_attach_session_survives_server_cwd_mismatch` — 서버가 다른 디렉터리를 기록해도(스텁이
  엉뚱한 directory 를 돌려줘도) 위임이 성공한다 (PITFALLS 18 회귀 고정)
- `::test_session_creation_failure_falls_back_to_standalone` — 생성이 실패하면 standalone 으로
  진행하고 `--attach` 없이 클라이언트를 띄운다
- `::test_new_session_per_model_attempt` — 모델 폴백 시 이전 세션 ID 를 재사용하지 않는다

## 필수 규칙

- bash 3.2 호환 · CLI 인터페이스 불변 · exit 코드 의미 불변(0/2/3/4/5/6/7/64/66)
- ctl stdout 계약 유지 + `create` 는 **ID 한 줄만** 출력
- 워치독의 스톨·429 판정 로직은 그대로 (진행 판정 소스만 단순해진다)
- 경로는 상대 경로만 사용(워크트리 밖은 거부됨)

## 완료 조건 (출력 첨부)

- `python3 -m unittest discover -s tests -v` 전건 PASS
- `bash -n core/scripts/run-delegation.sh core/scripts/opencode-serve-ctl.sh`
- `grep -c "discover_server_session\|snapshot_server_sessions" core/scripts/run-delegation.sh` → **0**
- 변이 검증 2건 (`.orchestrate/mutation/<이름>/` 에 저장소 전체 사본, `/tmp` 금지, 수행 주체 명시):
  ① `--session` 전달을 제거하면 `test_attach_creates_session_before_launch` 가 죽는가
  ② 생성 실패 시 폴백을 제거하면 `test_session_creation_failure_falls_back_to_standalone` 이 죽는가
- flock 제거 환경(심링크 팜) 전건 통과

## 공통 금지

대상 파일 2개 외 수정 금지 (특히 `tests/`) · `git commit`/`git push` 금지 · docker 조작 · sudo 금지
