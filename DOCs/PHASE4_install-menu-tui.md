---
phase: 4
date: 2026-08-11
kind: task
domain: install, docs
status: done
commits: 4f34115..28321ed (파트 4-1~4-4, 세션 7 분 12개 포함)
cost: $30.68 (프로젝트 세션 파일 3개 누적 — 세션 7 시점 실측)
compactions: 0
interventions: 1
summary: install.sh 메뉴 UX 개편 — 체크박스 TUI, 마법사 뒤로가기, 구독 인증·컨테이너·MCP 스텝, 원인별 수동 조치 안내
---

# 작업 지시서 — install.sh 메뉴 UX 개편 (2026-08-11)

## 인터뷰 결과
- 스코프: ① 하네스 메뉴 문구(오케스트레이터 선택임을 명확히) ② 공개 README EN·KO quickstart 동일 혼동 해소
  ③ 번호 입력 → Claude CLI 식 방향키·체크박스 TUI ④ 마법사 단계 간 뒤로가기(전체)
  ⑤ 구독 프로바이더 설치 중 `opencode auth login` 대화형 실행(클린 호스트 실측: 7/7 검증이 인증 미완으로 무조건 ❌)
  ⑥ 호스트 전용 라이브 인프라 경고(`/opt/chrome-cdp`) 일반화 — 새 호스트에서 브라우저 작업 거부 유발(실측)
  ⑦ insane-cloak(browser) 컨테이너 설치를 마법사 스텝으로 (서브모듈 init + compose up 자동화)
  ⑧ chrome-devtools-mcp 연결 옵션 + MCP 미연결에도 쓸 수 있는 insane-cloak 기본 스킬 신설
- 우선순위: 한 페이즈로 전부 (사용자 선택 — 2페이즈 분리안 기각)
- 제약: 순수 bash ANSI(의존성 금지), **bash 3.2 호환**, 비TTY·`INSTALL_SELFTEST_MENU` 번호 입력 폴백 유지,
  실제 홈 오염 금지(테스트는 주입 플래그·임시 디렉터리)
- 크기 등급: **large** (메뉴 엔진 + 흐름 재구성 + 테스트 횡단) → task-orchestrator 경유, kit-scripts는 heavy
- 반영 경로: **`feat/public-release-0811` (PR #5 헤드)에서 직접 작업** — phase-claim `--base`가
  새 브랜치를 만들지 않고 base를 체크아웃한 것을 Task 2 검수에서 실측(claim 출력 `BRANCH=`와
  불일치, phase-tools 버그 후보). 사용자 선택("PR #5 브랜치에 추가")과 일치해 그대로 진행.
  푸시(PR #5 갱신)·공개 main 스냅샷 푸시는 별도 명시 승인.

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| 메뉴 헬퍼는 install.sh 내장, 외부 source는 lib/stamp.sh뿐 | install.sh:14, 80-260 | 유지 |
| 대화 지점 4곳: 하네스 726 · ECC 758 · 프로바이더 864 · 요금제 913 (+prompt_yes_no 362 sudo, 543 동의) | grep 실측 | 유지 |
| 컨테이너는 `--with` 플래그 전용 — 대화 메뉴 없음 | install.sh:886-905 | 유지 |
| 테스트는 메뉴 라벨 문자열에 비의존 (비대화형 안내·CLI 경고 문자열만 참조) | tests grep: test_install_menu.py:110, test_install_claude_bootstrap.py:161 | 유지 |
| `INSTALL_SELFTEST_MENU=1`이 read_line_interactive에서 입력을 `\|` 구분 주입 | install.sh:82-114 | 유지 — TUI는 이 경로를 우회하면 안 됨 |
| opencode auth login은 device-code로 헤드리스 대화형 가능 | install.sh 남은 수동 단계(:936-), 클린 호스트 실측 로그 | 유지 |
| EN quickstart는 공개 트리에만 존재 | 공개 README.md:64-75, README.ko.md:53-63 | 유지 |
| (파트 4-2) `choose_*` 에 뒤로가기 신호가 있다 | install.sh:284-410 — 번호 폴백은 `b`를 무효 처리, TUI `back` 토큰은 기본값 반환 rc=0 (선택과 구분 불가) | **뒤집힘** → 종료코드 10 계약 신설 (task4.md) |
| back 의미 변경이 기존 테스트를 깬다 | test_install_menu.py:95(keyparse 토큰만), 109·127·147(enter·arrow·timeout·eof만) | 뒤집힘 — 회귀 없음 |
| 전역 플래그로 back 신호 가능 | `_choice=$(choose_one ...)` 는 서브셸 — 전역 유실 | 뒤집힘 → 종료코드로 신호 |
| 대화 지점 4곳 행번호 (Task 3 이후) | install.sh:879 하네스 · 911 ECC · 1017 프로바이더 · 1066 요금제 | 이동(구조 동일) |
| (Task 5) `INSTALL_SELFTEST_MENU=1`로 6/7 실행 시점 마커를 검증할 수 있다 | install.sh:1022-1033 — 셀프테스트 블록에서 `exit 0`, 메인 흐름 미도달 | **뒤집힘** → `INSTALL_SELFTEST_AUTH` 신설 (task5.md C5) |
| (Task 5) 마법사 스텝은 1~5, 마커 5줄, STEPS 토큰 5종 | install.sh:837-970, 1014-1018 | 유지 — auth 삽입 시 summary 5→6 재번호 필요 |
| (Task 5) 로그인 명령 문자열의 유일한 출처는 「남은 수동 단계」 heredoc | install.sh:1277-1293 (quoted `'EOF'` — 변수 확장 불가) | 유지 — 단일화하려면 heredoc 밖으로 빼야 함 |
| (Task 5) 6/7 이후 7/7 앞에 삽입 지점이 있다 | install.sh:1214-1234(6/7) → 1270(7/7), 사이에 컨테이너·요금제 블록 | 유지 — 삽입은 gen-policy 직후 |
| (Task 5) `set -euo pipefail` 이 켜져 있다 | install.sh:8 | 유지 — 로그인 실패는 명시 처리해야 설치가 안 죽음 |
| (Task 5) 마커 추가가 기존 wizard 테스트를 깬다 | tests/test_install_wizard.py:26-30·49-53·72-76 (3건) | 유지 — 갱신은 5a 책임(5b는 tests 편집 불가) |
| (Task 8) 컨테이너 플래그는 `--with` | install.sh:56 — 실제로는 `--containers=<콤마목록>` | **뒤집힘** → 계약 C2·C3 는 `--containers=` 기준 |
| (Task 8) 마법사 스텝은 1~6, 마커 6줄 | install.sh:831-1030, 1112-1126 (AUTH 포함 6줄) | 유지 — 컨테이너 삽입 시 7스텝·7마커(C1·C5) |
| (Task 8) `test_wizard_has_no_side_effects` 가 `docker` 부분문자열을 금지한다 | tests/test_install_wizard.py — 함수 본문 슬라이스 검사 | 유지 — **메뉴 라벨·주석에도 `docker` 금지**(C6) |
| (Task 8) insane-cloak compose project·container 명이 고정 | containers/browser/docker-compose.yml:23,26,29 `chrome-cdp`, image `local/chrome-cdp:0.11.0`, 포트 9222/9223 | 유지 — 남의 CDP 세션 충돌 가능 → `/dev/tcp` 포트 검사 필수(C11) |
| (Task 9) README 에 MCP 서버 정의가 있다 | README.md:188-190 — `chrome-devtools`, `--browserUrl http://127.0.0.1:9222` | 유지 — args 드리프트 금지(D5) |
| (Task 10) 새 전역 스킬은 install.sh 수정이 필요하다 | install.sh:1291-1296 — `adapters/claude/global/skills/*/` glob 복사 | **뒤집힘** → 디렉터리만 추가하면 자동 배치, install.sh 수정 금지 |

## Task 목록

| # | 제목 | 에이전트 | 모델 | 선행 | 상태 | 커밋 |
|---|---|---|---|---|---|---|
| 1 | 하네스 메뉴 문구 명확화 | kit-scripts | heavy | — | 완료(리뷰 PASS×3) | 4f34115 |
| 2 | README EN·KO quickstart 명확화 | kit-docs | default | — | 완료(리뷰 PASS) | 800d57a |
| 3 | TUI 엔진 (방향키 choose_one · 체크박스 choose_many) | kit-scripts | heavy | 1 | 완료(리뷰 PASS — 반려 2회 극복) | 65c2730+720f645+1e06cc2 |
| 4a | 마법사 RED 테스트 (계약 시나리오 A~D) | kit-tests | heavy | 3 | 완료(리뷰 PASS — 반려 1회) | 3e043fe |
| 4b | 설치 마법사 프론트로딩 + 단계 간 뒤로가기 | kit-scripts | heavy | 4a | 완료(리뷰 PASS — 반려 2회) | d71227c |
| 4c | pty 회귀 테스트에 메뉴 유휴 상한 주입 | kit-tests | heavy | 4b | 완료(리뷰 PASS, 🟠 1건 Task 6 이월) | d741d33 |
| 5a | 마법사 auth 스텝 RED 테스트 (계약 C1~C5) | kit-tests | heavy | 4 | 완료(리뷰 PASS — 반려 1회+🟡 보강 1회) | 77e64b5 |
| 5b | auth 동의 스텝 + 6/7 뒤 로그인 실행 | kit-scripts | heavy | 5a | 완료(리뷰 PASS — 🔴 단일소스 보강 1회) | 1652396 |
| 6a-1 | 스텁 바이너리로 MCP·auth 실함수 커버 | kit-tests | heavy | 9b | ✅ python-reviewer PASS | `e92d2de` |
| 6a-2 | 통합 시나리오·SIGINT·유휴 상한 런타임 검증 | kit-tests | heavy | 6a-1 | ✅ PASS (반려 1회) | `09588e2` |
| 6b | 실패 집계 + 원인별 수동 조치 안내 | kit-scripts | heavy | 6a | ✅ bash PASS (🔴 반려 2회 극복) | `575355d`→`c3f0883` |
| 6c | expectedFailure 표식 제거 | kit-tests | default | 6b | ✅ (trivial, 메인 커밋) | `fd16091` |
| 6d | MCP 실패 집계·번호 순서 회귀 테스트 | kit-tests | heavy | 6b | ✅ (trivial, 메인 커밋) | `a4963ab` |
| 7 | 호스트 전용 라이브 인프라 경고 일반화 (chrome-cdp) | kit-docs | default | — | 완료(리뷰 PASS) | 64f47be |
| 8a | 컨테이너 스텝 RED 테스트 (계약 C1~C11) | kit-tests | heavy | 5b | 완료(3차 보강 승인 후 재개 — 반려 3회 극복) | 23235ed+de8e920 |
| 8b | 컨테이너 스텝 + 자동 설치 구현 | kit-scripts | heavy | 8a | 완료(리뷰 PASS×3, 🔴 0·🟠 0) | 1ab95ad |
| 8c | 컨테이너 스텝 파급 픽스처 갱신 (8a 누락 보정) | kit-tests | default | 8b | 완료(리뷰 SIGN OFF, 🟡 1) | 5bc7f0d |
| 9a | MCP 옵션 RED 테스트 (계약 D1~D8) | kit-tests | heavy | 8b | 완료(python-reviewer PASS — 반려 3회 극복) | 75499d5+52caa2f+8a125f5 |
| 9b | MCP 옵션 구현 | kit-scripts | heavy | 9a | 완료(리뷰 PASS×3, 🔴 0 / 🟠 1건 6a 이월) | d8325cb |
| 10 | insane-cloak 활용 기본 스킬 | kit-docs | default | — | 완료(리뷰 SIGN OFF — 반려 0회) | b73d467 |

## 파트 그룹핑 (세션 단위)
- **파트 4-1 (세션 1)**: Task 1·2·7·3 — 문구·문서·경고 일반화·TUI 엔진
- **파트 4-2 (세션 2~4)**: Task 4·5 — 마법사·인증 스텝 (완료)
- **파트 4-3 (세션 5, 오토 모드)**: Task 8a·8b·9a·9b·10·6a·6b — 컨테이너 스텝·MCP 옵션·기본 스킬·통합
  - 세션 5 에서 Task 10 완료, 8a 는 반려 3회로 보류 → 세션 6(일반 모드)에서 8a 승인·재개, 8b·8c 완료
  - **파트 4-4 (세션 7~)**: Task 9a·9b·6a·6b — MCP 옵션·통합/이월 🟡
- 파트 경계에서 `tasks/HANDOFF.md` 작성 후 세션 전환.

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| TUI 도입 후 비TTY·SELFTEST 폴백 회귀 | 파이프 실행·CI에서 메뉴가 멈추거나 TUI 코드가 실행됨 | `tests/test_install_menu.py::test_selftest_number_input_still_works` (Task 3) |
| 뒤로가기 후 상태 오염 | 하네스를 바꿔 되돌아오면 요금제 스텝 조건·기선택이 갱신되지 않음 | `tests/test_install_wizard.py::test_back_navigation_resets_dependent_steps` (Task 4) |
| bash 3.2 비호환 문법 | 연관배열·mapfile·`${v,,}`·소수점 `read -t` 사용 | `bash -n` + 리뷰어 체크리스트 (Task 3·4) |
| auth 로그인 실패가 설치를 죽인다 | `set -euo pipefail` 하에서 login 실패·Ctrl-C(130)가 exit 전파 | `test_auth_failure_does_not_abort_install` (Task 5a) |
| 로그인 명령 문자열 드리프트 | 실행부와 「남은 수동 단계」 안내에 같은 문자열이 따로 존재 | `grep -c "auth login -p xai" install.sh` → 1 (Task 5b 완료 조건) |
| auth 스텝이 키 기반 프로바이더에도 뜬다 | qwen만 골랐는데 로그인 질문이 나옴 | `test_auth_step_skipped_without_subscription_provider` (Task 5a) |
| 마법사 안에서 실제 로그인이 실행됨 | 부수효과가 프론트로딩 계약을 깸 | `test_wizard_has_no_side_effects` 금지 목록에 `auth login` 추가 (Task 5a) |

## 전파 제약 누적
- **(Task 1 실측)** `INSTALL_SELFTEST_MENU=1` 경로는 install.sh 648~718행 셀프테스트 블록에서
  **항상 exit 0** — 메인 흐름의 메뉴(하네스 721~·ECC 757~·프로바이더 863~·요금제 912~)에는 절대
  도달하지 않는다. 따라서 메뉴 동작의 SELFTEST 검증은 **셀프테스트 블록 안에 해당 시나리오를
  추가**하는 방식이어야 한다 (Task 4·5·8·9의 마커 검증도 동일 — 블록 보강 필수). 실행 grep 로
  메인 흐름 문구·마커를 검증하는 완료 조건 금지. 문구 검증은 소스 정적 grep/diff 대조로.
- **(Task 7 리뷰 중 발생)** 리뷰어·검수 서브에이전트에게 **공유 워크트리에서 `git stash` 금지**를
  명시할 것 — Task 7 리뷰어가 격리 검증용으로 stash/pop 을 썼는데, 병렬 위임(Task 3)이 같은
  트리를 편집 중이었다 (이번엔 무사고 실측 확인, 그러나 위임 에이전트의 미저장 편집과 겹치면
  유실 가능). 격리 검증이 필요하면 `git show <커밋>:<파일>` 또는 임시 디렉터리 사본으로.
- **(파트 4-2 착수 시 실측)** kit-scripts 는 `tests/*.py` 편집 권한이 없다 —
  **테스트와 구현이 함께 필요한 task 는 `<N>a`(kit-tests) → `<N>b`(kit-scripts) 로 분할하고,
  두 에이전트가 공유할 계약(문자열·종료코드·마커)을 지시서에 먼저 확정한다.** Task 5·8·9 도 동일.
- **(Task 4 계약)** 뒤로가기 = `choose_*` 종료코드 **10**(무출력). 번호 폴백·SELFTEST 는 입력 `b`,
  TUI 는 `back` 토큰. 마법사 셀프테스트는 `INSTALL_SELFTEST_WIZARD=1` +
  `INSTALL_SELFTEST_INPUTS`(`|` 구분) → `SELFTEST WIZARD HARNESSES/ECC/PROVIDERS/PLAN/STEPS=` 마커.
  Task 5·8 의 새 스텝은 이 스텝 배열·마커에 추가하는 형태여야 한다.
- **(Task 4b 실측 — rc=11 계약)** `script(1)` pty 는 **첫 read 만 EOF 로 끝나고 이후 read 는 영구
  대기**한다. 따라서 입력 불가 상황은 rc **11** 로 구분한다: `choose_*` 가 안내+기본값을 stderr 로
  내고 rc 11 을 반환하면, 마법사는 남은 스텝을 프롬프트 없이 기본값으로 확정하고 종료한다.
  **rc 11 관용은 `prompt_yes_no` 로 전파 금지** — sudo·Claude CLI 설치 동의는 fail-closed 유지
  (무인 `npm i -g` 유발 🔴 전례). 마법사 호출을 `INSTALL_PLAIN_MENU != 1` 로 가드하지 말 것
  (그 모드에서 선택 메뉴가 통째로 사라진다 — 4b 1차 반려 사유).
- **(Task 4c 실측 — 유휴 상한)** 메뉴 read 에 **기본 유휴 타임아웃을 두지 말 것**(5초 기본값은
  느린 응답을 조용히 버린다). 상한은 `INSTALL_MENU_IDLE_LIMIT` 로 **주입 전용**이며 pty 자동화
  테스트가 이를 주입한다.
- **(Task 5a 실측 — 위임 스크래치 경로)** 위임·리뷰 프롬프트에 `/tmp` 등 **저장소 밖 쓰기**를
  지시하지 말 것. opencode 가 `external_directory` 로 자동 거부하고 **런이 최종 보고 없이 종료**된다
  (PITFALLS 8). 변이·리뷰용 사본은 gitignore 경로 `.orchestrate/mut<task>/`·`.orchestrate/rev<task>/`
  에 만들고 사용 후 삭제하게 한다. Task 5b·6·8·9·10 프롬프트에 반영할 것.
- **(Task 5a 실측 — 변이 검증 시점)** `<N>a`(RED) task 에 변이 검증을 요구하지 말 것 — 변이시킬
  구현이 아직 없어 항상 참인 검증이 된다 (PITFALLS 9). **변이 검증은 `<N>b`(구현)의 완료 조건**이며
  `<N>a` 의 완료 조건은 ① RED 출력 ② 실패 범위가 해당 계약으로만 국한됨 두 가지다.
- **(Task 5b 실측 — 드리프트 가드가 우회될 수 있다)** "명령 문자열이 두 곳에 남으면 🔴" 를
  `grep -c "auth login -p xai"` → 1 로 검사했더니, 실행부가 **argv 배열**로 조립해 리터럴이
  안 나타나는 바람에 지식이 두 벌인 채 가드를 통과했다 (리뷰어 3인 독립 지적).
  **완료 조건 grep 은 "형태"가 아니라 "지식"을 세는 문자열**(여기서는 `ChatGPT Pro/Plus`)로
  잡을 것. Task 8·9 의 명령 단일소스 조건에도 동일하게 적용.
- **(Task 5b 계약 — auth 단일 소스)** `AUTH_LOGIN_ARGV` 전역 배열이 유일한 소스다
  (bash 3.2 에 nameref 없음). `build_auth_login_argv <프로바이더>` 가 화이트리스트
  `{xai,openai}` 를 강제하고 그 외 `return 1`; `auth_login_command` 는 그 argv 를
  **렌더링**만 한다(`eval` 금지, 표시 문자열 재실행 금지). 실행은 항상
  `"${AUTH_LOGIN_ARGV[@]}"`. 새 프로바이더 추가 시 `build_auth_login_argv` 한 곳만 고치고
  **안내 출력 :1396-1397 의 하드코딩된 `xai`·`openai` 호출도 함께 갱신**할 것.

- **(파트 4-3 계약 소재)** 8a·8b 의 유일한 진실의 원천은 **task8.md 의 C1~C12**,
  9a·9b 는 **task9.md 의 D1~D8** 이다. 위임 프롬프트에 계약 전문을 인라인할 것.
  마커 줄 수는 **현재 6줄 → 8b 후 7줄(CONTAINERS) → 9b 후 8줄(MCP)** 로 순차 증가하며,
  기존 마커 테스트 갱신 책임은 항상 **`<N>a`(kit-tests)** 에 있다.
- **(파트 4-3 경계)** `CLAUDE_INSTALL_FAILED` 집계 접합은 **6b 단독 스코프** —
  8b·9b 는 건드리지 않는다(C12·D8). 셀프테스트 블록 밖 **새 stdout 마커 추가 금지**
  (기존 테스트가 stdout 전체를 assertEqual 한다).
- **(Task 10 경계)** 전역 스킬은 glob 복사(install.sh:1291-1296)로 자동 배치되므로
  **install.sh 를 수정하지 않는다**. 서브모듈 실측값은 오케스트레이터가 task10.md 표로
  제공했고, 위임 에이전트는 **`git submodule update --init` 을 실행하지 않는다**.
- **(Task 8a 실측 — RED 테스트의 앵커 함정)** `assertRegex` 는 `re.search` 라서 `(?m)` 없는 `^` 는
  **stdout 맨 앞에서만** 매칭된다. 8a 2차 보강이 `CONTAINER_SUBMODULE_WOULD_INIT` 단언을 추가하면서
  `^CONTAINER_INSTALL_WOULD_RUN=` 를 그대로 둔 탓에, **계약 순서(init → run)대로 구현하면 실패하고
  순서를 뒤집은 잘못된 구현이 통과**하는 테스트가 됐다(리뷰어 실측 재현). 여러 마커를 함께 검증할
  때는 반드시 `(?m)^...$` 를 쓸 것. Task 9a 의 MCP 마커 테스트에도 동일 적용.
- **(Task 8b 계약 — 마커 출력부 형태)** 8a 의 `test_container_up_command_single_source` 는
  ① `up -d` 리터럴이 **`build_container_up_argv` 함수 본문 안에만** 존재할 것,
  ② `CONTAINER_INSTALL_WOULD_RUN=` 출력부 **±400자 이내에 `container_up_command` 호출**이 있을 것,
  ③ `chrome-cdp` 가 install.sh 에 없을 것을 정적으로 고정한다. 렌더링을 변수에 담았다가 출력하는
  형태(`_rendered=$(container_up_command "$name")` → `printf ... "$_rendered"`)는 **허용**된다.
- **(Task 8b 계약 — 서브모듈 마커 의미론)** `CONTAINER_SUBMODULE_WOULD_INIT=browser` 는
  **init 시도 예정 안내**이지 성공 보고가 아니다. `INSTALL_CONTAINER_FAKE=submodule_missing`
  경로에서도 이 마커는 **찍히고**, 실패는 뒤따르는
  `CONTAINER_INSTALL_SKIPPED=browser reason=unknown` 으로 표현한다(rc 0 유지).
- **(Task 8a 3차 실측 — 마커 "순서"는 별도 단언 없이는 검증되지 않는다)** `assertIn`(A) + `assertRegex`(B)
  두 개는 각각 존재만 본다. 순서를 계약으로 삼았다면 `assertLess(stdout.index(A), stdout.index(B))` 를
  **명시적으로** 써야 한다. `(?m)^` 은 거짓 실패만 없앨 뿐 순서를 강제하지 않는다. → Task 9a 의
  `MCP_REGISTER_*` 마커 순서에도 동일 적용.
- **(Task 8a 3차 실측 — 부정 단언의 반증가능성)** `INSTALL_SELFTEST_WIZARD=1` 분기는 마법사 마커를
  찍고 **곧바로 `exit 0`** 한다(install.sh:1111-1126). 그 모드에서 실행 단계 마커에 대한
  `assertNotIn` 은 **어떤 구현이든 통과하는 항상-참 단언**이다(CLAUDE.md 함정 1과 같은 유형).
  부정 단언을 쓸 때는 "그 모드에서 그 마커가 나올 수 있는 경로가 존재하는가"를 먼저 확인하고,
  없으면 실행 게이트 모드(`INSTALL_SELFTEST_CONTAINERS`/`_MCP`)에서 별도 테스트로 검증할 것.
- **(Task 8a — 오케스트레이터가 기각한 리뷰 제안)** 윈도 검사를
  `assertRegex(window, r"container_up_command\s+[\"$]")` 로 좁히자는 3차 제안은 **기각**했다.
  `[\"$]` 는 `container_up_command browser` 같은 비인용 리터럴 인자를 거부해 2차 반려의
  과잉 제약과 같은 실수를 재도입한다. 윈도 검사는 `assertIn` 형태를 유지한다. 후속 리뷰에서
  같은 제안이 다시 나오면 이 항목을 근거로 기각할 것.
- **(Task 8b 확정 — 마커 7줄·입력 토큰 수)** 마커는 이제 **7줄**이고 순서는
  `HARNESSES → ECC → PROVIDERS → AUTH → CONTAINERS → PLAN → STEPS`. `STEPS=` 의 `containers`
  토큰은 **auth 다음·plan 이전**(auth 스킵 시 providers 다음). `INSTALL_SELFTEST_INPUTS` 는
  **표시되는 스텝마다 토큰 하나**를 소비하므로, 컨테이너 스텝이 표시되는 모든 시나리오의 입력
  문자열이 **토큰 한 개 길어졌다**. Task 9a 가 MCP 스텝을 추가하면 **같은 파급이 다시 발생한다** —
  9a 의 완료 조건에 "기존 `tests/test_install_*.py` 전체 GREEN(158→N)"을 반드시 넣을 것.
- **(Task 8c 실측 — 파급 수정은 `<N>a` 의 책임인데 누락된다)** 8a 는 자기 테스트 파일만 갱신하고
  `test_install_auth_step.py`(7건)·`test_install_wizard.py`(1건)·`test_install_claude_bootstrap.py`(1건)
  의 픽스처를 **못 고쳐서 9건이 RED 로 남았다**(입력 토큰·마커 줄·pty 개행 수). 8b 결함이 아니었다.
  → `<N>a` 프롬프트에 **"영향받는 다른 테스트 파일 목록"을 오케스트레이터가 미리 grep 해서 명시**하고,
  완료 조건을 "새 테스트 GREEN" 이 아니라 **"스위트 전체 GREEN"** 으로 쓸 것. 9a 에 즉시 적용.
  (pty 기본 선택 개행 수는 `test_install_claude_bootstrap.py:44` `input="\n\n\n\ny\n"` — 스텝이
  늘 때마다 개행 한 개 추가. 부족하면 `y` 가 요약 스텝에 먹혀 Claude CLI 동의가 fail-closed 된다.)
- **(Task 8b 계약 — 컨테이너 argv 단일소스)** `CONTAINER_UP_ARGV` 전역 배열 + `build_container_up_argv`
  화이트리스트(`browser` 만) + 렌더 전용 `container_up_command` 구조다(5b 의 auth 패턴과 동일).
  단, `container_up_command` 가 내부에서 `build_container_up_argv` 를 **다시 호출해
  `CONTAINER_UP_ARGV` 를 덮어쓴다** — 현재는 같은 값이라 무해하지만, 렌더와 실행 사이에 argv 를
  조작하는 코드를 넣으면 조용히 무효화된다. 6b·9b 에서 이 함수를 만질 때 주의.

## 잔여 🟡 (후속 정리 — 반려 사유 아님)

### Task 6 (마감 안내) 리뷰 이월 — 차기 페이즈 후보

- ~~**🟡 최우선 — auth 재시도 목록이 성공한 프로바이더까지 나열한다.**~~
  → **해소 (2026-08-12, 마감 후 후속 task 6e, 커밋 `83f24d0`)**. 신규 `AUTH_LOGIN_FAILED` 에
  **실패한 프로바이더만** 누적하고 렌더링이 그것을 순회한다. `opencode` 부재로 일괄 스킵되면
  `AUTH_LOGIN` 전체를 실패로 기록한다. RED→구현 분할(6e-a/6e-b)로 진행했고
  신규 테스트는 셀프테스트 훅이 아니라 **가짜 바이너리로 실제 실행 분기**를 탄다.
  bash-reviewer 재검수 APPROVE(실측: openai 성공·xai 실패 → xai 만 안내).
  남은 🟢: 셀프테스트 분기의 `AUTH_LOGIN_FAILED` 누적은 **죽은 코드**다
  (그 분기는 렌더링 전에 `exit 0`). 공통 헬퍼로 묶으면 드리프트를 원천 차단할 수 있다.
  아래는 해소 전 기록:
  `mark_manual_step auth` 는 원인을 `auth` 하나로만 기록하고 **어느 프로바이더가 실패했는지
  추적하지 않아서**, 렌더링이 `$AUTH_LOGIN` 전체를 순회한다.
  실측(bash-reviewer): openai 성공 + xai 실패인데 `6) openai 로그인 재시도` 와
  `7) xai 로그인 재시도` 가 **둘 다** 출력됐다 — 이미 성공한 openai 를 재시도하라는 거짓 안내다.
  → 실패한 프로바이더만 별도 변수(예: `AUTH_LOGIN_FAILED`)에 누적하고 그것을 순회할 것.
  (원래 🔴 "엉뚱한 컴포넌트를 가리킴"보다는 가벼운 계열 — 무해한 명령을 한 번 더 실행하게 할 뿐이라
  마감을 막지 않는다고 판단했다.)
- **🟢 같은 패턴이 컨테이너 재시도 블록에도 잠재.** 지금은 `build_container_up_argv` 가
  `browser` 하나만 지원해 영향이 없지만, 두 번째 컨테이너 타입이 생기는 순간 재현된다.
- **🟡 테스트 공백 — auth·컨테이너 실패 경로에 `Claude CLI 수동 설치` 문구 부재·번호 정렬 단언이 없다.**
  `a4963ab` 는 MCP 경로만 보강했다. 위 다중 프로바이더 버그가 안 걸린 이유가 이 공백이다.
- ~~**🟡 컨테이너 집계 경로는 이 호스트에서 자동 테스트 불가**~~
  → **해소 (2026-08-12, 마감 후 후속 task 7a·7b, 커밋 `5f3d2dd`·`a13c077`)**.
  차단 원인이 **하드코딩된 포트**였다 — `9222` 지식이 install.sh 3곳(MCP URL·포트 점유 검사·
  경고 문구)에 중복돼 있어 주입이 불가능했다. `CDP_PORT="${INSTALL_CDP_PORT:-9222}"`(`install.sh:14`)
  단일 소스로 통합하니(`grep -c 9222` → **1**) 테스트가 빈 포트를 주입해 **실제 기동 경로**에
  도달할 수 있게 됐다. 기본값 9222 유지로 README 대조 테스트도 그대로 통과.
  신규 `test_actual_container_up_failure_marks_manual_step` 이
  `assertRegex(argv, r"(?m)^<compose><-f><.+><up><-d>$")` 로 **실제 실행 도달을 argv 로그로 증명**하고
  `Claude CLI 수동 설치` **부재**를 단언한다 — 🔴 회귀가 다시 조용히 통과할 수 없다.
  검수: 스위트 2회 연속 GREEN(flaky 없음), `compose version` 만으로는 정규식이 매치되지 않음을
  별도 프로브로 확인, 가짜 `git` 이 실제 서브모듈을 건드리지 않음 확인.
  남은 🟡: pty 입력 `stdin="\n\n\n1\ny\n"` 이 **마법사 스텝 수에 의존**한다 — 스텝이 늘면 깨진다.
  주석으로 명시할 것(소규모).
  아래는 해소 전 기록: — 포트 9222 가 점유돼
  (라이브 `/opt/chrome-cdp`) 실제 `compose up -d` 전에 스킵된다. argv 로그가 `<compose><version>`
  만 기록하는 것으로 도달 불가를 확인했다. **포트가 빈 환경에서 추가할 것.**
- **🟢 기존 결손** — `NODE_PATH_ADDED=1`·`CLAUDE_INSTALL_FAILED=0` 이면 화면에 5) 다음 7) 이 나와
  6 이 비어 보인다(고정 항목의 하드코딩 번호 탓, `d8325cb` 이전부터 존재).
- **🔵 미검수** — 6b 최종본(`c3f0883`)은 bash-reviewer 만 재검수했다.
  silent-failure-hunter 의 🟠 2건(원인별 체크리스트·경고 구분)은 이번 구현으로 해소됐으나
  **재검수는 돌리지 않았다**(오케스트레이터 판단 — 그가 요구한 것이 그대로 구현됐고
  bash-reviewer 가 실측 재현으로 확인했다).


### Task 9 (MCP) 리뷰 이월 — 6a·6b 가 받는다

- **🟠 (6a 필수)** `run_mcp_registration()`(install.sh:1209-1227)에 **테스트 커버리지가 0** 이다.
  `tests/test_install_mcp_step.py` 는 `INSTALL_SELFTEST_MCP` 블록(1289-1298)만 구동하는데,
  그 블록은 `command -v claude`·`claude mcp list`·`"${MCP_ADD_ARGV[@]}"` 를 **하나도 호출하지 않는**
  별개의 시뮬레이션이다. 실제 멱등 검사·CLI 가드·`mcp add` 종료코드 처리가 회귀해도
  아무 테스트도 안 깨진다 (silent-failure-hunter 실측).
  → **5b 의 "실제 `opencode auth login` 분기 커버리지 0" 과 같은 계열**이다.
  6a 에서 **스텁 바이너리를 PATH 에 놓고 실함수를 구동**하는 방식으로 함께 해결할 것
  (CLI 부재 / `mcp list` 실패 / 미등록 / `mcp add` 실패 / 성공 5경로).
- **🟡 (6a·6b)** 멱등 검사가 **부분 문자열 매칭 + stderr 폐기**다:
  `claude mcp list 2>/dev/null | grep -q 'chrome-devtools'`.
  ① `my-chrome-devtools-fork` 같은 다른 이름이 등록돼 있으면 **"이미 등록됨"으로 오판해 건너뛴다**
  (안내 문구가 경고가 아니라 평범한 note 라 사용자가 눈치채기 어렵다 — "등록됐다고 믿는데 안 된"
  전형적 침묵). ② `mcp list` 자체가 실패(인증 만료 등)해도 원인이 사라진다.
  → 이름 필드 앵커링(`grep -qE '^chrome-devtools[[:space:]:]'` 또는 `claude mcp get chrome-devtools`)
  + list 실패 시 구분되는 경고.
- **🟡 (6a·6b)** `claude mcp list` 는 **등록된 모든 MCP 서버에 라이브 헬스체크를 수행**한다
  (리뷰어가 실제 CLI 로 실측). 무관한 서버가 응답 없으면 설치가 그 자리에서 오래 멈추는데
  사용자는 이유를 모른다. 타임아웃이 없다(`grep -n "timeout " install.sh` → 0건).
  → `timeout <n>s` 로 감싸고 타임아웃은 "확인 실패 → 등록 시도"로 처리.
- **🟡 (6b)** 비대화형에 **MCP 등록을 켜는 경로가 없다**. `--containers=mcp` 를 시도하면
  `build_container_up_argv` 가 모르는 값이라 `⚠️ 알 수 없는 컨테이너: mcp` 라는 엉뚱한 경고만 난다
  (install.sh:1522-1526). → `--register-mcp` 플래그를 만들거나, 최소한 `mcp` 를 특수 케이스로
  "대화형 마법사 전용 — README MCP 절 참조"로 안내.
- **🟡 (6b)** MCP 등록 실패가 **마감 요약에 안 잡힌다**. `CLAUDE_INSTALL_FAILED` 를 안 건드리므로
  중간 `⚠️` 한 줄만 남고 끝은 `설치 완료.` 다 (계약대로 비치명이지만, 사용자가 실제로 읽는
  마지막 체크리스트에 흔적이 없다). 5b 의 같은 항목과 **함께** 처리할 것.
- **🟡 (6b)** 마법사 "선택 요약"(install.sh:1057)에 `CONTAINERS`·`MCP_REGISTER` 가 빠져 있다 —
  사용자가 start 직전에 MCP 등록 여부를 확인할 수 없다 (9b 이전부터의 결함이나 9b 가
  부작용 있는 선택을 이 사각지대에 하나 더 얹었다).
- **🔵** argv 렌더 패턴이 **3벌**(auth·container·mcp)로 늘었다 — `render_argv()` 공통 헬퍼 후보.
  `run_mcp_registration` 이 기존 `claude_is_available()`(install.sh:574) 대신
  `command -v claude` 를 다시 쓴다(테스트 훅 `INSTALL_TEST_NO_CLAUDE` 와 불일치 가능).
- **🔵** `chrome-devtools-mcp@latest` 미고정 — 기존 저장소 정책(claude-code·opencode 도 최신판)과
  일관되므로 이번 변경이 리스크를 새로 만든 것은 아니다. 버전 고정은 별도 판단 사항.

- Task 2: 감독/실행자 설명이 문서 5곳 반복 (지시서 요구에 따른 의도적 반복 — code-reviewer 판정)
- Task 3: `install.sh:62` 하네스 자동감지 예외 목록에 `INSTALL_SELFTEST_TUI` 누락 —
  claude/codex 없는 머신에서 TUI 셀프테스트가 조용히 미실행 (security-reviewer 재현).
  Task 6(kit-tests)에서 예외 추가 + 검증 케이스로 처리 예정. → 720f645 에서 예외 추가 완료,
  검증 케이스는 Task 6 잔여.
- **Task 4c 🟠 (Task 6 이월)**: `tests/test_install_wizard.py::test_menu_read_has_no_default_idle_timeout`
  이 정적 substring 단언이라 **변이 회피 가능** — `: "${INSTALL_MENU_IDLE_LIMIT:=5}"` 를 넣어
  기본 타임아웃 버그를 되살려도 두 단언 모두 통과한다 (silent-failure-hunter 재현).
  Task 6 에서 런타임 pty 검사로 교체할 것.
- **Task 4b 🟡 (Task 6 이월)**: TUI `INT` 트랩이 `exit 130` 으로 빠져나가면서 셀프테스트 fd 9
  임시 파일의 `exec 9<&-; rm -f` 정리를 건너뛴다 (security-reviewer). 셀프테스트 전용 경로라
  영향은 임시 파일 잔존뿐.
- **Task 5b 🟡 (Task 6 이월)**: auth 로그인 실패가 `CLAUDE_INSTALL_FAILED` 집계에 반영되지 않는다 —
  3개 중 2개가 실패해도 마감 문구가 `설치 완료.` 그대로이고 「남은 수동 단계」 auth 절도
  성공/실패와 무관하게 동일하다 (silent-failure-hunter). 실패 누산기를 기존
  `CLAUDE_INSTALL_FAILED` 분기(:1421)에 접합할 것 — **새 stdout 마커 추가 금지**(테스트가
  stdout 전체를 assertEqual).
- **Task 5b 🟡 (Task 6 이월)**: `opencode` 바이너리 부재(rc 127)와 로그인 거부가 :1103 의
  같은 경고로 뭉뚱그려진다 — 조치 경로가 전혀 다르다. `command -v` 프리체크로 구분할 것.
- Task 5b 🟢 minor 2건: ① `note()` 가 stdout 에 쓰고 호출부 `>&2` 에 의존 (bash-reviewer)
  ② 표시 문자열 렌더링이 공백만 보고 인용한다 — 따옴표·`$`·백슬래시 든 인자가 추가되면
  렌더링이 깨진다 (현 화이트리스트엔 없음).
- **Task 8b 🟡 (Task 6b 이월)**: 컨테이너 루프의 `note` 안내가 `$c` 대신 **`browser` 를 하드코딩**한다 —
  화이트리스트에 두 번째 컨테이너가 추가되면 잘못된 이름을 보고한다 (bash-reviewer).
- **Task 8b 🟡 (Task 6b 이월)**: 컨테이너 기동 실패가 **docker 데몬 미동작 / compose 파일 부재 /
  포트 점유**를 구분하지 않고 같은 경고로 뭉뚱그려진다. 또 기동 후 **CDP 헬스체크(9222 응답 확인)가
  없어** `up -d` rc 0 이면 성공으로 보고한다 (silent-failure-hunter). 5b 의 rc127 구분 🟡 과 함께
  6b 에서 처리 — 단 **실패 집계 접합은 6b 단독 스코프**(C12).
- **Task 8b 🟡**: 컨테이너 스텝의 rc=11(입력 불가)은 auth 와 동일하게 **마법사를 조기 종료**시킨다
  (의도된 fail-closed). 다만 폴백 안내 문구에 `컨테이너=` 항목이 빠져 무엇이 기본값으로 확정됐는지
  안 보인다 (security-reviewer 🟢). 문구 보강은 6b.
- **Task 8c 🟡 (후속 정리)**: `test_install_auth_step.py`·`test_install_wizard.py` 의 기대 stdout
  블록이 7줄 리터럴로 8곳 중복돼, 스텝이 늘 때마다 8곳을 손으로 고쳐야 한다 (python-reviewer).
  6a 에서 헬퍼(`expected_wizard_stdout(...)`)로 묶을 것 — 단 **단언 약화 없이** 리터럴 동등성을 유지.
- Task 3 재리뷰 🟢 minor 2건: ① TUI 진짜 eof(rc=1) 분기는 script(1) pty 구조상 자동 테스트
  불가 (수동 경계값 검증만 존재) ② TUI 중 Ctrl-C 가 터미널만 복구하고 설치를 중단하지는 않음
  (trap 후 실행 재개) — 중단 의미론이 필요하면 후속 페이즈에서.

## 자동 결정 로그

> **오토 모드 활성 (2026-08-12 세션 5)** — 사용자 취침 전 인터뷰 2라운드(8문항)로 설계 분기점을
> 프론트로딩했다. 이후 선택지·게이트는 120초 무응답 시 권장안으로 자동 진행한다.
> **GATE 1 은 예외 — 명시 승인 필수.** GATE 2 skip = 로컬 커밋 상태로 마감, **푸시 절대 금지.**

| # | 질문 | 채택안 | 사유 |
|---|---|---|---|
| 1 | 이번 세션 범위 | 갈 수 있는 데까지 (8→9→10→6) | 사용자 직접 선택 (인터뷰 R1) |
| 2 | 컨테이너 스텝 위치 | auth 뒤 = 스텝 5 (재번호 6=요금제·7=요약) | 사용자 직접 선택 (인터뷰 R1) |
| 3 | `--containers=` 플래그 경로 | 플래그로 와도 동의 후 자동 설치 | 사용자 직접 선택 (인터뷰 R1) |
| 4 | 페이즈 마감 방식 | **로컬 커밋만 — 푸시 금지** | 사용자 직접 선택 (인터뷰 R1) |
| 5 | MCP 등록 수단 | `claude mcp add -s user` (`~/.claude.json` 직접 편집 금지) | 사용자 직접 선택 (인터뷰 R2) |
| 6 | 서브모듈 사실 수집 | 메인 체크아웃에서 오케스트레이터가 실측 → 프롬프트 인라인 | 사용자 직접 선택 (인터뷰 R2) — 워크트리 submodule init 시 phase-close rc=128 |
| 7 | Task 6 구조 | 6a(kit-tests) + 6b(kit-scripts) 분할 | 사용자 직접 선택 (인터뷰 R2) — 전파 제약 5 |
| 8 | 반려 2회 실패 시 | 해당 task `pending-approval` 보류, 독립 task 계속 | 사용자 직접 선택 (인터뷰 R2) |

### 자동 진행 기록 (세션 5)
- `[GATE 1]` 120초 무응답(skip) → 인터뷰에서 사용자가 스코프·순서·제약을 명시 선택했고
  "오토 모드로 진행하자" 지시가 있었으므로 **진행으로 해석**. 스코프는 인터뷰 결정 1 그대로.
- `[Task 8a]` 위임 완료 → 커밋 `23235ed` (RED 11건). python-reviewer **REJECT**
  (🔴 뒤로가기 입력 시퀀스가 기대 STEPS 와 불일치 — 실제로는 plan 단계에서 b / 🟠 단일소스 단언이
  "죽은 코드+printf 하드코딩" 변이로 우회 / 🟡 `submodule_missing` 미커버).
  오케스트레이터가 토큰 소비를 독립 재검산해 🔴 확인 → 1차 보강 위임.
- `[Task 8a 1차 보강]` 3건 반영. 그러나 오케스트레이터 검토에서 **새 결함 발견** —
  `assertRegex(r"^CONTAINER_INSTALL_WOULD_RUN=...")` 에 `(?m)` 이 없어 계약 순서(init→run)를
  뒤집도록 강제. python-reviewer 재리뷰 **REJECT** (🔴 앵커 / 🟠 마커 정규식 과잉 제약) → 2차 보강 위임.
- `[Task 10]` 위임 완료 → task-orchestrator 검증 후 커밋 `b73d467`.
  code-reviewer **SIGN OFF** (실측 표 12항목 1:1 일치, 지어낸 값 없음, 🔴/🟠/🟡 0건).
  install.sh 미수정 확인, 임시 HOME glob 리허설로 배치 확인.
- `[Task 8a 2차 보강]` 4건 전부 정확히 반영됨(오케스트레이터가 파일 직접 읽어 확인, 리뷰어도 재확인).
  그러나 python-reviewer 3차 리뷰가 **새 🔴 2건**을 냈다 — ① INIT→RUN 순서 미검증(역순 구현도 통과,
  실측 재현) ② `test_container_step_empty_selection` 의 부정 단언이 WIZARD 모드에서 구조적 항상-참.
  → **BLOCK**.
- `[Task 8a 보류 결정]` 재위임 2회(1차·2차 보강)를 모두 소진했고 3차 반려가 나왔다.
  `/orchestrate` 규정("재위임 최대 2회 → 중단", 오토 모드에서도 **완화 없음**)과 인터뷰 결정 8에 따라
  **`pending-approval` 로 보류**한다. 오토 모드의 skip(권장안 채택) 메커니즘으로 🔴 를 통과시키는 것은
  명시적으로 금지되어 있으므로 재질의도 하지 않았다.
  - 판단 근거(사용자 참고용): 3차 지적 2건은 **모두 "단언 추가"이지 계약 오류가 아니다.** 현재 파일이
    잘못된 계약을 고정하고 있지는 않다(2차의 순서 역전 🔴 는 해소·검증 완료). 즉 8b 를 오염시키지는
    않는 상태다. 다만 서명 없이 진행하지 않는다는 규정을 우선했다.
  - 재개 준비 완료: `.orchestrate/task8a-fix3.prompt` (4개 항목 + 기각 항목 명시) 작성됨.
    승인 시 `bash scripts/run-delegation.sh kit-tests .orchestrate/task8a-fix3.prompt .orchestrate/task8a-fix3.log heavy` 한 줄.
- `[파트 4-3 중단]` 잔여 task(6a·6b·8b·9a·9b)가 **전부 8a 하류**라 독립 진행 가능한 task가 없다.
  인터뷰 결정 1("갈 수 있는 데까지, 스래싱 시 HANDOFF 후 중단")에 따라 세션을 마감하고 인계한다.

### 세션 6 기록 (2026-08-12, **일반 모드** — 오토 모드 아님)

사용자가 AskUserQuestion 으로 직접 선택: ① 8a 보류 해제 = **"3차 보강 승인·재개"**
② 범위·모드 = **"8a→8b 까지, 일반 모드"** (게이트는 사용자 응답 대기, 자동 승인 없음).
9a·9b·6a·6b 는 다음 세션.

- `[Task 8a 3차 보강]` 승인 → `kit-tests` heavy 재위임. 4개 항목 반영 + 기각 항목 유지.
  python-reviewer **SIGN OFF** → 커밋 `de8e920`.
- `[Task 8b]` `kit-scripts` heavy 위임 → task-orchestrator 검증 → 커밋 `1ab95ad` (install.sh +130/-17).
  리뷰어 3인 병렬: bash-reviewer **PASS** · security-reviewer **SIGN OFF** ·
  silent-failure-hunter **SIGN OFF** (🔴 0 · 🟠 0, 🟡 만 — 위 잔여 🟡 절에 기록).
- `[9건 RED 원인 규명]` 8b 커밋 후 스위트가 `Ran 158, failures=9`. **8b 결함으로 오인하지 않기 위해**
  오케스트레이터가 install.sh 를 직접 8개 시나리오로 실행해 계약(마커 7줄·STEPS 토큰 위치·빈 기본값)과
  1:1 대조했다 → **전부 8a 의 픽스처 파급 누락**으로 확정(구현은 계약 준수). 이 실측이 8c 의
  기대값 근거가 됐다(위임 에이전트가 "구현에 맞춰 기대값을 늘리는" 것을 차단).
- `[Task 8c 신설]` 지시서에 없던 파급 수정 task 를 **8a 의 잔무 보정**으로 신설(승인 범위 내).
  `kit-tests` default 위임 → 커밋 `5bc7f0d` (테스트 3파일, +22/-15). python-reviewer **SIGN OFF**
  (🟡 1 — 중복, 기존 문제). 오케스트레이터가 diff 를 자체 실측값과 **바이트 단위 대조**하고
  단언 약화(assertEqual→assertIn·줄 삭제·skip)가 없음을 확인.
- `[검증]` `python3 -m unittest discover -s tests` → **Ran 158 tests, OK** ·
  `bash -n` SYNTAX_OK · `bash scripts/hook-selfcheck.sh` → **HOOK_SELFCHECK_PASS**.
- `[마감]` 승인 범위(8a→8b)를 다 썼으므로 HANDOFF 작성 후 세션 종료. **전부 로컬 커밋 — 푸시 없음.**
  GATE 2·`session-cost.py` 정량 기록·PITFALLS append·docs-index·`phase-close.sh 4` 는 페이즈 마감 시.
