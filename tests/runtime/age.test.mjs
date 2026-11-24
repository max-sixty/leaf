/* `lf-age` (browser/runtime/age.js): the age it shows in place of the words its author
   wrote, as the clock ticks and its moment changes, and the clock time it previews. */
import assert from "node:assert/strict";
import process from "node:process";
import test from "node:test";
import "../../browser/runtime/age.js";
import { ago, tickClock } from "../../browser/runtime/presence.js";

const NOW = Date.parse("2026-11-24T18:05:00Z");
const tick = () =>
  tickClock((message) => {
    throw new Error(message);
  });
/** @param {string} markup */
const drawn = (markup) => {
  const holder = document.createElement("div");
  holder.innerHTML = markup;
  document.body.append(holder);
  const age = holder.querySelector("lf-age");
  return { holder, age, shows: () => age.shadowRoot.textContent };
};

test("an age stands in place of its author's words and follows the clock", async (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: NOW });
  const { holder, age, shows } = drawn(
    '<p>Ran <lf-age datetime="2026-11-24T18:05:00Z">24 Nov, 18:05 UTC</lf-age>.</p>',
  );
  t.after(() => holder.remove());
  // The age is drawn apart from the author's words, which stay the page's own.
  assert.equal(shows(), "just now");
  assert.equal(age.textContent, "24 Nov, 18:05 UTC");
  assert.equal(age.shadowRoot.querySelector("slot"), null);

  t.mock.timers.setTime(NOW + 40_000);
  await tick();
  assert.equal(shows(), "just now");
  t.mock.timers.setTime(NOW + 60_000);
  await tick();
  assert.equal(shows(), "1m ago");
  // Every age reads one wording.
  assert.equal(shows(), ago("2026-11-24T18:05:00Z"));

  // Another moment shows at once, without waiting for a tick.
  age.setAttribute("datetime", "2026-11-24T15:06:00Z");
  assert.equal(shows(), "3h ago");
  age.removeAttribute("datetime");
  assert.equal(shows(), "");
});

test("an age out of the page follows nothing, and reads the clock again on return", async (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: NOW });
  const { holder, age, shows } = drawn(
    '<lf-age datetime="2026-11-24T18:05:00Z"></lf-age>',
  );
  t.after(() => holder.remove());
  assert.equal(shows(), "just now");
  age.remove();
  t.mock.timers.setTime(NOW + 5 * 60_000);
  await tick();
  assert.equal(shows(), "just now");
  holder.append(age);
  assert.equal(shows(), "5m ago");
});

// Dates read as the reader's platform writes them, so this holds where the platform
// reads American English, as Node does under an en_US locale.
const american = Intl.DateTimeFormat().resolvedOptions().locale === "en-US";

test(
  "an age previews its clock time in the reader's zone",
  { skip: !american && "the platform doesn't read American English" },
  (t) => {
    const zone = process.env.TZ;
    process.env.TZ = "America/Los_Angeles";
    const { holder, age } = drawn('<lf-age datetime="2026-08-15T21:02:00Z"></lf-age>');
    t.after(() => {
      process.env.TZ = zone;
      holder.remove();
    });
    assert.deepEqual(age.lfPreview("pointer"), {
      name: "Sat, Aug 15, 2026, 2:02 PM PT",
    });
    age.removeAttribute("datetime");
    assert.equal(age.lfPreview("pointer"), null);
  },
);
