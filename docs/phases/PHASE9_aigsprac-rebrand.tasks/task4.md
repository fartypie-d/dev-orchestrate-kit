# Task 4: docs/WORKFLOW.md·WORKFLOW.ko.md 개칭

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `docs/WORKFLOW.md`, `docs/WORKFLOW.ko.md` (2개 — 이 외 수정 금지)
- **선행**: Task 0
- **목표**: 워크플로우 문서 속 제품명(`## 06` 절 제목, `<img alt>` 문구 등 각 2곳)을
  `aigsprac`으로 바꾼다.
- **재사용**: 없음 — 명칭 치환만
- **실패 테스트**: 불가 — 순수 문서 치환 (대체 검증: 완료 조건 grep + 이미지 경로 실재 확인 + 리뷰어)
- **필수 규칙**:
  - `assets/fig-kit*.svg` 이미지 참조 경로는 변경하지 않는다 (파일명 유지 — Task 5는
    svg 내부 텍스트만 바꾼다).
  - "v2" 등 버전 표기·문서 구조는 유지.
- **금지**: 절 재작성, 대상 외 파일 수정, `tests/` 수정, `git commit`.
- **완료 조건**:
  - `grep -c dev-orchestrate-kit docs/WORKFLOW.md docs/WORKFLOW.ko.md` → 모두 0
  - `grep -o 'assets/fig-kit[^"]*' docs/WORKFLOW.md docs/WORKFLOW.ko.md | sort -u` 의
    각 경로가 `ls docs/assets/`에 실재
