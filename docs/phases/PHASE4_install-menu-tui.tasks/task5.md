# Task 5: 구독 프로바이더 인증 — 마법사 동의 스텝 + 실행 시점 로그인

> 세션 4 인터뷰(2026-08-11)로 **원안 대비 2건이 바뀌었다**:
> ① 동의 질문을 6/7 실행 시점이 아니라 **마법사 스텝으로 편입**(프론트로딩 계약 유지).
> ② 셀프테스트 우회는 `INSTALL_SELFTEST_MENU`가 아니라 **`INSTALL_SELFTEST_AUTH`** —
>    전파 제약 1(SELFTEST_MENU 경로는 exit 0이라 메인 흐름 미도달) 때문에 원안은 성립하지 않는다.
>
> 제약 5에 따라 **5a(kit-tests RED) → 5b(kit-scripts 구현)** 으로 분할한다.
> 아래 「공유 계약」은 두 에이전트가 **똑같이** 따라야 하는 확정 사항이다 — 임의 변경 금지.

---

## 공유 계약 (5a·5b 공통 — 변경 금지)

### C1. 마법사 스텝 번호

`run_install_wizard()`의 스텝이 하나 늘어난다. **auth 는 providers 바로 다음**이다:

| 스텝 | 현재 | 변경 후 |
|---|---|---|
| 1 | harness | harness |
| 2 | ecc | ecc |
| 3 | providers | providers |
| 4 | plan | **auth (신규)** |
| 5 | summary | plan |
| 6 | — | summary |

### C2. auth 스텝 동작

- **스킵 조건**: 선택된 `PROVIDERS`에 구독형(`openai`·`xai`)이 **하나도 없으면 스텝 자체를 건너뛴다**
  (`WIZARD_STEPS_SHOWN`에 `auth` 토큰도 남기지 않는다). `qwen`·`antigravity`는 키 기반이라 대상 아님.
- **질문**: `choose_many "설치 후 바로 로그인할 구독 프로바이더를 고른다" "<선택된 구독 프로바이더 전체>" 0 <해당 항목들>`
  - `prompt_yes_no` 를 쓰지 말 것 — 뒤로가기(rc 10)를 지원하지 않아 마법사 계약이 깨진다.
  - 기본값 = 선택된 구독 프로바이더 전체. **빈 입력은 기본값 그대로 반환된다**(제약 8) — 정상 동작이다.
- **결정 변수**: `AUTH_LOGIN` — 공백 구분 프로바이더 목록, 미선택이면 빈 문자열.
  `PROVIDERS` 에 나온 순서를 유지한다.
- **rc 10(뒤로가기)**: 다른 스텝과 동일하게 `_wizard_back=1`.
- **rc 11(입력 불가)**: **fail-closed — `AUTH_LOGIN=""`** (제약 7: rc 11 관용을 동의에 전파 금지).
  기존 rc 11 처리 블록의 안내 문구에 추가할 필요는 없다(로그인 안 함이 기본이므로).
- **뒤로가기 리셋**: 스텝 1·2·3 으로 되돌아가면 `AUTH_LOGIN=""` 도 함께 초기화한다
  (`PROVIDERS`가 바뀌면 대상이 바뀌므로). 스텝 4(auth)로 되돌아가면 `PLAN`만 초기화한다.

### C3. 셀프테스트 마커

`INSTALL_SELFTEST_WIZARD=1` 출력에 **한 줄 추가**한다. 위치는 `PROVIDERS` 다음, `PLAN` 앞
(스텝 순서와 일치):

```
SELFTEST WIZARD AUTH=<AUTH_LOGIN 값>
```

`STEPS` 토큰 이름은 **`auth`**. 예: 구독 프로바이더 선택 시
`STEPS=harness ecc providers auth plan summary`.

> **기존 테스트 3건의 기대값이 깨진다** — 마커 5줄이 6줄이 되고 STEPS 토큰이 늘어난다.
> 갱신은 5a 의 책임이다 (5b 는 `tests/*.py` 편집 권한이 없다).

### C4. 실행 시점 (6/7 뒤, 7/7 앞)

- 실행 블록은 **함수 `run_auth_logins()`** 로 분리한다 (셀프테스트가 단위 호출할 수 있어야 한다).
- 호출 위치: `say "6/7 모델 프로바이더"` 블록의 gen-policy 처리가 끝난 **직후**,
  `say "7/7 검증"` **앞**. 이 순서여야 7/7 model-doctor 가 인증 완료 상태에서 돈다.
- `AUTH_LOGIN` 이 비어 있으면 아무것도 하지 않는다(무출력).
- 프로바이더별 명령 (안내 블록과 **문자열이 갈라지면 안 된다** — 단일 소스로):
  - `xai` → `~/.opencode/bin/opencode auth login -p xai`
  - `openai` → `~/.opencode/bin/opencode auth login -p openai -m "ChatGPT Pro/Plus (headless)"`
- **실패 내성**: `set -euo pipefail` 이 켜져 있다. 로그인 실패·Ctrl-C(130)가 설치를 죽이면 안 된다.
  실패해도 다음 프로바이더를 계속 시도하고, `run_auth_logins` 는 **항상 0을 반환**한다.
  실패한 프로바이더는 `note "⚠️ ..."` 경고를 남기고 「남은 수동 단계」 안내에 그대로 유지한다.
- 시크릿(키 값·토큰)을 stdout·로그에 남기지 않는다. 프로바이더 이름까지만.

### C5. 셀프테스트 우회 (5a 가 검증에 쓴다)

`INSTALL_SELFTEST_WIZARD` 블록과 **동형**으로, 마법사 셀프테스트 블록 근처에 추가한다:

- 진입: `INSTALL_SELFTEST_AUTH=1`
- 입력 주입: `INSTALL_AUTH_LOGIN=<공백 구분 프로바이더>` → `AUTH_LOGIN` 에 대입
- 실패 주입: `INSTALL_AUTH_FAIL=<공백 구분 프로바이더>` → 그 프로바이더는 실패한 것으로 처리
- 동작: 실제 `opencode auth login` 을 **실행하지 않고** 프로바이더당 한 줄씩 stdout 출력 후 `exit 0`
  - 성공 예정: `AUTH_LOGIN_WOULD_RUN=<provider> <실행될 명령 전체>`
  - 실패 주입분: `AUTH_LOGIN_FAILED=<provider>`
- 출력 순서는 `AUTH_LOGIN` 순서를 따른다.

---

## Task 5a: 마법사 auth 스텝 RED 테스트

- **에이전트**: kit-tests
- **모델**: heavy
- **대상 파일**: `tests/test_install_auth_step.py`(신규), `tests/test_install_wizard.py`(기대값 갱신)
- **선행**: Task 4 (완료)
- **목표**: 위 공유 계약 C1~C5 를 그대로 검증하는 테스트를 먼저 작성해 **RED 를 확인**한다.
  5b 구현 전이므로 신규 테스트는 전부 실패해야 하고, 갱신한 기존 wizard 테스트도 실패해야 한다.
- **재사용**: 그대로 재사용 `tests/_install_helpers.py` (셀프테스트 실행 헬퍼) ·
  `tests/test_install_wizard.py` 의 `INSTALL_SELFTEST_WIZARD`·`INSTALL_SELFTEST_INPUTS` 호출 패턴 —
  **새 헬퍼를 만들지 말 것**. 검색어: `SELFTEST_WIZARD`, `_install_helpers`, `run_install`
- **실패 테스트** (신규 **9건** + 기존 갱신 — 리뷰 2라운드로 4건 증보, 2026-08-11 정정):
  1. `test_auth_step_skipped_without_subscription_provider` — `qwen` 만 선택 → `STEPS` 에 `auth` 없음, `AUTH=` 빈값
  2. `test_auth_step_collects_subscription_providers` — `openai` 선택 → `STEPS` 에 `auth` 포함, `AUTH=openai`
  3. `test_auth_step_back_returns_to_providers` — auth 스텝에서 `b` → providers 재질문.
     stdout 전체 `assertEqual` (STEPS = `harness ecc providers auth providers auth plan summary`)
  4. `test_auth_default_covers_subscription_providers_in_providers_order` — 키 기반+구독형 혼합
     (`3 1 2` → `PROVIDERS=qwen,openai,xai`) + auth 빈 입력 → `AUTH=openai xai` (qwen 제외·공백 구분)
  5. `test_auth_selection_follows_providers_order` — `2 1` → `PROVIDERS=xai,openai` · `AUTH=xai openai`.
     **카탈로그 고정 순서(openai,xai,…)와 어긋나는 케이스** — 카탈로그를 훑는 구현을 걸러낸다
  6. `test_back_to_providers_clears_auth_when_subscription_dropped` — auth 에서 `b` → providers 를
     키 기반(qwen)으로 교체 → `AUTH=` 빈값. **back 리셋에서 `AUTH_LOGIN` 누락**을 걸러낸다
  7. `test_auth_step_read_failure_is_fail_closed` — `__READ_FAILURE__` 주입(rc 11) → `choose_many` 가
     기본값을 출력해도 마법사는 **`AUTH=` 빈값으로 fail-closed**, `STEPS=harness ecc providers auth`
  8. `test_auth_selftest_reports_would_run_without_executing` — `INSTALL_SELFTEST_AUTH=1` +
     `INSTALL_AUTH_LOGIN="xai openai"` → `AUTH_LOGIN_WOULD_RUN=` 2줄, 명령 문자열이 C4 와 일치
  9. `test_auth_failure_does_not_abort_install` — `INSTALL_AUTH_FAIL=xai` 주입 →
     `AUTH_LOGIN_FAILED=xai` 출력 + **exit 0** + 뒤 프로바이더(openai) 줄이 계속 나옴
  10. 기존 `test_wizard_has_no_side_effects` 의 금지 목록에 **`auth login` 추가**
     (마법사 함수 본문에서 실제 로그인이 일어나면 안 된다 — 제약 9 의 확장)
  11. 기존 **4건**(`test_back_navigation_resets_dependent_steps` ·
     `test_wizard_forward_flow_collects_all_choices` · `test_wizard_skips_steps_fixed_by_flags` ·
     `test_wizard_summary_back_returns_to_last_visible_step`)의 마커 5줄 → 6줄, STEPS 기대값 갱신
     (초안이 "3건"으로 잘못 셌다 — `skips_steps_fixed_by_flags` 누락이 1라운드 🔴 사유)
- **필수 규칙**:
  - ~~변이 검증 필수~~ → **5b 로 이관**(2026-08-11 정정). RED 시점에는 변이시킬 구현이 없어
    항상 참인 검증이 된다 (PITFALLS 9). 5a 는 RED 출력 + 실패 범위 국한만 증명한다.
  - 실제 `opencode auth login` 이 테스트 중 절대 실행되면 안 된다 — 셀프테스트 우회만 사용.
  - 실제 `~/.claude`·`~/.config` 오염 금지 — `HOME` 은 임시 디렉터리 주입.
  - `install.sh` 를 수정하지 말 것 (구현은 5b 담당).
- **완료 조건**: 신규·갱신 테스트가 **RED** 임을 출력으로 증명 + `python3 -m unittest discover -s tests`
  실행 결과에서 실패가 auth 관련 항목으로만 국한됨을 확인

## Task 5b: 마법사 auth 스텝 + 실행 시점 로그인 구현

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`
- **선행**: Task 5a
- **목표**: 공유 계약 C1~C5 를 구현해 5a 의 테스트를 GREEN 으로 만든다.
  클린 호스트에서 7/7 model-doctor 가 인증 완료 상태로 돌아, 첫인상이 "설치 실패"가 아니게 한다.
- **재사용**: 그대로 재사용 `choose_many`(install.sh:365) · `note`(:82) ·
  「남은 수동 단계」 안내 블록(install.sh:1277-)의 로그인 명령 문자열 —
  **명령 문자열을 복사하지 말고 단일 소스로 묶을 것**(안내 블록의 heredoc 은 quoted 라 확장되지
  않으므로, 해당 2줄을 함수·printf 로 빼내는 방식 등 재량. 두 곳에 같은 문자열이 남으면 🔴).
  검색어: `auth login`, `choose_many`, `run_install_wizard`
- **실패 테스트**: 5a 가 작성한 `tests/test_install_auth_step.py` 전부 + 갱신된
  `tests/test_install_wizard.py`. **먼저 실행해 RED 를 확인한 뒤** 구현에 들어갈 것.
- **필수 규칙**:
  - `tests/*.py` 를 편집하지 말 것 — 권한이 없다. 테스트가 계약과 다르면 **고치지 말고 보고**한다.
  - TUI 계약(제약 2): `trap ... INT` 진입 설정과 **모든 return 직전 해제**. 새 조기 return 경로 주의.
  - 메뉴 read 에 **기본 유휴 타임아웃을 두지 말 것**(제약 3, 4b 2차 반려 사유).
  - 마법사 함수 본문 안에서 실제 부수효과(로그인 실행 포함) 금지 — 실행은 6/7 뒤 `run_auth_logins()`.
  - 함수 본문에 heredoc 금지, **주석에도 `git clone`·`gen-policy.sh`·`apply-plan-profile.sh`·
    `docker`·`auth login` 문자열을 쓰지 말 것**(제약 9 — 정적 검사가 부분 문자열로 자른다).
  - 마법사의 stdout 은 마커 전용 — 프롬프트·안내·요약은 전부 stderr(제약 7).
  - 비TTY(비대화형)에서는 마법사가 돌지 않으므로 `AUTH_LOGIN` 은 빈 값 → 현행 안내만 유지.
  - 커밋 금지(오케스트레이터가 수행). 대상 파일 외 수정 금지.
  - **변이 검증 필수 (5a 에서 이관)** — 구현이 GREEN 이 된 뒤, `install.sh` 사본을
    **`.orchestrate/mut5/`** (gitignore 경로 — `/tmp` 등 저장소 밖은 opencode 가 자동 거부한다,
    PITFALLS 8) 에 만들어 아래 2건을 각각 망가뜨리고 해당 테스트가 **실제로 실패**하는지 확인한다.
    검증 후 `.orchestrate/mut5/` 는 삭제한다. 명령과 출력을 보고에 첨부할 것.
    1. **C2 스킵 조건 제거** (구독 프로바이더가 없어도 auth 스텝을 돌게 함) →
       `test_auth_step_skipped_without_subscription_provider` 실패해야 함
    2. **C4 실패 내성 제거** (로그인 실패 시 `run_auth_logins` 가 비0 반환·중단) →
       `test_auth_failure_does_not_abort_install` 실패해야 함
    - 사본 실행 방법: `tests/_install_helpers.py:17` 이 `KIT/install.sh` 를 **하드코딩**하므로
      `run_install()` 로는 사본을 못 돌린다. 사본을 `install.sh` 자리에 임시로 놓고 원본을
      되돌리는 방식은 **금지**(공유 워크트리 — 다른 위임이 죽는다). `bash .orchestrate/mut5/install.sh`
      를 직접 실행해 해당 테스트가 단언하는 출력이 달라짐을 보이면 된다.
- **완료 조건**:
  - `bash -n install.sh` 통과
  - `python3 -m unittest discover -s tests` **전체 GREEN**(145 tests — 5a 완료 시점 실측.
    5a RED 상태는 145 tests / 13 failures)
  - `grep -c "auth login -p xai" install.sh` → **1** (드리프트 없음 증명)
  - 변이 검증 2건의 명령·출력 첨부
