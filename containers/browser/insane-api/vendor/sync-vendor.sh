#!/usr/bin/env bash
# vendor/engine 를 핀 고정된 업스트림 insane-search 커밋에서 내려받는다.
#
# 왜 커밋에 vendored 하지 않는가:
#   engine/ 은 업스트림(fivetaku/insane-search, MIT)의 무수정 트리다. 이 키트는
#   이를 재배포하는 대신 출처(UPSTREAM_COMMIT.txt)만 핀으로 박고, 빌드 전에 정확히
#   그 커밋을 가져온다. 출처가 명확하고, 업스트림 갱신이 한 줄로 끝난다.
#
# 사용법: bash vendor/sync-vendor.sh      (containers/browser/insane-api 기준)
# 그다음:  docker compose build && docker compose up -d
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PIN_FILE="$HERE/UPSTREAM_COMMIT.txt"

command -v git >/dev/null 2>&1 || { echo "git 이 필요하다" >&2; exit 69; }
[ -f "$PIN_FILE" ] || { echo "핀 파일 없음: $PIN_FILE" >&2; exit 66; }

COMMIT="$(sed -n '1p' "$PIN_FILE")"
REPO="$(sed -n '2p' "$PIN_FILE")"
[ -n "$COMMIT" ] && [ -n "$REPO" ] || { echo "핀 파일 형식 오류 (1줄=커밋, 2줄=repo URL): $PIN_FILE" >&2; exit 65; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "clone $REPO @ $COMMIT ..."
git clone --quiet "$REPO" "$TMP/is"
git -C "$TMP/is" checkout --quiet "$COMMIT"

SRC="$TMP/is/skills/insane-search/engine"
[ -d "$SRC" ] || { echo "업스트림 레이아웃이 바뀌었다 — engine 경로 없음: $SRC" >&2; exit 70; }

rm -rf "$HERE/engine"
cp -r "$SRC" "$HERE/engine"
rm -rf "$HERE/engine/tests"

echo "동기화 완료: $HERE/engine (업스트림 $COMMIT)"
echo "다음: docker compose build && docker compose up -d"
