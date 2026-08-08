#!/usr/bin/env bash
# 페이즈 마감 원샷 정리 — 구현은 phase-tools.py close
exec python3 "$(dirname "${BASH_SOURCE[0]}")/phase-tools.py" close "$@"
