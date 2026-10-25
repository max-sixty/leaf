# TODO

## Biggest current challenges

- **Improve our outputs against a standard HTML output.** The
  [recovered comparison](notes/agent-usability-evals.md#recovered-codex-comparison-2026-10-14)
  measures complete authoring and feedback cycles on saved Leaf and HTML pages.
  Use task-specific evidence to decide which compositions help, and measure current
  authoring time before adding more widgets or instructions.
- **Simplify the harness, host, and CLI workflow.** Make feedback delivery and
  agent wake-up reliable, including Codex's message back into the session and
  Claude Code's potentially overcomplicated state machine.
- **Make tasks and work in progress clear.** Find a robust state model that
  users can understand: what is running, waiting, blocked, or complete, and
  whose next move it is.
- **Keep authored pages flexible.** Find the useful middle ground between
  unrestricted HTML and brittle templates, especially for workspaces.
- **Make page-level Threads easy to create and use.** Give users a clear way
  to start, find, and continue conversations about the whole page.
- **Build coherent UI without repeated patches.** Improve the layout and
  interaction mechanisms so each new case does not require another fix.
- **Reduce the burden of tests.** Tests now take long enough to meaningfully
  slow development. Reduce their runtime and the work needed to run them while
  preserving useful coverage. `notes/shift-watch-cost.md` records the Stability
  sensor's idle-cost evidence and remaining optimization questions.
  Sharing one page across a test's cases (`tests/AGENTS.md`, "One page for the
  cases that can share it") reaches only cases that leave the log and the page's
  own UI alone, so most of the time spent opening pages needs each opening to
  cost less.

## Backlog

Every other item is a GitHub issue labelled `backlog`, and its priority label runs
from `now` to `next` to `etc`. An `etc` item waits for the trigger it states and is
not an active queue. Theme labels, such as `ux` and `layout`, group related work
(`gh label list`). An issue's title is an outcome, not an implementation plan;
linked notes hold the evidence and detailed briefs. Completed work lives in closed
issues and git history, and rejected ideas in a closed issue or the relevant
research note. An item marked **Unconfirmed** rests on a reading nobody has run or a
design nobody has tried; settle that before building it.

An issue labelled `waits-on-user` needs Max's decision, review or go-ahead before
more work, and its body says which. Every other item is open to an agent working
unattended. An agent that finds an unlabelled item needs the user adds the label.

To list the items open to an agent that no pull request has claimed, start with
`now`, then `next`:

```bash
gh issue list --search "label:backlog label:now -label:waits-on-user -linked:pr"
```

A new item is an issue labelled `backlog` and its priority, with a theme where one
fits.
