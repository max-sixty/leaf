Review a browser journey recorded by Playwright in `lf-trace`, so each comment names
the exact action, image or saved element it is about. Bind it to an imported
`playwright-trace` source; the contract's `producer` instructions give the import
command.

Write a caption saying what the recording shows, which outcomes the reader should judge,
and what the captures establish. Make each of those outcomes reachable with a named
`lf-trace-bookmark`, preferably at a successful expectation's After checkpoint, reading
its target from the imported source as the bookmark's entry describes. Label it with
the result, such as "Settings saved", rather than the browser operation. The viewer has
its own playback, timeline, keyboard and zoom controls, so the prose explains the
evidence and its limits, not how to operate the viewer.

State timing only as precisely as the recording does. Playwright records when each call
starts and ends, but not the moment an input inside it happened or how long a key was
held. A caption can say what came before or after a capture, but not the instant of a
click.

Images and saved accessibility trees are separate captures, taken at different times,
so a saved element's box does not mark an exact spot in the image beside it. A comment
on an image names that capture. A comment on a saved element names its action phase and
its path in the accessibility tree, which tells apart two controls with the same name.

Equal elapsed times in two recordings don't mean the application was in the same state.
To compare recordings, import each under its own source, put their viewers inside one
`lf-trace-compare` with a `label` on each, and give the bookmarks for the same result
the same `key`.

Keep the original archive and serve it in Playwright's own viewer at the imported
`viewerUrl`, which offers DOM snapshots, element picking, console, network and source.
Import a new recording under a new source id, so earlier comments keep naming the
evidence the user saw.
