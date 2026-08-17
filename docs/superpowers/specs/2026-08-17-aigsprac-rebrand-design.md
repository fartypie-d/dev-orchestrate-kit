# aigsprac 리브랜딩 + 고도화 로드맵 설계

- 날짜: 2026-08-17
- 상태: 사용자 승인 (브레인스토밍 세션)
- 범위: 마스터 로드맵 5페이즈 + 페이즈 ①(브랜딩 전환) 상세 설계

## 배경: ruflo 분석에서 얻은 방향

경쟁 서비스 [ruvnet/ruflo](https://github.com/ruvnet/ruflo)(구 claude-flow, ★68k)를 심층
분석했다. 표방 규모(100+ 에이전트, ~210 MCP 도구, 스웜·합의·자기학습)는 압도적이나,
독립 감사(2026-04, roman-rr)에서 **MCP 도구의 ~97%가 스텁**으로 판정됐다 — `agent_spawn`은
LLM 호출 없이 Map 기록만, 벤치마크 비교 대상이 `sleep(352)`, 신경망 정확도는 `Math.random()`.
실제로 동작이 확인된 가치는 두 가지뿐: **HNSW 메모리 계층**과 **설치·진단 UX**
(`init wizard` / `init doctor` / `init upgrade --add-missing` / `eject`).

비교 결론:

| 관점 | ruflo | 본 키트 |
|---|---|---|
| 위임 파이프라인 | 자동화 수사, 실체는 스텁 다수 | `run-delegation.sh` 락·exit code — 실배선 |
| 검증 게이트 | 자동·암묵적(스텁 합의) | 리뷰어 + 고정 검증 명령 + 변이 검증 — 명시적 |
| 상태 외부화 | SQLite/벡터 DB (유일하게 진짜) | 마크다운 페이즈 문서 — 감사 가능 |
| 설치·온보딩 UX | 가장 성숙 | doctor류 진단·증분 업그레이드 부재 |

**전략**: 우리 차별점(실측 함정 문서·동결 회귀 테스트·명시적 게이트)은 유지·강조하고,
ruflo에서 진짜였던 두 축(설치 진단 UX, 세션 간 메모리)을 이식한다. 규모의 수사는 따라가지
않는다.

## 브랜드 결정

- **제품명**: `aigsprac` — 전부 소문자 (CLI 도구 관례).
- **백로님**: *"AI General Staff practice"* — 오케스트레이터 = 참모본부(계획·검토·승인),
  위임 에이전트 = 예하 부대(실행). 기존 supervisor→delegation 서사에 정확히 대응.
- **도메인**: aigsprac.com (보유 중). 페이즈 ⑤에서 GitHub Pages + 커스텀 도메인으로 활용.
- **리네이밍 범위**: 이름 + 도메인 풀 브랜딩 (저장소명·문서·랜딩 사이트까지).

## 마스터 로드맵 (페이즈 1개 = 세션 1개)

| # | 페이즈 | 내용 | 산출물 |
|---|---|---|---|
| ① | 브랜딩 전환 | 저장소·문서·내부 명칭 → aigsprac | 리네임된 저장소 2개, 새 README |
| ② | doctor·upgrade UX | 설치 후 자가진단(`doctor`), 증분 업그레이드(`--add-missing`) | install.sh 신기능 + 테스트 |
| ③ | 패턴 메모리 | PITFALLS·페이즈 문서의 기계 판독 구조화 + 회수 훅 (마크다운 감사가능성 유지) | 메모리 스키마 + 훅 |
| ④ | 위임 자동화 | task 분해·병렬 위임 자동화 강화 — 명시적 게이트는 유지 | orchestrate 스킬 개선 |
| ⑤ | 랜딩·문서 사이트 | aigsprac.com 사이트 (제품 소개·설치 가이드·비교표) | 사이트 + DNS 연결 |

순서 근거: 브랜딩을 먼저 확정해야 이후 산출물(명령어명·문서·사이트 콘텐츠)이 새 이름으로
생성돼 재작업이 없다. 사이트는 콘텐츠가 쌓인 마지막에.

각 페이즈는 별도 세션에서 spec → plan → `/orchestrate` 위임 사이클로 진행한다.

## 페이즈 ① 브랜딩 전환 — 상세 설계

### 저장소 리네임

- GitHub에서 두 리모트 모두 `aigsprac`으로 리네임:
  - origin: `ACIF-ai-dev/dev-orchestrate-kit` → `ACIF-ai-dev/aigsprac`
  - public: `fartypie-d/dev-orchestrate-kit` → `fartypie-d/aigsprac`
- GitHub이 옛 URL을 자동 리다이렉트하므로 파괴 위험 낮음. 로컬 리모트 URL 갱신 필요.

### 문자열 치환 원칙

- **살아있는 표면만 치환**: README.md / README.ko.md, CLAUDE.md, AGENTS.md, install.sh,
  adapters/*, `.claude/orchestrate.md`, docs/assets/*.svg (다이어그램 4종),
  docs/WORKFLOW.md / WORKFLOW.ko.md, containers/browser/README.md,
  components/usage-dashboard/README.md.
- **이력 문서는 옛 이름 유지**: docs/phases/, docs/specs/, docs/plans/,
  docs/superpowers/specs/ — 작성 시점 기록의 소급 재작성 금지 (감사가능성).
  대신 `docs/phases/INDEX.md` 상단에 "구명 dev-orchestrate-kit → aigsprac (2026-08-17)"
  한 줄 추가.
- **함정 준수**: `core/project-template/`의 `__PROJECT__` 플레이스홀더 절대 불변
  (2026-08-08 실측 사고). 전역 일괄 치환 금지 — 파일 목록 명시 방식으로.
- 실측 기준(2026-08-17): 옛 이름 97곳 / 25파일.

### README 개편

- 타이틀·배지·클론 URL을 aigsprac으로.
- 백로님 스토리 절 추가: "aigsprac = AI General Staff practice" + 참모본부 메타포.
- 영/국문(README.md, README.ko.md) 동기 갱신.

### 로컬 체크아웃

- 페이즈 ① **마감 직전**에 `/home/jh/dev-orchestrate-kit` → `/home/jh/aigsprac` 리네임.
- 선행 작업: Claude Code 메모리 디렉터리(`~/.claude/projects/-home-jh-dev-orchestrate-kit/`)를
  새 경로 키(`-home-jh-aigsprac`)로 복사. 다음 세션부터 새 경로에서 시작.

### 실행 방식·검증

- 소스(README·install.sh·adapters 등) 수정은 `/orchestrate` 위임 파이프라인으로.
  페이즈 문서 `docs/phases/PHASE9_aigsprac-rebrand.md`로 상태 외부화.
- 검증: 표준 3종(`python3 -m unittest discover -s tests -v`, `bash -n …`,
  `bash scripts/hook-selfcheck.sh`) + 치환 후 `grep -rI dev-orchestrate-kit`가
  이력 문서 외 0건인지 확인.
- 브랜치 규칙 준수: `feat/aigsprac-rebrand` 계열에서 작업 후 main 병합.

## 결정 기록

| 결정 | 선택 | 비고 |
|---|---|---|
| 리네이밍 범위 | 이름+도메인 풀 브랜딩 | |
| 이름 유래 | 특별한 의미 없음 → 백로님 역부여 | AI General Staff practice |
| 표기 | aigsprac (전부 소문자) | CLI 관례 |
| 페이즈 순서 | 브랜딩 먼저 | 재작업 방지 |
| 이력 문서 | 옛 이름 유지 | INDEX에 구명 표기 1줄 |
| 로컬 디렉터리 | 페이즈 마지막에 리네임 | 메모리 이주 포함 |
