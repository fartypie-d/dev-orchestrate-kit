# Task 3: README 2종에 재생성 절차 문서화

- **에이전트**: `kit-docs`
- **모델**: default
- **대상 파일**: `README.md`, `README.ko.md` (2개. 다른 문서는 건드리지 말 것)
- **선행**: Task 1, Task 2
- **목표**: usage-dashboard 절(README.md:147~, README.ko.md:130~)에
  **프로젝트 진행내역 문서 마운트가 레지스트리에서 자동 생성된다는 사실**과
  **새 프로젝트 등록 후 재생성하는 한 줄**을 추가한다.

- **재사용**:
  - `개선 후 재사용 README.md:147 "usage-dashboard — session observability (submodule)" 절` —
    새 절을 만들지 말고 기존 절 안에 소절로 넣는다.
  - `개선 후 재사용 README.ko.md:130 "usage-dashboard — 세션 관측 대시보드 (서브모듈)" 절` — 동일.
  - `없음 — "dashboard-mounts" 로 문서 전역 조사, 기존 언급 없음.`

## 문서에 반드시 들어갈 내용

1. 대시보드는 프로젝트별 진행내역 문서를 **호스트 절대경로 그대로** 연다 → 컨테이너에 그 경로가
   마운트돼 있어야 한다. 안 그러면 UI 가 "문서 없음"이 된다.
2. `./install.sh --containers=dashboard` 가 오케스트레이트 레지스트리를 읽어
   `~/.local/state/orchestrate/dashboard-compose.override.yml` 을 생성하고 compose 에 얹는다.
3. 새 프로젝트를 등록했거나 DOCs 경로가 바뀌면 **재생성 + 재기동**:

   ```bash
   python3 scripts/phase-tools.py dashboard-mounts
   docker compose -f components/usage-dashboard/docker-compose.yml \
     -f ~/.local/state/orchestrate/dashboard-compose.override.yml up -d
   ```
4. 존재하지 않는 DOCs 디렉터리는 마운트하지 않는다 (docker 가 root 소유 빈 디렉터리를 만드는 것 방지).
5. 영문/국문 내용이 **의미상 동일**해야 한다. 영문 README 는 영어로, 국문 README 는 한국어로.

- **실패 테스트**: 작성 불가 — 문서 변경.
  └ **대체 검증**: `python3 -m unittest tests.test_docs_index -v` 통과 +
    `grep -n "dashboard-mounts" README.md README.ko.md` 가 양쪽에서 매칭
    (로스터의 문서 task 대체 검증 규약)

- **필독 스킬**: `technical-writing`
- **필수 규칙**:
  - 존재하지 않는 옵션·경로를 쓰지 말 것 — Task 1/2 가 실제로 구현한 경로만 쓴다
    (`dashboard-mounts` 서브커맨드, `~/.local/state/orchestrate/dashboard-compose.override.yml`).
  - 사설 저장소(`~/usage-dashboard`)나 호스트 개인 경로를 문서에 넣지 말 것.
  - 기존 문단 구조·헤딩 레벨을 유지하고 순수 추가로.
  - 코드 블록의 명령은 실제로 실행 가능한 형태여야 한다.

- **완료 조건**:
  1. `python3 -m unittest discover -s tests` → 회귀 없음
  2. `grep -c "dashboard-mounts" README.md README.ko.md` → 양쪽 1 이상
  3. 두 README 의 추가 내용이 서로 대응(누락 항목 없음)
