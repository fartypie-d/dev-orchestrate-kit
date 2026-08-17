# Task 2: `install.sh` dashboard 기동 경로에 생성·주입 배선

- **에이전트**: `kit-scripts`
- **모델**: heavy
- **대상 파일**: `install.sh` (단 하나)
- **선행**: Task 1
- **목표**: `--containers=dashboard` 로 대시보드를 기동할 때 Task 1 의 생성기를 먼저 돌리고,
  override 파일이 **실제로 존재할 때만** `docker compose -f <base> -f <override> up -d` 로
  두 번째 `-f` 를 붙인다. 없으면 기존과 완전히 동일한 argv 를 유지한다.

- **재사용**:
  - `개선 후 재사용 install.sh:build_container_up_argv()` (install.sh:1184, 호출부 2곳 —
    `container_up_command()` install.sh:1193, 컨테이너 기동 루프 install.sh:1617 부근).
    `container_up_command()` 가 사용자에게 출력하는 수동 실행 명령도 **자동으로 같이 갱신**되어야
    한다 — 그래서 argv 조립부 한 곳만 고친다. 새 함수를 만들어 분기하지 말 것.
  - `그대로 재사용 install.sh:$KIT_DIR` — 경로 기준.
  - `없음 — "ORCH_STATE_DIR"·"phase-tools" 로 install.sh 조사, 기존 호출 없음.`

## 배선 규격

1. 대시보드 기동 직전(compose 파일 존재 확인·docker 확인 이후, `prompt_yes_no` 이전)에
   `python3 "$KIT_DIR/scripts/phase-tools.py" dashboard-mounts` 를 실행한다.
   - `python3` 가 없으면 **조용히 건너뛴다** (note 한 줄, 기동은 계속).
   - 생성기가 0 이 아닌 코드로 끝나도 **기동을 막지 않는다** — note 한 줄 후 계속.
2. override 경로는 `${ORCH_STATE_DIR:-$HOME/.local/state/orchestrate}/dashboard-compose.override.yml`.
   `build_container_up_argv dashboard` 는 **그 파일이 `-f` 로 붙일 수 있게 존재할 때만**
   `-f "$_dash_override"` 를 추가한다.
3. `INSTALL_DRY_RUN` 경로에서도 같은 판정이 적용되어야 한다 (테스트가 argv 를 그 경로로 관찰한다).
4. bash 3.2 호환 — `[[ ]]` 대신 `[ ]`, 배열은 기존 스타일 유지.

- **실패 테스트** (오케스트레이터가 이미 작성·동결 — **`tests/` 를 수정하지 말 것**):
  - `tests/test_install_dashboard_container.py::test_startup_omits_override_when_absent`
    — override 가 없을 때 argv 가 `^<compose><-f><...docker-compose.yml><up><-d>$` 그대로일 것
  - `tests/test_install_dashboard_container.py::test_startup_appends_override_when_present`
    — override 가 있을 때 두 번째 `-f` 가 base 다음·`up` 앞에 정확히 한 번 들어갈 것
  - 기존 `tests/test_install_dashboard_container.py` 의 앵커 정규식(구 191행)은 오케스트레이터가
    이미 갱신했다. **테스트가 기대하는 argv 순서에 구현을 맞출 것** (PITFALLS 23 계열 회귀 방지).
  - 테스트는 `ORCH_STATE_DIR`·`HOME` 을 임시 디렉터리로 주입한다. 실제 홈을 읽는 코드를 넣지 말 것.

- **필독 스킬**: `bash-scripting`
- **필수 규칙**:
  - `set -u` 안전: 미정의 변수 참조 금지 (`${VAR:-}` 형태로).
  - 생성기 호출 실패가 설치 전체를 죽이면 안 된다 — 대시보드는 **선택 컨테이너**다.
  - 사용자에게 출력하는 수동 명령(`container_up_command`)과 실제 실행 argv 가 **달라지면 안 된다**.
  - browser 컨테이너 경로 동작을 바꾸지 말 것.

- **완료 조건**:
  1. `python3 -m unittest tests.test_install_dashboard_container -v` → 전부 통과
  2. `python3 -m unittest discover -s tests` → 회귀 없음
  3. `bash -n install.sh` 통과
  4. 변이 검증: `.orchestrate/mut2/` 사본에서 override 존재 검사를 제거해 항상 `-f` 를 붙이게 하면
     `test_startup_omits_override_when_absent` 가 **실패**해야 한다
