Give a browser journey a review surface whose comments return to the captured
action, image or saved element. Bind `lf-trace` to the imported
`playwright-trace` source. The `producer` audience owns the import command.

Write an evidence caption: what the recording shows, which outcomes the reader
should judge, and what the captures establish. Make those outcomes directly
reachable with named `lf-trace-bookmark` members, preferably
the successful expectations' After checkpoints. Read their exact targets from
the imported source as the bookmark entry describes. Choose labels that name
the result rather than a browser operation. Leave transport, timeline, keyboard
shortcuts and zoom instructions to the viewer's controls. They are already present
on the review surface; surrounding prose carries the evidence and its limits.

The review opens at the earliest authored moment that resolves, in the first
stream holding one; without one, at the first saved tree, then the first image.
The timeline places every call, input and capture at its recorded time: calls and
inputs are bars spanning their call, so a caption can say what happened before or
after a capture but not an input's exact instant. Native input events carry no
timestamp, and a key's held duration is not recorded.
The timeline includes action checkpoints and intermediate filmstrip images at
their native times. Browser and context operations remain in the chronology;
multi-page recordings can filter it by page. Separate streams keep their own
clocks. Recorded pace preserves native timing; optional Review pace slows near
recorded input and named results, and accelerates quiet intervals. It changes
viewing speed, not evidence timestamps. Matched recordings need a source and bookmark targets of their own;
equal elapsed times do not establish matching application states. Put paired viewers
inside `lf-trace-compare`, with a `label` on each recording and the same `key` on
corresponding bookmarks. Result selection chooses each recording’s own target;
the Recording chooser retains the shared inspection position. Manual seeking keeps
independent positions. Separate viewers can share a `compare` token when the page
needs to display them together.

An image comment names its actual capture. A saved-element comment names an
action phase and accessibility-tree path, which distinguishes controls with the
same name. Images and trees are separate captures and can have different times.
The inspector labels the checkpoint whose saved elements it holds while images
advance. A first captured image shown before its capture time is labeled as a
preview, not evidence of an earlier state. Use the linked Playwright viewer for
DOM snapshots, element picking, console, network and source inspection.

Keep the original archive and serve it in Playwright's viewer at the imported
`viewerUrl`. Another recording gets a new source id, so prior comments continue
to name the evidence the user saw.
