# Task 2: claude 전제 강제 + 동의 자동 설치 (Node 유저공간 폴백)

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`
- **선행**: Task 1 (`prompt_yes_no`·`run_privileged`·`INSTALL_DRY_RUN` 을 재사용한다)
- **목표**: `--claude` 하네스인데 `claude` CLI 가 없으면 **눈에 띄는 경고 + 동의 후 자동 설치**를
  시도한다. 실패하거나 거부해도 **자산 설치는 계속**되고(멱등), 정확한 수동 명령을 안내한다.
- **재사용**: `개선 후 재사용 install.sh:69 (command -v claude ... note "⚠️ claude CLI 미설치")` —
  현재 경고 한 줄뿐인 지점을 확장한다. Task 1 이 만든 `prompt_yes_no()`·`INSTALL_DRY_RUN` 출력
  규약을 **그대로 재사용**한다 (새 프롬프트 헬퍼를 다시 만들지 말 것).
  opencode 유저공간 설치 패턴은 `install.sh:72-77` 을 참고한다.
- **실패 테스트**: `tests/test_install_claude_bootstrap.py` (신규)
  - `INSTALL_DRY_RUN=1` + `--claude` + `INSTALL_TEST_NO_CLAUDE=1` → 출력에
    `DRY_RUN CLAUDE=missing` 과 설치 계획(`DRY_RUN CLAUDE_INSTALL=npm i -g @anthropic-ai/claude-code`)
  - 위 + `INSTALL_TEST_NO_NPM=1` → `DRY_RUN NODE_BOOTSTRAP=` 계획 줄이 먼저 나온다
  - `--codex` 만 준 경우 → claude 관련 계획 줄이 **없다**
  - `INSTALL_TEST_NO_CLAUDE` 미설정 + claude 존재 시 → `DRY_RUN CLAUDE=present`
  - `INSTALL_TEST_*` 는 `INSTALL_DRY_RUN=1` 일 때만 해석된다 (Task 1 규약)
- **구현 지침**:
  - 순서: `command -v claude` → 있으면 통과. 없으면
    ① 굵은 경고(하네스가 claude 인데 CLI 가 없다 = 스킬·훅이 동작하지 않는다)
    ② `prompt_yes_no "지금 설치할까요?"`
    ③ 동의 시: `command -v npm` 있으면 `npm i -g @anthropic-ai/claude-code`.
       npm 이 없으면 **유저공간 prebuilt Node** 부트스트랩
       (`https://nodejs.org/dist/<ver>/node-<ver>-<os>-<arch>.tar.(gz|xz)` → `$HOME/.local/opt/node`,
       `PATH` 에 앞세워 그 세션에서만 사용) 후 `npm i -g`.
       **sudo 로 전역 npm 설치를 시도하지 말 것** — 유저공간 경로만 쓴다.
    ④ 실패·거부 시: `⚠️` + 정확한 수동 명령 안내 + **계속 진행**(exit 하지 않는다).
  - 아키텍처 매핑: `uname -m` → `x86_64→x64`, `aarch64|arm64→arm64`. 그 외는 미지원으로
    안내하고 계속 진행.
  - PATH 에 추가한 경우, "남은 수동 단계"에 `export PATH="$HOME/.local/opt/node/bin:$PATH"` 를
    영구 등록하라는 안내를 남긴다 (**셸 rc 파일을 스크립트가 자동 편집하지 말 것**).
  - 설치 후 `command -v claude` 로 재검증하고 결과를 명시적으로 보고한다(조용한 성공 가정 금지).
- **필독 스킬**: 없음
- **필수 규칙**:
  - bash 3.2 호환. `set -euo pipefail` 하에서 실패해도 계속 진행해야 하는 구간은
    `|| true` 남용 대신 `if ...; then ... else 안내; fi` 로 **명시적으로** 다룬다.
  - 네트워크 다운로드는 `curl -fsSL` + 체크(파일 크기·압축 해제 성공)로 실패를 감지한다.
  - 4/7 superpowers 단계(`install.sh:91-118`)의 기존 분기는 건드리지 말 것 — 이 task 는
    1/7 프리플라이트 쪽만 바꾼다.
  - `install.sh` 외 수정 금지(신규 테스트 파일 제외). `git commit`·sudo·docker 금지.
- **완료 조건**:
  ```bash
  python3 -m unittest discover -s tests -v
  bash -n install.sh
  INSTALL_PARSE_ONLY=1 bash install.sh --claude typescript    # 기존 출력 유지
  ```
