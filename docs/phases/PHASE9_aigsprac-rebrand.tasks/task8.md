# Task 8: 로컬 디렉터리 리네임 + Claude Code 메모리 이주 (메인 직접 — 페이즈 마감 직전)

- **실행 주체**: 오케스트레이터 (위임 아님)
- **선행**: Task 7 + `phase-close.sh 9` (워크트리 제거가 디렉터리 이동보다 먼저여야 안전)
- **절차**:
  1. `cp -r ~/.claude/projects/-home-jh-dev-orchestrate-kit ~/.claude/projects/-home-jh-aigsprac`
     (메모리·세션 키 복사 — 원본은 남겨 두어 롤백 가능)
  2. `mv /home/jh/dev-orchestrate-kit /home/jh/aigsprac`
  3. 사용자 안내: **이 세션 종료 → `/home/jh/aigsprac` 에서 새 세션 시작** (다음 페이즈 ②).
- **비고**: 현재 세션의 cwd가 옛 경로이므로 mv 는 반드시 세션 마지막 행동. mv 이후 이
  세션에서는 저장소 파일 작업 금지.
