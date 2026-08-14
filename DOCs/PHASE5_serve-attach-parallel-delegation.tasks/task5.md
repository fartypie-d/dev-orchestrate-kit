# Task 5: 호스트 전파 (오케스트레이터 직접 — 키트 소스 아님)

- **실행 주체**: 오케스트레이터 (claude) — 호스트 설정·설치 작업, 위임 대상 아님
- **선행**: Task 1~4 검수 통과 + GATE 2 승인 + main 병합

## 체크리스트
1. `sudo loginctl enable-linger jh` (systemd user 버스 활성 — 실측: 현재 비활성)
2. `~/.config/opencode/serve.env` 생성 (chmod 600): `OPENCODE_SERVE_PORT=4096`,
   `OPENCODE_SERVER_PASSWORD=<생성>` — 값은 로그·보고에 절대 노출 금지
3. systemd user 유닛 `~/.config/systemd/user/opencode-serve.service`:
   `ExecStart=opencode-serve-ctl.sh` 경유 아닌 직접 serve 실행 + `EnvironmentFile=serve.env`,
   `Restart=on-failure`, `RestartSec=5` → enable --now → 헬스 확인
4. 프로젝트 4곳(usage-dashboard·insane-cloak·비공개 2곳) `scripts/`에
   `run-delegation.sh`·`opencode-serve-ctl.sh` 복사 (사본 실측 — 심링크 아님),
   각 저장소에 chore 커밋 (push는 별도 승인)
5. `~/.claude/skills/orchestrate/SKILL.md` ← adapters 판 설치 (키트 install 경로 사용)
6. 실증: 서로 다른 두 프로젝트에서 동시 위임 → 겹침 확인 + LOCK_WAIT 부재 확인
7. 429/MODEL_FALLBACK 빈도 모니터링 안내를 완료 보고에 포함
