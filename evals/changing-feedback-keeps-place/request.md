Finish this small Leaf comparison page. Two boxes illustrate linear motion and
ease-out motion over the same 1200ms interval. They travel from left to right in
their own tracks. The user compares their positions using shared Replay all,
Pause all/Resume all, a speed select with 1×, 0.5× and 0.25×, and a timeline slider.
Replay starts both at the beginning; pause/resume and seeking affect both.

The existing toolbar draft is:
  <div id="playback" style="display:flex;flex-wrap:wrap;align-items:center;gap:10px">
    <button class="button" id="replay">Replay all</button>
    <button class="button" id="pause">Pause all</button>
    <label>Speed <select class="field" id="speed"><option>1×</option></select></label>
    <span id="status" role="status">Ready to compare.</span>
  </div>
  <input id="timeline" type="range" min="0" max="1200" value="0" aria-label="Timeline">
Show a notice while playing, while paused, and when the run finishes. Completion
should tell the user they can replay to compare again. Keep the controls compact.

Beneath the comparison include an explanation of what the motion demonstrates.
A "Show observations" button reveals this complete paragraph:
"Linear motion covers equal distances in equal time. Ease-out starts faster,
then slows near the destination. Both arrive together at 1200ms, but their positions
differ through the run. Compare the midpoint, pause just before arrival, and replay
at quarter speed to see how the final approach changes. Neither curve is universally
better: choose according to what the movement communicates."

Write the complete working page in the provided page directory.
