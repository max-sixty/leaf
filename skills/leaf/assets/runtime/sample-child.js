/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm. */
import { capturePlace, restorePlace } from "./reading-place.js";
import { cancelRender, nextRender } from "./rendering.js";
import { retainUserIntent } from "./user-intent.js";
import {
  canPlaceFocus,
  focused,
  focusDestination,
  onStanding,
  onUserInput,
} from "./focus.js";
import { pagePresented } from "./page-paint.js";

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
  // A parent cannot inspect focus in this opaque document. Keep the control while
  // a parent borrows focus, but report the current standing separately. The native
  // handoff can pass through the body before blur; capture its intent after the
  // shared input owner counts the blur after that first body handoff. Window loss
  // that keeps the active control needs no return. Later input voids a borrowed return, and
  // another blur cannot renew it before a control stands again.
  let standing = null;
  let borrowed = null;
  onStanding((node) => {
    if (node && node !== document.body) {
      standing = node;
      borrowed = null;
    }
    sampleNotice("standing", { focused: Boolean(node && node !== document.body) });
  });
  onUserInput((event) => {
    if (
      event.type === "blur" &&
      focused() === document.body &&
      standing &&
      borrowed === null
    )
      borrowed = retainUserIntent({ source: standing });
  });
  registerSampleCommand("restore-standing", () => {
    if (!standing?.isConnected || !borrowed?.() || !canPlaceFocus()) return false;
    focusDestination(standing, "return");
    return document.hasFocus();
  });
  let embeddedPlace = null;
  let returning = null;
  let restoration = null;
  const restoreEmbedded = () => {
    if (!returning || restoration !== null) return;
    restoration = nextRender(() => {
      restoration = null;
      if (!returning()) {
        returning = null;
        embeddedPlace = null;
        return;
      }
      restorePlace(embeddedPlace, null, returning);
    });
  };
  addEventListener("resize", restoreEmbedded);
  // Capture before the parent enlarges the viewport: resizing can clamp its
  // scroll before any later command arrives. The live landmark stays in this
  // realm, beside the controls and unfinished editors it describes.
  registerSampleCommand("inspection", ({ opening }) => {
    if (opening) {
      // A rapid reopen under the same reading intent keeps the original landmark,
      // including while the native return resize is still in flight.
      if (restoration !== null) cancelRender(restoration);
      restoration = null;
      if (!returning?.()) embeddedPlace = capturePlace();
      returning = null;
    } else if (embeddedPlace) {
      // Port delivery and native viewport resize have no shared ordering. Keep
      // this local landmark through the return's native resizes, while its
      // original intent holds; an early clamped restore is corrected at resize.
      returning = retainUserIntent();
      restoreEmbedded();
    }
  });
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
    sampleNotice("ready");
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
