# Task 2: `run-delegation.sh` v3 — attach 모드 + 프로젝트별 락 + 폴백

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/run-delegation.sh` (개조), `tests/test_run_delegation.py` (신규)
- **선행**: Task 1 (`opencode-serve-ctl.sh ensure` 호출)
- **목표**: 위임을 serve+attach로 실행해 **프로젝트 간 병렬**을 허용한다. 같은 프로젝트 안은
  프로젝트별 락으로 직렬 유지. serve 불가 시 기존 v2 경로(전역 락 + 단독 실행)로 폴백.
- **재사용**: 개선 후 재사용 `core/scripts/run-delegation.sh` (호출부: 문서·스킬 다수가 인터페이스
  참조 — **CLI 인터페이스·기존 exit 코드 의미를 바꾸지 말 것**, 추가만 허용).
  모델 폴백 체인·FAIL_RE·`MODEL_USED=` 출력·프롬프트 파일 방식 전부 유지.

## 스펙

### 모드 결정
1. `bash "$(dirname "$0")/opencode-serve-ctl.sh" ensure` → 성공: **attach 모드**
2. 실패: **standalone 폴백** = 기존 v2 경로 그대로 (전역 락 + `opencode run` 단독).
   폴백 진입 시 `SERVE_FALLBACK: standalone 모드 (serve 기동 실패)` 를 출력 — 조용한 강등 금지.

### attach 모드
- **락**: 전역 락 대신 **프로젝트별 락** `~/.local/state/orchestrate/opencode-<slug>.lock`
  (slug = `basename $PWD` + 절대경로 해시 6자리 — basename 충돌 대비). 대기 로그는
  `LOCK_WAIT(project): ...` 로 전역과 구분. 타임아웃 30분 = exit 4 유지.
  **워크트리 주의**: 같은 프로젝트의 워크트리들은 basename이 다르다
  (`phase5-...` vs `dev-orchestrate-kit`). 프로젝트 동일성은 `git rev-parse --git-common-dir`
  기준으로 판정할 것 — 워크트리끼리 같은 락을 공유해야 한다 (venv·포트·docker 공유가 근거).
  git 밖이면 `$PWD` 기준.
- **실행**: `opencode run --attach "http://127.0.0.1:$PORT" --dir "$PWD" --agent "$AGENT"
  -m "$MODEL" "$(cat "$PROMPT_FILE")"` — 출력 포맷은 기존과 같은 default(텍스트) 유지
  (로그 가독성 = task-orchestrator·리뷰어가 읽는다). `OPENCODE_SERVER_PASSWORD` 는
  serve.env에서 주입 (클라이언트가 env로 읽음 — `run --help` 실측).
- **PREFLIGHT_UNMANAGED (exit 3) 판정 변경**: attach 모드에서는 로컬 `opencode run` 프로세스
  스캔을 하지 않는다 (다른 프로젝트의 병렬 위임이 정상 존재). standalone 폴백 경로에서만
  기존 판정 유지.
- **에이전트 미발견 감지 (신규, 실측 근거)**: 클라이언트 출력에서
  `agent "<이름>" not found` 패턴 발견 시 **즉시 kill + exit 7** (`AGENT_NOT_FOUND`).
  실측(2026-08-12): 이 경우 opencode는 실패하지 않고 기본 에이전트로 조용히 폴백하며 rc=0 —
  로스터 없는 에이전트가 task를 실행하는 최악의 침묵 오배정이다.
- **워치독 재설계 (실측 근거: `loop session.id` 는 attach에서 서버 로그에만 찍힘)**:
  - init: 로그 파일이 120초 내 비어 있지 않게 되는지 (기존 12×10초 루프 구조 유지)
  - 진행: **로그 파일 크기 증가** 기준 (`wc -c` 비교, 10초 주기). 텍스트 스트림이므로
    포맷 파싱 불필요. 90초 무증가 + 말미 ERROR + FAIL_RE 매치 → 기존 스톨 가드와 동일 처리.
- **모델 실패 판정**: 기존 `model_error_in_log`(FAIL_RE) + rc≠0 유지. 미등록 모델 rc=1 실측 확인.

### 🔴 반드시 실측·문서화: 클라이언트 kill 의 서버측 효과
워치독이 클라이언트를 kill 했을 때 **서버 세션이 함께 중단되는지** 실측하라 (미검증 전제).
중단되지 않으면: 서버 API로 세션 중단(`/doc` 에서 abort 엔드포인트 확인, basic auth)을
워치독 kill 경로에 추가할 것. 실측 방법·결과를 스크립트 주석과 보고에 남겨라.
**고아 세션이 파일을 계속 수정하는 상태**가 최악의 결과다 — 이 확인 없이 완료 보고 금지.

- **실패 테스트** (PATH 스텁 방식, 실제 serve 기동 금지):
  - `::test_attach_mode_uses_project_lock` — attach 모드에서 전역 락 파일을 잡지 않고 프로젝트 락을 잡는다
  - `::test_standalone_fallback_acquires_global_lock` — serve-ctl 스텁이 실패하면 전역 락 + 단독 실행 (리뷰 예상 지점 1)
  - `::test_agent_not_found_fails_fast` — 스텁이 폴백 경고를 출력하면 exit 7 (리뷰 예상 지점 2)
  - `::test_worktrees_share_project_lock` — 같은 저장소의 두 워크트리가 같은 락 파일을 쓴다
  - `::test_model_fallback_chain_preserved` — FAIL_RE 매치 시 다음 모델 재시도 (v2 회귀 방지)

## 필수 규칙
- bash 3.2 호환 · 기존 exit 코드(0/2/3/4/5/64/66) 의미 불변, 신규는 7만 추가
- 금지사항 3종(timeout 래핑·파이프 수신·프롬프트 인라인) 주석 유지
- 테스트는 임시 디렉터리 주입 (실제 `~/.local/state` 오염 금지)

## 완료 조건
- `python3 -m unittest tests.test_run_delegation -v` 전건 PASS (RED 먼저)
- `bash -n core/scripts/run-delegation.sh` 통과
- kill→서버측 효과 실측 결과가 보고에 포함

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
라이브 위임이 쓰는 실제 전역 락·실제 serve 를 테스트에서 건드리지 말 것 ·
작업 전 skill 툴로 `karpathy-guidelines` 로드

## 보고 형식
수정·생성 파일 목록 / RED·GREEN 출력 전문 / kill 실측 결과와 대응 /
v2 대비 변경점 표 (모드·락·워치독·exit) / 새 파일 사유
