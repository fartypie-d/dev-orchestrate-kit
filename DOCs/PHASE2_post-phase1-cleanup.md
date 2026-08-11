---
phase: 2
date: 2026-08-11
kind: task
domain: scripts, tests
status: done
commits: 45b6d2a,8441144,83945f0,b183254,b220a0c + 마감 문서 커밋
cost: $18.13 (세션 실측 — Phase 1 마감분 포함)
compactions: 0
interventions: 2
summary: Phase 1 리뷰 🟡 후속 정리 — install.sh 스트림·메시지·주석, 테스트 timeout, docs-index 심링크 버그, phase-close 병합 판정
---

# 작업 지시서 — Phase 1 후속 정리 (2026-08-11)

출처: `DOCs/PHASE1_install-ux-overhaul.md` "페이즈 마감 시 처리할 후속 항목" (🟡 기록분)
+ 2026-08-11 마감 중 실측된 phase-close 병합 판정 함정.

## 인터뷰 결과

- **스코프**: Phase 1 기록 후속 5건(2번은 이미 해소 확인돼 제외) + phase-close 병합 판정 개선.
  제외: install.sh 기능 추가, janitor(audit) 쪽 병합 판정 변경(안전상 이번엔 close 경로만).
- **우선순위**: 전 task 상호 독립 — 1→2→3→4 순차 위임 (전역 락이 직렬화).
- **제약**: bash 3.2 호환 / 실제 홈·네트워크 불가침 / `INSTALL_DRY_RUN` stdout 10줄 규약 불변 /
  `scripts/*`는 심링크 — **`core/scripts/` 원본만 수정** / 신규·수정 테스트는 저장소 밖 사본 변이 검증.
- **크기 등급**: standard → 전 task task-orchestrator 경유. kit-scripts는 로스터 ⚠️라 heavy tier.
- GATE 1: 2026-08-11 사용자 승인 (아래 설계 결정 포함).

## 설계 결정 (GATE 1에서 확정)

1. **안내 스트림 통일 = stderr** — stdout은 데이터(DRY_RUN 계획 줄) 전용. `report_plan_skip`·
   `report_ecc_lang_skip` 미입력 분기를 `>&2`로 통일.
2. **docs-index.py 경로 = 심링크 비추종** (`os.path.abspath`, `resolve()` 금지) + `--docs-dir` 오버라이드.
3. **phase-close 병합 판정 = origin/<db> ∪ 로컬 <db> ∪ 메인 체크아웃 HEAD** 중 하나의 조상이면
   병합으로 인정 + `--target <ref>` 수동 오버라이드. janitor(audit) 경로는 불변.

## 워크트리

- PHASE=2 / BRANCH=`feature/phase2-post-phase1-cleanup` /
  WORKTREE=`.claude/worktrees/phase2-post-phase1-cleanup`
- 베이스: origin/main claim 후 `feat/kit-v2-adapters` 머지로 보정 (Phase 1 산출물 포함).

## task 목록

| # | 제목 | 에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 1 | install.sh 안내 stderr 통일·빈 값 메시지·`$arg` 주석 제거 | kit-scripts | heavy | ✅ 완료 | `45b6d2a` |
| 2 | test_install_claude_bootstrap.py `subprocess.run` timeout 2곳 | kit-tests | default | ✅ 완료 | `8441144` |
| 3 | docs-index.py 심링크 버그 수정 + `--docs-dir` | kit-scripts | heavy | ✅ 완료 | `83945f0` |
| 4 | phase-tools.py close 병합 판정 확장 (+`--target`) | kit-scripts | heavy | ✅ 완료 | `b183254` |
| 4b | 리뷰 🟠 반려 수정 — 자기참조 오판·무효 `--target` 침묵 실패 | kit-scripts | heavy | ✅ 완료 | `b220a0c` |

상세: `DOCs/PHASE2_post-phase1-cleanup.tasks/task<N>.md`

## 결과 (GATE 2 제출용)

- **커밋 5개** (`45b6d2a`·`8441144`·`83945f0`·`b183254`·`b220a0c`), 전부 로컬. **origin 미푸시.**
- 최종 검증 (2026-08-11 실측): `python3 -m unittest discover -s tests` → **125 passed OK**
  (Phase 1 대비 +6: docs-index 2·phase-tools 2·회귀 2) / `bash -n` 4파일 SYNTAX_OK /
  `HOOK_SELFCHECK_PASS` / 변경 규모 8파일 +173/−34.
- 리뷰어 판정: task 1 (bash·security·silent-failure 3/3 APPROVE) / task 2 (python APPROVE) /
  task 3 (python·security·silent-failure 3/3 APPROVE) / task 4 **반려 1회**
  (security 🟠 자기참조 오삭제 + silent-failure 🟠 무효 --target 침묵 실패, 둘 다 실측 재현)
  → 4b 수정 후 확인 리뷰 2/2 APPROVE. 리뷰가 실데이터 손실 경로를 잡아낸 사례.
- 실사용 모델: task 1·3·4·4b = openai/gpt-5.6-terra (heavy) / task 2 = openai/gpt-5.6-luna (default).

### 정량 3필드

- 비용: `python3 scripts/session-cost.py` 실측 **$18.13** (이 세션 파일 1개 — Phase 1 마감분 포함).
- auto-compaction: **0회**.
- 사람 개입: **2회** (GATE 2 Phase 1 승인 + 푸시·후속 진행 지시. Phase 2 GATE 1 이후 무인).

## 전파 제약 누적

> 각 task 완료 보고에서 다음 task에 영향을 주는 사실을 여기에 append 한다.

- (Phase 1 계승) 커밋 메시지에 트리거 단어 필요 시 단순 `-m` 여러 개. heredoc·명령치환 금지.
- (Phase 1 계승) `INSTALL_PARSE_ONLY`로 메뉴 검증 금지 — 훅별 종료 지점은 `DOCs/PITFALLS.md` 1절.
- (Phase 1 계승) 병렬 위임 없음(순차)이지만 커밋은 항상 경로 명시 스테이징.
- task 1 리뷰 🟡 (기록만, 차기 후보): ① 빈 값 표기 관례 비일관 — `(빈 값)` vs 기존 `없음`(160·211행)
  ② "안내는 전부 stderr" 원칙이 파일 전역엔 미적용 — 다른 `note` 호출 다수(474·491·518·539·563·
  745·750·791~809·831·840·856·858·883행)는 여전히 stdout. 이번 task 스코프 밖(호출부 불변 제약).
- task 3 리뷰 🟡 (기록만, 차기 후보): ① 신규 테스트가 INDEX.md 존재만 단언(내용 행 단언 없음)
  ② 존재하지 않는 DOCs/`--docs-dir` 경로에서 raw traceback (사전 `is_dir()` 검사 권장)
  ③ `--docs-dir` 플래그명이 phase-tools.py와 의미 다르게 중복 (타입·기준 상이).
- task 4/4b 결과 — close 병합 판정 규약: 후보 = origin/<db> ∪ 로컬 <db> ∪ HEAD 브랜치(detached 제외),
  **자기참조(후보==판정 대상 브랜치) 자동 배제**, `--target` 은 사전 `rev-parse --verify` (무효 시 exit 2).
- task 4b 리뷰 🟡 (기록만, 차기 후보): ① 빈 후보 집합 진단 경로 자동 테스트 없음(수동 검증만)
  ② `--target` 자체의 rev-parse 호출에 `--` 구분자 없음(악용 경로는 없음, 일관성 차원)
  ③ `symbolic-ref` 현재 브랜치 조회가 cmd_close·_janitor_inner 중복(DRY) — 의도적 미해결
  ④ 빈 후보 진단 라인이 워크트리 없는 phase에도 출력(노이즈).

## 자동 결정 로그

- 2026-08-11 — Phase 1 마감 중 phase-close "미병합 — 보존" 실측 → task 4로 편입 (사용자 "후속도 진행" 승인 범위로 해석).

## 검증 명령 (모든 task 공통)

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh
bash scripts/hook-selfcheck.sh
```
