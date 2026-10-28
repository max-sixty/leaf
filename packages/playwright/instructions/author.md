Show a Playwright recording of a browser journey in `lf-trace`, where each comment names
the action, image or saved element the user pointed at. Bind it to an imported
`playwright-trace` source; the contract's `producer` instructions give the import
command.

Write a caption saying what the recording shows, which outcomes the reader should judge,
and what the captures establish. Make each of those outcomes reachable with a named
`lf-trace-bookmark`, preferably at a successful expectation's After checkpoint, whose
target you read from the imported source (the `lf-trace-bookmark` entry gives the id
forms). Label it with the result, such as "Settings saved", rather than the browser
operation. The viewer has its own playback, timeline, keyboard and zoom controls, so the
prose explains the evidence and its limits, not how to operate the viewer.

State timing only as precisely as the recording does. Playwright records when each call
starts and ends, but not the moment an input inside it happened or how long a key was
held. A caption can say what came before or after a capture, but not the instant of a
click.

Images and saved accessibility trees are separate captures taken one after another, so
don't place an element from the tree at a particular spot in an image. A comment on a
saved element names its action phase and its path in the accessibility tree, which tells
apart two controls with the same name.

To compare recordings, import each under its own source and put their viewers inside one
`lf-trace-compare`, with a `label` on each. Give bookmarks for corresponding steps the
same `key`. An input can produce different results across versions, so name its identity
separately from the outcome the reader should inspect.

### Record comparable journeys

Run one journey function against both versions, with the same fixture, viewport and
input targets. Separate setup from the recorded interaction: load and establish the
same ready state before starting the capture. If startup itself is under review,
include it in both instead. Wrap each logical input and its outcome check in a native
Playwright tracing group with the same stable name, such as `enter-ask`, in both runs.
Use that same identity for the paired bookmarks. Do not match steps by elapsed time,
rendered labels, archive-local call ids or which outcome happened to succeed.

For a paced demonstration, use one requested input schedule and stop time measured
from each capture's start. Waiting after every completed action accumulates differing
latencies; absolute deadlines do not. Report a missed deadline instead of silently
shifting the remaining schedule. Read the actual native input calls and capture bounds
back from both traces: the same requested schedule does not guarantee identical browser
dispatch times. Preserve that difference; do not stretch playback to conceal it. A
performance comparison must also distinguish intentional demonstration waits from the
application's response time.

Keep the original archive and serve it in Playwright's own viewer at the imported
`viewerUrl`, which offers DOM snapshots, element picking, console, network and source.
Import a new recording under a new source id, so earlier comments keep naming the
evidence the user saw.
