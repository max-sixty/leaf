Give a browser journey a review surface whose comments return to the captured
action, image or saved element. Bind an empty `lf-trace` to the imported
`playwright-trace` source, and introduce the journey's purpose beside it. The
`producer` audience for that contract owns the import command.

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
