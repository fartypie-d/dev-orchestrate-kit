"""gen-policy.sh 테스트 — 프로바이더 조합에서 tier 체인이 생성되는지 검증."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
GEN = KIT / "core/opencode/gen-policy.sh"


def gen(providers, out):
    return subprocess.run(
        ["bash", str(GEN), providers, str(out)], capture_output=True, text=True
    )


def gen_with_table(providers, out, directory):
    """임시 스크립트의 같은 디렉터리에 둔 매핑표로 생성기를 실행한다."""
    script = directory / "gen-policy.sh"
    shutil.copy2(GEN, script)
    return subprocess.run(
        ["bash", str(script), providers, str(out)], capture_output=True, text=True
    )


class GenPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "model-policy.json"

    def load(self):
        return json.loads(self.out.read_text())

    def test_single_provider_produces_both_tiers(self):
        r = gen("qwen", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        policy = self.load()
        self.assertTrue(policy["tiers"]["default"])
        self.assertTrue(policy["tiers"]["heavy"])

    def test_only_selected_providers_appear(self):
        gen("qwen", self.out)
        chains = self.load()["tiers"]
        for entry in chains["default"] + chains["heavy"]:
            self.assertTrue(entry.startswith("qwencloud/"), entry)

    def test_multiple_providers_are_mixed(self):
        gen("qwen,openai,xai", self.out)
        chains = self.load()["tiers"]
        joined = " ".join(chains["default"] + chains["heavy"])
        self.assertIn("qwencloud/", joined)
        self.assertIn("openai/", joined)
        self.assertIn("xai/", joined)

    def test_gpt_is_first_in_every_tier_when_openai_selected(self):
        """GPT 우선 정책 — openai 를 고르면 두 tier 모두 1순위여야 한다."""
        gen("qwen,openai,xai", self.out)
        chains = self.load()["tiers"]
        self.assertTrue(chains["default"][0].startswith("openai/"), chains["default"])
        self.assertTrue(chains["heavy"][0].startswith("openai/"), chains["heavy"])

    def test_fallback_after_gpt_is_a_different_provider(self):
        """같은 프로바이더를 연달아 두면 한도에 함께 막혀 폴백이 무의미하다."""
        gen("qwen,openai,xai", self.out)
        heavy = self.load()["tiers"]["heavy"]
        self.assertGreater(len(heavy), 1, heavy)
        self.assertFalse(heavy[1].startswith("openai/"), heavy)

    def test_unknown_provider_warns_but_succeeds(self):
        r = gen("qwen,nosuchprovider", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nosuchprovider", r.stderr)

    def test_all_unknown_providers_fail(self):
        r = gen("nosuch,alsonope", self.out)
        self.assertEqual(r.returncode, 65)

    def test_output_is_valid_json_with_comment(self):
        gen("openai", self.out)
        policy = self.load()
        self.assertIn("_comment", policy)
        self.assertIsInstance(policy["tiers"]["default"], list)

    def test_empty_tier_chain_warns_but_succeeds(self):
        r = gen("xai", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("비었다", r.stderr)
        self.assertEqual(self.load()["tiers"]["default"], [])

    def test_malformed_table_reports_corruption(self):
        table = Path(self.tmp.name) / "provider-models.json"
        table.write_text("{ 손상된 JSON")
        r = gen_with_table("qwen", self.out, Path(self.tmp.name))
        self.assertEqual(r.returncode, 66)
        self.assertIn("손상", r.stderr)

    def test_non_array_tier_fails(self):
        table = Path(self.tmp.name) / "provider-models.json"
        mapping = json.loads((GEN.parent / "provider-models.json").read_text())
        mapping["providers"]["qwen"]["heavy"] = "배열이 아닌 값"
        table.write_text(json.dumps(mapping))
        r = gen_with_table("qwen", self.out, Path(self.tmp.name))
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
