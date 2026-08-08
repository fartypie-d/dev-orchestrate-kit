"""phase-tools.py 테스트 — 임시 git 저장소 + ORCH_STATE_DIR 격리."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "core/scripts/phase-tools.py"


def run_tool(args, cwd, env, check=False):
    r = subprocess.run(
        [sys.executable, str(TOOLS), *args],
        cwd=cwd, env=env, capture_output=True, text=True,
    )
    if check and r.returncode != 0:
        raise AssertionError(f"phase-tools {args} 실패: {r.stdout}\n{r.stderr}")
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.env = {
            **os.environ,
            "ORCH_STATE_DIR": str(Path(self.tmp.name) / "state"),
        }
        subprocess.run(
            ["git", "init", "-b", "develop", str(self.root)],
            check=True, capture_output=True,
        )
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        (self.root / "DOCs").mkdir()
        (self.root / "DOCs" / "PHASE7_seed.md").write_text(
            "---\nphase: 7\nstatus: done\n---\n"
        )
        (self.root / "a.txt").write_text("a\n")
        self.git("add", ".")
        self.git("commit", "-m", "init")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True, capture_output=True, text=True,
        )

    def init_registry(self):
        run_tool(
            ["init", "--default-branch", "develop", "--docs-dir", "DOCs"],
            self.root, self.env, check=True,
        )

    def registry(self):
        p = Path(self.env["ORCH_STATE_DIR"]) / "registry" / "proj.json"
        return json.loads(p.read_text())


class TestInit(Base):
    def test_init_seeds_next_phase_from_docs(self):
        self.init_registry()
        reg = self.registry()
        self.assertEqual(reg["next_phase"], 8)  # DOCs에 PHASE7 → 다음 8
        self.assertEqual(reg["default_branch"], "develop")
        self.assertEqual(reg["docs_dir"], "DOCs")
        self.assertEqual(reg["active"], [])

    def test_init_scans_worktree_docs_too(self):
        # 다른 세션 워크트리에만 존재하는 지시서(브랜치 미병합)도 시드에 반영돼야 한다
        self.init_registry()
        run_tool(["claim", "other"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-other"
        # 워크트리 안에서 번호가 리네임된 상황 재현 (166→167 실측 사례)
        (wt / "DOCs" / "PHASE12_renamed.md").write_text("---\nstatus: in-progress\n---\n")
        run_tool(
            ["init", "--default-branch", "develop", "--docs-dir", "DOCs", "--reseed"],
            self.root, self.env, check=True,
        )
        self.assertEqual(self.registry()["next_phase"], 13)

    def test_init_is_idempotent_without_reseed(self):
        self.init_registry()
        (self.root / "DOCs" / "PHASE20_x.md").write_text("---\nstatus: done\n---\n")
        self.init_registry()  # reseed 없으면 기존 값 유지
        self.assertEqual(self.registry()["next_phase"], 8)


class TestClaim(Base):
    def test_claim_allocates_number_worktree_branch(self):
        self.init_registry()
        r = run_tool(["claim", "my-feature"], self.root, self.env, check=True)
        self.assertIn("PHASE=8", r.stdout)
        self.assertIn("BRANCH=feature/phase8-my-feature", r.stdout)
        wt = self.root / ".claude/worktrees/phase8-my-feature"
        self.assertTrue(wt.is_dir())
        head = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(head, "feature/phase8-my-feature")
        reg = self.registry()
        self.assertEqual(reg["next_phase"], 9)
        self.assertEqual(reg["active"][0]["phase"], 8)

    def test_claim_from_inside_worktree_uses_main_root(self):
        self.init_registry()
        run_tool(["claim", "first"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-first"
        r = run_tool(["claim", "second"], wt, self.env, check=True)
        self.assertIn("PHASE=9", r.stdout)
        self.assertTrue((self.root / ".claude/worktrees/phase9-second").is_dir())

    def test_parallel_claims_get_distinct_numbers(self):
        self.init_registry()
        procs = [
            subprocess.Popen(
                [sys.executable, str(TOOLS), "claim", f"par-{i}"],
                cwd=self.root, env=self.env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for i in range(2)
        ]
        outs = [p.communicate()[0] for p in procs]
        self.assertTrue(all(p.returncode == 0 for p in procs))
        nums = sorted(
            int(line.split("=")[1])
            for out in outs for line in out.splitlines()
            if line.startswith("PHASE=")
        )
        self.assertEqual(nums, [8, 9])


class TestClose(Base):
    def _claim_and_finish(self, slug="feat-x", merge=True):
        """claim → 워크트리에서 커밋 + 지시서 status: done → (선택) develop에 병합."""
        self.init_registry()
        run_tool(["claim", slug], self.root, self.env, check=True)
        wt = self.root / f".claude/worktrees/phase8-{slug}"
        (wt / "DOCs" / f"PHASE8_{slug}.md").write_text(
            "---\nphase: 8\nstatus: done\n---\n"
        )
        (wt / "b.txt").write_text("b\n")
        subprocess.run(["git", "-C", str(wt), "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "work"],
                       check=True, capture_output=True)
        if merge:
            self.git("merge", "--no-ff", f"feature/phase8-{slug}", "-m", "merge")
        return wt

    def test_close_removes_worktree_branch_and_entry(self):
        wt = self._claim_and_finish()
        r = run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertFalse(wt.exists())
        branches = self.git("branch").stdout
        self.assertNotIn("feature/phase8-feat-x", branches)
        self.assertEqual(self.registry()["active"], [])
        self.assertIn("phase 8 마감", r.stdout)

    def test_close_refuses_when_doc_not_done(self):
        wt = self._claim_and_finish(merge=False)
        doc = wt / "DOCs" / "PHASE8_feat-x.md"
        doc.write_text("---\nphase: 8\nstatus: in-progress\n---\n")
        subprocess.run(["git", "-C", str(wt), "commit", "-am", "wip"],
                       check=True, capture_output=True)
        r = run_tool(["close", "8"], self.root, self.env)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(wt.exists())  # 아무것도 지우지 않음

    def test_close_keeps_dirty_worktree_but_clears_entry_with_force(self):
        wt = self._claim_and_finish()
        (wt / "dirty.txt").write_text("uncommitted\n")
        r = run_tool(["close", "8", "--force"], self.root, self.env, check=True)
        self.assertTrue(wt.exists())  # dirty 워크트리는 보존
        self.assertIn("dirty", r.stdout)
        self.assertEqual(self.registry()["active"], [])

    def test_close_archives_orchestrate_logs(self):
        self._claim_and_finish()
        orch = self.root / ".orchestrate"
        orch.mkdir()
        (orch / "p8-task1.log").write_text("log\n")
        run_tool(["close", "8"], self.root, self.env, check=True)
        self.assertFalse((orch / "p8-task1.log").exists())
        self.assertTrue((orch / "archive/phase8/p8-task1.log").exists())


class TestJanitor(Base):
    def test_janitor_removes_merged_clean_worktree_and_branch(self):
        self.init_registry()
        run_tool(["claim", "done-work"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-done-work"
        (wt / "b.txt").write_text("b\n")
        subprocess.run(["git", "-C", str(wt), "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "work"],
                       check=True, capture_output=True)
        self.git("merge", "--no-ff", "feature/phase8-done-work", "-m", "merge")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertFalse(wt.exists())
        self.assertNotIn("feature/phase8-done-work", self.git("branch").stdout)
        self.assertEqual(self.registry()["active"], [])
        self.assertIn("자동정리", r.stdout)

    def test_janitor_reports_dirty_worktree_without_touching(self):
        self.init_registry()
        run_tool(["claim", "wip"], self.root, self.env, check=True)
        wt = self.root / ".claude/worktrees/phase8-wip"
        (wt / "dirty.txt").write_text("x\n")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertTrue(wt.exists())
        self.assertIn("확인필요", r.stdout)
        self.assertIn("phase8-wip", r.stdout)

    def test_janitor_reports_main_checkout_drift(self):
        self.init_registry()
        self.git("checkout", "-b", "integration/other")
        r = run_tool(["janitor"], self.root, self.env, check=True)
        self.assertIn("integration/other", r.stdout)

    def test_janitor_drops_ghost_entry_and_always_exit_zero(self):
        self.init_registry()
        run_tool(["claim", "ghost"], self.root, self.env, check=True)
        self.git("worktree", "remove", "--force",
                 ".claude/worktrees/phase8-ghost")
        r = run_tool(["janitor"], self.root, self.env)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.registry()["active"], [])

    def test_janitor_never_deletes_longlived_branches(self):
        # main/master/develop 같은 장수 브랜치는 병합돼 있어도 삭제 금지
        self.init_registry()
        self.git("branch", "main")      # develop과 동일 커밋 = merged 판정됨
        self.git("branch", "release")   # 임의 feature성 브랜치는 삭제 대상
        run_tool(["janitor"], self.root, self.env, check=True)
        branches = self.git("branch").stdout
        self.assertIn("main", branches)
        self.assertNotIn("release", branches)

    def test_janitor_archives_old_orchestrate_files(self):
        self.init_registry()
        orch = self.root / ".orchestrate"
        orch.mkdir()
        old = orch / "p3-task1.log"
        old.write_text("old\n")
        eight_days = 8 * 86400
        os.utime(old, (old.stat().st_atime - eight_days,
                       old.stat().st_mtime - eight_days))
        (orch / "fresh.log").write_text("new\n")
        run_tool(["janitor"], self.root, self.env, check=True)
        self.assertFalse(old.exists())
        self.assertTrue((orch / "archive/old/p3-task1.log").exists())
        self.assertTrue((orch / "fresh.log").exists())


if __name__ == "__main__":
    unittest.main()
