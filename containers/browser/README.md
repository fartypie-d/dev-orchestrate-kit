# 공용 스텔스 브라우저 + 우회 fetch 서비스

> **오케스트레이션 없이 이것만 써도 된다.** 이 컨테이너는 dev-orchestrate-kit 의
> 나머지(claude·opencode 위임 워크플로우)와 완전히 독립적이다. 키트를 설치하지 않아도
> 이 디렉터리에서 바로 `docker compose up -d` 하면 헤드리스 서버에서 브라우저를 쓸 수
> 있다 — Claude Code, X 디스플레이, GPU, per-user Chrome 설치가 전부 불필요하다.

> **이 사본의 원본은 개발 호스트다.** dev-orchestrate-kit 에 번들된 복사본이며, 개선은
> 호스트(`/opt/chrome-cdp`)에서 먼저 하고 키트에 반영한 뒤 push 한다. 반대 방향으로
> 키트를 먼저 고치면 호스트와 어긋난다.

한 컨테이너가 두 포트를 서빙한다. **어떤 사용자·도구든** 쓸 수 있고, 브라우저는
컨테이너 자체 Xvfb 위에서 **헤디드로** 돈다(헤드리스 아님 — 안티봇 시스템이 헤디드를
요구하기 때문).

| 포트 (localhost 전용) | 내용 |
|---|---|
| `127.0.0.1:9222` | CloakBrowser 스텔스 Chromium, 헤디드, raw CDP |
| `127.0.0.1:9223` | insane-search 우회 파이프라인의 HTTP 서비스 |

## 설치

```bash
cd containers/browser
bash insane-api/vendor/sync-vendor.sh    # 업스트림 MIT 엔진을 핀 커밋에서 가져온다 (빌드 전 1회)
docker compose up -d
docker compose ps
```

`insane-fetch` CLI 를 PATH 에 두려면 (선택):

```bash
sudo ln -sf "$PWD/bin/insane-fetch" /usr/local/bin/insane-fetch
```

> `vendor/engine/` 은 커밋에 포함하지 않는다 — `sync-vendor.sh` 가 업스트림
> [insane-search](https://github.com/fivetaku/insane-search)(MIT)의 핀 고정 커밋
> (`insane-api/vendor/UPSTREAM_COMMIT.txt`)에서 가져온다. 출처가 명확하고 업스트림
> 갱신이 한 줄로 끝난다.

## 화면 보기 (선택 — noVNC 오버레이)

Chrome 이 헤디드로 돌지만 평소엔 화면이 필요 없다(CDP 로 제어). 디버깅·수동 로그인·
CAPTCHA 확인이 필요하면 noVNC 오버레이로 실제 화면을 브라우저에서 볼 수 있다:

```bash
docker compose -f docker-compose.yml -f docker-compose.novnc.yml up -d
# http://127.0.0.1:6080/vnc.html  (원격 서버면 SSH 포트포워딩)
```

noVNC 포트도 127.0.0.1 전용이다 — 화면에 로그인 세션이 그대로 보이므로 LAN 에 열지 말 것.
기본은 뷰어 전용이며, 수동 제어가 필요하면 `novnc/start-novnc.sh` 의 `x11vnc` 에서
`-viewonly` 를 빼면 된다.

## 보안 — 무엇이든 바꾸기 전에 읽을 것

**CDP 는 인증이 없다.** 포트 9222 에 닿을 수 있는 사람은 로컬 파일을 읽고, 임의
JavaScript 를 실행하고, 이 호스트를 경유해 요청을 보낼 수 있다. 그래서 두 포트 모두
`127.0.0.1` 에만 게시한다. 이 바인딩을 `0.0.0.0` 으로 바꾸거나 tailnet·터널 뒤에 두지
말 것 — 공용 개발 서버가 원격 코드 실행 대상이 된다.

`insane-api` 는 private·loopback·link-local·클라우드 메타데이터 대상을
`403 blocked target` 으로 거부하며, 이는 의도적으로 요청 파라미터로 노출하지 **않는다**.

`vendor/` 재동기화 시 주의: 업스트림은 SSRF 가드를 curl 트랜스포트(`transport.py`)
안에서만 강제한다. 브라우저 실행기는 넘겨받은 URL 을 그대로 navigate 한다 — 실측:
`169.254.169.254` 요청이 빈 본문을 반환했지만 실제 Chrome 창은 이미 그 주소로 열려
있었다. 그래서 검사를 API 경계(`server.py`)에 두고, `cloak_executor.py` 에 두 번째를
둔다. 그 코드를 건드리면 둘 다 유지할 것.

가져온 페이지 콘텐츠는 공격자가 제어할 수 있다. LLM 에 넣을 때는 `--wrap` / `"wrap": true`
를 쓰면 엔진의 신뢰불가-콘텐츠 봉투와 `prompt_injection_risk` 판정을 함께 받는다.

## 1. `insane-fetch` — 쉬운 경로

```bash
insane-fetch https://example.com/article -s 'article'      # 콘텐츠를 stdout 으로
insane-fetch https://spa.example/page -s '.content' --trace # + 시도 로그를 stderr 로
insane-fetch https://example.com --json | jq .verdict
insane-fetch https://example.com -s h1 --wrap              # LLM-안전 봉투
```

`--selector` 를 넘겨라. 엔진이 실제 페이지와 챌린지 페이지를 구분하는 방법이다 — 없으면
WAF 인터스티셜이 성공으로 보고될 수 있다.

종료 코드: `0` 성공, `1` 모든 경로 실패, `2` 사용법/트랜스포트 오류.

## 2. HTTP API — 스크립트·에이전트용

```bash
curl -s 'http://127.0.0.1:9223/fetch?url=https://example.com&selector=h1' | jq .

curl -s -X POST http://127.0.0.1:9223/fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","selectors":["h1"],"device":"mobile"}' | jq .
```

`GET /usage` 가 모든 필드를 나열한다. `GET /health` 는 liveness 프로브다.

응답: `ok`, `verdict`(`strong_ok` | `weak_ok` | `challenge` | ...), `content`,
`final_url`, `trace[]`(각 시도의 실행기·판정), `summary`, `prompt_injection_risk` 등.

다른 컨테이너에서는 네트워크에 합류해 서비스 이름으로 부른다:

```bash
docker network connect browser_default <your-container>
# 이후: http://chrome-cdp:9223/fetch  (http://insane-api:9223 도 별칭으로 해석된다)
```

## 3. Raw CDP — 자체 자동화

어떤 Playwright/Puppeteer 클라이언트든 공용 브라우저를 구동할 수 있다:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()
    page.goto("https://example.com")
```

`cloakserve` 는 fingerprint 로 멀티플렉싱한다: `http://127.0.0.1:9222?fingerprint=123`
은 다른 호출자와 격리된 브라우저 정체성을 준다. `&timezone=`·`&locale=` 도 받는다.

### 세션은 fingerprint seed 단위로 유지된다

각 seed 는 전용 Chrome 프로세스와 `--user-data-dir` 을 받고 그 프로세스가 연결 간에
**재사용**된다. 실측: 한 seed 로 쿠키·localStorage 를 쓰고 끊었다가 같은 seed 로
재접속하면 둘 다 남아 있다. 다른 seed 로 붙으면 둘 다 없다. 즉 seed 아래의 로그인은
접속을 끊어도 살아남는다.

수명 한계는 `CLOAKSERVE_IDLE_TIMEOUT`(`docker-compose.yml` 에서 1800초). seed 가 그만큼
유휴이면 Chrome 이 회수되고 프로필 디렉터리가 **삭제**된다 — 세션이 사라진다. 컨테이너
재시작 때도 사라진다. 더 오래 유지해야 하면 쿠키를 밖으로 내보내 `context.add_cookies()`
로 복원할 것.

기본값(`0`, 비활성)이 더 나쁘다: 아무것도 회수되지 않는다. 실측: 2주 가동에 Chrome
프로세스 86개·8.4GB.

### 인간형 상호작용도 CDP 로 동작한다

CloakBrowser 의 인간화는 Playwright 객체의 클라이언트측 패치라, `launch(humanize=True)`
를 CDP 연결에서 두 줄로 재현할 수 있다:

```python
from cloakbrowser.human import resolve_config, patch_browser
browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222?fingerprint=123")
patch_browser(browser, resolve_config("default", None))   # launch() 가 내부에서 하는 일
```

이후 `page.click()`·`page.type()` 은 인간형 구현을 탄다. 실측: 클릭 1회에 곡선 경로를
따르는 mousemove 285개, 정중앙 아닌 착지, `isTrusted: true`, 타이핑 간격 63–142ms.

### 컨테이너 안에서 `cloakserve` 를 직접 실행하지 말 것

`--help` 가 없어 어떤 호출이든 두 번째 서버를 띄우려다 바인딩 실패하고
`All Chrome processes terminated` 를 남기며 죽는다. `/usr/local/bin/cloakserve` 소스를 읽을 것.

## 동작 원리

`insane-api` 는 업스트림의 에스컬레이션 파이프라인을 무수정으로 돌린다:

```
Phase 0  플랫폼별 공개 엔드포인트 (yt-dlp, 공식 API)
Phase 1  경량 프로브 — RSS/AMP/mobile/JSON 변형
Phase 2  curl_cffi TLS 위장 (실제 브라우저의 JA3 지문)
Phase 3  실제 헤디드 브라우저  ← 이 컨테이너의 cloakserve 로 CDP 라우팅
```

Phase 3 만 브라우저 비용이 든다. 대부분은 그 전에 끝난다.

**trace 의 `playwright_real_chrome` 는 평범한 Chrome 이 아니다.** 업스트림 실행기
*이름*이며 vendored 엔진이 이 문자열로 분기하므로 그대로 둔다. 실제로는
`cloak_executor.run_via_cdp` 가 스텔스 Chromium 에 붙는다 — 실측: `navigator.webdriver`
false, 리눅스 호스트에 윈도우 UA·D3D11 GPU 위장, `cdc_` 흔적 없음.

로그인 벽·페이월에서는 멈추고 "authentication required" 를 보고한다 — 인증을 뚫으려
시도하지 않는다.

## 레이아웃

```
docker-compose.yml          단일 서비스 (두 포트)
docker-compose.novnc.yml    선택적 화면 뷰어 오버레이
bin/insane-fetch            CLI
novnc/                      noVNC 사이드카 (Dockerfile + start-novnc.sh)
insane-api/                 빌드 컨텍스트
  Dockerfile                베이스 이미지 + 엔진 의존성 + 두 역할
  start-both.sh             cloakserve 와 API 를 띄우고, 하나가 죽으면 컨테이너를 내린다
  server.py                 stdlib HTTP 프런트엔드
  cloak_executor.py         CDP 실행기 (업스트림 JS 템플릿과 같은 JSON 봉투를 낸다)
  cdp_bridge.py             임포트 시점 몽키패치 — 엔진을 CDP 로 돌린다
  vendor/                   업스트림 MIT 엔진 (sync-vendor.sh 가 가져온다)
    LICENSE                 업스트림 MIT 라이선스
    UPSTREAM_COMMIT.txt     핀 고정 커밋
    sync-vendor.sh          핀 커밋에서 engine/ 을 가져온다
patches/                    insane-search 플러그인을 직접 쓰는 사람용 CDP 인식 Node 템플릿
```

## 크레딧

우회 엔진: [insane-search](https://github.com/fivetaku/insane-search) by fivetaku,
MIT (`insane-api/vendor/LICENSE`). 브라우저:
[CloakBrowser](https://github.com/CloakHQ/CloakBrowser) — MIT 래퍼. 고정된 Chromium
v146 바이너리는 자유 재배포 빌드라 구독이 필요 없다.
