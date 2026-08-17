# Task 1: `phase-tools.py` 에 `dashboard-mounts` 서브커맨드

- **에이전트**: `kit-scripts`
- **모델**: heavy
- **대상 파일**: `core/scripts/phase-tools.py` (단 하나. `scripts/` 는 심링크 — 건드리지 말 것)
- **선행**: 없음
- **목표**: `python3 scripts/phase-tools.py dashboard-mounts` 가 오케스트레이트 레지스트리를 읽어
  usage-dashboard 용 compose override 를 `$ORCH_STATE_DIR/dashboard-compose.override.yml`
  (기본 `~/.local/state/orchestrate/dashboard-compose.override.yml`) 에 생성한다.
  마운트할 것이 하나도 없으면 **파일을 만들지 않는다**.

- **재사용**:
  - `그대로 재사용 core/scripts/phase-tools.py:state_dir()` — 레지스트리 디렉터리 해석.
    `ORCH_STATE_DIR` 주입이 이미 여기 있다. **새 경로 해석 함수를 만들지 말 것.**
    override 파일은 `state_dir().parent / "dashboard-compose.override.yml"` 에 쓴다
    (레지스트리 디렉터리가 아니라 그 **상위** 상태 디렉터리).
  - `그대로 재사용 core/scripts/phase-tools.py:main()` 의 argparse `sub.add_parser(...)` 패턴 —
    `init`/`claim`/`close`/`janitor` 와 같은 형태로 `dashboard-mounts` 를 추가한다.
  - `없음 — "docker-compose"·"override"·"volumes"·"yaml" 로 core/ 전역 조사, 킷에 compose 생성기 없음.`
    YAML 은 **문자열 조립**으로 쓴다 (PyYAML 의존 추가 금지 — 킷은 표준 라이브러리만 쓴다).

## 생성 규격

레지스트리(`state_dir()/*.json`)의 각 프로젝트에서 `root` + `docs_dir` 를 합쳐 **호스트 절대경로**를
얻고, 그 경로가 **실제로 존재하는 디렉터리일 때만** `<경로>:<같은 경로>:ro` 로 마운트한다.
대시보드가 문서를 호스트 절대경로 그대로 여는 구조(`app/main.py:_progress_docs_root`)라 좌우가 같아야 한다.

추가로 레지스트리 자체를 마운트하고 환경변수를 준다 (서브모듈 compose 에는 둘 다 없다):

```yaml
services:
  usage-dashboard:
    volumes:
      - /home/u/.local/state/orchestrate/registry:/data/orchestrate-registry:ro
      - /home/u/proj/DOCs:/home/u/proj/DOCs:ro
    environment:
      - USAGE_REGISTRY_DIR=/data/orchestrate-registry
```

- 경로 정렬은 **프로젝트명 오름차순**으로 결정적(deterministic)이게 한다.
- 중복 경로는 한 번만 쓴다.
- 파싱 불가·필드 누락 JSON 은 건너뛰고 stderr 경고 한 줄. **exit 0 유지** (대시보드 기동을 막지 않는다).
- 마운트할 DOCs 가 하나도 없고 레지스트리 디렉터리도 비어 있으면(=`services:` 아래 쓸 게 없으면)
  파일을 쓰지 않는다. **기존 파일이 있으면 지운다** — 낡은 override 가 사라진 경로를 마운트하면
  docker 가 host 에 root 소유 빈 디렉터리를 만든다 (sudo 없이 못 지운다).
- 성공 시 생성 경로를 **stdout 한 줄**로 출력한다 (install.sh 가 이 값을 읽는다).
  쓸 게 없어 만들지 않았으면 stdout 에 아무것도 쓰지 않는다.
- `--print-path` 옵션: 생성하지 않고 대상 경로만 출력 (install.sh 존재 확인용, 선택 구현 아님 — 필수).

- **실패 테스트** (오케스트레이터가 이미 작성·동결 — **`tests/` 를 수정하지 말 것**):
  - `tests/test_dashboard_mounts.py::test_writes_override_with_registry_and_docs_mounts`
    — 존재하는 DOCs 2개 + 레지스트리 마운트 + `USAGE_REGISTRY_DIR` 이 모두 들어가는지
  - `tests/test_dashboard_mounts.py::test_skips_missing_docs_dir`
    — `root/docs_dir` 가 없는 프로젝트는 volumes 에 **절대 나타나지 않아야** 한다
  - `tests/test_dashboard_mounts.py::test_empty_registry_writes_no_file`
    — 빈 레지스트리면 파일이 생기지 않고, 기존 파일이 있었으면 제거되며, exit 0
  - 전부 `ORCH_STATE_DIR` 를 임시 디렉터리로 주입한다. 실제 `~/.local/state` 를 건드리면 안 된다.

- **필독 스킬**: `python-patterns`
- **필수 규칙**:
  - 표준 라이브러리만. 외부 의존성 추가 금지.
  - `state_dir()` 를 복사해 변형하지 말 것 — 그대로 호출한다.
  - 기존 `init/claim/close/janitor` 동작·시그니처를 바꾸지 말 것 (순수 추가).
  - 절대 경로 문자열을 셸로 넘기지 않는다 (subprocess 사용 없음).
  - 파일은 `0o600` 이 아니라 기본 권한이면 된다(비밀 아님) — 다만 **레지스트리 밖 경로를 쓰지 말 것**.

- **완료 조건**:
  1. `python3 -m unittest tests.test_dashboard_mounts -v` → 3개 전부 통과
  2. `python3 -m unittest discover -s tests` → 기존 테스트 회귀 없음
  3. 변이 검증: `.orchestrate/mut1/` 에 저장소를 복사해 (a) `docs_dir` 존재 검사 제거,
     (b) 빈 레지스트리에서도 파일을 쓰도록 변경 — 각각 해당 테스트가 **실패**해야 한다
