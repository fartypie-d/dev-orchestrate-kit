# Task 5: README·런북·"남은 수동 단계" 갱신

- **에이전트**: kit-docs
- **모델**: heavy
- **대상 파일**: `README.md`, `docs/` 하위 런북(설치 절차를 다루는 파일 — `grep -rn "install.sh"
  README.md docs/` 로 확정), `install.sh` 의 "남은 수동 단계" heredoc은 **Task 2/3 이 이미 갱신**
  하므로 문서 쪽만 맞춘다
- **선행**: Task 4
- **목표**: 새 설치 UX(자동 도구 설치·동의 프롬프트·번호 선택 메뉴·`INSTALL_DRY_RUN`)를 문서가
  정확히 설명한다. 도그푸딩 실측 ③(**ECC 언어 인자 누락**)이 재발하지 않도록 예시에 언어 인자를
  포함한다.
- **재사용**: `개선 후 재사용 README.md 의 설치 절 + docs/ 런북` — 새 문서를 만들지 말고
  기존 절을 고친다. 중복 설명이 두 곳에 생기면 한쪽을 링크로 대체한다.
- **실패 테스트**: 작성 불가 — 마크다운 문서 변경.
  **대체 검증**(로스터 규정): 문서에 나오는 모든 경로·명령이 실재하는지 `ls`·`grep` 으로 확인하고
  그 출력을 보고에 첨부한다 + code-reviewer 검수.
- **반영할 내용**:
  1. `./install.sh` 가 git·curl·python3·jq 누락 시 **동의를 받아** 설치한다는 것과,
     거부 시 수동 명령이 출력된다는 것.
  2. `--claude` 사용 시 claude CLI 자동 설치 동의 흐름과 실패 시 수동 명령.
  3. 번호 선택 메뉴가 뜨는 항목(harness·providers·plan·ECC 언어)과 **플래그로 스킵**하는 법.
  4. 비대화형/CI 사용법: 모든 값을 플래그로 주는 예 1줄 +
     `INSTALL_DRY_RUN=1` 로 계획만 확인하는 예 1줄.
  5. ECC 언어 인자 예시를 **모든 설치 예제에 포함**
     (`./install.sh --claude --providers=openai,xai --plan=max20 typescript python`).
  6. 실행비트 관련: `git clone` 후 바로 `./install.sh` 가 실행되는지(`3eb285f`) 확인 문구.
- **필수 규칙**:
  - 존재하지 않는 플래그·경로를 쓰지 말 것 — 실제 `install.sh` 를 읽고 사실만 쓴다.
  - 소스 코드(`install.sh` 포함) 수정 금지 — 이 task 는 문서 전용이다.
  - 한국어 문서 톤·기존 구조를 유지한다.
- **완료 조건**:
  ```bash
  grep -n "INSTALL_DRY_RUN\|--providers=\|--plan=" README.md docs/*.md
  bash -n install.sh                                  # 문서 작업이 스크립트를 건드리지 않았는지
  python3 -m unittest discover -s tests -v            # 회귀 없음
  ```
