# HANDOFF — Phase 5 마감 (2026-08-13)

**페이즈 완료.** 프로젝트 간 병렬 위임이 실환경에서 작동한다.

## 최종 상태

- `serve.env` **생성됨**(`~/.config/opencode/serve.env`, 600, 비밀번호 영숫자 32자, 포트 4096).
- 4개 프로젝트(usage-dashboard·insane-cloak·비공개 2곳)에 `run-delegation.sh`(v3)+
  `opencode-serve-ctl.sh` 동기화 완료(md5 일치 확인). 전역 스킬은 키트 어댑터 사본과 바이트 동일.
- 스위트 **200 tests OK** (flock 있는/없는 환경 양쪽).
- 실환경 검증: **3개 프로젝트**에서 성공. 서버를 다른 프로젝트에서 lazy 기동한 상태로
  키트·usage-dashboard 위임이 각자 세션을 만들어 정상 완료 — **서버 cwd 와 무관**함을 확인.
  두 프로젝트 동시 실행 시 락이 프로젝트별로 분리되고 `LOCK_WAIT` 가 발생하지 않음.

## 운영 메모

- **킬 스위치**: 이상 시 `bash scripts/opencode-serve-ctl.sh stop` → `rm ~/.config/opencode/serve.env`.
  이 순서를 지킬 것(반대로 하면 ctl 이 환경 파일을 못 읽어 고아 서버가 남는다 — PITFALLS 19).
  serve.env 가 없으면 전 프로젝트가 검증된 standalone 폴백(전역 락)으로 돌아간다.
- **관찰 지표**: `LOCK_WAIT(project)` 가 보이면 같은 프로젝트 직렬화(정상), `LOCK_WAIT` 는 폴백 상태다.
  `SERVE_FALLBACK` 이 자주 보이면 serve 기동 실패를 의심할 것. 병렬이 늘면 429 압력이 커진다.
- **미검증**: macOS 경로(BSD `install`, 비flock 스핀락)는 이 리눅스 호스트에서 실행되지 않는다.
  로컬 맥에서 `install.sh` 를 돌릴 때 1회 확인할 것.
- linger 미활성(사용자 결정) — 재부팅 후엔 첫 위임이 serve 를 lazy 기동한다.

## 남은 정리

- 3개 프로젝트(usage-dashboard·비공개 2곳)에 **스크립트 변경이 미커밋**으로 남아 있다.
  각 프로젝트 세션에서 커밋할 것. insane-cloak 은 `scripts/` 가 `.git/info/exclude` 라 추적되지 않는다.
- 이 워크트리·브랜치 정리는 메인 체크아웃에서 `bash scripts/phase-close.sh 5` 로 하거나,
  다음 세션의 SessionStart 재니터가 병합·clean 상태를 확인해 자동 정리한다.
