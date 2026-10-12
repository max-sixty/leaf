/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm. */
import { canPlaceFocus, focusDestination, onStanding } from "./focus.js";
import { pagePresented } from "./page-paint.js";
import { enterLoop, joinOuterLoop } from "./keyboard/layer-stack.js";
const child = document.documentElement.lfSample;
const commands = new Map();
const observers = new Map();
export function onSampleNotice(type, callback) {
  if (!observers.has(type)) observers.set(type, new Set());
  observers.get(type).add(callback);
  return () => observers.get(type).delete(callback);
}
export function registerSampleCommand(name, callback) {
  commands.set(name, callback);
  return () => commands.delete(name);
}
export function sampleNotice(type, detail = {}) {
  child?.send({ type, detail });
}
if (child)
  child.receive(async ({ id, method, type, detail }) => {
    if (type) {
      for (const callback of observers.get(type) ?? []) callback(detail);
      return;
    }
    try {
      if (!commands.has(method)) throw new Error(`Unknown sample command: ${method}`);
      const result = await commands.get(method)(detail);
      child.send({ id, result });
    } catch (error) {
      child.send({
        id,
        error: { name: error.name, message: error.message, stack: error.stack },
      });
    }
  });

if (child) {
  let presented = false;
  let height = null;
  // A parent cannot inspect focus in this opaque document. Report whether a
  // control holds it, and retain its node while a parent control borrows focus.
  let standing = null;
  onStanding((node) => {
    if (node && node !== document.body) standing = node;
    sampleNotice("standing", { focused: Boolean(node && node !== document.body) });
  });
  // The containing page says whether this frame stands in a Tab loop there, and Tab
  // past this document's ends goes back to that page to move on past the frame
  // (keyboard/layer-stack.js, `joinOuterLoop`).
  let looped = false;
  onSampleNotice("tab-loop", ({ standing }) => {
    looped = standing;
  });
  onSampleNotice("tab-enter", ({ backward }) => enterLoop(backward));
  joinOuterLoop({
    standing: () => looped,
    leave: (backward) => sampleNotice("tab", { backward }),
  });
  registerSampleCommand("restore-standing", () => {
    if (!standing?.isConnected || !canPlaceFocus()) return false;
    focusDestination(standing, "return");
    return document.hasFocus();
  });
  const measure = () => {
    if (!document.body) return;
    const next = Math.ceil(document.body.getBoundingClientRect().height);
    if (next !== height) {
      height = next;
      sampleNotice("height", { height });
    }
  };
  // The containing page's image shows this part of the viewport where the frame stands.
  registerSampleCommand("image", async ({ x, y, width, height }) => {
    const { pageImage } = await import("./composing/page-image.js");
    return pageImage({ x: scrollX + x, y: scrollY + y, width, height });
  });
  registerSampleCommand("window", async ({ window: asWindow }) => {
    child.settings.window = asWindow;
    document.documentElement.lfInitial.setRuntimeRootAttribute(
      document.documentElement,
      "data-lf-sample-block",
      !child.settings.passive && !asWindow ? "" : null,
    );
    measure();
    return { height };
  });
  const inspect = () => {
    const error = document.documentElement.dataset.lfStartupError;
    if (error)
      sampleNotice(
        "error",
        document.documentElement.lfStartupException ?? { message: error },
      );
    if (presented || !(document.body && pagePresented())) return;
    presented = true;
    child.present();
    measure();
    if (!child.settings.passive) {
      const observer = new window.ResizeObserver(measure);
      observer.observe(document.body);
    }
    sampleNotice("ready", {
      height,
      block: document.documentElement.hasAttribute("data-lf-sample-block"),
    });
  };
  const observer = new MutationObserver(inspect);
  observer.observe(document, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["data-lf-presented", "data-lf-startup-error"],
  });
  inspect();
}
