# Task 3: 번호 선택 메뉴 (harness·providers·plan·ECC 언어) + 비대화형 스킵

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`
- **선행**: Task 2
- **목표**: free-text `read` 대신 **번호 선택 메뉴**로 harness·providers·plan·ECC 언어를 고른다.
  플래그로 값이 온 항목은 메뉴를 띄우지 않고, 비대화형(`! [ -t 0 ]`)이면 전부 기본값으로 스킵한다.
- **재사용**: `개선 후 재사용 install.sh:166-176 (providers read -r)` 와
  `install.sh:214-233 (plan read -r)` — 두 인라인 프롬프트를 공통 헬퍼로 바꾼다.
  Task 1 의 `prompt_yes_no()` 와 같은 `/dev/tty` 폴백·비대화형 판정 규약을 **재사용**한다
  (같은 판정 로직을 다시 쓰지 말고 한 곳에 모을 것).
- **실패 테스트**: `tests/test_install_menu.py` (신규)
  - 비대화형(stdin 파이프)에서 `--claude --providers=qwen --plan=pro typescript` →
    메뉴 문구가 **출력되지 않고** 기존 파싱 결과가 그대로 나온다 (`INSTALL_PARSE_ONLY=1`)
  - 대화형 시뮬레이션: `printf '1\n' | ...` 로는 `[ -t 0 ]` 이 거짓이므로 **메뉴가 뜨지 않아야**
    한다 (파이프를 대화형으로 오인하지 않는지 검증)
  - 선택 파싱 단위 테스트: `choose_many` 의 입력 정규화(`1,3` / `1 3` / `1,3,` / 빈 입력 /
    범위 밖 `9`)를 **신규 자가진단 훅 `INSTALL_SELFTEST_MENU=1`** 로 검증한다 —
    이 훅은 메뉴 헬퍼만 실행하고 그 결과(`SELFTEST CHOICE=qwen,xai` 형태)를 출력한 뒤
    즉시 종료한다. 설치 흐름을 전혀 타지 않으므로 안전하다.

  > **DRY_RUN 을 메뉴 테스트에 쓰지 말 것 (Task 1 결과 반영)**: `INSTALL_DRY_RUN=1` 은
  > **1/7 프리플라이트 끝에서 `exit 0`** 한다. 메뉴는 6/7·요금제 단계(그 이후)에 있으므로
  > DRY_RUN 경로로는 **도달하지 않는다.** 메뉴 검증은 위의 `INSTALL_SELFTEST_MENU` +
  > `INSTALL_PARSE_ONLY` 조합으로 한다. DRY_RUN 종료 지점을 뒤로 옮기려 하지 말 것 —
  > 2/7 이후는 실제 네트워크·홈 쓰기가 있어 테스트가 실제 시스템을 건드리게 된다.
- **구현 지침**:
  - `choose_one <프롬프트> <기본값> <항목...>` / `choose_many <프롬프트> <기본값> <항목...>`
    두 헬퍼. 항목은 `값:힌트` 형식으로 넘겨 번호·값·힌트를 함께 출력한다.
    (bash 3.2 — 연관배열 금지. 위치 파라미터·`set --`·`$*` 로 구현한다.)
  - 입력 검증: 숫자 아님·범위 밖은 재입력을 요구한다(무한 루프 방지 — 3회 실패 시 기본값).
    빈 입력 = 기본값.
  - 메뉴 항목:
    - harness: `claude` / `codex` / `both` (단일, 기본 = `stamp_detect_harness` 결과)
    - providers: `openai(구독/키)` `xai(구독)` `qwen(키)` `antigravity(키+로컬프록시)` (다중)
    - plan: `pro` `max5` `max20` `skip` (단일, claude 하네스일 때만)
    - ECC 언어: `typescript` `python` `golang` `vue` `react-native` ... (다중, 자유 입력 허용)
      — **언어 미지정 시 메뉴를 유도**한다(도그푸딩 실측 ③: 자산만 깔리고 리뷰어가 없는 상태 방지)
  - **플래그 우선**: `--providers=`·`--plan=`·`--claude/--codex`·위치 인자(ECC 언어)가 있으면
    해당 항목 메뉴는 **띄우지 않는다**.
  - 비대화형이면 모든 메뉴 스킵 + 기존과 동일한 안내 문구를 유지한다.
- **필독 스킬**: 없음
- **필수 규칙**:
  - bash 3.2 호환. `INSTALL_PARSE_ONLY` 경로는 인자 파싱 직후 종료하므로 **메뉴보다 앞**이어야
    한다 (기존 테스트 `tests/test_install_args.py` 8건이 계속 통과해야 한다).
  - 기존 테스트가 검사하는 문자열
    (`'if [ -t 0 ]; then'`, `'비대화형 실행 — --providers= ...'`)이 사라지면 테스트가 깨진다 —
    문구를 바꿔야 한다면 Task 4 에서 테스트를 함께 갱신하도록 **보고에 명시**할 것.
  - `install.sh` 외 수정 금지(신규 테스트 파일 제외).
- **완료 조건**:
  ```bash
  python3 -m unittest discover -s tests -v
  bash -n install.sh
  printf '' | INSTALL_DRY_RUN=1 bash install.sh --claude    # 메뉴 없이 계획만 출력
  ```
