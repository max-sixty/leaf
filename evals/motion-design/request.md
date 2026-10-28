# Subject: panel-motion design review

Make me a working design page to compare three proposed timings for Leaf's panel
against the supplied baseline, then record which one I want implemented. The recordings
are real captures of the same panel folding, unfolding and reversing mid-motion.
I need to judge how the movement feels, rather than choose from timing numbers alone.

The local files are in `evals/motion-design/` relative to your working directory:

- `current.mp4`: Baseline, 300 ms. Fast departure with a long settling tail.
- `a.mp4`: A · Crisp, 220 ms. Quick departure with a short settle.
- `b.mp4`: B · Balanced, 260 ms. Gentler departure with a clean arrival.
- `c.mp4`: C · Glide, 280 ms. Builds speed, then eases into place.

These historical demonstration clips follow the same input schedule.
The baseline names this recorded version, not a claim about today's live application.
They are muted, recorded slowly and retimed to nominal speed for visual comparison;
they are demonstrations,
not performance measurements. The panels inside the recordings are not interactive.

Let me compare the candidates together with Baseline as a reference. I want one
set of playback controls to replay all recordings, pause them, slow them to quarter
speed and inspect the same instant in each. Keep those controls available as I
read and compare candidates further down the page, including on a phone. I should
be able to select the candidate where I see its recording, without having to match
it to a separate list of answers. Trying playback or seeking is only inspection;
it must not choose a design for me. Make comparison and choosing work with a
keyboard and touch.

Give me a clear way to finish choosing. After I finish, preserve the chosen design
and its recording in the final record. Recording my choice does not mean it has
been implemented or shipped. Choose the page's layout and visual treatment yourself.
