# Task 2: install.sh dashboard 컨테이너 + 파이프라인 일반화

- **에이전트**: kit-scripts
- **모델**: heavy (⚠️ 도메인 — 설치 스크립트)
- **대상 파일**: `install.sh` (저장소 루트 실파일 1개만)
- **선행**: Task 1 (동결 테스트가 RED 로 존재)
- **목표**: `--containers=browser,dashboard` 와 마법사 컨테이너 스텝의 dashboard 항목으로
  usage-dashboard 서브모듈(`components/usage-dashboard`)을 init 하고 동의 후 `docker compose up -d`
  로 기동한다. 실패는 전부 비치명 + 수동 안내 (browser 와 동일 UX).
- **재사용**: 개선 후 재사용 `install.sh`:`build_container_up_argv`·컨테이너 실기동 루프·
  `INSTALL_SELFTEST_CONTAINERS` 블록·마법사 컨테이너 스텝 (호출부 4곳 — 전부 install.sh 안)
- **실패 테스트**: `tests/test_install_dashboard_container.py` (Task 1 이 동결 — **수정 금지**,
  먼저 실행해 RED 확인 후 구현)
- **필독 스킬**: 없음
- **필수 규칙**:
  - `up -d` 문자열은 `build_container_up_argv` 함수 밖에 쓰지 말 것 (기존 테스트가 고정).
  - compose 서비스명을 install.sh 에 쓰지 말 것 (compose 파일 경로까지만).
  - 실기동 루프의 browser 하드코딩(서브모듈 경로 존재검사·`$CDP_PORT`·"browser:" 문구·동의 프롬프트)을
    컨테이너별 분기/헬퍼로 일반화. 포트: `DASH_PORT="${INSTALL_DASH_PORT:-9280}"` 를 `CDP_PORT` 와
    동형으로 단일 소스 신설.
  - 마법사 항목 순서: browser(1)·dashboard(2)·mcp(3, claude 시). 조합부는 browser·dashboard 를
    모두 보존하도록 일반화. mcp→browser 의존성 로직은 불변.
  - `tests/` 수정 금지. `bash -n install.sh` 통과. bash 3.2 호환 (연관배열·`${var,,}` 금지).
  - `git commit`·docker 실행 금지. 대상 파일 외 수정 금지.
- **완료 조건**: ① `python3 -m unittest tests.test_install_dashboard_container -v` 전건 PASS
  ② `python3 -m unittest tests.test_install_container_step -v` 기존 12건 무수정 PASS
  ③ `bash -n install.sh` 통과. 완료 후 수정 파일 목록 + 테스트 출력 보고.
