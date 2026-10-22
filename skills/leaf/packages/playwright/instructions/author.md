Show a Playwright recording of a browser journey in `lf-trace`, where each comment names
the action, image or saved element the user pointed at. Bind it to an imported
`playwright-trace` source; the contract's `producer` instructions give the import
command.

Write a caption saying what the recording shows, which outcomes the reader should judge,
and what the captures establish. Make each of those outcomes reachable with a named
`lf-trace-bookmark`, preferably at a successful expectation's After checkpoint, and
label it with the result, such as "Settings saved", rather than the browser operation.
The viewer has its own playback, timeline, keyboard and zoom controls, so the prose
explains the evidence and its limits, not how to operate the viewer.

State timing only as precisely as the recording does. Playwright records when each call
starts and ends, but not the moment an input inside it happened or how long a key was
held, so a caption can say what came before or after a capture but not the instant of a
click. Images and saved accessibility trees are separate captures taken one after
another, so don't place an element from the tree at a spot in an image. A comment on a
saved element names its action phase and its path in the accessibility tree, which
tells apart two controls with the same name.

To compare recordings, import each under its own source, put their viewers inside one
`lf-trace-compare`, each with a `label`, and give bookmarks for corresponding steps the
same `key`. An input can produce different results across versions, so name its
identity separately from the outcome the reader should inspect.

Keep the original archive, and keep Playwright's own viewer at the imported `viewerUrl`
running for DOM snapshots, element picking, console, network and source. Import a new
recording under a new source id, so earlier comments keep naming the evidence the user
saw.

### Record comparable journeys

Run one journey function against both versions, with the same fixture, viewport and
input targets. Establish the same ready state before starting the capture, or include
startup in both when it is under review. Wrap each logical input and its outcome check
in a native Playwright tracing group with the same stable name in both runs, such as
`enter-ask`, and use that name as the paired bookmarks' `key`. Don't match steps by
elapsed time, rendered labels, archive-local call ids or which outcome succeeded.

For a paced demonstration, schedule each input at a deadline measured from the capture's
start, rather than waiting after each action, which accumulates differing latencies.
Report a missed deadline instead of shifting the rest of the schedule. The same schedule
doesn't give identical browser dispatch times, so read the actual input calls back from
both traces and keep that difference rather than stretching playback to hide it. A
performance comparison separates intentional demonstration waits from the application's
response time.
