# Task 3: docs-index.py 심링크 버그 수정 + `--docs-dir`

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/docs-index.py`, `tests/test_docs_index.py` (신규)
- **선행**: 없음
- **목표**: 27행 `DOCS = Path(__file__).resolve().parent.parent / "DOCs"` 가 심링크
  (`scripts/docs-index.py` → `core/scripts/docs-index.py`)를 따라가 `core/DOCs`로 해석되는
  버그를 고친다. ① 경로 계산을 **심링크 비추종**으로 바꾼다 — `Path(os.path.abspath(__file__))`
  기반 (`resolve()` 사용 금지). ② argparse로 `--docs-dir <경로>` 오버라이드 인자를 추가한다
  (기본값 = 스크립트 위치 기준 `../DOCs`). 모듈 상수 `DOCS`/`INDEX`에 의존하는 함수가 있으면
  인자로 받게 정리하되 **출력 포맷·스캔 규칙은 불변**.
- **재사용**: 없음 — `grep -rn "abspath\|docs-dir" core/scripts/` 조사, 유사 처리 없음.
  argparse 사용 예는 `core/scripts/phase-tools.py` 참조 (스타일 통일).
- **실패 테스트**: `tests/test_docs_index.py` 신규 — 임시 디렉터리에
  `core/scripts/docs-index.py`(사본) + `scripts/docs-index.py`(심링크) + `DOCs/`(frontmatter 있는
  더미 PHASE 문서) 구조를 재현하고, **심링크 경로로 실행**했을 때 루트 `DOCs/INDEX.md`가
  생성되는지 단언한다 (현재 구현은 `core/DOCs` FileNotFoundError로 죽으므로 먼저 실패).
  `--docs-dir` 오버라이드 케이스 1건 추가.
- **필독 스킬**: 없음
- **필수 규칙**:
  - `scripts/docs-index.py`(심링크)를 수정하지 말 것 — **원본 `core/scripts/docs-index.py`만**.
  - 테스트는 저장소 밖 임시 디렉터리(`tempfile`)에서만 실행 파일을 만들 것. subprocess에 `timeout=` 필수.
  - 저장소의 실제 `DOCs/INDEX.md` 생성은 task 범위 아님 (검수 시 오케스트레이터가 실행).
  - 변이 검증: 사본에서 abspath를 resolve로 되돌려 신규 테스트 FAIL 확인.
- **완료 조건**: `python3 -m unittest discover -s tests -v` 전체 통과 + 변이 검증 증거.
