# Task 3: 훅 제외 패턴 + 어댑터·템플릿·CLAUDE·AGENTS 참조 갱신

- **에이전트**: kit-scripts (task-orchestrator 경유)
- **모델**: heavy
- **대상 파일**: `.claude/hooks/post-edit-check.sh`,
  `adapters/claude/project/.claude/hooks/post-edit-check.sh`,
  `adapters/claude/global/skills/orchestrate/SKILL.md`,
  `adapters/codex/global/prompts/orchestrate.md`,
  `adapters/claude/project/CLAUDE.md`, `CLAUDE.md`, `AGENTS.md`,
  `core/project-template/` 내 `DOCs` 참조 (grep으로 실측 후)
- **선행**: Task 2
- **목표**: 살아있는 `DOCs` 경로 참조를 `docs/phases`로 일괄 갱신한다.
  훅 제외 패턴은 `*/DOCs/*` → **`*/docs/phases/*`** (── `*/docs/*` 광역 패턴 금지:
  docs 하위 코드 파일이 검사에서 빠진다). `hook-selfcheck.sh`에
  "docs/phases 하위 py는 검사 제외, docs/ 직하 py는 검사됨" 케이스를 추가한다.
- **재사용**: 해당 없음 (문자열 참조 갱신)
- **실패 테스트**: 불가 (셸 훅·마크다운) — 대체 검증:
  - `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS` (신규 케이스 포함)
  - `bash -n` 수정된 모든 .sh
  - 잔존 검증: `grep -rIln 'DOCs' --exclude-dir=.git --exclude-dir=docs --exclude-dir=.claude/worktrees .` 결과가
    **빈 출력** (docs/phases/ 내 과거 문서 본문은 제외 대상이므로 --exclude-dir=docs)
- **필수 규칙**:
  - `docs/phases/` 하위 과거 페이즈 문서의 **본문은 수정 금지**
  - `core/project-template/`의 `__PROJECT__` 플레이스홀더 일괄 치환 금지 (실측 사고 이력)
  - 심링크 원본(core/) 수정 원칙 동일
- **완료 조건**: 위 대체 검증 3종 통과 + `python3 -m unittest discover -s tests -v` 유지
