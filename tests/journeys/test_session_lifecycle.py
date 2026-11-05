"""A session's lifecycle record: prompts, stops and provider observations opening
and closing its turn, session end releasing its pages, and the prompt that serves a
resumed session's pages again."""

import json
import os
import subprocess

from interact_support import (
    LEAF_COMMAND,
    STATED_TIMEOUT,
    start_server_command,
    wait_for,
)

from leaf import server as server_model
from leaf import service as service_model
from leaf import state as cleanup_model


def test_the_server_a_prompt_hook_starts_lives_as_long_as_its_session(claimed):
    """The prompt hook is a process of its own that exits once it answers. The
    server it starts for a resumed session lives by the session's process, which
    the harness names to the hook, so it outlives the hook, and it retires when the
    session ends again, as one `leaf server start` started does."""
    started = start_server_command(claimed, session_id="s1")
    assert started.returncode == 0, started.stderr
    for outage in ("first", "second"):
        cleanup_model.end_harness_instance("s1")
        wait_for(
            lambda: server_model.running_server(claimed),
            lambda running: not running,
            failure=f"the server did not retire after the {outage} session ended",
        )
        hook = subprocess.run(
            [*LEAF_COMMAND, "hook", "--harness", "claude-code"],
            input=json.dumps(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "s1",
                    "prompt_id": f"{outage}-resumed",
                }
            ),
            env=os.environ | {"CLAUDE_PID": str(os.getpid())},
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (hook.returncode, hook.stdout) == (0, ""), hook.stderr
        assert server_model.running_server(claimed), outage
        claim = service_model.page_claim(claimed)
        assert service_model.claim_is_active(claim), outage
        assert claim is not None
        assert (claim["pid"], claim["turn"]) == (os.getpid(), f"{outage}-resumed")
