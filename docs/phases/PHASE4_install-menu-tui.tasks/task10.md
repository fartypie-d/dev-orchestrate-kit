# Task 10: insane-cloak 활용 기본 스킬

- **에이전트**: kit-docs
- **모델**: default
- **대상 파일**: `adapters/claude/global/skills/insane-cloak-browser/SKILL.md` (신규) — **단 1개**
- **선행**: 없음 (Task 8·9 와 독립 — 병행 가능)
- **목표**: browser 컨테이너가 떠 있으면 **MCP 미연결 상태에서도** 에이전트가 insane-cloak을
  활용할 수 있도록 사용법 스킬을 전역 스킬로 추가한다. MCP를 연결한 경우와 안 한 경우의
  경로를 모두 다룬다.

## 실측 사실 표 (2026-08-12, 오케스트레이터가 메인 체크아웃에서 실측 — 이것만 쓸 것)

> 서브모듈 커밋 `aa7a284`. **아래 표에 없는 명령·포트·플래그는 문서에 쓰지 말고**
> "자세한 것은 `containers/browser/README.md` 참조"로 위임한다.

| 항목 | 실측값 |
|---|---|
| compose project / 컨테이너 이름 | `chrome-cdp` (`containers/browser/docker-compose.yml:23,26,29` — 고정) |
| 이미지 | `local/chrome-cdp:0.11.0` |
| 포트 | `127.0.0.1:9222` 순수 CDP / `127.0.0.1:9223` 우회 fetch API / (옵션) noVNC `6080` |
| 기동 확인 | `GET http://127.0.0.1:9223/health` |
| 사용량 | `GET http://127.0.0.1:9223/usage` |
| fetch API | `GET /fetch?url=...&selector=...` 또는 `POST /fetch` (JSON 바디) |
| fetch 응답 필드 | `ok`, `verdict`, `content`, `final_url`, `trace[]`, `summary`, `prompt_injection_risk` |
| CLI | `containers/browser/bin/insane-fetch` — **`--selector` 필수**, 종료코드 `0` 성공 / `1` 실패 / `2` 사용법 오류 |
| 다른 컨테이너에서 접근 | `docker network connect chrome-cdp_default <컨테이너>` → `http://chrome-cdp:9223/fetch` |
| 순수 CDP 사용 | Playwright `connect_over_cdp("http://127.0.0.1:9222")`, 쿼리 `?fingerprint=<시드>`·`&timezone=`·`&locale=` 로 세션 지문 고정·영속 |
| MCP 연결 인자 | README.md:188-190 과 **동일** — 서버명 `chrome-devtools`, `npx -y chrome-devtools-mcp@latest --browserUrl http://127.0.0.1:9222` |
| 보안 | **9222 는 인증이 없다** — 반드시 `127.0.0.1` 바인딩 유지, 외부 노출 금지 |
| 금지 | 컨테이너 안에서 `cloakserve` 를 직접 실행하지 말 것 (엔트리포인트가 이미 관리) |

- **재사용**: 없음 — `grep -rn "insane\|9222\|browserUrl" adapters/` 조사 결과 기존 전역 스킬 3종
  (karpathy·orchestrate·orchestrate-onboard)에 브라우저 내용 없음(2026-08-11 실측).
  내용 소스는 **위 실측 표 + 킷 `README.md` 브라우저/MCP 절**.
- **install.sh 수정 불필요**: 전역 스킬은 `install.sh:1291-1296` 의 glob 루프
  (`for d in "$KIT_DIR"/adapters/claude/global/skills/*/`)가 디렉터리 단위로 복사한다 →
  **새 스킬 디렉터리를 추가하면 자동 배치된다. install.sh 를 건드리지 말 것.**
- **실패 테스트**: 불가 사유 — markdown 스킬 문서. 대체 검증: ① SKILL.md frontmatter
  (`name`·`description`) 형식 확인 ② 문서 내 모든 명령·포트가 위 실측 표와 일치하는지 대조
  ③ 임시 HOME 설치 리허설에서 `~/.claude/skills/insane-cloak-browser/SKILL.md` 배치 확인
  ④ 전체 unittest GREEN(회귀 없음).
- **필수 규칙**:
  - 다룰 것: ① 컨테이너 기동 확인법(`/health`) ② MCP 연결 시(chrome-devtools-mcp 툴 사용)
    ③ MCP 미연결 시(우회 fetch API·`insane-fetch` CLI·순수 CDP) ④ 언제 브라우저를 쓰지 말지
    (컨테이너 미기동 시 일반 fetch 폴백).
  - **위 표에 없는 명령·포트·플래그를 지어내지 말 것** — 미실측 항목은 서브모듈 README 참조로 위임.
  - **`git submodule update --init` 을 실행하지 말 것** — 서브모듈을 init 한 워크트리는
    phase-close 가 rc=128 로 크래시한다(PITFALLS). 필요한 사실은 위 표가 전부다.
  - 대상 파일 외 수정 금지 — 특히 `install.sh`·`tests/*.py` 는 건드리지 않는다.
  - 스킬 트리거 조건(`description`)을 명확히: 스텔스 브라우저·우회 fetch·CDP 가 필요한 작업.
  - codex 어댑터 대응물은 이번 스코프 제외 (후속 제안으로 기록).
  - 스크래치는 `.orchestrate/mut10/` — `/tmp` 등 저장소 밖 쓰기 금지(PITFALLS 8).
  - 공유 워크트리에서 `git stash` 금지, `git add` 경로 명시.
- **완료 조건**:
  1. 임시 HOME 설치 리허설에서 `~/.claude/skills/insane-cloak-browser/SKILL.md` 배치 확인
  2. `python3 -m unittest discover -s tests` 전부 GREEN
  3. 문서의 포트·명령이 실측 표와 1:1 일치함을 grep 출력으로 제시
