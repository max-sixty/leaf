/* How long a notice offering a press stands (runtime/notifications.js, `holds`): one its
   caller holds keeps the press until the user's next input; any other, news included,
   passes with its press after a notice's moment. */
import assert from "node:assert/strict";
import test from "node:test";

import { NOTICE_MS, notice, noticeReading } from "/runtime/notifications.js";

const press = {
  action: "show-changes",
  command: "changes.toggle",
  run: () => {},
  stands: () => true,
};

test("a press passes with its notice unless the notice is held", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => window.happyDOM.cancelAsync());
  notice("2 changes since v1", { background: true, press });
  assert.equal(noticeReading().press, press);
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(noticeReading().visible, false);

  notice("Annotations hidden", { press });
  t.mock.timers.tick(NOTICE_MS);
  assert.equal(noticeReading().visible, false);

  notice("Resolved “Retries”", { press, holds: true });
  t.mock.timers.tick(NOTICE_MS * 2);
  assert.deepEqual(
    [noticeReading().visible, noticeReading().press, noticeReading().holds],
    [true, press, true],
  );
});
