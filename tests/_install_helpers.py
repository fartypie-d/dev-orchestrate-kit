"""install.sh 테스트가 공유하는 격리된 실행 헬퍼."""
import os
import subprocess
import tempfile
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT = 30


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
    with tempfile.TemporaryDirectory() as home:
        env = {"INSTALL_DRY_RUN": "1", "HOME": home, **overrides}
        return run_install(args, env=env)


def selftest_menu(**overrides):
    """메뉴 전용 자가검증 훅을 실행한다."""
    return run_install((), env={"INSTALL_SELFTEST_MENU": "1", **overrides})
