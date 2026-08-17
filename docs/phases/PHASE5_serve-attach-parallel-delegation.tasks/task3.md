# Task 3: 회귀 테스트 보강

- **담당**: **오케스트레이터 직접 구현** (사용자 결정 2026-08-13)
  > 근거: 2b~2d 반려 사유가 **전부 테스트 품질**이었고(“통과하는데 아무것도 검증하지 않는” 사례
  > 7건), 실제 검출은 매번 위임이 아니라 **검수자의 변이 검증**이 했다. 스크립트 축(2e·2f)은
  > `kit-scripts` 위임을 유지한다. 이 결정은 Task 4 에서 로스터 `kit-tests` 항목에 반영한다.
- **모델**: - (위임 없음)
- **대상 파일**: `tests/test_run_delegation.py` (확장), `tests/test_serve_ctl.py` (확장)
- **선행**: **Task 2e·2f 커밋 후** — 2e 가 ctl 액션 픽스처를, 2f 가 `ps` 스텁을 바꾸므로
  먼저 하면 두 번 작업하게 된다.
- **목표**: "락 산출물이 존재하는가"만 보는 현재 단정을 **행동 검증**으로 바꾸고,
  전파(Task 5) 후 4개 프로젝트 동시 위임에서 상호배제가 깨지는 회귀를 막는다.
- **재사용**: 기존 테스트 파일을 **확장**한다 — 새 테스트 파일 금지. 스텁·임시 디렉터리는
  `tests/test_serve_ctl.py` 가 쓰는 방식(stdlib `tempfile` + PATH 선행 스텁)을 따른다.
  > ⚠️ **`tests/_install_helpers.py` 에 새 의존을 만들지 말 것** — 병행 브랜치
  > (`feat/public-release-0811`, phase4 워크트리)가 이 파일을 +52줄 수정 중이다(2026-08-12 실측).

## 항목 (2d 리뷰 이월 C28~C31)

### 🔴 C28 — 상호배제를 **행동으로** 검증하는 테스트가 저장소에 하나도 없다

현재 단정은 락 파일·디렉터리의 **존재**만 본다. 생존 변이 2건(2d 리뷰 재현):
- flock 환경: `if ! flock -n 9; then` → `if false; then` (파일은 `exec 9>` 로 여전히 생성) → 그린
- 비flock 환경: 배타적 `mkdir "$MLOCK"` 을 항상 성공하도록 변경 → 그린

**설계 (동시 프로세스 2개 + 실행 구간 겹침 판정)**

1. `opencode` 스텁을 PATH 선행에 두고, 스텁이 자기 실행 구간을 기록하게 한다:
   실행 시작 시 `START <epoch.ns>`, `sleep <HOLD>` 후 `END <epoch.ns>` 를 **공유 파일에 append**
   (append 는 원자적이어야 하므로 한 줄씩 `printf`).
2. 같은 프로젝트 디렉터리에서 `run-delegation.sh` 를 **`subprocess.Popen` 2개로 동시 기동**하고
   둘 다 종료할 때까지 기다린다.
3. 단정: 두 실행 구간 `[START_i, END_i]` 가 **겹치지 않는다**. 순서는 단정하지 않는다
   (경합 순서는 비결정적 — 순서를 단정하면 이 페이즈에서 이미 나온 "비결정 테스트" 함정 재발).
4. `HOLD` 는 1.5~2초. 겹침 판정은 `min(END) <= max(START)` 로 한다.

**완료 조건**: 위 변이 2건을 각각 적용하면 이 테스트가 **죽어야** 한다
(`.orchestrate/mutation/` 사본에서 확인, 결과를 보고에 첨부).

### 🟠 C29 — 락 이름 단정이 비flock 환경에서 프로젝트/전역 구분을 잃는다

`assert_lock_snapshot(project=True)` 의 유일한 이름 단정이 `assertNotEqual(lock.name, "opencode.lock")`
인데 비flock 산출물은 `opencode.lock.d` 라 **전역 락으로 회귀해도 통과**한다.

> **이력 — 이게 "단정 약화" 7번째 사례다.** 원래 `assertEqual(len(locks), 1)` 이었는데 비flock
> 에서 4건 FAIL 하자 `len(locks)+len(lock_dirs)==1` 로 완화해 그린을 만들었다. **환경 차이는
> 단정을 지우는 이유가 아니라 환경을 인지해 각각 단언하라는 뜻이다.**

수정: 접미사를 정규화한 뒤 단정한다 —
`stem = lock.name[:-2] if lock.name.endswith(".d") else lock.name`,
`project=True` → `stem.startswith("opencode-")`, `project=False` → `stem == "opencode.lock"`.
**변이 기준**: `LOCK_FILE` 을 전역 락 이름으로 되돌리면 flock **유무 양쪽에서** FAIL 해야 한다.

### 🟡 C30 — 권한 테스트가 umask 에 의존한다
`chmod` 두 줄을 `true` 로 변이하면 `umask 022` 에서는 FAIL 하지만 `umask 077` 에서는 생존한다.
테스트가 umask 를 **명시 주입**하도록 고친다. (2e 의 원자 생성 변경과 정합을 맞출 것)

### 🟡 C31 — `COUNT_FILE` 정리 누락
C11 이 지시한 미사용 `COUNT_FILE` 이 `tests/test_run_delegation.py:372` 에 남아 있다. 제거.

### 기존 계획분 (Task 1·2 시점)
- `::test_lock_slug_stable_across_workdirs` — 같은 프로젝트를 다른 cwd(워크트리)에서 호출해도 slug 동일
- `::test_lock_slug_distinct_for_same_basename` — basename 이 같은 두 프로젝트는 락이 다르다
- `::test_serve_env_missing_gives_clear_error` — `serve.env` 부재 시 attach 를 건너뛰고 폴백 + 안내 출력
- `::test_lock_released_on_wrapper_kill` — 래퍼가 SIGTERM 으로 죽어도 락이 남지 않는다
- attach 모드에서 **전역 락을 잡지 않음**을 단언 (현재 글롭이 매칭되지 않아 공허하다)
- `test_model_fallback_chain_preserved` 의 죽은 첫 스텁 정의 제거

### 환경 커버리지
**flock 없는 PATH**(macOS 경로)를 정식 커버리지로 승격한다 — 2d 시점에 전체 스위트가 이 환경에서
통과하도록 정리됐으므로, 이제 두 환경 모두에서 도는 것을 규약으로 고정한다.

## 필수 규칙
- **신규 테스트마다 변이 검증** — 검증 대상 로직을 일시 제거했을 때 그 테스트가 죽는지
  `.orchestrate/mutation/` 사본에서 확인하고 결과를 보고에 남긴다 (`/tmp` 금지)
- 실제 `~/.local/state`·`~/.config`·실제 opencode 바이너리 접근 금지 (전부 스텁·임시 디렉터리)
- 실패하는 단정을 **완화해서** 그린을 만들지 말 것 — 환경 차이는 분기해서 각각 단언한다

## 완료 조건
- `python3 -m unittest discover -s tests -v` 전체 PASS (flock 있는/없는 PATH 양쪽)
- C28 변이 2건·C29 변이 1건이 각각 테스트를 죽이는 것을 확인한 출력 첨부
- 전체 스위트 2회 연속 실행 후 잔여 `opencode run` 프로세스 없음

## 보고 형식
추가한 테스트 목록 / RED·GREEN 출력 / 변이 검증 결과(수행 주체 명시) / 전체 스위트 수치
