/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm.
 * `ready` announces the usable, upgraded interface, independently of saved state.
 * Commands that need history wait at their owning child capability. */
import {
  canPlaceFocus,
  focusDestination,
  onCurrentLocation,
  onUserInput,
} from "./focus.js";
import { exceptionRecord } from "./exception.js";
import { pagePresented, pageUpgraded } from "./page-paint.js";
import { whenArrived } from "./presentation.js";
import { sizeObserver } from "./rendering.js";
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
        error: exceptionRecord(error),
      });
    }
  });

if (child) {
  let upgraded = false;
  let arriving = false;
  let height = null;
  // A parent cannot inspect focus in this opaque document. Report whether a
  // control holds it, and retain its node while a parent control borrows focus.
  let currentLocation = null;
  onCurrentLocation((node) => {
    if (node && node !== document.body) currentLocation = node;
    sampleNotice("current-location", {
      focused: Boolean(node && node !== document.body),
    });
  });
  // The reader's own input here goes to the containing page by its event type, for its
  // focus (focus.js, `inputInFrame`) and for whether the frame is theirs to move
  // (lf-sample.js, `#release`). The inputs are the document's one reading of them
  // (focus.js, `onUserInput`). A click is input of its own, since by pointer or by
  // Enter or Space it lands after the press that began it.
  const input = (event) => {
    if (!event.isTrusted || event.type === "blur") return;
    sampleNotice("input", { type: event.type });
  };
  onUserInput(input);
  window.addEventListener("click", input, { capture: true, passive: true });
  registerSampleCommand("restore-current-location", () => {
    if (!currentLocation?.isConnected || !canPlaceFocus()) return false;
    focusDestination(currentLocation, "return");
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
    document.documentElement.lfRootState.setRuntimeRootAttribute(
      document.documentElement,
      "data-lf-sample-block",
      asWindow ? null : "",
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
    // Presentation is not this document's whole arrival: work it deferred, its own
    // samples' children included, lands later, and the containing page reads as
    // arriving until it has.
    if (upgraded && !arriving && pagePresented()) {
      arriving = true;
      void whenArrived().then(() => sampleNotice("arrived"));
    }
    if (upgraded || !(document.body && pageUpgraded())) return;
    upgraded = true;
    child.present();
    measure();
    sizeObserver(measure, { counted: false }).observe(document.body);
    sampleNotice("ready", {
      height,
      block: document.documentElement.hasAttribute("data-lf-sample-block"),
    });
    inspect();
  };
  const observer = new MutationObserver(inspect);
  observer.observe(document, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["data-lf-upgraded", "data-lf-presented", "data-lf-startup-error"],
  });
  inspect();
}
