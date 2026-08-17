# Task 2: README EN·KO quickstart 명확화

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `README.md`(영문), `README.ko.md`
- **선행**: 없음
- **목표**: quickstart에서 ① 하네스 플래그(`--claude`/`--codex`)가 "오케스트레이터 쪽 선택"이고
  opencode는 항상 실행자로 설치됨 ② `install.sh`는 홈 전역 설치이고 프로젝트 적용은
  `new-project.sh`/`adopt-project.sh`라는 2단 구조 — 두 가지를 명시한다.
  (클린 호스트 사용자가 실제로 두 번 혼동한 지점.)
- **재사용**: 개선 후 재사용 `README.md:64-75`·`README.ko.md:53-63` quickstart 코드블록 (다른 절 구조 변경 금지)
- **실패 테스트**: 불가 사유 — markdown 문서. 대체 검증: 링크·경로 실재 확인(`ls`·`grep`) + 리뷰어 검수
- **필수 규칙**:
  - EN 주석 예: `# Once per machine — installs GLOBAL assets to $HOME (orchestrator harness: Claude Code and/or Codex; opencode is always installed as the delegation executor)` 취지. 두 줄로 나눠도 좋다.
  - `new-project.sh`/`adopt-project.sh` 줄에 "applies the kit to a project directory" 취지 명시.
  - EN·KO 내용 동기 유지 (같은 정보, 같은 순서).
  - "하네스 조합" / "Harness combos" 표 절에도 한 줄 주석: 표의 두 행 모두 실행자는 opencode라는 점.
- **완료 조건**: `grep -n "opencode" README.md README.ko.md`로 quickstart 절에 실행자 명시 확인 +
  문서 내 참조 경로(스크립트 파일명) 실재 확인
