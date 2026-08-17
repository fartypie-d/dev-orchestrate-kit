# Task 4: 문서·스킬 갱신

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `adapters/claude/skills/orchestrate/SKILL.md`,
  `core/project-template/CLAUDE.md`, `DOCs/PITFALLS.md`
- **선행**: Task 2
- **목표**: v3 의미론(프로젝트별 락 + serve 병렬 + 폴백)을 스킬·템플릿·함정 문서에 반영한다.
- **재사용**: 그대로 재사용 — 기존 문서 구조. 새 문서 파일을 만들지 말 것.
- **실패 테스트**: 불가 (markdown) — 대체 검증: 언급하는 스크립트 경로·플래그·exit 코드가
  Task 1·2 산출물과 일치하는지 `grep` 대조 + 리뷰어 검수 (로스터 대체 검증 표 준거)

## 반영 내용

### `adapters/claude/skills/orchestrate/SKILL.md` — "병렬 세션" 절의 "위임 직렬화" 항목 재작성
- 새 의미론: 위임은 `run-delegation.sh` 경유(불변). **프로젝트가 다르면 병렬**(serve+attach),
  같은 프로젝트(워크트리 포함)는 프로젝트별 락으로 직렬.
- `LOCK_WAIT(project)` / `SERVE_FALLBACK` / exit 7 `AGENT_NOT_FOUND` 로그 의미 추가.
- 6-B exit 코드 표에 7 추가, 3(PREFLIGHT)은 "standalone 폴백 경로에서만" 주석.
- **왜 단독 병렬이 금지인지 근거를 한 줄로**: 업스트림 busy_timeout=0 → SQLITE_BUSY 침묵사
  (anomalyco/opencode#21215 · #15188, "고칠 계획 없음" 확정) — serve 경유만 병렬 허용.

### `core/project-template/CLAUDE.md` — 함정 절의 위임 관련 줄 갱신
- "timeout으로 위임을 죽이지 말 것" 항목 유지, "동시 위임 금지" 뉘앙스를
  "run-delegation.sh 밖에서 opencode run을 직접 띄우지 말 것"으로 정정.

### `DOCs/PITFALLS.md` append (실측 함정 3건, 형식: 무엇을 하면 → 무엇이 죽는지 → 실측 날짜)
1. 락 없는 동시 `opencode run` → SQLITE_BUSY로 세션이 토큰 0개·exit 0 침묵사 (업스트림 확정) → 2026-08-12
2. 없는 에이전트로 `opencode run` → 실패 대신 기본 에이전트 조용 폴백 rc=0 → 2026-08-12
3. attach 모드에서 `loop session.id` 워치독 → 서버 로그에만 찍혀 클라이언트 로그 감시가 침묵 → 2026-08-12

## 필수 규칙
- 문서가 참조하는 모든 경로·명령을 워크트리에서 실재 확인 (`ls`·`grep`) — 죽은 참조 금지
- CLAUDE.md 함정 절은 한 줄 인덱스 원칙 유지 (상세는 PITFALLS.md)

## 완료 조건
- `grep -n "opencode-serve-ctl\|AGENT_NOT_FOUND\|LOCK_WAIT(project)" adapters/claude/skills/orchestrate/SKILL.md` 매치
- 참조 대조 결과 (명령·출력) 첨부

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지

## 보고 형식
수정 파일 목록 / 절별 변경 요약 / 참조 대조 출력

---

### 프로세스 함정 (Task 4가 PITFALLS에 기록할 것)
- **테스트가 스텁 `opencode` 프로세스를 누수시켜 실제 위임을 막는다** (2026-08-13 실측).
  스톨 경로 테스트가 남긴 고아 스텁 2개(PPID=1, 임시 디렉터리·스크립트 파일마저 삭제됨)가
  5분 넘게 살아 다음 위임을 `PREFLIGHT_UNMANAGED`(exit 3)로 차단했다. 오케스트레이터가 수동 kill.
  → 테스트는 `tearDown`에서 자기가 띄운 스텁을 반드시 정리할 것. 회귀 확인법:
  전체 스위트를 2회 연속 돌린 뒤 `ps -eo pid,ppid,args | grep 'opencode run'` 가 비어야 한다.
- **위임 실행 스크립트를 고치는 페이즈에서는 그 스크립트로 위임하지 말 것** (2026-08-13).
  Task 2 의 exit 7 오탐은 로그 전체를 grep 하므로, `agent "..." not found` 문구가 들어간
  **수정 지시 프롬프트 자체**에 걸려 정상 위임을 죽이고 세션에 abort 를 날린다.
  → 커밋 이전 안정본을 `scripts/run-delegation-v2.sh` 로 임시 배치해 위임을 돌렸다(페이즈 마감 시 제거).
- **병렬 리뷰어가 세션 scratchpad를 공유해 서로의 픽스처를 덮어썼다** (2026-08-12 실측).
  두 리뷰어가 동시에 `scratchpad/repro/serve.env`를 사용 → 한쪽의 `start` 재현이 즉사 스텁인데도
  `started`/exit 0을 관측하는 **거짓 판정**이 나왔다(재실행으로 정정). 병렬 에이전트에게는
  고유 작업 디렉터리(`$$`·에이전트명 접미사)를 지시할 것.


- **위임 프롬프트에 "저장소 밖 사본에서 변이 검증"을 지시하지 말 것** (2026-08-13 실측).
  opencode 가 `/tmp` 접근을 `external_directory` 권한으로 자동 거부하고 에이전트가 그 자리에서 멈춘다.
  Task 2c 위임이 구현·테스트를 끝낸 뒤 변이 검증 단계에서 정확히 이렇게 중단됐다(같은 계열 사고가
  insane-cloak Task 4b·이 페이즈 Task 2 에서도 발생). 저장소 오염을 피하면서 허용되는 경로는
  **`.orchestrate/mutation/` 하위**다 (`.orchestrate/` 는 gitignore 대상).
  → 변이 검증은 위임에 맡기기보다 **task-orchestrator 검수자(Claude)가 직접** 하는 편이 확실하다.
