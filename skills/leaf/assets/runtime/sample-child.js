/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm.
 * `ready` announces the usable, upgraded interface, independently of saved state.
 * Commands that need history wait at their owning child capability. */
import { canPlaceFocus, focusDestination, onStanding } from "./focus.js";
import { pagePresented, pageUpgraded } from "./page-paint.js";
import { whenArrived, whenArriving } from "./presentation.js";
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
        error: { name: error.name, message: error.message, stack: error.stack },
      });
    }
  });

if (child) {
  let upgraded = false;
  let arriving = false;
  let height = null;
  // A parent cannot inspect focus in this opaque document. Report whether a
  // control holds it, and retain its node while a parent control borrows focus.
  let standing = null;
  onStanding((node) => {
    if (node && node !== document.body) standing = node;
    sampleNotice("standing", { focused: Boolean(node && node !== document.body) });
  });
  // The reader's own input here, a press, a key or a wheel, is theirs to move the
  // frame with, so the containing page applies a size it held while they read.
  const input = ({ isTrusted }) => {
    if (isTrusted) sampleNotice("input");
  };
  for (const type of ["pointerdown", "keydown", "wheel"])
    window.addEventListener(type, input, { capture: true, passive: true });
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
    // arriving until it has. Arrival can begin again, as when one of its samples is
    // Reset, and the containing page reads as arriving again until it lands.
    if (upgraded && !arriving && pagePresented()) {
      arriving = true;
      void (async () => {
        await whenArrived();
        sampleNotice("arrived");
        for (;;) {
          await whenArriving();
          sampleNotice("arriving");
          await whenArrived();
          sampleNotice("arrived");
        }
      })();
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
