# Run the agent journey

`uv run --project <root> leaf-dev journey run TARGET` runs one user's journey against a
real agent and times each step on the page server's clock. Its `--help` lists the
targets and options, and each target's module header lists its steps and the promises
it checks. A run spends the target's login. Add `--browser` when what the page shows
is part of the change.

The suite only stands in for each harness, so run the journey on the harness a change
touches:

- `claude-code` (`commands/journey/_claude_code.py`): after a change to `hooks/hooks.json`,
  `hooks/claude-code.ts`, `ClaudeCodeHarness`, `hooks.py`, the watch between turns in
  `session.py`, what wakes it (`delivery.wake_inputs`), `forks.py` or `carrier.py`. Add `--sandbox` after a
  change to `bridge.py`, the README's "Agent sandboxes" settings, or what a `leaf`
  command needs from outside its page directory.
- `codex-app-server` and `codex-queue` (`commands/journey/_codex.py`), both: after a change to
  `codex.py`, `codex_adapter.py`, `codex_run.py`, `hooks.py`, `hook_transport.py`, or the claim's turn
  in `service.py`. Add `--sandbox` for a change to `codex_tool.py`, the MCP server in
  `.codex-plugin/plugin.json`, or what a `leaf` command needs from outside its page
  directory.
- `pi` (`commands/journey/_pi.py`): after a change to `hooks/pi.ts`, `PiHarness`, `hooks.py`, or
  the watch between turns in `session.py` and what wakes it (`delivery.wake_inputs`).

For the website, `tests/AGENTS.md`, "Run what the change needs", says which delivery
checks CI runs, and `worker/README.md`, "Local development", how to reproduce a Worker
or container failure. Only the `publish-site` workflow's journey against the deployed
release reads production.

To benchmark replies, run each harness's journey a few times, with and without
`--case working`, and tabulate the samples with `leaf-dev journey chart --replies`;
`leaf-dev logs response-times` measures retained pages and sorts each pickup's wait
by what ended it, which shows the waits only long real sessions have
(`dev/leaf_dev/page_timings.py`). The benchmark is the whole reply's time,
which `dev/leaf_dev/reply_phases.py` attributes to Leaf's delivery, commands and hooks,
the harness, the model's wait and generation, and the agent's other tools. Model time
varies widely from run to run, so compare a phase Leaf owns directly, and the whole
reply over enough runs to see past that spread.

To find out what happened to one message, on a real page or in a journey's evidence
directory, run `leaf-dev logs timeline PAGE --message ID`: it lays the page's log and
diagnostics beside the Claude Code session's transcript and debug log, so it shows
what came of the line fork, when Leaf handed the message to the session, and what the
session did meanwhile (`dev/leaf_dev/commands/logs/timeline.py`).
