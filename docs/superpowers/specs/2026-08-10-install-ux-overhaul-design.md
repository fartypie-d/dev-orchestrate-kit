# install.sh UX 개편 — 자동 설치 + 선택 메뉴 (hermes-agent 참고)

- 날짜: 2026-08-10
- 상태: 설계 승인 대기 (GATE 1)
- 계기: 클린 호스트(boldyoc) 도그푸딩에서 새 유저가 걸리는 지점 실측 — 실행비트·jq·ECC 언어 인자·claude 전제

## 목표

새 유저가 맨바닥 호스트에서 `install.sh` 한 번으로 **필요 도구까지 설치**되고, 프로바이더·요금제·
하네스를 **자유 입력이 아니라 선택지로** 고르며 진행할 수 있게 한다. NousResearch/hermes-agent
설치기의 방식(OS/PM 감지·동의 기반 자동 설치·유저공간 폴백)을 참고한다.

## 확정 결정 (대화에서)

- **필수 도구 자동 설치**: 감지 → 동의 → 패키지 매니저 설치, 거부·실패 시 정확한 명령 출력.
  몰래 sudo 하지 않는다(동의 후에만).
- **sudo 3-tier**(hermes): root → `sudo -n true`(무암호 sudo) → 동의 프롬프트(`/dev/tty` 폴백).
- **claude 자동 설치**: `--claude`인데 없으면 눈에 띄는 경고 + **동의받아 자동 설치 시도**
  (Node 없으면 유저공간 prebuilt Node → `npm i -g @anthropic-ai/claude-code`). 실패·거부 시
  명령 안내하고 **자산 설치는 계속**(멱등).
- **번호 선택 메뉴**: harness·providers·plan·ECC 언어를 free-text `read` 대신 번호 선택.
  비대화형(플래그 있음/파이프)엔 메뉴 스킵·기본값.
- **bash 3.2·macOS 호환** 유지(연관배열·mapfile 금지, `. /etc/os-release`는 Linux 한정,
  Darwin→brew 분기).
- **테스트 가능**: `INSTALL_DRY_RUN=1`(신규)로 실제 설치 없이 "계획"만 출력 → unittest 검증.
  기존 `INSTALL_PARSE_ONLY` 패턴 계승.

## 개선 항목 (도그푸딩 4건 통합)

1. **프리플라이트 자동 설치** — git·curl·python3·jq 누락 시 감지·동의·설치 (jq 이슈 해결).
2. **claude 전제 강제 + 동의 자동 설치** — `--claude` 무claude 상태 방지.
3. **번호 선택 UI** — providers(다중)·plan(단일)·harness(단일)·ECC 언어(다중).
4. **ECC 언어 프롬프트** — 자산만 깔고 리뷰어 없는 상태 방지(언어 미지정 시 선택 유도).
5. 실행비트(#1)는 이미 커밋(`3eb285f`).
6. **DRY_RUN 테스트 훅** + unittest 확장.

## 설계 상세

### OS/PM 감지 (`detect_pm`)
```
uname -s: Linux → . /etc/os-release; case $ID in ubuntu|debian) apt-get ;; fedora|rhel) dnf ;;
                                                  arch) pacman ;; alpine) apk ;; opensuse*) zypper ;;
          Darwin → brew
```
설치 커맨드·sudo 필요 여부를 변수로 확정. 미지원 PM이면 자동 설치 없이 명령 안내로 폴백.

### 자동 설치 흐름 (`ensure_tools`)
- `command -v X` + (필요 시 버전) → 누락 목록 계산.
- 누락 있으면: 목록 출력 → `prompt_yes_no "지금 설치할까요?"`(단일 동의) →
  동의 시 sudo 3-tier 로 PM 설치, 거부·실패·미지원 시 정확한 명령 출력 후 `exit 1`.
- opencode: 현행 유저공간 자동 설치 유지.
- claude: `--claude`일 때만, 위 결정대로 동의 자동 설치(폴백=안내, 자산 설치 계속).

### 선택 메뉴 (`choose_one` / `choose_many`)
- 번호 입력 방식(휴대성 — arrow-key TUI 없음). 각 항목에 힌트(인증 방식 등).
- providers: openai/xai/qwen/antigravity 다중, plan: pro/max5/max20/skip 단일,
  harness: claude/codex/both 단일, ECC 언어: 자유 다중(예시 제시).
- **비대화형**: 플래그로 값이 오면 메뉴 자체를 띄우지 않는다. 파이프(`! [ -t 0 ]`)면 기본값.

### 테스트 훅
- `INSTALL_DRY_RUN=1`: `ensure_tools`·`detect_pm`·설치 계획을 **출력만** 하고 실행하지 않음.
- unittest: PM 라우팅(모의 `$ID`), 누락 계산, 비대화형 메뉴 스킵, claude 분기 계획.

## 구현 계획 (task 분할)

| task | 내용 | 에이전트 | 리뷰어 |
|---|---|---|---|
| 0 | **bash-guard 오탐 수정** — `sudo`·`rm -rf` 등을 부분 문자열이 아니라 **명령 토큰/단어 경계**로 검사. (이 기능이 sudo 를 다뤄 이후 커밋·위임 오탐을 막으므로 **먼저** 한다.) 대상: `.claude/hooks/bash-guard.sh` | 오케스트레이터 직접(.claude/ 허용) 또는 kit-scripts | bash + security |
| 1 | `detect_pm`·`ensure_tools`·권한상승 3단계 동의·DRY_RUN (git·curl·python3·jq) | kit-scripts | bash + security + silent-failure-hunter |
| 2 | claude 전제 강제 + 동의 자동 설치(Node 폴백) | kit-scripts | bash + security + silent-failure-hunter |
| 3 | 번호 선택 메뉴(harness·providers·plan·ECC 언어) + 비대화형 스킵 | kit-scripts | bash + security + silent-failure-hunter |
| 4 | DRY_RUN·PM·메뉴 스킵 unittest (test_install_* 확장) | kit-tests | python-reviewer |
| 5 | README·런북·"남은 수동 단계" 갱신 | kit-docs | code-reviewer |

- 등급: **large** (횡단·외부 실행·보안 민감 → heavy tier, task-orchestrator 경유).
- TDD: 각 task 는 `INSTALL_DRY_RUN`/`INSTALL_PARSE_ONLY` 기반 실패 테스트 먼저.
- **순서**: task 0 먼저(guard 오탐 제거) → task 1~3 은 install.sh 동일 파일이라 **순차 위임**(병렬 금지) → 4 → 5.
- **guard 수정 근거(실측)**: 2026-08-10 이 스펙 커밋이 메시지의 "sudo" 문자열만으로 bash-guard 에 차단됨.

## 리스크

- **sudo·자동 설치 = 보안 민감** → security-reviewer 필수, 몰래 sudo 금지 원칙 준수.
- **claude/Node 자동 설치**가 가장 깨지기 쉬움 — 실패해도 자산 설치는 계속(멱등)하고 명확히 안내.
- **bash 3.2·다PM 이식성** — 실기기 검증은 제한적, DRY_RUN 계획 출력으로 최대한 커버.
- 대화형 메뉴는 unittest 가 비대화형 경로만 검증 — 대화형은 수동 확인.
