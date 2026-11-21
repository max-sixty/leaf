/* How long a notice's press stands (notifications.js): news and its press pass on the
   notice's time but neither come nor go while the pointer rests on the surface that
   draws them, and the press of the user's own gesture stands until their next input. */
import assert from "node:assert/strict";
import test from "node:test";

const PRESS = Object.freeze({
  action: "show-changes",
  command: "changes.toggle",
  run: () => {},
  stands: () => true,
});

test("news's press passes on its time, but never comes or goes under a resting pointer", async (t) => {
  const { NOTICE_MS, notice, noticeReading, restOnSeat } =
    await import("/runtime/notifications.js");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => window.happyDOM.cancelAsync());
  // What the seat shows: its words and the action its press offers, or null.
  const seat = () => {
    const { visible, message, press } = noticeReading();
    return visible ? [message, press?.action ?? null] : null;
  };

  // Away from the panel, news and its press pass on the notice's time.
  notice("2 changes since v1", { background: true, press: PRESS });
  assert.deepEqual(seat(), ["2 changes since v1", "show-changes"]);
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(seat(), null);

  // Arriving under a resting pointer, it waits until the pointer leaves.
  restOnSeat(true);
  notice("3 changes since v1", { background: true, press: PRESS });
  assert.equal(seat(), null);
  restOnSeat(false);
  assert.deepEqual(seat(), ["3 changes since v1", "show-changes"]);

  // Its time running out under a resting pointer, it stays until the pointer leaves.
  restOnSeat(true);
  t.mock.timers.tick(NOTICE_MS);
  assert.deepEqual(seat(), ["3 changes since v1", "show-changes"]);
  restOnSeat(false);
  assert.equal(seat(), null);

  // News offering no press passes under the pointer as anywhere.
  restOnSeat(true);
  notice("Updated to v4", { background: true });
  assert.deepEqual(seat(), ["Updated to v4", null]);
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(seat(), null);
  restOnSeat(false);

  // The press of the user's own gesture stands past its time, until their next input.
  notice("Draft kept", { press: { ...PRESS, action: "resume-writing" } });
  t.mock.timers.tick(NOTICE_MS);
  assert.deepEqual(seat(), ["Draft kept", "resume-writing"]);
});
