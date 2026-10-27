/* The hint session's state machine (`createHintSession`): what a typed letter, Tab,
   Enter and Escape do to an armed map, and when the map is read again.

   Each case arms a session over a scene of links the test states, the way a caller
   (go-to-sequence.js, target-picker.js) does: `read` names the links in view, each
   with its code, and `layout` puts a chip on each. A paint is called where a frame
   would run one, and a scroll is the `scroll` and `scrollend` events the page's scroll
   tracking hears (arrivals.js), so no case waits on a clock. The live region speaks
   after its own delay (notifications.js), which the mocked timers run. */

import assert from "node:assert/strict";
import test from "node:test";

import { createHintSession, hintCodes } from "/runtime/keyboard/hints.js";
import { setQuickShortcuts } from "/runtime/keyboard/bindings.js";
import { liveEl } from "/runtime/notifications.js";
import { html } from "/runtime/framework.js";

// Three letters, so a fourth link branches: a, s, da, ds.
const KEYS = ["a", "s", "d"];

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
      // Nothing is laid out here, so each link states its own box.
      const top = 20 + 40 * links.size;
      node.getBoundingClientRect = () => new DOMRect(10, top, 80, 20);
      node.getClientRects = () => [node.getBoundingClientRect()];
      document.body.append(node);
      links.set(name, node);
    }
    return links.get(name);
  };
  let inView = names;
  const taken = [];
  const session = createHintSession({
    layer,
    walk: `hint-session-${++sessions}`,
    read: () => {
      const codes = hintCodes(inView.length, KEYS);
      return inView.map((name, at) => ({ name, member: link(name), code: codes[at] }));
    },
    identity: (candidate) => candidate.member,
    scene: () => ({}),
    layout: (candidates, { current }) =>
      candidates.map((candidate) => {
        const target = candidate.member.getBoundingClientRect();
        return {
          candidate,
          model: {
            key: candidate.name,
            code: candidate.code,
            className: `lf-key-hint${candidate === current ? " lf-current" : ""}`,
          },
          target,
          placement: "corner",
          left: target.left,
          top: target.top,
        };
      }),
    template: (model) =>
      html`<span class=${model.className} data-code=${model.code}>${model.code}</span>`,
    take: (candidate) => taken.push(candidate.name),
    words: {
      describe: (candidate) => `Link, ${candidate.name}`,
      take: "go there",
      all: "All hints.",
    },
    chrome: { barriers: () => [] },
  });
  session.mount();
  const [walk, choose] = session.walkRows({
    id: `hint-session-${sessions}`,
    choose: { title: "go there", description: "Go to the heard target" },
  });
  t.after(() => {
    session.disarm();
    layer.remove();
    for (const node of links.values()) node.remove();
  });
  return {
    session,
    taken,
    links,
    show: (names) => (inView = names),
    tab: () => walk.run("Tab"),
    shiftTab: () => walk.run("Shift+Tab"),
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

test("a letter narrows the map, one that names nothing changes nothing, and the letter that completes a code takes it", (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  map.session.arm();
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

test("Escape gives back one letter at a time, then hands Escape on", (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  map.session.arm();
  map.session.type("d");

  assert.equal(map.session.backOneLetter(), true);
  assert.equal(map.heard(), "All hints.");
  assert.equal(map.session.prefix(), "");
  map.session.paint();
  assert.deepEqual(map.shown(), ["a", "s", "da", "ds"]);
  // Nothing left to give back: the caller's Escape takes its own next step.
  assert.equal(map.session.backOneLetter(), false);
});

test("Tab and Shift+Tab walk the map aloud, round from either end, and Enter takes the one heard", (t) => {
  const map = hintMap(t, ["one", "two"]);
  map.session.arm();
  map.session.paint();
  assert.equal(map.canChoose(), false, "Enter is offered before anything is heard");

  map.tab();
  assert.equal(map.heard(), "Hint a: Link, one. Press Enter to go there.");
  map.session.paint();
  assert.equal(map.current(), "a");
  map.tab();
  assert.equal(map.heard(), "Hint s: Link, two. Press Enter to go there.");
  map.tab();
  assert.equal(map.heard(), "Hint a: Link, one. Press Enter to go there.");
  map.shiftTab();
  assert.equal(map.heard(), "Hint s: Link, two. Press Enter to go there.");
  map.session.paint();
  assert.equal(map.current(), "s");

  assert.equal(map.canChoose(), true);
  map.enter();
  assert.deepEqual(map.taken, ["two"]);
});

test("a walk begun with Shift+Tab starts at the last target and walks back", (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  map.session.arm();
  map.shiftTab();
  assert.equal(map.heard(), "Hint d: Link, three. Press Enter to go there.");
  map.shiftTab();
  assert.equal(map.heard(), "Hint s: Link, two. Press Enter to go there.");
});

test("a typed letter puts the walk back at the head of what it leaves", (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  map.session.arm();
  map.tab();
  map.session.type("d");
  assert.equal(map.canChoose(), false);
  map.tab();
  assert.equal(map.heard(), "Hint da: Link, three. Press Enter to go there.");
});

test("a target that left the scene is not taken by its stale code", (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  map.session.arm();
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

test("a whole map is read again when a member leaves the document", (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  map.session.arm();
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

test("a scroll holds the map as read, and its end reads the scene again", (t) => {
  const map = hintMap(t, ["one", "two", "three"]);
  map.session.arm();
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

test("a letter typed during a scroll hides the chips it rules out", (t) => {
  const map = hintMap(t, ["one", "two", "three", "four"]);
  map.session.arm();
  map.session.paint();
  scrollStarts();
  t.after(scrollEnds);
  map.session.type("d");
  map.session.paint();
  assert.deepEqual(map.shown(), ["da", "ds"]);
});

test("a map armed while the page is in flight shows nothing until the scroll settles", (t) => {
  const map = hintMap(t, ["one", "two"]);
  scrollStarts();
  t.after(scrollEnds);
  map.session.arm();
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

test("a resize reads the scene again and keeps the heard hint where it still stands", (t) => {
  const map = hintMap(t, ["one", "two"]);
  map.session.arm();
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

test("without character routes the chips go, and the walk and Enter remain", (t) => {
  const map = hintMap(t, ["one", "two"]);
  map.session.arm();
  map.session.paint();
  setQuickShortcuts(false);
  t.after(() => setQuickShortcuts(true));
  map.session.paint();
  assert.deepEqual(map.shown(), []);

  map.tab();
  assert.equal(map.heard(), "Link, one. Press Enter to go there.");
  map.session.paint();
  // The heard target's chip names the key that takes it rather than a code.
  const native = document.querySelector("[data-lf-hint-native]");
  assert.equal(native?.dataset.lfHintNative, "Enter");
  map.enter();
  assert.deepEqual(map.taken, ["one"]);
});

test("a disarmed map paints nothing and is read fresh when armed again", (t) => {
  const map = hintMap(t, ["one", "two"]);
  map.session.arm();
  map.session.type("s");
  map.session.disarm();
  map.session.paint();
  assert.equal(map.session.armed(), false);
  assert.deepEqual(map.shown(), []);

  map.show(["three"]);
  map.session.arm();
  assert.equal(map.session.prefix(), "");
  map.session.paint();
  assert.deepEqual(map.shown(), ["a"]);
});
