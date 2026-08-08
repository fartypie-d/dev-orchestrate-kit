#!/usr/bin/env python3
"""세션 비용 집계 — ~/.claude/projects/<cwd 슬러그>/*.jsonl 의 usage 합산.

사용: python3 scripts/session-cost.py [session-id]
  인자 없음: 오늘(mtime) 수정된 세션 전부 / session-id: 해당 세션만.
단가 미등록 모델은 토큰만 출력하고 비용은 '?' (추정하지 않는다 — ECC 교훈:
자동 기록은 원자료까지만 신뢰).
"""
import json
import sys
import time
from pathlib import Path

# USD per 1M tokens: (input, output, cache_write(1.25x), cache_read(0.1x))
# 출처: claude-api 스킬 단가표 2026-07-28. 미등록 모델은 추정하지 말고 표에 추가할 것.
PRICES = {
    "claude-opus-5": (5.0, 25.0, 6.25, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 6.25, 0.50),
    "claude-sonnet-5": (3.0, 15.0, 3.75, 0.30),
    "claude-haiku-4-5": (1.0, 5.0, 1.25, 0.10),
    "claude-haiku-4-5-20251001": (1.0, 5.0, 1.25, 0.10),
    "claude-fable-5": (10.0, 50.0, 12.50, 1.00),
}


def project_dir() -> Path:
    slug = str(Path.cwd()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def collect(files):
    # message.id 기준 마지막 usage만 (스트리밍 중복 방지)
    by_msg = {}
    fallback = 0
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue
                key = msg.get("id")
                if key is None:
                    fallback += 1
                    key = f"_no_id_{fallback}"
                by_msg[key] = (msg.get("model", "?"), usage)
    totals = {}
    for model, u in by_msg.values():
        t = totals.setdefault(model, [0, 0, 0, 0])
        t[0] += u.get("input_tokens", 0)
        t[1] += u.get("output_tokens", 0)
        t[2] += u.get("cache_creation_input_tokens", 0)
        t[3] += u.get("cache_read_input_tokens", 0)
    return totals


def main():
    pdir = project_dir()
    if not pdir.is_dir():
        sys.exit(f"세션 디렉터리 없음: {pdir}")
    if len(sys.argv) > 1:
        files = [pdir / f"{sys.argv[1]}.jsonl"]
        if not files[0].is_file():
            sys.exit(f"세션 파일 없음: {files[0]}")
    else:
        now = time.localtime()
        midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
        files = [f for f in pdir.glob("*.jsonl") if f.stat().st_mtime >= midnight]
        if not files:
            sys.exit("오늘 수정된 세션 없음")
    grand = 0.0
    unknown = False
    print(f"{'model':<24} {'in':>10} {'out':>10} {'c_write':>10} {'c_read':>11} {'USD':>8}")
    for model, (i, o, cw, cr) in sorted(collect(files).items()):
        if i + o + cw + cr == 0:
            continue
        p = PRICES.get(model)
        if p:
            cost = (i * p[0] + o * p[1] + cw * p[2] + cr * p[3]) / 1e6
            grand += cost
            cost_s = f"{cost:8.2f}"
        else:
            unknown = True
            cost_s = "       ?"
        print(f"{model:<24} {i:>10} {o:>10} {cw:>10} {cr:>11} {cost_s}")
    print(f"합계: ${grand:.2f}" + (" + ? (단가 미등록 모델 있음)" if unknown else "")
          + f"  (파일 {len(files)}개)")


if __name__ == "__main__":
    main()
