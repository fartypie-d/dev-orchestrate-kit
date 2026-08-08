#!/usr/bin/env bash
# SessionStart 재니터 — 구현은 phase-tools.py janitor (항상 exit 0)
exec python3 "$(dirname "${BASH_SOURCE[0]}")/phase-tools.py" janitor
