# Task 4: README·WORKFLOW·PORTING 문서 갱신 (영/국문)

- **에이전트**: kit-docs (task-orchestrator 경유)
- **모델**: default
- **대상 파일**: `README.md`, `README.ko.md`, `docs/WORKFLOW.md`, `docs/WORKFLOW.ko.md`,
  `docs/PORTING.md`, `docs/assets/fig-kit*.svg` (다이어그램 내 `DOCs` 라벨)
- **선행**: Task 3
- **목표**: 사용자 노출 문서·다이어그램의 `DOCs` 표기를 `docs/phases`로 갱신하고,
  README의 대시보드 마운트 재생성 절차에 "레지스트리 `docs_dir` 전환(병합 후)" 한 줄을 추가한다.
  영문/국문 문서가 서로 어긋나지 않게 대응 유지.
- **재사용**: 해당 없음
- **실패 테스트**: 불가 (문서) — 대체 검증:
  - 문서에 적힌 경로 실재 확인 (`ls docs/phases/INDEX.md` 등 문서 내 경로 grep→ls)
  - 잔존 검증: 대상 파일들에서 `grep -n 'DOCs'` 빈 출력
- **필수 규칙**: SVG는 텍스트 라벨만 치환 — 구조 변경 금지. `docs/plans/`·`docs/specs/` 과거
  설계 문서 본문은 수정 금지 (역사 기록).
- **완료 조건**: 위 대체 검증 통과 + 리뷰어(code-reviewer) 검수
