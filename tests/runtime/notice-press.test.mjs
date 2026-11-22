/* How long a notice's press stands, and what a listener hears of it
   (notifications.js): news and its press pass on the notice's time, while the press of
   the user's own gesture stands its time and then until their next input; the live
   region hears the press
   and the keys that would make it after the words, in their spoken form
   (keyboard/control-keys.js, `commandPress`). */
import assert from "node:assert/strict";
import test from "node:test";

/** @param {string} action @param {string[]} keys */
const press = (action, keys) =>
  Object.freeze({
    action,
    run: () => {},
    stands: () => true,
    keys: () => keys,
    spoken: () => keys.join(" "),
  });

test("news's press passes on its time; the user's own stands its time, then until their next input", async (t) => {
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
  // An input within its time, such as the Escape that takes the caret out of a box
  // where the field shows no notice, leaves it standing.
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  t.mock.timers.tick(NOTICE_MS);
  assert.deepEqual(seat(), ["Draft kept", "resume-writing", false]);
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "x" }));
  assert.equal(seat(), null);
});

test("a listener hears a press and its keys after the words", async () => {
  const { heard } = await import("/runtime/notifications.js");
  const { wordsText } = await import("/runtime/voice.js");
  assert.equal(
    wordsText(heard("Draft kept", press("resume-writing", ["g", "i"]))),
    "Draft kept. Resume writing, g i",
  );
  // Where no key would make the press now, the press's word alone.
  assert.equal(
    wordsText(heard("Edit discarded", press("restore-edit", []))),
    "Edit discarded. Restore edit",
  );
  assert.equal(heard("Updated to v4", null), "Updated to v4");
});

test("a page command's press is heard with the key the field shows, a modifier named", async () => {
  const { pageCommand } = await import("/runtime/keyboard/register.js");
  const { commandPress } = await import("/runtime/keyboard/control-keys.js");
  const { applicationState } = await import("/runtime/semantic-state.js");
  const { heard } = await import("/runtime/notifications.js");
  const { wordsText } = await import("/runtime/voice.js");
  applicationState.setPhase("ready");
  // As navigation.js declares the thread walk: `t` is its route `thread.next`.
  pageCommand({
    id: "thread.walk",
    touch: false,
    keys: ["t", "Shift+t"],
    routes: [
      { id: "thread.next", binding: "t", title: "Next thread or draft" },
      { id: "thread.previous", binding: "Shift+t", title: "Previous thread or draft" },
    ],
    title: "Threads",
    run: () => {},
  });
  const next = commandPress({ action: "next-thread", command: "thread.next" });
  assert.deepEqual(next.keys(), ["t"]);
  assert.equal(
    wordsText(heard("Resolved “Retries”", next)),
    "Resolved “Retries”. Next thread, t",
  );
  // The field's chip draws Shift+t as "T", which a screen reader reads as "t".
  const previous = commandPress({ action: "next-thread", command: "thread.previous" });
  assert.deepEqual(previous.keys(), ["T"]);
  assert.equal(previous.spoken(), "Shift+t");
});
