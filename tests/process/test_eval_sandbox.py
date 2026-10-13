"""An eval child's sandbox keeps samples from sharing files in `/tmp`."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from leaf_dev.arms import claude_child


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS sandbox only")
def test_a_child_writes_its_own_directories_and_no_shared_tmp_name():
    """A child placed under `/tmp` still owns its workspace and home; a fixed name
    another sample could also write is refused; Claude Code's own per-user
    directory stays writable."""
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="leaf-sandbox-") as root:
        cwd = Path(root) / "cwd"
        cwd.mkdir()
        spec = claude_child(cwd, "")
        assert spec["args"][0] == "sandbox-exec"
        profile = spec["args"][2]
        shared = Path(f"/tmp/leaf-sandbox-shared-{os.getpid()}")
        claude = Path(f"/tmp/claude-{os.getuid()}")

        def writes(path: Path) -> bool:
            return (
                subprocess.run(
                    ["sandbox-exec", "-p", profile, "/bin/sh", "-c", f": > '{path}'"],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )

        try:
            assert writes(cwd / "tmp" / "scratch.py")
            assert writes(Path(spec["env"]["HOME"]) / "note")
            assert not writes(shared)
            assert not shared.exists()
            claude.mkdir(exist_ok=True)
            assert writes(claude / f"leaf-sandbox-{os.getpid()}")
        finally:
            (claude / f"leaf-sandbox-{os.getpid()}").unlink(missing_ok=True)
