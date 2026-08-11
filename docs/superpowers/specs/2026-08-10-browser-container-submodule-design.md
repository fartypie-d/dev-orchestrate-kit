# 브라우저 컨테이너 서브모듈 분리 — 설계

- 날짜: 2026-08-10
- 상태: 승인됨 (사용자 확정)

## 목표

`containers/browser/` 를 별도 공개 저장소 `github.com/fartypie-d/insane-cloak` 로
분리하고, dev-orchestrate-kit 에서는 git 서브모듈로 참조한다. 동시에 더 이상 이 키트에
포함하지 않기로 한 `containers/antigravity/` 컨테이너를 제거한다.

## 확정 결정

- **새 저장소**: `github.com/fartypie-d/insane-cloak` — public, MIT, 스쿼시 fresh-start
  단일 커밋. usage-dashboard 와 동일한 "공개 단일 저장소" 패턴(프라이빗 개발 쌍 없음).
- **서브모듈 경로/URL**: `containers/browser` → `https://github.com/fartypie-d/insane-cloak.git`
  (usage-dashboard 와 같은 https·공개 URL). usage-dashboard 는 공개 브랜치에만 존재하지만
  browser 는 현재 디렉터리로 추적 중이므로 현재 개발 브랜치에서 바로 서브모듈로 전환한다.
- **antigravity 컨테이너**: `containers/antigravity/` 삭제. 컨테이너 레벨 참조 정리.
- **antigravity 프로바이더(옵션 B)**: 위임 프로바이더 자산(`profiles/antigravity.json`,
  `provider-models.json`, `run-delegation.sh` 분기, `secrets.env.example`,
  `install.sh --providers=antigravity`)은 **유지**한다. 단 프록시(:8045)를 더 이상
  번들하지 않으므로, 프로바이더를 쓰려면 사용자가 OpenAI 호환 :8045 엔드포인트를 **직접
  준비**해야 한다고 문서(PORTING.md)에 명시한다.

## 새 저장소 콘텐츠

현재 git 추적 중인 16개 파일 그대로 이관한다. vendored 엔진(`insane-api/vendor/engine/`)은
지금처럼 gitignore 유지 — `sync-vendor.sh` 가 업스트림(fivetaku/insane-search, MIT
핀 커밋)에서 가져온다. 추가:

- 루트 `LICENSE` (MIT) — 표준 OSS 배포용.
- 클린 `README.md` — 키트-내부 결합 문구(개발 호스트 원본, 키트 상대 경로)를 걷어내고
  독립 사용 + 서브모듈 사용을 함께 안내. 기술 내용(설치·보안·CLI/HTTP/CDP·동작 원리·
  레이아웃·크레딧)은 보존.

## 키트 변경

- `git rm -r containers/browser` → `git submodule add … containers/browser` (포인터 고정).
- `.gitmodules` 항목 추가.
- `containers/antigravity/` 삭제, 참조 정리:
  - `.gitignore`: `containers/antigravity/data/` 제거
  - `install.sh`: `--containers=browser,antigravity` → `--containers=browser` (usage·주석)
  - `README.md`: containers 표 행에서 antigravity 프록시 제거
  - `AGENTS.md`, `CLAUDE.md`: 레이아웃 설명에서 antigravity 프록시 제거
  - `docs/PORTING.md`: antigravity 프록시 절을 옵션 B(직접 준비)로 재작성
  - `tests/test_install_args.py`: 컨테이너 CSV 테스트를 `browser` 로 갱신

## 검증

```bash
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh
python3 -m unittest discover -s tests -v
bash scripts/hook-selfcheck.sh
git submodule status
```
