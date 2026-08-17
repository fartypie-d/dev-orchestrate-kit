"""phase-tools.py dashboard-mounts 서브커맨드 계약을 검증한다.

Phase 7 동결 테스트 — 오케스트레이터가 작성·동결(PITFALLS 14). 위임의 수정 금지.

대시보드는 프로젝트 진행내역 문서를 **호스트 절대경로 그대로** 연다
(usage-dashboard app/main.py `_progress_docs_root`). 따라서 컨테이너에 같은 절대경로가
마운트돼 있어야 하고, 그 마운트 목록은 오케스트레이트 레지스트리에서 나와야 한다.

실제 ~/.local/state 를 건드리지 않도록 모든 실행에 ORCH_STATE_DIR 를 주입한다.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # PyYAML 은 킷의 의존성이 아니다 — 있으면 구조까지 검증한다.
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


KIT = Path(__file__).resolve().parents[1]
TOOL = KIT / "core" / "scripts" / "phase-tools.py"
SCRATCH_ROOT = KIT / ".orchestrate" / "mut7"
RUN_TIMEOUT = 30

OVERRIDE_NAME = "dashboard-compose.override.yml"
REGISTRY_MOUNTPOINT = "/data/orchestrate-registry"


def temporary_directory():
    """저장소 안의 격리 스크래치 디렉터리를 만든다 (/tmp 는 위임이 못 쓴다)."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=SCRATCH_ROOT)


class DashboardMountsTest(unittest.TestCase):
    def run_tool(self, state_dir, *args, cwd=None):
        env = os.environ.copy()
        env["ORCH_STATE_DIR"] = str(state_dir)
        return subprocess.run(
            ["python3", str(TOOL), "dashboard-mounts", *args],
            capture_output=True, text=True, env=env, timeout=RUN_TIMEOUT,
            cwd=None if cwd is None else str(cwd),
        )

    def details(self, result, extra=""):
        return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n{extra}"

    def write_project(self, state_dir, name, root, docs_dir="DOCs", make_docs=True):
        """레지스트리 항목을 만들고, 필요하면 실제 DOCs 디렉터리도 만든다."""
        registry = Path(state_dir) / "registry"
        registry.mkdir(parents=True, exist_ok=True)
        (registry / f"{name}.json").write_text(json.dumps({
            "project": name,
            "root": str(root),
            "default_branch": "main",
            "docs_dir": docs_dir,
            "next_phase": 1,
            "active": [],
        }), encoding="utf-8")
        docs = Path(root) / docs_dir
        if make_docs:
            docs.mkdir(parents=True, exist_ok=True)
        return docs

    def write_entry(self, state_dir, name, payload):
        """임의 필드로 레지스트리 항목만 만든다 (경계값 검증용)."""
        registry = Path(state_dir) / "registry"
        registry.mkdir(parents=True, exist_ok=True)
        (registry / f"{name}.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def override_path(self, state_dir):
        return Path(state_dir) / OVERRIDE_NAME

    def parsed(self, text):
        """PyYAML 이 있으면 usage-dashboard 서비스 블록을 돌려준다."""
        if yaml is None:
            return None
        return yaml.safe_load(text)["services"]["usage-dashboard"]

    def test_writes_override_with_registry_and_docs_mounts(self):
        """존재하는 DOCs 는 절대경로 그대로, 레지스트리는 마운트+환경변수로 배선된다."""
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            alpha_docs = self.write_project(
                state_dir, "alpha", Path(scratch) / "alpha")
            beta_docs = self.write_project(
                state_dir, "beta", Path(scratch) / "beta", docs_dir="docs")

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertTrue(override.exists(), details)
            # stdout 은 install.sh 가 읽는다 — 생성 경로 한 줄.
            self.assertIn(str(override), result.stdout, details)

            # 문서는 호스트 절대경로 → 컨테이너 같은 절대경로, 읽기 전용.
            self.assertIn(f"{alpha_docs}:{alpha_docs}:ro", text, details)
            self.assertIn(f"{beta_docs}:{beta_docs}:ro", text, details)
            # 서브모듈 compose 에는 레지스트리 배선이 아예 없다 — 여기서 채운다.
            self.assertIn(
                f"{state_dir / 'registry'}:{REGISTRY_MOUNTPOINT}:ro", text, details)
            self.assertIn(f"USAGE_REGISTRY_DIR={REGISTRY_MOUNTPOINT}", text, details)
            # 프로젝트명 오름차순 — 결정적 출력.
            self.assertLess(text.index(str(alpha_docs)), text.index(str(beta_docs)),
                            details)

            service = self.parsed(text)
            if service is not None:
                volumes = service["volumes"]
                self.assertIn(f"{alpha_docs}:{alpha_docs}:ro", volumes, details)
                self.assertIn(f"{beta_docs}:{beta_docs}:ro", volumes, details)
                self.assertIn(
                    f"{state_dir / 'registry'}:{REGISTRY_MOUNTPOINT}:ro", volumes,
                    details)
                self.assertIn(f"USAGE_REGISTRY_DIR={REGISTRY_MOUNTPOINT}",
                              service["environment"], details)
                # 원본 compose 의 다른 키를 덮어쓰지 않는다.
                self.assertNotIn("image", service, details)
                self.assertNotIn("ports", service, details)

    def test_skips_missing_docs_dir(self):
        """존재하지 않는 root/docs_dir 는 절대 마운트하지 않는다.

        docker bind 는 없는 호스트 경로를 root 소유 빈 디렉터리로 만들어 버린다
        (되돌리려면 sudo). 등록만 되고 체크아웃이 없는 프로젝트가 흔하다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            live_docs = self.write_project(
                state_dir, "alive", Path(scratch) / "alive")
            ghost_docs = self.write_project(
                state_dir, "ghost", Path(scratch) / "ghost", make_docs=False)

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{live_docs}:{live_docs}:ro", text, details)
            self.assertNotIn(str(ghost_docs), text, details)
            # 생성기가 없는 경로를 만들어 놓아서도 안 된다.
            self.assertFalse(ghost_docs.exists(), details)

    def test_empty_registry_writes_no_file(self):
        """마운트할 것이 없으면 파일을 만들지 않고, 낡은 파일은 지운다.

        `volumes: []` 같은 빈 키는 compose 파싱을 깨뜨려 컨테이너 기동 자체를 막는다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            (state_dir / "registry").mkdir(parents=True, exist_ok=True)
            stale = self.override_path(state_dir)
            stale.write_text(
                "services:\n  usage-dashboard:\n    volumes:\n"
                "      - /gone/DOCs:/gone/DOCs:ro\n", encoding="utf-8")

            result = self.run_tool(state_dir)
            details = self.details(result)

            self.assertEqual(result.returncode, 0, details)
            self.assertFalse(stale.exists(), details)
            self.assertEqual(result.stdout.strip(), "", details)

    def test_print_path_does_not_generate(self):
        """--print-path 는 경로만 알려준다 — install.sh 존재 확인용."""
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            self.write_project(state_dir, "alpha", Path(scratch) / "alpha")

            result = self.run_tool(state_dir, "--print-path")
            details = self.details(result)

            self.assertEqual(result.returncode, 0, details)
            self.assertEqual(result.stdout.strip(),
                             str(self.override_path(state_dir)), details)
            self.assertFalse(self.override_path(state_dir).exists(), details)

    def test_broken_registry_entry_does_not_abort(self):
        """깨진 JSON 하나가 대시보드 기동을 막으면 안 된다 — 건너뛰고 계속."""
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            (state_dir / "registry" / "broken.json").write_text(
                "{ not json", encoding="utf-8")

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            self.assertRegex(result.stderr, r"broken", details)


    def test_missing_docs_dir_warns_on_stderr(self):
        """제외된 프로젝트는 반드시 알려야 한다 — 침묵하면 증상이 그대로 재현된다.

        이 페이즈가 고치려는 증상이 곧 "UI 에 문서가 없는데 이유를 알 수 없음"이다.
        마운트에서 조용히 빠지면 사용자는 도구를 돌리고도 원인을 알 방법이 없다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            live_docs = self.write_project(
                state_dir, "alive", Path(scratch) / "alive")
            self.write_project(
                state_dir, "ghost", Path(scratch) / "ghost", make_docs=False)

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{live_docs}:{live_docs}:ro", text, details)
            self.assertRegex(result.stderr, r"ghost", details)

    def test_docs_dir_outside_root_is_not_mounted(self):
        """docs_dir 는 root 하위여야 한다 — 절대경로·`..` 는 봉쇄를 무력화한다.

        `Path(root) / "/etc"` 는 `/etc` 가 되고 `Path(root) / "../.ssh"` 는 밖을
        가리킨다. 둘 다 "존재하는 디렉터리" 검사를 통과해 그대로 컨테이너에 마운트된다
        ($HOME 통째 마운트를 기각하고 화이트리스트로 간 설계 의도가 무너진다).
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            outside = Path(scratch) / "outside"
            outside.mkdir(parents=True, exist_ok=True)
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            for name, docs_dir in (("absolute", str(outside)),
                                   ("climb", "../outside")):
                self.write_entry(state_dir, name, {
                    "project": name,
                    "root": str(Path(scratch) / name),
                    "default_branch": "main",
                    "docs_dir": docs_dir,
                    "next_phase": 1,
                    "active": [],
                })

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            self.assertNotIn(str(outside), text, details)

    def test_newline_in_path_cannot_inject_compose_entries(self):
        """문자열 조립 YAML 에 개행이 든 경로가 새 항목을 주입하면 안 된다.

        건너뛰든 따옴표로 감싸든 상관없다 — 결과에 독립된 volumes 항목이
        생기지만 않으면 된다 (`- /:/:rw` 주입이 실제로 가능한 형태였다).
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            evil_root = Path(scratch) / "inject"
            evil_docs_dir = "DOCs\n      - injectedmarker"
            (evil_root / evil_docs_dir).mkdir(parents=True, exist_ok=True)
            self.write_entry(state_dir, "inject", {
                "project": "inject",
                "root": str(evil_root),
                "default_branch": "main",
                "docs_dir": evil_docs_dir,
                "next_phase": 1,
                "active": [],
            })

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            self.assertNotIn("\n      - injectedmarker", text, details)

            service = self.parsed(text)
            if service is not None:
                for volume in service["volumes"]:
                    self.assertFalse(volume.startswith("injectedmarker"), details)

    def test_empty_docs_dir_does_not_mount_project_root(self):
        """`docs_dir` 가 비면 root 전체가 마운트된다 — 봉쇄 검사를 통과해 버린다.

        `Path(root) / ""` 는 root 그대로라 "root 하위" 검사를 통과하고, root 에는
        `.git`·`.env` 가 들어 있다. $HOME 통째 마운트를 기각한 이유와 같은 노출이다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            bare_root = Path(scratch) / "bareroot"
            (bare_root / ".git").mkdir(parents=True, exist_ok=True)
            (bare_root / ".env").write_text("TOKEN=x\n", encoding="utf-8")
            self.write_entry(state_dir, "bare", {
                "project": "bare",
                "root": str(bare_root),
                "default_branch": "main",
                "docs_dir": "",
                "next_phase": 1,
                "active": [],
            })

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            self.assertNotIn(str(bare_root), text, details)
            # 제외했으면 침묵하지 말 것.
            self.assertRegex(result.stderr, r"bare", details)

    def test_symlinked_root_mounts_source_resolved_target_as_registered(self):
        """심링크 root 는 **비대칭 마운트**여야 한다 — 소스는 실경로, 타깃은 등록된 경로.

        타깃(컨테이너 쪽)은 대시보드가 여는 경로여야 한다: 대시보드는
        `Path(root) / docs_dir` 를 resolve 없이 그대로 연다
        (usage-dashboard app/main.py `_progress_docs_root`). 실경로로 마운트하면
        컨테이너 안에 그 경로가 없어 "문서 없음"이 그대로 남는다.

        소스(호스트 쪽)는 반대로 resolve 한 실경로여야 한다: 심링크를 그대로 두면
        override 생성 후 `docker compose up` 사이에 링크를 바꿔치기해 root 밖 실체를
        마운트할 수 있다 (검증은 생성 시점에만 도니 봉쇄 계약이 깨진다).
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            real_root = Path(scratch) / "realproj"
            (real_root / "DOCs").mkdir(parents=True, exist_ok=True)
            link_root = Path(scratch) / "linkproj"
            link_root.symlink_to(real_root, target_is_directory=True)
            self.write_entry(state_dir, "linked", {
                "project": "linked",
                "root": str(link_root),
                "default_branch": "main",
                "docs_dir": "DOCs",
                "next_phase": 1,
                "active": [],
            })

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")
            link_docs = link_root / "DOCs"
            real_docs = real_root / "DOCs"

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{real_docs}:{link_docs}:ro", text, details)
            # 링크 경로를 소스로 쓰면 bind 시점 재해석으로 봉쇄가 뚫린다.
            self.assertNotIn(f"{link_docs}:{link_docs}:ro", text, details)

    def test_relative_root_is_not_mounted(self):
        """`root` 가 상대경로면 마운트하지 말고 알려야 한다.

        검증은 `resolve()` 값으로 통과하는데 마운트 문자열엔 상대경로가 박힌다 —
        compose 가 어디서 뜨느냐에 따라 엉뚱한 경로가 붙거나 아무것도 안 붙는다.
        (컨테이너 쪽 경로는 절대경로여야 한다.)
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            (Path(scratch) / "relproj" / "DOCs").mkdir(parents=True, exist_ok=True)
            self.write_entry(state_dir, "relative", {
                "project": "relative",
                "root": "relproj",
                "default_branch": "main",
                "docs_dir": "DOCs",
                "next_phase": 1,
                "active": [],
            })

            # 상대 root 가 실제로 해석되는 위치에서 실행한다 (최악의 조건).
            result = self.run_tool(state_dir, cwd=scratch)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            self.assertNotIn("relproj/DOCs", text, details)
            self.assertRegex(result.stderr, r"relative", details)

    def test_duplicate_mount_path_is_reported(self):
        """같은 경로로 수렴한 프로젝트를 조용히 버리지 말 것.

        중복은 한 번만 마운트하면 되지만, 어떤 프로젝트가 빠졌는지는 알려야 한다 —
        모르면 "왜 저 프로젝트만 문서가 없지"로 되돌아간다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            shared_root = Path(scratch) / "shared"
            docs = self.write_project(state_dir, "dupalpha", shared_root)
            self.write_project(state_dir, "dupbeta", shared_root)

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertEqual(text.count(f"{docs}:{docs}:ro"), 1, details)
            self.assertRegex(result.stderr, r"dupbeta", details)

    def test_path_with_colon_keeps_override_parseable(self):
        """콜론이 든 경로를 그대로 흘리면 compose 파싱이 깨진다.

        `- /a/My: Weird/DOCs:...:ro` 는 YAML 매핑으로 읽혀
        `mapping values are not allowed here` 로 컨테이너가 아예 안 뜬다.
        건너뛰든 인용하든 상관없다 — 파일이 계속 파싱되기만 하면 된다.
        """
        with temporary_directory() as scratch:
            state_dir = Path(scratch) / "state"
            good_docs = self.write_project(
                state_dir, "good", Path(scratch) / "good")
            odd_docs = self.write_project(
                state_dir, "odd", Path(scratch) / "oddproj",
                docs_dir="My: Weird Dir")

            result = self.run_tool(state_dir)
            override = self.override_path(state_dir)
            text = override.read_text(encoding="utf-8") if override.exists() else ""
            details = self.details(result, f"override:\n{text}")

            self.assertEqual(result.returncode, 0, details)
            self.assertIn(f"{good_docs}:{good_docs}:ro", text, details)
            # 인용 없이 날것으로 흘린 형태는 YAML 이 매핑으로 읽는다.
            self.assertNotIn(f"\n      - {odd_docs}:{odd_docs}:ro", text, details)

            service = self.parsed(text)
            if service is not None:
                self.assertIn(f"{good_docs}:{good_docs}:ro", service["volumes"],
                              details)


if __name__ == "__main__":
    unittest.main()
