# /orchestrate-onboard 절차 (하네스 공통)

> 이 파일이 절차의 단일 소스다. claude 스킬과 codex 프롬프트는 이 파일을 읽는 얇은 래퍼일 뿐이다.
> 설치 위치: `~/.config/orchestrate/ONBOARD-PROCEDURE.md`

## 0. 모델 게이트 — 미달이면 여기서 중단한다

이 명령은 프로젝트 전체를 읽고 로스터·에이전트·스킬을 설계한다. **사용 가능한 가장 똑똑한
모델로 실행해야 한다.** 현재 모델을 확인하고, 미달이면 전환 방법을 안내한 뒤 **작업을 시작하지 말 것**.

- claude: opus 이상(fable 포함)이 아니면 → `/model` 로 전환 후 재실행하도록 안내하고 중단.
- codex: 설치본에서 선택 가능한 최상위 모델 + `model_reasoning_effort = "high"` 이상이
  아니면 → 설정 방법을 안내하고 중단.

## 1. 스택 감지 (실측만 — 추측 금지)

다음을 **파일을 읽어서** 확인한다. 없으면 "없음"으로 기록하고 넘어간다.

- 언어·프레임워크: 매니페스트(`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml` 등)
- 빌드·테스트·린트 명령: 매니페스트의 scripts 섹션, `Makefile`, CI 워크플로
- **러너의 절대경로**: `.venv/bin/pytest` 처럼 PATH 에 없을 수 있다 — bare 명령을 로스터에 쓰지 말 것
- 컨테이너: `docker-compose.yml`, `Dockerfile`, 실행 중이면 `docker ps`
- 디렉터리 경계: 최상위 디렉터리와 각각의 책임

## 2. 로스터 작성 — `.claude/orchestrate.md`

파일 안의 `[TODO]` 를 1단계 실측값으로 전부 채운다. 채울 표는 5개다:

1. 에이전트 로스터 (에이전트명 · 담당 디렉터리 · 위험도)
2. 리뷰어 매핑 (구현 에이전트 → ECC 리뷰어). **새 리뷰어를 만들기 전에 ECC 대응물을 먼저 확인**하고,
   프로젝트 리뷰어를 만들었다면 근거를 한 줄 남긴다.
3. TDD 게이트 (도메인 · 테스트 위치 · 러너 절대경로)
4. 도메인별 검증 명령
5. 커밋 scope · 프로젝트 주의사항

에이전트 분할 기준: **디렉터리·모듈 경계**를 따른다. 하나의 에이전트가 두 언어를 담당하면
리뷰어 매핑이 모호해지므로 나눈다.

## 3. opencode 에이전트 생성 — `.opencode/agent/*.md`

`_example.md` 를 규격으로 삼아 2단계 로스터의 에이전트마다 파일을 만든다. frontmatter 필수 필드:
`description`, `mode: primary`, `model`(수동 실행용 기본값), `temperature`, `permission.bash`.

`permission.bash` 의 deny 목록(`git commit*`, `git push*`, `docker *` 등)은 `_example.md` 에서
그대로 가져온다 — 위임 에이전트가 커밋·인프라를 건드리지 못하게 하는 안전선이다.

전부 만든 뒤 `_example.md` 를 삭제하고 로드를 확인한다:

    ~/.opencode/bin/opencode agent list

## 4. 가드 등급 채우기 (claude 하네스에만 해당)

`.claude/hooks/bash-guard.sh` 상단의 세 변수를 채운다. **`docker ps` 실측으로 후보를 만들고,
반드시 사용자 확인을 받은 뒤 기입한다** — 잘못 넣으면 정상 작업이 차단된다.

- `FORBIDDEN` — 조작 절대 금지 (터널·VPN·시크릿 저장소·공용 인프라 컨테이너)
- `RESTART_ONLY` — `restart` 만 허용, `stop`/`rm` 금지 (상태 보유 DB 등)
- `FOREIGN` — 타 프로젝트 컨테이너

값은 `|` 구분 정규식이다. 예: `FORBIDDEN='my-vpn|my-vault'`. 비우면 해당 규칙은 무시된다.

## 5. 스킬 갭 분석 → 제안 → 승인 → 생성

먼저 **이미 있는 것을 확인한다**: ECC 언어 룰(`~/.claude/rules/ecc/<언어>/`)과 ECC 스킬이
프로젝트 스택을 이미 커버하는지. 커버되면 스킬을 만들지 않는다.

커스텀 스킬 후보는 **프로젝트에만 있는 반복 절차**로 한정한다:
배포·릴리스 절차, 도메인 특유의 함정, 손이 많이 가는 반복 워크플로.

후보를 목록으로 **제안하고 사용자 승인을 받는다**. 승인된 것만 생성한다:

- claude: `.claude/skills/<name>/SKILL.md`
- codex: `.agents/skills/<name>/SKILL.md` + `.agents/skills/<name>/agents/openai.yaml` (ECC 패턴)

## 6. 검증

- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS` (claude 하네스)
- `~/.opencode/bin/opencode agent list` → 2단계 로스터의 에이전트가 전부 보이는지
- `grep -c '\[TODO' .claude/orchestrate.md` → `0`

## 7. 온보딩 보고서

마지막 메시지에 다음을 담는다:

- 감지된 스택 (언어·프레임워크·러너 절대경로)
- 생성·수정한 파일 목록
- 생성한 에이전트와 담당 범위
- 제안했으나 사용자가 거절한 스킬 (있으면)
- 남은 수동 단계 (secrets 입력, 구독 로그인 등)
