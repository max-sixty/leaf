Use `lf-motion` for several previews compared at the same instant: recorded videos,
authored animations, or both. Put the previews in its body, give each a caption,
and set `duration` to the study's length in milliseconds. Choose layout and frame
size for what the reader needs to compare. The shared toolbar stays visible while
the previews scroll beneath it.

The reader can play or pause with one icon button. Play at the end starts again from
the beginning; to restart mid-study, seek to the beginning and play. Use these controls
rather than adding transport buttons or a second clock. Playback starts paused.

For recordings, put ordinary `<video muted playsinline>` elements inside the body.
Include dimensions or an aspect ratio so loading media keeps the page still. Omit
`autoplay`, `loop` and individual playback controls: the transport plays all the
videos at their native rate, changes their speed together, and aligns them when
paused or sought. Use recordings with a shared starting point and duration; the
timeline follows the furthest recording's native playback time. The browser decodes
each video independently, so use frame drawings for comparisons requiring exactly
the same computed frame. Use `lf-trace` when the reader needs captured checkpoints
and their inspection tools.

Size the evidence for the movement the reader is judging: its full path, reversal
and settling must stay visible together at the narrowest view. Use the available
width before nesting recordings in padded frames. When a recording needs a closer
view, keep that view on the shared timeline and preserve the moving subject
throughout the sequence; a native-size scrolling crop can hide the very motion
being compared. Inspect playback at the delivered sizes, judging the details the
decision depends on rather than whether every incidental word in a recording is
readable.

For illustrations, a page module assigns `renderFrame` after
`customElements.whenDefined('lf-motion')`. It receives milliseconds from zero through
`duration` and draws a complete frame, so seeking backward works too. Include any
lead-in or final hold in the duration and subtract the lead-in in the drawing
function. No timer or control handlers belong in that module. Label illustrative
studies as illustrations and say where their timing came from.

In a playground, put `lf-motion` inside `lf-playground-preview` around the baseline
and the `lf-playground-control` whose rich choices contain the candidate previews.
The playback controls inspect the candidates; the playground's choice selects what
to build. Playback time and speed are tab-local exploration, never configuration
submitted to the agent or decisions in the page log.
