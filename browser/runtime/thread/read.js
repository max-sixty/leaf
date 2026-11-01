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
   leaves the message unread and is retried only on a new visit. A leaf.page visitor who
   has only read the page has no private page to record a read in, so exposure counts
   only while the session is active (layer-client.js), as user-view.js reports a view
   only then, and a pass runs when it turns active; the edge refuses a read sent
   before. A pass also runs on each change to what the page shows of its window
   (geometry.js, `watchRoom`), which includes a nonmodal surface closing: it can reveal
   a body without moving it or closing its permanent native ancestor.

   The same rendered-body and room observations record first visible agent words in
   the best-effort interaction trace. Those diagnostics need neither focus, unread
   status nor complete exposure; they require a visible document and an actually
   painted text range. They never change semantic state or delay presentation. A
   surface fading in, as the leaf's menu and a view arriving in the panel do, moves no
   box and announces nothing, so words a pass finds hidden under a running animation
   are read again when it ends.

   The first unread destination belongs to this reading too. Its Go-to route (`g u`)
   and Next unread at the head of the floating panel's view of a thread, which goes to
   that thread's first, share the same exact-message arrival. Ordinary `u` remains
   paired with `d` in whichever reading region the user is in. */
import { nextRender, sizeObserver } from "../rendering.js";
import { signal } from "/runtime/framework.js";
import {
  layoutWindow,
  presented,
  seenRect,
  watchRoom,
  clippedContents,
  shownWindow,
} from "../geometry.js";
import { intersect, hasArea } from "../rect.js";
import { recordInteraction } from "../interaction-log.js";
import { sessionIsActive } from "../layer-client.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { moved } from "./model.js";
import { readThreads } from "./state.js";
import { renderedParent } from "../shadow-tree.js";

import { savedReadingSettled } from "../keyboard/bindings.js";
import {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
} from "../frame-visibility.js";

/** @typedef {import("../../types/domain.js").ContentVersion} ContentVersion */
/** @typedef {[number, number]} Interval */
/** @typedef {{reply_id?: string | null, input_id?: string | null,
 * attempt?: string | null, reply_kind: string, presentation_kind: string,
 * surface: string}} Feedback */
/** @typedef {{id: string | null, version: string | null, feedback: Feedback | null}} BodyReading */
/** @typedef {{key: string, width: number, height: number, contentHeight: number, intervals: Interval[]}} Exposure */
/** @param {ContentVersion} item */
const keyOf = (item) => `${item.message}\u0000${item.version}`;
const EPSILON = 1;

/** @param {Interval[]} intervals */
function mergeIntervals(intervals) {
  const ordered = intervals.sort((a, b) => a[0] - b[0]);
  /** @type {Interval[]} */
  const merged = [];
  for (const [start, end] of ordered) {
    const prior = merged.at(-1);
    if (prior && start <= prior[1] + EPSILON) prior[1] = Math.max(prior[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

/** @param {Element} body @param {import("../geometry.js").ClipCache} clips @param {import("../rect.js").Box} band
 * @returns {{interval: Interval, height: number, width: number, contentHeight: number} | null} */
function visibleInterval(body, clips, band) {
  if (!presented(body)) return null;
  const box = body.getBoundingClientRect();
  // Sticky headers and the floating panel are left out of what is seen (geometry.js), so
  // a message any part of which is under one has not been shown whole, and the
  // full-width rule below withholds it.
  const clipped = seenRect(body, clips);
  if (!clipped || box.width <= 0 || box.height <= 0) return null;
  const shown = intersect(clipped, band);
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

// An element's box can intersect the viewport while all its words are clipped or
// below it. Measure the text itself through the shared clipping/chrome reading.
/** @param {Element} body @param {import("../geometry.js").ClipCache} clips @param {import("../rect.js").Box} band */
function wordsAreVisible(body, clips, band) {
  if (!presented(body) || !body.checkVisibility({ opacityProperty: true }))
    return false;
  const text = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let node = text.nextNode(); node; node = text.nextNode()) {
    if (!node.textContent?.trim()) continue;
    const holder = node.parentElement;
    if (
      !holder ||
      !presented(holder) ||
      !holder.checkVisibility({ opacityProperty: true })
    )
      continue;
    range.selectNodeContents(node);
    for (const box of range.getClientRects()) {
      const clipped = clippedContents(box, holder, clips);
      if (!clipped) continue;
      const room = shownWindow({ within: clipped, item: holder });
      if (hasArea(intersect(intersect(clipped, room), band))) return true;
    }
  }
  return false;
}

/** @param {{
 * markRead: (items: ContentVersion[]) => ReturnType<typeof import("../delivery.js").deliverBookkeeping>,
 * openThread: ReturnType<typeof import("./destination.js").createThreadDestinations>["openPageThread"],
 * }} dependencies */
export function createReadTracking({ markRead, openThread }) {
  /** @type {WeakMap<Element, Exposure>} */
  let coverage = new WeakMap();
  /** @type {Map<Element, BodyReading & {body: Element}>} */
  const renderedBodies = new Map();
  /** @type {Set<string>} */
  const visibleReplies = new Set();
  /** @type {Set<string>} */
  const refusedThisVisit = new Set();
  const sizes = sizeObserver(() => scheduleScan());
  /** @type {(() => void)[]} */
  const frameWatches = [];
  // The threads the last presented pass drew. A signal, because the first-unread
  // command's liveness reads it once the pass has committed.
  const committedThreads = signal(
    /** @type {ReturnType<typeof readThreads>["threads"]} */ ([]),
  );
  let threadsPresented = false;
  let presentationGeneration = 0;
  let visitGeneration = 0;
  let scheduled = false;
  // What waits for the next pass over the presented threads (`afterPass`).
  /** @type {(() => void)[]} */
  let passWaiters = [];

  function resetExposure() {
    visitGeneration++;
    exposureGeneration++;
    coverage = new WeakMap();
    refusedThisVisit.clear();
  }

  /** @param {ReturnType<typeof readThreads>["threads"]} threads */
  const unreadIn = (threads) =>
    threads.flatMap((thread) => {
      const unread = new Map(thread.unread.map((item) => [item.message, item]));
      return thread.msgs.flatMap((message) => {
        const item = unread.get(message.id);
        return item ? [{ thread, item, message }] : [];
      });
    });
  // Unread in what the page has presented and still unread in the current reading: a
  // version this tab is marking read, or another tab or update already did, is not
  // offered again.
  const actionableUnread = () => {
    const live = new Set(
      unreadIn(readThreads().threads).map(({ item }) => keyOf(item)),
    );
    return unreadIn(committedThreads.value).filter(({ item }) => live.has(keyOf(item)));
  };

  // The first unread message on the page, or in the thread keyed `thread`.
  /** @param {string | null} [thread] */
  function firstUnread(thread = null) {
    const target = actionableUnread()
      .filter((each) => thread === null || each.thread.key === thread)
      .sort((a, b) => Number(moved(a.message).seq) - Number(moved(b.message).seq))[0];
    return target
      ? openThread(target.item.message, { part: "message" })
      : Promise.resolve();
  }

  /** @satisfies {import("../keyboard/bindings.js").Command} */
  const firstUnreadCommand = {
    id: "thread.unread.first",
    ready: savedReadingSettled,
    keys: ["u"],
    title: "first unread",
    touch: false,
    travels: true,
    when: () => actionableUnread().length > 0,
    run: () => void firstUnread(),
  };

  /** @param {import("../frame-visibility.js").SampleVisibility | null} [sampleBand] */
  function scan(sampleBand) {
    if (document.visibilityState !== "visible" || sampleBand?.visible === false) return;
    const band = sampleBand ?? layoutWindow();
    if (!band) return;
    const candidates = new Map(
      (threadsPresented ? actionableUnread() : []).map(({ item }) => [
        item.message,
        item,
      ]),
    );
    const mayRead = threadsPresented && document.hasFocus() && sessionIsActive();
    const clips = new Map();
    /** @type {Map<string, ContentVersion>} */
    const completed = new Map();
    const unseenWords = [];
    for (const [node, rendered] of renderedBodies) {
      const { body, id, version, feedback } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      if (feedback) {
        const identity = feedback.reply_id ?? `input:${feedback.input_id}`;
        const key = `${identity}:${feedback.presentation_kind}:${feedback.surface}`;
        if (!visibleReplies.has(key)) {
          if (wordsAreVisible(body, clips, band)) {
            visibleReplies.add(key);
            recordInteraction("reply_visible", feedback);
          } else unseenWords.push(body);
        }
      }
      const item = mayRead && id !== null ? candidates.get(id) : undefined;
      if (!item || item.version !== version) continue;
      const key = keyOf(item);
      if (completed.has(key) || refusedThisVisit.has(key)) continue;
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
        tracked.intervals.every(
          ([start, end]) => start <= EPSILON && end >= visible.height - EPSILON,
        )
      ) {
        completed.set(key, item);
      }
    }
    if (unseenWords.length) passAfterFades(unseenWords);
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
    if (!threadsPresented) return;
    const waiting = passWaiters;
    passWaiters = [];
    for (const then of waiting) then();
  }

  // Neither the size observer nor the room announces a fade (the header). For words a
  // pass found hidden, each animation or transition on their body, inside it, or on a
  // box the body renders inside brings one more pass when that run ends or is
  // cancelled. A replayed animation has a new `finished` promise and is awaited again.
  const awaitedRuns = new WeakSet();
  /** @param {readonly Element[]} bodies */
  function passAfterFades(bodies) {
    for (const body of bodies) {
      const animations = body.getAnimations({ subtree: true });
      for (let at = renderedParent(body); at; at = renderedParent(at))
        animations.push(...at.getAnimations());
      for (const { finished } of animations) {
        if (awaitedRuns.has(finished)) continue;
        awaitedRuns.add(finished);
        finished.then(scheduleScan, scheduleScan);
      }
    }
  }

  // Runs `then` after the next pass over the presented threads, once what that pass
  // read counts as read in `readThreads()`: what still stands unread then is what the
  // page has not shown whole, as the floating panel's Next unread asks.
  /** @param {() => void} then */
  function afterPass(then) {
    passWaiters.push(then);
    scheduleScan();
  }

  let exposureGeneration = 0;

  function scheduleScan() {
    exposureGeneration++;
    if (scheduled) return;
    scheduled = true;
    nextRender(() => {
      scheduled = false;
      // The containing page owns a sample's clips and chrome. Ask it when this scan
      // runs; a rectangle from an earlier threshold crossing cannot acknowledge words.
      const asked = readSampleVisibility();
      if (!asked) {
        // Any other frame reads words only while it shows.
        if (frameVisibility()?.visible !== false) scan();
        return;
      }
      const generation = exposureGeneration;
      void asked.then((reading) => {
        if (generation === exposureGeneration) scan(reading);
      }, reportError);
    });
  }

  function mount() {
    frameWatches.push(watchRoom(scheduleScan));
    addEventListener("focus", scheduleScan);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") resetExposure();
      else scheduleScan();
    });
    addEventListener("blur", resetExposure);
    addEventListener("load", scheduleScan, true);
    document.addEventListener("lf-session-active", scheduleScan);
    frameWatches.push(
      onFrameVisibility((visibility) => {
        if (!visibility || visibility.visible) scheduleScan();
        else resetExposure();
      }),
    );
    // A page kept for back and forward comes back with its watches.
    addEventListener("pagehide", (event) => {
      exposureGeneration++;
      if (event.persisted) return;
      sizes.disconnect();
      for (const unwatch of frameWatches) unwatch();
      frameWatches.length = 0;
    });
  }

  /** @param {Element} body @param {BodyReading} reading */
  function observeBody(body, reading) {
    if (!renderedBodies.has(body)) sizes.observe(body);
    const registration = {
      body,
      ...reading,
    };
    renderedBodies.set(body, registration);
    scheduleScan();
    return () => {
      if (renderedBodies.get(body) !== registration) return;
      sizes.unobserve(body);
      renderedBodies.delete(body);
    };
  }

  /** @param {Element} body @param {{id: string, version: string, author: string, attempt: string | null, provisional: boolean, progress: boolean, failure: string | null}} message */
  function observeMessage(body, message) {
    return observeBody(body, {
      id: message.id,
      version: message.version,
      feedback:
        message.author === "agent"
          ? {
              reply_id: message.id,
              attempt: message.attempt,
              presentation_kind: "message_words",
              reply_kind: message.provisional
                ? "stream"
                : message.progress
                  ? "progress"
                  : message.failure
                    ? "failure"
                    : "answer",
              surface: "margin",
            }
          : null,
    });
  }

  // A working line displays explicit agent words without mounting their folded
  // MessageView. Its renderer supplies exact source identity, never its thread parent.
  /** @param {Element} body @param {Feedback} feedback */
  function observeFeedback(body, feedback) {
    return observeBody(body, { id: null, version: null, feedback });
  }

  function present() {
    const generation = presentationGeneration;
    const threads = readThreads().threads;
    void whenDocumentPresented()
      .then(() => {
        if (generation !== presentationGeneration) return;
        committedThreads.value = threads;
        threadsPresented = true;
        const unread = unreadIn(threads);
        const current = new Set(unread.map(({ item }) => keyOf(item)));
        for (const key of refusedThisVisit)
          if (!current.has(key)) refusedThisVisit.delete(key);
        scheduleScan();
      })
      .catch(() => {
        if (generation === presentationGeneration) coverage = new WeakMap();
      });
  }

  function begin() {
    presentationGeneration++;
    exposureGeneration++;
    threadsPresented = false;
  }

  function abort() {
    presentationGeneration++;
    threadsPresented = false;
    resetExposure();
  }

  return {
    mount,
    begin,
    abort,
    present,
    observeMessage,
    observeFeedback,
    firstUnread,
    afterPass,
    firstUnreadCommand,
  };
}
