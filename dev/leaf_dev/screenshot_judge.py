"""Configure native screenshot judges; `screenshot_judge.mjs` owns their lifetime.

Standard assertions grant the run's screenshot tree. UI review supplies one anonymous
packet at assertion time. Both use the same profile and isolated login setup; the
Promptfoo Codex provider still owns execution, structured output and accounting.
"""

import json
import shutil
import sys
from pathlib import Path


def screenshot_judge(screenshots: Path | None, login: Path) -> dict:
    """Prepare an isolated seed that keeps the host's login shared.

    The caller retires the seed with its run's temporary resources. Import the
    current harness setup here, before UI review freezes its configuration, so a
    staged helper's later calls depend only on the prepared seed and standard library.
    """
    from leaf_dev.arms import JUDGE_MODELS, codex_home, codex_program

    return {
        "id": Path(__file__).with_suffix(".mjs").as_uri(),
        "config": {
            "model": JUDGE_MODELS["codex"],
            "codex_path_override": str(codex_program()),
            "screenshots": str(screenshots) if screenshots is not None else None,
            "pythonExecutable": sys.executable,
            "login": str(codex_home(login)),
        },
    }


def native_config(home: Path, config: dict) -> dict:
    """Seed the disposable home and configure the native Codex provider.

    `:minimal` supplies runtime paths, excluding the repository. Codex executes
    itself to start its sandbox helper, so grant the resolved executable too.
    A permission profile replaces the older `sandbox_mode` setting.
    """
    screenshots = Path(config.pop("screenshots")).resolve()
    codex = home / ".codex"
    shutil.copytree(config.pop("login"), codex, symlinks=True)
    profile = "\n".join(
        [
            'default_permissions = "screenshots"',
            "",
            "[permissions.screenshots.filesystem]",
            '":minimal" = "read"',
            f'{json.dumps(f"{screenshots}/**")} = "read"',
            f'{json.dumps(config["codex_path_override"])} = "read"',
            "",
        ]
    )
    (codex / "config.toml").write_text(profile)
    return {
        **config,
        "working_dir": str(home),
        "skip_git_repo_check": True,
        "cli_env": {
            "HOME": str(home),
            "CODEX_HOME": str(codex),
        },
    }


if __name__ == "__main__":
    print(json.dumps(native_config(Path(sys.argv[1]), json.loads(sys.argv[2]))))
