Use `lf-timeline` when the reader needs the order of events between actors, such as
two jobs racing on shared state, a retry storm, or a handoff between services. It
draws one lane per actor on a shared time axis and lets the reader step through the
events in start order, with the playhead and the step list following. It draws and
places every label itself: don't hand-draw a timeline in SVG or add your own
playback controls.

Choose events for the steps the explanation needs. Every start is a step, so an
event the reader should stop at, such as a write landing or a lock being released,
is an instant of its own rather than the end of a span. Times are milliseconds from
the start of the sequence; illustrative times are fine when the prose says so.

For a comparison, such as the run before a fix and the run after it, put each run in
an `lf-run` of one `lf-timeline`, with the same lanes in the same order. The runs
share one time axis, so a run that takes longer draws longer, and one playhead, so
each step shows every run at the same moment. Event ids share the page's id space, so
prefix them per run.
