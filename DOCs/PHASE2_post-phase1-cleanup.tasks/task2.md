# Task 2: test_install_claude_bootstrap.py `subprocess.run` timeout 2곳

- **에이전트**: kit-tests
- **모델**: default
- **대상 파일**: `tests/test_install_claude_bootstrap.py`
- **선행**: 없음
- **목표**: 42행·152행의 독립 `subprocess.run` 호출에 `timeout=`을 추가해 공용 헬퍼와 같은
  행업 보호를 갖게 한다. 값은 `tests/_install_helpers.py`의 공용 timeout 상수와 통일한다
  (상수가 없으면 헬퍼에 모듈 상수로 승격해 양쪽이 공유 — 매직 넘버 중복 금지).
- **재사용**: 개선 후 재사용 `tests/_install_helpers.py`의 timeout 값/상수 (grep `timeout` 으로
  현재 값 확인 후 동일 값 사용). 새 헬퍼 함수 금지.
- **실패 테스트**: 불가 — 테스트 인프라 자체 수정(테스트의 테스트 없음).
  **대체 검증**: `grep -n "subprocess.run" tests/test_install_claude_bootstrap.py` 전 호출에
  `timeout` 인자 존재 확인 + 전체 unittest 통과.
- **필독 스킬**: 없음
- **필수 규칙**: 테스트 동작·단언 변경 금지 — timeout 인자 추가만. 실제 홈·네트워크 불가침 유지.
- **완료 조건**: `python3 -m unittest discover -s tests -v` 전체 통과 + grep 증거.
