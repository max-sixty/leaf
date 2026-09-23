/* The page's evidence that the reader has seen exact agent content.

   Whether a version is unread is the server's reading of the whole log (`read_state`),
   published as each Thread's `unread`; replying, answering and resolving already count
   there. This owner adds the one kind of evidence only the page has, exposure: a
   visible prose body is marked read once its complete vertical extent has been shown
   without gaps in one rendered surface and one content version. What the body holds
   inside that extent — a wide code block, a scroller of its own — is part of what was
   shown; geometry cannot say whether the reader read every column of it, and a message
   whose contents never let it count would stand unread forever. A widget-authored body
   has hidden states of its own and no general contract for them, so exposure does not
   mark it read: answering its widget does, and so does its thread's Mark read control.
   Each observation pass batches newly completed versions into one `read` event, which
   the application sends outside the gesture queue (delivery.js). */
import { shownRect } from "../geometry.js";
import { notice } from "../notifications.js";
import { containsAcross } from "../passages.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { moved } from "./model.js";
import { firstUnreadBtn, panel, panelWouldCover } from "./panel-elements.js";
import { readThreads } from "./state.js";

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

// A child viewport does not know when its iframe is hidden by the parent page.
// Require each containing frame to stand wholly inside its parent's shown region.
// This is deliberately conservative for a partially visible frame.
function frameIsFullyVisible() {
  for (let current = window; current !== current.top;) {
    let frame;
    try {
      frame = current.frameElement;
    } catch {
      return false;
    }
    if (!frame || !frame.checkVisibility()) return false;
    const owner = frame.ownerDocument.defaultView;
    const box = frame.getBoundingClientRect();
    if (
      box.width <= 0 ||
      box.height <= 0 ||
      box.left < 0 ||
      box.top < 0 ||
      box.right > owner.innerWidth ||
      box.bottom > owner.innerHeight
    )
      return false;
    const modal = owner.document.querySelector("dialog:modal");
    if (modal && !containsAcross(modal, frame)) return false;
    for (
      let ancestor = frame.parentElement ?? frame.getRootNode()?.host;
      ancestor;
      ancestor = ancestor.parentElement ?? ancestor.getRootNode()?.host
    ) {
      const style = owner.getComputedStyle(ancestor);
      if (
        ancestor.inert ||
        ancestor.getAttribute?.("aria-hidden") === "true" ||
        style.visibility === "hidden" ||
        style.display === "none"
      )
        return false;
      if (!/(auto|scroll|hidden|clip)/.test(`${style.overflowX} ${style.overflowY}`))
        continue;
      const clip = ancestor.getBoundingClientRect();
      if (
        box.left < clip.left ||
        box.top < clip.top ||
        box.right > clip.right ||
        box.bottom > clip.bottom
      )
        return false;
    }
    current = owner;
  }
  return true;
}

function visibleInterval(body, clips) {
  if (!body.checkVisibility()) return null;
  for (
    let owner = body;
    owner;
    owner = owner.parentElement ?? owner.getRootNode()?.host ?? null
  )
    if (owner.inert || owner.getAttribute?.("aria-hidden") === "true") return null;
  const modal = document.querySelector("dialog:modal");
  if (modal && !containsAcross(modal, body)) return null;
  if (panel.open && panelWouldCover() && !containsAcross(panel, body)) return null;
  const box = body.getBoundingClientRect();
  // Sticky run headings are left out of what is shown (geometry.js, visibleBand), so a
  // message hidden under one is not read.
  const shown = shownRect(body, clips);
  if (!shown || box.width <= 0 || box.height <= 0) return null;
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

export function createReadTracking({ markRead, showThread }) {
  let coverage = new WeakMap();
  const renderedBodies = new Map();
  const refusedAutomatic = new Set();
  const sizes = new ResizeObserver(() => scheduleScan());
  const frameObservers = [];
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
    if (
      !presented ||
      document.visibilityState !== "visible" ||
      !document.hasFocus() ||
      !frameIsFullyVisible()
    )
      return;
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
      const visible = visibleInterval(body, clips);
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
    // Moving a specimen frame in its parent changes exposure without a scroll or
    // resize inside the child. Observe each containing frame in its own viewport.
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
      frameObservers.push(observer);
      current = owner;
    }
    addEventListener(
      "pagehide",
      () => {
        sizes.disconnect();
        for (const observer of frameObservers) observer.disconnect();
        frameObservers.length = 0;
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
