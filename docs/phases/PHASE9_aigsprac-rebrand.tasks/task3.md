# Task 3: install.sh 헤더 주석 개칭

- **에이전트**: kit-scripts
- **모델**: heavy (⚠️ 도메인 — 설치 스크립트)
- **대상 파일**: `install.sh` (1개 — 이 외 수정 금지)
- **선행**: Task 0
- **목표**: `install.sh:2` 헤더 주석의 `dev-orchestrate-kit` → `aigsprac`. 코드 로직은
  단 한 글자도 변경하지 않는다.
- **재사용**: 없음 — 주석 1곳 치환
- **실패 테스트**: 불가 — 주석 1곳 (대체 검증: `bash -n` + 기존 unittest 전체 + 리뷰어)
- **필수 규칙**: 실측상 옛 이름은 2행 주석 1곳뿐이다. 다른 라인·문자열·변수를 건드리면 반려.
- **금지**: 로직·메뉴 문구 수정, 대상 외 파일 수정, `tests/` 수정, `git commit`.
- **완료 조건**:
  - `grep -c dev-orchestrate-kit install.sh` → 0
  - `bash -n install.sh` 통과, `python3 -m unittest discover -s tests -v` 전체 통과
  - `git diff --stat` 이 `install.sh` 1파일 ±1라인만 표시
