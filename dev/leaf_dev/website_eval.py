"""Score the hosted agent's actual replies, including the opening users see.

The arm's WebsiteCodexHarness owns the model, instructions, delivery and reply
projection. A subprocess imports it normally from the arm's worker directory,
with a private login home. The adapter's private page diagnostics retain published
reply updates, native status and follower completion; the evaluator queries that
evidence without replacing the adapter's classes or lifecycle.
Promptfoo judges meaning, while fixed checks require completed exact-input replies.
Each turn's time to its first words, to text showing in the reply, and to its
completed answer joins the metadata as `timings`, read from the adapter's own
records.
No Worker, browser or page-authoring task is needed for these response evals.
"""

import json
import os
import signal
import subprocess
import sys
import time
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
from leaf_dev.commands.distribution import current_kernel
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
    payload = current_kernel(payload)
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

        result = json.loads((work / "result.json").read_text())
        result["metadata"]["timings"] = turn_timings(work / "adapter.log")
        return result


# The milestones each hosted turn records (`HostedTurn.observe`, `.observe_reply`,
# `.commit`), by the name `turn_timings` gives each.
TURN_MILESTONES = {
    "turn_first_model_message": "first_words",
    "turn_reply_first_text_published": "shown",
    "turn_stream_completed": "completed",
}


def turn_timings(log: Path) -> list[dict]:
    """Each hosted turn's milestones in milliseconds from its start, read from the
    adapter's own records: when the model's first words arrived and whether they
    were an opening (`commentary`) or the answer (`final_answer`), when text first
    showed in the user's reply, and when the turn completed with its answer."""
    turns: dict[str, dict] = {}
    for line in log.read_text().splitlines():
        if not line.startswith('{"component":"leaf-agent"'):
            continue
        record = json.loads(line)
        if (name := TURN_MILESTONES.get(record["event"])) is None:
            continue
        turn = turns.setdefault(record["turnId"], {"turn": record["turnId"]})
        turn[f"{name}_ms"] = record["durationMs"]
        if name == "first_words":
            turn["first_words_phase"] = record["phase"]
    return list(turns.values())


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
    from leaf.interaction_log import read_interactions
    from leaf.thread import successful_replies
    from leaf_dev.commands.preview import terminated
    from leaf_dev.review_scenario import post

    try:
        kinds = leaf_website.HOSTED_TURN_RECORDS
    except AttributeError as error:
        raise RuntimeError(
            "This arm does not produce hosted-turn diagnostics; it cannot run the "
            "hosted reply experiment. Select an arm with producer-owned evidence."
        ) from error
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
    replies, inputs = [], []
    agent = leaf_website.WebsiteCodexHarness(log_path=work / "codex.log")
    signal.signal(signal.SIGTERM, terminated)
    try:
        for number, question in enumerate(CASES[request["case"]]):
            event = post(request["url"], f"website-{number}", question)
            inputs.append(event)
            agent.attach(page, event)
            deadline = time.monotonic() + TURN_LIMIT
            while not any(
                record["type"] == kinds["following"] and record.get("eventId") == event
                for record in read_interactions(page)
            ):
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
            else:
                replies.append(
                    {
                        "question": question,
                        "replies": successful_replies(read_events(page), event),
                    }
                )
                continue
            # A timeout remains incomplete evidence for the fixed grade.
            break
    finally:
        agent.close()
        (work / "events.jsonl").write_text((page / "events.jsonl").read_text())
    records = [
        record for record in read_interactions(page) if record.get("eventId") in inputs
    ]
    (work / "observations.jsonl").write_text((page / "observations.jsonl").read_text())
    ended = {
        record["turnId"]: record["completed"]
        for record in records
        if record["type"] == kinds["following"]
    }
    statuses = [
        record["status"]
        for record in records
        if record["type"] == kinds["terminal"] and ended.get(record["turnId"])
    ]
    output = {
        "model": leaf_website.HOSTED_MODEL,
        "turns": replies,
        "shown_updates": [
            record["reply"] for record in records if record["type"] == kinds["reply"]
        ],
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
