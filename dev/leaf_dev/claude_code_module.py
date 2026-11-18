"""A stand-in for Leaf's Claude Code hooks module, for a session no module serves:
the suite's sessions, and the demo recording's own (`commands/site/demo.py`)."""

import threading
from contextlib import contextmanager

from leaf import completions


@contextmanager
def claude_code_module(session: str, reply: str | dict):
    """Stand in for Leaf's Claude Code hooks module (`hooks/claude-code.ts`), which
    `tests/process/test_interact_claude_code_module.py` holds to the same: answer each
    completion `session` is asked (`completions`) with the text `reply`, or the failure
    it names (`{"failed": …}`), as the model's usage of 300 tokens in and 12 out, and
    yield the requests it took, each with its `id` and `request`."""
    asked = []
    done = threading.Event()
    answered = reply if isinstance(reply, dict) else {"text": reply}
    queued = completions.watch(session)

    def answer() -> None:
        while not done.is_set():
            mark = queued.mark()
            for request in completions.pending(session):
                asked.append(request)
                completions.cmd_reply(
                    session,
                    {
                        "completion": request["id"],
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
