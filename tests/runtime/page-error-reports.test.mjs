/* One fault reaches the agent once, however many consumers carry it.

   A producer reports each failure it sees, even where owners share one exception; a
   consumer that carries a fault up reports it only where no producer did. */
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

test("document faults end at swap and resume when the same realm is shown", (t) => {
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
    window.dispatchEvent(new Event("pageshow"));
  });
  const startupFault = (reason) =>
    window.dispatchEvent(new CustomEvent("lf-startup-failed", { detail: { reason } }));
  // A canceled beforeunload never swaps the document: ordinary faults remain live.
  const leave = new Event("beforeunload", { cancelable: true });
  leave.preventDefault();
  window.dispatchEvent(leave);
  reportPageError(new Error("still active"));
  assert.match(errors[0], /still active/);
  window.dispatchEvent(new Event("pageswap"));
  reportPageError(new Error("departing fetch canceled"));
  startupFault("departing startup canceled");
  assert.equal(errors.length, 1);
  assert.deepEqual(faults, []);
  assert.equal(root.hasAttribute("data-lf-startup-error"), false);
  // Pagehide is also the retirement boundary on engines without pageswap.
  window.dispatchEvent(new Event("pageshow"));
  window.dispatchEvent(new Event("pagehide"));
  reportPageError(new Error("hidden document canceled"));
  startupFault("hidden startup canceled");
  assert.equal(errors.length, 1);
  assert.deepEqual(faults, []);
  // BFCache restores this realm, including its original error listeners.
  window.dispatchEvent(new Event("pageshow"));
  reportPageError(new Error("restored real fault"));
  startupFault("restored startup fault");
  assert.match(errors[1], /restored real fault/);
  assert.deepEqual(faults, ["restored startup fault"]);
  assert.equal(root.dataset.lfStartupError, "restored startup fault");
});
