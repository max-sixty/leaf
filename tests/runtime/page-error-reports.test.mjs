/* One fault reaches the agent once, however many consumers carry it.

   A producer reports each failure it sees, even where owners share one exception; a
   consumer that carries a fault up reports it only where no producer did. A widget's
   failure reaches it as the `error` event the widget dispatches (widget-upgrade.js),
   named for the widget. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// The log's door answers every report; only what reaches the console is read here.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { reportCarried, reportPageError } = await import("/runtime/layer-client.js");
const { failSoft } = await import("/runtime/widget-upgrade.js");

const reported = (run) => {
  const lines = [];
  const original = console.error;
  console.error = (line) => lines.push(line.split("\n")[0]);
  try {
    run();
  } finally {
    console.error = original;
  }
  return lines;
};

test("a carried fault its producer reported is not reported again", () => {
  const fault = new Error("paint broke");
  assert.deepEqual(
    reported(() => {
      reportPageError(fault, "Presentation failed");
      reportCarried(fault, "State presentation failed");
      reportCarried(fault, "read failed");
    }),
    ["leaf: Presentation failed: paint broke"],
  );
});

test("a carried fault no producer saw is reported by its consumer", () => {
  const fault = new SyntaxError("Unexpected token");
  assert.deepEqual(
    reported(() => reportCarried(fault, "read failed")),
    ["leaf: read failed: Unexpected token"],
  );
});

test("owners sharing one exception each report it", () => {
  const fault = new Error("grammar failed to load");
  assert.deepEqual(
    reported(() => {
      reportPageError(fault, "<lf-code first>");
      reportPageError(fault, "<lf-code second>");
    }),
    [
      "leaf: <lf-code first>: grammar failed to load",
      "leaf: <lf-code second>: grammar failed to load",
    ],
  );
});

test("a primitive reason stands for itself by its text", () => {
  assert.deepEqual(
    reported(() => {
      reportPageError("boom", "Presentation failed");
      reportCarried("boom", "read failed");
    }),
    ["leaf: Presentation failed: boom"],
  );
});

test("a widget's failure reaches the agent named for its widget, in the page or out of it", () => {
  const widget = (id) => Object.assign(document.createElement("lf-probe"), { id });
  const shown = widget("shown");
  document.body.append(shown);
  // A message body the panel holds while its thread is shut stands in no document.
  const cached = widget("cached");
  assert.deepEqual(
    reported(() => {
      failSoft(shown, new Error("drew nothing"));
      failSoft(cached, new Error("plot failed to load"));
    }),
    [
      'leaf: <lf-probe id="shown"> failed: drew nothing',
      'leaf: <lf-probe id="cached"> failed: plot failed to load',
    ],
  );
  shown.remove();
});

test("a failure with no Error gives every listener one and reports the reason as thrown", () => {
  const widget = Object.assign(document.createElement("lf-probe"), { id: "bare" });
  document.body.append(widget);
  const heard = [];
  const hear = (event) => heard.push(event.error);
  window.addEventListener("error", hear);
  try {
    assert.deepEqual(
      reported(() => failSoft(widget, undefined)),
      ['leaf: <lf-probe id="bare"> failed: undefined'],
    );
  } finally {
    window.removeEventListener("error", hear);
    widget.remove();
  }
  assert.equal(heard.length, 1);
  assert.ok(heard[0] instanceof Error, "the event carries an Error");
  assert.equal(heard[0].stack, undefined, "no stack names a site the failure isn't at");
});

test("a departing document holds its faults until it stays, and drops them as it goes", (t) => {
  const root = document.documentElement;
  const errors = [];
  const faults = [];
  const error = console.error;
  console.error = (...args) => errors.push(args.join(" "));
  const fault = (event) => faults.push(event.detail.reason);
  window.addEventListener("lf-startup-fault", fault);
  t.after(() => {
    console.error = error;
    window.removeEventListener("lf-startup-fault", fault);
    root.removeAttribute("data-lf-startup-error");
    window.dispatchEvent(returning());
  });
  const startupFault = (reason) =>
    window.dispatchEvent(new CustomEvent("lf-startup-failed", { detail: { reason } }));
  // The page cache's return; the document's own first pageshow reopens nothing.
  const returning = () => Object.assign(new Event("pageshow"), { persisted: true });
  const leave = () =>
    window.dispatchEvent(new Event("beforeunload", { cancelable: true }));
  // Firefox rejects the loads a navigation aborts before any swap, and the navigation
  // may still leave the document in place, as a download or a stay at the prompt does.
  // A fault then waits, once however often it repeats. Neither a wheel turn nor the
  // document's own first pageshow says the reader stayed.
  leave();
  reportPageError(new Error("load a download aborted"));
  for (let poll = 0; poll < 100; poll++) reportPageError(new Error("read failed"));
  startupFault("startup a download aborted");
  window.dispatchEvent(new Event("wheel"));
  window.dispatchEvent(new Event("pageshow"));
  assert.deepEqual(errors, []);
  assert.deepEqual(faults, []);
  // The user's next key shows the document stayed, and the faults are reported then.
  window.dispatchEvent(new Event("keydown"));
  assert.match(errors[0], /load a download aborted/);
  assert.deepEqual(faults, ["startup a download aborted"]);
  assert.equal(errors.length, 2);
  root.removeAttribute("data-lf-startup-error");
  errors.length = faults.length = 0;
  // A departure drops what waited with it.
  leave();
  reportPageError(new Error("departing fetch canceled"));
  startupFault("departing startup canceled");
  window.dispatchEvent(new Event("pageswap"));
  window.dispatchEvent(new Event("keydown"));
  reportPageError(new Error("swapped document canceled"));
  assert.equal(errors.length, 0);
  assert.deepEqual(faults, []);
  assert.equal(root.hasAttribute("data-lf-startup-error"), false);
  // Pagehide is also the retirement boundary on engines without pageswap.
  window.dispatchEvent(returning());
  window.dispatchEvent(new Event("pagehide"));
  reportPageError(new Error("hidden document canceled"));
  startupFault("hidden startup canceled");
  assert.equal(errors.length, 0);
  assert.deepEqual(faults, []);
  // BFCache restores this realm, including its original error listeners.
  window.dispatchEvent(returning());
  reportPageError(new Error("restored real fault"));
  startupFault("restored startup fault");
  assert.match(errors[0], /restored real fault/);
  assert.deepEqual(faults, ["restored startup fault"]);
  assert.equal(root.dataset.lfStartupError, "restored startup fault");
});
