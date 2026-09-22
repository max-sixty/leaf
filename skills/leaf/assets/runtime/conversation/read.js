/* Page-owned acknowledgement of exact, presented agent content.

   The log and semantic publisher decide unread. This owner observes only mechanical
   exposure: a visible prose body is acknowledged after its complete vertical extent
   has been shown without gaps in one rendered surface and one content version. A
   widget-authored body has no general contract for its hidden internal states, so its
   thread's explicit Mark read control acknowledges it. Reading never answers an Ask.
   Each observation pass batches newly completed versions into one event. */
import { shownRect } from "../geometry.js";
import { notice } from "../notifications.js";
import { closestAcross, containsAcross } from "../passages.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { firstUnreadBtn, panel, panelWouldCover } from "./panel-elements.js";
import { readThreads } from "./state.js";

const keyOf = (message) => `${message.id}\u0000${message.contentVersion}`;
const itemOf = (message) => ({ message: message.id, version: message.contentVersion });
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
  for (let current = window; current !== current.top; ) {
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
      box.width <= 0 || box.height <= 0 ||
      box.left < 0 || box.top < 0 ||
      box.right > owner.innerWidth || box.bottom > owner.innerHeight
    ) return false;
    const modal = owner.document.querySelector("dialog:modal");
    if (modal && !containsAcross(modal, frame)) return false;
    for (let ancestor = frame.parentElement ?? frame.getRootNode()?.host;
      ancestor;
      ancestor = ancestor.parentElement ?? ancestor.getRootNode()?.host) {
      const style = owner.getComputedStyle(ancestor);
      if (ancestor.inert || ancestor.getAttribute?.("aria-hidden") === "true" ||
          style.visibility === "hidden" || style.display === "none") return false;
      if (!/(auto|scroll|hidden|clip)/.test(`${style.overflowX} ${style.overflowY}`)) continue;
      const clip = ancestor.getBoundingClientRect();
      if (box.left < clip.left || box.top < clip.top ||
          box.right > clip.right || box.bottom > clip.bottom) return false;
    }
    current = owner;
  }
  return true;
}

function hasHiddenInnerScroll(body) {
  return [...body.querySelectorAll("*")].some((element) => {
    const { overflowX, overflowY } = getComputedStyle(element);
    return (/(auto|scroll|hidden|clip)/.test(overflowY) &&
      element.scrollHeight > element.clientHeight + EPSILON) ||
      (/(auto|scroll|hidden|clip)/.test(overflowX) &&
      element.scrollWidth > element.clientWidth + EPSILON);
  });
}

function visibleInterval(body, clips) {
  if (!body.checkVisibility()) return null;
  for (let owner = body; owner; owner = owner.parentElement ?? owner.getRootNode()?.host ?? null)
    if (owner.inert || owner.getAttribute?.("aria-hidden") === "true") return null;
  const modal = document.querySelector("dialog:modal");
  if (modal && !containsAcross(modal, body)) return null;
  if (panel.open && panelWouldCover() && !containsAcross(panel, body)) return null;
  const box = body.getBoundingClientRect();
  const shown = shownRect(body, clips);
  if (!shown || box.width <= 0 || box.height <= 0) return null;
  if (shown.left > box.left + EPSILON || shown.right < box.right - EPSILON) return null;
  let top = shown.top;
  let bottom = shown.bottom;
  // Sticky run headings paint above the list without clipping its scrollport.
  // Subtract their occupied edge so a message hidden under one is not called read.
  const threadList = closestAcross(body, "leaf-thread-list");
  if (threadList) for (const heading of threadList.querySelectorAll(".lf-pinned")) {
    if (!heading.checkVisibility()) continue;
    const cover = heading.getBoundingClientRect();
    if (cover.left < shown.right && cover.right > shown.left &&
        cover.top <= top && cover.bottom > top) top = Math.max(top, cover.bottom);
  }
  if (bottom <= top) return null;
  return {
    interval: [Math.max(0, top - box.top), Math.min(box.height, bottom - box.top)],
    height: box.height,
    width: box.width,
    contentHeight: body.scrollHeight,
  };
}

export function createReadAcknowledgement({ post, showThread, setUnreadThreadCount }) {
  let coverage = new WeakMap();
  const renderedBodies = new Map();
  const refusedAutomatic = new Set();
  const sizes = new ResizeObserver(() => scheduleScan());
  const frameObservers = [];
  let committedThreads = [];
  let presented = false;
  let presentationGeneration = 0;
  let scheduled = false;

  const unread = () => committedThreads.flatMap((thread) =>
    thread.msgs.filter((message) => message.unread && message.contentVersion)
      .map((message) => ({ thread, message })),
  );
  const actionableUnread = () => {
    const live = new Set(readThreads().threads.flatMap((thread) =>
      thread.msgs.filter((message) => message.unread && message.contentVersion)
        .map(keyOf),
    ));
    return unread().filter(({ message }) => live.has(keyOf(message)));
  };

  function markThread(id) {
    const messages = actionableUnread().filter(({ thread }) => thread.root.id === id)
      .map(({ message }) => message)
      .map(itemOf);
    if (messages.length) void post(messages).then((accepted) => {
      if (!accepted) notice("Couldn't mark thread read — try again.");
    });
  }

  function firstUnread() {
    const target = actionableUnread().sort((a, b) =>
      (a.message.edited?.seq ?? a.message.seq) -
      (b.message.edited?.seq ?? b.message.seq),
    )[0];
    if (target) void showThread(target.message.id, { focus: "message" });
  }

  function scan() {
    if (!presented || document.visibilityState !== "visible" || !document.hasFocus() ||
        !frameIsFullyVisible()) return;
    const candidates = new Map(actionableUnread().map(({ message }) => [keyOf(message), message]));
    if (!candidates.size) return;
    const clips = new Map();
    const completed = new Map();
    for (const [node, rendered] of renderedBodies) {
      const { body, id, version, authored } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      const key = `${id}\u0000${version}`;
      const message = candidates.get(key);
      if (!message || authored || completed.has(key) || refusedAutomatic.has(key) ||
          hasHiddenInnerScroll(body)) continue;
      const visible = visibleInterval(body, clips);
      if (!visible) continue;
      let tracked = coverage.get(body);
      if (!tracked || tracked.key !== key ||
          tracked.width !== visible.width ||
          tracked.height !== visible.height ||
          tracked.contentHeight !== visible.contentHeight) {
        tracked = { key, width: visible.width, height: visible.height,
          contentHeight: visible.contentHeight, intervals: [] };
        coverage.set(body, tracked);
      }
      tracked.intervals = mergeIntervals([...tracked.intervals, visible.interval]);
      if (tracked.intervals.length === 1 &&
          tracked.intervals[0][0] <= EPSILON &&
          tracked.intervals[0][1] >= visible.height - EPSILON) {
        completed.set(key, itemOf(message));
      }
    }
    if (completed.size) {
      const items = [...completed.values()];
      void post(items).then((accepted) => {
        if (!accepted) for (const item of items)
          refusedAutomatic.add(`${item.message}\u0000${item.version}`);
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
    addEventListener("blur", () => { coverage = new WeakMap(); });
    addEventListener("load", scheduleScan, true);
    // Moving a specimen frame in its parent changes exposure without a scroll or
    // resize inside the child. Observe each containing frame in its own viewport.
    for (let current = window; current !== current.top; ) {
      let frame;
      try {
        frame = current.frameElement;
      } catch {
        break;
      }
      if (!frame) break;
      const owner = frame.ownerDocument.defaultView;
      const observer = new owner.IntersectionObserver(scheduleScan, { threshold: [0, 1] });
      observer.observe(frame);
      frameObservers.push(observer);
      current = owner;
    }
    addEventListener("pagehide", () => {
      sizes.disconnect();
      for (const observer of frameObservers) observer.disconnect();
      frameObservers.length = 0;
    }, { once: true });
  }

  function observeBody(node, body, message) {
    if (!body) return;
    const previous = renderedBodies.get(node);
    if (previous?.body !== body) {
      if (previous) sizes.unobserve(previous.body);
      sizes.observe(body);
    }
    renderedBodies.set(node, {
      body, id: message.id, version: message.contentVersion,
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
    void whenDocumentPresented().then(() => {
      if (generation !== presentationGeneration) return;
      committedThreads = threads;
      presented = true;
      const current = new Set(unread().map(({ message }) => keyOf(message)));
      for (const key of refusedAutomatic) if (!current.has(key)) refusedAutomatic.delete(key);
      const count = unread().length;
      setUnreadThreadCount(threads.filter((thread) => thread.unreadCount > 0).length);
      firstUnreadBtn.hidden = count === 0;
      firstUnreadBtn.textContent = `Unread ${count}`;
      firstUnreadBtn.setAttribute("aria-label", `${count} unread messages. Go to first unread message`);
      scheduleScan();
    }).catch(() => {
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

  return { mount, begin, abort, present, scheduleScan, scan, observeBody, forgetBody,
    markThread, firstUnread, unread };
}
