#!/usr/bin/env python3
"""orchestrate phase 레지스트리 도구 — init / claim / close / janitor / dashboard-mounts.

phase 번호의 유일한 진실의 원천은 ~/.local/state/orchestrate/registry/<project>.json.
git 밖·세션 밖 파일이므로 병렬 세션의 브랜치 가시성 한계와 세션 절단에 영향받지 않는다.
모든 레지스트리 갱신은 flock 안에서 수행된다.

사용:
  python3 scripts/phase-tools.py init --default-branch develop --docs-dir docs/phases
  python3 scripts/phase-tools.py claim <slug> [--base <ref>]
  python3 scripts/phase-tools.py close <N> [--keep-worktree] [--force] [--target <ref>]
  python3 scripts/phase-tools.py janitor
  python3 scripts/phase-tools.py dashboard-mounts [--print-path]
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKTREE_BASE = ".claude/worktrees"
PHASE_RE = re.compile(r"phase[_-]?(\d+)", re.IGNORECASE)
STALE_LOG_DAYS = 7
STALE_PR_DAYS = 3
# 병합돼 있어도 janitor가 절대 삭제하지 않는 장수 브랜치
PROTECTED_BRANCHES = {"main", "master", "develop", "even-mode"}


def state_dir() -> Path:
    base = Path(os.environ.get(
        "ORCH_STATE_DIR", str(Path.home() / ".local/state/orchestrate")))
    d = base / "registry"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sh(args, cwd=None, check=True, timeout=60):
    return subprocess.run(
        [str(a) for a in args], cwd=cwd, check=check, timeout=timeout,
        capture_output=True, text=True)


def git(root, *args, check=True, timeout=60):
    return sh(["git", "-C", root, *args], check=check, timeout=timeout)


def find_root() -> Path:
    """워크트리 안에서 실행돼도 메인 체크아웃 루트를 돌려준다."""
    r = sh(["git", "rev-parse", "--git-common-dir"])
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = (Path.cwd() / common).resolve()
    return common.parent


def is_clean(path) -> bool:
    return git(path, "status", "--porcelain", check=False).stdout.strip() == ""


def is_merged(root, ref, target) -> bool:
    return git(root, "merge-base", "--is-ancestor", "--", ref, target,
               check=False).returncode == 0


def merge_target(root, db: str) -> str:
    """origin/<db>가 있으면 그것을, 없으면 로컬 <db>를 병합 판정 기준으로 쓴다."""
    if git(root, "rev-parse", "--verify", f"origin/{db}",
           check=False).returncode == 0:
        return f"origin/{db}"
    return db


def scan_max_phase(root: Path, docs_dir: str) -> int:
    nums = [0]
    for f in phase_document_files(root, docs_dir):
        m = PHASE_RE.search(f.name)
        if m:
            nums.append(int(m.group(1)))
    branches = git(root, "branch", "-a", check=False).stdout
    nums += [int(m.group(1)) for m in PHASE_RE.finditer(branches)]
    wt_base = root / WORKTREE_BASE
    if wt_base.is_dir():
        for d in wt_base.iterdir():
            m = PHASE_RE.search(d.name)
            if m:
                nums.append(int(m.group(1)))
            # 워크트리 안에서 번호가 리네임되면 문서만이 유일한 근거다 (166→167 실측)
            for f in phase_document_files(d, docs_dir):
                m = PHASE_RE.search(f.name)
                if m:
                    nums.append(int(m.group(1)))
    return max(nums)


def phase_document_files(root: Path, docs_dir: str):
    """스캐폴드 제외 재귀 페이즈 문서를 반환한다."""
    base = root / docs_dir
    if not base.is_dir():
        return
    for path in base.rglob("*.md"):
        parts = path.relative_to(base).parts
        if any(part in ("TEMPLATES", "specs", "images") for part in parts):
            continue
        if PHASE_RE.search(path.name):
            yield path


def default_docs_dir(root: Path) -> str:
    """문서 내용까지 확인해 init의 기본 문서 경로를 고른다."""
    docs_phases = root / "docs" / "phases"
    legacy_docs = root / "DOCs"
    if docs_phases.is_dir() and any(
            PHASE_RE.search(path.name)
            for path in phase_document_files(root, "docs/phases")):
        return "docs/phases"
    if legacy_docs.is_dir():
        return "DOCs"
    return "docs/phases"


class Registry:
    """flock 하에 레지스트리 파일을 읽고 쓰는 컨텍스트 매니저."""

    def __init__(self, root: Path):
        self.root = root
        self.path = state_dir() / f"{root.name}.json"
        self._lock_path = self.path.with_suffix(".lock")
        self._fh = None
        self.data = None

    def __enter__(self):
        self._fh = open(self._lock_path, "w")
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")
        tmp.rename(self.path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def cmd_init(args):
    root = find_root()
    with Registry(root) as reg:
        if reg.data is not None and not args.reseed:
            print(f"레지스트리 존재 — next_phase={reg.data['next_phase']} (변경 없음)")
            return 0
        if args.docs_dir is not None:
            docs_dir = args.docs_dir
        elif reg.data is not None:
            docs_dir = reg.data["docs_dir"]
        else:
            docs_dir = default_docs_dir(root)
        seed = scan_max_phase(root, docs_dir) + 1
        reg.data = {
            "project": root.name,
            "root": str(root),
            "default_branch": args.default_branch,
            "docs_dir": docs_dir,
            "next_phase": seed,
            "active": reg.data["active"] if reg.data else [],
        }
        reg.save()
        print(f"초기화 완료 — project={root.name} next_phase={seed}")
    return 0


def cmd_claim(args):
    root = find_root()
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init을 실행하세요", file=sys.stderr)
            return 64
        d = reg.data
        n = d["next_phase"]
        slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
        branch = f"feature/phase{n}-{slug}"
        wt_rel = f"{WORKTREE_BASE}/phase{n}-{slug}"
        db = d["default_branch"]
        git(root, "fetch", "origin", db, check=False, timeout=30)
        base = args.base or merge_target(root, db)
        r = git(root, "worktree", "add", "-b", branch, wt_rel, base, check=False)
        if r.returncode != 0:
            # 실패 시 카운터를 올리지 않는다 — flock을 쥔 채라 경쟁 없음
            print(f"worktree add 실패:\n{r.stderr}", file=sys.stderr)
            return 1
        d["next_phase"] = n + 1
        d["active"].append({
            "phase": n,
            "slug": slug,
            "worktree": wt_rel,
            "branch": branch,
            "base": base,
            "claimed_at": now_iso(),
            "source": os.environ.get("ORCH_SOURCE", "cli"),
        })
        reg.save()
    print(f"PHASE={n}")
    print(f"WORKTREE={root / wt_rel}")
    print(f"BRANCH={branch}")
    return 0


def doc_status(root: Path, docs_dir: str, n: int, worktree: Path | None):
    """지시서 PHASE<n>_*.md의 frontmatter status 값. (경로, 값) 또는 (None, None)."""
    search = [root / docs_dir]
    if worktree is not None:
        search.append(worktree / docs_dir)
    for base in search:
        if not base.is_dir():
            continue
        for f in sorted(base.glob(f"PHASE{n}_*.md")):
            for line in f.read_text(errors="replace").splitlines()[:15]:
                m = re.match(r"status:\s*(\S+)", line.strip())
                if m:
                    return f, m.group(1)
    return None, None


def archive_orchestrate(root: Path, n: int) -> int:
    """메인 체크아웃 .orchestrate/에서 phase n 관련 파일을 archive로 이동."""
    orch = root / ".orchestrate"
    if not orch.is_dir():
        return 0
    dest = orch / "archive" / f"phase{n}"
    moved = 0
    for item in list(orch.iterdir()):
        if item.name == "archive":
            continue
        if re.match(rf"(p{n}[-_.]|phase{n}([-_.]|$))", item.name):
            dest.mkdir(parents=True, exist_ok=True)
            item.rename(dest / item.name)
            moved += 1
    return moved


def cmd_close(args):
    root = find_root()
    n = args.number
    lines = []
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init을 실행하세요", file=sys.stderr)
            return 64
        d = reg.data
        db = d["default_branch"]
        if args.target:
            if git(root, "rev-parse", "--verify", args.target,
                   check=False).returncode != 0:
                print(f"--target ref 를 찾을 수 없음: {args.target}",
                      file=sys.stderr)
                return 2
            targets = [args.target]
        else:
            targets = []
            default_target = merge_target(root, db)
            if git(root, "rev-parse", "--verify", default_target,
                   check=False).returncode == 0:
                targets.append(default_target)
            if default_target != db and \
                    git(root, "rev-parse", "--verify", db,
                        check=False).returncode == 0:
                targets.append(db)
            current = git(root, "symbolic-ref", "--short", "HEAD",
                          check=False).stdout.strip()
            if current and current not in targets:
                targets.append(current)
        if not targets:
            lines.append("병합 판정 기준 없음(default_branch/HEAD 확인 불가) — 보존")
        entry = next((e for e in d["active"] if e["phase"] == n), None)
        wt_rel = entry["worktree"] if entry else None
        if wt_rel is None:
            hits = sorted((root / WORKTREE_BASE).glob(f"phase{n}-*")) \
                if (root / WORKTREE_BASE).is_dir() else []
            wt_rel = str(hits[0].relative_to(root)) if hits else None
        wt = (root / wt_rel) if wt_rel else None
        wt_exists = wt is not None and wt.is_dir()

        doc, status = doc_status(root, d["docs_dir"], n, wt if wt_exists else None)
        if status is not None and status != "done" and not args.force:
            print(f"지시서 status가 done이 아님 ({doc}: {status}) — "
                  f"frontmatter를 갱신하거나 --force로 우회하세요", file=sys.stderr)
            return 2

        branch = entry["branch"] if entry else None
        if wt_exists:
            wt_branch = git(wt, "rev-parse", "--abbrev-ref", "HEAD",
                            check=False).stdout.strip() or branch
            if not is_clean(wt):
                lines.append(f"워크트리 dirty — 보존: {wt_rel}")
            elif args.keep_worktree:
                lines.append(f"워크트리 보존(--keep-worktree): {wt_rel}")
            elif wt_branch and any(is_merged(root, wt_branch, target)
                                   for target in targets if target != wt_branch):
                git(root, "worktree", "remove", wt_rel)
                lines.append(f"워크트리 제거: {wt_rel}")
                branch = wt_branch
            else:
                lines.append(f"워크트리 미병합 — 보존: {wt_rel} ({wt_branch})")

        if branch and not (wt_rel and (root / wt_rel).is_dir()):
            if any(is_merged(root, branch, target)
                   for target in targets if target != branch) and \
                    git(root, "branch", "-d", branch, check=False).returncode == 0:
                lines.append(f"로컬 브랜치 삭제: {branch}")

        moved = archive_orchestrate(root, n)
        if moved:
            lines.append(f".orchestrate 아카이브: {moved}개 파일")

        if entry:
            d["active"] = [e for e in d["active"] if e["phase"] != n]
            reg.save()
            lines.append("레지스트리 항목 제거")

    print(f"phase {n} 마감:")
    for ln in lines or ["정리할 항목 없음"]:
        print(f"  - {ln}")
    return 0


def stale_prs(root: Path):
    """gh가 있으면 3일+ 정체된 열린 PR 목록. 실패는 조용히 빈 목록."""
    import shutil as _shutil
    if _shutil.which("gh") is None:
        return []
    r = sh(["gh", "pr", "list", "--state", "open",
            "--json", "number,title,isDraft,updatedAt"],
           cwd=root, check=False, timeout=10)
    if r.returncode != 0:
        return []
    out = []
    try:
        prs = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []
    now = datetime.now().astimezone()
    for pr in prs:
        upd = datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
        age = (now - upd).days
        if age >= STALE_PR_DAYS:
            draft = " (draft)" if pr.get("isDraft") else ""
            out.append(f"PR #{pr['number']}{draft} {age}일 정체 — {pr['title'][:40]}")
    return out


def cmd_janitor(args):
    try:
        return _janitor_inner()
    except Exception as e:  # 세션 시작을 막지 않는다
        print(f"JANITOR: 오류로 건너뜀 ({type(e).__name__}: {e})")
        return 0


def _janitor_inner():
    root = find_root()
    auto, warn = [], []
    with Registry(root) as reg:
        if reg.data is None:
            print("JANITOR: 레지스트리 없음 — init 필요")
            return 0
        d = reg.data
        db = d["default_branch"]
        target = merge_target(root, db)
        active_branches = {e["branch"] for e in d["active"]}

        # 1. 유령 레지스트리 항목
        for e in list(d["active"]):
            if not (root / e["worktree"]).is_dir():
                d["active"].remove(e)
                auto.append(f"유령 항목 제거: phase{e['phase']}")

        # 2. 워크트리: 병합+clean → 제거 / 그 외 보고
        wt_base = root / WORKTREE_BASE
        if wt_base.is_dir():
            for wt in sorted(wt_base.iterdir()):
                if not wt.is_dir():
                    continue
                br = git(wt, "rev-parse", "--abbrev-ref", "HEAD",
                         check=False).stdout.strip()
                if not is_clean(wt):
                    warn.append(f"dirty 워크트리: {wt.name} ({br})")
                elif br and is_merged(root, br, target):
                    git(root, "worktree", "remove",
                        str(wt.relative_to(root)), check=False)
                    git(root, "branch", "-d", br, check=False)
                    d["active"] = [e for e in d["active"] if e["worktree"]
                                   != str(wt.relative_to(root))]
                    auto.append(f"병합된 워크트리 제거: {wt.name}")
                else:
                    warn.append(f"미병합 워크트리: {wt.name} ({br})")

        # 3. 병합된 로컬 브랜치
        merged = git(root, "branch", "--merged", target,
                     check=False).stdout.splitlines()
        cur = git(root, "symbolic-ref", "--short", "HEAD",
                  check=False).stdout.strip()
        for b in (x.strip().lstrip("+ ") for x in merged):
            if not b or b.startswith("*") or b in (db, cur) \
                    or b in PROTECTED_BRANCHES or b in active_branches:
                continue
            if git(root, "branch", "-d", b, check=False).returncode == 0:
                auto.append(f"병합된 브랜치 삭제: {b}")

        # 4. 오래된 .orchestrate 파일 → archive/old/
        orch = root / ".orchestrate"
        if orch.is_dir():
            import time as _time
            cutoff = _time.time() - STALE_LOG_DAYS * 86400
            moved = 0
            for item in list(orch.iterdir()):
                if item.name in ("archive", "events.jsonl"):
                    continue
                if item.stat().st_mtime < cutoff:
                    dest = orch / "archive" / "old"
                    dest.mkdir(parents=True, exist_ok=True)
                    item.rename(dest / item.name)
                    moved += 1
            if moved:
                auto.append(f".orchestrate 아카이브: {moved}건")

        # 5. 메인 체크아웃 이탈·미푸시
        if cur and cur != db:
            warn.append(f"메인 체크아웃이 {db}가 아님: {cur} (메인=안정 전용 위반)")
        if not is_clean(root):
            warn.append("메인 체크아웃 dirty")
        if target != db:
            ahead = git(root, "rev-list", "--count", f"{target}..{db}",
                        check=False).stdout.strip()
            if ahead and ahead != "0":
                warn.append(f"{db}가 origin보다 {ahead}커밋 앞섬 (미푸시)")

        # 6. in-progress 방치 문서 (레지스트리 active에 없는 것)
        active_nums = {e["phase"] for e in d["active"]}
        docs = root / d["docs_dir"]
        if docs.is_dir():
            for f in sorted(docs.glob("PHASE*.md")):
                status = None
                for line in f.read_text(errors="replace").splitlines()[:15]:
                    m = re.match(r"status:\s*(\S+)", line.strip())
                    if m:
                        status = m.group(1)
                        break
                mnum = PHASE_RE.search(f.name)
                if status == "in-progress" and mnum \
                        and int(mnum.group(1)) not in active_nums:
                    warn.append(f"in-progress 방치 문서: {f.name}")

        warn.extend(stale_prs(root))
        reg.save()

    summary = f"JANITOR({root.name}): 자동정리 {len(auto)}건 / 확인필요 {len(warn)}건"
    print(summary)
    for ln in (auto + warn)[:12]:
        print(f"  - {ln}")
    log = state_dir().parent / f"janitor-{root.name}.log"
    with open(log, "a") as fh:
        fh.write(f"[{now_iso()}] {summary}\n")
        for ln in auto + warn:
            fh.write(f"  {ln}\n")
    return 0


def cmd_dashboard_mounts(args: argparse.Namespace) -> int:
    """레지스트리의 존재하는 문서 디렉터리로 대시보드 compose override를 만든다."""
    registry_dir = state_dir()
    override_path = registry_dir.parent / "dashboard-compose.override.yml"
    if args.print_path:
        print(override_path)
        return 0

    project_docs: list[tuple[str, str, Path, Path]] = []
    registry_paths = sorted(registry_dir.glob("*.json"))
    for registry_path in registry_paths:
        try:
            entry = json.loads(registry_path.read_text(encoding="utf-8"))
            if not isinstance(entry, dict):
                raise ValueError("레지스트리 항목은 객체여야 함")
            project = entry["project"]
            root = entry["root"]
            docs_dir = entry["docs_dir"]
            if not all(isinstance(value, str) for value in
                       (project, root, docs_dir)):
                raise ValueError("project, root, docs_dir는 문자열이어야 함")
        except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError) as error:
            print(f"경고: 레지스트리 항목 건너뜀 ({registry_path.name}: {error})",
                  file=sys.stderr)
            continue

        try:
            mount_path = Path(root) / docs_dir
            if not Path(root).is_absolute():
                raise ValueError("프로젝트 root가 절대경로가 아님")
            root_path = Path(root).resolve()
            docs_path = mount_path.resolve()
            if any(ord(char) < 32 or ord(char) == 127
                   for value in (root, docs_dir, str(mount_path))
                   for char in value):
                raise ValueError("경로에 제어 문자가 있음")
            try:
                docs_path.relative_to(root_path)
            except ValueError as error:
                raise ValueError("문서 경로가 프로젝트 root 밖에 있음") from error
            if docs_path == root_path:
                raise ValueError("문서 경로가 프로젝트 root와 같음")
            if not docs_path.is_dir():
                print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                      f"registry={registry_path.name!r}, path={str(docs_path)!r}: "
                      "디렉터리가 없음)", file=sys.stderr)
                continue
        except (OSError, RuntimeError, ValueError) as error:
            print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                  f"registry={registry_path.name!r}, "
                  f"path={str(Path(root) / docs_dir)!r}: {error})", file=sys.stderr)
            continue
        project_docs.append((project, registry_path.name, docs_path, mount_path))

    mounts: list[str] = []
    seen_paths: set[Path] = set()
    for project, registry_name, docs_path, mount_path in sorted(
            project_docs, key=lambda item: item[0]):
        if mount_path in seen_paths:
            print(f"경고: 문서 디렉터리 건너뜀 (project={project!r}, "
                  f"registry={registry_name!r}, path={str(mount_path)!r}: "
                  "중복 마운트 경로)", file=sys.stderr)
            continue
        seen_paths.add(mount_path)
        mounts.append(f"{docs_path}:{mount_path}:ro")

    if not mounts:
        override_path.unlink(missing_ok=True)
        if registry_paths:
            print(f"경고: 레지스트리 항목 {len(registry_paths)}개 중 마운트 0개",
                  file=sys.stderr)
        return 0

    registry_mount = f"{registry_dir}:/data/orchestrate-registry:ro"
    lines = [
        "services:",
        "  usage-dashboard:",
        "    volumes:",
        f"      - {json.dumps(registry_mount, ensure_ascii=False)}",
    ]
    lines.extend(f"      - {json.dumps(mount, ensure_ascii=False)}" for mount in mounts)
    lines.extend([
        "    environment:",
        "      - USAGE_REGISTRY_DIR=/data/orchestrate-registry",
        "",
    ])
    tmp = override_path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.rename(override_path)
    print(override_path)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="phase-tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="레지스트리 생성·시드")
    p_init.add_argument("--default-branch", required=True)
    p_init.add_argument("--docs-dir", default=None)
    p_init.add_argument("--reseed", action="store_true")
    p_init.set_defaults(fn=cmd_init)

    p_claim = sub.add_parser("claim", help="phase 번호 발급 + 워크트리 생성")
    p_claim.add_argument("slug")
    p_claim.add_argument("--base", default=None)
    p_claim.set_defaults(fn=cmd_claim)

    p_close = sub.add_parser("close", help="페이즈 마감 원샷 정리")
    p_close.add_argument("number", type=int)
    p_close.add_argument("--keep-worktree", action="store_true")
    p_close.add_argument("--force", action="store_true")
    p_close.add_argument("--target", default=None,
                         help="병합 판정에 사용할 단일 ref")
    p_close.set_defaults(fn=cmd_close)

    p_jan = sub.add_parser("janitor", help="세션 시작 잔재 정리·보고 (항상 exit 0)")
    p_jan.set_defaults(fn=cmd_janitor)

    p_mounts = sub.add_parser("dashboard-mounts",
                              help="대시보드 문서·레지스트리 마운트 override 생성")
    p_mounts.add_argument("--print-path", action="store_true",
                          help="생성 없이 override 대상 경로만 출력")
    p_mounts.set_defaults(fn=cmd_dashboard_mounts)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
