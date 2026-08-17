# Task 2d: 배선·권한·서버 API 통합

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/opencode-serve-ctl.sh`, `core/scripts/run-delegation.sh`(호출부만),
  `scripts/opencode-serve-ctl.sh`(심링크 신설), `tests/test_serve_ctl.py`, `tests/test_run_delegation.py`
- **선행**: **Task 2c 커밋 후에 착수**한다. 같은 파일을 만지므로 병행 금지.
- **재사용**: 개선 후 재사용 — 신규 스크립트 금지. 서버 API 표면은 `opencode-serve-ctl.sh` 가 소유한다.

## 범위

> **⚠️ 이번 라운드(2d)의 범위는 C8·C6·C5·C10·C11·C19·C22 로 한정한다.**
> 원래 C5~C24 를 한 라운드로 잡았으나, 이 페이즈에서 "큰 라운드가 새 결함을 만든다"가 세 번
> 반복돼(2b 세 라운드·2c 세 라운드) **국소 수정 축(2d)** 과 **구조 변경 축(2e)** 으로 분리했다.
>
> | 라운드 | 항목 | 성격 |
> |---|---|---|
> | **2d (이번)** | **C8 심링크 · C6 스핀락 PID · C5 로그·락 권한 · C10 락 파일명 개행 · C11 잔여 정리 · C19 테스트 위생 · C22 주석 척도 정정** | 전부 국소·독립·저위험 |
> | 2e (다음 세션) | C7+C14 (curl 을 ctl 액션으로 통합 + `serve.env` 검증) · C18 (프리플라이트 부모 검증) · C17 · C20 · C21 · C23 · C24 | 구조 변경 |
>
> **2e 항목은 이번에 건드리지 말 것.** 특히 curl 을 ctl 로 옮기는 작업과 프리플라이트 판별자 교체는
> 다음 라운드다. 발견해도 보고만 하라.
>
> 따라서 이번 라운드의 대상 파일은 `core/scripts/run-delegation.sh`,
> `scripts/opencode-serve-ctl.sh`(심링크 신설), `tests/test_run_delegation.py` 다.
> `core/scripts/opencode-serve-ctl.sh` 본문과 `tests/test_serve_ctl.py` 는 **2e 소관**이라
> 이번에 수정하지 않는다(심링크 대상일 뿐).
>
> 아래 "실패 테스트" 목록에서 `tests/test_serve_ctl.py::<신규>` 와
> `test_serve_env_injection_is_rejected` 는 **2e 로 이월**한다.

항목 설명 원문은 `.tasks/task2c.md` 에 있으니 그쪽을 읽을 것 — 여기서는 범위와 순서만 정의한다.

| 항목 | 요지 | 심각도 |
|---|---|---|
| **C8** | `scripts/opencode-serve-ctl.sh` 심링크 신설 (`-> ../core/scripts/opencode-serve-ctl.sh`) — 없어서 키트 자신에서 attach 가 **도달 불가**(rc=127 실측). 사본 금지, 반드시 심링크 + git 등록 | 🟠 |
| **C7 + C14** | curl basic-auth 를 ctl 액션으로 통합. `run-delegation.sh` 안 **3중 복제**(`server_sessions`·`server_progress`·`abort_server_session`) + ctl `health_check` = 4번째 사본. **통합하면서 PW·PORT 형식 검증도 ctl 이 소유하게 만들 것** — 현재 run-delegation 은 같은 `serve.env` 를 재소싱하면서 검증을 물려받지 않아 curl config 주입이 가능하다(재현은 task2c.md C14 참조) | 🟠 |
| **C6** | mkdir 스핀락 PID 기록이 디렉터리에 쓰여 실패 → 스테일 락 감지 영구 무력화 (macOS 회귀). v2 대로 `$MLOCK/pid` | 🟠 |
| **C5** | 로그 `600`·상태 디렉터리 `700`. 공용 서버인데 현재 644/755 로 프롬프트 전문·세션 ID 노출 | 🟠 |
| **C10** | 락 파일명 개행·제어문자 제거 (센티널 위조 방지) | 🟡 |
| **C11** | `mkdir -p "$LOCK_DIR"` 실패의 `exit 4` 재사용, `stop_watchdog_client` 별칭 제거, 죽은 스텁·미사용 `COUNT_FILE` 정리 | 🟢 |
| **C17** | 세션 매칭이 `RUN_DIR=$(pwd -P)` 와 서버 `.directory` 의 **문자열 정확 일치**에 의존 — 심링크 경로가 개입하면 attach 가 영구 exit 2. 실서버 1회 실측으로 확인하거나 불가 사유·근거 주석을 남길 것 | 🟡 |

## 순서

1. **C8 심링크 먼저** — 이것이 없으면 이후 실측이 전부 standalone 폴백으로 흘러 의미가 없다.
   심링크를 만든 뒤 `bash scripts/run-delegation.sh` 가 실제로 attach 경로를 타는지 확인하라.
2. C7+C14 통합 (구조 변경이라 가장 큼)
3. C6·C5·C10·C11
4. C17 실측 또는 근거 주석

## 실패 테스트 (RED 먼저)

- `tests/test_serve_ctl.py::<신규>` — C7 로 추가한 ctl 액션(세션 목록·단건·abort)의 정상·실패 경로,
  그리고 **PW·PORT 형식 검증이 새 액션에도 적용되는지**
- `tests/test_run_delegation.py::test_spinlock_writes_pid_file` — flock 없는 PATH 에서 `$MLOCK/pid` 가
  생성되고 스테일 락 감지가 동작한다 (C6)
- `::test_log_file_permissions_are_600` — 로그 파일 권한 `600` (C5)
- `::test_lock_name_strips_newlines` — 개행 포함 디렉터리명에서 락 파일명에 개행이 없다 (C10)
- `::test_serve_env_injection_is_rejected` — `serve.env` 의 PW 에 개행이 있으면 curl config 에
  두 번째 `url =` 가 주입되지 않는다 (C14)

## 필수 규칙
- bash 3.2 호환 · CLI 인터페이스 불변 · exit 코드 의미 불변 (0/2/3/4/5/6/7/64/66, 신규 금지)
- ctl 의 기존 exit 계약(0/1/64)·stdout 계약(`up`/`down`/`started`/`stopped`)을 깨지 말 것 —
  **새 액션의 stdout·exit 계약을 정의해 보고에 남길 것** (Task 5 전파 때 필요하다)
- Task 2b·2c 가 확정한 워치독 판정 로직을 바꾸지 말 것 — **호출부만** ctl 경유로 옮긴다
- 금지사항 3종 주석·근거 주석 삭제 금지
- 테스트는 임시 디렉터리 주입. 실제 `~/.local/state/orchestrate`·실제 serve 금지

## 완료 조건
- `python3 -m unittest discover -s tests -v` 전건 PASS (신규 RED 선행 출력 첨부)
- `bash -n core/scripts/run-delegation.sh core/scripts/opencode-serve-ctl.sh` 통과
- `ls -la scripts/opencode-serve-ctl.sh` 가 **심링크**임을 보이는 출력 첨부
- **flock 없는 환경 실측** — PATH 에서 flock 을 제거하고 전체 스위트를 돌린 출력 첨부
- 변이 검증 3건 이상 (C6·C14 + 자체 고안 1건) 을 저장소 **밖** 사본에서 수행하고 결과 첨부
- 전체 스위트 2회 연속 실행 후 잔여 `opencode run` 프로세스 없음

## 공통 금지
대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지 ·
`scripts/run-delegation-v2.sh`(오케스트레이터 임시 파일) 읽기·수정·삭제 금지 ·
작업 전 skill 툴로 `karpathy-guidelines` 로드

## 보고 형식
수정·생성 파일 목록 / RED·GREEN 출력 전문 / 심링크 확인 출력 / flock 없는 환경 출력 /
변이 검증 결과 / 항목별 "어떻게 닫았는지" 한 줄 / **새 ctl 액션의 stdout·exit 계약** /
Task 3·5 로 넘길 전파 제약

---

## Task 2c 리뷰에서 이월된 항목 (2026-08-13)

### 🟠 C18. "관리되는 프로세스" 판별을 argv 추측이 아니라 **부모 검증**으로 바꿀 것

2c 는 프리플라이트의 attach 판정을 `$i=="--attach" && $(i+1) ~ /^https?:\/\//` 로 좁혔고,
"단어만 있는 경우"는 닫혔다. 그러나 security-reviewer 가 **잔여 우회를 재현**했다:
프롬프트 본문에 `--attach http(s)://...` 가 **인접 토큰으로** 등장하면 PPID≠1 비관리 프로세스가
관리 attach 로 위장돼 `PREFLIGHT_UNMANAGED` 를 완전히 빠져나간다.

재현 (`ps` 스텁, PPID=2):
```
401 2 401 /tmp/opencode run 프롬프트에 --attach http://127.0.0.1:9999 이런 문구가 있음
→ PREFLIGHT_UNMANAGED 비어 있음, EXIT=0
```

**근본 한계**: `ps` 는 argv 를 공백으로 이어 보여주므로 프롬프트 안의 토큰과 진짜 플래그를
**문자열만으로는 구분할 수 없다.** 이 저장소는 위임 스크립트의 `--attach http://...` 문법을
다루는 프로젝트라 프롬프트에 그 패턴이 등장할 개연성이 낮지 않다
(2c 커밋 메시지에도 그 구문이 그대로 들어갔다).

→ **"관리된다"의 정의를 바꿔라**: attach 플래그 유무를 추측하지 말고,
**부모 프로세스가 실제로 `run-delegation.sh` 인지 확인**한다.
- PPID 를 얻어 그 부모의 argv/comm 을 조회해 `run-delegation` 이 포함되는지 본다.
- 부모가 `run-delegation.sh` 면 관리 중 → 제외. 아니면(PPID=1 포함) 경고.
- 이렇게 하면 `--attach` 토큰 검사 자체가 불필요해지고 E3 계열 오분류가 원천 제거된다.
- **회귀 테스트**: ① 프롬프트 본문에 `--attach http://...` 가 있고 부모가 `run-delegation.sh` 가
  아닌 프로세스 → exit 3 ② 부모가 `run-delegation.sh` 인 정상 attach 클라이언트 → 통과
  ③ PPID=1 고아 → exit 3.
- `ps` 스텁이 부모 조회에도 답해야 하므로 테스트 픽스처 확장이 필요하다.

### 🟡 C19. 테스트 위생
`test_preflight_blocks_bare_orphan_in_own_process_group` 의 `ps` 스텁에 `[ "$1" = "-o" ]` 분기가
남아 있는데, 2c 가 `ps -o pgid= -p $$` 호출을 제거해 **죽은 코드**다(`grep -n "ps -o"` 결과 없음).
정리할 것.

### 🟡 C20. `head -n 60` 상한의 잔존 트레이드오프 (정보성 — 이번에 고치지 않아도 됨)
프리앰블이 60줄을 넘는 환경(LSP + 포매터 + 대형 설정 다수)에서는 여전히 exit 7 대신
침묵 오배정이 재발할 수 있다. 실측 근거(배너 19번째 줄)와 회귀 테스트가 있어 의도된 트레이드오프로
수용했으나, 더 나은 해법은 **첫 세션 시작 신호(`loop session.id`) 출현 전까지**로 끊는 것이다.
2d 에서 여력이 되면 검토하고, 아니면 Task 3·4 로 넘겨라.

### 🟡 C21. `--attach=URL` 등호 형식이 "비관리"로 오분류된다
현재 검사는 `$i=="--attach" && $(i+1) ~ /^https?:\/\//` 라 **공백 형식만** 인정한다.
건강한 관리 클라이언트가 `--attach=http://...` 등호 형식으로 떠 있으면 다른 프로젝트의
정상 위임이 exit 3 으로 죽는다 — C3 이 닫은 "정상 병렬 세션 오탐"과 같은 방향의 회귀다.
재현(awk 단독): `/tmp/opencode run --attach=http://127.0.0.1:4096 --dir /x` (PPID=2) → `FLAGGED-AS-UNMANAGED`.
현재 이 저장소는 항상 공백 형식을 쓰므로 실사용 노출은 낮다.
→ **C18(부모 검증)로 가면 이 항목은 자연 소멸한다** — attach 토큰 파싱 자체가 없어지기 때문이다.
   C18 을 채택하지 않는 경우에만 `$i ~ /^--attach=https?:\/\//` 를 OR 로 추가하라.

### 🟡 C22. `head -n 60` 근거 주석의 척도가 틀렸다
주석은 "배너 19행 → 60줄까지 41줄 여유"라고 쓰지만, **실측하면 에이전트가 직접 쓴 텍스트가
43~45행부터 시작**한다(이 저장소 로그 5건 전부: `Todos` 블록이 43·43·44·45·45행).
즉 30줄 시절엔 스캔 창에 산출물이 0줄이었는데 60줄로 넓히면서 **15~17줄이 창 안에 들어왔다** —
C1 이 닫은 오탐 경로가 좁게 다시 열린 것이다. 실제 안전 상한은 **40 근처**다.
→ 최소한 주석을 실제 여유(산출물 43행 기준)로 정정하라. 상한을 40으로 낮추거나,
   C20 의 제안대로 **첫 `loop session.id` 출현 전까지**로 끊는 편이 더 낫다.

### 🟢 C23. 커버리지 공백 — E1×E3 교차 정상 케이스
"**bare** argv + **진짜** `--attach URL` + PPID≠1 → 무시" 를 고정하는 테스트가 없다.
기존 `test_preflight_ignores_managed_attach_process` 는 경로 형식이고, 신규 bare 테스트는 PPID=1 이라
교차점이 비어 있다. 로직이 공유라 실위험은 낮지만 테스트를 추가하라.

### 🟢 C24. 동작 변화 기록 (지시서에 없던 부수 효과)
`$3 != group` 제거로, **같은 pgid 에서 도는 다른 standalone `opencode run`**(예: 중첩 위임)이
이제 exit 3 으로 차단된다. 세션 DB 경합 방지 측면에서 옳은 방향이나 의도하지 않은 부수 효과이므로
문서화하거나 명시적으로 수용 결정을 남길 것.

---

## Task 2d 리뷰에서 이월된 항목 (2026-08-13) → **2e 소관**

### 🟠 C25. 로그 파일 권한에 TOCTOU 창이 있다 (C5 부분 충족)
`: > "$LOG_FILE"` 로 만든 뒤 별도 `chmod 600` 을 호출한다. 권한 검사는 `open()` 시점 1회뿐이라
**그 창에 fd 를 확보한 프로세스는 chmod 이후에도 계속 읽는다** (security-reviewer PoC 재현:
poller 가 생성 직후 fd 를 잡고, 파일이 600 이 된 뒤 append 된 내용을 그대로 읽음).
`.orchestrate/` 는 755 이고 로그 파일명(`task<N>.log`)이 예측 가능해 공용 서버에서 노려질 수 있다.
→ **`(umask 0177; : > "$LOG_FILE")` 또는 `install -m 600 /dev/null "$LOG_FILE"`** 로 바꿔
생성과 권한 설정을 한 번의 `open()` 으로 원자화하라. `LOCK_DIR`(mkdir→chmod 700)도 같은 패턴이나
그 창에 민감 내용이 없고 기본 755 에 world-write 가 없어 실익이 없다 — LOG_FILE 만 고치면 된다.

### 🟠 C26. `.orchestrate/*.prompt` 가 644 로 남아 있다 — C5 의 원래 목적 미달성
C5 가 지목한 민감 데이터는 **프롬프트 전문**인데, 프롬프트 파일을 만드는 주체는
`run-delegation.sh` 가 아니라 **전역 `/orchestrate` 스킬**(`~/.claude/skills/orchestrate/SKILL.md`
의 heredoc)이다. 따라서 2d 범위 밖이었고 여전히 644 다.
→ **Task 4(문서·스킬)** 가 스킬의 프롬프트 생성 절차에 `umask 0177` 또는 생성 후 `chmod 600` 을
넣도록 하라. **키트 어댑터 사본과 `~/.claude/skills/orchestrate/SKILL.md` 양쪽** 갱신이 필요하다.

### 🟡 C27. 커밋 메시지가 검증 출처를 구분하지 않는다 (프로세스)
2d 커밋 메시지가 "변이 5건 전멸"을 확정 주장했는데, 위임 로그(`task2d.log`·`task2d-fix.log`)에는
그 근거가 없다 — 두 라운드 모두 `/tmp` 접근 거부로 변이 단계에서 끊겼기 때문이다.
실제로는 **task-orchestrator 검수자가 직접 수행**한 결과이고 그 보고에 출력이 남아 있다.
기능적 결함은 아니지만 감사 시 혼동을 부른다.
→ **규칙**: 커밋 메시지·보고에 검증 결과를 쓸 때 **누가 수행했는지**(위임 / 검수자)를 명시할 것.

### 🟠 C28. 락 테스트가 **배타적 획득**을 검증하지 않는다 (silent-failure-hunter 🔴) → **Task 3**
락 단정이 "락 산출물(파일/디렉터리)이 존재하는가"만 본다. 저장소 전체에 동시 프로세스로
상호배제를 검증하는 테스트가 없다(`grep Popen/concurrent` 무결과). 생존 변이 2건:
- flock 환경: `if ! flock -n 9; then` → `if false; then` (파일은 `exec 9>` 로 여전히 생성) → 그린
- 비flock 환경: 배타적 `mkdir "$MLOCK"` 을 항상 성공하도록 → 그린

**전파(Task 5) 후 4개 프로젝트가 동시에 위임을 돌릴 때 상호배제가 깨지면 업스트림의
"토큰 0개 + exit 0 침묵사"가 재발한다.** 이 페이즈가 막으려던 바로 그 결함이다.
→ **동시 프로세스 2개로 상호배제를 확인하는 테스트**를 추가하라. 완료 조건: 위 변이 2건이 죽어야 한다.

### 🟠 C29. 락 이름 단정이 비flock 환경에서 프로젝트/전역 구분을 잃는다 (bash-reviewer) → **Task 3**
`assert_lock_snapshot(project=True)` 의 유일한 이름 단정이 `assertNotEqual(lock.name, "opencode.lock")`
인데, 비flock 산출물은 `opencode.lock.d` 라 **전역 락으로 회귀해도 통과**한다.
재현: `LOCK_FILE=".../opencode-${PROJECT_NAME}-${PROJECT_HASH}.lock"` → `".../opencode.lock"` 변이 후
flock 제거 PATH 에서 `test_attach_mode_uses_project_lock`·`test_worktrees_share_project_lock` 둘 다 생존
(flock 있는 환경에서는 3건 정상 FAIL).

**이력**: 원래 `assertEqual(len(locks), 1)` 이었는데 비flock 에서 4건 FAIL 하자
`len(locks)+len(lock_dirs)==1` 로 **완화**해 그린을 만들었다 — "환경 분기를 핑계로 단정 약화"가
형태만 바꿔 재발한 것이다(이 페이즈에서 같은 계열 7번째).
→ 접미사를 정규화한 뒤 단정하라:
`stem = lock.name[:-2] if lock.name.endswith(".d") else lock.name` →
`project=True` 는 `stem.startswith("opencode-")`, `project=False` 는 `stem == "opencode.lock"`.

### 🟡 C30. 권한 테스트가 umask 에 의존한다 (bash-reviewer) → **Task 3**
`chmod` 두 줄을 `true` 로 변이하면 `umask 022` 에서는 FAIL 하지만 **`umask 077` 에서는 생존**한다.
테스트가 umask 를 명시 주입해야 한다.

### 🟡 C31. C11 미완 — `COUNT_FILE` 정리 누락 (bash-reviewer) → **Task 3**
지시서가 명시한 미사용 `COUNT_FILE` 정리가 `tests/test_run_delegation.py:372` 에 그대로 남아 있다.

### 🟡 C32. exit 4 의미 확장이 문서와 어긋난다 (bash-reviewer) → **Task 4**
헤더 8행과 `adapters/claude/global/skills/orchestrate/SKILL.md:426` 은 `4 = LOCK_TIMEOUT`(사용자 보고)이다.
C11 이 승인한 건 `mkdir "$LOCK_DIR"` 실패까지인데, **로그 chmod 실패**는 락과 무관한데도 같은 코드로
나가면서 `LOCK_TIMEOUT` 센티널도 없다. 신규 exit 코드 금지가 유지되는 한 재사용은 불가피하니
**헤더 주석 정정 또는 구분 센티널**을 남길 것.

### 🟢 C33. C22 산수 1 어긋남
산출물이 43행부터면 60줄 창에 들어오는 건 43~60 = **18줄**인데 주석은 17줄로 적혀 있다.
