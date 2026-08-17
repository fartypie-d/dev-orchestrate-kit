# Task 1: install.sh 안내 stderr 통일·빈 값 메시지·`$arg` 주석 제거

- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `install.sh`, `tests/test_install_menu.py` (스트림 단언 갱신·추가)
- **선행**: 없음
- **목표**: ① `report_plan_skip`(274행)과 `report_ecc_lang_skip`(278행)의 "미입력" 분기 `note` 호출을
  `>&2`로 통일한다 — stdout은 데이터(DRY_RUN 계획 줄) 전용, 안내는 전부 stderr.
  ② `add_ecc_lang`의 거부 메시지(40행)가 빈 문자열일 때 `유효하지 않은 ECC 언어: (빈 값)`으로
  표기한다 (비어 있으면 `(빈 값)`, 아니면 값 그대로). ③ 34행의 옛 변수명 잔재 주석
  `# 기존 배열 보존 검사 식: ECC_LANGS[${#ECC_LANGS[@]}]="$arg"` 를 삭제한다.
- **재사용**: 개선 후 재사용 `install.sh`:`report_plan_skip`·`report_ecc_lang_skip`·`add_ecc_lang`
  (호출부: 707~718·775·924행 — 호출부는 수정하지 말고 함수 본문만). 새 헬퍼 금지.
- **실패 테스트**: `tests/test_install_menu.py`에 스트림 분리 단언을 추가한다 —
  `INSTALL_SELFTEST_MENU` 훅 경유로 `report_plan_skip`·`report_ecc_lang_skip`(미입력 분기)의 출력이
  **stderr에 있고 stdout에 없음**을 단언 (현재 stdout으로 나오므로 먼저 실패한다).
  빈 값 거부 메시지 `(빈 값)` 단언도 추가 (현재 값이 비어 나오므로 먼저 실패).
  기존 테스트 중 이 두 함수의 stdout 단언이 있으면 stderr로 갱신한다.
- **필독 스킬**: 없음 (opencode 쪽 skill 미필요 — 규칙은 아래에 인라인)
- **필수 규칙**:
  - bash 3.2 호환. `INSTALL_DRY_RUN=1` stdout 10줄 규약 절대 불변 (추가·순서 변경 금지).
  - `INSTALL_PARSE_ONLY`로 이 동작을 검증하지 말 것 — "항상 참" 함정 (`DOCs/PITFALLS.md` 1절).
  - 신규·수정 테스트는 **저장소 밖 임시 사본**에서 변이 검증 (`>&2` 제거 시 FAIL 확인) 후 보고에 증거 첨부.
  - 저장소 안 파일에 `sed -i`·`git checkout`·`git stash` 금지.
- **완료 조건**: `python3 -m unittest discover -s tests -v` 전체 통과 +
  `bash -n install.sh` 통과 + 변이 검증 증거 (깨뜨린 사본에서 신규 테스트 FAIL 출력).
