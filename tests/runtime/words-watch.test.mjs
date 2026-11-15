// The words watch must read actual document ancestry, including named document
// properties, without depending on a browser frame's execution speed.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import { JSDOM } from "jsdom";

const source = readFileSync(new URL("../words_watch.js", import.meta.url), "utf8");

test("a form named host cannot trap the words watch's ancestry climb", () => {
  const dom = new JSDOM(
    '<form name="host"></form><textarea></textarea><details></details>',
    {
      runScripts: "outside-only",
    },
  );
  const { window } = dom;
  const context = dom.getInternalVMContext();
  const listeners = new Map();
  const frames = [];
  const findings = [];
  let edit;
  window.lfWatchPlatform = {
    frame: (run) => frames.push(run),
    later: (run) => run(),
    listen: (_owner, type, run) => listeners.set(type, run),
  };
  window.lfInputWork = {
    current: () => null,
    subscribeEdits: (run) => (edit = run),
    subscribe: (run) => (window.checkpoint = run),
    dispatching: () => false,
  };
  window.__leafWatchFinding = (finding) => findings.push(finding);
  const field = window.document.querySelector("textarea");
  // Layout isn't part of this reading: this field remains drawn until removed.
  field.checkVisibility = () => !field.hidden;
  window.runFrame = () => frames.shift()();
  try {
    assert.equal(window.document.host.localName, "form");
    vm.runInContext(source, context);
    edit({ node: field, order: 1, event: { type: "beforeinput" } });
    field.value = "Keep this draft";
    listeners.get("input")({ isTrusted: true, composedPath: () => [field] });
    // A script execution deadline makes an ancestry cycle fail instead of hanging
    // the Node worker. It is only a hang bound, never a performance assertion.
    vm.runInContext("runFrame()", context, { timeout: 1000 });
    assert.equal(findings.length, 0);
    // A native disclosure close cannot redeem words hidden somewhere outside it;
    // this second ancestry reading must also finish at the document.
    field.hidden = true;
    vm.runInContext(
      `checkpoint({
      order: 2, event: {type: 'toggle'}, nativeDefault: document.querySelector('details')
    }, true); runFrame()`,
      context,
      { timeout: 1000 },
    );
    assert.equal(findings.length, 1);
    assert.equal(findings[0].code, "words-left-screen");
    assert.equal(findings[0].words, "Keep this draft");
  } finally {
    dom.window.close();
  }
});

// Another tab's edit puts words away only if it had replaced them in the store by the
// time they left the screen; one arriving before the next frame judges the loss is
// later input, which cannot redeem it.
for (const [foreignFirst, reported] of [
  [true, 0],
  [false, 1],
]) {
  const when = foreignFirst ? "before" : "after";
  const outcome = reported ? "does not redeem" : "puts away";
  test(`a foreign store write ${when} a passive loss ${outcome} its words`, () => {
    const dom = new JSDOM("<textarea></textarea>", {
      runScripts: "outside-only",
      url: "http://localhost/",
    });
    const { window } = dom;
    const context = dom.getInternalVMContext();
    const listeners = new Map();
    const frames = [];
    const findings = [];
    let edit;
    let checkpoint;
    window.lfWatchPlatform = {
      frame: (run) => frames.push(run),
      later: (run) => run(),
      listen: (_owner, type, run) => listeners.set(type, run),
    };
    window.lfInputWork = {
      current: () => null,
      subscribeEdits: (run) => (edit = run),
      subscribe: (run) => (checkpoint = run),
      dispatching: () => false,
    };
    window.__leafWatchFinding = (finding) => findings.push(finding);
    const field = window.document.querySelector("textarea");
    field.checkVisibility = () => field.isConnected;
    // Another document's write reaches this one's store without its own setItem.
    const { setItem } = window.Storage.prototype;
    const theirs = JSON.stringify({ text: "Theirs" });
    const foreignWrite = () => setItem.call(window.localStorage, "draft", theirs);
    try {
      vm.runInContext(source, context);
      const words = "Keep this draft";
      edit({ node: field, order: 1, event: { type: "beforeinput" } });
      field.value = words;
      listeners.get("input")({ isTrusted: true, composedPath: () => [field] });
      window.localStorage.setItem("draft", JSON.stringify({ text: words }));
      frames.shift()();
      assert.equal(findings.length, 0);
      if (foreignFirst) foreignWrite();
      // Cleared with no input: the checkpoint observes the loss and leaves it pending.
      field.value = "";
      checkpoint(null);
      if (!foreignFirst) foreignWrite();
      frames.shift()();
      assert.equal(findings.length, reported);
      if (reported) assert.equal(findings[0].words, words);
    } finally {
      dom.window.close();
    }
  });
}
