# Task 2: CLAUDE.md·AGENTS.md·.claude/orchestrate.md 개칭

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `CLAUDE.md`, `AGENTS.md`, `.claude/orchestrate.md` (3개 — 이 외 수정 금지)
- **선행**: Task 0
- **목표**: 세 운영 문서의 제품명 표기를 `aigsprac`으로 바꾼다. 내용·규칙은 일절 변경하지 않는다.
- **재사용**: 없음 — 명칭 치환만, 신규 코드 없음
- **실패 테스트**: 불가 — 순수 문서 치환 (대체 검증: 아래 완료 조건 grep + 리뷰어 검수)
- **필수 규칙**:
  - 치환 지점 실측 4곳: `CLAUDE.md:1`(제목), `CLAUDE.md:15`(프로젝트 확인 가드 문구),
    `AGENTS.md:1`(제목), `.claude/orchestrate.md:1`(제목). 이 4곳 외에는 손대지 않는다.
  - CLAUDE.md:15 가드 문구는 "이 프로젝트(aigsprac)" 형태로 — 가드 의미 보존.
  - 표기는 소문자 `aigsprac`.
- **금지**: 문장 재작성·규칙 추가·포맷 변경, 대상 외 파일 수정, `tests/` 수정, `git commit`.
- **완료 조건**:
  - `grep -c dev-orchestrate-kit CLAUDE.md AGENTS.md .claude/orchestrate.md` → 모두 0
  - `git diff --stat` 이 3파일·4라인 내외의 변경만 표시
