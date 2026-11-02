/* Contextual thread preview: a card with a nested conversation lifetime.

   One Floating UI driver follows this card across conversation changes and stops
   when the card closes. Each selected conversation owns its originating control,
   reading region, held edge, pending placement/focus, and growth out of the comment
   box Send replaced (`sent`). Replacing it retires that work before margin
   preparation can synchronously render again.
   A retained refresh preserves the selection's reading and draft continuity.
   Margin disclosure remains the margin's; selection records only whether a walk
   opened a cluster so its end can return that disclosure.

   ThreadView owns conversation rendering; comment-placement.js owns the side,
   frame adoption and opening-scroll policy. CardAnchor owns the place an interaction
   preserves. Floating UI follows
   the attachment within the reading region or viewport, under the chrome; regions
   clip it at their edges. A scroll never closes the card: it leaves with its target
   and comes back with it. A target hidden by the document withholds the card's native
   draft and focus until it is drawn again.

   A selection holds its placement side, its width and one edge. The width is the
   comment box's where Send opened the card, else the one the card first stood at, or
   was carried at, so a longer line arriving wraps inside it rather than carrying the
   controls at its far edge; only a narrower room narrows it.
   Another selection chooses afresh. Floating UI supplies room at that edge; native
   grid tracks share it between transcript and reply, growing to their words before
   scrolling. Reply continuity retains removed turns as flexible space and lets the
   transcript yield writing room without losing the visible lines.

   Placement changes geometry, never rebuilds contents. Retained state reads hold the
   reader's message and scroll position; another thread opens at its first unread
   message, else its latest, and the thread a comment's Send opened where the box's
   words stood (`showArrival`).
   A new/growing agent turn follows only at the tail. Landing, Send and stepping may
   move the reading; keepThreadLanding retains their destination through fitting until
   a newer reading gesture ends that authority. Size is fitted before paint, so a sent
   reply does not grow twice. Margin location and its keyboard ladder own dismissal
   and target landing; the card keeps Send's focus on the thread that received it. */
import {
  atScrollEnd,
  moveScrollerBy,
  pageScroller,
  scrollToEnd,
  scrollLimit,
} from "../scrolling.js";
import { cancelRender, nextRender, sizeObserver } from "../rendering.js";
import { spokenSubject } from "../contribution-model.js";
import { labelWords } from "../words.js";
import { THREAD_CARD } from "./margin-layout.js";
import { showsContents, slotTop } from "../geometry.js";
import {
  focusDestination,
  holdFocus,
  inputCount,
  onCurrentLocation,
  onUserInput,
  focused,
  tabStops,
} from "../focus.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { closeControl, el, offerAction } from "../widget-elements.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "../keeps.js";
import { setChildren } from "../dom-children.js";
import { move } from "../dom-move.js";
import { registerReadingRegion, scrollerFor } from "../reading-regions.js";
import { declareOffFlowSurface } from "../off-flow.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { boxMotion } from "../box-motion.js";
import { paintKeysWithin } from "../keyboard/scopes.js";
import { closestAcross } from "../passages.js";
import { threadIdNamed } from "../thread/state.js";
import { turns } from "../thread/model.js";
import { anchorLabel, releaseAuthoredUnder } from "../thread/messages.js";
import { coarsePointer } from "../pointer.js";
import {
  cardMeasure,
  cardMinimum,
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
  makeRoom,
} from "./comment-placement.js";
import { passageGeometry } from "../resolved-target.js";
import {
  floatingPlacement,
  floatingUi,
  floatingGeometry,
  heldEdges,
} from "./floating.js";
import { surfaceGrip } from "./surface-grip.js";
import { placeKeeper } from "../user-place.js";
import { renderedOrder, renderedUnder, under } from "../shadow.js";
import { keys } from "../keyboard/scopes.js";
import { retainUserIntent } from "../user-intent.js";
import { threadFocusDestination } from "../thread/focus.js";
import { claimSeatReplies } from "../thread/inline.js";
import { releaseReplies } from "../thread/replies.js";
import { keepThreadLanding, showReturnTurn } from "../thread/reply-landing.js";
import { CardAnchor } from "../thread/card-anchor.js";

/** @typedef {import("../annotation-inventory.js").InventoryEntry} Entry
 * @typedef {import("../margin-model.js").ThreadItem} Item
 * @typedef {import("../margin-model.js").ThreadChoice} Choice
 * @typedef {import("../thread/workflow.js").ThreadRecord} ThreadRecord
 * @typedef {NonNullable<ReturnType<ReturnType<typeof import("./composing/floating-response.js").createFloatingResponsePlacement>["frame"]>>} Origin
 * @typedef {{entry: Entry, choice: Choice, threadItem: string, control: Element | null,
 * accompanies: boolean, forced: boolean, disclosed: boolean}} Selection
 * @typedef {Selection & {item: Item, preparing: boolean, latest: {id: string, text: string | undefined} | null,
 * arriving: boolean, sent: Pick<Origin, "fromEnd" | "field"> | null, away: boolean,
 * positionFrame: number, positionResult: PromiseWithResolvers<boolean> | null,
 * focusPending: {holding: Element | null} | null, withheldFocus: ReturnType<typeof holdFocus>,
 * transcript: HTMLElement | null, place: ReturnType<typeof placeKeeper> | null,
 * stopRegion: (() => void) | null, side: ReturnType<typeof commentPlacement>, anchor: CardAnchor,
 * reading: {input: number, scroll: number, end: boolean} | null, itemView: {node: HTMLElement, body: HTMLElement} | null, width: number | null, scroller: Element, followed: boolean}} Session
 * @typedef {{latest: boolean, end: boolean, scroll: number, keepTop: boolean, transcript: HTMLElement}} Reading
 */

// A margin card's reply box.
const REPLY_BOX = `.lf-thread-reply ${TEXT_FIELD}`;
// Where a reading region cuts the card, inward from each of its edges.
const CUT_EDGES = [
  "--lf-cut-top",
  "--lf-cut-right",
  "--lf-cut-bottom",
  "--lf-cut-left",
];

/** @param {{inventory: ReturnType<typeof import("../annotation-inventory.js").createAnnotationInventory>,
 * renderMarginThread: (host: HTMLElement, thread: ThreadRecord, controls: import("../thread/thread-card.js").MarginControls) => ReturnType<typeof import("../thread/inline.js").renderMarginThread>,
 * placedAt: ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["placedAt"],
 * scrollThreadIntoView: typeof import("../thread/reply-landing.js").scrollThreadIntoView,
 * scrollToElement: ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["scrollToElement"],
 * openPageThread: ReturnType<typeof import("../thread/destination.js").createThreadDestinations>["openPageThread"],
 * openInPanel: (id: string) => unknown, onClose: (selection: Selection | null) => void}} dependencies */
export function createThreadPreview({
  inventory,
  renderMarginThread,
  placedAt,
  scrollThreadIntoView,
  scrollToElement,
  openPageThread,
  openInPanel,
  onClose,
}) {
  /** @type {Session | null} */
  let previewSession = null;
  const { targetFor, entryPoint, entryPlace } = inventory;
  // The card is the margin's, as the cluster it hangs from is, rather than a layer over
  // the page: a top-layer popover made every press on the page a light dismissal and
  // tiered the keyboard over it, so being on the passage it discusses took it down.
  // It shows while the user is at its target (`followCurrentLocation`).
  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = THREAD_CARD;
  // A public part a theme restyles (`layer.chrome_restyle`), its ground inside it.
  preview.setAttribute("part", "card");
  preview.hidden = true;
  preview.setAttribute("role", "dialog");
  const previewOpen = () => previewSession !== null;
  const previewClose = closeControl({
    name: "Dismiss thread view",
    title: "Dismiss thread view (Esc)",
    className: "lf-margin-preview-close",
  });
  const previewNav = el("span", "lf-margin-preview-nav");
  const previewPosition = el("span", "lf-margin-preview-position");
  const previewPrevious = offerAction(
    "symbol",
    "lf-margin-preview-step",
    "Previous thread",
    { action: "previous" },
  );
  const previewNext = offerAction("symbol", "lf-margin-preview-step", "Next thread", {
    action: "next",
  });
  previewNav.append(previewPrevious, previewPosition, previewNext);
  // Open in panel moves the card's thread into the floating panel's view of it, which
  // reads a long thread wider than the card's room beside the column. The card closes,
  // so one thread stands open, and the view's Show on page comes back.
  const previewOpenInPanel = offerAction(
    "symbol",
    "lf-margin-preview-expand",
    "Open in panel",
    { action: "expand" },
  );
  const previewList = el("div", "lf-margin-preview-list");
  let dismiss = () => {};
  // Carried by its grip, the card stands where the user drops it, relative to what it is
  // about, at the width it was carried at, until its placement chooses afresh.
  const carry = surfaceGrip({
    surface: preview,
    bounds: () => commentBoundary({ scroller: previewSession?.scroller }),
    dropped(box) {
      const session = previewSession;
      if (!session) return;
      if (box) {
        session.width = box.width;
        session.side.adopt({
          box,
          placement: { ...session.side.capture(), moved: true },
        });
      }
      placeThreadPreview();
    },
  });
  const face = el("div", "lf-margin-preview-card");
  face.append(previewList);
  // The card follows every change of its layout as the panel does, on the panel's
  // tween, whoever made it: a send, typing, an answer arriving, another thread. It reads
  // in the plane its placement stands it in, by the edges that hold it there
  // (floating.js, `heldEdges`), so a scroll or a carry that moves it whole moves
  // nothing in it. A card no placement stands yet has nothing to move from.
  const followCard = () => {
    if (!preview.hasAttribute("data-lf-thread-placement")) return following.forget();
    following.follow();
  };
  const followed = sizeObserver(followCard);
  const following = boxMotion({
    // The face is the root, so the grip beside it, whose clip opens its middle to
    // the card's own presses, is never cut by the motion.
    root: face,
    box: face,
    // The card stands on a surface of its own, as the floating panel does: the card's
    // face paints nothing past its own box, and the surface, a layer behind it reaching
    // far past the card, draws its ring, the card's border, its fill and its shadow
    // cut to the card's outline, so the outline can travel between two places while
    // the card's layout stands at the second. The surface is inside the card, so the
    // page's scroll carries it with the card and a reading region's cut cuts it too.
    surface: "lf-margin-preview-ground",
    lift: 3,
    outset: 0,
    observer: followed,
    held: () => heldEdges(preview),
  });
  preview.append(following.ground, carry.grip, face);
  followed.observe(face);
  // The card follows the margin entry it hangs from (`session.control`) in the Tab
  // order, as a popover follows its invoker: Tab on the entry enters the card, Shift+Tab
  // from before the card's first stop returns to the entry, and Tab past the card's last
  // stop, or Shift+Tab from the entry, goes on from the entry as though the card weren't
  // there. The browser's own order doesn't: the card stands in the chrome after the
  // page and just before the margin, so Shift+Tab out of it reached the page's last
  // stop, which scrolled the page there and, being away from the card's target,
  // closed the card. To pass over the card, a row puts the user on the entry, or on the
  // card's own box just before the margin, and leaves the browser to take the step from
  // there, as the floating panel's menu does.
  const opener = () =>
    previewSession?.control?.checkVisibility() ? previewSession.control : null;
  const onOpener = () => Boolean(opener()) && focused() === opener();
  // The stops in `root` before (-1) or after (1) `at`, in the browser's order.
  /** @param {Element} root @param {Element} at @param {number} side */
  const stopsBeside = (root, at, side) =>
    tabStops(root).filter(
      (stop) =>
        stop !== at &&
        !renderedUnder(at, stop) &&
        Math.sign(renderedOrder(stop, at)) === side,
    );
  /** @param {number} side */
  const atCardEdge = (side) => {
    const at = focused();
    return (
      at !== null && Boolean(opener()) && stopsBeside(preview, at, side).length === 0
    );
  };
  keys(preview, null, [
    {
      id: "margin.card.back",
      keys: ["Shift+Tab"],
      title: "back to the margin entry",
      repeat: true,
      runFromCommandReference: false,
      when: () => atCardEdge(-1),
      get run() {
        const target = opener();
        return target ? () => focusDestination(target, "step") : undefined;
      },
    },
    {
      id: "margin.card.onward",
      keys: ["Tab"],
      title: "on past the margin entry",
      native: true,
      repeat: true,
      runFromCommandReference: false,
      when: () => atCardEdge(1),
      get run() {
        const target = opener();
        return target ? () => focusDestination(target, "return") : undefined;
      },
    },
  ]);
  // The entry's half, which the margin declares on its rows.
  const openerKeys = [
    {
      id: "margin.card.enter",
      keys: ["Tab"],
      title: "into the thread card",
      repeat: true,
      runFromCommandReference: false,
      when: () => onOpener() && tabStops(preview).length > 0,
      get run() {
        const target = tabStops(preview)[0];
        return target ? () => focusDestination(target, "step") : undefined;
      },
    },
    {
      id: "margin.card.over",
      keys: ["Shift+Tab"],
      title: "back past the thread card",
      native: true,
      repeat: true,
      runFromCommandReference: false,
      when: () => {
        const target = opener();
        return (
          target !== null &&
          onOpener() &&
          under(stopsBeside(chromeRoot, target, -1).at(-1), preview)
        );
      },
      run: () => focusDestination(preview, "return"),
    },
  ];
  // Capture before the control changes the card. Native editing ends a send's hold
  // before the field changes its words or geometry.
  onUserInput((event) => previewSession?.anchor.pressed(event, inputCount()));
  preview.addEventListener("lf-before-edit", (event) => {
    if (
      event
        .composedPath()
        .some((node) => node instanceof Element && node.matches(".lf-thread-reply"))
    )
      previewSession?.anchor.writing();
  });
  let previewRegionMounted = false;
  // The card's transcript is re-rendered on every reading of its thread; a message holds
  // the user's place in it under the event id it is rendered with (user-place.js).
  /** @param {Session} session @param {ReturnType<typeof import("../thread/inline.js").renderMarginThread>[number]} reading */
  function syncPreviewTranscript(session, { thread: card, transcript }) {
    if (transcript === session.transcript) return;
    session.stopRegion?.();
    session.stopRegion = null;
    session.transcript = transcript;
    session.place = transcript
      ? placeKeeper(transcript, {
          items: ".lf-msg[data-event]",
          identity: (message) => message.getAttribute("data-event"),
        })
      : null;
    if (previewRegionMounted && transcript) {
      // The transcript's width and shown turns when its gutter was last decided.
      let decided = "";
      session.stopRegion = registerReadingRegion({
        id: THREAD_CARD,
        host: preview,
        body: transcript,
        paintContinuation: (above) => {
          // A head sticks only while its own message is under it. Follow its real
          // lower edge as the next message pushes it away; between messages the
          // transcript's edge is the cut. A declared head height cannot say this.
          // Once anything is scrolled away, the head rows cover the room above them
          // (`data-lf-scrolled`, annotation-chrome.css).
          let edge = 0;
          let height = above ? 12 : 0;
          // Once its turns overflow, the transcript holds its scrollbar's gutter
          // (`data-lf-overflows`, annotation-chrome.css) until its width or the
          // number of turns it shows changes. The gutter narrows the turns, and a
          // narrowed picture is shorter, so turns can overflow without the gutter and
          // fit with it: dropping the gutter whenever they fit brought it back the
          // next frame, and so on every frame. A transcript that stops overflowing
          // otherwise, as when the window grows taller or the reply box empties,
          // keeps its words the gutter's width narrower until then.
          /** @type {NodeListOf<HTMLElement>} */
          const messages = transcript.querySelectorAll(":scope > .lf-msg");
          const overflows = transcript.scrollHeight > transcript.clientHeight;
          const shown = [...messages].filter((message) => !message.hidden).length;
          const shape = `${transcript.offsetWidth} ${shown}`;
          const room = slotTop(transcript);
          const top =
            transcript.getBoundingClientRect().top + transcript.clientTop + room;
          // A later message's head spans the actions' track (annotation-chrome.css),
          // so while its line shares the actions' it keeps to its own track and its
          // controls stand aside.
          for (const message of messages) {
            const head = message.querySelector(":scope > .lf-msg-head");
            const box = head?.getBoundingClientRect();
            keeps(
              message,
              "data-lf-beside-actions",
              above && box && box.top < top + box.height && box.bottom > top
                ? ""
                : null,
            );
          }
          if (above) {
            for (const head of transcript.querySelectorAll(".lf-msg-head")) {
              const box = head.getBoundingClientRect();
              if (!box.height || box.bottom <= top) continue;
              if (box.top <= top) edge = box.bottom - top;
              else {
                // Heads follow message order. Stop before the next name, including
                // when only a sliver of the inter-message gap remains above it.
                height = Math.min(height, box.top - top - edge);
                break;
              }
            }
          }
          card.style.setProperty("--lf-thread-fade-top", layoutPx(edge));
          card.style.setProperty("--lf-thread-fade-height", layoutPx(height));
          keeps(card, "data-lf-scrolled", above ? "" : null);
          if (overflows || shape !== decided)
            keeps(transcript, "data-lf-overflows", overflows ? "" : null);
          decided = shape;
        },
      });
    }
  }
  const placementDriver = floatingPlacement({
    floating: preview,
    update: () => scheduleThreadPreviewPosition(),
  });

  // A placement lands in the microtasks after it starts, before the frame paints. One
  // that cannot land yet — its owner not connected, no room — is answered by a later
  // placement, or by the close that abandons it.
  /** @param {Session} session */
  const placedThreadPreview = (session) => {
    session.positionResult ??= Promise.withResolvers();
    cancelRender(session.positionFrame);
    session.positionFrame = 0;
    placeThreadPreview();
    return session.positionResult.promise;
  };
  // Floating UI follows what moves the card's target: its scroll containers, the window
  // and visual viewport, and the target and card changing size or moving.
  // A card that stays open keeps its spot while its next placement is worked out from
  // nothing it held: the edge it was held by, the frame queued, and any answer in flight
  // are dropped, and the placement rewrites only what moved. A card with no spot yet is
  // unplaced, and chrome.css keeps an unplaced card unseen and out of reach.
  /** @param {Session} session */
  function forgetThreadPreviewPlacement(session) {
    placementDriver.supersede();
    cancelRender(session.positionFrame);
    session.positionFrame = 0;
    session.side.forget();
    session.anchor.forget();
    session.away = false;
  }
  function retirePreviewSession() {
    carry.placed();
    const session = previewSession;
    if (!session) return;
    keeps(preview, "data-lf-grows", null);
    session.positionResult?.resolve(false);
    cancelRender(session.positionFrame);
    placementDriver.supersede();
    session.stopRegion?.();
    preview.style.removeProperty("visibility");
    previewSession = null;
  }
  // A card's focus waits for its placement; a newer input the user gave meanwhile, or
  // focus they took elsewhere, keeps them where they went.
  /** @param {Promise<boolean>} positioned @param {() => void} focus @param {Session} session */
  function deferThreadPreviewFocus(positioned, focus, session) {
    const mayFocus = retainUserIntent();
    const pending = { holding: focused() };
    session.focusPending = pending;
    void positioned?.then((placed) => {
      if (previewSession !== session || session.focusPending !== pending) return;
      session.focusPending = null;
      const holdingGone =
        focused() === document.body &&
        (!pending.holding?.isConnected || !pending.holding?.checkVisibility());
      if (placed && (focused() === pending.holding || holdingGone))
        mayFocus.handoff(focus);
    });
  }

  // Placement supplies the outer bounds; the native tracks share them between
  // reading and writing. A scroll that only carries a fitting card writes nothing;
  // clipped contents receive newly available room without requiring a complete fit.
  /** @param {number} room @param {number} cap @param {Reading | null} reading @param {Session} session */
  function measureThreadCard(room, cap, reading, session) {
    preview.style.setProperty("--lf-thread-width", layoutPx(room));
    const transcript = session.transcript;
    // Growing a top-held card may reveal new words below, but must not reveal lines
    // the reader had already scrolled past. Leave that scroll travel in its transcript.
    // Follow the tail only after this fit, when the available room is known.
    if (reading?.keepTop && transcript)
      cap = Math.min(
        cap,
        preview.offsetHeight + Math.max(0, scrollLimit(transcript) - reading.scroll),
      );
    const worn = parseFloat(preview.style.getPropertyValue("--lf-thread-max-height"));
    const height = preview.offsetHeight;
    const overflow = [
      session.transcript,
      ...previewList.querySelectorAll(REPLY_BOX),
    ].some((box) => box && box.scrollHeight > box.clientHeight + 0.5);
    if (!(worn >= 0) || cap < height - 0.5 || (overflow && cap > height + 0.5))
      preview.style.setProperty("--lf-thread-max-height", layoutPx(cap));
    if (reading?.latest) showArrival(session, reading.transcript);
    else if (reading?.end) scrollToEnd(reading.transcript);
    return preview.getBoundingClientRect().height;
  }
  // A card opens on its first unread turn, else its latest, at that turn's start
  // (`showReturnTurn`). A card Send opened stands
  // its words as far above its end as the box it replaces stood them, which shares
  // its text column and its foot, so the words the user was reading stay where they
  // were.
  /** @param {Session} session @param {HTMLElement} transcript */
  function showArrival(session, transcript) {
    if (!session.sent) return showReturnTurn(transcript, threadCardThread(session));
    scrollToEnd(transcript);
    moveScrollerBy(transcript, -session.sent.fromEnd);
  }
  // The row the card hangs from where its thread has no target to stand by. A row the
  // rail has no room for is withheld and has no box; it stands by the row's target
  // instead, at the row inside it the cluster would stand level with (pointed-place.js).
  /** @param {Session} session @param {Element} control */
  function threadCardCluster(session, control) {
    const row = control.closest("[data-lf-margin-for]") ?? control;
    if (row.checkVisibility()) return row;
    return entryPlace(session.entry) ?? row;
  }
  // The thread the card shows, and the first line of the words it quotes, if it does.
  /** @param {Session} session */
  const threadCardThread = (session) => {
    return session.item.thread;
  };
  // What the card stands by, read as the comment box reads it (comment-placement.js):
  // its target's shown box, or the row a pointing gesture named in it, and the line it
  // stands level with, a quoted passage's first. A thread with no target stands by its
  // cluster.
  /** @param {Session} session @param {Element} control */
  function threadCardPlace(session, control) {
    const target = targetFor(session.entry);
    const point = entryPoint(session.entry);
    if (!target) {
      const cluster = threadCardCluster(session, control);
      const box = cluster.getBoundingClientRect();
      return {
        element: cluster,
        place: {
          element: cluster,
          contextNode: cluster,
          geometry: floatingGeometry([cluster]),
          clear: box,
          extent: box,
          row: box.top,
          lastRow: box.top,
          column: null,
          margin: null,
          scroller: scrollerFor(cluster),
        },
      };
    }
    const thread = threadCardThread(session);
    const words =
      !point && thread?.anchor?.quote ? passageGeometry(placedAt(thread.id)) : null;
    return {
      element: target,
      place: commentAttachment({ target, point, passage: words }),
    };
  }
  const THREAD_SIDES = { right: "right", left: "left", bottom: "below", top: "above" };
  // Feed the shared placement policy the current conversation and native draft;
  // fitting and landing below retain the transcript's reading through that geometry.
  function placeThreadPreview() {
    const session = previewSession;
    if (!session || !session.control?.isConnected) return false;
    const control = session.control;
    const placement = placementDriver.begin();
    /** @type {Reading | null} */
    let reading = null;
    const stillCurrent = () =>
      previewSession === session &&
      placementDriver.current(placement) &&
      session.control?.isConnected;
    const { element, place } = threadCardPlace(session, control);
    // Floating UI follows what moves what the card stands by, so a card with no room yet
    // is placed once something gives it some.
    /** @param {Awaited<ReturnType<typeof floatingUi>>} ui */
    const watch = (ui) =>
      placementDriver.watch(
        element,
        {
          contextElement: element,
          getBoundingClientRect: () => {
            const box =
              threadCardPlace(session, control).place?.clear ??
              element.getBoundingClientRect();
            return new DOMRect(box.left, box.top, box.width, box.height);
          },
        },
        ui.autoUpdate,
      );
    if (!place) {
      if (preview.style.visibility !== "hidden") {
        session.withheldFocus = holdFocus(preview);
        preview.style.visibility = "hidden";
      }
      session.away = true;
      void floatingUi().then((ui) => stillCurrent() && watch(ui));
      return false;
    }
    const boundary = commentBoundary({
      scroller: place.scroller,
      at: { x: place.column ?? place.extent.left, y: place.row },
    });
    session.scroller = place.scroller;
    if (!boundary.width || !boundary.height) {
      void floatingUi().then((ui) => stillCurrent() && watch(ui));
      return false;
    }
    const { scroller } = boundary;
    const seat = session.side.choose({
      clear: place.clear,
      row: place.row,
      column: place.column,
      extent: place.extent,
      boundary,
      scroller,
      coarse: coarsePointer.matches,
    });
    const { side, fresh, opening } = seat;
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        const anchored = session.anchor.prepare(seat);
        const { reference, placement, middleware, plane } = seat.options(ui, {
          clear: place.clear,
          row: place.row,
          lastRow: place.lastRow,
          column: place.column,
          margin: place.margin,
          boundary,
          fit({ width, height, stood, scale, stationary }) {
            if (!stillCurrent()) return;
            // Capture when fitting actually starts, after the module load and any
            // Send landing. Hold this reading through every middleware measurement:
            // an intermediate cap must not turn an earlier offset into end-following.
            const priorReading =
              session.reading?.input === inputCount() ? session.reading : null;
            reading ??= session.transcript && {
              end: !fresh && (priorReading?.end ?? atScrollEnd(session.transcript)),
              scroll: priorReading?.scroll ?? session.transcript.scrollTop,
              keepTop:
                stationary && !fresh && anchored.edge === "top" && !anchored.writing,
              latest: session.arriving,
              transcript: session.transcript,
            };
            if (fresh) session.width = null;
            // A card that has stood keeps its width (`session.width`): its floor and
            // cap are that width, or the room where the room is narrower.
            const room = Math.min(
              cardMeasure(),
              width,
              (session.width ?? Infinity) / scale.x,
            );
            preview.style.setProperty(
              "--lf-thread-min-width",
              layoutPx(session.width === null ? Math.min(cardMinimum(), room) : room),
            );
            // Choosing its spot, the card is capped by the boundary alone, and slides
            // inside it rather than shrinking. Held, it has the room from its held edge
            // to the boundary's far edge, or the tallest it has stood since its line
            // last moved where that is more. Beside its subject, it has the
            // boundary's whole height (`rises`): a growing editor or an arriving
            // answer lifts it from the window's foot, then it scrolls internally.
            const fitted = measureThreadCard(
              room,
              Math.max(stood, height),
              reading,
              session,
            );
            // Fitting the width settles wrapping before opening the card spends
            // scroll travel. A scroll supersedes this answer's attachment geometry.
            if (
              opening &&
              (side === "top" || side === "bottom") &&
              makeRoom(side, place.clear, place.extent, fitted, boundary, scroller)
            ) {
              session.side.scrolled();
              placeThreadPreview();
            }
          },
          edge: anchored.edge,
          rises: anchored.rises,
        });
        watch(ui);
        return placementDriver
          .position(
            ui.computePosition,
            commentReference(place, reference),
            { placement, middleware },
            plane,
            place.element,
          )
          .then((position) => ({ position, anchored }));
      })
      .then((answer) => {
        if (!answer?.position || !stillCurrent()) return;
        const { position, anchored } = answer;
        session.arriving = false;
        session.reading = null;
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale } = session.side.landed(position);
        anchored.commit();
        // An unchanged declaration is the browser's own no-op, and `keeps` is the rest's.
        placementDriver.stand(position);
        session.width ??= preview.getBoundingClientRect().width;
        carry.placed();
        preview.style.removeProperty("visibility");
        session.withheldFocus?.();
        session.withheldFocus = null;
        const card = placementDriver.clientBox(position);
        session.away = card.bottom <= boundary.top || card.top >= boundary.bottom;
        // Leaving with what it is about, the card passes under the chrome, which stacks
        // over it, and a reading region it stands in cuts it at the region's edge as it
        // cuts the words, as does the edge of a block its row has crossed (`cut`). An
        // edge further out than the card paints cuts nothing, and stands at that reach,
        // so a scroll that moves it there writes nothing. Each
        // edge's cut is its own property, which the card's clip and its growth out of
        // the comment box both read (annotation-chrome.css).
        const region = boundary.cut;
        if (region) {
          const cuts = {
            "--lf-cut-top": (region.top - card.top) / scale.y,
            "--lf-cut-right": (card.right - region.right) / scale.x,
            "--lf-cut-bottom": (card.bottom - region.bottom) / scale.y,
            "--lf-cut-left": (region.left - card.left) / scale.x,
          };
          for (const [edge, cut] of Object.entries(cuts))
            preview.style.setProperty(
              edge,
              layoutPx(Math.max(cut, -following.shadowReach())),
            );
        } else for (const edge of CUT_EDGES) preview.style.removeProperty(edge);
        keeps(preview, "data-lf-thread-placement", THREAD_SIDES[side]);
        // The card's first spot is the first reading its motion follows from. A card
        // Send opened grows out of the field it replaces, as any box's outline travels
        // (box-motion.js): the box paints only its field while it is written, and the
        // user preferred (19 October) a field that opens into its card at Send to a box
        // painted as the card throughout (#3157). The card stands whole under its
        // outline from the first frame, so no word moves.
        if (!session.followed) {
          session.followed = true;
          if (session.sent) following.drawnAt(session.sent.field);
          followCard();
        }
        keepThreadLanding(previewList.querySelector(".lf-page-thread"));
        session.positionResult?.resolve(true);
        session.positionResult = null;
      })
      .catch((error) => {
        // A card Floating UI cannot place would stand open and unseen, so it closes, as
        // the comment box withdraws, and the failure surfaces.
        if (stillCurrent()) close();
        throw error;
      });
    return true;
  }
  function scheduleThreadPreviewPosition() {
    const session = previewSession;
    if (!session || session.positionFrame || preview.hasAttribute("data-lf-carried"))
      return;
    session.positionFrame = nextRender(() => {
      session.positionFrame = 0;
      if (previewSession === session) placeThreadPreview();
    });
  }
  // The card hangs from another entry, and a user on the entry it hung from goes
  // with it: the same place, the thread's own entry, under a new control.
  /** @param {Element | null} button @param {boolean} [carry] */
  function transferThreadCard(button, carry = focused() === previewSession?.control) {
    if (previewSession?.control === button) return;
    const session = previewSession;
    if (!session) return;
    forgetThreadPreviewPlacement(session);
    session.control = button;
    if (carry && button) focusDestination(button, "return");
  }

  /** @param {Omit<Selection, "threadItem"> & {item: Item, origin?: Origin | null}} chosen @returns {Session} */
  function select({
    entry,
    choice,
    item,
    control,
    origin,
    accompanies,
    forced = false,
    disclosed = false,
  }) {
    retirePreviewSession();
    /** @type {Session} */
    const session = {
      entry,
      choice,
      item,
      threadItem: item.id,
      control,
      accompanies,
      forced,
      disclosed,
      preparing: false,
      latest: null,
      arriving: true,
      // The box Send replaced, whose reading the card keeps (`showArrival`) and whose
      // field it grows out of (`followCard`).
      sent: origin ? { fromEnd: origin.fromEnd, field: origin.field } : null,
      away: false,
      positionFrame: 0,
      positionResult: null,
      focusPending: null,
      withheldFocus: null,
      transcript: null,
      place: null,
      reading: null,
      stopRegion: null,
      side: commentPlacement(),
      anchor: new CardAnchor(preview),
      // The width the card stands at for this selection, in client pixels: the box's
      // Send replaced, so the two are one rectangle, else the one it first stood at, or
      // was carried at (`placeThreadPreview`). Sized by itself, Firefox stood a one-line
      // comment's card 13px wider than its box.
      itemView: null,
      width: origin?.box.width ?? null,
      scroller: pageScroller,
      // Whether the card's motion has read the card at its first spot (`followCard`).
      followed: false,
    };
    previewSession = session;
    if (origin) session.side.adopt(origin);
    // A card Send opened stands at once where its box stood and grows out of the box's
    // field, rather than fade in (annotation-chrome.css).
    keeps(preview, "data-lf-grows", origin ? "" : null);
    return session;
  }

  /** @param {Entry} entry @param {Choice} choice @param {Session} current @param {string | null} [requestedItem] */
  function buildThreadCard(entry, choice, current, requestedItem = null) {
    const restoreFocus = holdFocus(preview);
    const focusedItem = restoreFocus
      ? (focused(document)
          ?.closest?.("[data-lf-margin-entry]")
          ?.getAttribute("data-lf-margin-entry") ?? null)
      : null;
    const threadItems = choice.items;
    const wanted = requestedItem ?? current.threadItem ?? focusedItem;
    const selected = threadItems.find((item) => item.id === wanted) ?? threadItems[0];
    const arriving = current.threadItem !== selected.id || !current.transcript;
    const session =
      arriving && current.threadItem !== selected.id
        ? select({ ...current, entry, choice, item: selected })
        : current;
    Object.assign(session, { entry, choice, item: selected });
    const latest = turns(selected.thread).at(-1);
    const messageSelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-transcript > .lf-msg";
    const replySelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-reply";
    const lastShown = [...previewList.querySelectorAll(messageSelector)].findLast(
      (node) => showsContents(node),
    );
    const lastBox = lastShown?.getBoundingClientRect();
    const followTranscript = session.transcript;
    const listBox = followTranscript?.getBoundingClientRect();
    const replyBox = previewList.querySelector(replySelector)?.getBoundingClientRect();
    const follow =
      !arriving &&
      session.latest &&
      latest?.author === "agent" &&
      (latest.id !== session.latest.id || latest.text !== session.latest.text) &&
      lastBox &&
      listBox &&
      lastBox.bottom >= listBox.top &&
      lastBox.bottom <= (replyBox?.top ?? listBox.bottom) + 80 &&
      followTranscript &&
      atScrollEnd(followTranscript)
        ? followTranscript
        : null;
    session.reading = session.transcript && {
      input: inputCount(),
      scroll: session.transcript.scrollTop,
      end: Boolean(follow),
    };
    const present = () => {
      const targetHeading =
        targetFor(entry)?.querySelector(":scope > strong")?.textContent;
      // A target with a heading is named by it. One without — an aside, a paragraph —
      // is headed by the passage the selected thread quotes, as the panel heads it: a card
      // headed "aside · The fallback cookie is read-only…" over a comment on the aside's
      // last sentence was a third name for one thread, and the least exact.
      const quoted = selected.thread?.anchor
        ? anchorLabel(selected.thread.anchor, selected.thread.root.about)
        : null;
      const title = labelWords(targetHeading || quoted || entry.title);
      keeps(preview, "aria-label", `Thread for ${spokenSubject(title)}`);
      keepsHidden(previewNav, threadItems.length < 2);
      const selectedIndex = Math.max(0, threadItems.indexOf(selected));
      // Every other walk says "1 of 3" (walk-position.js). This one stands on the card's
      // actions line, which on a 311px phone already leaves the message heads no room;
      // " of " made it 12px wider, which pushed the actions past the card's start.
      keepsText(previewPosition, `${selectedIndex + 1}/${threadItems.length}`);
      previewPrevious.toggleAttribute("disabled", selectedIndex === 0);
      previewNext.toggleAttribute("disabled", selectedIndex === threadItems.length - 1);
      const item = previewItemNode(selected, session);
      setChildren(previewList, [item.node]);
      // The thread renders before the card shows it, and takes the reply being written
      // in it once it stands in the document (thread/inline.js, `claimSeatReplies`).
      claimSeatReplies(item.body);
      // The list holds the one thread the card shows, so a user whose place in a thread
      // the rebuild took lands on that thread; a step button it hid hands them to Close.
      restoreFocus?.(
        focusedItem ? previewList.querySelector(".lf-page-thread") : null,
        previewClose,
      );
    };
    if (!arriving && session.place) session.place.around(present);
    else {
      present();
      const transcript = session.transcript;
      session.arriving = transcript !== null;
      if (transcript) showArrival(session, transcript);
    }
    session.latest = latest ? { id: latest.id, text: latest.text } : null;
  }

  /** @param {number} step */
  function stepPreviewThread(step) {
    if (!previewSession) return;
    const session = previewSession;
    if (!session) return;
    const threadItems = session.choice.items;
    const current = threadItems.findIndex((item) => item.id === session.threadItem);
    const next = Math.max(0, Math.min(threadItems.length - 1, current + step));
    const item = threadItems[next];
    if (next === current || !item) return;
    void openPageThread(item.thread.id, { part: "thread" });
  }
  /** @param {Item} item @param {Session} session */
  function previewItemNode(item, session) {
    let view = session.itemView;
    if (!view) {
      const node = el("section", "lf-margin-thread");
      const body = el("div", "lf-margin-thread-body");
      node.append(body);
      view = { node, body };
      session.itemView = view;
    }
    const { node, body } = view;
    const shownThread = item.thread;
    // The panel's view carries the reply being written along from the closed card
    // (thread/replies.js, `carry`).
    previewOpenInPanel.onclick = () => {
      dismiss();
      openInPanel(shownThread.id);
    };
    const rendered = renderMarginThread(body, shownThread, {
      nav: previewNav.hidden ? null : previewNav,
      expand: previewOpenInPanel,
      close: previewClose,
      anchor: session.anchor,
      // A send from the card is the user's change joining the stream the card shows
      // (box-motion.js, "send"), read before the send draws.
      sending: following.stream,
      // A resolved thread with no draft has no margin card, so resolving closes it and
      // hands the user to its target.
      prepareLanding: () => {
        const target = targetFor(previewSession?.entry);
        if (!target) return () => false;
        const mayLand = retainUserIntent({
          source: focused(),
          available: () => Boolean(target?.isConnected),
        });
        return () => {
          if (previewOpen()) return false;
          return mayLand.handoff(() => focusDestination(target, "return"));
        };
      },
    });
    keeps(node, "data-lf-margin-entry", item.id);
    for (const reading of rendered) syncPreviewTranscript(session, reading);
    return view;
  }

  // The card's threads the margin no longer holds give up the reply being written in
  // them, whether the card is open or closed (thread/replies.js, `releaseReplies`). A
  // thread still in the margin keeps it, for the card to show again.
  /** @param {Set<string>} items */
  function releaseLeft(items) {
    for (const node of previewList.children)
      if (!items.has(node.getAttribute("data-lf-margin-entry") ?? ""))
        releaseReplies(node);
  }

  function selection() {
    if (!previewSession) return null;
    const { entry, choice, threadItem, control, accompanies, forced, disclosed } =
      previewSession;
    return Object.freeze({
      entry,
      choice,
      threadItem,
      control,
      accompanies,
      forced,
      disclosed,
    });
  }

  /** @param {{entry: Entry, choice: Choice, threadItem?: string | null, control?: Element | null, origin?: Origin | null, accompanies?: boolean, forced?: boolean, disclosed?: boolean, prepare?: (() => Element | null) | null}} options */
  function show({
    entry,
    choice,
    threadItem = null,
    control = null,
    origin = null,
    accompanies = false,
    forced = false,
    disclosed = false,
    prepare = null,
  }) {
    const items = choice.items;
    const selected = items.find((item) => item.id === threadItem) ?? items[0];
    const current = previewSession;
    const session =
      current && current.entry.key === entry.key && current.threadItem === selected.id
        ? current
        : select({
            entry,
            item: selected,
            choice,
            control,
            origin,
            accompanies,
            forced,
            disclosed,
          });
    Object.assign(session, { entry, accompanies, forced, disclosed, preparing: true });
    let preparedControl;
    try {
      preparedControl = prepare ? prepare() : control;
    } finally {
      session.preparing = false;
    }
    if (previewSession !== session) return null;
    transferThreadCard(preparedControl);
    if (!session.control?.isConnected) {
      close();
      return null;
    }
    keepsHidden(preview, false);
    keeps(preview, "inert", null);
    buildThreadCard(entry, choice, session, selected.id);
    const positioned = placedThreadPreview(session);
    paintKeysWithin(preview);
    return positioned;
  }

  /** @param {Entry} entry @param {Choice} choice @param {Element | null} control @param {boolean} [carry] */
  function refresh(
    entry,
    choice,
    control,
    carry = focused() === previewSession?.control,
  ) {
    if (!previewSession || previewSession.preparing) return;
    transferThreadCard(control, carry);
    buildThreadCard(entry, choice, previewSession);
    placeThreadPreview();
  }

  function close() {
    if (!previewSession) return;
    const closed = selection();
    retirePreviewSession();
    // Unplaced, the card fades out where it stood (annotation-chrome.css), inert, and
    // hides once the fade ends, unless a card opened meanwhile. Its placement holds it
    // there until then.
    placementDriver.supersede();
    delete preview.dataset.lfThreadPlacement;
    const hide = () => {
      if (previewSession) return;
      placementDriver.stop();
      for (const edge of CUT_EDGES) preview.style.removeProperty(edge);
      keepsHidden(preview, true);
      keeps(preview, "inert", null);
      // Rows inside the retained card can read whether its reply box is shown.
      // Hiding after the fade is later than the focus move that closed the card.
      paintKeysWithin(preview);
    };
    const fade = preview.hidden
      ? null
      : preview
          .getAnimations()
          .find(
            (played) =>
              played instanceof CSSTransition &&
              played.transitionProperty === "opacity",
          );
    if (fade) {
      keeps(preview, "inert", "");
      fade.finished.then(hide, hide);
    } else hide();
    // The widgets of a reply the card held go back to another drawing of it.
    releaseAuthoredUnder(preview);
    onClose(closed);
  }

  /** @param {Promise<boolean> | null} positioned @param {{closeControl?: boolean, cause?: import("../focus.js").PlacementCause}} [options] */
  function focusThread(positioned, { closeControl = false, cause = "move" } = {}) {
    if (!positioned) return;
    const session = previewSession;
    if (!session) return;
    deferThreadPreviewFocus(
      positioned,
      () => {
        const target = closeControl
          ? previewClose
          : previewList.querySelector(".lf-page-thread");
        if (!target) return;
        focusDestination(target, cause);
        if (!closeControl) scrollThreadIntoView(target, target);
      },
      session,
    );
  }

  /** @param {string} name @param {{part?: import("../thread/destination.js").ThreadPart}} [options] */
  function focusTarget(name, { part = null } = {}) {
    const id = threadIdNamed(name);
    const thread = [...previewList.querySelectorAll(".lf-page-thread")].find(
      (candidate) => candidate.getAttribute("data-thread") === id,
    );
    return thread
      ? threadFocusDestination(thread, { part: part ?? "thread", message: name })
      : null;
  }

  /** @param {() => void} onDismiss */
  function mount(onDismiss) {
    dismiss = onDismiss;
    previewClose.onclick = onDismiss;
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    onCurrentLocation((node, cause, left) => {
      if (
        node &&
        under(node, preview) &&
        closestAcross(node, ".lf-thread-reply") &&
        cause !== "return" &&
        cause !== "drop"
      ) {
        previewSession?.anchor.writing();
        scheduleThreadPreviewPosition();
      }
      const row =
        left && under(left, preview) && closestAcross(left, ".lf-thread-reply");
      /** @type {HTMLTextAreaElement | null} */
      const field = row ? row.querySelector(REPLY_BOX) : null;
      if (row && !(node && under(node, row)) && !field?.value)
        scheduleThreadPreviewPosition();
    });
    declareOffFlowSurface(preview, {
      bringBack: (behavior) =>
        scrollToElement(
          entryPlace(previewSession?.entry) ?? previewSession?.control ?? null,
          behavior,
          "nearest",
        ),
    });
    move(chromeRoot, preview, chromeForeground);
    previewRegionMounted = true;
    if (previewSession?.itemView) previewItemNode(previewSession.item, previewSession);
  }

  return {
    element: preview,
    isOpen: previewOpen,
    selection,
    show,
    refresh,
    releaseLeft,
    close,
    focusThread,
    focusTarget,
    openerKeys,
    thread: () => previewList.querySelector(".lf-page-thread"),
    accompanied: () =>
      previewSession && !previewSession.away
        ? previewList.querySelector(".lf-page-thread")
        : null,
    closeFocused: () => focused() === previewClose,
    // Whether the user is in the card's reply box.
    replying: () =>
      under(focused(), preview) && Boolean(closestAcross(focused(), REPLY_BOX)),
    // Whether the open card has a placement (`threadCardPlace`).
    hasPlacement: () => {
      const session = previewSession;
      return Boolean(
        session?.control && threadCardPlace(session, session.control).place,
      );
    },
    place: placeThreadPreview,
    schedulePosition: scheduleThreadPreviewPosition,
    mount,
  };
}
