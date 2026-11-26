"""What Leaf's Claude Code hooks module (`hooks/claude-code.ts`) runs for Leaf, and what
it reports back of each. Leaf's Python decides every model call the session
makes for it, as instructions, and the module runs each with Claude Code and reports
what it came to. The module adds only what it alone sees: the tool calls the main
thread is running, the main thread's last request, which a fork resends, and the end
of a main-loop turn the model answered.

Claude Code keeps the module it loaded until it loads another copy or the module's
own code changes (`hooks/claude-code.ts`), while a session whose hooks run a checkout
Claude Code loads in place (`--plugin-dir`) runs each hook from that checkout as it
stands, so its module can be older than the Python the module reports to. The user chose that the module only carry instructions, over running
each kind of fork's steps itself, so a change to what Leaf forks for, to what it asks
of a call, or to what it does with an answer changes only the Python, and an older
module runs it as it runs any instruction. The module changes only for a call or an
event Leaf starts to use: it reports a main-loop turn's end only where the model
answered, so a fork at an interrupted turn would need it to report that end too. An
instruction whose `do` an older module doesn't know comes back
`failed` at once, which moves what waits on it on as any failure does, so nothing
checks that the two agree.

An instruction is an object: its `id`, unique among the session's instructions, since
the module runs each id once however often it is listed; `do`, what to run;
`request`, which the module passes to that call as it stands; and `basis`, which the
module hands back untouched with every report of it, and whose `kind` names the step
that takes the result. A basis can come back to a newer Leaf than wrote it, as when
the follower that listed it runs on under an older one, so a change to a basis's shape
is one to this contract.

| `do` | the module runs `request` through | its report adds |
| --- | --- | --- |
| `report` | nothing | nothing more |
| `fork` | `$.model.fork`, a fork of the conversation that can call no tool (`fork`) | `answer`, or why there is none (`failed`); `usage`, `elapsed_ms` and what it resent of the main thread's conversation (`resent`) |
| `complete` | `$.model.complete`, on the session's model client | `text`, or `failed` with an API error's `status` and `error`; `usage`, `elapsed_ms` |

A report is `leaf hook --fork` (`hooks.cmd_fork`), whose payload carries `running`,
the calls the main thread is running, each `{"tool", "input"}`, and either `turn_end`,
as a main-loop turn the model answered ends, or the instruction's `done` (its id),
`do` and `basis` with what came of it. The answer may list instructions to run next
(`do`) and a line for Claude Code's debug log (`log`); the module reads nothing else
of it. Where the step that takes an instruction's result fails, the module reports it
once more with `failed`, so whatever waits on it moves on.
Turn ends report one at a time: the report, the instructions its answer lists and
their reports all finish before the next, and turns that end meanwhile report once
after. The pages follower lists instructions too (`hooks.cmd_pages`), the module's way
in for what the session's pages ask, such as a completion a page server wants or a
line fork for a round of the user's that awaits the agent's working line."""


def fork(instruction: str, prompt: str, basis: dict) -> dict:
    """The instruction `instruction` to fork the conversation with `prompt`, whose
    report comes back with `basis`.

    The fork thinks at the session's effort, and Leaf's prompts ask it to answer
    straight away. A fork at another effort reads the conversation from the cache only
    where Claude Code's per-message effort reaches the model; elsewhere, as on Vertex,
    through a proxy that rewrites mid-conversation system messages, or with
    `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, it writes the conversation to the cache
    again from the session's first reply on. Learning that per backend from each
    fork's usage would cost a stored answer per backend, a rewrite to learn it and
    another to check it again each week."""
    # TODO: fork at `low` effort again (`"effort": "low"` in the request) once Claude
    # Code carries a change of effort per message on every backend it serves, with no
    # environment variable to set (`ModelForkRequest.effort`).
    return {
        "id": instruction,
        "do": "fork",
        "request": {"prompt": prompt},
        "basis": basis,
    }


def run_facts(payload: dict) -> dict:
    """What a page's diagnostics note of a fork's run, from the module's report of it
    (`fork`): its `usage`, its time (`elapsedMs`) and what it resent of the main
    thread's conversation (`request`), each where the report gives it."""
    facts = {
        "usage": payload.get("usage"),
        "elapsedMs": payload.get("elapsed_ms"),
        "request": payload.get("resent"),
    }
    return {name: value for name, value in facts.items() if value is not None}
