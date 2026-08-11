---
phase: 3
date: 2026-08-11
kind: task
domain: containers, docs
status: done
commits: 07ecca0,9e2846a + 마감 문서 커밋 (PR 병합)
cost: $29.73 (세션 누적 실측 — Phase 1 마감·Phase 2 포함)
compactions: 0
interventions: 3

summary: insane-cloak 서브모듈 범프 (fc88eaa→2f99245, MCP 절 포함) + 키트 README 에 MCP 사용법 절 추가
---

# 작업 지시서 — insane-cloak MCP 반영 (2026-08-11)

## 인터뷰 결과

- **스코프**: ① 서브모듈 `containers/browser` 포인터 fc88eaa → 2f99245 (공개 저장소 푸시 확인됨)
  ② 키트 `README.md` 브라우저 컨테이너 절에 MCP 사용법 요약 추가. 제외: `.mcp.json` 어댑터
  템플릿(선택지에서 미채택), 브라우저 툴 레이어 스펙(별도 대형 페이즈).
- **제약**: 상세는 서브모듈 README 4절이 단일 소스 — 키트 README 는 요약+참조만 (중복 금지).
- **크기 등급**: **small** (README 1파일 + 포인터 1커밋) → 간이 지시서, 직접 위임(6-B), 리뷰어 code-reviewer.
- GATE 1: 인터뷰 선택지("범프 + README MCP 절 (권장)" 채택, 2026-08-11)로 갈음 — 범위가 선택지와 동일.

## 워크트리

PHASE=3 / BRANCH=`feature/phase3-insane-cloak-mcp-bump` / 베이스: origin/main `cb72f3b`
(kit-v2 스택·ECC 보고서 채택 포함 — 다른 세션이 main 병합·푸시 완료한 상태에서 claim).

## task 목록

| # | 제목 | 에이전트 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 서브모듈 포인터 범프 (오케스트레이터 직접 — git 포인터 op) | (직접) | ✅ 완료 | `07ecca0` |
| 2 | README.md 브라우저 절에 MCP 사용법 요약 추가 | kit-docs | ✅ 완료 | `9e2846a` |

## 결과 (GATE 2 제출용)

- 커밋 2개: `07ecca0`(서브모듈 범프 fc88eaa→2f99245) + `9e2846a`(README MCP 절 +18줄). 로컬, 미푸시.
- 검증: unittest 125 OK (문서·포인터 변경 무영향 확인) / code-reviewer APPROVE (findings 0 —
  .mcp.json 예시 서브모듈 README와 바이트 일치, 참조 실재, 순수 추가 확인).
- 실사용 모델: task 2 = openai/gpt-5.6-luna (default). 위임 1회, 반려 0회.
- 병합 대상: **main** (베이스가 origin/main cb72f3b — main 직접 push는 가드 차단이므로 PR 경유 권장).

## Task 2: README.md MCP 절

- **에이전트**: kit-docs / **모델**: default
- **대상 파일**: `README.md` (1파일)
- **목표**: "독립 모듈 — 브라우저 컨테이너" 절(94~110행 부근)에 MCP 연결 요약 추가 —
  chrome-devtools-mcp 를 `.mcp.json` 으로 :9222 CDP 에 붙이는 최소 예시 + fingerprint 격리 한 줄 +
  상세는 `containers/browser/README.md` 4절 참조.
- **재사용**: 그대로 재사용 `containers/browser/README.md` 4절 (MCP 절) — 내용을 복제하지 말고
  최소 예시 + 참조로. 새 파일 금지.
- **실패 테스트**: 불가 (markdown 문서) — 대체 검증: 참조 경로·링크 실재 확인 + 리뷰어 검수.
- **완료 조건**: `python3 -m unittest discover -s tests` 통과(문서 변경이라 무영향 확인) + code-reviewer APPROVE.

## 자동 결정 로그

- 2026-08-11 — insane-cloak 푸시는 사용자 승인 후 시도했으나 이미 타 세션이 푸시 완료(2f99245) →
  포인터를 8399dbc 가 아닌 최신 2f99245 로 범프 (문서 커밋 1개 차이, 동일 성격).
- 2026-08-11 — claim 베이스가 이미 최신 main(cb72f3b)이라 feat/kit-v2-adapters 머지 보정 불필요
  (해당 로컬 브랜치는 타 세션이 main 병합 후 삭제).
- 2026-08-11 — 서브모듈 포인터 커밋은 소스 수정이 아닌 git 포인터 op 로 판단, 오케스트레이터가 직접 수행.

## 검증 명령

```bash
python3 -m unittest discover -s tests -v
bash scripts/hook-selfcheck.sh
```
