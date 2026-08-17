# Task 4: 설치 마법사 프론트로딩 + 단계 간 뒤로가기

- **목표**: 흩어진 대화 지점(하네스 879 → ECC 언어 911 → 프로바이더 1017 → 요금제 1066)을 실행 단계
  이전의 **마법사 구간**으로 모으고, 어느 스텝에서든 이전 스텝으로 돌아가 선택을 바꿀 수 있게 한다.
  마법사 마지막에 선택 요약을 보여주고 확정 후 1/7~7/7 실행이 시작된다.

## 분할 (전파 제약 5 — kit-scripts 는 `tests/*.py` 편집 권한 없음)

| 하위 task | 에이전트 | 모델 | 대상 파일 | 선행 |
|---|---|---|---|---|
| **4a** RED 테스트 작성 | kit-tests | heavy | `tests/test_install_wizard.py` (신규) | Task 3 |
| **4b** 마법사 구현 | kit-scripts | heavy | `install.sh` | 4a |

두 하위 task 는 **아래 "마법사 계약"을 유일한 인터페이스 정의로 공유한다**. 4a 는 계약에 대해
테스트를 먼저 작성해 RED(마법사 미구현 상태 실패)를 확인하고, 4b 는 계약대로 구현해 GREEN 을 만든다.
4a 는 `install.sh` 를 읽기만 하고 수정하지 않는다. 4b 는 `tests/` 를 수정하지 않는다 —
테스트가 계약과 어긋난다고 판단되면 고치지 말고 **보고**한다(오케스트레이터가 4a 재위임).

---

## 마법사 계약 (4a·4b 공통 — 이 문자열·종료코드가 규격이다)

### 1. 뒤로가기 신호 = 종료코드 10

- `choose_one`·`choose_many`·`choose_one_tui`·`choose_many_tui` 는 사용자가 뒤로가기를 요청하면
  **아무것도 출력하지 않고 `return 10`** 한다. 그 외 동작(기본값 폴백·3회 실패·eof·timeout)은 현행 유지.
- 번호 입력 폴백·SELFTEST 주입 경로: 입력이 `b` 또는 `B` 이면 뒤로 (숫자 유효성 검사 **이전**에 처리,
  재시도 카운터 증가시키지 않음). `choose_many` 의 직접 입력 허용(`allow=1`) 메뉴에서도 `b` 는 예약어다.
- TUI 경로: `read_menu_key` 의 `back` 토큰(ESC 또는 ←)이 곧 뒤로 — 현재의 "기본값 반환" 동작을
  `trap - INT; return 10` 으로 바꾼다.
- `choose_one`/`choose_many` 의 TUI 위임부는 현재 `choose_one_tui "$@"; return 0` 로 종료코드를
  버리고 있다 → **`return $?`** 로 전파해야 한다.
- 호출부는 `_choice=$(choose_one ...)` 직후 `_rc=$?` 로 판정한다 (명령치환이 종료코드를 보존한다).

### 2. `run_install_wizard()` 함수

- 정의 위치: `choose_*` 정의 이후, `INSTALL_SELFTEST_MENU` 블록(현 798행) **이전**.
- 부작용 금지: ECC clone·`gen-policy.sh`·`apply-plan-profile.sh`·`git`·`docker` 를 **절대 호출하지 않는다.**
  변수 확정만 한다. 실행은 기존 1/7~7/7 위치 그대로.
- 자신은 `is_interactive_menu` 를 검사하지 않는다 — 호출 여부는 호출부가 정한다.
- 확정하는 전역: `HARNESSES`, `ECC_LANGS`(배열, `add_ecc_lang` 경유), `PROVIDERS`, `PLAN`.
- 실제로 표시한 스텝 id 를 표시 순서대로(중복 포함) 공백 구분으로 `WIZARD_STEPS_SHOWN` 에 누적한다.
- **stdout 은 셀프테스트 마커 전용이다.** 마법사의 모든 프롬프트·메뉴·안내·요약은 **stderr** 로 낸다
  (`note`·`echo` 는 stdout 이므로 그대로 쓰지 말고 `>&2` 를 붙일 것). 요금제 스텝으로 옮기는
  "토큰 예산" 안내 한 줄도 stderr. 셀프테스트가 stdout 전문 일치로 검증하므로 이 규칙이 깨지면 실패한다.

### 3. 스텝 정의 (id / 순서 / 스킵 조건)

| # | id | 스킵 조건 | 메뉴 | 옵션(순서 고정) |
|---|---|---|---|---|
| 1 | `harness` | `HARNESS_FROM_FLAG=1` | `choose_one` | `claude` `codex` `both` — 현 879행 프롬프트·힌트 문자열 그대로. 기본값은 현 `_harness_default` 계산 유지. `both` → `HARNESSES="claude codex"` |
| 2 | `ecc` | `${#ECC_LANGS[@]} -gt 0` | `choose_many`(allow=1) | 현 911행 옵션·프롬프트 그대로. 결과는 현행 `IFS=,`+`set -f` 루프와 `add_ecc_lang` 그대로 재사용 |
| 3 | `providers` | `-n "$PROVIDERS"` | `choose_many`(allow=0) | `openai` `xai` `qwen` `antigravity` — 현 1017행 그대로 |
| 4 | `plan` | `-n "$PLAN"` **또는** `HARNESSES` 에 `claude` 미포함 | `choose_one` | `pro` `max5` `max20` `skip` — 현 1066행 그대로. 안내 문구(토큰 예산 한 줄)도 이 스텝으로 이동 |
| 5 | `summary` | 없음(항상) | `choose_one` | `start:이 설정으로 설치를 시작한다` `back:이전 단계로 돌아간다`. 직전에 확정된 선택 요약을 stderr 로 출력. `start` 선택 시 마법사 종료 |

### 3-bis. 스킵 조건 보정 (4b 구현 중 확정 — bash-reviewer 검증)

`ecc`·`providers` 스텝의 스킵 조건은 값의 존재만으로 판정하면 **마법사가 채운 값 때문에 뒤로
돌아왔을 때 그 스텝이 영구히 스킵된다.** 따라서 실제 조건은 "**CLI 플래그로 고정된 경우에만 스킵**"이다:
`ecc` = `${#ECC_LANGS[@]} -gt 0` **&& `ECC_LANGS_FROM_FLAG=1`**, `providers` = `-n "$PROVIDERS"`
**&& `PROVIDERS_FROM_FLAG=1`**, `plan` = `PLAN_FROM_FLAG=1` 또는 `HARNESSES` 에 claude 미포함.

### 3-ter. 입력 불가(rc 11) 처리 — 2026-08-11 사용자 결정

리뷰에서 "확인 단계가 무응답 시 자동으로 설치 시작이 된다"는 지적이 나와 사용자에게 물었고,
**"기본값으로 계속 + 명시 안내"** 로 결정됐다 (마법사 도입 이전 동작과 동일한 관용).

- 마법사는 rc 11 을 받으면 남은 스텝을 프롬프트 없이 각자의 기본값으로 확정하고 종료한다.
- **stderr 안내는 구체적이어야 한다** — 어떤 항목이 기본값으로 확정됐는지(하네스·ECC·프로바이더·요금제)
  와 **확인(요약) 단계가 생략됐다는 사실**을 명시한다. 한 줄짜리 모호한 안내는 불충분하다.
- **이 관용은 마법사 안에서만 유효하다.** 실행 시점 동의 게이트(`prompt_yes_no` — sudo 동의,
  Claude CLI 설치 동의)는 **fail-closed 를 유지한다**: 입력을 읽지 못하면 거부(비동의)로 처리하고
  안내를 남긴다. 마법사의 입력 상태를 나타내는 전역 플래그가 `prompt_yes_no` 의 판정에
  영향을 주어서는 **절대** 안 된다 (🔴 사고 사례 — 무단 `npm i -g` 실행).

### 4. 뒤로가기 의미론

- rc=10(또는 summary 에서 `back` 선택) → **직전에 실제로 표시된(스킵되지 않은) 스텝**으로 이동.
- **히스토리 push 규칙**: 스텝 이력은 **전진해서 표시할 때만** 쌓는다. 뒤로가기로 **재표시**되는
  스텝은 push 하지 않는다 — 재표시마다 push 하면 다음 뒤로가기가 그 항목을 pop 해 제자리를 맴돌아
  **연속 뒤로가기가 불가능해진다** (🔴 실측: `INSTALL_SELFTEST_INPUTS='1|1|1|b|b|b|b|b|b'` →
  `STEPS=harness ecc providers plan providers providers ...`). 연속 `b` 로 첫 스텝까지 거슬러 갈 수 있어야 한다.
- 첫 표시 스텝에서 뒤로 → 같은 스텝을 다시 표시한다(마법사를 벗어나지 않는다).
- 스텝 N 으로 되돌아가면 **N 이후 스텝의 확정값을 초기화**한다 — 플래그로 고정된 값(스킵 대상)은 건드리지 않는다.
  예: 하네스를 `claude`→`codex` 로 바꾸면 `PLAN=""` 로 리셋되고 `plan` 스텝은 이후 표시되지 않는다.
- 재진입한 스텝은 **직전 선택을 기본값으로** 제시한다.

### 5. 셀프테스트 훅 `INSTALL_SELFTEST_WIZARD=1`

- `read_line_interactive` 의 주입 조건을
  `[ "${INSTALL_SELFTEST_MENU:-0}" = "1" ] || [ "${INSTALL_SELFTEST_WIZARD:-0}" = "1" ]` 로 확장한다.
  주입 문자열은 환경변수 **`INSTALL_SELFTEST_INPUTS`**(`|` 구분)에서 읽어 `_interactive_selftest_inputs` 에 넣는다.
- 62행 하네스 자동감지 예외 목록에 `INSTALL_SELFTEST_WIZARD` 를 추가한다
  (claude/codex 없는 머신에서 exit 64 방지 — Task 3 잔여 🟡 와 동일 부류).
- **주입 방식 (4b 구현에서 확정 — bash-reviewer 검증)**: `INSTALL_SELFTEST_INPUTS` 를 `|` 로 쪼개
  임시파일에 쓰고 **fd 9** 로 열어 `read_line_interactive` 가 거기서 읽는다. 문자열을 잘라 쓰는
  방식과 달리 **입력이 소진되면 진짜 EOF** 가 나므로 rc 11(입력 불가) 경로가 실제로 검증된다.
  Task 5·8·9 가 스텝을 추가할 때도 이 방식을 그대로 쓴다.
- 블록 위치: `run_install_wizard` 정의 직후, `INSTALL_SELFTEST_MENU` 블록 이전. 파싱된 CLI 플래그를
  **초기화하지 않고 그대로** 마법사에 넘긴다(플래그 스킵 검증용). 출력 후 `exit 0`:

```
SELFTEST WIZARD HARNESSES=<값>
SELFTEST WIZARD ECC=<ECC_LANGS[*]>
SELFTEST WIZARD PROVIDERS=<값>
SELFTEST WIZARD PLAN=<값>
SELFTEST WIZARD STEPS=<표시된 스텝 id 공백 구분>
```

### 6. 계약 시나리오 (4a 가 이대로 테스트를 쓰고, 4b 가 이대로 통과시킨다)

환경: `INSTALL_SELFTEST_WIZARD=1 INSTALL_SELFTEST_INPUTS=<아래>`, 인자 없음(별도 표기 시 제외).

| 시나리오 | 입력 | 기대 |
|---|---|---|
| A 정방향 | `1\|typescript\|1\|2\|1` | `HARNESSES=claude` `ECC=typescript` `PROVIDERS=openai` `PLAN=max5` `STEPS=harness ecc providers plan summary` |
| B 뒤로가기 의존 리셋 (**고정 RED**) | `1\|b\|2\|\|\|1` | `HARNESSES=codex` `ECC=` `PROVIDERS=` `PLAN=` (셋 다 빈 값 — 빈 입력은 기본값 `""`, install.sh:359) `STEPS=harness ecc harness ecc providers summary` |
| C summary 에서 뒤로 | `1\|\|\|1\|2\|4\|1` | `HARNESSES=claude` `ECC=` `PROVIDERS=` (빈 입력) `PLAN=skip` `STEPS=harness ecc providers plan summary plan summary` |
| D 플래그 고정 스텝 스킵 | 인자 `--claude --providers=qwen --plan=pro typescript`, 입력 `1` | `HARNESSES=claude` `ECC=typescript` `PROVIDERS=qwen` `PLAN=pro` `STEPS=summary` |

---

## 4a — RED 테스트 (kit-tests)

- **대상 파일**: `tests/test_install_wizard.py` (신규, 다른 파일 수정 금지)
- **재사용**: 그대로 재사용 `tests/_install_helpers.py:run_install` (신규 러너 작성 금지).
  `INSTALL`·`KIT` 상수도 같은 모듈에서 import — `tests/test_install_menu.py:1-10` 과 동일한 임포트 형태.
- **필수 테스트** (이름 고정):
  - `test_back_navigation_resets_dependent_steps` — 시나리오 B. 리뷰 예상 지점 고정 RED.
  - `test_wizard_forward_flow_collects_all_choices` — 시나리오 A.
  - `test_wizard_summary_back_returns_to_last_visible_step` — 시나리오 C.
  - `test_wizard_skips_steps_fixed_by_flags` — 시나리오 D.
  - `test_wizard_has_no_side_effects` — `install.sh` 소스에서 `run_install_wizard` 함수 본문만 잘라
    `git clone`·`gen-policy.sh`·`apply-plan-profile.sh`·`docker` 문자열이 없음을 정적 검증.
- **필수 규칙**:
  - 실제 홈 오염 금지 — `run_install` 에 임시 `HOME` 을 주입한다(`tempfile.TemporaryDirectory`).
  - 표준 라이브러리 `unittest` 만. 타임아웃은 헬퍼의 `RUN_TIMEOUT` 사용.
  - **RED 확인 필수**: 작성 후 `python3 -m unittest discover -s tests -v` 를 실행해 새 테스트 5개가
    실패하는 출력을 보고에 그대로 붙인다. 기존 테스트는 전부 통과 상태를 유지해야 한다.
- **완료 조건**: 새 테스트 5개 FAIL + 기존 테스트 전원 PASS 출력 첨부.

## 4b — 마법사 구현 (kit-scripts)

- **대상 파일**: `install.sh` (단일)
- **재사용**: 개선 후 재사용 — 기존 4개 대화 지점의 메뉴 호출을 스텝 함수로 이동(호출부 4곳).
  메뉴 렌더는 Task 3 의 `choose_one`/`choose_many` 그대로. 새 헬퍼는 스텝 배열·상태 저장용 최소한만
  (`ECC_LANGS` 확정은 기존 `add_ecc_lang` 재사용, 새 파서 작성 금지).
- **필수 규칙**:
  - **bash 3.2 호환** — 연관배열·`mapfile`·`${v,,}` 금지. 배열 추가는 `ARR[${#ARR[@]}]=x`.
  - 비대화형·`INSTALL_DRY_RUN=1` 경로의 현행 동작 불변: 마법사 호출부는
    `[ "${INSTALL_DRY_RUN:-0}" != "1" ] && is_interactive_menu` 일 때만. 비대화형 안내
    (`notify_noninteractive_harness`·`report_ecc_lang_skip`·프로바이더 안내 echo·`report_plan_skip`)는
    **기존 위치에 그대로 남긴다** — 각 안내가 한 번만 나오는 현행 보장을 깨지 말 것
    (`tests/test_install_menu.py::test_selftest_reports_each_noninteractive_skip_once`).
  - sudo 동의(362)·설치 동의(543)는 실행 시점 확인이므로 마법사로 옮기지 않는다.
  - 기존 `INSTALL_SELFTEST_MENU` 블록(798-)은 그대로 동작해야 한다 — 마법사 도입으로 깨뜨리지 말 것.
  - `[ "$PLAN" = "skip" ] && PLAN=""` 매핑은 기존 요금제 섹션 위치에 그대로 둔다.
- **완료 조건**: `bash -n install.sh` + `python3 -m unittest discover -s tests -v` 전원 GREEN
  (4a 의 신규 테스트 5개 포함) + 계약 시나리오 A~D 를 직접 실행한 출력 첨부.

## 4c — pty 회귀 테스트에 유휴 상한 주입 (kit-tests)

4b 2차 반려의 후속. 메뉴 read 의 기본 유휴 타임아웃(5초)을 제거하면서, pty 자동화 테스트가
블록되지 않도록 `INSTALL_MENU_IDLE_LIMIT="2"` 를 주입하도록 `tests/test_install_wizard.py`·
`tests/test_install_claude_bootstrap.py` 를 수정하고, 기본값 재발 방지 테스트
`test_menu_read_has_no_default_idle_timeout` 를 추가했다.

## 진행 이력 (2026-08-11)

| 단계 | 결과 |
|---|---|
| 4a 위임(kit-tests) | 반려 1회(빈 입력=기본값 오해) → 수정 → python-reviewer PASS → `3e043fe` |
| 4b 위임(kit-scripts) | 반려 2회 → 수정 → `d71227c` |
| 4b 1차 반려 | 마법사 호출을 `INSTALL_PLAIN_MENU != 1` 로 가드해 그 모드의 선택 메뉴가 소멸 |
| 4b 2차 반려 | 메뉴 read 기본 유휴 타임아웃 5초가 느린 응답을 조용히 폐기 |
| 4c 위임(kit-tests) | `d741d33` |
| 최종 리뷰(병렬 3종) | bash-reviewer PASS · security-reviewer PASS(🟡 1) · silent-failure-hunter 🟠 1 — **🔴 0 → PASS** |

### 최종 검수 실측
- `bash -n install.sh` OK / `python3 -m unittest discover -s tests` → **136 tests OK**
- `grep -n INSTALL_PLAIN_MENU install.sh` → `is_tui_menu`(install.sh:166) 1곳만
- pty 실측 exit 0, 메뉴 표시 → 안내 → 기본값 확정 → 7/7 완주, 실제 홈 오염 없음

### 이월 (Task 6)
- 🟠 `test_menu_read_has_no_default_idle_timeout` 이 정적 substring 단언이라 변이 회피 가능 →
  런타임 pty 검사로 교체
- 🟡 TUI `INT` 트랩의 `exit 130` 이 셀프테스트 fd 9 임시 파일 정리를 건너뜀
