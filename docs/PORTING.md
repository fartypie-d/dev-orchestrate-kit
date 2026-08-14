# 이식 가이드 — 수동 단계와 머신별 차이

## install.sh 설치 UX

`git clone` 직후에는 실행비트가 이미 있으므로 `./install.sh` 로 실행한다. ECC 언어 인자를 생략하면
ECC 자산 설치를 건너뛰어 리뷰어가 없는 상태가 된다. 설치 예제에는 사용할 언어를 반드시 넣는다.

```bash
./install.sh --claude --providers=qwen,openai --plan=max20 typescript python
```

| 항목 | 지정 방법 | 생략 시 동작 |
|---|---|---|
| 하네스 | `--claude`, `--codex` (둘 다 지정 가능) | 터미널에서는 번호 선택, 비대화형에서는 자동 감지값 사용 |
| 프로바이더 | `--providers=qwen,openai` | 터미널에서는 다중 번호 선택, 비대화형에서는 정책을 건드리지 않음 |
| Claude 요금제 | `--plan=pro`, `--plan=max5`, `--plan=max20` | 터미널에서는 번호 선택, 비대화형에서는 적용하지 않음 |
| ECC 언어 | 위치 인자. 예: `typescript python` | 터미널에서는 다중 번호 선택 또는 직접 입력, 비대화형에서는 ECC 설치를 건너뜀 |
| 컨테이너 | `--containers=browser` | 지정하지 않으면 설치 안내를 하지 않음 |

플래그나 언어 인자로 지정한 항목에는 선택 메뉴가 나타나지 않는다. 다중 선택 항목(프로바이더·ECC 언어)은
콤마 또는 공백으로 여러 번호를 받으며, 잘못된 번호를 세 번 입력하면 해당 항목의 기본값으로 진행한다.

### 필수 도구와 Claude CLI

`install.sh` 는 `git`·`curl`·`python3`·`jq` 누락을 확인한다. 지원하는 패키지 관리자
`apt-get`·`dnf`·`pacman`·`apk`·`zypper`·`brew`를 찾으면 설치 명령을 보여 주고 동의를 받은 뒤 설치한다.
권한은 root, 무암호 `sudo`, 관리자 권한 동의 프롬프트 순으로 판정하며, 동의 없이 `sudo`를 실행하지 않는다.
동의를 거부하거나 지원하는 패키지 관리자를 찾지 못하면 정확한 수동 설치 명령을 출력하고 중단한다.

`--claude` 를 지정했는데 `claude` CLI가 없으면 설치 여부를 묻는다. `npm`도 없으면
`$HOME/.local/opt/node`에 유저공간 Node를 부트스트랩한 다음 `npm i -g @anthropic-ai/claude-code`를
시도한다. 거부하거나 설치에 실패해도 나머지 자산 설치는 계속하며, 마지막에 수동 설치 명령을 안내한다.
이미 `claude`가 있으면 다시 설치하지 않는다.

### 비대화형 실행과 dry-run

stdin이 터미널이 아닌 파이프·CI 실행에서는 선택 메뉴를 모두 건너뛰며, 각 생략 항목을 안내한다.
따라서 CI에서는 하네스, 프로바이더, 요금제, ECC 언어를 모두 명시한다.

```bash
./install.sh --claude --providers=qwen,openai --plan=max20 typescript python < /dev/null
```

실제 변경 전에 계획을 보려면 `INSTALL_DRY_RUN=1`을 쓴다. 감지한 패키지 관리자, 누락 도구,
설치·권한 방식, Claude CLI 및 Node 부트스트랩 계획을 출력하고 종료한다.

```bash
INSTALL_DRY_RUN=1 ./install.sh --claude --providers=qwen,openai --plan=max20 typescript python
```

## v2 변경점 (2026-08-07)

- 레이아웃이 `core/` + `adapters/<하네스>/` 로 재편됐다. 구 `global/`·`project-template/` 경로는 없다.
- 진입 경로가 둘이다: `new-project.sh`(신규) / `adopt-project.sh`(기존, 비파괴).
- 모델 정책은 고정 프로파일 대신 `gen-policy.sh` 가 생성하고 `model-doctor.sh` 가 검증한다.
- OpenAI 는 구독 인증이 기본이다 — 원격 서버는 헤드리스 디바이스 인증을 쓴다:
  `opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"`.
  **구독으로 열리는 모델은 API 가격표와 다르다** — `opencode models` 로 실측할 것.
- 요금제별 토큰 프로파일: `./install.sh --claude --plan=pro typescript`처럼 설치 시 지정한다. ECC 가 에이전트를 덮으므로
  프로파일은 ECC **뒤**에 적용되고, ECC 갱신 때마다 `apply-plan-profile.sh` 재실행이 필요하다.
- 브라우저 컨테이너는 단일 컨테이너다(9222 CDP + 9223 우회 API). `CLOAKSERVE_IDLE_TIMEOUT` 을
  반드시 설정한다(초 단위 숫자만 — `"30m"` 은 기동 실패). 헤드풀이며 noVNC 오버레이로 화면 확인 가능.
- 브라우저 컨테이너는 오케스트레이션과 독립 사용 가능하다 — 빌드 전 `vendor/sync-vendor.sh` 로
  업스트림 MIT 엔진을 핀 커밋에서 가져온다.

## ECC가 플러그인이 아닌 이유

ECC는 `claude plugin install`이 아니라 **저장소 clone + `./install.sh <언어>` 수동 설치**로
쓴다 (install.sh 3단계가 이 방식). 플러그인은 rules(`~/.claude/rules/ecc/`)를 배포하지
못하므로, rules까지 얻는 유일한 경로가 수동 설치다. 커맨드도 짧은 형태(`/plan`)를 쓰게 된다 —
`/ecc:plan` 네임스페이스 형태가 아니다. superpowers는 반대로 정식 플러그인 경로
(마켓플레이스 `obra/superpowers` 등록 → install)를 쓴다 — install.sh 4단계가 자동 처리.

## 설치 후 수동 단계 (install.sh가 못 하는 것)

1. **QWEN_API_KEY** — `~/.config/opencode/secrets.env`에 입력 (chmod 600 유지).
   비밀은 git으로 옮기지 말 것 — 1Password 등 안전 경로로 전달.
2. **xai(grok) 인증** — 구독 OAuth는 머신별 재인증이 필요하다:
   ```bash
   ~/.opencode/bin/opencode auth login --provider xai \
     --method "xAI Grok OAuth (Headless / Remote / VPS)"
   ```
   출력된 `https://accounts.x.ai/oauth2/device?user_code=...` 를 브라우저에서 승인.
   확인: `~/.opencode/bin/opencode models | grep grok-4.5`
3. **전역 settings 병합** — `adapters/claude/global/settings-env.md` 참조.
   ⚠️ `CLAUDE_CODE_SUBAGENT_MODEL`은 설정 금지 (리뷰어 모델까지 덮어쓰는 사고 전례).
4. **동작 확인** (아무 온보딩된 프로젝트에서):
   ```bash
   mkdir -p .orchestrate && printf '어떤 파일도 만들지 말고 PIPELINE-OK 한 줄만 응답하라.\n' > .orchestrate/smoke.prompt
   bash scripts/run-delegation.sh <에이전트명> .orchestrate/smoke.prompt .orchestrate/smoke.log
   # 기대: DONE + MODEL_USED=... (실패 시 exit 코드 표는 run-delegation.sh 헤더 참조)
   ```

## macOS 차이 (이식판에 이미 반영됨)

- 기본 bash 3.2 → `run-delegation.sh`는 `mapfile` 없이 작성됨. brew bash 설치 불필요.
- `flock` 없음 → mkdir 스핀락 폴백 내장 (flock이 있으면 자동으로 flock 사용).
  단 flock 경로와 달리 래퍼 프로세스가 죽으면 락이 즉시 풀린다(스테일 감지로 회수).
- `rsync`·`perl`은 macOS 기본 탑재 — new-project.sh가 사용.
- 필요 도구: `brew install jq` (install.sh가 검사).

## gemini(antigravity 프록시)를 쓰는 머신

> **프록시 컨테이너는 이 키트에 더 이상 번들되지 않는다.** antigravity 는 위임
> 프로바이더로만 남아 있다(`--providers=antigravity`). 쓰려면 OpenAI 호환 `:8045`
> 엔드포인트를 **직접 준비**해야 한다 — 원격 서버면 SSH 포트포워딩만 쓰고 LAN 에 열지 말 것.

`:8045` OpenAI 호환 프록시가 준비된 머신은:

1. `~/.config/opencode/opencode.json`의 `provider`에 추가:
   ```json
   "antigravity": {
     "npm": "@ai-sdk/openai-compatible",
     "name": "Antigravity (local proxy :8045)",
     "options": { "baseURL": "http://localhost:8045/v1", "apiKey": "{env:ANTIGRAVITY_API_KEY}" },
     "models": { "gemini-3.6-flash-high": { "name": "Gemini 3.6 Flash (high)" } }
   }
   ```
2. `model-policy.json`의 `tiers.default` 맨 앞에 `"antigravity/gemini-3.6-flash-high"` 추가.
3. `secrets.env`에 ANTIGRAVITY_API_KEY 입력.

run-delegation.sh는 antigravity 모델 시도 전 프록시 생존을 확인하고, 죽어 있으면 시도 없이
다음 모델로 스킵하므로 프록시가 내려가 있어도 위임은 계속 동작한다.

## 알려진 함정 (이 환경 실측 이력)

- `timeout N opencode run` 금지 — 세션 DB 오염으로 다음 실행까지 막힌다.
- opencode는 한도 소진 모델에 지수 백오프로 무한 재시도한다 — run-delegation.sh의
  90초 스톨 가드가 끊고 폴백한다 (정상 실행은 오판하지 않음: 타이머는 백오프 공백에서만 누적).
- 한도 에러가 항상 429로 오지 않는다 — gemini는 `AI_APICallError: Service Unavailable`.
- 위임 프롬프트에 프로젝트 밖 절대경로를 "읽어라"고 쓰면 opencode가 `external_directory`로
  차단하고 에이전트가 포기한다. 외부 참조는 오케스트레이터가 읽어 프롬프트에 인라인할 것.
- opencode 세션 DB는 전역 공유지만, serve attach가 가능하면(`~/.config/opencode/serve.env` 존재 및 serve 기동 성공)
  프로젝트별 락을 사용한다. 프로젝트가 다르면 병렬로 실행되고, 같은 프로젝트(워크트리 포함)는 직렬 대기한다
  (`LOCK_WAIT(project)`). serve 환경이 없거나 기동에 실패하면 standalone 폴백(`SERVE_FALLBACK`)으로
  전역 락을 사용해 전체를 직렬화한다. 새 머신에서 병렬 실행을 사용하려면 `serve.env`를 만들고
  `chmod 600`을 적용하며 비밀번호는 영숫자만 사용해야 한다. 없으면 자동 폴백되어 동작하지만 병렬 이득은 없다.

## Phase 레지스트리 + 재니터 설치 (2026-08-03)

새 프로젝트/새 머신에 오케스트레이션을 이식할 때:

1. `core/scripts/{phase-tools.py,phase-claim.sh,phase-close.sh,orchestrate-janitor.sh}`
   를 프로젝트 `scripts/`로 복사, 실행 권한 유지 (스캐폴드 스크립트가 자동 처리 —
   수동 이식 시에만 이 경로)
2. 레지스트리 초기화 (프로젝트 루트에서):
   `python3 scripts/phase-tools.py init --default-branch <병합 기준 브랜치> --docs-dir <DOCs|docs>`
3. `.claude/settings.json` SessionStart 훅에 추가 (기존 hook-selfcheck 항목 뒤):
   `{"type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/orchestrate-janitor.sh", "timeout": 60}`
4. permissions.allow에 추가:
   `Bash(bash scripts/phase-claim.sh:*)`, `Bash(bash scripts/phase-close.sh:*)`,
   `Bash(bash scripts/orchestrate-janitor.sh)`, `Bash(python3 scripts/phase-tools.py:*)`
5. 검증: `bash scripts/orchestrate-janitor.sh` 수동 실행 → `JANITOR(<project>): ...` 1행 확인

레지스트리는 `~/.local/state/orchestrate/registry/<project>.json` — git 밖·세션 밖이
설계 요점이다 (병렬 세션 phase 번호 충돌·세션 절단 후 미정리의 근본 원인 제거).
페이즈 시작은 `bash scripts/phase-claim.sh <slug>`, 마감은 `bash scripts/phase-close.sh <N>`.
