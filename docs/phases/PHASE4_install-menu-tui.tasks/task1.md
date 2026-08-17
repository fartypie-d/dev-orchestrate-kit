# Task 1: 하네스 메뉴 문구 명확화 + 전역 설치 안내 배너

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`
- **선행**: 없음
- **목표**: 하네스 메뉴가 "오케스트레이터 하네스 선택"임을 명확히 하고(실행자 opencode는 공통 설치),
  설치 시작 시 "이 설치는 $HOME 전역 설치, 프로젝트 적용은 new-project.sh/adopt-project.sh"임을 안내한다.
  클린 호스트 실측에서 두 혼동이 모두 실제 발생했다.
- **재사용**: 개선 후 재사용 `install.sh:726-727` choose_one 호출 (호출부 1곳) — 새 함수 금지, 인자 문구만 교체
- **실패 테스트**: 불가 사유 — 출력 문구 변경만이며 분기·동작 변화 없음.
  대체 검증: ① `bash -n install.sh` ② `INSTALL_SELFTEST_MENU=1 bash install.sh` 출력에 기존
  하네스 메뉴 경로가 그대로 통과(기존 tests/test_install_menu.py 전부 GREEN) ③ 새 문구 grep 확인
- **필수 규칙**:
  - 하네스 메뉴는 정확히 이 문구로 (사용자 승인 완료):
    - 프롬프트: `오케스트레이터 하네스를 고른다 (실행자 opencode는 공통 설치)`
    - 항목: `claude:Claude Code에서 오케스트레이션` / `codex:Codex CLI에서 오케스트레이션` / `both:둘 다`
  - 전역 설치 배너: 스크립트 대화 시작 직전(하네스 메뉴 이전)에 1~2줄 —
    "이 설치는 $HOME 전역 설정(~/.claude, ~/.config/opencode)을 배치한다. 킷 클론 디렉토리에는 설치하지 않는다.
    프로젝트 적용은 ./new-project.sh · ./adopt-project.sh" 취지. `say`/`note` 기존 헬퍼 사용.
  - `notify_noninteractive_harness` 문구(테스트가 참조: `비대화형 실행 — 하네스 자동 감지값(`)는 건드리지 않는다.
  - bash 3.2 호환 문법 유지.
- **완료 조건**: `bash -n install.sh` 통과 + `python3 -m unittest discover -s tests -v` 전부 GREEN
  + `grep -n "오케스트레이터 하네스를 고른다" install.sh` 소스 정적 매칭 (승인 문구 3종 diff 대조)
  - (정정 2026-08-11: 최초 조건이던 SELFTEST 실행 grep은 구조적으로 불가 — SELFTEST 분기는
    하네스 메뉴 도달 전 exit 0. task-orchestrator 에스컬레이션으로 발견, 정적 대조로 대체)
