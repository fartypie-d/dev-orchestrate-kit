# 컨테이너 브라우저 툴 레이어 + 하네스 무관 스킬 — 설계

> **⚠️ 대체됨 (SUPERSEDED, 2026-08-11).** rev1 이후 chrome-devtools-mcp attach 방식이 도입돼
> 이 문서의 Phase 1 상호작용/캡처 표면 대부분이 이미 커버됐다. 스코프를 좁힌 **개정판 rev2**가
> 구현의 단일 소스다: insane-cloak `docs/specs/2026-08-11-browser-tool-layer-design-rev2.md`
> (https://github.com/fartypie-d/insane-cloak/blob/main/docs/specs/2026-08-11-browser-tool-layer-design-rev2.md).
> 이 문서는 설계 이력으로만 보존한다. 키트 쪽 후속(스킬 어댑터·온보딩 등록)은 rev2의
> "키트 쪽 후속" 절 참조.

- 날짜: 2026-08-10
- 상태: **대체됨 — rev2로 이관** (원래 상태: 설계 승인 대기)
- 관련: [insane-cloak](https://github.com/fartypie-d/insane-cloak) 컨테이너, [2026-08-10-browser-container-submodule-design](./2026-08-10-browser-container-submodule-design.md)

## 목표

어떤 CLI 에이전트 도구(**claude · codex · opencode · hermes · openclaw**)를 쓰든, 이
스텔스 브라우저 컨테이너를 띄워 **브라우저 조작 툴**로 활용할 수 있게 한다. CloakBrowser 가
지원하는 항목(지문·humanize·세션·캡처 등)을 컨테이너 밖으로 노출하고, 에이전트가 바로 쓸 수
있는 **전용 스킬**을 키트에 포함한다.

핵심 통찰: CloakBrowser 스텔스 지문은 이미 cloakserve(:9222) Chromium 프로세스에 컴파일되어
있다. 부족한 것은 (1) humanize·screenshot 등 클라이언트측 기능의 노출, (2) 여러 명령에 걸친
**세션 상태 유지**, (3) 하네스 무관 호출 표면이다.

## 확정 결정 (사용자)

- **인터페이스: HTTP 코어 + 얇은 CLI·MCP 래퍼.** 기존 `insane-api`(:9223, stdlib HTTP)를
  브라우저 제어 엔드포인트로 확장해 **단일 소스**로 삼는다. `browser` CLI 와 MCP 서버는 둘 다
  그 HTTP 를 감싸는 얇은 래퍼다. (사용자가 고른 "CLI 단일 소스 + MCP 래퍼"를 HTTP 코어로 한
  단계 밀어 원격·타 컨테이너·상태 유지를 공짜로 얻는다.)
- **대상 하네스:** claude(스킬+bash), codex(prompt+bash), opencode(에이전트+MCP/bash),
  hermes·openclaw(bash CLI). 전부 bash 실행이 공통분모이므로 CLI 가 보편 경로, MCP 는
  지원 하네스용 네이티브 표면.
- **저장소 2곳:** 툴 레이어(HTTP·CLI·MCP)는 **insane-cloak**, 스킬·온보딩 등록은 **키트**.
- **베이스 이미지 업그레이드 포함:** `cloakhq/cloakbrowser:0.4.13` → `0.5.6` (Phase 0).

## 아키텍처

```
에이전트 (claude · codex · opencode · hermes · openclaw)
   │  bash: browser <verb> …            │  MCP: browser.* 툴 (claude·opencode)
   ▼                                    ▼
 browser CLI (curl 래퍼)          MCP stdio 서버 (python, stdlib+mcp)
   └──────────────┬─────────────────────┘
                  ▼  HTTP  127.0.0.1:9223  (원격=SSH 터널 · 타 컨테이너=network alias)
        insane-api / server.py  ── 단일 소스, 세션 상태 보유
                  │  CDP  127.0.0.1:9222
                  ▼
        cloakserve — 스텔스 Chromium (fingerprint seed별 프로세스)
```

- **세션 모델(채택):** 서버가 세션 id → 살아있는 Playwright page/context(= cloakserve
  fingerprint seed)를 보유한다. `click → type → shot` 이 여러 HTTP/CLI 호출에 걸쳐 같은
  페이지를 조작한다. 유휴 세션은 리퍼가 닫는다(cloakserve idle-timeout 과 정렬).
  - *대안(기각):* 매 명령이 `docker exec` 로 컨테이너 내부 Python 실행 — 원격·타 컨테이너에서
    불리하고 docker 소켓 접근을 강요한다.
- **구현 유의(서버 동시성):** 기존 `/fetch` 는 요청당 엔진을 돌린다. 장수 page 를 요청 간
  유지하려면 서버 프로세스에 **전용 Playwright 드라이버(스레드 또는 asyncio 루프 + 명령 큐)**가
  필요하다. stdlib HTTP 서버는 요청을 이 드라이버에 위임하고 결과만 반환한다. 이 경계가
  Phase 1 의 가장 큰 구현 리스크다.

## Phase 0 — 베이스 이미지 0.4.13 → 0.5.6 + 동작 재검증

0.4.13 은 "테스트한 그 버전" 재현성 핀이다(명시적 이유 주석 없음, 근거는
`patches/playwright_real_chrome.js` 의 *"Measured against cloakserve 0.4.13"*). 현재 Docker
Hub 최신은 `0.5.6`. 툴 레이어를 새로 짜는 김에 최신으로 맞추되, 아래를 **실측 재검증**한다:

- [ ] `FROM cloakhq/cloakbrowser:0.5.6` 로 변경, 이미지 빌드·기동.
- [ ] CDP 동작: 연결당 새 Chrome 프로세스 여부, `browser.close()` 격리, 끊었을 때 쿠키 수명
      — `cloak_executor.py`·`patches/playwright_real_chrome.js` 주석의 가정이 유지되는지.
- [ ] `?fingerprint=` seed 프로세스 재사용·프로필 지속(`--data-dir`)·idle 회수.
- [ ] humanize preset 이름(`default`/`careful`)·`human_config` 파라미터
      (`mistype_chance`·`typing_delay`·`idle_between_*`) 유효성.
- [ ] 스텔스 회귀: `navigator.webdriver`·`cdc_` 흔적·UA/GPU 위장·JA3 (기존 실측 기준 대비).
- [ ] 엔진 파이프라인 회귀: `insane-fetch` verdict 5종이 0.4.13 과 동등.
- 검증이 깨지면 해당 가정을 코드/주석에 갱신하거나 핀을 되돌린다(핀 되돌림도 정상 결과).

## Phase 1 — 브라우저 제어 (코어 동작)

CloakBrowser/Playwright 근거의 최소 실용 집합. HTTP 엔드포인트 · CLI verb · MCP 툴이 1:1 대응.

| 그룹 | CLI (예) | HTTP | 비고 |
|---|---|---|---|
| 세션·정체성 | `browser new --fp N --timezone TZ --locale L --platform OS --proxy URL --geoip` | `POST /session` → `{sid}` | cloakserve 쿼리파라미터로 전달 |
| | `browser end <sid>` · `browser list` | `DELETE /session/<sid>` · `GET /sessions` | |
| 내비게이션 | `browser goto <sid> <url> --wait load\|networkidle\|<sel>` | `POST /session/<sid>/goto` | |
| | `browser back\|reload <sid>` | `POST /session/<sid>/nav` | |
| 상호작용 | `browser click\|hover <sid> <sel> [--human]` | `POST /session/<sid>/click` | `--human` = humanize preset/config |
| | `browser type <sid> <sel> <text> [--human] [--enter]` | `POST /session/<sid>/type` | |
| | `browser fill\|select <sid> <sel> <val>` · `browser press <sid> <key>` | `POST …/fill` `…/press` | |
| | `browser scroll <sid> [--to sel\|--by N] [--human]` | `POST …/scroll` | |
| 추출 | `browser text\|html <sid> [sel]` · `browser attr <sid> <sel> <name>` | `GET …/text?selector=` 등 | |
| | `browser eval <sid> '<js>'` · `browser url\|title <sid>` | `POST …/eval` · `GET …/url` | |
| 캡처 | `browser shot <sid> [--out f\|--full\|--selector s]` | `POST …/shot` → base64/파일 | Playwright `page.screenshot` |
| | `browser pdf <sid> [--out f]` | `POST …/pdf` | |
| 세션 지속 | `browser cookies <sid> [--export f\|--import f]` | `GET/POST …/cookies` | seed 프로필 재사용 |
| 기존 유지 | `insane-fetch <url> -s <sel>` · `/fetch` · `/usage` · `/health` | 변경 없음 | 원샷 스텔스 fetch |

- **humanize:** `--human` 은 서버가 `patch_browser`/`humanizeBrowser` + preset 을 적용. 기본
  비활성(속도), 옵트인. 프리셋·파라미터는 요청 필드로도 override.
- **출력 규약:** 기본 JSON(`{ok, sid, …}`), `--json`/plain 선택. 종료코드는 `insane-fetch`
  관례 계승(0 성공 / 1 실패 / 2 사용오류).
- **CLI 접근점:** `BROWSER_API`(기본 `http://127.0.0.1:9223`) 로 원격/타 컨테이너 대상 지정.

## Phase 2 — 선택 (후속)

- `browser console <sid>` · `browser network <sid>` — 캡처된 콘솔/요청 로그.
- 확장 로딩(`extension_paths`), proxy 프로파일, `browser wait <sid> <sel>` 명시 대기.
- MCP 리소스로 스크린샷/텍스트 노출(툴 반환 외).

## 전용 스킬 — 하네스 무관 단일 소스 + 어댑터 배포

키트의 기존 패턴(`core/onboard/ONBOARD-PROCEDURE.md` 단일 소스 → 하네스 스킬이 참조)을 따른다.

- **단일 소스:** `core/browser/BROWSER-TOOLS.md` — 컨테이너 기동 확인 → 없으면
  `docker compose up` 안내 → `browser` verb 사용법 → **안전 경계**(아래) → 예시 흐름
  (로그인 폼·스크래핑·스크린샷). install.sh 가 `~/.config/orchestrate/BROWSER-TOOLS.md` 로
  설치.
- **얇은 래퍼(하네스별):**
  - `adapters/claude/global/skills/browser-tools/SKILL.md` → `~/.claude/skills/browser-tools`
  - `adapters/codex/global/prompts/browser-tools.md` → `~/.codex/prompts/`
  - opencode·hermes·openclaw: 단일 소스 본문이 `browser` CLI 를 그대로 안내(별도 배포 불필요).
- **온보딩 등록:** `/orchestrate-onboard` 가 프로젝트 로스터/문서에 "브라우저 툴 사용 가능"을
  기록하도록 `core/onboard/ONBOARD-PROCEDURE.md` 에 한 줄 추가.

## 안전 경계 (스킬·문서에 명시)

- **CDP 무인증 · 127.0.0.1 전용.** :9222/:9223 을 `0.0.0.0`·tailnet·터널에 노출 금지. 원격은
  SSH 포트포워딩만.
- **SSRF 가드 유지.** private·loopback·클라우드 메타데이터 대상은 `403 blocked target`; 요청
  파라미터로 끌 수 없다. 브라우저 실행기 경로에도 API 경계 검사가 있어야 한다(기존 이중 검사
  유지).
- **가져온 콘텐츠는 신뢰 불가.** LLM 에 넣을 땐 `--wrap`(비신뢰 봉투 + `prompt_injection_risk`).
- **MCP 노출 주의.** MCP 서버는 로컬 stdio 만; 원격 노출 금지. 세션 남용 방지로 최대 세션 수·
  idle 리퍼 상한을 둔다.
- **로그인/페이월.** 인증 우회 시도 금지 — 벽을 만나면 "authentication required" 보고.

## 저장소별 변경 목록

**insane-cloak (컨테이너):**
- `insane-api/Dockerfile`: 베이스 `0.5.6`.
- `insane-api/server.py`: 세션 보유 브라우저 제어 엔드포인트(+ Playwright 드라이버 스레드).
- `insane-api/session.py`(신규): 세션 레지스트리·idle 리퍼.
- `bin/browser`(신규): CLI 래퍼.
- `mcp/`(신규): stdio MCP 서버 + 등록 예시(.mcp.json / opencode).
- `README.md`: 툴 레이어·세션·MCP 절 추가.
- Phase 0 재검증 결과를 README/주석에 반영.

**dev-orchestrate-kit (키트):**
- `core/browser/BROWSER-TOOLS.md`(신규): 스킬 단일 소스.
- `adapters/claude/global/skills/browser-tools/SKILL.md`(신규).
- `adapters/codex/global/prompts/browser-tools.md`(신규).
- `install.sh`: BROWSER-TOOLS.md 설치 + 스킬/프롬프트 배포(기존 루프에 편입).
- `core/onboard/ONBOARD-PROCEDURE.md`: 브라우저 툴 등록 한 줄.
- 서브모듈 포인터: insane-cloak 갱신분 반영.

## 검증 계획

- **컨테이너:** Phase 0 체크리스트 + 각 verb 스모크(goto→text/shot, click/type --human, cookies
  export/import, 세션 idle 회수). 스텔스 회귀(webdriver/cdc_/JA3).
- **CLI:** 종료코드·JSON 스키마 단위 테스트(모의 HTTP).
- **키트:** `python3 -m unittest discover -s tests`,
  `bash -n install.sh …`, `bash scripts/hook-selfcheck.sh`, 스킬 설치 멱등성.
- **하네스 실사용:** claude(MCP+bash)·codex(bash)·opencode(bash) 각 1회 로그인 폼 흐름.

## 리스크 · 오픈 이슈

- **서버 동시성/드라이버 스레드**가 최대 난점 — Playwright sync API + stdlib HTTP 결합. asyncio
  단일 루프로 재작성할지, 스레드+큐로 갈지 구현 초기에 스파이크로 결정.
- **0.5.6 동작 변화** — Phase 0 재검증에서 가정이 깨지면 코드 갱신 또는 핀 되돌림.
- **MCP SDK 의존성** — 컨테이너 이미지에 추가 시 크기·콜드스타트 영향. stdio MCP 는 호스트에서
  돌리고 컨테이너는 HTTP 만 노출하는 방안 우선 검토.
- **세션 누수** — 리퍼 상한·최대 세션 수 필수(기존 2주 86프로세스/8.4GB 실측 교훈).

## 구현 경로

CLAUDE.md 상 소스 변경은 위임 대상이다. 이 문서는 설계 스펙까지다. 승인 후:
`/orchestrate` 로 페이즈를 열어 insane-cloak(컨테이너) · 키트(스킬) 두 트랙으로 task 분할,
Phase 0 재검증을 첫 task 로 배치한다.
