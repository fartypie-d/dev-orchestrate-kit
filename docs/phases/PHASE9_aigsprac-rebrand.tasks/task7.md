# Task 7: GitHub 저장소 2개 리네임 + 리모트 갱신 (메인 직접 — GATE 2·병합 후)

- **실행 주체**: 오케스트레이터 (위임 아님 — gh CLI 인프라 작업)
- **선행**: GATE 2 승인 + main 병합 완료
- **절차**:
  1. `gh api -X PATCH repos/ACIF-ai-dev/dev-orchestrate-kit -f name=aigsprac`
  2. `gh api -X PATCH repos/fartypie-d/dev-orchestrate-kit -f name=aigsprac`
  3. `git remote set-url origin git@github.com:ACIF-ai-dev/aigsprac.git`
  4. `git remote set-url public git@github.com:fartypie-d/aigsprac.git`
  5. 확인: `git fetch origin --dry-run && git fetch public --dry-run`
- **비고**: GitHub이 옛 이름 URL을 자동 리다이렉트하므로 기존 클론은 깨지지 않는다.
  외부(GitHub) 변경이므로 GATE 2와 별도로 실행 직전 사용자 확인 1회.
