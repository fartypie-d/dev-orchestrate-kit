# Task 1: `git mv DOCs docs/phases` (이력 보존)

- **실행 주체**: 메인 오케스트레이터 직접 (문서 도메인 — DOCs/는 직접 수정 허용 대상)
- **대상**: `DOCs/` 전체 → `docs/phases/` (워크트리 안에서)
- **선행**: 없음
- **목표**: 킷의 페이즈 문서 50개(지시서·INDEX·PITFALLS·reviews·archive·.tasks)가
  `docs/phases/` 하위로 rename 이력을 보존한 채 이동한다. 제품 문서(`docs/*.md` 등)와 병렬 공존.
- **재사용**: 해당 없음 (파일 이동)
- **실패 테스트**: 불가 (git 조작) — 대체 검증:
  - `git mv DOCs docs/phases` 후 `git status --short`가 전부 `R ` (rename) 인지
  - `git log --follow --oneline -3 -- docs/phases/PITFALLS.md` 가 이동 전 이력을 보여주는지
  - `[ ! -e DOCs ]` && `ls docs/phases/INDEX.md`
- **필수 규칙**:
  - 파일 **내용 수정 금지** — 이 task는 이동만 한다 (참조 갱신은 T2~T4)
  - 이동은 워크트리 안에서만. 메인 체크아웃·레지스트리는 건드리지 않는다
- **완료 조건**: 위 대체 검증 3종 통과 + 커밋 (`chore(docs): DOCs/ → docs/phases/ 이동 (이력 보존)`)
