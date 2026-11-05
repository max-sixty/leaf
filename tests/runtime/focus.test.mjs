/* Who moved the user, and whether they have moved on since.

   focus.js answers both for every owner. Each placement names its cause, and every
   reader of where the user stands hears it. One module keeps the two readings of
   "since": a hold asks whether focus was placed anywhere since it began, since typing in
   the box it holds is the user working there; delayed work asks whether the user did
   anything at all since the gesture that started it. A press on a label leaves the user
   standing on the control they stood on until the press lands. These are asked over
   happy-dom's focus, which moves focus and fires its events as a browser does but lays
   nothing out. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Window } from "happy-dom";

const {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  layerLanding,
  onCurrentLocation,
  onPress,
  openLayer,
  openerOf,
  pressing,
  pressRecords,
  rove,
  takesLetters,
  typesText,
} = await import("/runtime/focus.js");
const { retainUserIntent } = await import("/runtime/user-intent.js");

const heard = [];
onCurrentLocation((node, cause) => heard.push([node, cause]));

function scene() {
  document.body.replaceChildren();
  const box = document.createElement("section");
  const first = document.createElement("input");
  const second = document.createElement("input");
  const other = document.createElement("button");
  box.append(first, second);
  document.body.append(box, other);
  heard.length = 0;
  return { box, first, second, other };
}

const key = (target, key = "a") =>
  target.dispatchEvent(
    new window.KeyboardEvent("keydown", { key, bubbles: true, composed: true }),
  );
const pointer = (type, target) =>
  target.dispatchEvent(
    new window.PointerEvent(type, {
      bubbles: true,
      composed: true,
      isPrimary: true,
      button: 0,
      pointerId: 1,
    }),
  );
// The label's click alone, without the platform's activation of its control, which
// happy-dom would run: the tests focus the control themselves, or leave it unfocused.
const click = (target) =>
  target.dispatchEvent(
    new window.MouseEvent("click", { bubbles: true, composed: true, cancelable: true }),
  );
const settled = () => new Promise((resolve) => setTimeout(resolve));

test("a departing package releases its current location reader", () => {
  const { first, second } = scene();
  const places = [];
  const stop = onCurrentLocation((node) => places.push(node));
  focusDestination(first, "move");
  stop();
  focusDestination(second, "move");
  assert.deepEqual(places, [first]);
});

test("text entry distinguishes editors, typeahead and controls that take no letters", () => {
  const cases = [
    ["input", { type: "text" }, true, true],
    ["input", { type: "number" }, true, true],
    ["input", { type: "date" }, true, true],
    ["input", { type: "checkbox" }, false, false],
    ["input", { type: "range" }, false, false],
    ["textarea", {}, true, true],
    ["leaf-text", {}, true, true],
    ["div", { contenteditable: "true" }, true, true],
    ["select", {}, false, true],
    ["div", { role: "option" }, false, true],
  ];
  for (const [tag, attributes, text, letters] of cases) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes))
      node.setAttribute(name, value);
    assert.equal(typesText(node), text, node.outerHTML);
    assert.equal(takesLetters(node), letters, node.outerHTML);
  }
  for (const absent of [null, undefined]) {
    assert.equal(typesText(absent), false);
    assert.equal(takesLetters(absent), false);
  }
});

test("a placement reaches every reader with the cause it names", () => {
  const { first, second, other } = scene();
  focusDestination(first, "move");
  focusDestination(second, "return");
  focusDestination(other, "step");
  assert.deepEqual(heard, [
    [first, "move"],
    [second, "return"],
    [other, "step"],
  ]);
  assert.throws(() => focusDestination(first), TypeError);
});

test("focus paint follows the settled destination without painting same-script round trips", async () => {
  const { box, first, second } = scene();
  focusDestination(first, "move");
  await settled();
  const writes = [];
  const observer = new MutationObserver((records) => writes.push(...records));
  observer.observe(box, { attributes: true, subtree: true });
  focusDestination(second, "move");
  focusDestination(first, "return");
  await settled();
  assert.deepEqual(
    writes.map(({ attributeName }) => attributeName),
    [],
  );
  assert.equal(first.hasAttribute("data-lf-focus"), true);
  assert.equal(second.hasAttribute("data-lf-focus"), false);
  focusDestination(second, "move");
  await settled();
  observer.disconnect();
  assert.equal(first.hasAttribute("data-lf-focus"), false);
  assert.equal(second.hasAttribute("data-lf-focus"), true);
  assert.equal(box.hasAttribute("data-lf-focus-within"), true);
});

test("a hold gives way to a placement, not to typing where it holds", () => {
  const { box, first, other } = scene();
  focusDestination(first, "move");
  const typed = holdFocus(box);
  key(first);
  const fresh = document.createElement("input");
  first.replaceWith(fresh);
  assert.equal(typed(fresh), true);
  assert.equal(focused(), fresh);

  const placed = holdFocus(box);
  focusDestination(other, "move");
  const again = document.createElement("input");
  fresh.replaceWith(again);
  assert.equal(placed(again), false);
  assert.equal(focused(), other);
});

test("delayed work gives way to any input since its gesture", () => {
  const { first } = scene();
  focusDestination(first, "move");
  const quiet = retainUserIntent();
  assert.equal(quiet(), true);
  const typed = retainUserIntent();
  key(first);
  assert.equal(typed(), false);
});

test("early input ignores inaccessible foreign events but counts keys before interception", async () => {
  const page = new Window({ url: "https://leaf.test/" });
  try {
    let wheel;
    const listen = page.addEventListener.bind(page);
    page.addEventListener = (type, handler, options) => {
      if (type === "wheel" && !wheel) wheel = handler;
      listen(type, handler, options);
    };
    page.eval(
      readFileSync(
        new URL("../../browser/runtime/document-inputs.js", import.meta.url),
        "utf8",
      ),
    );
    const inputs = page.eval('Reflect.get(window, Symbol.for("leaf.inputs"))');
    const heard = [];
    inputs.observe((event) => heard.push(event.type));
    // Native Firefox can call a sandboxed window's wheel listener with a foreign
    // wrapper whose properties are inaccessible and which is not a local Event.
    // Model that browser delivery at its listener, since dispatchEvent itself
    // requires an accessible Event before it can dispatch anything.
    const foreign = new Proxy(
      {},
      {
        get() {
          throw new Error("Permission denied to access event property");
        },
      },
    );
    assert.doesNotThrow(() => wheel(foreign));
    assert.equal(inputs.count, 0);
    assert.deepEqual(heard, []);
    wheel(new page.WheelEvent("wheel"));
    // Bootstrap holds startup shortcuts at window capture. The user's key must
    // count before that handler stops it from reaching the document.
    page.addEventListener("keydown", (event) => event.stopImmediatePropagation(), true);
    page.document.body.dispatchEvent(
      new page.KeyboardEvent("keydown", {
        key: "c",
        bubbles: true,
        composed: true,
      }),
    );
    assert.equal(inputs.count, 2);
    assert.deepEqual(heard, ["wheel", "keydown"]);
    // The module graph evaluates the same input source after early delivery. It
    // must retain both the clock and its subscriptions, without counting twice.
    page.eval(
      readFileSync(
        new URL("../../browser/runtime/document-inputs.js", import.meta.url),
        "utf8",
      ),
    );
    assert.equal(page.eval('Reflect.get(window, Symbol.for("leaf.inputs"))'), inputs);
    page.dispatchEvent(new page.WheelEvent("wheel"));
    assert.equal(inputs.count, 3);
    assert.deepEqual(heard, ["wheel", "keydown", "wheel"]);
  } finally {
    await page.happyDOM.close();
  }
});

test("a press on a label keeps the user on the control they stood on until it lands", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  box.append(label);
  focusDestination(first, "move");
  heard.length = 0;
  pointer("pointerdown", label);
  // The press blurs the field to the body before the platform focuses the control.
  first.blur();
  await settled();
  assert.equal(focused(), first);
  assert.notEqual(holdFocus(box), null);
  assert.deepEqual(heard, []);
  pointer("pointerup", label);
  click(label);
  check.focus();
  assert.equal(focused(), check);
  assert.deepEqual(heard, [[check, "press"]]);
});

test("a label press through a focusable container tells no reader of the container", async () => {
  scene();
  const thread = document.createElement("section");
  thread.tabIndex = -1;
  const field = document.createElement("input");
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  thread.append(field, label);
  document.body.append(thread);
  focusDestination(field, "move");
  const held = holdFocus(thread);
  heard.length = 0;
  pointer("pointerdown", label);
  // The press's default focuses the containing thread before its click.
  thread.focus();
  await settled();
  assert.deepEqual(heard, []);
  assert.equal(focused(), field);
  pointer("pointerup", label);
  click(label);
  check.focus();
  await settled();
  assert.deepEqual(heard, [[check, "press"]]);
  assert.equal(held(), false);
});

test("a label press whose control takes no focus leaves the user nowhere, by their own move", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  box.append(label);
  focusDestination(first, "move");
  const held = holdFocus(box);
  heard.length = 0;
  pointer("pointerdown", label);
  first.blur();
  pointer("pointerup", label);
  click(label);
  await settled();
  assert.deepEqual(heard, [[null, "move"]]);
  assert.equal(held(), false);
  assert.equal(document.activeElement, document.body);
});

test("a native menu lands a label press, whose release it swallowed", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  label.append(
    "Agree",
    Object.assign(document.createElement("input"), { type: "checkbox" }),
  );
  box.append(label);
  focusDestination(first, "move");
  pointer("pointerdown", label);
  first.blur();
  label.dispatchEvent(
    new window.MouseEvent("contextmenu", { bubbles: true, composed: true }),
  );
  await settled();
  assert.equal(focused(), document.body);
});

test("delayed work follows a hold that carries the user to the node replacing theirs", () => {
  const { box, first } = scene();
  focusDestination(first, "move");
  const mayFocus = retainUserIntent();
  const restore = holdFocus(box);
  const fresh = document.createElement("input");
  first.replaceWith(fresh);
  assert.equal(restore(fresh), true);
  assert.equal(mayFocus(), true);
  // A second render carries the user on again before they do anything.
  const again = holdFocus(box);
  const newer = document.createElement("input");
  fresh.replaceWith(newer);
  assert.equal(again(newer), true);
  assert.equal(mayFocus(), true);
  key(newer);
  assert.equal(mayFocus(), false);
});

test("a hold leaves a still-painted inert layer for its replacement", () => {
  const { box, first, other } = scene();
  focusDestination(first, "move");
  const restore = holdFocus(box);
  // A closing layer can keep painting through its fade while the browser has
  // not yet blurred its control. Its old focus must not satisfy the hold.
  box.inert = true;
  assert.equal(restore(other), true);
  assert.equal(focused(), other);
});

test("a keyed hold lands on the row keyed the same, or the nearest that survived", () => {
  scene();
  const list = document.createElement("ul");
  const row = (key) => {
    const item = document.createElement("button");
    item.dataset.row = key;
    return item;
  };
  list.append(row("a"), row("b"), row("c"));
  document.body.append(list);
  focusDestination(list.children[1], "move");
  const same = holdFocus(list, { key: "data-row" });
  list.replaceChildren(row("a"), row("b"), row("c"));
  assert.equal(same(), true);
  assert.equal(focused(), list.children[1]);

  const gone = holdFocus(list, { key: "data-row" });
  list.replaceChildren(row("a"), row("c"));
  assert.equal(gone(), true);
  assert.equal(focused().dataset.row, "c");
});

test("a keyed hold reads the rows once however many held keys have gone", () => {
  scene();
  const list = document.createElement("ul");
  const rows = (prefix) =>
    Array.from({ length: 50 }, (_, at) => {
      const item = document.createElement("button");
      item.dataset.row = `${prefix}${at}`;
      return item;
    });
  list.append(...rows("old"));
  document.body.append(list);
  focusDestination(list.children[25], "move");
  const held = holdFocus(list, { key: "data-row" });
  list.replaceChildren(...rows("new"));
  let reads = 0;
  const read = list.querySelectorAll.bind(list);
  list.querySelectorAll = (selector) => (reads++, read(selector));
  const outside = document.createElement("button");
  document.body.append(outside);
  held(outside);
  assert.equal(focused(), outside);
  assert.equal(reads, 1);
});

test("closing a layer tells the readers only where the user ends up", () => {
  const { box, first, other } = scene();
  focusDestination(first, "move");
  heard.length = 0;
  closeLayer(
    () => {
      first.blur();
      box.hidden = true;
      other.focus();
    },
    () => focusDestination(document.body.querySelector("button"), "return"),
  );
  assert.deepEqual(heard, [[other, "return"]]);
});

test("a roving group offers one Tab stop", () => {
  scene();
  const items = [0, 1, 2].map(() => document.createElement("button"));
  rove(items, items[1]);
  assert.deepEqual(
    items.map((item) => item.getAttribute("tabindex")),
    ["-1", "0", "-1"],
  );
});

test("a keyed hold reads its rows in the shadow tree they stand in, and lands on the like control", async () => {
  scene();
  const host = document.createElement("div");
  document.body.append(host);
  const root = host.attachShadow({ mode: "open" });
  const row = (key) => {
    const item = document.createElement("li");
    item.dataset.row = key;
    const remove = document.createElement("button");
    remove.className = "remove";
    item.append(document.createElement("button"), remove);
    return item;
  };
  root.append(row("a"), row("b"), row("c"));
  focusDestination(root.children[1].querySelector(".remove"), "move");
  const restore = holdFocus(host, { key: "data-row" });
  root.replaceChildren(row("a"), row("c"));
  assert.equal(restore(), true);
  const at = focused();
  assert.equal(at.classList.contains("remove"), true);
  await settled();
  assert.equal(at.hasAttribute("data-lf-focus"), true);
  assert.equal(host.hasAttribute("data-lf-focus"), false);
  assert.equal(host.hasAttribute("data-lf-focus-within"), true);
  assert.equal(at.parentElement.dataset.row, "c");
});

test("a layer hands the user back to where it opened from, and a close inside another lands once", () => {
  const { box, first, other } = scene();
  focusDestination(first, "move");
  openLayer(box);
  assert.equal(openerOf(box), first);
  focusDestination(other, "move");
  heard.length = 0;
  closeLayer(
    () =>
      closeLayer(
        () => {},
        () => focusDestination(other, "return"),
      ),
    () => handBack(openerOf(box)),
  );
  assert.equal(focused(), first);
  assert.deepEqual(heard, [[first, "return"]]);
});

test("a close inside another lands the user where the outer close names no landing", () => {
  const { first, other } = scene();
  focusDestination(first, "move");
  heard.length = 0;
  closeLayer(() =>
    closeLayer(
      () => {},
      () => focusDestination(other, "return"),
    ),
  );
  assert.equal(focused(), other);
  assert.deepEqual(heard, [[other, "return"]]);
});

test("a landing built away from its close runs only as a layer closes", () => {
  const { first, other } = scene();
  focusDestination(other, "move");
  const land = layerLanding((node) => handBack(node));
  assert.throws(() => land(first), /runs only as the layer closes/);
  // A close a landing makes hides as any close does, and lands nobody while it hides.
  closeLayer(
    () => {},
    () => closeLayer(() => assert.throws(() => land(first), /runs only/)),
  );
  assert.equal(focused(), other);
  closeLayer(
    () => {},
    () => land(first),
  );
  assert.equal(focused(), first);
});

test("a failed focus arrival publishes the departure to the document", async () => {
  const { first, other } = scene();
  focusDestination(first, "move");
  heard.length = 0;
  other.addEventListener("focus", () => other.remove(), { once: true });
  other.focus();
  await settled();
  assert.equal(focused(), document.body);
  assert.deepEqual(heard, [[null, "move"]]);
});

test("what an owner keeps of a press lasts until the press is over, and no longer", async () => {
  const { box, other } = scene();
  const kept = pressRecords();
  const overs = [];
  const stop = onPress(() => () => () => overs.push("over"));
  const down = (target) => {
    pointer("pointerdown", target);
    kept.keep({ pointerId: 1 }, target.localName);
  };
  // A widget can stop its release; the canonical owner still hears it first.
  box.addEventListener("pointerup", (event) => event.stopImmediatePropagation());
  // A release leaves the press owed its click, so what was kept still reads.
  down(box);
  pointer("pointerup", box);
  await settled();
  assert.equal(pressing()?.released, true);
  assert.equal(kept.kept(), "section");
  // The next press is over the one before before it begins, owed click or not.
  down(other);
  assert.deepEqual(overs, ["over"]);
  assert.equal(kept.kept(), "button");
  // A cancel owes no click: the press is over at the task after it.
  pointer("pointercancel", other);
  assert.equal(kept.kept(), "button");
  await settled();
  assert.equal(pressing(), null);
  assert.equal(kept.kept(), null);
  // A newer input follows every event a release owes: a key ends the stage it leaves.
  down(box);
  pointer("pointerup", box);
  key(box);
  await settled();
  assert.equal(pressing(), null);
  assert.deepEqual(overs, ["over", "over", "over"]);
  // A native menu swallows release, so it also ends the owner's work.
  down(box);
  box.dispatchEvent(new window.MouseEvent("contextmenu", { bubbles: true }));
  await settled();
  assert.equal(pressing(), null);
  assert.deepEqual(overs, ["over", "over", "over", "over"]);
  stop();
});
