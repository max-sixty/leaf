/* A state answer that carries the changes since the reading a tab holds completes to
   the whole answer, and keeps every part the changes leave alone as the very object
   the held reading had.

   The server writes each case (`served_records.py`, `tail_cases`): the reading the tab
   held, the answer to a request naming it, and the whole answer at the same position,
   so the completion is held to what the server would have sent rather than to a
   fixture's idea of it. */
import assert from "node:assert/strict";
import test from "node:test";
import { isDeepStrictEqual } from "node:util";
import { servedTails } from "../served.mjs";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// Nothing here is sent; the page's background requests are answered and dropped.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { completeState, heldHeaders } = await import("/runtime/layer-client.js");

// Every object of `done` equal to the one at its place in `held` is that object, and
// every item of a list equal to an item the held list had is that item, down into an
// item that changed, such as a thread one reply joined: the readers after completion
// compare by identity, so a copy would read as a change.
/** @param {unknown} item */
const named = (item) =>
  item && typeof item === "object" && "id" in item ? item.id : undefined;
/** @param {unknown} held @param {unknown} done @param {string} path */
function assertKept(held, done, path) {
  if (!held || !done || typeof held !== "object" || typeof done !== "object") return;
  if (isDeepStrictEqual(held, done)) {
    assert.equal(done, held, `${path} was copied`);
    return;
  }
  if (Array.isArray(held) && Array.isArray(done)) {
    for (const item of done)
      if (held.some((each) => isDeepStrictEqual(each, item)))
        assert.ok(held.includes(item), `an item of ${path} was copied`);
      else if (named(item) !== undefined) {
        const before = held.find((each) => named(each) === named(item));
        if (before) assertKept(before, item, `${path}[${named(item)}]`);
      }
    return;
  }
  for (const [key, value] of Object.entries(done))
    if (Object.hasOwn(held, key))
      assertKept(
        /** @type {Record<string, unknown>} */ (held)[key],
        value,
        `${path}.${key}`,
      );
}

for (const { name, held, tail, whole } of servedTails())
  test(`an answer completes the held reading to the whole answer: ${name}`, () => {
    const holding = { data: held.data, state: held };
    assert.equal(
      heldHeaders(holding)["Leaf-Held-Basis"],
      held.browser.basis.key,
      "the request names the reading the tab holds",
    );
    const done = completeState(tail, holding);
    assert.deepEqual(done, whole);
    // The log and the data keep their own mechanisms.
    const { events: _events, data: _data, ...rest } = done;
    assertKept(held, rest, "the answer");
  });

test("an answer extending a reading the tab did not name is a fault", () => {
  const [{ held, tail }, other] = servedTails();
  assert.throws(
    () => completeState(tail, { data: held.data, state: other.held }),
    /extends a reading this tab did not name/,
  );
});

test("an answer that moves every item of a list puts each after the one it names", () => {
  const ids = Array.from({ length: 4096 }, (_, at) => String(at));
  const data = { version: "v", sources: {} };
  // Reversed: the last item stays where it was, and each other one follows the one
  // before it in the new order.
  const reversed = ids.toReversed();
  const after = reversed
    .slice(0, -1)
    .map((id, at) => [id, at ? reversed[at - 1] : null]);
  const held = {
    browser: { basis: { key: "held" }, list: ids.map((id) => ({ id })) },
    events: [],
  };
  const done = completeState(
    {
      since: { key: "held" },
      patch: [{ at: ["browser", "list"], by: "id", after }],
      events: [],
      data,
    },
    { data, state: /** @type {never} */ (held) },
  );
  assert.deepEqual(
    /** @type {{list: {id: string}[]}} */ (
      /** @type {unknown} */ (done.browser)
    ).list.map(({ id }) => id),
    reversed,
  );
});
