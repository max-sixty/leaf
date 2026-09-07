# Claude Code handoff and wait loop

Read this immediately before handing a page over in Claude Code, and when
recovering its wait process.

## Serve the page

```bash
leaf server start <page>
```

It prints the page's keyed URL on stdout and returns. Hand that exact string
back. `leaf server run` prints the same URL but never exits, so nothing it says
reaches you and there is no turn to end. `references/serving-pages.md` owns the
key, the address it binds, and a URL the reader cannot reach.

## Wait loop

One unnamed `leaf wait` watches every page the host session owns. A batch begins
with `{"page": …, "threads": […], "handling": {…}}` and continues with that
page's events. Name a
page only to pick up a page this session did not serve; `leaf wait <page>` claims
it.

Start `leaf wait` as a background task and end the turn. Its completion becomes
host input and records the included moves as opened in that exact turn. After each
batch, start `leaf ack` as the next background task; it acknowledges that batch
and waits for another. The event reference owns the complete-batch and
acknowledgement rules.

If a turn ends without answering an acknowledged move, the next prompt hook
carries that obligation back into context and records it as opened in the new
turn. The page therefore resumes **handling** from that exact prompt delivery;
the agent does not need a status write to repair the top bar.

The initial `leaf wait` revives a dead server under its recorded lifetime and
reports that on stderr. Its exit 2 means stderr names an ending rather than a
batch. After `leaf ack` advances the cursor, however, its exit stays 0 whether
the rearmed wait delivered or ended; read its streams rather than branching on
that status:

- JSON lines on stdout are the next batch.
- `the leaf ended` or `the leaves ended` on stderr means every page left in the
  watch is idle; `nothing to watch` means the session holds none. End the loop.
- `server is not running` gives the recovery command. After recovery, resume
  the session-wide loop with an unnamed `leaf wait`.
- `this session no longer owns` means a successor has the page. Do not name or
  reclaim it. A rearm keeps watching any other live page; when the observed
  transfer empties that set, it exits with this line.
- Stderr saying another `leaf wait` is already active means the existing
  process still owns the session lease. Leave that watcher running rather than
  starting another.

Empty stdout alone is not evidence that the host stopped the process. Start a
replacement unnamed wait only when the host itself reports that it canceled or
killed the command.

## Review fixtures

A page put up to be looked at — a preview of an example, a fixture for a visual
check — is not a handoff, so it owes no watcher. `scripts/preview.py` in a Leaf
checkout marks every page it builds as a preview, and the per-turn reminder to
start one skips those. Nothing else is exempt: a comment left on a preview is a
delivery this session owes like any other, and the reminder says so.

Do not idle a fixture to quiet the loop. `idle` closes the page in the browser,
which changes the banner a visual check may be reading.
