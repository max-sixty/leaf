/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm.
 * `ready` announces the usable, upgraded interface, independently of saved state.
 * Commands that need history wait at their owning child capability. */
import {
  canPlaceFocus,
  focusDestination,
  onCurrentLocation,
  onUserInput,
} from "../dom/focus.js";
import { exceptionRecord } from "../lib/exception.js";
import { pagePresented, pageUpgraded } from "../base/page-paint.js";
import { startNearWork, whenArrived } from "../readings/presentation.js";
import { sizeObserver } from "../lib/frame-pass.js";
const child = document.documentElement.lfSample;
/** @typedef {import("../base/sample-protocol.js").SampleCommands} SampleCommands
 * @typedef {import("../base/sample-protocol.js").SampleMethod} SampleMethod
 * @typedef {import("../base/sample-protocol.js").SampleHandlers} SampleHandlers
 */
/** @type {SampleHandlers} */
const commands = {};
/** @type {Set<() => unknown>} */
const observers = new Set();
/** @param {"cancel-view"} _type @param {() => unknown} callback */
export function onSampleNotice(_type, callback) {
  observers.add(callback);
  return () => observers.delete(callback);
}
/** @template {SampleMethod} K @param {K} name @param {NonNullable<SampleHandlers[K]>} callback */
export function registerSampleCommand(name, callback) {
  commands[name] = callback;
  return () => {
    delete commands[name];
  };
}
/** @param {import("../base/sample-protocol.js").SampleNotice | import("../base/sample-protocol.js").ChildStatus} notice */
export function sampleNotice(notice) {
  child?.send(notice);
}
/** @template {SampleMethod} K @param {{method: K, detail: SampleCommands[K]["detail"]}} request */
async function execute({ method, detail }) {
  const command = commands[method];
  if (!command) throw new Error(`Unknown sample command: ${method}`);
  return await command(detail);
}
if (child)
  child.receive(async (message) => {
    if (message.type) {
      if (message.type === "cancel-view") for (const callback of observers) callback();
      return;
    }
    try {
      const result = await execute(message);
      child.send({ id: message.id, result });
    } catch (error) {
      child.send({ id: message.id, error: exceptionRecord(error) });
    }
  });

if (child) {
  let upgraded = false;
  let arriving = false;
  // A parent cannot inspect focus in this opaque document. Report whether a
  // control holds it, and retain its node while a parent control borrows focus.
  /** @type {Element | null} */
  let currentLocation = null;
  onCurrentLocation((node) => {
    if (node && node !== document.body) currentLocation = node;
    sampleNotice({
      type: "current-location",
      detail: { focused: Boolean(node && node !== document.body) },
    });
  });
  // The reader's own input here goes to the containing page by its event type, for its
  // focus (dom/focus.js, `inputInFrame`) and for whether the frame is theirs to move
  // (sample.js, `claim`). The inputs are the document's one reading of them
  // (dom/focus.js, `onUserInput`). A click is input of its own, since by pointer or by
  // Enter or Space it lands after the press that began it.
  /** @param {Event} event */
  const input = (event) => {
    if (!event.isTrusted || event.type === "blur") return;
    sampleNotice({ type: "input", detail: { type: event.type } });
  };
  onUserInput(input);
  window.addEventListener("click", input, { capture: true, passive: true });
  registerSampleCommand("restore-current-location", () => {
    if (!currentLocation?.isConnected || !canPlaceFocus()) return false;
    focusDestination(currentLocation, "return");
    return document.hasFocus();
  });
  // The containing page's check asks for all near work (readings/presentation.js,
  // `startNearWork`); this document starts its own and answers at once, and the check
  // waits for each document's readiness itself (render_checks.py, `start_near_work`).
  registerSampleCommand("near-work", () => {
    startNearWork();
    return null;
  });
  // The containing page's image shows this part of the viewport where the frame stands.
  registerSampleCommand("image", async ({ x, y, width, height }) => {
    const { pageImage } = await import("./page-image.js");
    return pageImage({ x: scrollX + x, y: scrollY + y, width, height });
  });
  // The body's height, which a block's frame takes: sent as the document upgrades, as
  // the body resizes, and read again as it arrives, since a frame off screen may get no
  // rendering to deliver a resize (sample.js).
  let height = 0;
  const measure = () => {
    const next = Math.ceil(document.body.getBoundingClientRect().height);
    if (next !== height) {
      height = next;
      sampleNotice({ type: "height", detail: { height } });
    }
  };
  const inspect = () => {
    const error = document.documentElement.dataset.lfStartupError;
    if (error)
      sampleNotice({
        type: "error",
        detail: document.documentElement.lfStartupException ?? { message: error },
      });
    // Presentation is not this document's whole arrival: work it deferred, its own
    // samples' children included, lands later, and the containing page reads as
    // arriving until it has.
    if (upgraded && !arriving && pagePresented()) {
      arriving = true;
      void whenArrived().then(() => {
        measure();
        sampleNotice({ type: "arrived" });
      });
    }
    if (upgraded || !pageUpgraded()) return;
    upgraded = true;
    child.present();
    height = Math.ceil(document.body.getBoundingClientRect().height);
    sampleNotice({ type: "height", detail: { height } });
    registerSampleCommand("window", ({ window: asWindow }) => {
      child.settings.window = asWindow;
      window.lfRootState.setRuntimeRootAttribute(
        document.documentElement,
        "data-lf-sample-block",
        asWindow ? null : "",
      );
      measure();
      return { height };
    });
    sizeObserver(measure, { counted: false }).observe(document.body);
    sampleNotice({
      type: "ready",
      detail: {
        height,
        block: document.documentElement.hasAttribute("data-lf-sample-block"),
      },
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
