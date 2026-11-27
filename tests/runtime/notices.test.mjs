/* How long a notice stands (runtime/transport/notifications.js, `showNotice`): every notice its
   time; one answering the user's own gesture with a press then until the user's next
   input, which an input within its time doesn't end; news passes with its press. */
import assert from "node:assert/strict";
import test from "node:test";

import { NOTICE_MS, notice, noticeReading } from "/runtime/transport/notifications.js";

const press = {
  action: "show-changes",
  keys: () => ["v"],
  run: () => {},
  stands: () => true,
};
const input = () =>
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown" }));

test("news passes with its press, and a gesture's press stays until the next input", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => window.happyDOM.cancelAsync());
  notice("2 changes since v1", { background: true, press });
  assert.equal(noticeReading().press, press);
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(noticeReading().visible, false);

  notice("Annotations hidden", { press });
  input();
  t.mock.timers.tick(NOTICE_MS * 2);
  assert.deepEqual([noticeReading().visible, noticeReading().press], [true, press]);
  input();
  assert.equal(noticeReading().visible, false);
});
