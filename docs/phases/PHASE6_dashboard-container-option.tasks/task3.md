# Task 3: README 영·한 문서 반영

- **에이전트**: kit-docs
- **대상 파일**: `README.md`, `README.ko.md`
- **선행**: Task 2 (구현 확정 후 문구 작성)
- **목표**: usage-dashboard 절의 수동 4줄(submodule init → cd → build → up)을
  `./install.sh --containers=dashboard` (또는 마법사 선택) 경로로 대체·보완한다.
  usage 헤더 주석(`install.sh` 4행)과 Layout 표는 Task 2 가 갱신한 것을 따른다.
- **재사용**: 그대로 재사용 — 기존 usage-dashboard 절(`README.md` "## usage-dashboard — session
  observability" / `README.ko.md` 대응 절)을 수정. 새 절 신설 금지.
- **실패 테스트**: 불가 (markdown 문서) — 대체 검증: 문서에 적힌 플래그·경로가 실재하는지
  `grep -n 'containers=' install.sh`·`ls components/` 로 확인 + 리뷰어 검수 (로스터 대체 검증 표).
- **필독 스킬**: 없음
- **필수 규칙**: 영·한 내용 동등 (한쪽만 갱신 금지). 수동 docker compose 경로도 대안으로 유지
  (docker 없이 배포하는 사용자용). 대상 파일 외 수정 금지.
- **완료 조건**: 영·한 두 문서에 `--containers=dashboard` 반영 + 문서 내 명령·경로 실재 확인 출력.
