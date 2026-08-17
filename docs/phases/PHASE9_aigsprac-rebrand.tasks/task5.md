# Task 5: docs/assets/fig-kit*.svg 4종 개칭

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `docs/assets/fig-kit.svg`, `docs/assets/fig-kit-dark.svg`,
  `docs/assets/fig-kit-en.svg`, `docs/assets/fig-kit-en-dark.svg`
  (4개 — 파일명은 유지, 내부 텍스트만)
- **선행**: Task 0
- **목표**: 다이어그램 SVG 내부의 `dev-orchestrate-kit` 텍스트(파일당 3곳, 총 12곳)를
  `aigsprac`으로 바꾼다. 파일명·구조·좌표는 유지한다.
- **재사용**: 없음 — 텍스트 치환만
- **실패 테스트**: 불가 — SVG 텍스트 치환 (대체 검증: 완료 조건의 grep + XML 정형성 확인 + 리뷰어)
- **필수 규칙**:
  - `<text>`/`<title>`/주석 등 텍스트 노드만 치환. 태그·속성·경로(d=)·좌표는 불변.
  - 새 이름이 옛 이름보다 짧으므로(9자 vs 19자) 레이아웃 위험 없음 — 글자 폭 보정을
    시도하지 말 것 (x·width 조정 금지).
  - 라이트/다크·영/국문 4종 모두 동일하게.
- **금지**: SVG 재생성·최적화 도구 사용, 대상 외 파일 수정, `tests/` 수정, `git commit`.
- **완료 조건**:
  - `grep -c dev-orchestrate-kit docs/assets/fig-kit*.svg` → 모두 0
  - `python3 -c` 한 줄로 4파일 각각 `xml.etree.ElementTree.parse` 성공 (XML 정형성)
