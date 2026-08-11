# Task 1: detect_pm · ensure_tools · sudo 3단계 동의 · INSTALL_DRY_RUN

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh` (단일 파일)
- **선행**: Task 0
- **목표**: `install.sh` 1/7 단계가 누락 도구(git·curl·python3·jq)를 감지해 **동의를 받은 뒤**
  OS 패키지 매니저로 설치한다. 거부·실패·미지원 PM 이면 정확한 설치 명령을 출력하고 `exit 1`.
  `INSTALL_DRY_RUN=1` 이면 아무것도 설치하지 않고 **계획만 출력**하고 종료한다.
- **재사용**: `개선 후 재사용 install.sh:57-70 (say "1/7 필수 도구 확인" 블록)` — 기존 MISSING
  계산 루프를 확장한다. 프롬프트 헬퍼는 저장소에 없음 — `grep -rn "read -r\|prompt_yes\|confirm"
  --include=*.sh` 로 조사한 결과 `install.sh:172,224` 의 인라인 `read -r` 뿐이므로
  `prompt_yes_no()` 를 **install.sh 안에** 신규 작성한다 (Task 3 의 메뉴 헬퍼가 이걸 재사용한다).
  `INSTALL_PARSE_ONLY` 패턴(`install.sh:35-42`)을 계승해 `INSTALL_DRY_RUN` 을 만든다.
- **실패 테스트**: `tests/test_install_preflight.py` (신규)
  - `INSTALL_DRY_RUN=1 INSTALL_TEST_UNAME=Linux INSTALL_TEST_OS_ID=ubuntu` → 출력에
    `DRY_RUN PM=apt-get` 포함
  - `...OS_ID=fedora` → `DRY_RUN PM=dnf` / `arch` → `pacman` / `alpine` → `apk` /
    `opensuse-leap` → `zypper` / `INSTALL_TEST_UNAME=Darwin` → `brew`
  - 미지원(`INSTALL_TEST_OS_ID=nosuchdistro`) → `DRY_RUN PM=none` + 수동 안내 문구
  - `INSTALL_TEST_MISSING="jq"` → `DRY_RUN MISSING=jq` 와 `DRY_RUN INSTALL_CMD=...jq` 포함
  - `INSTALL_TEST_MISSING=""` → `DRY_RUN MISSING=` (빈 값) 이고 설치 계획 줄이 없음
  - **테스트 실행 중 실제 설치·sudo 호출이 없어야 한다** (DRY_RUN 경로만 탄다)

  > `INSTALL_TEST_*` 오버라이드는 **`INSTALL_DRY_RUN=1` 일 때만** 해석한다 —
  > 실제 설치 경로에서 환경변수로 PM 을 바꿔치기할 수 없어야 한다(보안).

- **구현 지침**:
  - `detect_pm()`: `uname -s` → Linux 면 `. /etc/os-release` (**Linux 한정**, 없으면 none),
    `case $ID in ubuntu|debian) apt-get ;; fedora|rhel|centos) dnf ;; arch|manjaro) pacman ;;
    alpine) apk ;; opensuse*|sles) zypper ;; esac`. Darwin → `brew`.
    `ID_LIKE` 폴백은 선택. 결과를 `PM`·`PM_INSTALL`(설치 서브커맨드)·`PM_SUDO`(1/0)에 담는다.
  - `run_privileged()`: **hermes 3단계** — ① `id -u` = 0 이면 그대로 실행
    ② `sudo -n true` 성공이면 `sudo` ③ 아니면 `prompt_yes_no` 로 동의를 받고 `sudo`
    (동의 거부 시 실패로 처리). 프롬프트는 파이프 환경을 위해 `/dev/tty` 폴백을 쓴다.
    **동의 없이 sudo 를 실행하는 경로가 존재해서는 안 된다.**
  - `ensure_tools()`: 누락 목록 계산 → 없으면 즉시 반환 → 있으면 목록·설치 명령을 보여주고
    **단일 동의** → `run_privileged $PM_INSTALL <목록>` → 설치 후 재검증(`command -v`)해서
    여전히 없으면 실패 처리. 실패·거부·PM=none 이면 정확한 명령을 stderr 로 출력하고 `exit 1`.
  - `INSTALL_DRY_RUN=1`: `DRY_RUN PM=` / `DRY_RUN MISSING=` / `DRY_RUN INSTALL_CMD=` /
    `DRY_RUN PRIVILEGE=<root|sudo-nopass|sudo-consent>` 를 출력하고 **1/7 단계 끝에서 exit 0**.
  - macOS: brew 는 sudo 를 쓰지 않는다(`PM_SUDO=0`). brew 미설치면 PM=none 처리 + 안내.
- **필독 스킬**: 없음
- **필수 규칙**:
  - bash 3.2 호환 (연관배열·`mapfile` 금지). `set -euo pipefail` 유지.
  - 조용한 실패 금지 — 설치 실패는 stderr 로 원인과 수동 명령을 반드시 출력한다.
  - `install.sh` 외 파일 수정 금지(테스트는 Task 4 가 확장하지만, 이 task 의 실패 테스트
    `tests/test_install_preflight.py` 는 여기서 만든다).
  - 기존 `INSTALL_PARSE_ONLY` 동작·인자 파싱·이후 2/7~7/7 단계는 건드리지 말 것.
- **완료 조건**:
  ```bash
  python3 -m unittest discover -s tests -v
  bash -n install.sh
  INSTALL_PARSE_ONLY=1 bash install.sh --claude --providers=qwen typescript   # 기존 출력 그대로
  ```
