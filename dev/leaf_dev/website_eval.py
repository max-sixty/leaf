"""Score the hosted agent's actual replies, including the opening users see.

The arm's WebsiteCodexHarness owns the model, instructions, delivery and reply
projection. A subprocess imports it normally from the arm's worker directory,
with a private login home. Observation retains native notifications and each
projected reply update; it changes neither the turn nor the text being scored.
Promptfoo judges meaning, while fixed checks require completed exact-input replies.
No Worker, browser or page-authoring task is needed for these response evals.
"""

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from leaf_dev import ROOT
from leaf_dev.arms import (
    TURN_LIMIT,
    build_source,
    codex_home,
    codex_program,
    environment,
    install_codex_plugin,
    scratch,
    serving,
)
from leaf_dev.eval_cases import definition

CASES = {
    name: tuple(case["inputs"]["questions"])
    for name, case in definition("website_eval")["cases"].items()
    if case["inputs"]
}


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    return ["completed", "replied", "page-unchanged"]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = "codex",
    condition: str = "leaf",
) -> dict:
    """Run the arm's hosted adapter against the local login and a seeded page."""
    with scratch(payload) as cwd:
        state, page = cwd / "state", cwd / "page"
        build_source(payload, state, ROOT / "evals/website-replies/page.html", page)
        home = cwd.parent / "home"
        home.mkdir()
        config = codex_home(
            home / ".codex", (payload / "worker/codex-config.toml").read_text()
        )
        env = environment(
            HOME=str(home),
            CODEX_HOME=str(config),
            XDG_STATE_HOME=str(state),
            LEAF_SITE_ROOT=str(page),
        )
        for key in (
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "ANTHROPIC_API_KEY",
            "UV_PROJECT_ENVIRONMENT",
            "VIRTUAL_ENV",
        ):
            env.pop(key, None)
        install_codex_plugin(codex_program(), payload, cwd=cwd, env=env)
        with (
            serving(payload, state, page) as url,
            (work / "adapter.log").open("w") as log,
            subprocess.Popen(
                [
                    "uv",
                    "run",
                    "-q",
                    "--no-dev",
                    "--project",
                    str(payload),
                    "--with-editable",
                    str(ROOT / "dev"),
                    "python",
                    "-m",
                    "leaf_dev.website_eval",
                ],
                stdin=subprocess.PIPE,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=payload / "worker",
                env=env,
            ) as child,
        ):
            try:
                child.communicate(
                    json.dumps(
                        {
                            "case": case,
                            "page": str(page),
                            "url": url,
                            "work": str(work),
                        }
                    ),
                    timeout=TURN_LIMIT * len(CASES[case]) + 30,
                )
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait()
            if child.returncode:
                raise subprocess.CalledProcessError(child.returncode, child.args)

        return json.loads((work / "result.json").read_text())


def grade(
    case: str, turns: list[dict], statuses: list[str], *, unchanged: bool
) -> dict[str, bool]:
    """Partial execution and failure receipts cannot establish successful replies."""
    count = len(CASES[case])
    return {
        "completed": len(turns) == count
        and len(statuses) == count
        and all(status == "completed" for status in statuses),
        "replied": len(turns) == count
        and all(len(turn["replies"]) == 1 for turn in turns),
        "page-unchanged": unchanged,
    }


def run_hosted() -> None:
    """The isolated child, importing the arm's production hosted implementation."""
    import leaf_website
    from leaf import __file__ as leaf_source
    from leaf.event_log import read_events
    from leaf.thread import successful_replies

    from leaf_dev.commands.preview import terminated
    from leaf_dev.review_scenario import post

    request = json.load(sys.stdin)
    os.environ.setdefault("LEAF_AGENT", leaf_website.WEBSITE_AGENT)
    page, work = Path(request["page"]), Path(request["work"])
    original = (page / "index.html").read_bytes()
    (work / "runtime.json").write_text(
        json.dumps(
            {
                "python": sys.executable,
                "leaf": leaf_source,
                "website": leaf_website.__file__,
                "leaf_command": leaf_website.LEAF_COMMAND,
                "leaf_root": subprocess.run(
                    [leaf_website.LEAF_COMMAND, "--root"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
            },
            indent=2,
        )
        + "\n"
    )
    updates, replies, statuses, finished = [], [], [], threading.Event()
    hosted_turn = leaf_website.HostedTurn

    class ObservedTurn(hosted_turn):
        def observe(self, message, update):
            with (work / "notifications.jsonl").open("a") as stream:
                stream.write(json.dumps(message) + "\n")
            super().observe(message, update)
            if message.get("method") == "turn/completed":
                statuses.append(message["params"]["turn"]["status"])

        def observe_reply(self, update, published):
            super().observe_reply(update, published)
            if published and update and update.get("message", {}).get("complete"):
                updates.append(update["message"])

    class ObservedHarness(leaf_website.WebsiteCodexHarness):
        def _run_follow_turn(self, turn):
            try:
                super()._run_follow_turn(turn)
            finally:
                finished.set()

    leaf_website.HostedTurn = ObservedTurn
    agent = ObservedHarness(log_path=work / "codex.log")
    signal.signal(signal.SIGTERM, terminated)
    try:
        for number, question in enumerate(CASES[request["case"]]):
            finished.clear()
            event = post(request["url"], f"website-{number}", question)
            agent.attach(page, event)
            if not finished.wait(TURN_LIMIT):
                break
            replies.append(
                {
                    "question": question,
                    "replies": successful_replies(read_events(page), event),
                }
            )
    finally:
        agent.close()
        (work / "events.jsonl").write_text((page / "events.jsonl").read_text())
    output = {
        "model": leaf_website.HOSTED_MODEL,
        "turns": replies,
        "shown_updates": updates,
    }
    response = {
        "output": json.dumps(output),
        "metadata": {
            "model": leaf_website.HOSTED_MODEL,
            "checks": grade(
                request["case"],
                replies,
                statuses,
                unchanged=original == (page / "index.html").read_bytes(),
            ),
        },
    }
    (work / "result.json").write_text(json.dumps(response, indent=2) + "\n")


if __name__ == "__main__":
    run_hosted()
