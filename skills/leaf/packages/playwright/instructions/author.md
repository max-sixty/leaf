Give a browser journey a review surface whose comments return to the captured
action, image or saved element. Bind `lf-trace` to the imported
`playwright-trace` source, and introduce the journey's purpose beside it. The
`producer` audience for that contract owns the import command.

Optional `lf-trace-bookmark` members mark exact captures on the time-scaled timeline.
Numbers match the chronological Moments list and selected readout. Every moment
has its own selectable button, with its name and time on hover or keyboard focus.
Close times stack in a bounded timeline viewport; scroll it vertically for dense
recordings. Explicit zoom controls spread different times horizontally. Focus the
timeline and use Left/Right or Home/End to step through captured stops. Drag the
blue handle to scrub; empty space pans. Play follows the captured images and
checkpoints at their recorded timing, including intermediate frames. Pause holds
the current capture; selecting a moment or engaging with evidence also pauses.
Play at the end restarts the recording.
Image controls fit, zoom and inspect the actual captured pixels; ordinary wheel
scrolling keeps its page-navigation meaning. Image zoom and pan and the chosen
timeline window survive playback, replay and returning from another scope.
Explicit point navigation reveals its destination at the retained time zoom.
Selected point details, including saved elements, scroll within their own region,
so frame changes and disclosure keep the surrounding page steady.
The ruler starts at recording time zero; navigation selects actual captured stops.
Set each `target` as the bookmark entry describes, using the imported source’s ids. Bookmarks can reach intermediate frames
without first enabling the filmstrip. The evidence grows with the page.

One timeline steps through recorded calls' available Before, Action and After
checkpoints in timestamp order (or Start and Completion when no checkpoints
were captured). The review opens at the first checkpoint with saved elements,
or the first image when no elements were saved. Earlier stops remain reachable.
Show intermediate frames inserts the browser's original
filmstrip images into that same timeline. A saved element is a node in the
recorded accessibility tree; its path distinguishes controls with the same name.
Comments on images and elements refer to separate captures, whose displayed times
can differ. Use the
linked Playwright viewer for DOM, console, network and source inspection.

Keep the original archive and serve it in Playwright's viewer at the imported
`viewerUrl`. Another recording gets a new source id, so prior comments continue
to name the evidence the user saw.
