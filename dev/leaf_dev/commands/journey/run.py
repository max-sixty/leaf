"""One user's journey through a Leaf page, run on any harness, each step timed from
the page's own record and checked.

    uv run leaf-dev journey run TARGET [--browser | --http] [--release RELEASE]
                                   [--sandbox] [--case waiting|working]

TARGET names what answers the user's release ask and the steps around it, which
`_journey`'s header describes:

- `claude-code`: an interactive Claude Code session in a tmux pane
  (`_claude_code`);
- `codex-app-server` or `codex-queue`: a Codex task reaching Leaf through that
  transport (`_codex`): App Server's, as `leaf codex launch` and leaf.page run
  Codex, or the queue, as the desktop app and IDE extension do;
- `pi`: a Pi session in RPC mode (`_pi`);
- `website-adapter`: the website's adapter on this machine, against the host's
  Codex login, with no Worker, container limits, credential proxy or Docker;
- `website-worker`: the built site through the local Worker and its page container;
- an origin such as `https://leaf.page`: the deployed website, at `--release` or
  whichever release it serves.

`--sandbox` runs the session's shell commands in its harness's sandbox.

The JSON on stdout is the journey's sample (`User.sample`). Each sample is also
kept on the machine that ran it (`samples_path`), and `leaf-dev journey chart`
draws when each milestone came, from the kept samples of the latest version each
target ran at each end, as an `lf-chart` element for a page.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from datetime import datetime

import click

from leaf_dev.browser import headless_shell
from leaf_dev.commands.journey._journey import (
    CASES,
    HARNESS_TARGETS,
    BrowserEnd,
    Session,
    User,
    samples_path,
)
from leaf_dev.website import (
    LocalWorker,
    agent_session,
    local_adapter,
    local_worker,
    start_direct_agent,
)


def website_session(
    browser, release: str | None, *, origin: str, direct_agent: bool
) -> tuple[Session, str]:
    """A user's session on the website at `origin`, and the release it serves."""
    context, page, failures, url, state_url, state = agent_session(
        browser, release, origin=origin, direct_agent=direct_agent
    )
    if release is None:
        release = state.get("release")
        if not isinstance(release, str):
            raise RuntimeError(f"{state_url} returned no release")
    # The comment is posted under the layer its own container holds, not the edge's.
    headers = {"Leaf-Layer": state["layer"]["generation"], "Leaf-Release": release}
    after_post = (
        (lambda comment: start_direct_agent(context, url, comment))
        if direct_agent
        else None
    )
    session = Session(
        context, page, failures, url, state_url, state, headers, after_post
    )
    return session, release


@contextmanager
def target_session(
    browser,
    target: str,
    release: str | None,
    *,
    sandbox: bool,
) -> Generator[tuple[User, dict, Callable[[], None]]]:
    """The user at the page TARGET answers, what names TARGET in the journey's
    output (`target` the same across runs, as a local server's `origin` is not), and
    the journey's steps."""
    if target in HARNESS_TARGETS:
        _, harness, transport = HARNESS_TARGETS[target]
        named: dict = {"target": target, "harness": harness}
        if harness == "claude-code":
            from leaf_dev.commands.journey._claude_code import answering

            answered = answering(browser, sandbox=sandbox)
            named |= {"sandbox": True} if sandbox else {}
        elif harness == "pi":
            from leaf_dev.commands.journey._pi import answering

            answered = answering(browser)
        else:
            from leaf_dev.commands.journey._codex import answering

            assert transport is not None
            answered = answering(browser, transport, sandbox=sandbox)
            named |= {"transport": transport}
            named |= {"sandbox": True} if sandbox else {}
        with answered as (user, run):
            yield user, named, run
        return
    if target == "website-adapter":
        serving = local_adapter()
    elif target == "website-worker":
        serving = local_worker()
    else:
        origin = target.rstrip("/")
        session, version = website_session(
            browser, release, origin=origin, direct_agent=False
        )
        user = User(BrowserEnd(session, None), version)
        yield (
            user,
            {"target": origin, "harness": "website", "origin": origin},
            user.release_alone,
        )
        return
    with serving as hosted:
        origin, built = (
            (hosted.origin, hosted.release)
            if isinstance(hosted, LocalWorker)
            else hosted
        )
        session, version = website_session(
            browser,
            built if target == "website-adapter" else release or built,
            origin=origin,
            direct_agent=target == "website-adapter",
        )
        user = User(BrowserEnd(session, None), version)
        yield (
            user,
            {"target": target, "harness": "website", "origin": origin},
            user.release_alone,
        )


@click.command("run")
@click.argument("target")
@click.option(
    "--release",
    help="At an origin, require this release (default: whichever it serves).",
)
@click.option(
    "--sandbox",
    is_flag=True,
    help="On claude-code or a codex target, run the session's shell commands in its "
    "harness's sandbox, configured as the README says.",
)
@click.option(
    "--case",
    type=click.Choice(CASES),
    default="waiting",
    help="On a harness, whether the release ask reaches it waiting or working on the "
    "user's own turn.",
)
@click.option(
    "--browser/--http",
    default=None,
    help="Where the user is: in Chrome, every comment typed as a user types it and what the "
    "page shows timed (a website's only end), or posting as the page's tab does, with "
    "no browser (a harness's default).",
)
def journey(
    target: str,
    release: str | None,
    sandbox: bool,
    case: str,
    browser: bool | None,
) -> None:
    """Run the user's journey against TARGET, checking each step, and print its
    timed sample.

    TARGET is `claude-code`, `codex-app-server`, `codex-queue` or `pi` for a session
    of that harness on this working tree, `website-adapter` for the website's adapter
    on this machine, `website-worker` for the built site through the local Worker,
    or a website origin. A harness's user posts its comments over HTTP unless
    `--browser` puts them in Chrome.
    """
    harness = HARNESS_TARGETS[target].harness if target in HARNESS_TARGETS else None
    if sandbox and harness not in ("claude-code", "codex"):
        raise click.UsageError("--sandbox is an option of claude-code and codex")
    website = harness is None
    if website and case == "working":
        raise click.UsageError("a website's journey has no terminal to start a turn")
    if website and browser is False:
        raise click.UsageError(
            "a website's journey is its page in a browser, so it has no --http"
        )
    with ExitStack() as stack:
        chromium = stack.enter_context(headless_shell()) if website or browser else None
        user, named, run = stack.enter_context(
            target_session(
                chromium,
                target,
                release,
                sandbox=sandbox,
            )
        )
        user.case = case
        try:
            run()
            sample = {**named, **user.sample()}
        finally:
            user.end.close()
    print(json.dumps(sample, indent=2))
    samples = samples_path()
    samples.parent.mkdir(parents=True, exist_ok=True)
    with samples.open("a") as kept:
        kept.write(
            json.dumps({"at": datetime.now().astimezone().isoformat(), **sample}) + "\n"
        )
    print(f"kept in {samples}", file=sys.stderr)
