# dev-orchestrate-kit — 구현 에이전트 공통 규칙 (opencode instructions)

> 이 파일은 opencode 위임 에이전트에게 주입된다. 오케스트레이터(claude) 역할 정의를 여기 넣지 말 것 —
> 구현 에이전트에 모순 지시가 주입된다.

## 아키텍처

오케스트레이션 개발환경을 어떤 머신에든 재현하는 부트스트랩 키트. 하네스 무관 계층과
하네스 전용 계층이 분리되어 있다:

```
install.sh / new-project.sh / adopt-project.sh   # 진입점 (전역 설치 / 신규 stamp / 기존 stamp)
lib/stamp.sh          # 두 stamp 스크립트가 공유하는 스캐폴드 함수 (복사 로직 단일 소스)
core/                 # 하네스 무관 — claude/codex 단어를 모른다
  scripts/            # run-delegation.sh, phase-tools.py 등 (프로젝트에 stamp 되는 원본)
  opencode/           # opencode.json, 프로바이더 매핑·정책 시드, secrets.env.example
  onboard/            # /orchestrate-onboard 절차 본문 (단일 소스)
  project-template/   # AGENTS.md·로스터·.opencode/·DOCs 스켈레톤 (__PROJECT__ 플레이스홀더 포함)
adapters/
  claude/             # 전역 스킬 + 프로젝트 훅·settings·CLAUDE.md·에이전트
  codex/              # ~/.codex/prompts + .codex/ 프로젝트 계층
containers/           # browser(CDP+우회 API)·antigravity 프록시 compose 번들
tests/                # python unittest (스캐폴드·phase-tools)
```

의존 방향: 진입점 → `lib/stamp.sh` → `core/` + `adapters/<하네스>/`. core 는 adapters 를 참조하지 않는다.
이 저장소 자신도 키트의 사용자다(도그푸딩) — 루트의 `scripts/*` 는 `core/scripts/*` 심링크,
`.claude/orchestrate.md`·`.opencode/agent/` 는 자기 자신에게 stamp 한 산출물이다.

## 공통 규칙

- 지시받은 대상 파일 외 수정 금지. `git commit`·`git push`·docker 재시작 금지 (frontmatter permission으로도 차단됨).
- TDD: 실패 테스트 먼저. 테스트를 쓸 수 없으면 그 이유와 대체 검증을 보고에 명시.
- 기존 함수를 복사해 수정하지 말 것 — 확장이 필요하면 원본을 개선하고 호출부를 함께 갱신.
- 에러를 조용히 삼키지 말 것 (silent fallback 금지 — 부재 필드에 무경고 디폴트 대입 등).

## 검증

- 전체 테스트: `python3 -m unittest discover -s tests -v` (저장소 루트에서)
- bash 문법: `bash -n <파일>` (실행 없이 파싱만)
- 훅 자가진단: `bash scripts/hook-selfcheck.sh`
