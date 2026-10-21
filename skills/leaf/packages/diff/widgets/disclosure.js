/* Call roots and files use the same native disclosure. A pointer close immediately
 * changes its state and retires its controls; only the body's remaining room folds.
 * The browser interpolates its intrinsic size, including changing evidence. Opening
 * is instant except when it reverses an unfinished close. Keyboard and programmatic
 * navigation always reach their final geometry immediately. */
import {
  foldDuration,
  motion,
  plainPress,
  pressIsKeyboardActivation,
} from "/runtime/widget-api.js";

const folding = new WeakMap();

export function disclose(details, open, event) {
  const previous = folding.get(details);
  const pointer = event && !pressIsKeyboardActivation(event);
  details.toggleAttribute("open", open);
  if (previous) {
    if (pointer) {
      previous.open = open;
      previous.retire(!open);
      previous.animation.updatePlaybackRate(open ? -1 : 1);
      previous.animation.play();
      return;
    }
    previous.animation.cancel();
    previous.cleanup();
  }
  if (open || !pointer || !CSS.supports("block-size", "calc-size(auto, size)")) return;
  const animation = motion(
    details,
    [
      {
        blockSize: "calc-size(auto, size)",
        contentVisibility: "visible",
        overflow: "clip",
      },
      { blockSize: "0px", contentVisibility: "visible", overflow: "clip" },
    ],
    foldDuration(),
    "::details-content",
  );
  if (!animation) return;
  const children = [...details.children].filter((child) => child.tagName !== "SUMMARY");
  const inert = children.map((child) => child.inert);
  const retire = (closed) =>
    children.forEach((child, index) => {
      child.inert = closed || inert[index];
    });
  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    observer.disconnect();
    retire(false);
    folding.delete(details);
  };
  const entry = { animation, open, retire, cleanup };
  // Source navigation may open the native element without pressing its summary.
  const observer = new MutationObserver(() => {
    if (details.open !== entry.open) {
      animation.cancel();
      cleanup();
    }
  });
  observer.observe(details, { attributes: true, attributeFilter: ["open"] });
  retire(true);
  folding.set(details, entry);
  animation.finished.then(cleanup, cleanup);
}

export function disclosure(details) {
  // Summary listeners get first say, including a cancelled activation.
  details.addEventListener("click", (event) => {
    if (!details.firstElementChild.contains(event.target)) return;
    if (event.defaultPrevented || !plainPress(event)) return;
    event.preventDefault();
    disclose(details, !details.open, event);
  });
}
