# dev-orchestrate-kit v2 — 하네스 어댑터 재구성 설계

날짜: 2026-08-07
상태: 설계 승인 대기

## 목표

팀원들이 이 호스트의 오케스트레이션 워크플로우(감독 하네스 → opencode 위임 → 리뷰 → 게이트 커밋)를
자기 머신에서 재현할 수 있게 한다. 이번 개편의 5개 축:

1. **두 진입 경로** — 신규 프로젝트(`new-project.sh`) / 기존 프로젝트(`adopt-project.sh`)
2. **하네스 어댑터** — claude + opencode / codex + opencode 조합 지원
3. **`/orchestrate-onboard`** — 프로젝트 분석·로스터 작성·커스텀 스킬 생성 명령 (최상위 모델 강제)
4. **컨테이너 계층** — antigravity-manager, cloakbrowser CDP + insane-api 번들
5. **모델 설정 자격증명 주도 생성** — 가진 인증 수단(키·구독)을 묻고 체인 생성 후 실측 검증 (§5-1)

## 확정된 결정

| 결정 | 선택 | 근거 |
|---|---|---|
| 전체 구조 | core + adapters/ 재구성 | 사용자 선택. 하네스 추가가 구조적으로 명확해짐 |
| 로스터 경로 | `.claude/orchestrate.md` 유지 | 라이브 프로젝트·스킬 참조와 호환. codex는 `.codex/AGENTS.md`가 이 경로를 참조 |
| codex 리뷰 | codex 자체 리뷰 | 사용자 선택. 아래 "codex 어댑터" 참조 — 실험 플래그 리스크는 `codex exec` 폴백으로 흡수 |
| antigravity 바인딩 | 127.0.0.1 기본 | 무인증 프록시를 LAN에 열지 않음. 필요 시 compose에서 변경 |
| 온보딩 스킬 생성 | 제안 → 승인 → 생성 | YAGNI. 스킬 난립 방지 |
| 컨테이너 배포 | 키트에 번들 (insane-api 소스 vendored) | /opt/chrome-cdp는 276K 자급자족 소스, MIT 엔진 |

## 1. 레포 재배치

```
dev-orchestrate-kit/
├── install.sh                  # 전역 설치 — 하네스·컨테이너 선택형, v1 레이아웃 자동 마이그레이션
├── new-project.sh              # 경로 1: 신규 프로젝트 스캐폴드
├── adopt-project.sh            # 경로 2: 기존 프로젝트 stamp (신규)
├── core/                       # 하네스 무관 계층
│   ├── scripts/                # run-delegation.sh, phase-tools.py, phase-claim/close,
│   │                           #   orchestrate-janitor.sh, hook-selfcheck.sh, docs-index.py, session-cost.py
│   ├── opencode/               # opencode.json, model-policy.local.json, model-policy.antigravity.json,
│   │                           #   secrets.env.example
│   ├── onboard/                # ONBOARD-PROCEDURE.md — /orchestrate-onboard 절차 본문 (단일 소스)
│   └── project-template/       # AGENTS.md, .claude/orchestrate.md(로스터), .opencode/agent/_example.md,
│                               #   opencode.json, DOCs 체계, .claude/task-templates/
├── adapters/
│   ├── claude/
│   │   ├── global/skills/      # orchestrate, karpathy-guidelines, orchestrate-onboard(래퍼)
│   │   ├── global/settings-env.md
│   │   └── project/            # .claude/hooks/(bash-guard, post-edit-check), .claude/settings.json,
│   │                           #   .claude/agents/task-orchestrator.md, CLAUDE.md
│   └── codex/
│       ├── global/prompts/     # orchestrate.md, orchestrate-onboard.md → ~/.codex/prompts/
│       └── project/            # .codex/AGENTS.md(보완), .codex/config.toml,
│                               #   .codex/agents/reviewer.toml, scripts/codex-review.sh
├── containers/
│   ├── browser/                # docker-compose.yml, insane-api/(vendored), bin/insane-fetch, patches/, README
│   └── antigravity/            # docker-compose.yml (lbjlaq/antigravity-manager, 127.0.0.1:8045), README
├── docs/                       # PORTING.md, specs/, plans/
└── tests/                      # test_phase_tools.py (유지) + 스캐폴드 스모크 테스트
```

원칙:
- **core는 하네스 단어를 모른다** — scripts·opencode 설정·AGENTS.md는 claude/codex 언급 없이 동작.
  예외: 로스터가 `.claude/orchestrate.md`에 있는 것은 호환성 결정이며 core 문서에 그 이유를 명시.
- **어댑터는 얇다** — 진입점(스킬/프롬프트)과 하네스 전용 자산(훅/config.toml)만.
- `project-template/`의 AGENTS.md가 오케스트레이션 절차의 하네스 중립 서술을 담고,
  CLAUDE.md(claude)·`.codex/AGENTS.md`(codex)는 각자 하네스의 진입·보완만 담는다.

### v1 → v2 마이그레이션

`install.sh`가 구 레이아웃(`global/`, `project-template/`)의 산출물을 감지하면:
- 전역 자산은 새 경로 기준으로 그대로 재배치(내용 동일하면 no-op) — 멱등성 유지.
- 기존 프로젝트는 손대지 않는다. 템플릿 갱신을 원하면 `adopt-project.sh`를 재실행(비파괴).

## 2. 두 진입 경로

### `new-project.sh <경로> [이름] [--claude|--codex|--both]`

현행 유지 + 하네스 선택. 플래그 생략 시 설치된 CLI 자동 감지(둘 다 있으면 both).
core/project-template + 선택 어댑터의 project/ 를 복사(`--ignore-existing`), 플레이스홀더 치환,
실행 권한, .gitignore 보강. 마지막 안내가 바뀐다:

> 다음 단계: 프로젝트 루트에서 하네스를 열고 `/orchestrate-onboard` 실행
> (수동으로 채우고 싶으면 기존 체크리스트 §온보딩 참조)

### `adopt-project.sh <경로> [--claude|--codex|--both]` (신규)

기존 프로젝트용. new-project.sh와 동일한 stamp를 수행하되:
- git 저장소 여부 확인, 더러운 워킹트리면 경고(진행은 가능 — 어차피 기존 파일은 안 덮는다).
- 기존 `.claude/settings.json`·`opencode.json`이 있으면 **덮지 않고** `*.kit-suggested` 로 배치 후
  병합 안내 출력 (설정 병합은 온보딩 명령이 도운다).
- 종료 메시지: "기본 설치 완료. 이제 하네스에서 `/orchestrate-onboard`를 실행해
  프로젝트 분석·로스터 작성·스킬 생성을 진행하라."

두 스크립트는 공통 함수(`lib/stamp.sh`)를 공유한다 — 복사 로직 이중화 금지.

## 3. `/orchestrate-onboard` — 분석·온보딩 명령

절차 본문은 `core/onboard/ONBOARD-PROCEDURE.md` 한 곳에만 존재.
claude 스킬(`adapters/claude/global/skills/orchestrate-onboard/SKILL.md`)과
codex 프롬프트(`adapters/codex/global/prompts/orchestrate-onboard.md`)는
이 파일을 읽으라는 래퍼 + 하네스별 모델 게이트만 담는다.

### 절차 (ONBOARD-PROCEDURE.md)

0. **모델 게이트 (중단 조건)** — 이 명령은 사용 가능한 가장 똑똑한 모델로 실행해야 한다.
   - claude: 현재 모델이 opus 이상(fable 포함)이 아니면 `/model` 전환을 안내하고 **중단**.
   - codex: 설치본에서 선택 가능한 최상위 모델(작성 시점 GPT 5.5) + `model_reasoning_effort = "high"`
     이상이 아니면 설정 안내 후 **중단**.
1. **스택 감지** — 언어·프레임워크·빌드/테스트/실행 명령·컨테이너(compose/Dockerfile)·CI 를 실측.
2. **로스터 작성** — `.claude/orchestrate.md`의 [TODO]를 실측값으로 채움:
   위임 에이전트 목록, 리뷰어 매핑, 검증 명령(빌드·테스트·린트), 금지 사항.
3. **opencode 에이전트 생성** — `.opencode/agent/*.md` 를 역할별로 생성
   (`_example.md` 규격 준수, 생성 후 `_example.md` 삭제). `opencode agent list`로 로드 확인.
4. **가드 등급 채움** (claude 어댑터 설치 시) — `docker ps` 실측으로 bash-guard의
   FORBIDDEN/RESTART_ONLY/FOREIGN 후보를 제안하고 **사용자 확인 후** 기입.
5. **스킬 갭 분석 → 제안 → 승인 → 생성** — ECC 언어 룰 커버리지 확인 후,
   프로젝트 특화 절차(배포 절차, 도메인 함정, 반복 워크플로우)만 커스텀 스킬 후보로 제안.
   승인된 것만 생성: claude는 `.claude/skills/<name>/SKILL.md`,
   codex는 `.agents/skills/<name>/`(SKILL.md + `agents/openai.yaml`) — ECC 패턴.
6. **검증** — `bash scripts/hook-selfcheck.sh`(claude), `opencode agent list`,
   로스터 [TODO] 잔존 0건 확인.
7. **온보딩 보고서** — 감지 결과·생성 파일·남은 수동 단계(secrets 등)를 요약 출력.

## 4. codex 어댑터

- **진입점**: `~/.codex/prompts/orchestrate.md` — 오케스트레이션 파이프라인 진입.
  절차 서술은 프로젝트 AGENTS.md(하네스 중립)를 참조하고, codex 전용 지침만 담는다.
- **프로젝트 계층**: `.codex/AGENTS.md`(루트 AGENTS.md 보완 — 로스터 경로·위임 명령·리뷰 절차),
  `.codex/config.toml`(권장 sandbox/approval 설정, multi_agent 플래그 예시).
- **리뷰 (codex 자체)**:
  - 1순위: `codex exec` 기반 — `scripts/codex-review.sh <diff-range>` 가 리뷰어 프롬프트로
    비대화형 codex 세션을 띄워 심각도별 findings를 반환. 실험 플래그 불필요, 안정적.
  - 선택: `features.multi_agent` 활성 머신은 `.codex/agents/reviewer.toml` 역할로
    대화 내 `/agent` 리뷰 사용 가능 — 실험 기능임을 문서에 명시.
  - 리뷰 게이트 규칙(승인 전 커밋 금지)은 AGENTS.md 절차에 하네스 중립으로 서술.
- **훅 부재 명시**: bash-guard·post-edit-check는 claude 전용. codex 사용자는
  `.codex/config.toml`의 sandbox(workspace-write)·approval 설정으로 등가 안전선을 잡는다.
  컨테이너 등급 규칙(FORBIDDEN 등)은 `.codex/AGENTS.md`에 지침으로 서술(강제는 아님을 명시).

## 5. 컨테이너 계층

### `containers/browser/` — 단일 컨테이너 (2026-08-07 호스트 전환 완료)

`/opt/chrome-cdp` 소스 전체를 vendored (compose, `insane-api/`(빌드 컨텍스트 + vendored MIT 엔진
+ `start-both.sh`), `bin/insane-fetch`, `patches/`, README). 설치 절차:

```bash
sudo cp -r containers/browser /opt/chrome-cdp   # 또는 원하는 경로
cd /opt/chrome-cdp && docker compose up -d
sudo ln -sf /opt/chrome-cdp/bin/insane-fetch /usr/local/bin/insane-fetch
```

**컨테이너 1개가 두 포트를 서빙한다** — 9222(raw CDP) + 9223(우회 엔진 API). 엔진이 브라우저에
CDP 로만 붙는 구조라 병합이 가능했고, 이 호스트에서 실측 전환해 8개 항목(API·CDP·CLI·실제
fetch·외부 Playwright·인간화·내부 Phase 3 브리지·구 네트워크 별칭) 모두 통과했다.

- 프로세스 감독: `start-both.sh` 가 cloakserve 와 API 를 띄우고 **둘 중 하나라도 죽으면 컨테이너를
  내려** restart 정책이 복구하게 한다 (컨테이너에 감독자가 없으므로 필수).
- 헬스체크는 **두 포트를 모두** 확인한다 — 한쪽만 살아있는 상태를 healthy 로 보고하지 않도록.
- 구 네트워크 이름 `insane-api:9223` 은 network alias 로 계속 해석된다 (호출자 무수정).
- 보안 규약 그대로: 두 포트 모두 **127.0.0.1 바인딩 고정**, CDP 무인증 경고, SSRF 가드 2중화 유지.
- **병합의 대가**: 엔진 재빌드가 브라우저까지 내린다 → 다른 사용자의 라이브 CDP 세션이 끊긴다.
  공용 호스트에서는 재빌드 전 공지할 것. README 에 명시.
- 드리프트 규약: 이 호스트의 `/opt/chrome-cdp` 개선 시 키트에 반영 후 push (호스트가 원본).

#### 문서에 반드시 담을 실측 사실 4가지

1. **세션은 fingerprint seed 단위로 유지된다.** seed 마다 전용 `--user-data-dir` 를 받고 프로세스가
   재사용되므로, 접속을 끊었다 같은 seed 로 돌아와도 쿠키·localStorage 가 남는다(다른 seed 는 격리).
   구 README 의 "연결마다 새 프로세스라 쿠키가 안 남는다"는 서술은 **틀렸다**.
2. **`CLOAKSERVE_IDLE_TIMEOUT` 을 반드시 설정한다.** 기본값 `0`(비활성)이면 한 번 쓴 seed 의 Chrome 이
   컨테이너 재시작 때까지 절대 회수되지 않는다 — 실측: 2주 가동에 Chrome 86개·8.4GB. 값은 **초 단위
   숫자만** 받는다(`"30m"` 은 파싱 실패로 기동 불가). 트레이드오프: 유휴 회수 시 프로필이 삭제되므로
   로그인 세션 수명이 이 값으로 제한된다 → 더 길게 가려면 쿠키를 밖에 저장 후 `add_cookies()` 복원.
3. **인간화는 CDP 경로에서 그대로 쓸 수 있다.** `launch(humanize=True)` 의 실체는
   `patch_browser(browser, resolve_config(...))` 이며, `connect_over_cdp` 로 얻은 객체에도 적용된다.
   실측: 클릭 1회에 mousemove 285개(곡선), 정중앙 아닌 착지, `isTrusted: true`, 타이핑 간격 63~142ms.
4. **`playwright_real_chrome` 는 일반 Chrome 이 아니다.** 업스트림 실행기 *이름*일 뿐이고 vendored
   엔진이 이 문자열로 분기하므로 그대로 둔다. 실제로는 cloakbrowser 스텔스 Chromium 에 붙는다
   (실측: `navigator.webdriver` false, 리눅스 호스트에 윈도우 UA·D3D11 GPU 위장, `cdc_` 흔적 없음).

부가 주의: 컨테이너 안에서 `cloakserve` 를 직접 실행하지 말 것 — `--help` 가 없어 서버를 띄우려 하고
`All Chrome processes terminated` 를 남기고 죽는다. 옵션은 `/usr/local/bin/cloakserve` 소스를 읽을 것.

### `containers/antigravity/` — antigravity-manager

```yaml
services:
  antigravity-manager:
    image: lbjlaq/antigravity-manager:latest
    ports: ["127.0.0.1:8045:8045"]   # 기본 localhost — LAN 공유가 필요할 때만 변경
    volumes: ["./data:/root/.antigravity_tools"]   # 계정·키 상태 (이 호스트 실측 마운트 경로)
    restart: unless-stopped
```

수동 단계(README + PORTING.md): 매니저 UI 접속 → 구글 계정 연결 → API 키 발급 →
`~/.config/opencode/secrets.env` 의 `ANTIGRAVITY_API_KEY` 설정 → opencode provider 확인 →
model-policy 를 antigravity 프로파일로 전환.

## 5-1. 모델 설정 — 자격증명 주도 생성 (프로파일 고정 대신)

### 문제

모델 설정은 두 계층으로 나뉘어 있고, 둘 다 **사용자가 가진 자격증명에 종속**된다.

| 계층 | 파일 | 역할 |
|---|---|---|
| 프로바이더 | `~/.config/opencode/opencode.json` | 어떤 모델이 **존재**하는가 |
| 정책 | `~/.config/opencode/model-policy.json` | 어떤 모델을 **어떤 순서로 쓰는가** (tier 체인) |
| 비밀 | `~/.config/opencode/secrets.env` | 키 (run-delegation.sh 가 위임 직전 자가 주입) |

따라서 "모델을 고르세요" 식의 메뉴를 설치 시점에 띄우는 것은 순서가 거꾸로다. 키가 없는
프로바이더를 고르면 그 체인은 호출마다 실패하고, run-delegation 의 폴백만 소모한다.
**현행 프로파일 2종(local/antigravity) 고정 방식도 같은 한계** — 자격증명 조합이 그 둘로
떨어지지 않는 사용자(예: qwen 없이 openai만)는 손으로 고쳐야 한다.

### 설계: 가진 것을 묻고, 체인을 생성하고, 실측 검증한다

1. **프로바이더 다중 선택** (`install.sh --providers=qwen,openai,xai` / 생략 시 대화형)
   — "쓰고 싶은 모델"이 아니라 **"자격증명을 가진(또는 발급할) 프로바이더"** 를 묻는다.
2. **secrets.env 스텁 생성** — 선택한 프로바이더의 키 항목만 넣는다. 기존 파일은 절대 덮지 않음.
3. **opencode.json 병합** — 커스텀 엔드포인트가 필요한 프로바이더만 `provider` 블록을 넣는다.
   빌트인(openai·xai 등)은 블록이 불필요하다 — 아래 표 참조.
4. **model-policy.json 생성** — 선택된 프로바이더에서만 골라 tier 체인을 구성한다
   (프로바이더→권장 모델 매핑표는 `core/opencode/provider-models.json` 에 둔다).
5. **검증(`scripts/model-doctor.sh`, 신규)** — 설치 마지막 단계이자 상시 실행 가능:
   - 체인의 각 항목이 `opencode models` 출력에 **실제로 존재**하는지
   - 키 기반 프로바이더는 secrets.env 에 값이 있는지, OAuth 기반(xai)은
     `opencode auth list` 에 잡히는지
   - tier 당 1회 최소 호출 스모크
   - 결과를 프로바이더별 OK/누락으로 보고하고, 전부 실패하는 tier 가 있으면 exit 1

   **이 검증이 없으면 오타 난 모델 ID가 조용히 폴백만 소모한다** — 현재 아무도 체인을
   검증하지 않는다. 실측: `opencode models` 가 등록 모델의 단일 진실 소스다.

### 프로바이더 표 — 자격증명은 키 또는 구독

인증 수단이 **API 키만이 아니다.** 팀원마다 가진 구독이 다르므로(ChatGPT·SuperGrok·Copilot 등)
선택 단계는 "키를 가진 프로바이더"가 아니라 **"인증 수단(키 또는 구독)을 가진 프로바이더"** 를 묻고,
`model-doctor.sh` 는 `opencode auth list`(OAuth)와 `secrets.env`(키) **양쪽**을 확인해야 한다.

| 프로바이더 | opencode 등록 | 자격증명 | opencode.json 블록 |
|---|---|---|---|
| `openai` | 빌트인 | 구독 OAuth 또는 `OPENAI_API_KEY` | 불필요 |
| `xai` | 빌트인 | 구독 OAuth (SuperGrok) | 불필요 |
| `qwencloud` | 커스텀 | `QWEN_API_KEY` | 필요 (OpenAI 호환 baseURL) |
| `antigravity` | 커스텀 | `ANTIGRAVITY_API_KEY` + 로컬 프록시 :8045 | 필요 |

opencode 가 제공하는 구독 로그인은 이 외에도 GitHub Copilot·Poe·DigitalOcean·OpenCode Console 이 있다.

### OpenAI 추가 — 구독 인증이 기본

`opencode auth login -p openai` 의 방식 3가지:

| 방식 | ID | 용도 |
|---|---|---|
| ChatGPT Pro/Plus (browser) | `chatgpt-browser` | `localhost:1455` 콜백 — 로컬 데스크톱 |
| **ChatGPT Pro/Plus (headless)** | `chatgpt-headless` | **디바이스 코드** — 원격·헤드리스 서버 |
| API key | — | `OPENAI_API_KEY` |

헤드리스 경로는 `auth.openai.com/codex/device` 에 코드를 입력하는 디바이스 인증이라
브라우저도 콜백 포트도 필요 없다 — 공용 개발 서버에 설치하는 팀원이 쓸 경로다.
**설치 스크립트가 대신 수행할 수 없다**(대화형 코드 입력) — 수동 단계로 안내한다.

#### 구독으로 열리는 모델은 API 가격표와 다르다

이 호스트에서 `chatgpt-headless` 로 로그인한 뒤 `opencode models` 실측 결과, API 문서에 있는
`gpt-5.3-codex`·`gpt-5.5-pro` 는 열리지 않고 대신 `gpt-5.6` 계열이 나왔다. 즉 **모델 목록을
문서에 하드코딩하지 말고 `opencode models` 로 실측해야 한다** — 이것이 `model-doctor.sh` 가
필요한 또 하나의 이유다.

실측된 주요 모델 (괄호 안은 참고용 API 단가 — 구독에서는 요금이 아니라 **레이트 리밋**이 실질 제약):

| 모델 | 컨텍스트 | 성격 | 배치 |
|---|---|---|---|
| `gpt-5.6-luna` | 1.05M | 경량 ($0.2/$1.2) | **default 1순위** |
| `gpt-5.6-terra` | 1.05M | 중량 ($2/$12) | **heavy 1순위** |
| `gpt-5.6-sol` | 1.05M | 최상위 ($5/$30) | 필요 시 heavy 승격 |

세 모델 모두 `opencode run` 스모크 통과. reasoning·tool_call 지원, 출력 상한 128K.

#### 정책: GPT 우선

**두 tier 모두 1순위는 `openai` 다** — 실제 서비스와 키트 양쪽에 동일 적용한다.
`provider-models.json` 의 `tier_order` 첫 항목이 `openai` 이며, `gen-policy.sh` 가 이 순서를 따른다.

#### 뒤따르는 항목은 서로 다른 할당량 풀로 채운다

`xai`(SuperGrok)와 `openai`(ChatGPT)는 **별개의 할당량 풀**이다. openai 가 한도에 걸렸을 때
실제로 넘어갈 곳이 있어야 폴백이 의미를 가지므로, 1순위 뒤에는 **다른 프로바이더**를 둔다.
같은 프로바이더의 모델을 연달아 두면(예: terra → sol) 한도에 걸릴 때 함께 막혀 폴백이 무의미하다.
따라서 `tier_order` 는 `["openai", "xai", "antigravity", "qwen"]` 이다.

### 프로파일은 생성 결과의 기본값으로만 남긴다

`core/opencode/profiles/` 의 local·antigravity 프로파일은 **생성기의 시드**로 강등한다.
`--providers` 조합이 시드와 일치하면 그대로 쓰고, 아니면 매핑표로 체인을 만든다.
어느 경로든 최종 산출물은 `~/.config/opencode/model-policy.json` 하나이며,
기존 파일은 백업 후 교체한다 (현행 backup_and_copy 규약).

## 5-2. Claude 요금제별 토큰 경량화 프로파일 (claude 어댑터 전용)

opencode 쪽 모델 정책(§5-1)과 별개로, **claude 하네스 자체의 모델·토큰 설정**을 요금제에 맞춘다.
Pro 사용자와 Max x20 사용자가 같은 설정을 쓰면 한쪽은 한도에 막히고 다른 쪽은 성능을 낭비한다.

### 기계적 제약 — 서브에이전트 모델은 frontmatter 로만 정한다

**`CLAUDE_CODE_SUBAGENT_MODEL` 을 절대 쓰지 않는다.** 이 env 는 우선순위가 가장 높아
에이전트 frontmatter 의 `model:` 과 Agent 호출의 명시적 `model` 파라미터까지 전부 덮어쓴다.
2026-07-29 실제 운영 프로젝트에서 이 env 하나 때문에 **리뷰어 전원이 haiku 로 실행된** 전례가 있다.
"worker 는 haiku, 리뷰는 sonnet" 같은 차등 자체가 이 env 로는 표현 불가능하다.

따라서 티어링은 세 지점에서만 이뤄진다:

| 대상 | 설정 위치 |
|---|---|
| 메인 오케스트레이터 모델 | `~/.claude/settings.json` 의 `.model` |
| 서브에이전트 모델 | `~/.claude/agents/*.md` 의 frontmatter `model:` |
| 사고·압축 예산 | `~/.claude/settings.json` 의 `.env` 2개 키 |

### 에이전트 역할 분류 (실측 68개)

| 클래스 | 개수 | 대상 |
|---|---|---|
| `design` | 7 | `planner`·`architect`·`code-architect`·`spec-miner`·`*-architect` — 깊은 추론이 산출물 품질을 좌우 |
| `quality` | 29 + 1 | `*-reviewer`·`*-analyzer`·`silent-failure-hunter`·`*-evaluator` + **`task-orchestrator`**(검증·커밋 경로라 품질 등급) |
| `worker` | 32 | 나머지 — 빌드 에러 해결·문서 갱신·E2E 등 기계적 작업 |

분류는 `adapters/claude/global/agent-roles.json` 에 명시한다. 정규식 추측이 아니라 목록이며,
목록에 없는 에이전트는 `worker` 로 떨어진다(새 ECC 에이전트가 추가돼도 안전한 기본값).

### 프로파일 표

| 항목 | `pro` | `max5` | `max20` (현행 유지) |
|---|---|---|---|
| 메인 오케스트레이터 | `sonnet` | `opus` | **건드리지 않음** (사용자 선택 유지) |
| `design` 클래스 | `opus` | `opus` | `opus` |
| `quality` 클래스 | `sonnet` | `sonnet` | `sonnet` |
| `worker` 클래스 | `haiku` | `haiku` | `sonnet` |
| `MAX_THINKING_TOKENS` | `10000` | `10000` | `10000` |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | `75` | `75` | `75` |
| `/orchestrate-onboard` 게이트 | opus 필수 | opus 필수 | opus 이상 |

**토큰 env 2개는 요금제와 무관한 공통값이다.** 사용자가 x20 에서도 같은 값을 쓰기로 정했고,
실제로 운영 중인 세 프로젝트가 이미 `10000`/`75` 로 운영 중이다
(프로젝트 템플릿에도 같은 값이 들어 있다). 요금제가 가르는 것은 **모델뿐**이다 —
메인 오케스트레이터와 worker 클래스 두 곳.

프로젝트 `.claude/settings.json` 이 전역보다 우선하므로, 프로파일은 전역에 같은 값을 심어
프로젝트 밖(임시 디렉터리·홈 등)에서 여는 세션에도 동일한 예산이 적용되게 한다.

핵심 판단: **품질 게이트(리뷰)는 어느 요금제에서도 내리지 않는다.** Pro 에서 아끼는 곳은
worker 클래스(기계적 작업 32개)와 사고 예산이지 리뷰가 아니다 — 리뷰를 haiku 로 내리면
위임 산출물 검수가 무너져 오케스트레이션 자체가 의미를 잃는다.

스캐폴딩·스킬 생성이 `opus` 인 것은 `design` 클래스와 온보딩 게이트가 함께 담보한다.
Pro 에서도 이 순간에는 opus 를 쓴다 — 1회성이고 이후 모든 작업의 품질을 결정하기 때문이다.

### 적용 순서 — ECC 다음이어야 한다

**ECC install 은 `~/.claude/agents/*.md` 를 덮어쓴다** (매니페스트 기반 복사 — 실측 확인).
따라서 프로파일 적용은 반드시 ECC 단계 **뒤**여야 하며, ECC 를 갱신할 때마다 재적용해야 한다.
`apply-plan-profile.sh` 는 멱등이므로 언제든 다시 돌릴 수 있다.

## 6. install.sh v2

```
./install.sh [--claude] [--codex] [--containers=browser,antigravity] \
             [--providers=qwen,openai,xai,antigravity] [--plan=pro|max5|max20] [ECC 언어...]
```

- 하네스 플래그 생략 시 설치된 CLI 자동 감지. ECC 언어 생략 시 ECC 단계 스킵(현행 동일).
- 단계: 도구 확인 → opencode 설치 → ECC → superpowers(claude 시) → **어댑터별 전역 자산 배치**
  → **프로바이더 선택·secrets 스텁·체인 생성**(§5-1) → (옵션) 컨테이너 설치
  → **`model-doctor.sh` 검증** → 남은 수동 단계 출력.
- codex 경로: `~/.codex/prompts/` 배치 + config.toml 권장 설정은 **병합하지 않고 안내만**
  (ECC의 sync 스크립트 같은 TOML 병합은 이번 범위 밖 — 수동 단계로 출력).
- 멱등: 재실행 시 동일 결과. 기존 파일은 `.bak-<stamp>` 백업 후 교체, secrets.env는 절대 안 덮음.

## 7. 테스트·검증

- `tests/test_phase_tools.py` 유지.
- 스캐폴드 스모크 테스트 추가: 임시 디렉터리에 `new-project.sh`/`adopt-project.sh` 실행 →
  [TODO] 플레이스홀더 수·실행 권한·기존 파일 비파괴(adopt) 검증.
- `install.sh --dry-run` 은 만들지 않는다(YAGNI) — 스모크는 스캐폴드 계층만.
- 컨테이너는 CI 없이 문서 검증(이 호스트에서 compose config 통과 확인).

## 범위 밖 (명시)

- 음성 단말 클라이언트·docker-ops(개발 서버 전용) 계층 — 기존 제외 규약 유지.
- ECC codex sync 스크립트 수준의 TOML 자동 병합.
- codex용 훅 강제 시스템(등가물이 없음 — 문서 지침으로 대체).
- 비밀·OAuth(머신별 수동) — 현행 규약 유지.

## 동기화 규약 갱신

README의 "이 저장소가 단일 소스" 규약에 추가:
- `/opt/chrome-cdp` ↔ `containers/browser/` 드리프트 시 키트가 아니라 **호스트가 원본** —
  호스트 개선 → 키트 반영 → push.
- model-policy 는 프로파일 파일 2종이 원본이며, `~/.config/opencode/model-policy.json` 은 산출물.
