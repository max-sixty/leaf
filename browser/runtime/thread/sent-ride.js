/* A sent turn rides from the field it was written in to its place at the transcript's
   end, and the turns above it ride up by what the send moved them, so the eye follows
   the words from where they were typed to where they now stand (browser/AGENTS.md,
   "Motion").

   Layout changes in one step, as every landing does (reply-landing.js): the turn is
   drawn and the transcript scrolled before this plays. The ride is presentation only,
   a translation from each message's drawn place to its rest, on one tween. A turn new
   to the transcript starts where the field's words stood; a turn already drawn starts
   where it stood before the send. The transcript clips what it carries, so the new
   turn comes up out of the transcript's foot, over the field it left.

   The caller reads the places before the send draws (`rideSent`) and plays the ride
   once its landing has scrolled. Motion's shared gate answers reduced motion and the
   presentation boundary. The view names the transcript and the tween: the floating
   panel's, so the turns ride on the clock its box grows by (floating-panel.css).

   Only the floating panel rides a send. A margin card's message heads stick to its
   transcript's top, and a translation carries a stuck head down over its own words. */
import { motionEasing, motionPlays, motionTime, playMotion } from "../motion.js";

const MESSAGE = ".lf-msg";

export function rideSent(input, transcriptOf) {
  if (!motionPlays() || !input) return () => {};
  const field = input.getBoundingClientRect();
  const before = transcriptOf();
  const stood = new Map(
    [...(before?.querySelectorAll(MESSAGE) ?? [])].map((msg) => [
      msg,
      msg.getBoundingClientRect().top,
    ]),
  );
  return () => {
    const transcript = transcriptOf();
    if (!transcript || !motionPlays()) return;
    const duration = motionTime("--lf-motion-send", transcript);
    const easing = motionEasing("--lf-motion-send-ease", transcript);
    const shown = transcript.getBoundingClientRect();
    for (const msg of transcript.querySelectorAll(MESSAGE)) {
      const { top, height } = msg.getBoundingClientRect();
      const from = stood.get(msg) ?? field.top;
      const dy = from - top;
      if (Math.abs(dy) < 0.5) continue;
      // A turn out of sight both before and after the send has nothing to show.
      const seen = (at) => at < shown.bottom && at + height > shown.top;
      if (!seen(from) && !seen(top)) continue;
      playMotion(msg, [{ translate: `0 ${dy}px` }, { translate: "0 0" }], {
        duration,
        easing,
      });
    }
  };
}
