Use `lf-motion` for an authored animation, or several views compared at the same
instant. Put the figures in its body, each with a caption, and choose the layout and
frame size for what the reader needs to compare. The widget owns the clock and the
playback controls, with which the reader slows, pauses, seeks and replays, so add no
transport buttons, timers or control handlers of your own.

A page module assigns `renderFrame`, which draws a complete frame for any time, so
seeking backward works too. Include any lead-in or final hold in the duration, and
subtract the lead-in in the drawing function.

Label an illustrative study as an illustration and say where its timing came from; show
captured behavior with `lf-trace`. Playback and scrubbing are local exploration, not
decisions in the page log.
