Use `lf-motion` for an authored animation or several views compared at the same
instant. Put the figures in its body and give each a caption; the widget owns only
the clock and playback controls. Choose the layout and frame size for what the
reader needs to compare.

The reader can slow playback to half or quarter speed, pause, or seek with the
timeline. At the end, Replay starts the study again; the timeline also reaches
the beginning. Use these shared controls rather than adding transport buttons.

A page module assigns `renderFrame` after `customElements.whenDefined('lf-motion')`.
It receives milliseconds from zero through `duration` and draws a complete frame,
so seeking backward works too. Include any lead-in or final hold in the duration
and subtract the lead-in in the drawing function. No timer or control handlers
belong in that module.

Label illustrative studies as illustrations and say where their timing came from.
Use `lf-trace` for captured behavior. Playback and scrubbing are local exploration,
not decisions in the page log. Reduced motion makes Play show the end immediately;
manual scrubbing still reaches every frame.
