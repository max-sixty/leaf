/* A reading kept by `kept` or `keptEach` is made again exactly when a signal it read
   changes or an input it read answers otherwise, those of a reading made inside it
   included, and keeps nothing a make that threw left half made (kept.js). */
import assert from "node:assert/strict";
import test from "node:test";

import { kept, keptEach, reads } from "/runtime/kept.js";
import { effect, signal } from "/vendor/signals-core.js";

// An input outside the readings, and a reader of it that says so, as the page's
// readers do.
const fact = () => {
  let version = 0;
  const input = () => version;
  return {
    read: () => {
      reads(input);
      return version;
    },
    move: () => void (version += 1),
  };
};

test("a reading is kept while each input it read stands, and made again once one moves", () => {
  const [a, b, unread] = [fact(), fact(), fact()];
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
  assert.equal(made, 1, "an input it never read moves nothing");
  b.move();
  assert.equal(reading(), 1);
  assert.equal(made, 2);
  reading();
  assert.equal(made, 2);
});

test("a reading made inside another adds what it read to that one's inputs", () => {
  const [inner, outer] = [fact(), fact()];
  const part = kept(() => inner.read());
  let made = 0;
  const whole = kept(() => {
    made += 1;
    return part() + outer.read();
  });
  whole();
  inner.move();
  assert.equal(whole(), 1);
  assert.equal(made, 2, "the inner reading's input moves the outer");
  // Kept by the inner reading, its input is still the outer's.
  const again = kept(() => part());
  again();
  inner.move();
  assert.equal(again(), 2);
});

test("a reading around another stands no longer than what the inner one reads by then", () => {
  const [a, b] = [fact(), fact()];
  const which = signal("a");
  const inner = kept(() => (which.value === "a" ? a.read() : b.read()));
  const outer = kept(() => inner());
  assert.equal(outer(), 0);
  // A signal turns the inner reading to another input, which answers the same.
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

test("each key's reading is made when first asked for and kept with every other", () => {
  const page = fact();
  const unit = signal(1);
  // Items as a list holds them.
  const [a, b] = [{ name: "a" }, { name: "b" }];
  /** @type {string[]} */
  const made = [];
  const each = keptEach((/** @type {{name: string}} */ item) => {
    made.push(item.name);
    page.read();
    return item === a ? unit.value : 0;
  });
  each()(a);
  each()(a);
  assert.deepEqual(made, ["a"], "an item nobody asked about is not made");
  each()(b);
  unit.value = 2;
  assert.equal(each()(a), 2);
  each()(b);
  assert.deepEqual(
    made,
    ["a", "b", "a"],
    "a signal makes again only the item that read it",
  );
  page.move();
  const lookup = each();
  lookup(a);
  lookup(b);
  assert.deepEqual(
    made,
    ["a", "b", "a", "a", "b"],
    "an input any item read makes all again",
  );
});

test("a key's make may ask for another key, and a lookup kept answers from the last read", () => {
  const page = fact();
  const [parent, child] = [{ of: null }, { of: null }];
  parent.of = child;
  const each = keptEach((/** @type {{of: object | null}} */ item) =>
    item.of ? 1 + each()(item.of) : page.read(),
  );
  assert.equal(each()(parent), 1);
  assert.equal(each()(parent), 1);
  const saved = each();
  page.move();
  assert.equal(each()(parent), 2);
  assert.equal(saved(parent), 2);
});

test("an input that throws is not kept, so a make that no longer reads it recovers", () => {
  const input = () => {
    throw new Error("unreadable");
  };
  let needs = true;
  const each = keptEach(() => (needs ? reads(input) : 0));
  const item = {};
  assert.throws(() => each()(item), /unreadable/);
  needs = false;
  assert.equal(each()(item), 0);
});

test("a make that throws keeps nothing, and inputs read on the way are asked once", () => {
  const a = fact();
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
  // An input that reads itself on the way, as the page's own readers do.
  let asked = 0;
  const own = () => {
    asked += 1;
    reads(own);
    return 0;
  };
  kept(() => (reads(own), own()))();
  assert.equal(asked, 2, "once to record it, once by the reading itself");
});
