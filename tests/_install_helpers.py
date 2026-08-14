"""install.sh 테스트가 공유하는 격리된 실행 헬퍼."""
import os
import stat
import subprocess
import tempfile
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT = 30
SCRATCH_ROOT = KIT / ".orchestrate" / "mut6a"


def temporary_directory():
    """저장소 안의 격리 스크래치 디렉터리를 만든다."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=SCRATCH_ROOT)


def run_install(args=(), *, env=None, stdin=""):
    """주입 환경으로 install.sh를 실행한다."""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    command = ["bash", str(KIT / "install.sh"), *args]
    try:
        return subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            text=True,
            env=process_env,
            timeout=RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(
            f"install.sh 실행이 {RUN_TIMEOUT}초 안에 끝나지 않았다: {' '.join(command)}"
        ) from error


def parse_only(*args):
    """인자 파싱 훅만 실행한다."""
    return run_install(args, env={"INSTALL_PARSE_ONLY": "1"})


def dry_run(*args, **overrides):
    """임시 HOME에서 프리플라이트 계획 훅만 실행한다."""
    with temporary_directory() as home:
        env = {"INSTALL_DRY_RUN": "1", "HOME": home, **overrides}
        return run_install(args, env=env)


def selftest_menu(**overrides):
    """메뉴 전용 자가검증 훅을 실행한다."""
    return run_install((), env={"INSTALL_SELFTEST_MENU": "1", **overrides})


def run_install_with_fake_tools(*args, fake_tools, pseudo_tty=False,
                                minimal_path=False, stdin=None, fake_home_tools=None,
                                **overrides):
    """가짜 명령과 임시 HOME으로 실제 설치 흐름을 실행한다."""
    with temporary_directory() as home:
        bin_dir = Path(home) / "bin"
        bin_dir.mkdir()
        for name, content in fake_tools.items():
            path = bin_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        for name, content in (fake_home_tools or {}).items():
            path = Path(home) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        if minimal_path:
            for name in (
                "basename", "bash", "cat", "chmod", "cmp", "cp", "date", "dirname",
                "grep", "id", "mkdir", "mktemp", "mv", "rm", "sed", "tar", "uname",
            ):
                path = bin_dir / name
                if not path.exists():
                    path.write_text(f"#!/bin/bash\nexec /bin/{name} \"$@\"\n")
                    path.chmod(path.stat().st_mode | stat.S_IXUSR)
        env = {
            **os.environ,
            "HOME": home,
            "PATH": str(bin_dir) if minimal_path else str(bin_dir) + ":/usr/bin:/bin",
        }
        env.update(overrides)
        command = ["/bin/bash", str(KIT / "install.sh"), *args]
        if pseudo_tty:
            command = ["/usr/bin/script", "-q", "-c", " ".join(command), "/dev/null"]
        return subprocess.run(
            command, capture_output=True, text=True,
            input=("\n\n\n\ny\n" if pseudo_tty else "\n") if stdin is None else stdin,
            env=env, timeout=RUN_TIMEOUT,
        )
