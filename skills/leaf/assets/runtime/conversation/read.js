/* The page's evidence that the user has seen exact agent content.

   Whether a version is unread is the server's reading of the whole log (`read_state`),
   published as each Thread's `unread`; replying, answering and resolving already count
   there. This owner adds the one kind of evidence only the page has, exposure: a
   visible prose body is marked read once its complete vertical extent has been shown
   without gaps in one rendered surface and one content version. What the body holds
   inside that extent — a wide code block, a scroller of its own — is part of what was
   shown; geometry cannot say whether the user read every column of it, and a message
   whose contents never let it count would stand unread forever. A widget-authored body
   has hidden states of its own and no general contract for them, so exposure does not
   mark it read: answering its widget does, and so does its thread's Mark read control.
   Each observation pass batches newly completed versions into one `read` event, which
   the application sends outside the gesture queue (delivery.js). */
import { shownBand, shownRect } from "../geometry.js";
import { notice } from "../notifications.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { moved } from "./model.js";
import { firstUnreadBtn, panelEdgeOver } from "./panel-elements.js";
import { readThreads } from "./state.js";
import { under, upFrom } from "../shadow.js";

const keyOf = (item) => `${item.message}\u0000${item.version}`;
const EPSILON = 1;

function mergeIntervals(intervals) {
  const ordered = intervals.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [start, end] of ordered) {
    const prior = merged.at(-1);
    if (prior && start <= prior[1] + EPSILON) prior[1] = Math.max(prior[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

// A child viewport does not know how much of it the parent page shows. Walk each
// containing frame and cut this viewport down to what its owner shows of it, through
// the owner's viewport and every clipping ancestor, in this window's coordinates. A
// frame taller than its owner's viewport, as a live specimen is, shows a band of its
// page the way the top page's own viewport does.
function frameBand() {
  let band = { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
  let x = 0;
  let y = 0;
  for (let current = window; current !== current.top;) {
    let frame;
    try {
      frame = current.frameElement;
    } catch {
      return null;
    }
    if (!frame || !frame.checkVisibility()) return null;
    const owner = frame.ownerDocument.defaultView;
    const box = frame.getBoundingClientRect();
    x += box.left + frame.clientLeft;
    y += box.top + frame.clientTop;
    const cut = (rect) => {
      band = {
        left: Math.max(band.left, rect.left - x),
        top: Math.max(band.top, rect.top - y),
        right: Math.min(band.right, rect.right - x),
        bottom: Math.min(band.bottom, rect.bottom - y),
      };
    };
    cut({ left: 0, top: 0, right: owner.innerWidth, bottom: owner.innerHeight });
    const modal = owner.document.querySelector("dialog:modal");
    if (modal && !under(frame, modal)) return null;
    for (let ancestor = upFrom(frame); ancestor; ancestor = upFrom(ancestor)) {
      const style = owner.getComputedStyle(ancestor);
      if (
        ancestor.inert ||
        ancestor.getAttribute?.("aria-hidden") === "true" ||
        style.visibility === "hidden" ||
        style.display === "none"
      )
        return null;
      const shown = shownBand(ancestor);
      if (shown) cut(shown);
    }
    if (band.right <= band.left || band.bottom <= band.top) return null;
    current = owner;
  }
  return band;
}

function visibleInterval(body, clips, band) {
  if (!body.checkVisibility()) return null;
  for (let owner = body; owner; owner = upFrom(owner))
    if (owner.inert || owner.getAttribute?.("aria-hidden") === "true") return null;
  const modal = document.querySelector("dialog:modal");
  if (modal && !under(body, modal)) return null;
  const box = body.getBoundingClientRect();
  // Sticky run headings are left out of what is shown (geometry.js, visibleBand), so a
  // message hidden under one is not read.
  const clipped = shownRect(body, clips);
  if (!clipped || box.width <= 0 || box.height <= 0) return null;
  const shown = {
    left: Math.max(clipped.left, band.left),
    top: Math.max(clipped.top, band.top),
    right: Math.min(clipped.right, band.right),
    bottom: Math.min(clipped.bottom, band.bottom),
  };
  if (shown.bottom <= shown.top) return null;
  // The open thread panel stands over the right of the page and occludes what it stands
  // over, the way a clip cuts what it does not hold: a message reaching under its edge
  // has not been shown whole, and the full-width rule withholds it.
  const right = Math.min(shown.right, panelEdgeOver(body));
  if (shown.left > box.left + EPSILON || right < box.right - EPSILON) return null;
  return {
    interval: [
      Math.max(0, shown.top - box.top),
      Math.min(box.height, shown.bottom - box.top),
    ],
    height: box.height,
    width: box.width,
    contentHeight: body.scrollHeight,
  };
}

export function createReadTracking({ markRead, showThread }) {
  let coverage = new WeakMap();
  const renderedBodies = new Map();
  const refusedAutomatic = new Set();
  const sizes = new ResizeObserver(() => scheduleScan());
  const frameWatches = [];
  let committedThreads = [];
  let presented = false;
  let presentationGeneration = 0;
  let scheduled = false;

  const unreadIn = (threads) =>
    threads.flatMap((thread) =>
      thread.unread.map((item) => ({
        thread,
        item,
        message: thread.msgs.find((message) => message.id === item.message),
      })),
    );
  // Unread in what the page has presented and still unread in the current reading: a
  // version this tab is marking read, or another tab or move already did, is not
  // offered again.
  const actionableUnread = () => {
    const live = new Set(
      unreadIn(readThreads().threads).map(({ item }) => keyOf(item)),
    );
    return unreadIn(committedThreads).filter(({ item }) => live.has(keyOf(item)));
  };

  function markThread(id) {
    const items = actionableUnread()
      .filter(({ thread }) => thread.root.id === id)
      .map(({ item }) => item);
    if (items.length)
      void markRead(items).then((outcome) => {
        if (outcome !== "accepted") notice("Couldn't mark thread read — try again.");
      });
  }

  function firstUnread() {
    const target = actionableUnread().sort(
      (a, b) => moved(a.message).seq - moved(b.message).seq,
    )[0];
    if (target) void showThread(target.item.message, { focus: "message" });
  }

  function scan() {
    if (!presented || document.visibilityState !== "visible" || !document.hasFocus())
      return;
    const band = frameBand();
    if (!band) return;
    const candidates = new Map(
      actionableUnread().map(({ item }) => [item.message, item]),
    );
    if (!candidates.size) return;
    const clips = new Map();
    const completed = new Map();
    for (const [node, rendered] of renderedBodies) {
      const { body, id, authored } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      const item = candidates.get(id);
      const key = item && keyOf(item);
      if (!item || authored || completed.has(key) || refusedAutomatic.has(key))
        continue;
      const visible = visibleInterval(body, clips, band);
      if (!visible) continue;
      let tracked = coverage.get(body);
      if (
        !tracked ||
        tracked.key !== key ||
        tracked.width !== visible.width ||
        tracked.height !== visible.height ||
        tracked.contentHeight !== visible.contentHeight
      ) {
        tracked = {
          key,
          width: visible.width,
          height: visible.height,
          contentHeight: visible.contentHeight,
          intervals: [],
        };
        coverage.set(body, tracked);
      }
      tracked.intervals = mergeIntervals([...tracked.intervals, visible.interval]);
      if (
        tracked.intervals.length === 1 &&
        tracked.intervals[0][0] <= EPSILON &&
        tracked.intervals[0][1] >= visible.height - EPSILON
      ) {
        completed.set(key, item);
      }
    }
    if (completed.size) {
      const items = [...completed.values()];
      // A refusal would be repeated; an answer that never arrived may not be, and the
      // coverage already gathered sends it again on the next pass.
      void markRead(items).then((outcome) => {
        if (outcome === "refused")
          for (const item of items) refusedAutomatic.add(keyOf(item));
      });
    }
  }

  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      scan();
    });
  }

  function mount() {
    firstUnreadBtn.onclick = firstUnread;
    addEventListener("scroll", scheduleScan, true);
    addEventListener("resize", scheduleScan);
    addEventListener("focus", scheduleScan);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") coverage = new WeakMap();
      else scheduleScan();
    });
    document.addEventListener("close", scheduleScan, true);
    addEventListener("blur", () => {
      coverage = new WeakMap();
    });
    addEventListener("load", scheduleScan, true);
    // What a containing page shows of this one changes without a scroll or resize
    // inside it: the owner scrolls a frame taller than its viewport through the band
    // (frameBand), and moving the frame changes it without any scroll at all. Watch
    // each containing page's scrolling and each frame in its owner's viewport.
    for (let current = window; current !== current.top;) {
      let frame;
      try {
        frame = current.frameElement;
      } catch {
        break;
      }
      if (!frame) break;
      const owner = frame.ownerDocument.defaultView;
      const observer = new owner.IntersectionObserver(scheduleScan, {
        threshold: [0, 1],
      });
      observer.observe(frame);
      owner.addEventListener("scroll", scheduleScan, true);
      owner.addEventListener("resize", scheduleScan);
      frameWatches.push(() => {
        observer.disconnect();
        owner.removeEventListener("scroll", scheduleScan, true);
        owner.removeEventListener("resize", scheduleScan);
      });
      current = owner;
    }
    addEventListener(
      "pagehide",
      () => {
        sizes.disconnect();
        for (const unwatch of frameWatches) unwatch();
        frameWatches.length = 0;
      },
      { once: true },
    );
  }

  function observeBody(node, body, message) {
    if (!body) return;
    const previous = renderedBodies.get(node);
    if (previous?.body !== body) {
      if (previous) sizes.unobserve(previous.body);
      sizes.observe(body);
    }
    renderedBodies.set(node, {
      body,
      id: message.id,
      authored: message.body.authored,
    });
  }

  function forgetBody(node) {
    const rendered = renderedBodies.get(node);
    if (rendered) sizes.unobserve(rendered.body);
    renderedBodies.delete(node);
  }

  function present() {
    const generation = presentationGeneration;
    const threads = readThreads().threads;
    void whenDocumentPresented()
      .then(() => {
        if (generation !== presentationGeneration) return;
        committedThreads = threads;
        presented = true;
        const unread = unreadIn(threads);
        const current = new Set(unread.map(({ item }) => keyOf(item)));
        for (const key of refusedAutomatic)
          if (!current.has(key)) refusedAutomatic.delete(key);
        const count = unread.length;
        firstUnreadBtn.hidden = count === 0;
        firstUnreadBtn.textContent = `Unread ${count}`;
        firstUnreadBtn.setAttribute(
          "aria-label",
          `${count} unread ${count === 1 ? "message" : "messages"}. Go to first unread message`,
        );
        scheduleScan();
      })
      .catch(() => {
        if (generation === presentationGeneration) coverage = new WeakMap();
      });
  }

  function begin() {
    presentationGeneration++;
    presented = false;
  }

  function abort() {
    presentationGeneration++;
    presented = false;
    coverage = new WeakMap();
  }

  return {
    mount,
    begin,
    abort,
    present,
    observeBody,
    forgetBody,
    markThread,
    firstUnread,
    unreadCount: () => actionableUnread().length,
  };
}
