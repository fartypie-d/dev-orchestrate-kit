# Task 4: DRY_RUN·PM·메뉴 스킵 unittest 통합·보강

- **에이전트**: kit-tests
- **모델**: heavy
- **대상 파일**: `tests/test_install_preflight.py`, `tests/test_install_claude_bootstrap.py`,
  `tests/test_install_menu.py` (Task 1~3 이 만든 것) + 필요 시 `tests/test_install_args.py`
- **선행**: Task 3
- **목표**: Task 1~3 이 각자 만든 실패 테스트를 **한 벌로 정리**하고 빠진 경계를 채운다.
  전체 `python3 -m unittest discover -s tests -v` 가 통과하며, 테스트가 실제 홈·패키지 매니저·
  네트워크를 건드리지 않음을 보장한다.
- **재사용**: `개선 후 재사용 tests/test_install_args.py:10 (parse() 헬퍼)` — 서브프로세스 호출
  헬퍼가 4개 파일에 중복되면 **공용 헬퍼로 추출**한다 (`tests/_install_helpers.py` 또는
  `tests/test_install_args.py` 의 것을 import). 새 헬퍼를 파일마다 복사하지 말 것.
  기존 테스트 8건(`test_install_args.py`)의 의도를 **깨지 않고** 유지한다.
- **실패 테스트**: (이 task 자체가 테스트다 — 먼저 실패하는 케이스를 추가하고 채운다)
  - 보강할 경계:
    1. `INSTALL_DRY_RUN=1` 실행이 `$HOME` 아래 어떤 파일도 만들지 않는다
       (임시 `HOME=` 을 주입해 실행 전후 디렉터리 스냅샷 비교)
    2. `INSTALL_TEST_*` 오버라이드가 `INSTALL_DRY_RUN` 없이는 **무시**된다
       (`INSTALL_PARSE_ONLY=1` 경로로 확인 — 실제 설치는 실행하지 않는다)
    3. 미지원 PM 에서 수동 명령 안내 문구가 출력되고 종료 코드가 규약대로다
    4. `--claude` 없이 `--codex` 만일 때 claude 부트스트랩 계획이 없다
    5. 알 수 없는 옵션 exit 64 유지, `--plan=` 파싱 유지 (회귀 방지)
- **필독 스킬**: 없음
- **필수 규칙**:
  - **pytest 아님** — `python3 -m unittest` 로 돌아가야 한다 (저장소 표준).
  - 테스트는 반드시 임시 디렉터리·주입 환경변수만 쓴다. 실제 `~/.claude`·`~/.config`·
    `~/.local` 을 건드리는 테스트를 작성하지 말 것 (CLAUDE.md 실측 함정).
  - 네트워크를 타는 테스트 금지 (claude/Node 설치는 DRY_RUN 계획 출력으로만 검증).
  - `install.sh` 를 수정하지 말 것 — 테스트가 실패하면 **원인을 보고**한다
    (구현 수정은 재위임으로 처리한다).
- **완료 조건**:
  ```bash
  python3 -m unittest discover -s tests -v      # 전부 통과, 실패 0
  ```
  보고에 **테스트 개수와 전체 출력 tail** 을 첨부한다.
