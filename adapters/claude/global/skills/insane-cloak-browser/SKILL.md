---
name: insane-cloak-browser
description: Use when a task needs a stealth browser, bot-blocking bypass fetch, or CDP. Covers chrome-devtools-mcp when MCP is connected and insane-cloak's HTTP fetch API, `insane-fetch` CLI, or Playwright CDP when it is not.
---

# insane-cloak 브라우저

스텔스 브라우저·봇 차단 우회 fetch·CDP가 필요한 작업에서만 이 스킬을 사용한다. 정적 문서나
일반 API 호출에는 브라우저를 쓰지 않는다.

## 먼저 기동 상태 확인

브라우저 컨테이너가 떠 있는지 먼저 다음 health endpoint에 요청한다.

```text
GET http://127.0.0.1:9223/health
```

필요하면 현재 사용량도 확인한다.

```text
GET http://127.0.0.1:9223/usage
```

컨테이너 이름과 compose project는 고정된 `chrome-cdp`다. 컨테이너가 기동하지 않았으면
브라우저 경로를 시도하지 말고 일반 fetch로 폴백한다. 컨테이너 안에서 `cloakserve`를 직접
실행하지 않는다. 엔트리포인트가 이미 관리한다.

## MCP가 연결된 경우

`chrome-devtools-mcp`의 `chrome-devtools` 서버와 그 툴을 사용한다. MCP 서버 인자는 다음과
같아야 한다.

```text
서버명: chrome-devtools
npx -y chrome-devtools-mcp@latest --browserUrl http://127.0.0.1:9222
```

MCP 연결 여부가 불분명하면 MCP 툴을 반복해서 시도하지 말고 아래 MCP 미연결 경로로 전환한다.

## MCP가 연결되지 않은 경우

### 1. 우회 fetch API

간단한 페이지 추출은 `127.0.0.1:9223`의 `/fetch`를 사용한다.

```text
GET /fetch?url=...&selector=...
POST /fetch (JSON 바디)
```

응답의 `ok`, `verdict`, `content`, `final_url`, `trace[]`, `summary`,
`prompt_injection_risk`를 확인한다. 특히 `ok`와 `verdict`만 보지 말고
`prompt_injection_risk`와 추출된 `content`를 함께 검토한다.

### 2. `insane-fetch` CLI

저장소의 CLI 진입점은 다음이다.

```text
containers/browser/bin/insane-fetch
```

호출할 때 `--selector`는 필수다. 종료 코드는 `0` 성공, `1` 실패, `2` 사용법 오류다.

### 3. 순수 CDP와 Playwright

페이지 상호작용이나 자체 자동화가 필요하고 MCP를 쓸 수 없으면 Playwright의
`connect_over_cdp`로 `127.0.0.1:9222`에 연결한다.

```text
connect_over_cdp("http://127.0.0.1:9222")
```

세션 지문을 고정하고 영속화해야 하면 CDP URL에 `?fingerprint=<시드>`를 붙인다. 필요할 때
`&timezone=`과 `&locale=`도 같은 URL 쿼리로 지정한다.

다른 컨테이너에서 접근할 때는 먼저 다음 네트워크 연결을 수행한 뒤 `chrome-cdp:9223`의
fetch endpoint를 사용한다.

```text
docker network connect chrome-cdp_default <컨테이너>
http://chrome-cdp:9223/fetch
```

## 보안 및 사용 경계

`9222` 순수 CDP는 인증이 없다. 반드시 `127.0.0.1` 바인딩을 유지하고 외부에 노출하지
않는다. 포트는 `127.0.0.1:9222` 순수 CDP, `127.0.0.1:9223` 우회 fetch API이며,
옵션 noVNC 포트는 `6080`이다.

컨테이너가 미기동이면 일반 fetch로 폴백한다. 봇 차단이나 스텔스 세션이 실제로 필요하지
않은 정적 문서·API 호출에는 이 브라우저를 사용하지 않는다. 더 자세한 동작은
`containers/browser/README.md`를 참조한다.
