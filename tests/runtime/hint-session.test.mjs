/* The hint session's state machine (`createHintSession`): what a typed letter, Tab,
   Enter and Escape do to an armed map, and when the map is read again.

   Each case arms a session over a scene of links the test states, the way a caller
   (go-to-sequence.js, target-picker.js) does: `read` names the links in view that
   nothing covers, each with its code and its box, and `layout` puts a chip on each. A
   case awaits `arm`, which stands once the frames arming paints are drawn (hints.js), a
   paint is called where a frame would run one, and a scroll is the `scroll` and
   `scrollend` events the page's scroll tracking hears (dom/arrivals.js), so no case waits
   on a clock. The live region speaks after its own delay (transport/notifications.js), which the
   mocked timers run. */

import assert from "node:assert/strict";
import test from "node:test";

import { createHintSession, codedHints } from "/runtime/readings/key-badges/hints.js";
import { declareCover } from "/runtime/dom/geometry.js";
import { setQuickShortcuts } from "/runtime/dom/keyboard/bindings.js";
import { commandScope, keys } from "/runtime/dom/keyboard/scopes.js";
import { liveEl } from "/runtime/transport/notifications.js";
import { mountRepaint } from "/runtime/dom/repaint.js";
import { nextRender } from "/runtime/lib/frame-pass.js";
import { html } from "/vendor/lit.js";

// Three letters, so a fourth link branches: a, s, da, ds.
const KEYS = ["a", "s", "d"];

test("generated addresses retain members and expand the last shortest leaf", () => {
  const members = Array.from({ length: 5 }, (_, id) => ({ id }));
  assert.deepEqual(codedHints(members, "ad"), [
    { id: 0, code: "aa" },
    { id: 1, code: "ad" },
    { id: 2, code: "da" },
    { id: 3, code: "dda" },
    { id: 4, code: "ddd" },
  ]);
});

let sessions = 0;

function hintMap(t, names) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const layer = document.createElement("div");
  document.body.append(layer);
  const links = new Map();
  const link = (name) => {
    if (!links.has(name)) {
      const node = document.createElement("a");
      node.textContent = name;
      // Nothing is laid out here, so each link states its own box, and counts the
      // times it is read.
      const top = 20 + 40 * links.size;
      node.getBoundingClientRect = () => {
        boxReads += 1;
        return new DOMRect(10, top, 80, 20);
      };
      node.getClientRects = () => [node.getBoundingClientRect()];
      document.body.append(node);
      links.set(name, node);
    }
    return links.get(name);
  };
  let inView = names;
  // Links the chrome covers, the covers it declares over them (dom/geometry.js,
  // `declareCover`), and the filter on the map.
  let covered = new Set();
  /** @type {(() => void)[]} */
  let covers = [];
  let keep = () => true;
  let boxReads = 0;
  const taken = [];
  const session = createHintSession({
    layer,
    walk: `hint-session-${++sessions}`,
    read: () => {
      return codedHints(
        inView
          .filter((name) => !covered.has(name))
          .map((name) => ({
            name,
            member: link(name),
            rect: link(name).getBoundingClientRect(),
          })),
        KEYS.join(""),
      );
    },
    identity: (candidate) => candidate.member,
    kept: (candidate) => keep(candidate),
    layout: (candidates, { current }) =>
      candidates.map((candidate) => ({
        candidate,
        model: {
          key: candidate.name,
          code: candidate.code,
          className: `lf-key-hint${candidate === current ? " lf-current" : ""}`,
        },
        target: candidate.rect,
        placement: "corner",
        left: candidate.rect.left,
        top: candidate.rect.top,
      })),
    template: (model) =>
      html`<span class=${model.className} data-code=${model.code}>${model.code}</span>`,
    take: (candidate) => taken.push(candidate.name),
    words: {
      describe: (candidate) => `Link, ${candidate.name}`,
      all: "All hints.",
    },
  });
  session.mount();
  const [walk, choose] = session.walkRows({
    id: "fixture.hint",
    choose: { title: "go there", description: "Go to the heard target" },
  });
  // The rows answer where the user is, as a caller's scope puts them, so a heard target
  // says the key that takes it.
  const owner = document.createElement("div");
  owner.tabIndex = -1;
  document.body.append(owner);
  keys(owner, commandScope("Hints", [walk, choose]));
  owner.focus();
  t.after(() => {
    owner.remove();
    session.disarm();
    layer.remove();
    for (const node of links.values()) node.remove();
    for (const release of covers) release();
  });
  return {
    session,
    taken,
    links,
    show: (names) => (inView = names),
    // Covers links with the chrome, as the panel growing over them does.
    cover: (names) => {
      covered = new Set(names);
      for (const release of covers) release();
      covers = names.map((name) => {
        const box = links.get(name).getBoundingClientRect();
        return declareCover(document.createElement("div"), () => box);
      });
    },
    boxReads: () => boxReads,
    filter: (matches) => {
      keep = matches;
      return session.narrow();
    },
    // Moves a link down the page, as a layout that reflows it does.
    move: (name, by) => {
      const node = links.get(name);
      const box = node.getBoundingClientRect();
      node.getBoundingClientRect = () =>
        new DOMRect(box.x, box.y + by, box.width, box.height);
    },
    seat: (code) =>
      layer.querySelector(`[data-code="${code}"]`).closest(".lf-chip-seat"),
    tab: () => walk.runKey("Tab"),
    shiftTab: () => walk.runKey("Shift+Tab"),
    enter: () => choose.run(),
    canChoose: () => choose.when(),
    // The codes of the chips on screen, and the one the walk stands on.
    shown: () =>
      [...layer.querySelectorAll("[data-code]")]
        .filter((chip) => chip.closest(".lf-chip-seat").style.visibility !== "hidden")
        .map((chip) => chip.dataset.code),
    current: () => layer.querySelector(".lf-current")?.dataset.code ?? null,
    // What the live region says once its delay has run.
    heard: () => {
      t.mock.timers.tick(30);
      return liveEl.textContent;
    },
  };
}

const scrollStarts = () => document.dispatchEvent(new Event("scroll"));
const scrollEnds = () => document.dispatchEvent(new Event("scrollend"));

test("a letter narrows the map, one that names nothing changes nothing, and the letter that completes a code takes it", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "da", "ds"]);

  map.session.type("d");
  assert.equal(map.heard(), "2 targets remain.");
  map.session.paint();
  assert.deepEqual(map.shown(), ["da", "ds"]);

  map.session.type("f");
  assert.equal(map.heard(), "No hint df. The current hints are unchanged.");
  map.session.paint();
  assert.deepEqual(map.shown(), ["da", "ds"]);
  assert.deepEqual(map.taken, []);

  // A complete code acts at once, with no terminator or timeout.
  map.session.type("s");
  assert.deepEqual(map.taken, ["four"]);
});

test("Escape gives back one letter at a time, then hands Escape on", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.session.type("d");

  assert.equal(map.session.backOneLetter(), true);
  assert.equal(map.heard(), "All hints.");
  assert.equal(map.session.prefix(), "");
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "da", "ds"]);
  // Nothing left to give back: the caller's Escape takes its own next step.
  assert.equal(map.session.backOneLetter(), false);
});

test("Tab and Shift+Tab walk the map aloud, round from either end, and Enter takes the one heard", async (t) => {
  const map = hintMap(t, ["one", "two"]);
  await map.session.arm();
  map.session.paint();
  assert.equal(map.canChoose(), false, "Enter is offered before anything is heard");

  map.tab();
  assert.equal(map.heard(), "Hint a: Link, one. Enter go there");
  map.session.paint();
  assert.equal(map.current(), "a");
  map.tab();
  assert.equal(map.heard(), "Hint s: Link, two. Enter go there");
  map.tab();
  assert.equal(map.heard(), "Hint a: Link, one. Enter go there");
  map.shiftTab();
  assert.equal(map.heard(), "Hint s: Link, two. Enter go there");
  map.session.paint();
  assert.equal(map.current(), "s");

  assert.equal(map.canChoose(), true);
  map.enter();
  assert.deepEqual(map.taken, ["two"]);
});

test("a walk begun with Shift+Tab starts at the last target and walks back", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.shiftTab();
  assert.equal(map.heard(), "Hint d: Link, three. Enter go there");
  map.shiftTab();
  assert.equal(map.heard(), "Hint s: Link, two. Enter go there");
});

test("a typed letter puts the walk back at the head of what it leaves", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.tab();
  map.session.type("d");
  assert.equal(map.canChoose(), false);
  map.tab();
  assert.equal(map.heard(), "Hint da: Link, three. Enter go there");
});

test("a target that left the scene is not taken by its stale code", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.session.type("d");
  // The map is frozen while a code is part typed, so "da" still names three.
  map.show(["one", "two", "four"]);
  map.session.paint();
  assert.deepEqual(map.shown(), ["da", "ds"]);

  map.session.type("a");
  assert.equal(map.heard(), "That target is no longer visible. The hints are reset.");
  assert.deepEqual(map.taken, []);
  assert.equal(map.session.prefix(), "");
  assert.deepEqual(
    map.session.candidates().map(({ name, code }) => [name, code]),
    [
      ["one", "a"],
      ["two", "s"],
      ["four", "d"],
    ],
  );
});

test("a whole map is read again when a member leaves the document", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.session.paint();
  map.links.get("two").remove();
  map.show(["one", "three"]);
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s"]);
  assert.deepEqual(
    map.session.candidates().map(({ name }) => name),
    ["one", "three"],
  );
});

test("a scroll holds the map as read, and its end reads the scene again", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.session.paint();
  map.tab();
  map.session.paint();
  assert.equal(map.current(), "a");

  // While the page moves, the chips the user is reading keep their codes, and a link
  // arriving mid-scroll is not named on the frame it appears.
  scrollStarts();
  t.after(scrollEnds);
  map.show(["bottom"]);
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "d"]);

  // At rest, the map is the scene now in view, and the heard link has left it.
  scrollEnds();
  map.session.paint();
  assert.deepEqual(map.shown(), ["a"]);
  assert.equal(map.current(), null);
  assert.equal(map.canChoose(), false);

  // The old code of a link that scrolled away acts nowhere.
  map.session.type("s");
  assert.equal(map.heard(), "No hint s. The current hints are unchanged.");
  assert.deepEqual(map.taken, []);
  map.session.type("a");
  assert.deepEqual(map.taken, ["bottom"]);
});

test("a letter typed during a scroll hides the chips it rules out", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.session.paint();
  scrollStarts();
  t.after(scrollEnds);
  map.session.type("d");
  map.session.paint();
  assert.deepEqual(map.shown(), ["da", "ds"]);
});

test("a map armed while the page is in flight shows nothing until the scroll settles", async (t) => {
  const map = hintMap(t, ["one", "two"]);
  scrollStarts();
  t.after(scrollEnds);
  await map.session.arm();
  map.session.paint();
  assert.deepEqual(map.shown(), []);

  map.show(["two", "three"]);
  scrollEnds();
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s"]);
  assert.deepEqual(
    map.session.candidates().map(({ name }) => name),
    ["two", "three"],
  );
});

test("a resize reads the scene again and keeps the heard hint where it still stands", async (t) => {
  const map = hintMap(t, ["one", "two"]);
  await map.session.arm();
  map.tab();
  map.session.paint();
  assert.equal(map.current(), "a");

  map.show(["one", "two", "three"]);
  window.dispatchEvent(new Event("resize"));
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "d"]);
  assert.equal(map.current(), "a");
  assert.equal(map.canChoose(), true);
});

test("without character routes the chips go, and the walk and Enter remain", async (t) => {
  const map = hintMap(t, ["one", "two"]);
  await map.session.arm();
  map.session.paint();
  setQuickShortcuts(false);
  t.after(() => setQuickShortcuts(true));
  map.session.paint();
  assert.deepEqual(map.shown(), []);

  map.tab();
  assert.equal(map.heard(), "Link, one. Enter go there");
  map.session.paint();
  // The heard target's chip names the key that takes it rather than a code.
  const native = document.querySelector("[data-lf-hint-native]");
  assert.equal(native?.dataset.lfHintNative, "Enter");
  map.enter();
  assert.deepEqual(map.taken, ["one"]);
});

test("a disarmed map paints nothing and is read fresh when armed again", async (t) => {
  const map = hintMap(t, ["one", "two"]);
  await map.session.arm();
  map.session.type("s");
  map.session.disarm();
  map.session.paint();
  assert.equal(map.session.armed(), false);
  assert.deepEqual(map.shown(), []);

  map.show(["three"]);
  await map.session.arm();
  assert.equal(map.session.prefix(), "");
  map.session.paint();
  assert.deepEqual(map.shown(), ["a"]);
});

test("a filter narrows the map to the members it keeps, their codes and seats unchanged", async (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  await map.session.arm();
  map.session.paint();
  const seat = map.seat("ds");
  const stood = seat.style.cssText;
  const kept = map.filter(({ name }) => name.startsWith("t"));
  assert.deepEqual(
    kept.map(({ name, code }) => [name, code]),
    [
      ["two", "s"],
      ["three", "da"],
    ],
  );
  map.session.paint();
  assert.deepEqual(map.shown(), ["s", "da"]);
  map.filter(() => true);
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "da", "ds"]);
  assert.equal(map.seat("ds"), seat);
  assert.equal(seat.style.cssText, stood);
});

// The walk's rows stand on whether the filtered map holds anyone, so a re-read that
// empties or refills it asks for the keys again even while the unfiltered scene still
// holds members.
test("a re-read that empties or refills a filtered map repaints the keys", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  let frames = 0;
  const frame = () => new Promise((resolve) => nextRender(resolve));
  mountRepaint({ reflectKeys: () => frames++ });
  t.after(() => mountRepaint({}));
  await map.session.arm();
  map.filter(({ name }) => name.startsWith("t"));
  map.session.paint();
  await frame();
  assert.equal(map.canChoose(), false);

  for (const scene of [["one"], ["one", "two"]]) {
    map.show(scene);
    map.session.invalidate();
    await frame();
    const before = frames;
    map.session.paint();
    await frame();
    assert.ok(frames > before, `no repaint after the map read ${scene}`);
  }
  assert.deepEqual(map.shown(), ["s"]);
});

// A revision or an opening disclosure moves the page under an armed map with no scroll:
// each chip rides its target by its anchor, and the letters the user has read stay.
test("a page that moves under the map keeps every letter and the walk", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.session.paint();
  map.tab();
  map.tab();
  map.session.paint();
  assert.equal(map.current(), "s");
  map.move("one", 100);
  map.show(["new", "one", "two", "three"]);
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "d"]);
  assert.equal(map.current(), "s");
  map.tab();
  assert.equal(map.heard(), "Hint d: Link, three. Enter go there");
});

test("a walk redraws the chips it moves between and reads no target's box", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.session.paint();
  const reads = map.boxReads();
  map.tab();
  map.session.paint();
  map.tab();
  map.session.paint();
  assert.equal(map.current(), "s");
  assert.equal(map.boxReads(), reads);
});

// A panel view the user opens grows the chrome over targets the map named: the map is
// read again, so no chip stands for a target the user can no longer see or press.
test("a target the chrome comes to cover leaves the map", async (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  await map.session.arm();
  map.session.paint();
  map.tab();
  map.session.paint();
  assert.equal(map.current(), "a");
  map.cover(["three"]);
  map.session.paint();
  assert.deepEqual(
    map.session.candidates().map(({ name, code }) => [name, code]),
    [
      ["one", "a"],
      ["two", "s"],
    ],
  );
  assert.deepEqual(map.shown(), ["a", "s"]);
  assert.equal(map.current(), "a");
});
