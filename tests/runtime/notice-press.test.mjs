/* How long a notice's press stands, and what a listener hears of it
   (notifications.js): news and its press pass on the notice's time, marked as news so
   the panel holds the press as one arriving on its own, while the press of the user's
   own gesture stands until their next input; the live region hears the press and its
   shortcut after the words. */
import assert from "node:assert/strict";
import test from "node:test";

/** @param {string} action @param {string[]} shortcut */
const press = (action, shortcut) =>
  Object.freeze({
    action,
    command: "probe.command",
    run: () => {},
    stands: () => true,
    shortcut: () => shortcut,
  });

test("news's press passes on its time; the user's own stands until their next input", async (t) => {
  const { NOTICE_MS, notice, noticeReading } =
    await import("/runtime/notifications.js");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => window.happyDOM.cancelAsync());
  // What the seat shows: its words, the action its press offers, and whether it is news.
  const seat = () => {
    const { visible, message, press, news } = noticeReading();
    return visible ? [message, press?.action ?? null, news] : null;
  };

  notice("2 changes since v1", {
    background: true,
    press: press("show-changes", ["v"]),
  });
  assert.deepEqual(seat(), ["2 changes since v1", "show-changes", true]);
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(seat(), null);

  notice("Draft kept", { press: press("resume-writing", ["g", "i"]) });
  t.mock.timers.tick(NOTICE_MS);
  assert.deepEqual(seat(), ["Draft kept", "resume-writing", false]);
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "x" }));
  assert.equal(seat(), null);
});

test("a listener hears a press and its shortcut after the words", async () => {
  const { heard } = await import("/runtime/notifications.js");
  const { wordsText } = await import("/runtime/voice.js");
  assert.equal(
    wordsText(heard("Draft kept", press("resume-writing", ["g", "i"]))),
    "Draft kept. Resume writing, g i",
  );
  // Where no key reaches the command, the press's word alone.
  assert.equal(
    wordsText(heard("Edit discarded", press("restore-edit", []))),
    "Edit discarded. Restore edit",
  );
  assert.equal(heard("Updated to v4", null), "Updated to v4");
});
