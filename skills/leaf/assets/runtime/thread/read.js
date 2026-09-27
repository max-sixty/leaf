/* The page's evidence that the user has seen exact agent content.

   Whether a version is unread is the server's reading of the whole log (`read_state`),
   published as each Thread's `unread`; replying, answering and resolving already count
   there. This owner adds the one kind of evidence only the page has, exposure: a
   visible body is marked read once its complete vertical extent has been shown
   without gaps in one rendered surface and one content version. What the body holds
   inside that extent — a wide code block, a scroller of its own, or an interactive
   widget's hidden states — is not evidence the page can observe; unread tracks
   encounter with the message's visible surface, not exhaustive inspection.
   Each observation pass batches newly completed versions into one `read` event, which
   the application sends outside the gesture queue (delivery.js). A refused receipt
   leaves the message unread and is retried only on a new visit. */
import { nextRender, sizeObserver } from "../rendering.js";
import { seenRect, shownBand } from "../geometry.js";
import { SLIDE_END } from "../motion.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { moved } from "./model.js";
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
// frame taller than its owner's viewport, as a live sample is, shows a band of its
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
  // Sticky covers, the open thread panel standing over the right of the page, and the
  // banner and shortcut bar are left out of what is seen (geometry.js), so a message any
  // part of which is under one has not been shown whole, and the full-width rule below
  // withholds it.
  const clipped = seenRect(body, clips);
  if (!clipped || box.width <= 0 || box.height <= 0) return null;
  const shown = {
    left: Math.max(clipped.left, band.left),
    top: Math.max(clipped.top, band.top),
    right: Math.min(clipped.right, band.right),
    bottom: Math.min(clipped.bottom, band.bottom),
  };
  if (shown.bottom <= shown.top) return null;
  if (shown.left > box.left + EPSILON || shown.right < box.right - EPSILON) return null;
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

export function createReadTracking({ markRead, showThread, firstUnreadBtn }) {
  let coverage = new WeakMap();
  const renderedBodies = new Map();
  const refusedThisVisit = new Set();
  const sizes = sizeObserver(() => scheduleScan());
  const frameWatches = [];
  let committedThreads = [];
  let presented = false;
  let presentationGeneration = 0;
  let visitGeneration = 0;
  let scheduled = false;

  function resetExposure() {
    visitGeneration++;
    coverage = new WeakMap();
    refusedThisVisit.clear();
  }

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
      const { body, id } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      const item = candidates.get(id);
      const key = item && keyOf(item);
      if (!item || completed.has(key) || refusedThisVisit.has(key)) continue;
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
      const visit = visitGeneration;
      // A refusal would be repeated; an answer that never arrived may not be, and the
      // coverage already gathered sends it again on the next pass.
      void markRead(items).then((outcome) => {
        if (outcome === "refused" && visit === visitGeneration)
          for (const item of items) refusedThisVisit.add(keyOf(item));
      });
    }
  }

  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    nextRender(() => {
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
      if (document.visibilityState !== "visible") resetExposure();
      else scheduleScan();
    });
    document.addEventListener("close", scheduleScan, true);
    document.addEventListener(SLIDE_END, scheduleScan, true);
    addEventListener("blur", resetExposure);
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
        for (const key of refusedThisVisit)
          if (!current.has(key)) refusedThisVisit.delete(key);
        const count = unread.length;
        firstUnreadBtn.hidden = count === 0;
        firstUnreadBtn.textContent = "Next unread";
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
    resetExposure();
  }

  return {
    mount,
    begin,
    abort,
    present,
    observeBody,
    forgetBody,
    firstUnread,
    unreadCount: () => actionableUnread().length,
  };
}
