"""A stand-in for Leaf's Claude Code hooks module, for a session no module serves:
the suite's sessions, and the demo recording's own (`commands/site/demo.py`)."""

import threading
from contextlib import contextmanager

from leaf.agents import completions
from leaf.commands.hooks import cmd_fork


@contextmanager
def claude_code_module(session: str, reply: str | dict):
    """Stand in for Leaf's Claude Code hooks module (`hooks/claude-code.ts`), which
    `tests/process/test_interact_claude_code_module.py` holds to the same: run each
    completion Leaf lists for `session` (`completions.listed`) as the text `reply`, or
    the failure it names (`{"failed": …}`), with the model's usage of 300 tokens in and
    12 out, and report it as the module does (`hooks.cmd_fork`), yielding the requests
    it took, each with its `id` and `request`."""
    asked = []
    done = threading.Event()
    answered = reply if isinstance(reply, dict) else {"text": reply}
    queued = completions.watch(session)

    def answer() -> None:
        while not done.is_set():
            mark = queued.mark()
            for instruction in completions.listed(session):
                asked.append(
                    {
                        "id": instruction["basis"]["completion"],
                        "request": instruction["request"],
                    }
                )
                cmd_fork(
                    {
                        "session_id": session,
                        "done": instruction["id"],
                        "do": instruction["do"],
                        "basis": instruction["basis"],
                        **answered,
                        "usage": {
                            "input_tokens": 300,
                            "output_tokens": 12,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                        },
                        "elapsed_ms": 900,
                    },
                )
            # A tenth of a second at most, so the context's exit ends the thread.
            queued.wait(mark, 0.1)

    worker = threading.Thread(target=answer, daemon=True)
    worker.start()
    try:
        yield asked
    finally:
        done.set()
        worker.join()
        queued.close()
