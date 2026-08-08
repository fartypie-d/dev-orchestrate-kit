# orchestrate-onboard (codex)

## 0단계: 모델 확인 — 미달이면 중단

이 명령은 프로젝트 전체를 읽고 설계한다. **설치본에서 선택 가능한 최상위 모델 +
`model_reasoning_effort = "high"` 이상이 아니면 진행하지 말 것.**

미달이면 다음만 답하고 종료한다:

> 이 명령은 가장 똑똑한 모델이 필요합니다. `~/.codex/config.toml` 에서 최상위 모델과
> `model_reasoning_effort = "high"` 를 설정한 뒤 다시 실행해 주세요.

## 1단계: 절차 본문을 읽는다

`~/.config/orchestrate/ONBOARD-PROCEDURE.md` 를 읽고 1~7 단계를 순서대로 수행한다.
절차의 단일 소스는 그 파일이다.

파일이 없으면 `dev-orchestrate-kit` 의 `./install.sh --codex` 를 먼저 실행하도록 안내하고 종료한다.

## 2단계: 절차 수행 시 codex 전용 사항

- **4단계(가드 등급)는 건너뛴다** — bash-guard 훅은 claude 전용이다. 대신 조작 금지 컨테이너
  목록을 `.codex/AGENTS.md` 의 "인프라 주의" 절에 **지침으로** 기록한다(강제되지 않음을 명시).
- 5단계 스킬 생성 위치는 `.agents/skills/<name>/` 이며 `SKILL.md` 와 `agents/openai.yaml` 을 함께 만든다.
- 6단계 검증에서 `hook-selfcheck.sh` 는 생략하고, `opencode agent list` 와 로스터 [TODO] 0건만 확인한다.
- 사용자 승인이 필요한 지점(5단계 스킬 목록)에서는 반드시 멈추고 확인한다.
