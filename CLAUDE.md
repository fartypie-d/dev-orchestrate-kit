# dev-orchestrate-kit — Claude 오케스트레이터 가이드

## 역할

이 프로젝트에서 claude는 **오케스트레이터**다.

- 기획안·작업 지시서 작성, 작업 분해(플랜 수립)를 담당한다.
- 오케스트레이션 절차는 **`/orchestrate` 스킬**(전역, `~/.claude/skills/orchestrate/`)을 따른다:
  인터뷰 → task 세분화 → `scripts/run-delegation.sh` 위임 → 도메인 리뷰어 검수.
- 에이전트 로스터·검증 명령: **`.claude/orchestrate.md`** (에이전트 정의는 `.opencode/agent/*.md`)
- 소스 코드는 직접 수정하지 않는다 — 위임한다. 직접 수정 가능: `DOCs/`, `.claude/`.

## 프로젝트 개요

오케스트레이터(claude/codex) → opencode 위임 개발환경을 어떤 머신에든 재현하는 부트스트랩 키트.
`core/`(하네스 무관: 스크립트·opencode 설정·프로젝트 템플릿) + `adapters/<하네스>/`(스킬·훅·설정) +
`containers/`(브라우저 CDP·antigravity 프록시) 구조. 기술 스택: bash 3.2 호환 셸 스크립트,
python3 unittest, jq, docker compose. 서비스 포트 없음(설치 키트).
이 저장소 자신이 키트의 첫 사용자다(도그푸딩) — `scripts/*`는 `core/scripts/*` 심링크.

## 검증 명령 (위임 결과 검수 시 필수)

```bash
python3 -m unittest discover -s tests -v   # 저장소 루트에서 (python3는 PATH에 있음)
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh   # bash 문법
bash scripts/hook-selfcheck.sh             # 훅 자가진단 (HOOK_SELFCHECK_PASS 기대)
```

## 브랜치 규칙

- 기본 브랜치 `main` — 직접 push 금지. 작업은 `feat/*`·`fix/*` 브랜치에서 진행 후 병합한다.

## 이 저장소의 함정 (반복 금지)

> 실측으로 확인된 함정만 남긴다. 페이즈 중 새 함정이 실측되면 완료 보고 때 여기 append한다.
> (형식: 무엇을 하면 → 무엇이 죽는지 → 실측 날짜)

- **`pgrep -f`로 위임 프로세스를 폴링하지 말 것** — 감시 루프 자신의 명령줄이 패턴에 매칭되어
  무한 루프가 된다. `scripts/run-delegation.sh`(launch PID 대기)를 쓸 것.
- **`timeout N opencode run`으로 위임을 죽이지 말 것** — opencode 전역 세션 DB 트랜잭션이
  오염되어 다음 실행이 init에서 무한 대기하고 연쇄된다.
- **위임 프롬프트에 프로젝트 밖 절대경로를 "읽어라"고 쓰지 말 것** — opencode가
  `external_directory` 권한으로 차단하고 에이전트가 그 자리에서 포기한다. 외부 파일 내용은
  오케스트레이터가 읽어서 프롬프트에 인라인할 것.
- **`scripts/` 는 `core/scripts/` 로의 심링크다** — 작업용을 고치면 vendored 원본과 갈라진다.
  항상 `core/scripts/` 를 고칠 것.
- **설치 스크립트 테스트가 실제 홈을 오염시킬 수 있다** — `apply-plan-profile.sh` 는 기본값이
  `~/.claude/agents` 다. 테스트에서는 반드시 `--agents-dir`·`--settings` 주입 플래그를 쓸 것.
- **`__PROJECT__` 를 저장소 전역에서 일괄 치환하지 말 것** — `core/project-template/`·`docs/plans/`
  에는 플레이스홀더가 정당하게 존재한다. stamp 치환 범위를 넓히면 템플릿 원본이 클로버된다
  (2026-08-08 도그푸딩 실측 사고 — lib/stamp.sh 가 복사분만 치환하는 이유).

## 주의

- `~/.config/opencode/secrets.env`·`.env` 류는 커밋·외부 전송 금지. 키 이름만 로그에 남긴다.
- 라이브 인프라 조작 금지: `/opt/chrome-cdp` 컨테이너(다른 사용자의 CDP 세션이 살아 있다),
  실제 `~/.claude`·`~/.config` (테스트는 임시 디렉터리로).
