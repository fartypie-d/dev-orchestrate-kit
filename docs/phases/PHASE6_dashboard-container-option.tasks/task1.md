# Task 1: 동결 회귀 테스트 (RED)

- **에이전트**: 오케스트레이터 직접 (PITFALLS 14 — 회귀 테스트는 오케스트레이터가 작성·동결)
- **대상 파일**: `tests/test_install_dashboard_container.py` (신규)
- **선행**: 없음
- **목표**: dashboard 컨테이너 계약을 RED 로 고정한다. Task 2 완료 시 전부 GREEN 이 되어야 한다.
- **재사용**: 그대로 재사용 `tests/_install_helpers.py`:`run_install`·`run_install_with_fake_tools`·`temporary_directory`
- **실패 테스트** (이 task 의 산출물 자체):
  - `test_dashboard_selftest_would_run` — `INSTALL_SELFTEST_CONTAINERS=1 INSTALL_CONTAINERS=dashboard`
    → `CONTAINER_SUBMODULE_WOULD_INIT=dashboard` + `CONTAINER_INSTALL_WOULD_RUN=dashboard ...`
    (`components/usage-dashboard` 경로 + `up -d` 포함, INIT < RUN 순서)
  - `test_both_containers_selftest` — `INSTALL_CONTAINERS=browser,dashboard` → 두 컨테이너 각각의
    WOULD_RUN, browser 는 `containers/browser`, dashboard 는 `components/usage-dashboard` 경로
  - `test_wizard_dashboard_item` — 마법사 컨테이너 스텝에서 번호 2 선택 → `SELFTEST WIZARD CONTAINERS=dashboard`
  - `test_wizard_both_containers_preserved` — "1,2" 선택 → `SELFTEST WIZARD CONTAINERS=browser,dashboard`
  - `test_dashboard_fake_reasons` — fake `docker_missing`·`port_busy`·consent `n` 이 각각
    `CONTAINER_INSTALL_SKIPPED=dashboard reason=...` 을 남긴다
  - `test_dashboard_real_startup_uses_own_port_and_compose` — 스텁 docker/git 실기동 경로:
    docker argv 에 `components/usage-dashboard` compose 경로, 포트 검사는 `INSTALL_DASH_PORT`
    주입값(9280 기본) 기준(주입 포트를 리스너로 점유하면 skip), browser 문구 미출현
- **필독 스킬**: 없음
- **필수 규칙**: 변이 검증 — `.orchestrate/mutation/` 에 저장소 전체 사본을 만들어 Task 2 구현 후
  대상 로직을 깨뜨려 테스트가 실제 FAIL 하는지 확인 (PITFALLS 15, 저장소 밖·부분 사본 금지).
  기존 `test_install_container_step.py` 는 수정하지 않는다.
- **완료 조건**: `python3 -m unittest tests.test_install_dashboard_container -v` 가 **전건 FAIL(RED)**
  하고, 실패 범위가 dashboard 미구현에 국한됨 (다른 테스트는 무영향). RED 시점 변이 검증은
  하지 않는다 (PITFALLS 21 — 변이 검증은 구현 task 완료 조건).
