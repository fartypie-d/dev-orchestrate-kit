# 전역 ~/.claude/settings.json 토큰 절약 env

**install.sh 5단계가 자동 병합한다** (키가 이미 있으면 사용자 값 우선·스킵, 백업 생성).
이 문서는 값의 근거 참조용이다.

```json
{
  "env": {
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75"
  }
}
```

- `CLAUDE_CODE_SUBAGENT_MODEL`은 **설정하지 말 것** — 에이전트 frontmatter·명시적 model
  파라미터까지 전부 덮어써서 리뷰어가 의도치 않은 모델로 돈다 (2026-07-29 실측 사고).
- 프로젝트 단위 env는 project-template의 `.claude/settings.json`에 이미 들어 있다.
