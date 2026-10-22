Use `lf-motion` for an authored animation or several views compared at the same
instant. Put the figures in its body and give each a caption; the widget owns only
the clock and playback controls. Choose the layout and frame size for what the
reader needs to compare.

Use the widget's playback controls rather than adding transport buttons.

A page module assigns `renderFrame` after `customElements.whenDefined('lf-motion')`.
It receives milliseconds from zero through `duration` and draws a complete frame,
so seeking backward works too. Include any lead-in or final hold in the duration
and subtract the lead-in in the drawing function. No timer or control handlers
belong in that module.

Label illustrative studies as illustrations and say where their timing came from.
Use `lf-trace` for captured behavior. Playback and scrubbing are local exploration,
not decisions in the page log.
