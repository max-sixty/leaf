/* `lf-age` (browser/runtime/age.js): the age it shows in place of the words its author
   wrote, as the clock ticks and its moment changes, and the clock time it previews. */
import assert from "node:assert/strict";
import test from "node:test";
import "../../browser/runtime/age.js";
import { ago, clockTime, tickClock } from "../../browser/runtime/state/presence.js";

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
  // The words it draws, without the zero-width no-break space that leads them.
  return { holder, age, shows: () => age.shadowRoot.textContent.trim() };
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
  // A moment it can't read shows no age.
  for (const moment of ["yesterday", null]) {
    if (moment === null) age.removeAttribute("datetime");
    else age.setAttribute("datetime", moment);
    assert.equal(shows(), "");
  }
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

test("an age previews the clock time of its moment, as every age does", (t) => {
  const { holder, age } = drawn('<lf-age datetime="2026-08-15T21:02:00Z"></lf-age>');
  t.after(() => holder.remove());
  const said = clockTime("2026-08-15T21:02:00Z");
  assert.notEqual(said, "");
  assert.deepEqual(age.lfPreview("pointer"), { name: said });
  age.removeAttribute("datetime");
  assert.equal(age.lfPreview("pointer"), null);
});
