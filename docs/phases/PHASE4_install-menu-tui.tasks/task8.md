# Task 8: 마법사 컨테이너 스텝 + insane-cloak 설치 자동화 (8a/8b 분할)

> 전파 제약 5에 따라 **8a(kit-tests, RED) → 8b(kit-scripts, 구현)** 으로 분할한다.
> 아래 **공유 계약 C1~C12 가 두 에이전트의 유일한 진실의 원천**이다.

## 전제 실측 (2026-08-12, 세션 5)

| 전제 | 근거 | 판정 |
|---|---|---|
| 컨테이너 플래그는 `--with` | install.sh:56 — 실제로는 `--containers=<콤마목록>` | **뒤집힘** → 계약은 `--containers=` 기준 |
| 마법사 스텝은 1~6, 마커 6줄 | install.sh:831-1030, 1119-1124 (AUTH 추가로 6줄) | 유지 — 컨테이너 삽입 시 7스텝·7마커 |
| 실행 단계 컨테이너 블록은 수동 안내만 | install.sh:1350-1368 (`run_auth_logins` 직후) | 유지 |
| auth 가 단일소스 argv 패턴을 이미 씀 | install.sh:1065-1083 (`build_auth_login_argv`/`auth_login_command`) | 유지 — 컨테이너도 그대로 미러 |
| 마법사 본문 금지 문자열 검사가 존재 | tests/test_install_wizard.py `test_wizard_has_no_side_effects` — `git clone`·`gen-policy.sh`·`apply-plan-profile.sh`·**`docker`**·`auth login` | 유지 — **라벨·주석에도 `docker` 금지** |
| insane-cloak compose project 명은 고정 | `containers/browser/docker-compose.yml:23` `name: chrome-cdp`, `container_name: chrome-cdp`, 포트 9222(CDP)·9223(fetch API) | 유지 — 남의 chrome-cdp 와 충돌 가능 → 포트 검사 필수 |

## 공유 계약 (8a·8b 공통 — 위임 프롬프트에 그대로 인라인)

- **C1 재번호**: 스텝 5=컨테이너, 6=요금제, 7=요약. `_wizard_history` 값·`_wizard_step` 전이·
  rc=11 폴백 블록의 `[ "$_wizard_step" -le 5 ]` → `-le 6` 을 **함께** 갱신한다.
- **C2 스킵 조건**: `--containers=` 로 값이 온 경우 `CONTAINERS_FROM_FLAG=1`(신설, `PLAN_FROM_FLAG` 패턴)
  → 스텝 5 를 표시하지 않고 6 으로. 그 외에는 항상 표시.
- **C3 위젯**: `choose_many "설치할 컨테이너를 고른다" "$CONTAINERS" 0 "browser:스텔스 브라우저 컨테이너 (CDP·우회 fetch)"`.
  rc **10** → back, rc **11** → `CONTAINERS=""`. 결과는 **콤마 구분**으로 `CONTAINERS` 에 대입(플래그와 동일 형식).
- **C4 스텝 토큰**: `WIZARD_STEPS_SHOWN` 에 `containers` — `auth` 와 `plan` 사이.
- **C5 마커**: `printf 'SELFTEST WIZARD CONTAINERS=%s\n' "$CONTAINERS"` 를 **AUTH 다음 줄**에 삽입 → 마커 **7줄**.
  기존 마커 테스트 3건(test_install_wizard.py:26-30·49-53·72-76 계열) 갱신은 **8a 책임**.
- **C6 부작용 금지**: 마법사 함수 본문에 `docker`·`git clone`·`gen-policy.sh`·`apply-plan-profile.sh`·`auth login`
  문자열을 **주석·라벨 포함** 넣지 말 것.
- **C7 단일 소스**: `CONTAINER_UP_ARGV` 전역 배열이 유일한 소스(bash 3.2 nameref 없음).
  `build_container_up_argv <이름>` 이 화이트리스트 `{browser}` 를 강제(그 외 `return 1`),
  `container_up_command <이름>` 은 **렌더링 전용**(`eval`·표시 문자열 재실행 금지),
  실행은 항상 `"${CONTAINER_UP_ARGV[@]}"`. auth 패턴(install.sh:1065-1083)을 그대로 미러.
- **C8 셀프테스트**: `INSTALL_SELFTEST_CONTAINERS=1` 블록을 `INSTALL_SELFTEST_AUTH` 블록
  (install.sh:1128~) **바로 뒤**에 추가하고 `exit 0`. 주입 변수:
  `INSTALL_CONTAINERS`(콤마 목록) / `INSTALL_CONTAINER_FAKE=ok|docker_missing|port_busy|submodule_missing`(기본 ok) /
  `INSTALL_CONTAINER_CONSENT=y|n`(기본 y). stdout 마커:
  - `CONTAINER_SUBMODULE_WOULD_INIT=browser`
  - `CONTAINER_INSTALL_WOULD_RUN=browser <container_up_command 렌더링>`
  - `CONTAINER_INSTALL_SKIPPED=browser reason=docker_missing|port_busy|declined|unknown`
- **C9 비치명**: 서브모듈 init 실패·docker 부재·데몬 미기동·compose 부재·포트 충돌·up 실패 —
  **어느 것도 설치를 중단시키지 않는다**(`set -euo pipefail` 하에서 `|| { ... }` 명시).
  실패·스킵 시 기존 수동 안내(install.sh:1358-1362)를 폴백으로 출력한다.
- **C10 동의 게이트**: 실제 기동 전 `prompt_yes_no` 필수(fail-closed — **rc 11 관용 전파 금지**).
  "이미지 빌드에 수 분이 걸릴 수 있다"를 안내에 포함.
- **C11 포트 충돌**: 9222 가 이미 리스닝이면 up 을 시도하지 말고 감지·안내(`reason=port_busy`).
  검사는 **bash 내장 `/dev/tcp`** 로 — `ss`·`lsof`·`nc` 등 외부 의존성 금지.
  근거: compose project·container 명이 `chrome-cdp` 로 고정이라 **다른 사용자의 CDP 세션과 충돌**한다.
- **C12 범위 경계**: `CLAUDE_INSTALL_FAILED` 집계 접합은 **Task 6b 스코프** — 8b 는 건드리지 않는다.
  셀프테스트 블록 밖에 **새 stdout 마커 추가 금지**(기존 테스트가 stdout 전체를 assertEqual).

---

## Task 8a: 컨테이너 스텝 RED 테스트

- **에이전트**: kit-tests
- **모델**: heavy
- **대상 파일**: `tests/test_install_container_step.py`(신규), `tests/test_install_wizard.py`(마커 갱신)
- **선행**: Task 5b (완료)
- **목표**: 계약 C1~C11 을 고정하는 실패 테스트를 먼저 작성하고 RED 를 확인한다.
- **재사용**: 그대로 재사용 `tests/_install_helpers.py`(SELFTEST 실행 헬퍼) — 새 실행 헬퍼 금지.
  구조는 `tests/test_install_auth_step.py` 를 본뜬다.
- **실패 테스트** (11건):
  1. `test_container_step_marker_and_steps` — browser 선택 시 `SELFTEST WIZARD CONTAINERS=browser` + STEPS 에 `containers`
  2. `test_container_step_skipped_with_flag` — `--containers=browser` 지정 시 STEPS 에 `containers` 없음, CONTAINERS 값은 유지
  3. `test_container_step_back_navigation` — 컨테이너 스텝에서 `b` → 이전 스텝 복귀, 이후 정방향 재진행 가능
  4. `test_container_step_empty_selection` — 미선택이면 `CONTAINERS=` 빈 값, 실행 마커 없음
  5. `test_wizard_marker_lines_are_seven` — 마커 7줄 + 순서(HARNESSES/ECC/PROVIDERS/AUTH/CONTAINERS/PLAN/STEPS), 기존 3건 갱신
  6. `test_container_install_would_run` — `INSTALL_SELFTEST_CONTAINERS=1 INSTALL_CONTAINERS=browser` → `CONTAINER_INSTALL_WOULD_RUN=browser ...`
  7. `test_container_install_skipped_when_docker_missing` → `reason=docker_missing`
  8. `test_container_install_skipped_when_port_busy` → `reason=port_busy`
  9. `test_container_install_declined` — `INSTALL_CONTAINER_CONSENT=n` → `reason=declined`, WOULD_RUN 없음
  10. `test_unknown_container_rejected` — `INSTALL_CONTAINERS=foo` → stderr 경고만, stdout 마커 없음
  11. `test_container_up_command_single_source` — `up -d` 지식이 소스에 **한 벌**만 존재(`grep` 상당 정적 검사 + 렌더링 결과 대조)
- **필수 규칙**:
  - `INSTALL_PARSE_ONLY` 로 검증 금지 — 반드시 SELFTEST 경로.
  - 실제 홈·실제 docker 를 건드리지 말 것. 모든 실행은 임시 HOME + SELFTEST 주입.
  - **변이 검증을 하지 말 것** — 변이시킬 구현이 아직 없다(PITFALLS 9). 8b 의 완료 조건이다.
  - 스크래치 사본이 필요하면 `.orchestrate/mut8a/` — `/tmp` 등 저장소 밖 쓰기 금지(PITFALLS 8).
  - 공유 워크트리에서 `git stash` 금지. `git add` 는 경로 명시.
- **완료 조건**: ① 11건 RED 출력 첨부 ② 실패가 컨테이너 계약 범위로만 국한됨(기존 145건 중
  마커 3건 외 회귀 없음)을 `python3 -m unittest discover -s tests` 출력으로 제시

---

## Task 8b: 컨테이너 스텝 + 자동 설치 구현

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`
- **선행**: Task 8a
- **목표**: 계약 C1~C12 대로 마법사 스텝 5(컨테이너)를 추가하고, 실행 단계에서 서브모듈 init →
  docker 가용성·포트 확인 → 동의 → `compose up -d` 까지 자동 수행한다. 8a 의 11건을 GREEN 으로.
- **재사용**: 개선 후 재사용 `install.sh:1350-1368` 컨테이너 블록(호출부 1곳) — 수동 안내는
  **폴백 메시지로 유지**. argv 단일소스 패턴은 `install.sh:1065-1083` 미러. 스텝 구조는 Task 4,
  체크박스는 Task 3 `choose_many`. **새 메뉴 헬퍼·새 실행 헬퍼 금지**.
- **실패 테스트**: 8a 가 작성한 11건 (구현 전 RED 확인 후 착수)
- **필수 규칙**: 계약 C1~C12 전부 + 아래
  - `--containers=` 로 지정한 경로도 **동의 후 자동 설치**를 수행한다(사용자 결정 2026-08-12).
    비대화형(비TTY·SELFTEST)에서는 프롬프트 없이 현행대로 안내 폴백.
  - 이 킷 번들 `containers/<이름>` 한정 — 다른 실행 중 컨테이너·`/opt/chrome-cdp` 를 건드리지 않는다.
  - bash 3.2 호환(연관배열·mapfile·`${v,,}`·소수점 `read -t` 금지).
  - `tests/*.py` 편집 권한 없음 — 테스트가 계약과 다르면 고치지 말고 **보고**할 것.
  - 스크래치·변이 사본은 `.orchestrate/mut8b/`. `git stash` 금지, `git add` 경로 명시.
- **완료 조건**:
  1. `bash -n install.sh` OK
  2. `python3 -m unittest discover -s tests` 전부 GREEN (8a 11건 포함)
  3. 단일소스: `grep -c "up -d" install.sh` → **1**, `grep -c "chrome-cdp" install.sh` → 0
     (컨테이너 이름 지식은 compose 파일이 소유 — install.sh 에 하드코딩 금지)
  4. 변이 검증 3종(`.orchestrate/mut8b/` 사본): ① 동의 게이트 제거 → 9번 FAIL
     ② 포트 검사 제거 → 8번 FAIL ③ 스텝 5 블록 제거 → 1·5번 FAIL — 결과 표 첨부
