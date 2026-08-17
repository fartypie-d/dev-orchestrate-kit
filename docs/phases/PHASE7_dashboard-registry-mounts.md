---
phase: 7
date: 2026-08-14
kind: task
domain: install, containers, docs
status: done
commits: c3a8a07, 691eb88, 200292d, 9fe84b7, d0c6ca5
cost: -
compactions: 0
interventions: 0
summary: 대시보드 컨테이너의 프로젝트 DOCs 마운트를 오케스트레이트 레지스트리에서 자동 생성
---

# 작업 지시서 — 대시보드 진행내역 문서 마운트 자동화 (2026-08-14)

## 배경 (실측 증거)

usage-dashboard UI에서 dev-orchestrate-kit·insane-cloak 진행내역이 "문서 없음"으로 표시됐다.

대시보드는 레지스트리(`~/.local/state/orchestrate/registry/*.json`)의 `root + docs_dir`를
**호스트 절대경로 그대로** 문서 루트로 쓴다 (`app/main.py:421-425`). 컨테이너 안에 같은
절대경로가 없으면 `docs_root_missing` 경고와 함께 빈 화면이 된다. 실행 중이던 컨테이너에서:

```
/home/jh/dev-orchestrate-kit/DOCs: MISSING
/home/jh/insane-cloak/DOCs:        MISSING
/home/jh/k-stock/DOCs:             EXISTS
```

마운트 목록의 출처는 `~/usage-dashboard/docker-compose.override.yml` — **gitignore된 수작업
파일**이라 프로젝트를 새로 등록해도 아무도 갱신하지 않는다. 호스트는 그 파일에 두 줄을 더해
핫픽스했다(검증 완료: 6·4개 phase 렌더). 이 페이즈는 **킷 쪽 구조적 결함**을 고친다.

킷의 `install.sh --containers=dashboard` 는
`components/usage-dashboard/docker-compose.yml`(서브모듈) 로만 컨테이너를 띄우는데, 그 compose
에는 레지스트리 마운트도 `USAGE_REGISTRY_DIR`·`USAGE_DOCS_ROOT` 도 프로젝트 DOCs 마운트도
**전혀 없다**. 즉 킷으로 설치한 사용자는 *모든* 프로젝트가 "문서 없음"으로 보인다.

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| 서브모듈 핀이 멀티프로젝트 진행내역을 지원하지 않는다 | `components/usage-dashboard/app/main.py:375,382` — `USAGE_DOCS_ROOT`·`USAGE_REGISTRY_DIR` 존재. `app/sources/orchestrate_registry.py`·`app/metrics/progress_docs.py` 존재 | **뒤집힘** — 앱 코드는 정상, compose 배선만 없음. 서브모듈 핀 인상 불필요 |
| 킷에 레지스트리를 읽는 코드가 없다 | `core/scripts/phase-tools.py:34-39` `state_dir()` (`ORCH_STATE_DIR` 주입 지원) | **뒤집힘** — 재사용 대상이 이미 있다 |
| `phase-tools.py` 를 import 해서 재사용할 수 있다 | 파일명에 하이픈 — 파이썬 모듈로 import 불가 | **유지(제약)** — 별도 파일을 만들면 `state_dir()` 중복이 강제된다 → **서브커맨드로 추가**한다 |
| 기존 테스트가 docker argv 를 앵커 정규식으로 고정한다 | `tests/test_install_dashboard_container.py:191` `^<compose><-f><...><up><-d>$` | **유지** — `-f` 를 하나 더 붙이면 순수 회귀. Task 2에서 함께 갱신 (PITFALLS 23 계열) |

## 인터뷰 결과

- **스코프**: 킷이 대시보드 컨테이너를 띄울 때 레지스트리에 등록된 프로젝트의 DOCs를
  자동으로 마운트한다. 서브모듈 코드·핀은 건드리지 않는다. `~/usage-dashboard`(사설 저장소)도
  건드리지 않는다 (핫픽스는 이 페이즈 밖에서 이미 적용).
- **우선순위**: 생성기 → install.sh 배선 → 문서.
- **제약**:
  - 방식 = **레지스트리 기반 생성기** (`$HOME` 통째 ro 마운트는 `~/.ssh`·`secrets.env` 노출로 기각)
  - 갱신 = install 시 + **전용 커맨드로 수시 재생성**
  - 파일 위치 = `~/.local/state/orchestrate/` (서브모듈·킷 작업트리를 더럽히지 않음)
  - 실제 `~/.claude`·`~/.config`·`~/.local/state` 를 테스트에서 건드리지 말 것 (`ORCH_STATE_DIR` 주입)
- **크기 등급**: **standard** (3파일 + 테스트, 내부 모듈 추가, 설계 분기 해소됨.
  `install.sh` 는 ⚠️ 도메인이라 어차피 최소 standard)

### 설계 노트 — "전용 스크립트"의 실체

별도 `.sh` 파일을 새로 만들지 않고 **`python3 scripts/phase-tools.py dashboard-mounts`**
서브커맨드로 제공한다. 근거: 레지스트리 경로 해석(`state_dir()`)·`ORCH_STATE_DIR` 주입·
flock 규약이 이미 그 파일에 있고, 하이픈 파일명 때문에 import 재사용이 불가능해
새 파일을 만들면 `state_dir()` 중복이 확정된다. 사용자는 언제든 이 한 줄로 재생성한다.

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 (담당) |
|---|---|---|
| 존재하지 않는 `root/docs_dir` 를 마운트 | docker bind가 **root 소유 빈 디렉터리를 호스트에 생성**한다 (되돌리려면 sudo) | `test_dashboard_mounts.py::test_skips_missing_docs_dir` (Task 1) |
| 레지스트리가 비었을 때 빈 override 생성 | `volumes: []` 같은 빈 키는 compose 파싱 실패 → 컨테이너 기동 자체가 죽는다 | `test_dashboard_mounts.py::test_empty_registry_writes_no_file` (Task 1) |
| override 없는데 `-f` 를 붙임 | `docker compose -f 없는파일` 은 즉시 실패 → 대시보드가 아예 안 뜬다 (기존 사용자 회귀) | `test_install_dashboard_container.py::test_startup_omits_override_when_absent` (Task 2) |

## task 목록

| # | 제목 | 에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 1 | `phase-tools.py` 에 `dashboard-mounts` 서브커맨드 | `kit-scripts` | heavy | **완료** (리뷰 3인 PASS) | `66f31e4` → `c3a8a07` |
| 2 | `install.sh` dashboard 기동 경로에 생성·주입 배선 | `kit-scripts` | heavy | **완료** (재위임 1회 → 리뷰 2인 PASS) | `cc293f2`(RED) → `691eb88` → `200292d`(RED) → `9fe84b7` |
| 3 | README 2종에 재생성 절차 문서화 | `kit-docs` | default | **완료** (구조 수정 1회 → code-reviewer PASS) | `d0c6ca5` |

상세: `DOCs/PHASE7_dashboard-registry-mounts.tasks/task<N>.md`

## 테스트 동결 (오케스트레이터 작성 — 위임의 `tests/` 수정 금지)

PITFALLS 14에 따라 아래 테스트는 오케스트레이터가 작성·동결한다.

- `tests/test_dashboard_mounts.py` (신규)
- `tests/test_install_dashboard_container.py` (기존 앵커 정규식 갱신 + 신규 1건)

## 전파 제약 누적

- (Task 1 착수 중 실측) `kit-scripts` 담당 범위가 `core/scripts/*.sh` 로 적혀 있어 위임이
  `phase-tools.py` 구현을 **거부하고 빈손 반환**했다(1회). Phase 2 task4 는 같은 파일을
  kit-scripts 로 수정한 이력이 있어 **문서만 좁았던 불일치**다. 사용자 승인 후
  `.claude/orchestrate.md`·`.opencode/agent/kit-scripts.md` 의 범위를 `core/scripts/*`
  (sh·py 모두)로 교정하고, `core/scripts/*.py` 대상일 때 리뷰어를 `python-reviewer` 로
  바꾸도록 매핑을 보강했다. → **이후 task 도 이 범위를 전제로 위임한다.**
- (Task 1 리뷰 실측) `state_dir()` 는 `<state>/registry/` 를 반환하고 override 는 그 **부모**
  `<state>/dashboard-compose.override.yml` 에 생성된다. Task 2 의 `install.sh` 배선은
  `--print-path` 로 경로를 얻고, 생성 후 **파일 존재를 확인한 뒤에만** `-f` 를 붙여야 한다
  (마운트할 것이 없으면 파일 자체가 생성되지 않는다).
- (Task 1 리뷰 반려 — 3종 병렬 리뷰) 🔴 1건 + 🟠 4건. 동결 테스트 5개를 만족해도 계약이
  커버하지 않는 경계에서 **조용히 잘못된 compose 를 만들어 냈다**: ① 존재하지 않는 DOCs 로
  제외된 프로젝트를 무경고로 버림(이 페이즈가 고치려던 침묵과 동형) ② `docs_dir` 가
  절대경로·`..` 면 `root` 봉쇄가 무력화되어 임의 호스트 경로가 마운트됨(=$HOME 마운트를
  기각한 설계 의도 붕괴) ③ 문자열 조립 YAML 에 개행이 든 경로가 **독립 volumes 항목을 주입**
  (실측 재현, `- /:/:rw` 주입 가능) ④ 비원자적 쓰기(같은 파일 `Registry.save()` 의
  tmp+rename 패턴 미재사용). 지적을 RED 3건(`deacda3`)으로 고정한 뒤 heavy 재위임.
  "부분 실패 시 비0 exit" 제안은 동결 계약(exit 0 유지)과 충돌해 **불채택**.
  → **교훈: 동결 테스트는 정상 경로 계약만 고정했다. 경계값(경로 이탈·인젝션)은
  리뷰 예상 지점 표에 넣지 않았던 부분이다 — Task 2 지시서에도 같은 계열을 미리 넣는다.**
- (Task 1 재위임 결과 — 최종) 마운트는 **비대칭**이다: `f"{docs_path}:{mount_path}:ro"` —
  source 는 `resolve()` 한 실경로(도커 데몬이 bind 시점에 source 를 재해석하므로 심링크 스왑
  TOCTOU 차단), target 은 레지스트리에 등록된 **비정규화** 경로(usage-dashboard 가
  `Path(root)/docs_dir` 를 `resolve()` 없이 열기 때문). 추가로 `root` 가 절대경로가 아니면
  거부하고, 중복 마운트 경로는 경고 후 스킵한다. → **Task 3 문서화에 이 비대칭성을 반영할 것.**
- (Task 2 결과 — 재위임 후 확정) `install.sh` 는 `--print-path` 실패 시 셸에서 경로를 직접
  계산해 폴백한다. 폴백 규칙은 `state_dir()` 과 **정확히 동치**여야 한다:
  `ORCH_STATE_DIR` 이 비어 있지 않으면 그것, 아니면 `$HOME/.local/state/orchestrate`.
  **`XDG_STATE_HOME` 은 py·sh 어느 쪽도 참조하지 않는다** (1라운드에 오케스트레이터 지시서가
  잘못 적어 넣었다가 silent-failure-hunter 가 잡아냈다 — `XDG_STATE_HOME` 만 설정된 흔한 환경에서
  `[ -f ]` 가 조용히 거짓이 되어 override 미적용 + exit 0 이었다).
  즉 **경로 규칙이 py·sh 두 곳에 이중화**되어 있다 — `state_dir()` 를 바꾸면 `install.sh`
  폴백도 함께 고쳐야 한다. Task 3 문서에 이 결합을 명시할 것.
- (Task 2 리뷰 잔여 🟠 — 미채택, 의도적 트레이드오프) 생성기 호출이 실패하면 install.sh 는
  경고만 내고 **기존 override 파일을 그대로 재사용**한다. 리뷰어는 `rm -f` 로 무효화하자고
  제안했으나 불채택했다: 일시적 실패에 마운트를 통째로 날리면 정상 동작하던 대시보드가
  "문서 없음"으로 퇴행한다 — 이 페이즈가 없애려던 증상 그 자체다. stale 마운트는 경고가
  나가고 사용자가 재생성 한 줄로 복구할 수 있는 반면, 삭제는 무음 퇴행이다.
- (Task 2 지시서 교훈) 지시서에 코드 규칙을 **산문으로 옮겨 적으면** 위임은 코드가 아니라
  산문을 따른다. 규칙을 옮길 때는 원본을 그 자리에서 실측·인용할 것.
- (Task 2 변이 검증 실측) 위임이 보고한 변이 (b)(경고 제거)는 `if` 본문을 비워 **구문 오류**로
  실패한 것이어서 무효였다. 오케스트레이터가 `note …` → `:` (구문상 유효한 no-op)로 다시
  변이시켜 재검증 → `test_startup_survives_mount_generator_failure` **단 1건만** 실패 확인.
  → **교훈: 변이는 반드시 구문상 유효해야 한다. "변이 후 실패"만 보고받고 믿지 말 것.**
- (Task 3 결과) README 2종에 `### Dashboard document mounts` / `### 대시보드 문서 마운트` 소절을
  **순수 추가**(각 +23/−0). code-reviewer 가 경로·플래그·동작 주장을 `phase-tools.py`(37-40·455·
  483·516·571-575행)·`install.sh` 와 라인 단위로 대조해 PASS. py·sh 경로 규칙 이중화는
  **사용자 문서가 아니라 개발자 주의사항**이라 README 에 넣지 않았다 — 위 항목이 유일한 기록처다.
  유일한 🟠(새 소절이 상위 절 마무리 문장을 고아로 만듦)는 문장 이동 위임으로 해소.
  → **교훈: 기존 절 안에 `###` 를 추가할 때는 상위 절의 마무리 문장이 새 소절 아래로 밀리지
  않는지 확인할 것.**
- (환경) 이 워크트리는 `components/usage-dashboard`·`containers/browser` 서브모듈을 init 했다
  (PITFALLS 24 — init 없이는 실기동 테스트 5건이 환경 사유로 실패). 마감 시
  `git worktree remove --force --force` 수동 정리가 필요하다 (함정 7).

## 자동 결정 로그

(없음 — 오토 모드 아님)
