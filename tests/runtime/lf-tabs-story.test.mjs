/* The tab set's update as a story (`Story`, @effect/ui/testing): which tab the user is
   on and how they got there, which the strip's mount shows through Leaf. The drawing on
   a page, and the switch it makes, are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Effect } from "/vendor/effect-ui.js";
import { Tabs } from "../../packages/default/widgets/lf-tabs.js";

/** @param {string} id */
const panel = (id) => ({
  panel: document.createElement("lf-tab"),
  id,
  label: id,
  summary: null,
  group: null,
  face: null,
  changed: 0,
  asks: false,
  onUser: 0,
  onAgent: 0,
  open: 0,
  total: 0,
  only: null,
});

const props = {
  panels: [panel("plan"), panel("risks"), panel("notes")],
  side: false,
  parts: false,
  root: false,
  pageFlow: false,
  name: "",
  agent: "Claude",
  opening: "risks",
};

/** @param {(s: any) => void} story */
const tell = (story) =>
  Effect.gen(function* () {
    story(yield* Story.make(Tabs, props));
  }).pipe(Effect.scoped, Effect.runSync);

test("a set opens on the tab Leaf names, before the user chooses one", () =>
  tell((s) => assert.deepEqual(s.model, { active: null, via: null, step: 0, travels: false })));

test("a press opens its tab, and says it was the pointer's", () =>
  tell((s) => {
    s.send({ _tag: "Chose", id: "plan", pointer: true });
    assert.deepEqual(s.model, { active: "plan", via: "pointer", step: 1, travels: true });
  }));

test("the line travels from a neighbour until the strip settles, and jumps past one", () =>
  tell((s) => {
    s.send({ _tag: "Chose", id: "notes", pointer: true });
    assert.equal(s.model.travels, true);
    s.send({ _tag: "Settled" });
    assert.equal(s.model.travels, false);
    s.send({ _tag: "Chose", id: "plan", pointer: true });
    assert.deepEqual(s.model, { active: "plan", via: "pointer", step: 2, travels: false });
  }));

test("a key opens its tab, and the open tab pressed again is a step of its own", () =>
  tell((s) => {
    s.send({ _tag: "Chose", id: "notes", pointer: false });
    s.send({ _tag: "Chose", id: "notes", pointer: false });
    assert.deepEqual(s.model, { active: "notes", via: "key", step: 2, travels: false });
  }));

test("a tab the set doesn't hold opens nothing", () =>
  tell((s) => {
    s.send({ _tag: "Chose", id: "gone", pointer: true });
    assert.deepEqual(s.model, { active: null, via: null, step: 0, travels: false });
  }));

test("a panel the browser reveals opens its tab, and the open one changes nothing", () =>
  tell((s) => {
    s.send({ _tag: "Revealed", id: "risks" });
    assert.deepEqual(s.model, { active: null, via: null, step: 0, travels: false });
    s.send({ _tag: "Revealed", id: "plan" });
    assert.deepEqual(s.model, { active: "plan", via: "reveal", step: 1, travels: false });
  }));
