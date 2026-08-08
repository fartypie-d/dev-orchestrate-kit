#!/usr/bin/env bash
# phase 번호 발급 + 워크트리 생성 — 구현은 phase-tools.py claim
exec python3 "$(dirname "${BASH_SOURCE[0]}")/phase-tools.py" claim "$@"
