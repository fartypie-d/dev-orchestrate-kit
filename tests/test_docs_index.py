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

    # Phase 8 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_docs_dir_prefers_docs_phases(self):
        docs_dir = self.root / "docs" / "phases"
        self.write_phase_document(docs_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())
        first_line = (docs_dir / "INDEX.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("docs/phases", first_line)

    def test_docs_dir_prefers_docs_phases_over_DOCs(self):
        new_dir = self.root / "docs" / "phases"
        self.write_phase_document(new_dir)
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((new_dir / "INDEX.md").is_file())
        self.assertFalse((legacy_dir / "INDEX.md").exists())

    def test_empty_docs_phases_falls_back_to_DOCs(self):
        # 전환기 상태: docs/phases는 존재하지만 비어있고 실문서는 DOCs에 있다
        (self.root / "docs" / "phases").mkdir(parents=True)
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((legacy_dir / "INDEX.md").is_file())
        self.assertFalse((self.root / "docs" / "phases" / "INDEX.md").exists())

    def test_scaffolding_only_docs_phases_falls_back_to_DOCs(self):
        # docs/phases에 스캔 제외 대상(TEMPLATES·specs)만 있으면 실문서 없는 것으로 판정
        scaffold = self.root / "docs" / "phases"
        (scaffold / "TEMPLATES").mkdir(parents=True)
        (scaffold / "TEMPLATES" / "CURRENT_TASK_template.md").write_text("stub")
        (scaffold / "specs").mkdir()
        (scaffold / "specs" / "design.md").write_text("stub")
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((legacy_dir / "INDEX.md").is_file())
        self.assertFalse((scaffold / "INDEX.md").exists())

    def test_reviews_only_docs_phases_preferred_over_DOCs(self):
        # reviews/ 하위 실문서만으로도 docs/phases가 선택된다 (phase-tools와 동일 판정 계약)
        reviews = self.root / "docs" / "phases" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "PHASE12_REVIEW.md").write_text(
            "---\nphase: 12\nkind: review\nstatus: done\nsummary: 리뷰\n---\n",
            encoding="utf-8",
        )
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "docs" / "phases" / "INDEX.md").is_file())
        self.assertFalse((legacy_dir / "INDEX.md").exists())

    def test_missing_docs_dir_fails_clearly(self):
        result = self.run_index()

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr.strip(), "빈 stderr — 침묵 실패 금지")
