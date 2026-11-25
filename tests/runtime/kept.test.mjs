/* A reading kept by `kept` or `keptEach` is made again exactly when an argument it
   was read with differs, a signal it read changes, a version it read moves, or a
   reading made inside it is made again; a version that catches up does so before a
   reading that read it is checked; and a make that threw keeps nothing (state/kept.js). */
import assert from "node:assert/strict";
import test from "node:test";

import { kept, keptEach, version } from "/runtime/state/kept.js";
import { effect, signal } from "/vendor/signals-core.js";

test("a reading is kept while each version it read stands, and made again once one moves", () => {
  const [a, b, unread] = [version(), version(), version()];
  let made = 0;
  const reading = kept(() => {
    made += 1;
    return a.read() + b.read();
  });
  assert.equal(reading(), 0);
  assert.equal(reading(), 0);
  assert.equal(made, 1);
  unread.move();
  reading();
  assert.equal(made, 1, "a version it never read moves nothing");
  b.move();
  assert.equal(reading(), 1);
  assert.equal(made, 2);
  reading();
  assert.equal(made, 2);
});

test("a reading made inside another adds what it read to that one's", () => {
  const [inner, outer] = [version(), version()];
  const part = kept(() => inner.read());
  let made = 0;
  const whole = kept(() => {
    made += 1;
    return part() + outer.read();
  });
  whole();
  inner.move();
  assert.equal(whole(), 1);
  assert.equal(made, 2, "the inner reading's version moves the outer");
  // Kept by the inner reading, its version is still the outer's.
  const again = kept(() => part());
  again();
  inner.move();
  assert.equal(again(), 2);
});

test("a reading around another stands no longer than what the inner one reads by then", () => {
  const [a, b] = [version(), version()];
  const which = signal("a");
  const inner = kept(() => (which.value === "a" ? a.read() : b.read()));
  const outer = kept(() => inner());
  assert.equal(outer(), 0);
  // A signal turns the inner reading to another version, which answers the same.
  which.value = "b";
  assert.equal(inner(), 0);
  assert.equal(outer(), 0);
  b.move();
  assert.equal(outer(), 1);
});

test("a signal a reading read makes it again, and a view reading it kept still hears it", () => {
  // As a widget's module answers its word from a signal of its own.
  const word = signal("before");
  let made = 0;
  const reading = kept(() => {
    made += 1;
    return word.value;
  });
  /** @type {string[]} */
  const drawn = [];
  const stop = effect(() => void drawn.push(reading()));
  // Kept, as a view reading it again finds it.
  const again = effect(() => void reading());
  assert.equal(made, 1);
  word.value = "after";
  word.value = "third";
  assert.deepEqual(drawn, ["before", "after", "third"]);
  assert.equal(made, 3);
  stop();
  again();
});

test("each key's reading is made when first asked for, and only what moved is made again", () => {
  const [page, other] = [version(), version()];
  const unit = signal(1);
  // Items as a list holds them.
  const [a, b] = [{ name: "a" }, { name: "b" }];
  /** @type {string[]} */
  const made = [];
  const each = keptEach((/** @type {{name: string}} */ item) => {
    made.push(item.name);
    if (item === a) page.read();
    else other.read();
    return item === a ? unit.value : 0;
  });
  each(a);
  each(a);
  assert.deepEqual(made, ["a"], "an item nobody asked about is not made");
  each(b);
  unit.value = 2;
  assert.equal(each(a), 2);
  each(b);
  assert.deepEqual(
    made,
    ["a", "b", "a"],
    "a signal makes again only the item that read it",
  );
  page.move();
  each(a);
  each(b);
  assert.deepEqual(
    made,
    ["a", "b", "a", "a"],
    "a version makes again only the item that read it",
  );
});

test("a key's make may ask for another key, which it then stands no longer than", () => {
  const page = version();
  const [parent, child] = [{ of: null }, { of: null }];
  parent.of = child;
  /** @type {(item: {of: object | null}) => number} */
  const each = keptEach((item) => (item.of ? 1 + each(item.of) : page.read()));
  assert.equal(each(parent), 1);
  assert.equal(each(parent), 1);
  page.move();
  assert.equal(each(parent), 2);
});

test("a reading is made again when an argument differs, a list by its items", () => {
  const [x, y] = [{}, {}];
  let made = 0;
  const reading = kept((/** @type {object} */ one, /** @type {object[]} */ list) => {
    made += 1;
    return list.length + (one === x ? 0 : 10);
  });
  reading(x, [x, y]);
  reading(x, [x, y]);
  assert.equal(made, 1, "a fresh list of the same items is the same argument");
  reading(x, [y, x]);
  assert.equal(made, 2, "the same items in another order differ");
  assert.equal(reading(y, [y, x]), 12);
  assert.equal(made, 3);
});

test("a version that catches up does so before a reading that read it is checked", () => {
  // As the page's watcher takes the changes the browser reports a microtask late.
  let pending = 0;
  let caughtUp = 0;
  /** @type {import("/runtime/state/kept.js").Version} */
  const page = version(() => {
    caughtUp += 1;
    if (!pending) return;
    pending = 0;
    page.move();
  });
  const read = () => {
    page.read();
    return pending;
  };
  let made = 0;
  const inner = kept(() => {
    made += 1;
    return read();
  });
  const outer = kept(() => inner());
  outer();
  assert.equal(made, 1);
  // A change the watcher hasn't taken yet.
  pending = 1;
  outer();
  assert.equal(made, 2, "the outer reading caught the inner's version up first");
  const before = caughtUp;
  outer();
  assert.equal(caughtUp, before + 1, "once for the outer read, not again inside it");
  // A reading that read no version that catches up catches nothing up.
  const counted = version();
  const quiet = kept(() => counted.read());
  quiet();
  quiet();
  assert.equal(caughtUp, before + 1);
});

test("a make that throws keeps nothing, so it and every reading around it are made again", () => {
  const a = version();
  let fail = true;
  let made = 0;
  const reading = kept(() => {
    made += 1;
    a.read();
    if (fail) throw new Error("not yet");
    return "made";
  });
  assert.throws(reading, /not yet/);
  fail = false;
  assert.equal(reading(), "made");
  assert.equal(made, 2);
  // A reading around it that caught the throw is made again once it answers.
  fail = true;
  const failing = kept(() => {
    if (fail) throw new Error("not yet");
    return 1;
  });
  const outer = kept(() => {
    try {
      return failing();
    } catch {
      return -1;
    }
  });
  assert.equal(outer(), -1);
  fail = false;
  assert.equal(outer(), 1);
});
