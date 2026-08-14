# Task 3: TUI 엔진 — 방향키 choose_one · 체크박스 choose_many

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`, `tests/test_install_menu.py` (pin 테스트·키 파서 테스트)
  - (3회차 스코프 완화, 2026-08-11 사용자 승인): `tests/test_install_claude_bootstrap.py` 추가 —
    pty 자동화가 TUI 경로를 타며 30초 타임아웃 (pty는 EOF 미전달 → 유휴 상한 120초 대기).
    자동화 테스트에 `INSTALL_PLAIN_MENU=1` 주입으로 해소 (자동화=번호 입력 경로가 설계 의도)
- **선행**: Task 1
- **목표**: TTY에서 `choose_one`은 방향키(↑↓) 하이라이트 + Enter 선택, `choose_many`는 체크박스
  (스페이스 토글, `[x]` 표시) + Enter 확정으로 동작한다. 비TTY·`INSTALL_SELFTEST_MENU=1`·
  `INSTALL_PLAIN_MENU=1`에서는 기존 번호 입력 UI가 바이트 단위로 그대로 유지된다.
- **재사용**: 개선 후 재사용 `install.sh:144-260` `choose_one`/`choose_many` (호출부 4곳: 726·758·864·913) —
  함수 시그니처(인자·stdout 반환값 형식) 절대 불변. 내부에서 TTY면 TUI 렌더러, 아니면 기존 루프로 분기.
- **실패 테스트**: `tests/test_install_menu.py::test_selftest_number_input_still_works` —
  `INSTALL_SELFTEST_MENU=1` + 번호 입력 주입 시 기존과 동일한 선택 결과·출력을 검증 (TUI 코드 미실행).
  RED 확인 방법: 테스트를 먼저 쓰고, TUI 분기를 의도적으로 SELFTEST 경로에도 타게 한 상태를 가정한
  구현 전 실패를 확인할 수 없으므로 — **기존 동작 고정(pin) 테스트로 먼저 GREEN 확인 후, 구현 중
  회귀하면 RED가 되는 가드**로 운용한다. 추가로 TUI 키 파서(ESC 시퀀스 → 동작 토큰)는 순수 함수로
  분리해 `INSTALL_SELFTEST_KEYPARSE=1` 셀프테스트 훅으로 단위 검증한다 (이건 선-RED 가능).
- **필수 규칙** (bash 3.2 호환이 최상위 제약):
  - 금지: 연관배열(`declare -A`), `mapfile`/`readarray`, `${v,,}`/`${v^^}`, 소수점 `read -t 0.1`
    (3.2는 정수 초만), `;&`/`;;&`. `read -rsn1`은 3.2에서 동작 — 사용 가능.
  - 방향키 = `ESC [ A/B`. ESC 단독 판별은 `read -rsn2 -t 1`류 정수 타임아웃으로 처리.
  - 렌더링은 stderr, 반환값은 stdout printf (현행 계약 유지). ANSI는 최소만
    (커서 이동·반전·지우기). `tput` 의존 금지. `$TERM`이 dumb/빈값이면 번호 입력 폴백.
  - TUI 활성 조건: `is_interactive_menu` && stderr가 TTY && SELFTEST·PLAIN 아님.
  - `choose_many`의 직접 입력 허용(3번째 인자=1)은 TUI에서 "직접 입력…" 항목으로 제공 —
    선택 시 라인 입력으로 전환.
  - 조작 안내 한 줄을 메뉴 하단에 표시 (↑↓ 이동 · 스페이스 선택 · Enter 확정).
- **완료 조건**: `bash -n install.sh` + `python3 -m unittest discover -s tests -v` 전부 GREEN
  (신규 pin 테스트 포함). 수동 스모크는 Task 6의 변이 검증과 GATE 2 데모로 확인.
