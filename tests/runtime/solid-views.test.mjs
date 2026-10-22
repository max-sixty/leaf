/* A Solid view tracks the fields it draws while preserving native editing state. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  createView,
  html,
  For,
  createSignal,
  createMemo,
  flush,
  watchReaction,
} from "/vendor/browser-runtime.js";

test("an imperative draw follows completed reads without waking on a lazy first pull", () => {
  for (const memoized of [false, true]) {
    const [value, setValue] = createSignal(0);
    const memo = createMemo(() => value() * 2, { lazy: true });
    let wakes = 0;
    const stop = watchReaction(
      () => {
        assert.equal(memoized ? memo() : value(), 0);
        flush(() => setValue(1));
      },
      () => {
        wakes++;
      },
    );
    flush();
    assert.equal(wakes, 1, "the completed read was changed by its own draw");
    stop();
    flush(() => setValue(2));
    assert.equal(wakes, 1, "a disposed draw no longer follows its inputs");
    const stopLazy = watchReaction(
      () => {
        assert.equal(memo(), 4);
      },
      () => {
        wakes++;
      },
    );
    flush();
    assert.equal(wakes, 1, "the first pull returns fresh data and owes no second draw");
    stopLazy();
  }
});

test("a retained native view outlives the imperative draw that first mounts it", () => {
  const host = document.createElement("section");
  const [value, setValue] = createSignal(0);
  let view;
  const stop = watchReaction(
    () => {
      value();
      view = createView(host, (read) => html`<output>${() => read().value}</output>`, {
        value: "first",
      });
    },
    () => {},
  );
  flush(() => setValue(1));
  view.update({ value: "second" });
  assert.equal(host.textContent, "second");
  stop();
  view.dispose();
});

test("updating one field leaves an independent binding and native editor alone", () => {
  const host = document.createElement("section");
  document.body.append(host);
  let labelReads = 0;
  const view = createView(
    host,
    (props) =>
      html` <label
          >${() => {
            labelReads++;
            return props().label;
          }}<input
        /></label>
        <output>${() => props().count}</output>`,
    { label: "Notes", count: 0 },
  );
  const input = host.querySelector("input");
  input.value = "An unfinished sentence";
  input.focus();
  input.setSelectionRange(3, 13);
  view.update({ label: "Notes", count: 1 });
  assert.equal(host.querySelector("output").textContent, "1");
  assert.equal(labelReads, 1);
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "An unfinished sentence");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [3, 13]);
  view.dispose();
  host.remove();
});

test("reordering keyed records preserves each row's kind and native editor", () => {
  const host = document.createElement("section");
  document.body.append(host);
  const row = { key: "command", kind: "entry", entry: { label: "Run" } };
  const heading = { key: "heading", kind: "heading", title: "Commands" };
  const view = createView(
    host,
    (read) =>
      For({
        get each() {
          return read().items;
        },
        keyed: (item) => item.key,
        children: (item) =>
          item().kind === "entry"
            ? html`<label>${() => item().entry.label}<input /></label>`
            : html`<h2>${() => item().title}</h2>`,
      }),
    { items: [row, heading] },
  );
  const input = host.querySelector("input");
  input.value = "Unfinished";
  input.focus();
  input.setSelectionRange(2, 6);
  view.update({
    items: [
      { ...heading, title: "Available" },
      { ...row, entry: { label: "Execute" } },
    ],
  });
  assert.equal(host.firstElementChild.tagName, "H2");
  assert.equal(host.firstElementChild.textContent, "Available");
  assert.equal(host.querySelector("label").textContent, "Execute");
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "Unfinished");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [2, 6]);
  view.dispose();
  host.remove();
});
