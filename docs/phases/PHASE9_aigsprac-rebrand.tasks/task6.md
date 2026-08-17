# Task 6: adapters onboard 스킬·프롬프트 개칭

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `adapters/claude/global/skills/orchestrate-onboard/SKILL.md`,
  `adapters/codex/global/prompts/orchestrate-onboard.md` (2개 — 이 외 수정 금지)
- **선행**: Task 0
- **목표**: 온보딩 안내 문구 속 제품명(각 1곳 — "…가 없습니다. dev-orchestrate-kit 의
  `./install.sh` 를 먼저 실행…" 류)을 `aigsprac`으로 바꾼다.
- **재사용**: 없음 — 명칭 치환만
- **실패 테스트**: 불가 — 안내 문구 치환 (대체 검증: 완료 조건 grep + 리뷰어)
- **필수 규칙**: 안내 문구의 명령(`./install.sh`, `./install.sh --codex`)과 경로는 불변.
  이 파일들은 설치 시 전역으로 복사되는 어댑터 원본이다 — 문구 외 지시 내용을 바꾸면 반려.
- **금지**: 스킬 로직·frontmatter 변경, 대상 외 파일 수정, `tests/` 수정, `git commit`.
- **완료 조건**:
  - `grep -rc dev-orchestrate-kit adapters/` → 모든 파일 0
  - `git diff --stat` 이 2파일 ±2라인 내외만 표시
