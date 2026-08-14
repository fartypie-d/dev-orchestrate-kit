# Task 9: chrome-devtools-mcp 연결 옵션 (9a/9b 분할)

> 전파 제약 5에 따라 **9a(kit-tests, RED) → 9b(kit-scripts, 구현)** 으로 분할한다.
> 계약 D1~D8 이 두 에이전트의 유일한 진실의 원천이다. Task 8 계약 C1~C12 를 전제로 한다.

## 전제 실측 (2026-08-12)

| 전제 | 근거 | 판정 |
|---|---|---|
| README 에 MCP 서버 정의가 있다 | README.md:188-190 — 서버명 `chrome-devtools`, `npx -y chrome-devtools-mcp@latest --browserUrl http://127.0.0.1:9222` | 유지 — args 드리프트 금지 |
| 등록 스코프는 사용자 레벨 | 사용자 결정 2026-08-12 — `claude mcp add -s user` | 확정 |
| `~/.claude.json` 직접 편집 금지 | 하네스 소유 파일 | 유지 |

## 공유 계약

- **D1 노출 조건**: Task 8 의 컨테이너 스텝(스텝 5)에서 **claude 하네스일 때만** `choose_many`
  항목에 `mcp:chrome-devtools-mcp 를 사용자 레벨에 등록` 을 추가한다. codex 단독이면 항목을 넣지 않는다.
- **D2 변수 분리**: 선택 결과는 `CONTAINERS` 를 오염시키지 말고 전역 `MCP_REGISTER=1|0` 으로 분리한다
  (`CONTAINERS` 는 실행 루프의 입력이다).
- **D3 의존성**: `mcp` 만 고르고 `browser` 를 안 골랐으면 stderr 경고 후 `MCP_REGISTER=0` 으로 강등.
- **D4 마커**: `printf 'SELFTEST WIZARD MCP=%s\n' "$MCP_REGISTER"` 를 **CONTAINERS 다음 줄**에 삽입.
  **claude 하네스일 때만 출력한다** — codex 단독이면 이 줄 자체가 없다
  (사용자 결정 2026-08-12: D1 노출 조건과 일관되게, 실패 테스트 1번 "codex 는 마커에 mcp 흔적 없음"을 따른다).
  따라서 마커는 **claude = 8줄 / codex = 7줄**. 기존 마커 테스트 갱신은 **9a 책임**.
- **D4-1 STEPS 불변**: MCP 는 **새 스텝이 아니라 컨테이너 스텝(스텝 5)의 항목 추가**다.
  `SELFTEST WIZARD STEPS=` 토큰 목록은 **변하지 않는다**. 새 스텝 토큰을 넣지 말 것
  (넣으면 마법사·auth·컨테이너 픽스처와 pty 개행 수가 전부 깨진다).
- **D5 단일 소스**: `MCP_ADD_ARGV` 전역 배열 + `build_mcp_add_argv`(서버명 화이트리스트 `{chrome-devtools}`)
  + `mcp_add_command`(렌더링 전용, `eval` 금지). 실행은 `"${MCP_ADD_ARGV[@]}"`.
  `--browserUrl` 값·서버명은 **README.md:188-190 과 동일**해야 한다.
- **D6 등록 수단**: `command -v claude` 가 있으면 `claude mcp add -s user ...`,
  없으면 스킵 + README MCP 절 수동 안내. **`~/.claude.json` 직접 편집 금지.**
- **D7 멱등**: `claude mcp list` 에 이미 `chrome-devtools` 가 있으면
  `MCP_REGISTER_SKIPPED=chrome-devtools reason=exists`.
- **D8 셀프테스트**: `INSTALL_SELFTEST_MCP=1` 블록(`INSTALL_SELFTEST_CONTAINERS` 블록 뒤, `exit 0`).
  주입: `INSTALL_MCP_FAKE=ok|no_cli|exists|fail`(기본 ok). 마커:
  `MCP_REGISTER_WOULD_RUN=chrome-devtools <mcp_add_command 렌더링>` /
  `MCP_REGISTER_SKIPPED=chrome-devtools reason=no_cli|exists` /
  `MCP_REGISTER_FAILED=chrome-devtools`.
  등록 실패는 **비치명** — note 경고 + README 안내 폴백, 설치 중단 금지.
  `CLAUDE_INSTALL_FAILED` 집계 접합은 Task 6b 스코프 — 9b 는 건드리지 않는다.

---

## Task 9a: MCP 옵션 RED 테스트
- **에이전트**: kit-tests / **모델**: heavy / **선행**: Task 8b
- **대상 파일**: `tests/test_install_mcp_step.py`(신규), `tests/test_install_wizard.py`(마커 8줄 갱신)
- **재사용**: 그대로 재사용 `tests/_install_helpers.py`. 구조는 `tests/test_install_container_step.py`(8a) 미러.
- **실패 테스트** (7건):
  1. `test_mcp_item_shown_only_for_claude_harness` — codex 단독이면 STEPS·마커에 mcp 흔적 없음
  2. `test_mcp_marker_when_selected` — browser+mcp 선택 → `SELFTEST WIZARD MCP=1`
  3. `test_mcp_downgraded_without_browser` — mcp 만 선택 → `MCP=0` + stderr 경고
  4. `test_wizard_marker_lines_are_eight` — 마커 8줄·순서
  5. `test_mcp_register_would_run` — `INSTALL_SELFTEST_MCP=1` → `MCP_REGISTER_WOULD_RUN=chrome-devtools ...`
  6. `test_mcp_skipped_without_cli` / `test_mcp_skipped_when_exists` — `reason=no_cli` / `reason=exists`
  7. `test_mcp_args_match_readme` — 렌더링된 명령의 서버명·`--browserUrl http://127.0.0.1:9222` 가 README.md 와 일치
- **필수 규칙**: 8a 와 동일 — SELFTEST 경로 필수(`INSTALL_PARSE_ONLY` 금지), **변이 검증 금지**(9b 몫),
  스크래치는 `.orchestrate/mut9a/`(저장소 밖 쓰기 금지), `git stash` 금지, `git add` 경로 명시,
  실제 홈·실제 `claude mcp` 호출 금지
- **완료 조건**: 7건 RED 출력 + 실패 범위가 MCP 계약으로 국한됨을 unittest 출력으로 제시

## Task 9b: MCP 옵션 구현
- **에이전트**: kit-scripts / **모델**: heavy / **선행**: Task 9a
- **대상 파일**: `install.sh`
- **재사용**: 그대로 재사용 README.md:188-190 서버 정의(드리프트 금지),
  argv 단일소스 패턴은 `build_auth_login_argv`(install.sh:1065-1083) 미러,
  스텝은 Task 8 의 스텝 5 확장 — **새 스텝·새 메뉴 헬퍼 금지**
- **실패 테스트**: 9a 의 7건 (RED 확인 후 착수)
- **필수 규칙**: 계약 D1~D8 전부 + bash 3.2 호환 + `tests/*.py` 편집 불가(계약 불일치는 수정하지 말고 보고)
  + 마법사 본문 금지 문자열(C6: `docker`·`git clone`·`gen-policy.sh`·`apply-plan-profile.sh`·`auth login`) 유지
  + 스크래치 `.orchestrate/mut9b/` + `git stash` 금지 + `git add` 경로 명시
- **완료 조건**:
  1. `bash -n install.sh` OK
  2. `python3 -m unittest discover -s tests` 전부 GREEN
  3. 단일소스: `grep -c "browserUrl" install.sh` → **1**
  4. 변이 검증 2종(`.orchestrate/mut9b/` 사본): ① 멱등 검사 제거 → `exists` 테스트 FAIL
     ② claude 하네스 가드 제거 → 1번 FAIL — 결과 표 첨부
