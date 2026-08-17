# aigsprac — Claude 오케스트레이터 가이드

## 역할

이 프로젝트에서 claude는 **오케스트레이터**다.

- 기획안·작업 지시서 작성, 작업 분해(플랜 수립)를 담당한다.
- 오케스트레이션 절차는 **`/orchestrate` 스킬**(전역, `~/.claude/skills/orchestrate/`)을 따른다:
  인터뷰 → task 세분화 → `scripts/run-delegation.sh` 위임 → 도메인 리뷰어 검수.
- 에이전트 로스터·검증 명령: **`.claude/orchestrate.md`** (에이전트 정의는 `.opencode/agent/*.md`)
- 소스 코드는 직접 수정하지 않는다 — 위임한다. 직접 수정 가능: `docs/phases/`, `.claude/`.

## 세션 운영

- **프로젝트 확인 가드**: 요청이 이 프로젝트(aigsprac)와 무관해 보이면 — 다른 프로젝트의
  파일을 다뤄야 하면 — 진행하지 말고 AskUserQuestion으로 먼저 확인한다. 원격 클라이언트가 직전에
  쓰던 다른 프로젝트 세션에 붙은 채로 요청이 들어와 엉뚱한 프로젝트에서 페이즈가 수행된 실측
  사례가 있다 (2026-07-27).
- **페이즈 경계 = 세션 경계**: 페이즈 완료(지시서 아카이브 + 리뷰 문서 커밋) 후에는 세션을 정리하고,
  다음 페이즈는 **새 세션**으로 시작하도록 안내한다. 상태는 `docs/phases/PHASE*.md`와 `docs/phases/INDEX.md`에
  외부화되어 있으므로 새 세션 재시동 비용이 낮다. auto-compaction이 반복되는 장수 세션은 요약
  품질을 통제할 수 없고 비용도 크다 — 컴팩션에 의존하지 말고 명시적으로 끊을 것.
- **병렬 세션**: 같은 프로젝트에서 두 번째 세션이 동시에 작업해야 하면 메인 체크아웃이 아니라
  `.claude/worktrees/phase<N>-<slug>` 워크트리에서 진행한다 (전역 /orchestrate 스킬 "병렬 세션" 절).
  워크트리가 격리하는 건 파일뿐 — opencode 위임은 `scripts/run-delegation.sh`의 락이 직렬화한다
  (v3: serve attach 시 **프로젝트별 락** — 같은 프로젝트끼리만 직렬, 프로젝트 간 병렬.
  standalone 폴백 시에만 전역 락).

## 프로젝트 개요

오케스트레이터(claude/codex) → opencode 위임 개발환경을 어떤 머신에든 재현하는 부트스트랩 키트.
`core/`(하네스 무관: 스크립트·opencode 설정·프로젝트 템플릿) + `adapters/<하네스>/`(스킬·훅·설정) +
`containers/browser`(브라우저 CDP·우회 fetch — 서브모듈 insane-cloak) 구조. 기술 스택: bash 3.2 호환 셸 스크립트,
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
> (형식: 무엇을 하면 → 무엇이 죽는지 → 실측 날짜) — **상세는 `docs/phases/PITFALLS.md`**

- **`INSTALL_PARSE_ONLY` 로 메뉴 동작을 검증하지 말 것** — 메뉴 코드가 정의되기 전에 종료되므로
  기능을 통째로 지워도 통과하는 "항상 참" 테스트가 된다. 메뉴는 `INSTALL_SELFTEST_MENU` 로 검증하고,
  **새 테스트마다 저장소 밖 사본에서 변이 검증**을 할 것 (2026-08-10 Phase 1 에서 6회 실측).
- **커밋 메시지에 heredoc·명령치환을 쓰지 말 것** — bash-guard 가 차단한다.
  트리거 단어가 필요하면 단순 `-m "..."` 여러 개를 쓴다 (2026-08-10 실측 3회).
- **병렬 위임 중 `git add .`·`git commit -a` 금지** — 워크트리 작업 트리는 공유되므로 다른 task 의
  미완성 산출물이 함께 커밋된다. 경로를 명시할 것 (2026-08-10).
- **서브모듈을 init 한 워크트리는 phase-close 가 크래시한다** — `worktree remove` 가 rc=128 거부.
  병합 확인 후 `git worktree remove --force --force` 수동 제거 → close 재실행 (2026-08-11).
- **위임 에이전트에게 `/tmp` 에 쓰라고 하지 말 것** — `external_directory` 자동 거부로 런이
  보고 없이 종료된다. 변이·스크래치 사본은 `.orchestrate/mut<task>/`(gitignore)에 (2026-08-11).
- **RED 단계(`<N>a`) task 에 변이 검증을 요구하지 말 것** — 변이시킬 구현이 아직 없어
  항상 참인 검증이 된다. 변이 검증은 구현 task(`<N>b`)의 완료 조건에 (2026-08-11).

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
- **락 없이 `opencode run` 을 동시에 띄우면 토큰 0개·exit 0 으로 침묵사한다** — 위임은 반드시
  `scripts/run-delegation.sh` 경유 (PITFALLS 9).
- **없는 에이전트 이름은 실패가 아니라 기본 에이전트 조용 폴백(rc=0)이다** — 래퍼가 exit 7 로 끊는다 (PITFALLS 10).
- **위임 스크립트를 고치는 페이즈에서는 그 스크립트로 위임하지 말 것** — 안정본 사본을 얼려 쓴다 (PITFALLS 13).
- **회귀 테스트는 오케스트레이터가 작성·동결하고 위임의 `tests/` 수정을 금지한다** — 위임에 맡기면
  단정이 약화된다(같은 계열 7회 실측, PITFALLS 14).
- **변이 검증은 `.orchestrate/mutation/` 에 저장소 전체를 복사해서** — `/tmp` 는 거부되고,
  스크립트만 복사하면 테스트가 원본을 참조해 변이가 무효다 (PITFALLS 15).
- **워크트리 위임 프롬프트에는 상대 경로만 쓸 것** — 부모 체크아웃은 외부 디렉터리로 거부되고
  에이전트가 파일을 하나도 고치지 않은 채 `DONE` 으로 끝난다. 검수는 `git status` 부터 (PITFALLS 16).
- **마법사 메뉴에 항목을 추가하기 전에 기존 테스트의 번호 하드코딩을 grep 할 것** — 새 항목이
  기존 번호를 밀면 순수 회귀가 난다(8건 실측). 집합 소속을 `[ -z ]` 로 추론하는 가드도 함께
  깨진다 — `case ",$LIST," in *,이름,*)` 로 직접 검사 (PITFALLS 23, 2026-08-14).
- **컨테이너 실기동 테스트는 서브모듈이 초기화된 체크아웃을 전제한다** — 프레시 클론에서는
  먼저 `git submodule update --init containers/browser components/usage-dashboard`. 단 워크트리
  안에서 init 하면 phase-close 가 크래시한다(함정 7) — PITFALLS 24 (2026-08-14).
- **로컬 main 미푸시 상태에서 `phase-claim.sh` 를 실행하지 말 것** — 낡은 origin/main 에서
  분기돼 페이즈 도중 리베이스가 필요해진다. claim 직후 `git merge-base HEAD main` 확인 (PITFALLS 25, 2026-08-17).
- **`__PROJECT__` 를 저장소 전역에서 일괄 치환하지 말 것** — `core/project-template/`·`docs/plans/`
  에는 플레이스홀더가 정당하게 존재한다. stamp 치환 범위를 넓히면 템플릿 원본이 클로버된다
  (2026-08-08 도그푸딩 실측 사고 — lib/stamp.sh 가 복사분만 치환하는 이유).

## 주의

- `~/.config/opencode/secrets.env`·`.env` 류는 커밋·외부 전송 금지. 키 이름만 로그에 남긴다.
- 자기 소유가 아니거나 이미 운영 중인 라이브 CDP 컨테이너·세션은 조작 금지. 이 킷의
  `containers/browser` 번들을 본인이 직접 띄운 경우는 해당하지 않는다.
- 실제 `~/.claude`·`~/.config` 를 테스트에서 건드리지 말 것 (테스트는 임시 디렉터리로).
