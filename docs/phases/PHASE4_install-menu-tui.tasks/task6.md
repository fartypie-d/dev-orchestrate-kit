# Task 6: 통합 테스트 + 변이 검증 + 이월 잔무 (6a/6b 분할)

> 이월 잔무 중 **install.sh 수정이 필요한 항목**이 있고 kit-tests 는 `install.sh` 를 고칠 수 없다
> (전파 제약 5) → **6a(kit-tests) → 6b(kit-scripts)** 로 분할한다 (사용자 결정 2026-08-12).

---

## Task 6a: 통합 시나리오 + 변이 검증 + 테스트 잔무
- **에이전트**: kit-tests / **모델**: default
- **대상 파일**: `tests/test_install_wizard.py`, `tests/test_install_menu.py`,
  `tests/test_install_auth_step.py`, `tests/test_install_container_step.py`, `tests/test_install_mcp_step.py`
- **선행**: Task 8b, 9b (없으면 그 시나리오만 제외하고 진행)
- **목표**: Task 3~5·8·9 가 만든 테스트를 통합 시나리오로 묶고, 각 신규 테스트가
  "기능을 지워도 통과하는 항상-참 테스트"가 아님을 변이 검증으로 증명한다.
- **재사용**: 그대로 재사용 `tests/_install_helpers.py`(SELFTEST 실행 헬퍼) — **새 실행 헬퍼 금지**
- **테스트 잔무 (파트 4-1·4-2 리뷰에서 이월)**:
  - `test_tui_eof_falls_back_without_hanging_in_pseudo_tty` 는 이름과 달리 idle-limit 경로를
    검증한다 — 이름을 실검증 대상에 맞게 변경
  - TUI 중 SIGINT(Ctrl-C) 시 3초 내 종료하는 회귀 테스트 추가 (os.setsid + killpg 재현)
  - `install.sh:62` SELFTEST_TUI 예외가 claude/codex 없는 PATH 에서 동작하는지 검증 케이스
  - `INSTALL_SELFTEST_WIZARD` 예외의 검증 케이스, rc=11 경로의 단위 검증
  - **🟠 (4c 이월)** `test_menu_read_has_no_default_idle_timeout` 을 **런타임 pty 검사로 교체** —
    현재 정적 substring 단언이라 `: "${INSTALL_MENU_IDLE_LIMIT:=5}"` 변이를 통과시킨다
  - **(5b 이월)** 실제 `opencode auth login` 실행 분기는 커버리지 0 —
    `$HOME/.opencode/bin/opencode` 자리에 **argv 를 파일로 기록하는 스텁 바이너리**를 두고 검증
  - **(6b 연동)** 6b 가 붙일 두 동작의 테스트를 **먼저** 작성한다:
    ① auth·컨테이너·MCP 실패가 `CLAUDE_INSTALL_FAILED` 집계에 반영돼 마감 문구가 달라진다
    ② `opencode` 바이너리 부재(rc 127)와 로그인 거부가 **다른 경고**로 구분된다
- **필수 규칙**:
  - `INSTALL_PARSE_ONLY` 로 메뉴를 검증하지 말 것 — 반드시 `INSTALL_SELFTEST_MENU` 경로 (CLAUDE.md 함정 1)
  - **변이 검증 필수**: **`.orchestrate/mut6a/`** 안의 install.sh 사본에 변이를 넣고 검증한다.
    ⚠️ `/tmp`·`mktemp -d` 등 **저장소 밖 쓰기 금지** — opencode 가 `external_directory` 로 자동 거부해
    런이 보고 없이 종료된다 (PITFALLS 8). 사용 후 사본 삭제.
    변이 3종: ① 뒤로가기 분기 제거 ② TUI 폴백 조건 반전 ③ auth 프롬프트 조건 제거
  - 실제 홈 오염 금지 — 임시 HOME + 주입 플래그만. 실제 docker·실제 `claude mcp` 호출 금지
  - 새 stdout 마커를 install.sh 에 요구하지 말 것 (기존 테스트가 stdout 전체를 assertEqual)
  - 공유 워크트리에서 `git stash` 금지, `git add` 경로 명시
  - 커버 시나리오 최소: 정방향 전체 선택 / 각 스텝 뒤로가기 1회 / 플래그 지정 시 스텝 스킵 /
    비TTY 폴백 / qwen만·openai 포함 auth 분기 / 컨테이너 스텝 마커(Task 8) / MCP 옵션 분기(Task 9)
- **완료 조건**: `python3 -m unittest discover -s tests -v` — 6b 대기분(위 "6b 연동" 2건)만 RED,
  나머지 전부 GREEN + 변이 검증 표(변이 3종 × 검출 테스트명 × FAIL 확인)

---

## Task 6b: 이월 🟡 구현 (실패 집계·경고 구분)
- **에이전트**: kit-scripts / **모델**: default
- **대상 파일**: `install.sh`
- **선행**: Task 6a
- **목표**: 6a 가 RED 로 고정한 2건을 GREEN 으로 만든다.
  ① auth·컨테이너·MCP 등록 실패를 기존 `CLAUDE_INSTALL_FAILED` 집계(install.sh:1410·1423 분기)에 접합
  ② `opencode` 바이너리 부재(rc 127)와 로그인 거부를 `command -v` 프리체크로 구분해 다른 경고로
- **재사용**: 개선 후 재사용 `CLAUDE_INSTALL_FAILED` 누산기(install.sh:24, 717-748, 1410, 1423 — 호출부 4곳)
  — **새 누산기 변수·새 마감 문구 체계 금지**
- **실패 테스트**: 6a 가 작성한 2건 (RED 확인 후 착수)
- **필수 규칙**:
  - **새 stdout 마커 추가 금지** — 기존 테스트가 stdout 전체를 assertEqual 한다. 경고는 stderr 로.
  - 실패가 설치를 중단시키지 않는다는 기존 비치명 계약(C9)을 깨지 말 것 — 집계만 반영
  - bash 3.2 호환, `tests/*.py` 편집 불가(불일치는 보고), 스크래치 `.orchestrate/mut6b/`
  - `git stash` 금지, `git add` 경로 명시
- **완료 조건**:
  1. `bash -n install.sh` OK
  2. `python3 -m unittest discover -s tests -v` **전부 GREEN**
  3. 변이 검증 1종: 집계 접합 제거 → 6a 의 ① 테스트 FAIL
