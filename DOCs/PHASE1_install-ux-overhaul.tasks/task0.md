# Task 0: bash-guard 단어경계 오탐 수정

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**:
  - `adapters/claude/project/.claude/hooks/bash-guard.sh` (배포 원본)
  - `.claude/hooks/bash-guard.sh` (이 저장소 도그푸딩 사본 — 원본과 **바이트 동일**하게 유지)
  - `tests/test_bash_guard.py` (신규)
- **선행**: 없음
- **목표**: 가드가 `sudo`·`rm -rf` 를 **부분 문자열이 아니라 명령 토큰(단어 경계)** 으로 판정한다.
  `git commit -m "... sudo ..."` 같이 인용문 안에서 언급만 된 경우는 통과시키고,
  실제 실행되는 `sudo ls`·`| sudo tee`·`&& sudo -n true` 는 계속 차단한다.
- **재사용**: `개선 후 재사용 .claude/hooks/bash-guard.sh:case "$CMD" in *sudo*` — 기존 가드를
  고친다. **새 가드 스크립트를 만들지 말 것.** 호출부 3곳:
  `.claude/settings.json:43`, `adapters/claude/project/.claude/settings.json:43`,
  `core/scripts/hook-selfcheck.sh:11,13,15`(기존 자가진단 3케이스는 계속 통과해야 한다).
- **실패 테스트**: `tests/test_bash_guard.py::BashGuardTest`
  — 훅에 `{"tool_input":{"command": ...}}` JSON 을 stdin 으로 주고 exit code 를 검증한다
  (2 = 차단, 0 = 통과). 최소 케이스:
  - 차단(2): `sudo ls` / `apt-get install -y jq && sudo true` / `echo x | sudo tee /etc/f`
    / `rm -rf /tmp/x` / `git push origin main` / `git push --force`
  - 통과(0): `git commit -m "docs: sudo 자동 설치 설계"` (**이번 오탐 실측 케이스**)
    / `git commit -m "fix: rm -rf 가드"` / `echo "no sudo here"` 처럼 인용문 내부 언급
    / `grep -rn sudo install.sh` 는 **판단 필요** — 아래 규칙 참조
  - 두 사본이 동일한지 확인하는 테스트 1개 (`filecmp.cmp(..., shallow=False)`)
- **판정 규칙(구현 지침)**:
  - 명령 토큰 위치에서만 매칭한다 — 줄 시작, `;` `&&` `||` `|` `(` `{` 뒤, 그리고
    `env`·`nohup` 등 접두 명령 뒤. bash 3.2 호환 `grep -E` 로 구현한다
    (연관배열·`mapfile`·`=~` 의 bash4 전용 기능 금지).
  - 인용부호 안의 문자열은 명령이 아니다 — 단순화를 위해 **`-m "..."`/`'...'` 인자 내부**를
    제거한 뒤 판정하는 방식(sed 로 따옴표 구간 제거)을 권장한다. 완벽한 셸 파서를 만들지 말 것.
  - 오탐을 줄이되 **미탐(실제 sudo 실행을 통과시키는 것)은 절대 허용하지 않는다** —
    애매하면 차단 쪽으로 판정하고, 그 근거를 주석 한 줄로 남긴다.
  - `rm -rf`·`git push main`·`force push` 규칙도 같은 토큰 기준으로 정리한다.
- **필독 스킬**: 없음 (bash 표준)
- **필수 규칙**:
  - 두 사본을 **함께** 수정한다. 한쪽만 고치면 hook-selfcheck 와 배포본이 갈라진다.
  - 컨테이너 등급 변수(`FORBIDDEN`/`RESTART_ONLY`/`FOREIGN`)와 docker 규칙은 **건드리지 말 것**.
  - `git commit`·`git push`·docker 조작·패키지 설치 금지.
- **완료 조건**:
  ```bash
  python3 -m unittest discover -s tests -v      # 전부 통과 (신규 test_bash_guard 포함)
  bash scripts/hook-selfcheck.sh                # HOOK_SELFCHECK_PASS
  bash -n .claude/hooks/bash-guard.sh adapters/claude/project/.claude/hooks/bash-guard.sh
  ```
