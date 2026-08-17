# Task 1: README.md·README.ko.md 리브랜딩 + 백로님 스토리

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `README.md`, `README.ko.md` (2개 — 이 외 수정 금지)
- **선행**: Task 0 (가드 테스트 동결)
- **목표**: 두 README의 제품명을 `dev-orchestrate-kit` → `aigsprac`으로 바꾸고,
  백로님 스토리 절을 추가하며, 영/국문이 동일 구조를 유지한다.
- **재사용**: 없음 — `grep -rn aigsprac` 조사 결과 신규 명칭, 기존 자산 없음
- **실패 테스트**: `tests/test_rebrand.py::test_readme_rebranded` — 두 README 1행에
  `aigsprac` 포함 + 본문에 `AI General Staff` 포함 + `구 dev-orchestrate-kit`/
  `formerly dev-orchestrate-kit` 표기 존재를 검증 (오케스트레이터 동결 — 수정 금지)
- **필수 규칙**:
  - 표기는 항상 전부 소문자 `aigsprac` (문두에서도 대문자화하지 않는다).
  - 제목 라인: `# aigsprac` + 부제. 제목 근처에 구명 표기 1회:
    영문 `> formerly **dev-orchestrate-kit**` / 국문 `> 구 **dev-orchestrate-kit**`.
  - 백로님 스토리 절(“Why the name” / “이름의 유래”)을 Why 절 앞이나 뒤에 추가 — 요지
    (표현은 다듬되 내용 고정):
    - EN: *aigsprac = "AI General Staff practice". The supervisor harness is the
      general staff — it only plans, reviews, and approves; implementation is
      carried out by delegated field agents (opencode) running on the
      subscriptions you already pay for.*
    - KO: *aigsprac은 "AI General Staff practice" — 오케스트레이터는 참모본부로서
      계획·검토·승인만 맡고, 실행은 이미 구독 중인 모델들 위의 예하 부대(opencode
      위임 에이전트)가 수행한다.*
  - 클론 URL·경로 예시 속 `dev-orchestrate-kit` 도 `aigsprac`으로 (GitHub 리다이렉트가
    있으므로 새 이름 기준으로 적는다).
  - 영/국문 상호 링크(`README.ko.md` ↔ `README.md`)와 배지·이미지 경로는 깨뜨리지 않는다.
- **금지**: 대상 2파일 외 수정 (특히 `core/project-template/`·`docs/plans/`·`docs/phases/`
  는 절대 건드리지 않는다), `tests/` 수정, `git commit`.
- **완료 조건**:
  - `python3 -m unittest tests.test_rebrand -v` 전체 통과 (구현 전 `test_readme_rebranded`
    실패 확인 출력 첨부)
  - `grep -c dev-orchestrate-kit README.md README.ko.md` → 각 1 이하(구명 표기만)
