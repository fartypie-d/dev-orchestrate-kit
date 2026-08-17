# Task 1: `opencode-serve-ctl.sh` 신설

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/opencode-serve-ctl.sh` (신규), `tests/test_serve_ctl.py` (신규)
- **선행**: 없음
- **목표**: opencode serve 데몬의 ensure(없으면 기동)·status·start·stop을 파일 하나로 고정한다.
  v3 래퍼와 systemd 유닛 양쪽이 이 스크립트를 공유한다.
- **재사용**: 개선 후 재사용 아님 — 신규. 락 패턴은 `core/scripts/run-delegation.sh:72-92`의
  flock/mkdir 폴백 패턴을 그대로 따를 것 (bash 3.2 호환, macOS flock 부재 대응).
  헬스체크 curl 패턴은 같은 파일 `:124` (antigravity 프록시 체크) 참조.
- **실패 테스트**: `tests/test_serve_ctl.py::test_ensure_starts_server_when_down`,
  `::test_ensure_noop_when_healthy`, `::test_status_reports_down_without_password_leak`,
  `::test_start_fails_without_password` — PATH 앞에 가짜 `opencode`·가짜 `curl` 스텁을 놓는
  기존 키트 테스트 방식(`tests/_install_helpers.py` 참조)으로 실행 없이 검증.

## 스펙

```
사용법: bash scripts/opencode-serve-ctl.sh {ensure|status|start|stop}
환경 파일: ~/.config/opencode/serve.env  (OPENCODE_SERVE_PORT, OPENCODE_SERVER_PASSWORD)
exit: 0 정상 / 1 실패 / 64 사용법·환경 파일 문제
```

- `ensure`: 헬스 OK → 즉시 0. 다운 → 기동 시도 → 30초 내 헬스 OK 대기 → 0, 실패 시 1.
  동시 ensure 경합은 run-delegation v2의 flock/mkdir 패턴으로 원자화.
- `start`: `setsid nohup opencode serve --port $PORT` (로그 `~/.local/state/orchestrate/serve.log`,
  PID 파일 `~/.local/state/orchestrate/serve.pid`). **`OPENCODE_SERVER_PASSWORD` 미설정이면
  기동 거부** (exit 64) — 실측: 미설정 시 무인증 서버가 된다.
- `status`: 헬스 엔드포인트 `GET /global/health` (basic auth `opencode:$OPENCODE_SERVER_PASSWORD`,
  실측 2026-08-12: noauth=401/auth=200). 출력에 **패스워드를 절대 노출하지 말 것** (curl -u 를
  ps에서 가리는 방법 포함 — `curl -u "opencode:$PW"` 는 ps에 노출된다. `--config -` 또는
  netrc-file 방식을 쓸 것).
- `stop`: PID 파일 기반 종료. PID 파일이 스테일이면(프로세스 없음) 정리만 하고 0.
  **활성 세션이 있으면 경고를 출력**하고 종료는 진행 (호출자 판단).

## 필수 규칙
- bash 3.2 호환 (mapfile·연관배열 금지 — 키트 이식성 원칙, `run-delegation.sh:3` 참조)
- `serve.env`가 없으면 명확한 에러 메시지 + exit 64 (조용한 기본값 금지 — 패스워드는 기본값이 없다)
- silent fallback 금지 — 기동 실패 시 serve.log tail을 stderr로 보여줄 것

## 완료 조건
- `python3 -m unittest tests.test_serve_ctl -v` 전건 PASS (RED 출력 먼저 첨부)
- `bash -n core/scripts/opencode-serve-ctl.sh` 통과

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
실제 `~/.config`·`~/.local` 을 테스트에서 건드리지 말 것 (임시 디렉터리 주입 — `--state-dir`·
`--env-file` 오버라이드 플래그 또는 환경변수 주입을 스펙에 포함할 것) ·
작업 전 skill 툴로 `karpathy-guidelines` 로드

## 보고 형식
수정·생성 파일 목록 / RED·GREEN 출력 전문 / 패스워드 비노출 방법 설명 /
지시서에 없는 새 파일을 만들었으면 이유
