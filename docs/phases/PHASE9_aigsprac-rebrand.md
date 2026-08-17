---
phase: 9
date: 2026-08-17
kind: task
domain: docs, install
status: done
commits: 5ab35b8..8c0702e (10개 — task0~6 + 1b + 인덱스 2)
cost: $23.57 (session-cost.py 실측)
compactions: 0
interventions: 2
summary: dev-orchestrate-kit → aigsprac 리브랜딩 — 라이브 표면 치환 + 백로님 스토리 + 저장소·로컬 리네임
---

# 작업 지시서 — aigsprac 브랜딩 전환 (2026-08-17)

> 스펙: `docs/superpowers/specs/2026-08-17-aigsprac-rebrand-design.md` (승인됨)
> 로드맵 페이즈 ①/⑤. 새 제품명 **aigsprac** (전부 소문자), 백로님 *"AI General Staff practice"*.

## 인터뷰 결과

- 스코프: 라이브 표면 11파일의 옛 이름 치환 + README 백로님 스토리 + GitHub 저장소 2개
  리네임 + 로컬 디렉터리 리네임(마감 직전). **제외**: 이력 문서(docs/phases·specs·plans·
  superpowers), 서브모듈 README 2개(별도 저장소 — 후속), `core/project-template/`(불가침).
- 우선순위: 파일 치환(Task 1~6) → GATE 2 → 저장소 리네임 → 로컬 리네임.
- 제약: `__PROJECT__` 플레이스홀더 불변 / 이력 문서 소급 치환 금지 / main 직접 push 금지.
- 크기 등급: **large** (11파일 횡단 — 계약 변경·설계 모호성 없음, 작업 성격은 기계적 치환)

## 전제 실측

| 전제 | 근거 | 유지/뒤집힘 |
|---|---|---|
| 옛 이름 라이브 표면 분포 | README 3+3, CLAUDE 2, AGENTS 1, orchestrate.md 1, install.sh 1(주석), WORKFLOW 2+2, svg 3×4, adapters 1+1 | 유지 |
| INDEX.md에 구명 한 줄 추가 | `scripts/docs-index.py`가 INDEX 전체 재생성 — 수동 줄 덮어써짐 | **뒤집힘** → 구명 표기는 README 영/국문에 |
| 컴포넌트 README 치환 | containers/browser·components/usage-dashboard 는 **서브모듈** (`git submodule status` 실측) | **뒤집힘** → 이번 페이즈 제외, 후속 기록 |
| tests/ 에 옛 이름 어서션 없음 | 저장소 grep 97곳 목록에 tests/ 없음 | 유지 |
| new-project.sh·adopt-project.sh 에 옛 이름 없음 | grep 파일 목록에 없음 | 유지 |

## Task 목록 (상세: `PHASE9_aigsprac-rebrand.tasks/task<N>.md`)

| # | 제목 | 에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 0 | 회귀 가드 테스트 (오케스트레이터 직접 작성·동결) | — (메인) | — | 완료 | 5ab35b8 |
| 1 | README.md·README.ko.md 리브랜딩 + 백로님 스토리 | kit-docs | default | 완료 (PASS 🟡1) | 3cefdf7 |
| 2 | CLAUDE.md·AGENTS.md·.claude/orchestrate.md 개칭 | kit-docs | default | 완료 (PASS 🟡1) | b10a47a |
| 3 | install.sh 헤더 주석 개칭 | kit-scripts | heavy | 완료 (PASS×3) | 35544ae |
| 4 | docs/WORKFLOW.md·WORKFLOW.ko.md 개칭 | kit-docs | default | 완료 (PASS) | da82f09 |
| 5 | docs/assets/fig-kit*.svg 4종 개칭 | kit-docs | default | 완료 (PASS) | 4c0c673 |
| 6 | adapters onboard 스킬·프롬프트 개칭 | kit-docs | default | 완료 (PASS) | af62d27 |
| 7 | GitHub 저장소 2개 리네임 + 리모트 갱신 (GATE 2 후, 메인 직접) | — (메인) | — | 대기 | - |
| 8 | 로컬 디렉터리 리네임 + 메모리 이주 (마감 직전, 메인 직접) | — (메인) | — | 대기 | - |

의존: Task 0 → 1~6 (병렬 가능하나 위임은 프로젝트 락으로 직렬) → GATE 2 → 7 → 8.

## 리뷰 예상 지점

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| `core/project-template/` 오염 | 일괄 치환이 `__PROJECT__` 원본을 건드림 (2026-08-08 실측 사고 재발) | `tests/test_rebrand.py::test_project_template_intact` (Task 0, 동결) |
| 이력 문서 소급 치환 | docs/plans(52곳)·docs/phases 를 에이전트가 "친절하게" 치환 | `tests/test_rebrand.py::test_history_docs_untouched` (Task 0, 동결) |
| README 영/국문 비동기 | 한쪽만 치환하거나 스토리 절이 영문에만 추가됨 | `tests/test_rebrand.py::test_readme_rebranded` (양쪽 어서션) |

## 검증 (페이즈 말 총괄)

```bash
python3 -m unittest discover -s tests -v        # 가드 테스트 포함 전부 통과
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh
bash scripts/hook-selfcheck.sh                   # HOOK_SELFCHECK_PASS
grep -rIl "dev-orchestrate-kit" --exclude-dir=.git --exclude-dir=.claude \
  --exclude-dir=containers --exclude-dir=components . \
  | grep -v -e '^./docs/phases/' -e '^./docs/specs/' -e '^./docs/plans/' \
            -e '^./docs/superpowers/'             # 기대: 출력 0건
```

## 전파 제약 누적

- [Task 1] 명명 규칙 확정: 소문자 `aigsprac`, 구명 표기는 `formerly **dev-orchestrate-kit**`(EN) / `구 **dev-orchestrate-kit**`(KO) — 이후 task 동일 규칙.
- [베이스라인] unittest 실패는 **리베이스 후 309개 중 10건** (전부 docker/dashboard 컨테이너 환경 — 스태시 대조로 코드 무관 실측, Task 3에서 갱신. 리베이스 전 기록 276/4는 무효). 페이즈 말 총괄 검증에서 이 10건 외 실패만 회귀로 판정.
- [리베이스] phase-claim이 낡은 origin/main(f3a4884)에서 분기 → main(d952ec6) 위로 리베이스 완료. **새 함정 후보: 로컬 main 미푸시 상태에서 phase-claim 실행 → 낡은 분기** (마감 때 PITFALLS 기록).

## 자동 결정 로그

- (오토 모드 아님 — 해당 없음)

## 개입 기록 (interventions: 2)

1. phase-claim 낡은 분기(PITFALLS 25) — 리뷰어 발견 → `git rebase main` 으로 해소, 충돌 없음.
2. Task 4 위임을 셸 `&`로 분리 실행해 래퍼 stdout(MODEL_USED)이 유실, Monitor 오감시로 30분
   지연. 교훈: 위임은 항상 하네스 `run_in_background` 경유 (stdout 이 완료 신호다).

## 후속 (이번 페이즈 제외)

- 서브모듈 README 2건(containers/browser, components/usage-dashboard)의 옛 이름 각 1곳 —
  각 서브모듈 저장소에서 별도 처리.
- 페이즈 ②~⑤ (doctor UX / 패턴 메모리 / 위임 자동화 / aigsprac.com 사이트) — 스펙 참조.
