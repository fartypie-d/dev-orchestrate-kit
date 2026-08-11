# Task 4: phase-tools.py close 병합 판정 확장 (+`--target`)

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/phase-tools.py`, `tests/test_phase_tools.py`
- **선행**: 없음
- **목표**: `close` 서브커맨드의 병합 판정이 `merge_target()`(70행, origin/<db> 또는 로컬 <db>)
  하나만 봐서, feature 브랜치를 `feat/*` 통합 브랜치에 병합한 경우 "워크트리 미병합 — 보존"으로
  남는 문제(2026-08-11 Phase 1 마감 실측)를 고친다.
  ① close 경로의 병합 판정을 **후보 집합**으로 확장: `origin/<db>`(있으면) ∪ 로컬 `<db>`(있으면) ∪
  **메인 체크아웃의 현재 HEAD 브랜치** — 셋 중 하나의 조상이면 병합으로 인정.
  ② `close`에 `--target <ref>` 인자 추가 — 지정 시 후보 집합 대신 그 ref 하나로만 판정.
  ③ **janitor/audit 경로(326행 이하)는 변경 금지** — 브랜치 자동 삭제 판정 완화는 위험(이번 스코프 제외).
- **재사용**: 그대로 재사용 `core/scripts/phase-tools.py`:`is_merged`(65행)·`merge_target`(70행) —
  `is_merged`를 후보마다 호출하는 래퍼로 확장. 새 git 헬퍼 함수 금지 (기존 `git()` 사용).
- **실패 테스트**: `tests/test_phase_tools.py`에 추가 — 임시 저장소 픽스처에서 feature 브랜치를
  main이 아닌 통합 브랜치(예: `feat/integration`)에 병합하고 체크아웃한 상태로 `close` 실행 시
  워크트리·레지스트리가 정리되는지 단언 (현재 구현은 "미병합 — 보존"이므로 먼저 실패).
  `--target` 지정 케이스 1건 추가. 기존 테스트는 전부 그대로 통과해야 한다 (동작 하위 호환).
- **필독 스킬**: 없음
- **필수 규칙**:
  - detached HEAD(브랜치 아님)면 HEAD 후보는 조용히 제외 (에러 금지 — 기존 동작 유지).
  - 테스트 픽스처는 저장소 밖 임시 디렉터리, subprocess `timeout=` 필수.
  - 변이 검증: 사본에서 HEAD 후보를 빼고 신규 테스트 FAIL 확인.
- **완료 조건**: `python3 -m unittest discover -s tests -v` 전체 통과 (기존 test_phase_tools 포함) +
  변이 검증 증거.
