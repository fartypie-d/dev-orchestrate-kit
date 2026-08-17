---
phase: 6
date: 2026-08-14
kind: task
domain: install, docs
status: done
commits: db71ef2,9724994,4984ff3,082b286
cost: $36.46 (세션 합산 — 0814 공개 릴리스 작업 포함)
compactions: 0
interventions: 0
summary: usage-dashboard 를 --containers=dashboard 로 설치·기동 — 컨테이너 파이프라인 일반화 (서브모듈 경로·포트·문구)
---

# 작업 지시서 — usage-dashboard 컨테이너 옵션 (2026-08-14)

## 인터뷰 결과
- 스코프: `install.sh`가 usage-dashboard 를 설치 대상으로 받는다. 표면은 **기존 `--containers=` 확장**
  (`--containers=browser,dashboard`) — `--with` 신설 안 함. 마법사 컨테이너 스텝에도 항목 추가.
  기동 범위는 Phase 4 browser 패턴 그대로: 서브모듈 init → docker·compose·포트(9280) 확인 →
  동의 → `compose up -d`, 실패는 비치명 + 수동 안내.
- 우선순위: Task 1(동결 테스트) → 2(구현) → 3(문서). 직렬.
- 제약: `tests/` 는 오케스트레이터가 작성·동결(PITFALLS 14), 위임의 수정 금지.
  실기동 검증은 스텁 바이너리로 (실제 docker·홈 오염 금지). `scripts/`는 심링크 — `core/scripts/` 원본.
- 크기 등급: **standard** (kit-scripts ⚠️ 도메인 → 모델 heavy 기본, task-orchestrator 경유)

## Task 목록

| # | 제목 | 에이전트 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 동결 회귀 테스트 (RED) | 오케스트레이터 직접 | done | db71ef2 |
| 2 | install.sh dashboard 컨테이너 + 파이프라인 일반화 | kit-scripts (heavy) | done | 9724994, 4984ff3 |
| 3 | README 영·한 문서 반영 | kit-docs | done | 082b286 |

## 전제 실측

| 전제 | 근거 | 유지/뒤집힘 |
|---|---|---|
| 대시보드 compose 는 `127.0.0.1:9280`, build 섹션 있음(up -d 가 빌드 겸함) | fartypie-d/usage-dashboard `docker-compose.yml:3,10` | 유지 |
| `--containers=` 파싱·selftest(`INSTALL_SELFTEST_CONTAINERS`)·fake 4종 존재 | `install.sh:72,1287-1319` | 유지 |
| `build_container_up_argv` 가 browser 만 알고, `up -d` 지식은 이 함수 전속 (테스트 고정) | `install.sh:1174-1180`, `tests/test_install_container_step.py:147` | 유지 |
| 실기동 루프는 browser 하드코딩: 서브모듈 경로·`$CDP_PORT`·문구·동의 프롬프트 | `install.sh:1549-1596` | 유지 — 일반화 대상 |
| 마법사 조합부가 browser 만 보존 (`*,browser,*) CONTAINERS=browser`) | `install.sh:1021-1030` | 유지 — 일반화 대상 |
| `choose_many` 번호 폴백은 쉼표/공백 구분 다중 입력 허용 ("1,2") | `install.sh` choose_many 본문 | 유지 |
| `CDP_PORT="${INSTALL_CDP_PORT:-9222}"` 단일 소스 (Phase 4 task7a) | `install.sh:14` | 유지 — DASH_PORT 동형 신설 |

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| 포트 검사 일반화 | dashboard 가 9222 를 검사(오탐)하거나 포트 검사 자체 누락 | `test_install_dashboard_container.py::test_dashboard_real_startup_uses_own_port_and_compose` (Task 1) |
| 마법사 다중 선택 보존 | browser+dashboard 동시 선택 시 한쪽 유실 (현행 조합부가 browser 만 보존) | `::test_wizard_both_containers_preserved` (Task 1) |
| 서브모듈 경로 분기 | dashboard 가 `containers/browser` 를 init 하거나 존재 검사 경로 불일치 | `::test_dashboard_real_startup_uses_own_port_and_compose` (argv 단언, Task 1) |

## 전파 제약 (누적)

- `up -d` 문자열은 `build_container_up_argv` 함수 밖에 나타나면 안 된다 (기존 테스트 고정).
- compose **서비스명**은 install.sh 가 알면 안 된다 (compose -f 파일 경로까지만).
- 기존 browser 테스트 12건(`test_install_container_step.py`)은 무수정 통과해야 한다.
- Task 2 확정: 마법사 항목 순서 claude=`browser(1)·mcp(2)·dashboard(3)` / 비-claude=`browser(1)·dashboard(2)`.
  조합부는 고정 순서 `browser,dashboard` 로 재구성. `DASH_PORT="${INSTALL_DASH_PORT:-9280}"` 단일 소스.
  이후 컨테이너 항목 추가 시 mcp/wizard 테스트의 번호 하드코딩(18+11건)을 재점검할 것.
- 변이 검증 완료 (2026-08-14): 포트 오염·조합부 제거·up-argv 케이스 제거 3종 모두 동결 테스트 FAIL 확인.
- Task 2 리뷰 1라운드 (2026-08-14): bash=PASS(🟠1) / silent-failure=REJECT(🔴1) / security=REJECT(🟠1) —
  ① 🔴 mcp 가드가 `-z $CONTAINERS` 검사라 mcp+dashboard 조합에서 우회 ② 🟠 수동 재시도 요약이
  실패·성공 컨테이너를 구분 못 함. 동결 테스트 2건 추가(RED) 후 task2c 재위임(1/2회차).
  2R 재검수 (2026-08-14): security=PASS·silent-failure=PASS — 🔴·🟠 재현으로 해소 확인, 273건 2회 PASS.
  이월 🟡: case 이원화(경로·포트 매핑 vs up-argv 화이트리스트) 단일 헬퍼 통합, 동의 프롬프트에
  대시보드 홈 마운트(RO: ~/.claude/projects, ~/.local/share/opencode) 고지, compose 포트가
  INSTALL_*_PORT override 를 실바인딩에 반영하지 않는 기존 설계(정보성).

## 자동 결정 로그

- [2026-08-14] 마법사 항목 순서 충돌(Task 2 에스컬레이션: 동결 테스트 dashboard=2번 vs 기존
  mcp 테스트 8건 mcp=2번) → **옵션 A 채택**: browser(1)·mcp(2)·dashboard(3), 동결 테스트의
  선택 번호만 오케스트레이터가 갱신 (사유: 기존 테스트 무수정 유지 + mcp는 browser 의존이라
  인접 배치가 자연스러움. 메뉴 순서는 가역적 세부사항이라 사용자 질의 없이 결정, 지시서의
  원 순서 지정이 오류였음)
