# Task 2: docs-index 탈하드코딩 + phase-tools init 기본값

- **에이전트**: kit-scripts (task-orchestrator 경유)
- **모델**: heavy
- **대상 파일**: `core/scripts/docs-index.py`, `core/scripts/phase-tools.py`,
  `tests/test_docs_index.py`, `tests/test_phase_tools.py`
- **선행**: Task 1 (docs/phases가 실존해야 통합 테스트가 실경로로 돈다)
- **목표**: ① `docs-index.py`의 `default_docs_dir()`가 `DOCs` 하드코딩 대신
  **저장소 루트의 `docs/phases`를 우선, 없으면 `DOCs` 폴백**으로 해석하고,
  `--docs-dir <경로>` 인자로 명시 지정을 허용한다. 둘 다 없으면 명확한 에러로 종료(침묵 금지).
  INDEX 제목 등 출력 문구의 `DOCs` 표기도 실제 사용 경로를 따르게 한다.
  ② `phase-tools.py`의 `init` 서브커맨드 `--docs-dir` 기본값과 usage 문구를 `docs/phases`로 바꾼다
  (기존 레지스트리 값 해석 로직은 변경 금지 — 값은 병합 후 전환).
- **재사용**: 개선 후 재사용 `core/scripts/docs-index.py:default_docs_dir` (호출부 해당 파일 내부뿐).
  레지스트리 파싱을 새로 추가하지 말 것 — 프레시 클론 단독 동작이 요구사항.
- **실패 테스트** (RED 먼저 작성·실패 확인):
  - `tests/test_docs_index.py::test_docs_dir_prefers_docs_phases` — 임시 저장소에 docs/phases만 있을 때 그쪽에 INDEX 생성
  - `tests/test_docs_index.py::test_docs_dir_falls_back_to_DOCs` — DOCs만 있을 때 기존 동작 유지
  - `tests/test_phase_tools.py`의 init 기본값 단정 갱신
- **필독 스킬**: 없음
- **필수 규칙**:
  - `scripts/*`는 `core/scripts/*` 심링크 — **core/ 원본만** 수정
  - 테스트는 임시 디렉터리에서 — 실제 저장소·홈 오염 금지
  - `tests/test_dashboard_mounts.py`·`test_install_dashboard_container.py`의 `DOCs` 픽스처 값은
    레지스트리 임의 값 예시이므로 **의미가 깨지는 경우에만** 갱신
- **완료 조건**: `python3 -m unittest discover -s tests -v` 전체 통과 +
  워크트리 루트에서 `python3 scripts/docs-index.py` 실행 시 `docs/phases/INDEX.md` 재생성 확인
