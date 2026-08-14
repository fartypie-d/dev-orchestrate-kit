# Task 2f: 프리플라이트 판별자를 부모 검증으로 교체 (C18 · C21 · C23 · C24 · C20)

- **에이전트**: kit-scripts
- **모델**: heavy (⚠️ 프리플라이트는 정상 병렬 세션을 죽일 수 있는 축 — 이 페이즈에서 이미 1회 발생)
- **대상 파일**: `core/scripts/run-delegation.sh`(프리플라이트 절 117~145행만), `tests/test_run_delegation.py`
- **선행**: **Task 2e 커밋 후** 착수 (같은 파일 — 병행 금지)
- **재사용**: 개선 후 재사용 — 기존 `ps -eo pid,ppid,pgid,args` 스캔(130행)을 **판별 기준만** 교체한다.
  스캔 자체·자기제외(`$1 != self`)·경고 출력 형식은 유지. 신규 함수 최소화.

## 범위 — 이 라운드는 "프리플라이트 축"만

> C7+C14·C25·C17 은 Task 2e 에서 이미 처리됐다. 서버 API·로그 권한 코드는 **읽기만** 한다.

| 항목 | 요지 | 심각도 |
|---|---|---|
| **C18** | "관리되는 프로세스" 판별이 argv 추측이다 — `ps` 는 argv 를 공백으로 이어 보여줘서 **프롬프트 본문에 들어간 토큰**과 진짜 플래그를 문자열만으로 구분할 수 없다(2c 리뷰 재현: PPID=2 비관리 프로세스가 관리로 위장돼 exit 3 을 완전히 회피). → **부모 프로세스가 실제로 `run-delegation.sh` 인지 확인**하는 방식으로 바꾼다. PPID 로 부모 argv/comm 을 조회해 `run-delegation` 포함 여부를 본다. 부모가 맞으면 관리 중(제외), 아니면(PPID=1 포함) 경고 | 🟠 |
| **C21** | 등호 형식 attach 플래그가 "비관리"로 오분류돼 **정상 병렬 위임을 exit 3 으로 죽인다**. C18 채택 시 attach 토큰 파싱 자체가 사라져 **자연 소멸** — 소멸했음을 테스트로 고정할 것 | 🟡 |
| **C23** | 커버리지 공백: "경로 없는 bare argv + 진짜 attach 플래그 + PPID≠1 → 무시" 교차 케이스 테스트 부재 | 🟢 |
| **C24** | 2c 의 `$3 != group` 제거로 **같은 pgid 의 다른 standalone 위임(중첩)** 이 이제 exit 3 으로 차단된다. 의도치 않은 부수 효과이므로 **주석 + 지시서에 수용 결정 기록** | 🟢 |
| **C20** | exit 7 탐지 스코프 `head -n 60` 의 잔존 트레이드오프. 2d 실측으로 산출물이 43행부터 시작함이 확인됐다(안전 여유 ≈ 40). **판단만 하라**: 상한을 40 으로 낮추거나, 현행 유지 + 근거 주석. **첫 세션 신호까지 컷하는 재설계는 이번 범위 밖**(새 결함 위험) | 🟡 |

## 실패 테스트 (RED 먼저)

`ps` 스텁이 **부모 조회에도 답해야** 하므로 픽스처 확장이 필요하다.

- `::test_preflight_flags_process_with_attachlike_text_in_prompt` — 프롬프트 본문에 attach 플래그
  **처럼 보이는 문자열**이 들어간 비관리 프로세스(부모가 위임 래퍼가 아님) → **exit 3** (C18 핵심)
- `::test_preflight_ignores_child_of_delegation_wrapper` — 부모가 `run-delegation.sh` 인 정상
  attach 클라이언트 → 통과 (오탐 0)
- `::test_preflight_flags_orphan_regardless_of_flags` — PPID=1 고아는 플래그와 무관하게 exit 3
- `::test_preflight_ignores_bare_argv_managed_client` — bare argv + 진짜 attach + PPID≠1 → 무시 (C23)
- `::test_preflight_accepts_equals_form_attach` — 등호 형식이어도 부모가 래퍼면 통과 (C21 소멸 고정)

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED |
|---|---|---|
| 부모 조회 실패(부모가 이미 종료) 시 처리 | 조회 실패를 "관리 중"으로 취급하면 우회 경로가 열린다 | 부모 조회가 빈 결과를 주는 스텁 케이스 → exit 3 기대 |
| argv 판정 잔재 | attach 토큰 검사를 남겨두면 C21 이 소멸하지 않음 | `test_preflight_accepts_equals_form_attach` |
| 스텁이 실제 `ps` 호출 형태와 다름 | 테스트만 통과하고 실환경에서 무력 | 스텁이 **실제 호출 형태 그대로** 답하는지 검수자가 대조 |

## 필수 규칙

- bash 3.2 호환 · CLI 인터페이스 불변 · exit 코드 의미 불변(신규 금지)
- **자기제외는 `$1 != self` 만** — PGID 자기제외를 넣지 말 것. 비대화형 bash 는 job control 이 꺼져
  있어 백그라운드 자식이 부모 pgid 를 물려받고, 그러면 드라이버 아래 고아가 통째로 안 보인다(실측)
- `pgrep -f` 사용 금지 (자기 명령줄 매칭 — 이 저장소 함정)
- 경고 메시지 형식·exit 3 의미 유지 (다른 프로젝트 4곳이 이 계약에 의존한다)
- 테스트는 임시 디렉터리 + 스텁 주입. 실제 프로세스 스캔 의존 금지
- 변이 검증은 `.orchestrate/mutation/` 에서 (`/tmp` 금지 — external_directory 거부)

## 완료 조건

- `python3 -m unittest discover -s tests -v` 전건 PASS (신규 RED 선행 출력 첨부)
- `bash -n core/scripts/run-delegation.sh` 통과
- flock 제거 PATH 에서도 전체 스위트 통과
- 변이 검증 2건 이상 — 부모 검증 분기를 무력화하면 위 RED 가 죽는지 (**수행 주체 명시**)
- 전체 스위트 2회 연속 실행 후 잔여 `opencode run` 프로세스 없음

## ⚠️ 위임 프롬프트 작성자(오케스트레이터) 주의

이 task 의 프롬프트에는 **attach 플래그와 URL 을 인접해서 쓰지 말 것**, **에이전트 미발견 경고
문구를 그대로 인용하지 말 것**. 프롬프트는 opencode 클라이언트의 argv 로 들어가고 로그에도 남아,
프리플라이트와 exit 7 탐지가 **자기 자신의 프롬프트에 걸려** 정상 위임을 죽인 실측이 있다
(이 페이즈 함정 2·3). 플레이스홀더(`--attach <URL>`)로 우회 표기한다.

## 공통 금지

대상 파일 외 수정 금지 · `git commit`/`git push` 금지 · docker 조작 금지
