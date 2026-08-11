"""docs-index.py의 심링크 경로와 문서 디렉터리 오버라이드 테스트."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "core/scripts/docs-index.py"


class TestDocsIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        core_scripts = self.root / "core/scripts"
        core_scripts.mkdir(parents=True)
        shutil.copy2(SOURCE, core_scripts / "docs-index.py")
        scripts = self.root / "scripts"
        scripts.mkdir()
        os.symlink("../core/scripts/docs-index.py", scripts / "docs-index.py")

    def write_phase_document(self, docs_dir):
        docs_dir.mkdir(parents=True)
        (docs_dir / "PHASE1_dummy.md").write_text(
            "---\nphase: 1\ndate: 2026-08-11\nkind: task\n"
            "summary: 더미 페이즈 문서\n---\n# 더미 페이즈 문서\n",
            encoding="utf-8",
        )

    def run_index(self, *args):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/docs-index.py"), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_symlink_execution_writes_index_in_repository_docs(self):
        docs_dir = self.root / "DOCs"
        self.write_phase_document(docs_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())

    def test_docs_dir_override_writes_index_in_specified_directory(self):
        docs_dir = self.root / "다른-문서"
        self.write_phase_document(docs_dir)

        result = self.run_index("--docs-dir", str(docs_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())
