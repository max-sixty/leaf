# Claude Code wait loop

Read this immediately before starting Claude Code's wait loop for a page, and
when recovering that wait process.

One unnamed `leaf wait` watches every page the host session owns. A batch begins
with `{"page": …, "threads": […]}` and continues with that page's events. Name a
page only to pick up a page this session did not serve; `leaf wait <page>` claims
it.

Start `leaf wait` as a background task and end the turn. Its completion becomes
host input. After each batch, start `leaf ack` as the next background task; it
acknowledges that batch and waits for another. The event reference owns the
complete-batch and acknowledgement rules.

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
