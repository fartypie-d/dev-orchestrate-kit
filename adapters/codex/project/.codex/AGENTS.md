# 이 저장소에서의 codex 오케스트레이션

루트 `AGENTS.md`(하네스 중립 규칙)를 보완한다. 절차 진입은 `~/.codex/prompts/orchestrate.md`.

## 로스터 경로

에이전트 로스터·리뷰어 매핑·검증 명령은 **`.claude/orchestrate.md`** 에 있다.
디렉터리 이름이 `.claude` 인 것은 호환성 때문이다 — claude 하네스와 같은 파일을 공유해
두 하네스가 하나의 로스터를 쓴다. codex 도 이 파일을 읽고 갱신한다.

## 위임

    bash scripts/run-delegation.sh <에이전트> <프롬프트파일> <로그경로> [default|heavy]

에이전트 정의는 `.opencode/agent/*.md`. 로스터에 없는 에이전트에는 위임하지 않는다.

## 리뷰

    bash scripts/codex-review.sh <BASE_REF>

🔴 Critical 이 있으면 exit 1 이며 커밋해서는 안 된다. 같은 에이전트에 `heavy` tier 로
재위임한다(최대 2회).

| 종료 코드 | 의미 |
|---:|---|
| 0 | 리뷰 수행 + `VERDICT: PASS` 명시 확인 |
| 1 | 리뷰 수행 + REJECT (`VERDICT: REJECT` 또는 🔴 발견) |
| 2 | 판정 불명 — 출력에 PASS/REJECT 어느 쪽도 없음 (수동 확인 필요) |
| 64 | 사용법 오류 / BASE_REF 검증 실패 |
| 69 | codex 바이너리 없음 |
| 70 | `codex exec` 자체 실패 (인프라 — 인증·네트워크) |

장시간 무응답이면 Ctrl-C 후 재실행한다.

`features.multi_agent` 를 켠 머신은 `.codex/agents/reviewer.toml` 역할로 대화 내 `/agent`
리뷰도 쓸 수 있다 — **실험 기능이므로 실패해도 위 스크립트 경로가 정답이다.**

## 훅이 없다는 점

claude 하네스의 `bash-guard.sh`·`post-edit-check.sh` 같은 **강제 훅이 codex 에는 없다.**
`.codex/config.toml` 의 sandbox·approval 설정은 bash-guard 와 등가가 아니다 —
`workspace-write` 는 워크스페이스 내부 파괴 명령(`rm -rf .`, `git reset --hard`)을 막지 못한다.
강제 차단이 필요한 명령은 사람이 직접 확인하라.

## 인프라 주의 (지침 — 강제되지 않음)

아래 컨테이너·리소스는 조작하지 않는다. 훅이 막아주지 않으므로 스스로 지켜야 한다.

- 조작 절대 금지: [온보딩 시 채울 것 — 터널·VPN·시크릿 저장소 등]
- restart 만 허용: [온보딩 시 채울 것 — 상태 보유 DB 등]
- 타 프로젝트 소유: [온보딩 시 채울 것]
