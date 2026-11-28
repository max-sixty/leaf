/* Who moved the user, and whether they have moved on since.

   dom/focus.js answers both for every owner. Each placement names its cause, and every
   reader of where the user stands hears it. One module keeps the two readings of
   "since": a hold asks whether focus was placed anywhere since it began, since typing in
   the box it holds is the user working there; delayed work asks whether the user did
   anything at all since the gesture that started it. A press on a label leaves the user
   standing on the control they stood on until the press lands, and a press on what a
   tab panel holds lands where it would without the panel's stop. These are asked over
   happy-dom's focus, which moves focus and fires its events as a browser does but lays
   nothing out. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Window } from "happy-dom";

// Focus the page took before the runtime loaded: a frame the user pressed into while
// the modules loaded. A choice's ring is drawn from these marks alone (controls.css),
// and a frame's ring from the input that put the user there.
const before = document.createElement("iframe");
// A browser never matches `:focus-visible` on a frame's host; happy-dom does.
before.matches = (selector) =>
  selector !== ":focus-visible" && Element.prototype.matches.call(before, selector);
document.body.append(before);
before.focus();
const {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  layerLanding,
  onCurrentLocation,
  onFocusVisibility,
  onPress,
  openLayer,
  openerOf,
  pressing,
  pressRecords,
  takesLetters,
  typesText,
} = await import("/runtime/dom/focus.js");
const { retainUserIntent } = await import("/runtime/dom/user-intent.js");

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

test("focus held before the runtime loaded wears its marks, and a pressed frame no ring", async () => {
  await settled();
  assert.equal(document.activeElement, before);
  assert.equal(before.hasAttribute("data-lf-focus"), true);
  assert.equal(before.hasAttribute("data-lf-focus-visible"), false);
  assert.equal(document.body.hasAttribute("data-lf-focus-within"), false);
});

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

test("the box a control names shows its focus while the control holds it", async () => {
  const { box, first, second } = scene();
  first.style.setProperty("--lf-focus-box", "section");
  focusDestination(first, "move");
  await settled();
  assert.equal(box.hasAttribute("data-lf-control-focus"), true);
  assert.equal(box.hasAttribute("data-lf-control-focus-visible"), true);
  focusDestination(second, "move");
  await settled();
  assert.equal(box.hasAttribute("data-lf-control-focus"), false);
  assert.equal(box.hasAttribute("data-lf-control-focus-visible"), false);
});

test("a control that stops naming its box while it holds focus takes the box's marks off", async () => {
  const { box, first } = scene();
  const style = document.createElement("style");
  style.textContent = "section > input:not([data-off]) { --lf-focus-box: section; }";
  document.head.append(style);
  focusDestination(first, "move");
  await settled();
  assert.equal(box.hasAttribute("data-lf-control-focus"), true);
  first.toggleAttribute("data-off", true);
  await settled();
  assert.equal(box.hasAttribute("data-lf-control-focus"), false);
  style.remove();
});

test("a box named by something that isn't a selector is reported, and the paint goes on", async () => {
  const { box, first } = scene();
  const reported = [];
  const report = globalThis.reportError;
  globalThis.reportError = (error) => reported.push(error);
  const visibility = [];
  const stop = onFocusVisibility(() => visibility.push(focused()));
  first.style.setProperty("--lf-focus-box", '"section"');
  focusDestination(first, "move");
  await settled();
  stop();
  globalThis.reportError = report;
  assert.equal(reported.length, 1);
  assert.equal(box.hasAttribute("data-lf-control-focus"), false);
  assert.deepEqual(visibility, [first]);
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

test("a hold keeps its place across a closing layer's hand-back to its opener", () => {
  const { box, first } = scene();
  const strip = document.createElement("dialog");
  const inside = document.createElement("button");
  strip.append(inside);
  box.append(strip);
  strip.show();
  focusDestination(inside, "move");
  const restore = holdFocus(box);
  // A render takes the strip away, which hands the user back to its opener as it
  // closes, and draws its replacement.
  strip.close();
  first.focus();
  const again = document.createElement("dialog");
  const fresh = document.createElement("button");
  again.append(fresh);
  strip.replaceWith(again);
  again.show();
  assert.equal(restore(fresh), true);
  assert.equal(focused(), fresh);
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

// A send refused after it moved the user onto a thread that a widget draws in its own
// shadow root returns them to the box, as it does where the thread sits in the page.
test("delayed work taken for the page counts a move inside a widget's shadow tree as its own", () => {
  scene();
  const host = document.createElement("div");
  const box = document.createElement("input");
  const thread = document.createElement("section");
  thread.tabIndex = -1;
  host.attachShadow({ mode: "open" }).append(box, thread);
  document.body.append(host);
  focusDestination(box, "move");
  const untouched = retainUserIntent({ source: document.documentElement });
  focusDestination(thread, "move");
  assert.equal(untouched(), true);
  key(thread);
  assert.equal(untouched(), false);
});

test("a placement takes an element of another window as an element", () => {
  // A playground's preview is a same-origin frame, whose elements are instances of its
  // own window's `Element`, not this one's, and its range control puts focus back
  // inside the frame. happy-dom's windows share one `Element`, so the page's own is
  // swapped for another while the field is placed.
  const { first } = scene();
  const own = globalThis.Element;
  globalThis.Element = class Element {};
  try {
    assert.doesNotThrow(() => focusDestination(first, "move"));
  } finally {
    globalThis.Element = own;
  }
  assert.equal(document.activeElement, first);
});

test("a placement on an element that draws no box stands the user on the first it draws", () => {
  // A link to an author's `<section style="display: contents">`, or a composer closing
  // on a fact row of `dl.lf-facts`, names an element no engine will focus. The first
  // element it draws that takes focus, through any it holds laid out the same way and
  // past any hidden or disabled, is where its content starts.
  const { box, first, other } = scene();
  const wrapper = document.createElement("div");
  const hidden = document.createElement("button");
  const disabled = document.createElement("button");
  hidden.style.display = "none";
  disabled.disabled = true;
  wrapper.append(hidden, disabled, first);
  box.prepend(wrapper);
  box.style.display = wrapper.style.display = "contents";
  focusDestination(other, "move");
  heard.length = 0;
  assert.equal(focusDestination(box, "move"), first);
  assert.equal(document.activeElement, first);
  assert.deepEqual(heard, [[first, "move"]]);
  // A layer closing on such an element, as the comment box on it does, hands back there.
  focusDestination(other, "move");
  handBack(box);
  assert.equal(document.activeElement, first);
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
        new URL("../../browser/runtime/base/document-inputs.js", import.meta.url),
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
        new URL("../../browser/runtime/base/document-inputs.js", import.meta.url),
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

test("a press on what a tab panel holds lands where it would without the panel's stop", async () => {
  const { first } = scene();
  const thread = document.createElement("section");
  thread.tabIndex = -1;
  const panel = document.createElement("div");
  panel.setAttribute("role", "tabpanel");
  panel.tabIndex = 0;
  const words = document.createElement("p");
  words.append("Words in the open tab");
  panel.append(words);
  document.body.append(panel);
  focusDestination(first, "move");
  heard.length = 0;
  // The platform focuses the panel at the press, and keeps it there through a drag,
  // while every reading of where the user is reads where the press will land.
  pointer("pointerdown", words);
  panel.focus();
  await settled();
  assert.deepEqual(heard, []);
  assert.equal(document.activeElement, panel);
  assert.equal(focused(), document.body);
  pointer("pointerup", words);
  click(words);
  await settled();
  assert.deepEqual(heard, [[null, "move"]]);
  assert.equal(document.activeElement, document.body);

  // Inside a box a press focuses, the press lands on that box.
  thread.append(panel);
  document.body.append(thread);
  heard.length = 0;
  pointer("pointerdown", words);
  panel.focus();
  assert.equal(focused(), thread);
  pointer("pointerup", words);
  click(words);
  await settled();
  assert.deepEqual(heard, [[thread, "press"]]);

  // The keyboard reaching the panel stands on it, and a press on its words then lands
  // as any other does.
  heard.length = 0;
  key(thread, "Tab");
  panel.focus();
  assert.deepEqual(heard, [[panel, "step"]]);
  heard.length = 0;
  pointer("pointerdown", words);
  pointer("pointerup", words);
  click(words);
  await settled();
  assert.deepEqual(heard, [[thread, "press"]]);

  // A tap focuses at its click, after the release, and lands a task later.
  heard.length = 0;
  pointer("pointerdown", words);
  pointer("pointerup", words);
  panel.focus();
  click(words);
  assert.equal(document.activeElement, panel);
  assert.equal(focused(), thread);
  await settled();
  assert.deepEqual(heard, [[thread, "press"]]);

  // A control that takes no focus from a press, as a button in WebKit, leaves the panel
  // the browser's focus, and the press lands as one on the panel's words.
  const button = document.createElement("button");
  panel.append(button);
  heard.length = 0;
  pointer("pointerdown", button);
  panel.focus();
  pointer("pointerup", button);
  click(button);
  await settled();
  assert.deepEqual(heard, [[thread, "press"]]);
});

test("a key or a placement during a press on a tab panel takes over from it", async () => {
  const { first } = scene();
  const panel = document.createElement("div");
  panel.setAttribute("role", "tabpanel");
  panel.tabIndex = 0;
  const words = document.createElement("p");
  words.append("Words in the open tab");
  panel.append(words);
  document.body.append(panel);
  // Away and back by the keyboard while the pointer is held, then the release.
  pointer("pointerdown", words);
  panel.focus();
  key(panel, "Tab");
  first.focus();
  key(first, "Tab");
  panel.focus();
  pointer("pointerup", words);
  click(words);
  await settled();
  assert.equal(document.activeElement, panel);
  // A placement on the panel itself.
  first.focus();
  heard.length = 0;
  pointer("pointerdown", words);
  focusDestination(panel, "move");
  pointer("pointerup", words);
  click(words);
  await settled();
  assert.deepEqual(heard, [[panel, "move"]]);
  assert.equal(document.activeElement, panel);
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
