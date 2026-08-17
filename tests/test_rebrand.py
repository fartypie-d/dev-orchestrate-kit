# Phase 9 리브랜딩 회귀 가드 — 오케스트레이터 작성·동결 (위임 에이전트 수정 금지)
# 근거: docs/phases/PHASE9_aigsprac-rebrand.md "리뷰 예상 지점"
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_NAME = "dev-orchestrate-kit"
NEW_NAME = "aigsprac"


class TestRebrandGuards(unittest.TestCase):
    def test_project_template_intact(self):
        """치환이 core/project-template/ 원본을 오염시키지 않았는지 (2026-08-08 사고 재발 방지)."""
        template_dir = ROOT / "core" / "project-template"
        placeholder_found = False
        for path in template_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            self.assertNotIn(
                NEW_NAME, text,
                f"{path}: 템플릿 원본에 제품명 유입 — __PROJECT__ 자리를 침범했다",
            )
            if "__PROJECT__" in text:
                placeholder_found = True
        self.assertTrue(
            placeholder_found,
            "core/project-template/ 에서 __PROJECT__ 플레이스홀더가 사라졌다",
        )

    def test_history_docs_untouched(self):
        """이력 문서 소급 치환 금지 — 표본: kit-v2 계획 문서 (작성 시점 이름 52회)."""
        plan = ROOT / "docs" / "plans" / "2026-08-07-kit-v2-adapters.md"
        count = plan.read_text(encoding="utf-8").count(OLD_NAME)
        self.assertGreaterEqual(
            count, 50,
            f"이력 문서가 소급 치환됐다 (옛 이름 {count}회 < 50) — 기록은 작성 시점 그대로",
        )

    def test_readme_rebranded(self):
        """README 영/국문 동기 리브랜딩 — 제목·백로님 스토리·구명 표기."""
        for name in ("README.md", "README.ko.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            first_line = text.splitlines()[0]
            self.assertIn(NEW_NAME, first_line, f"{name}: 1행 제목에 aigsprac 없음")
            self.assertIn(
                "AI General Staff", text,
                f"{name}: 백로님 스토리(AI General Staff) 절 없음",
            )
            self.assertIn(
                OLD_NAME, text,
                f"{name}: 구명(formerly/구 {OLD_NAME}) 표기가 없음",
            )
            self.assertLessEqual(
                text.count(OLD_NAME), 2,
                f"{name}: 옛 이름 잔존 과다 — 구명 표기 외에는 치환돼야 한다",
            )


if __name__ == "__main__":
    unittest.main()
