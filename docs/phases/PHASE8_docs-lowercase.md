---
phase: 8
date: 2026-08-15
kind: task
domain: scripts, docs
status: done
commits: f8d78d6, b190b4f, 855663c, f73f1ae, d69186a, 8099038
cost: $32.08 (메인 세션 실측 — 위임 opencode 비용 별도)
compactions: 0
interventions: 1
summary: DOCs/ → docs/phases/ 소문자 통일 (킷 도그푸딩) — 이동 + 툴링 경로 탈하드코딩 + 참조 일괄 갱신
---

# 작업 지시서 — DOCs → docs/phases 소문자 통일, 킷 선행 도그푸딩 (2026-08-15)

> 근거: `DOCs/PLAN_docs-lowercase-migration.md` (2026-08-15 작성, 전제 실측 포함).
> 이 페이즈는 **킷만** 다룬다. k-stock·insane-cloak·s-orchestrator는 이 절차가 검증된 뒤
> 저장소당 1페이즈로 별도 진행 (착수 전 프로젝트 확인 가드 승인 필요).

## 인터뷰 결과
- 스코프: dev-orchestrate-kit 저장소 내 `DOCs/` → `docs/phases/` 이동 + 툴링·훅·어댑터·문서의
  경로 참조 갱신. 타 프로젝트 3개는 **제외** (후속 페이즈).
- 우선순위: 이동(T1) → 툴링(T2) → 훅·어댑터(T3) → 제품 문서(T4).
- 제약: 과거 페이즈 문서의 **본문 내용은 수정 금지** (살아있는 경로 참조만 갱신).
  레지스트리 `docs_dir` 전환과 전역 스킬 재설치는 **병합 후** 수행 (main이 아직 DOCs인 동안
  바꾸면 대시보드·전역 스킬이 깨진다).
- 크기 등급: **large** (저장소 횡단 리네임 + 툴링·훅·어댑터) → task-orchestrator 경유, heavy tier.
- 사용자 결정 (2026-08-15, 루트 세션 AskUserQuestion): "기존 계획대로 페이즈 진행" 채택.

## 전제 실측 (2026-08-15 재확인)
| 전제 | 근거 | 판정 |
|---|---|---|
| docs-index가 `DOCs` 하드코딩 | `core/scripts/docs-index.py:32` `default_docs_dir()` | 유지 — T2 대상 |
| phase-tools init 기본값 `DOCs` | `core/scripts/phase-tools.py` usage·argparse default | 유지 — T2 대상 |
| 훅이 `*/DOCs/*` 제외 | `.claude/hooks/post-edit-check.sh:7` (어댑터 사본 동일) | 유지 — T3 대상 |
| phase-tools 본체는 레지스트리 `docs_dir` 사용 | plan §전제 실측 | 유지 — 값 전환은 병합 후 |
| 레지스트리: kit=`DOCs` | `~/.local/state/orchestrate/registry/dev-orchestrate-kit.json:5` | 유지 |
| 킷에 열린 워크트리 없음 (phase8 자신 제외) | `git worktree list` 2026-08-15 | 유지 |
| 훅 자가진단 PASS | `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS` | 유지 |

## 계획서와 다른 결정 1건
plan은 docs-index를 "레지스트리 `docs_dir` 참조"로 바꾸라 했으나, **프레시 클론(레지스트리 없는
머신)에서 docs-index가 단독 동작해야 하는 이식성 요구**와 충돌한다. 결정: **`docs/phases` 우선,
없으면 `DOCs` 폴백(마이그레이션 전 저장소 호환), `--docs-dir` 플래그로 명시 지정 가능.**
레지스트리 의존은 추가하지 않는다. (GATE 1에서 확정)

## Task 목록
| # | 제목 | 실행 주체/에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 1 | `git mv DOCs docs/phases` (이력 보존 확인) | 메인 직접 (문서 도메인) | - | ✅ 완료 | f8d78d6 |
| 2 | docs-index 탈하드코딩 + phase-tools init 기본값 | kit-scripts (task-orchestrator 경유) | heavy | ✅ 완료 (반려 3회, 예외 1회 승인) | a06829a·023e453·3e20add·b190b4f (RED ae38698·ed99367·d9c5782·d5de631) |
| 3 | 훅 제외 패턴 + 어댑터·템플릿·CLAUDE·AGENTS 참조 갱신 | kit-scripts (task-orchestrator 경유) | heavy | ✅ 완료 (리뷰 🟠 2건 즉시 반영) | 855663c·f73f1ae(템플릿)·d69186a(훅 병행) |
| 4 | README·WORKFLOW·PORTING 문서 갱신 (영/국문) | kit-docs (task-orchestrator 경유) | default | ✅ 완료 (code-reviewer PASS, 🟡 1) | 8099038 |

상세: `DOCs/PHASE8_docs-lowercase.tasks/task<N>.md` (T1 이후 경로는 `docs/phases/PHASE8_...`)

## 리뷰 예상 지점 (RED 사전 고정)
| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| docs-index 폴백 순서 | `docs/phases`·`DOCs` 공존/부재 시 오동작·침묵 실패 | `tests/test_docs_index.py::test_docs_dir_prefers_docs_phases`·`::test_docs_dir_falls_back_to_DOCs` (T2) |
| 훅 제외 패턴 | `*/docs/*`로 넓히면 docs 하위 코드 검사 누락 | 패턴은 `*/docs/phases/*` 한정 + `hook-selfcheck.sh` 케이스 추가 (T3) |
| 참조 잔존 | 갱신 누락된 `DOCs` 경로 참조 | 완료 조건의 잔존 grep 검증 (T3·T4 공통) |

## 병합 후 체크리스트 (GATE 2 통과 → 메인이 수행)
1. main 병합 → `~/.local/state/orchestrate/registry/dev-orchestrate-kit.json` `docs_dir`를 `docs/phases`로 전환
2. `./install.sh`(claude 어댑터) 재실행 — 전역 `~/.claude/skills/orchestrate/SKILL.md` 반영
3. `python3 scripts/docs-index.py` 재생성 + usage-dashboard 마운트 재생성(README 절차)
4. `bash scripts/phase-close.sh 8`

## 자동 결정 로그
- (없음 — 일반 모드)

## 전파 제약 누적
- (T1 완료 후: 지시서 경로가 `docs/phases/PHASE8_docs-lowercase.md`로 바뀜 — 이후 task는 새 경로 기준)
- 이 워크트리의 unittest discover 전체는 컨테이너 실기동 4건이 환경 기인(서브모듈 미초기화)으로 항상 실패 — 기준선으로 취급, init 금지 (PITFALLS 24/7)
- INDEX 첫 줄 제목이 실제 경로 라벨로 동적 생성됨 — T3·T4에서 "DOCs 인덱스" 문구 참조 갱신
- T2 리뷰 반려 1회 (silent-failure-hunter 🔴): init 정적 기본값 → 동적 폴백으로 재위임 (RED ed99367 동결)
- `docs/PORTING.md:147`의 `--docs-dir <DOCs|docs>` 표기가 새 기본값과 불일치 — T4에서 갱신 (리뷰어 🟡)
- T2 최종 리뷰 잔여 권고 (비차단, 후속 페이즈 후보): 🟠 `.tasks/` 디렉터리가 phase_document_files 제외 목록에 없어 PHASE 패턴 파일명 유입 시 next_phase 오염 가능 / 🟡 제외 목록(TEMPLATES·specs·images)이 두 스크립트에 이중 관리
- phase-tools 문서 판정은 phase_document_files 단일 헬퍼(재귀·reviews 인지) 경유 — 스캔 대상 변경은 이 헬퍼만
- 훅 제외 패턴은 전환기 동안 `*/docs/phases/*|*/DOCs/*` 병행 (d69186a) — **4개 프로젝트 이관 완료 후 DOCs 제거하는 후속 정리 필요**
- 타 프로젝트 이관 순서 주의: 어댑터 재설치 전에 해당 프로젝트의 DOCs→docs/phases 이관을 선행하거나, 병행 패턴 유지 상태로 설치 (silent-failure-hunter 실측)
- SKILL.md의 `docs/phases/TODO.md` 참조는 실재하지 않는 파일 (구 DOCs/TODO.md부터의 기존 결함, 문자열 치환만 됨) — 후속 정리 후보
