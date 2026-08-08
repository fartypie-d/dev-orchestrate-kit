---
name: orchestrate-onboard
description: Use when 프로젝트에 오케스트레이션 스캐폴드를 찍은 직후(new-project.sh·adopt-project.sh 실행 후), 또는 사용자가 "프로젝트 분석해서 로스터·에이전트·스킬 만들어줘"를 요청할 때. 스택을 실측해 .claude/orchestrate.md 로스터와 .opencode/agent/*.md 를 채우고 필요한 커스텀 스킬을 제안한다.
---

# orchestrate-onboard (claude)

## 0단계: 모델 확인 — 미달이면 중단

이 명령은 프로젝트 전체를 읽고 설계한다. **opus 이상(fable 포함)이 아니면 진행하지 말 것.**

현재 모델이 미달이면 다음만 답하고 종료한다:

> 이 명령은 가장 똑똑한 모델이 필요합니다. `/model` 로 opus 이상으로 전환한 뒤 다시 실행해 주세요.

## 1단계: 절차 본문을 읽는다

`~/.config/orchestrate/ONBOARD-PROCEDURE.md` 를 Read 로 읽고, 거기 적힌 1~7 단계를 순서대로 수행한다.
절차의 단일 소스는 그 파일이다 — 이 스킬에 절차를 복제하지 않는다.

파일이 없으면 키트 설치가 안 된 것이다. 다음을 안내하고 종료한다:

> `~/.config/orchestrate/ONBOARD-PROCEDURE.md` 가 없습니다. dev-orchestrate-kit 의 `./install.sh` 를 먼저 실행해 주세요.

## 2단계: 절차 수행 시 claude 전용 사항

- 4단계(가드 등급)는 이 하네스에서 **수행한다** — `.claude/hooks/bash-guard.sh` 가 실제로 동작한다.
- 5단계 스킬 생성 위치는 `.claude/skills/<name>/SKILL.md` 다.
- 각 단계를 TodoWrite 항목으로 만들어 진행 상황을 보이게 한다.
- 사용자 승인이 필요한 지점(4단계 가드 등급, 5단계 스킬 목록)에서는 **반드시 멈추고 확인**한다.
