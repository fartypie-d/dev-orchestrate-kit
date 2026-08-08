# 이식 가이드 — 수동 단계와 머신별 차이

## v2 변경점 (2026-08-07)

- 레이아웃이 `core/` + `adapters/<하네스>/` 로 재편됐다. 구 `global/`·`project-template/` 경로는 없다.
- 진입 경로가 둘이다: `new-project.sh`(신규) / `adopt-project.sh`(기존, 비파괴).
- 모델 정책은 고정 프로파일 대신 `gen-policy.sh` 가 생성하고 `model-doctor.sh` 가 검증한다.
- OpenAI 는 구독 인증이 기본이다 — 원격 서버는 헤드리스 디바이스 인증을 쓴다:
  `opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"`.
  **구독으로 열리는 모델은 API 가격표와 다르다** — `opencode models` 로 실측할 것.
- 요금제별 토큰 프로파일: `install.sh --plan=pro|max5|max20`. ECC 가 에이전트를 덮으므로
  프로파일은 ECC **뒤**에 적용되고, ECC 갱신 때마다 `apply-plan-profile.sh` 재실행이 필요하다.
- 브라우저 컨테이너는 단일 컨테이너다(9222 CDP + 9223 우회 API). `CLOAKSERVE_IDLE_TIMEOUT` 을
  반드시 설정한다(초 단위 숫자만 — `"30m"` 은 기동 실패). 헤드풀이며 noVNC 오버레이로 화면 확인 가능.
- 브라우저 컨테이너는 오케스트레이션과 독립 사용 가능하다 — 빌드 전 `vendor/sync-vendor.sh` 로
  업스트림 MIT 엔진을 핀 커밋에서 가져온다.

## ECC가 플러그인이 아닌 이유

ECC는 `claude plugin install`이 아니라 **저장소 clone + `install.sh <언어>` 수동 설치**로
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

개발 서버처럼 antigravity-manager 프록시(:8045)가 있는 머신은:

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
- opencode 세션 DB는 전역 공유 — 동시 위임은 run-delegation.sh의 전역 락이 직렬화한다.

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
