/* Contextual thread preview: a card with a nested conversation lifetime.

   One Floating UI driver follows this card across conversation changes and stops
   when the card closes. Each selected conversation owns its originating control,
   reading region, pending placement/focus, and growth out of the comment box Send
   replaced (`sent`). Replacing it retires that work before margin
   preparation can synchronously render again.
   A retained refresh preserves the selection's reading and draft continuity.
   Margin disclosure remains the margin's; selection records only whether a walk
   opened a cluster so its end can return that disclosure.

   The card opens only on a window with room for the rail: on one without, its thread
   opens in the floating panel (margin-projection.js, `showPreview`), and nothing here
   places a card for a narrow window.

   ThreadView owns conversation rendering; comment-placement.js owns the side,
   frame adoption and opening-scroll policy. Floating UI follows the attachment within
   the reading region or viewport, under the chrome; regions clip it at their edges. A
   scroll never closes the card: it leaves with its target and comes back with it. A
   target hidden by the document withholds the card's native draft and focus until it
   is drawn again.

   As it grows, the card holds the edge it is attached by (comment-placement.js,
   `attachedEdge`): its foot above its subject, so it grows up over its transcript and
   leaves the words the thread is about in view, and its top beside or below it. Beside
   its subject it also rises (`rises`; `size-rises` in placement-rules.json): it may
   outgrow the room below its top, and the window's foot lifts it, so an answer
   arriving stays in view with the turn it answers, and its top stays where it stood,
   so a shorter thread brings it back down. News lifts it from under no control of its
   head or transcript the user is on, by focus or a resting pointer: that news waits
   behind the thread's notice (`endNewsMoves`), since the lift left Resolve's place to
   a reply's own presses under a pointer that hadn't moved. While the user writes words in its reply
   box (user-place.js, `focusPlace`), a card beside its subject holds its foot instead,
   as one above it does: the line being typed stays still as the conversation grows
   above it. A send empties the box, so the card holds its top through the send and
   grows down past the box, keeping still the transcript the user was reading; so does
   the empty box a click's opening leaves the caret in (thread/focus.js,
   `openingPart`). A user who empties the box themselves, as Select All and Backspace
   do, sees it rise to where the empty box stands, a rare path SOUL.md lets move, since
   to the card that looks the same as a send. A message's rewrite, whose field stands in
   the transcript, holds the top as well, so the rewrite grows down. Below its subject
   the card keeps its top even while the user writes, so it never grows up over the
   words it is about.
   Nothing else chooses the edge, whatever the user pressed, and the card remembers no
   press or send (`heldEdge`). News at the thread's end shows at once where that edge
   keeps still what the user is on, and waits otherwise (`endNewsMoves`;
   thread-card.js, `newsMoves`).

   The user chose this rule on 5 November 2026 as the platform's: CSS scroll anchoring
   prefers a focused text field or the find match as the node it keeps still, and
   neither it nor Floating UI holds a pressed control. On 9 November they asked for a
   send to grow the card down: holding the foot whenever the caret was in the box
   lifted the whole transcript at each send, and an empty box has no typed line to keep
   still. Rejected: keeping a pressed
   control under the pointer (thread/card-anchor.js, which remembered each press until
   the change it caused had fitted, and each send until the next words arrived), which
   tied the card's layout to every gesture's lifetime; and the attached edge with no
   exception for typing, under which an answer arriving while the user typed in a card
   beside its words waited behind the thread's notice. The rule
   replaces the card rising beside its subject as the user writes (2026-10-21). It
   keeps two earlier choices: the foot above the subject (2026-10-31), over keeping a
   written card's top there, which grew the draft down over its subject; and rising
   beside it for an answer (2026-10-31), over keeping a read card's top, which scrolled
   the transcript once the card met the window's foot and hid the question above the
   answer. Rising ends at the room's height. Past it, the thread keeps the user's turn
   in sight and says New reply at the transcript's foot (thread-card.js), as the
   floating panel does; that was done on 4 November 2026 to unify the two under the
   user's request for one thread view, and the user did not pick it.

   A selection holds its placement side and its width. A card is as wide as the
   measure, or its room where that is narrower (`size-width`), so a longer line
   arriving wraps inside it rather than carrying the controls at its far edge. Where
   Send opened it, it keeps the comment box's width, and where the user carried it, the
   width it was carried at; only a narrower room narrows it. The user chose the measure
   (2026-11-14) over a card as wide as its first words, kept while it was open, which
   left the card a short comment's Send opened 320px wide while a long answer wrapped
   inside it.
   Another selection chooses afresh. Floating UI supplies room from the held edge; native
   grid tracks share it between transcript and reply, growing to their words before
   scrolling. Reply continuity retains removed turns as flexible space and lets the
   transcript yield writing room without losing the visible lines.

   Placement changes geometry, never rebuilds contents. Retained state reads hold the
   reader's message and scroll position; another thread opens at its first unread
   message, else its latest, and the thread a comment's Send opened where the box's
   words stood (`showArrival`).
   A reader at the transcript's end follows it, whatever moves it: a turn drawn or
   growing, as a picture in it loads, or the room the card gives it; a reader read back
   stays where they are (scrolling.js, `followEnd`). The user asked for that one keeper
   on 10 November 2026, replacing two partial ones: one kept the end through a change of
   room, the fit followed the growth a reading of the thread drew, and growth after a
   reading, such as a picture loading, reached neither. An answer to the user's own turn
   instead stays the thread's to place (`answering`), by the floating panel's rule: their
   turn stays in sight above it, and New reply stands at the transcript's foot where it
   runs past, or where they had read back. An opening that leaves a reply unread offers
   Next unread on the head line. The thread draws both (thread-card.js): the card names
   its transcript as the box scrolling the thread, and tells the thread it stands each
   time a placement lands (`settled`). Landing, Send and stepping may move the reading;
   keepThreadLanding retains their destination through fitting until a newer reading
   gesture or an answer ends that authority. Size is fitted before paint, so a sent reply
   does not grow twice. Margin location and its keyboard ladder own dismissal
   and target landing; the card keeps Send's focus on the thread that received it.

   Resolve moves the card on to the next open thread at its passage, the one after the
   resolved thread in the card's count ("1/3"), else the one before, and stands the user
   on it, so the page never moves; at a passage with no other thread the card closes
   and leaves the user on its target (`landing`). Undo opens the thread again in the
   card where it was resolved (undo.js, the page's reader). The user chose this on 4
   November 2026 over closing the card onto its passage whatever else stood there, which
   left the card and the floating panel doing different things, and over moving on to
   the next open thread on the page, as the panel does, which scrolls the page under the
   user after each Resolve.

   A step to another thread at the passage, by Resolve, Previous or Next, places the card
   afresh, so a shorter thread brings it back beside its passage, with the controls on
   its head line. The user chose this on 4 November 2026 over keeping the frame it stood
   in, which held ✓ under a pointer resolving several threads in a row but took a
   placement rule and a press hold of its own, and still moved ✓ on a card above its
   subject. */
import {
  followEnd,
  moveScrollerBy,
  pageScroller,
  scrollToEnd,
  scrollLimit,
} from "../scrolling.js";
import { signal } from "/runtime/framework.js";
import { tick } from "../version-signal.js";
import { afterScript, cancelRender, nextRender } from "../rendering.js";
import { spokenSubject } from "../contribution-model.js";
import { labelWords } from "../words.js";
import { THREAD_CARD } from "./margin-layout.js";
import { slotTop } from "../geometry.js";
import {
  focusDestination,
  holdFocus,
  inputCount,
  onCurrentLocation,
  openLayer,
  focused,
  tabStops,
  typesText,
} from "../focus.js";
import { aimedControls, focusPlace } from "../user-place.js";
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
import { drawnThreadsWithId } from "../thread/selectors.js";
import { threadIdNamed } from "../thread/state.js";
import { threadKey } from "../thread/model.js";
import { anchorLabel, releaseAuthoredUnder } from "../thread/messages.js";
import { coarsePointer } from "../pointer.js";
import {
  attachedEdge,
  cardMeasure,
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
  makeRoom,
} from "./comment-placement.js";
import { passageGeometry } from "../resolved-target.js";
import { floatingPlacement, floatingUi, floatingGeometry } from "./floating.js";
import { surfaceGrip } from "./surface-grip.js";
import { renderedOrder, renderedUnder, under } from "../shadow.js";
import { keys } from "../keyboard/scopes.js";
import { retainUserIntent } from "../user-intent.js";
import { openingPart, threadFocusDestination } from "../thread/focus.js";
import { claimSeatReplies } from "../thread/inline.js";
import { dismissReply, releaseReplies, replyIsEditing } from "../thread/replies.js";
import { keepThreadLanding, showReturnTurn } from "../thread/reply-landing.js";

/** @typedef {import("../annotation-inventory.js").InventoryEntry} Entry
 * @typedef {import("../margin-model.js").ThreadItem} Item
 * @typedef {import("../margin-model.js").ThreadChoice} Choice
 * @typedef {import("../thread/workflow.js").ThreadRecord} ThreadRecord
 * @typedef {NonNullable<ReturnType<ReturnType<typeof import("./composing/floating-response.js").createFloatingResponsePlacement>["frame"]>>} Origin
 * @typedef {{entry: Entry, choice: Choice, threadItem: string, control: Element | null,
 * accompanies: boolean, forced: boolean, disclosed: boolean}} Selection
 * @typedef {Selection & {item: Item, preparing: boolean,
 * arriving: boolean, sent: Pick<Origin, "fromEnd" | "field"> | null, away: boolean,
 * positionFrame: number, positionResult: PromiseWithResolvers<boolean> | null,
 * focusPending: {holding: Element | null} | null, withheldFocus: ReturnType<typeof holdFocus>,
 * transcript: HTMLElement | null, settled: (() => void) | null, answering: (() => boolean) | null,
 * placesEnd: ((before: import("../scrolling.js").BoxExtent) => boolean) | null,
 * gutter: (() => void) | null, stopRegion: (() => void) | null, stopDraw: (() => void) | null, end: import("../scrolling.js").EndKeeper | null, side: ReturnType<typeof commentPlacement>,
 * reading: {input: number, scroll: number} | null, itemView: {node: HTMLElement, body: HTMLElement} | null, width: number | null, scroller: Element, followed: boolean}} Session
 * @typedef {{latest: boolean, scroll: number, keepTop: boolean, transcript: HTMLElement}} Reading
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
 * renderMarginThread: (host: HTMLElement, thread: ThreadRecord, outlets: import("../thread/thread-card.js").ViewOutlets) => {drawn: ReturnType<typeof import("../thread/inline.js").renderMarginThread>, stop: () => void},
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
  // The entry the card hangs from changes as the card opens, closes or moves to another
  // entry, which a row asking whether the user is on that entry reads through this
  // revision, as it reads where the user is through focus.js's (`onOpener`).
  const cardRevision = signal(0);
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
  // The card's head line: the thread's notice of held news and Next unread, Previous and
  // Next, Open in panel, the thread's Resolve or Reopen, and Close. It stands in the
  // thread, over its first message's head, whose track it shares (annotation-chrome.css),
  // and holds the boxes the thread draws its notice, Next unread and its settlement in
  // (thread-card.js, `CardOutlets`, `line`).
  const previewHead = el("div", "lf-margin-thread-controls");
  const previewActions = el("span", "lf-thread-meta-actions");
  previewHead.append(previewActions);
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
  // in the plane its placement stands it in, by the edges that hold it there, so a
  // scroll or a carry that moves it whole moves nothing in it, and a change of its size
  // asks for its placement first (box-motion.js, `placed`). A card no placement stands
  // yet, or put away, has nothing to move from, and one being carried stands where the
  // pointer holds it. A card closing stands where its placement left it until its fade
  // ends (`close`), so the card another thread opens meanwhile travels from there.
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
    placement: {
      held: () => placementDriver.held(),
      place: () => {
        const session = previewSession;
        return (
          session !== null &&
          preview.hasAttribute("data-lf-thread-placement") &&
          !preview.hasAttribute("data-lf-carried") &&
          placeNow(session)
        );
      },
    },
  });
  preview.append(following.ground, carry.grip, face);
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
  // Whether the user is on the entry the card hangs from, which the margin's keys ask
  // (`openerKeys`). Reading `cardRevision` keeps their reflection current as the card
  // opens, closes or moves while focus stays where it is.
  const onOpener = () => {
    void cardRevision.value;
    const target = opener();
    return Boolean(target) && focused() === target;
  };
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
      run: () => {
        const target = opener();
        if (target) focusDestination(target, "step");
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
      run: () => {
        const target = opener();
        if (target) focusDestination(target, "return");
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
      run: () => {
        const [target] = tabStops(preview);
        if (target) focusDestination(target, "step");
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
        const target = onOpener() ? opener() : null;
        return (
          target !== null && under(stopsBeside(chromeRoot, target, -1).at(-1), preview)
        );
      },
      run: () => focusDestination(preview, "return"),
    },
  ];
  let previewRegionMounted = false;
  // The card's transcript is re-rendered on every reading of its thread.
  /** @param {Session} session @param {ReturnType<typeof import("../thread/inline.js").renderMarginThread>[number]} reading */
  function syncPreviewTranscript(
    session,
    { thread: card, transcript, settled, answering, placesEnd },
  ) {
    session.settled = settled;
    session.answering = answering;
    session.placesEnd = placesEnd;
    if (transcript === session.transcript) return;
    session.stopRegion?.();
    session.stopRegion = null;
    session.transcript = transcript;
    // The card scrolls its transcript, which grows only at its end (browser/AGENTS.md,
    // `data-lf-reflow`).
    if (transcript) keeps(transcript, "data-lf-reflow", "append");
    // A reader at the transcript's end stays there, whatever moves the end: the reply
    // box taking room or giving it back, a fit, a turn drawn or growing. One read back
    // keeps their offset, as the card hangs from its passage (scrolling.js,
    // `followEnd`). The end is another's to place while the card arrives on its opening
    // turn (`showArrival`), and where the thread places an answer to the user's turn
    // (thread-card.js, `placesEnd`).
    session.end?.stop();
    session.end = transcript
      ? followEnd(
          transcript,
          (before) => session.arriving || Boolean(session.placesEnd?.(before)),
        )
      : null;
    session.gutter = null;
    if (previewRegionMounted && transcript) {
      // Once its turns overflow, the transcript holds its scrollbar's gutter
      // (`data-lf-overflows`, annotation-chrome.css) until its width or the number of
      // turns it shows changes. The gutter narrows the turns, and a narrowed picture is
      // shorter, so turns can overflow without the gutter and fit with it: dropping the
      // gutter whenever they fit brought it back the next frame, and so on every frame.
      // A transcript that stops overflowing otherwise, as when the window grows taller
      // or the reply box empties, keeps its words the gutter's width narrower until
      // then. A send's ride draws the turns below where they stand, which the browser
      // counts as overflow, so the decision reads where layout stands them
      // (`scrollLimit`).
      // The gutter resizes the transcript's box, so the card's fit decides it in the
      // script that changes the card's room (`measureThreadCard`), before the size
      // delivery that reports the transcript; the paint below decides it for a change
      // no fit answers.
      // The transcript's width and shown turns when its gutter was last decided.
      let decided = "";
      const gutter = () => {
        const shown = [...transcript.querySelectorAll(":scope > .lf-msg")].filter(
          (message) => !(/** @type {HTMLElement} */ (message).hidden),
        ).length;
        const overflows = scrollLimit(transcript) > 0;
        const shape = `${transcript.offsetWidth} ${shown}`;
        if (overflows || shape !== decided)
          keeps(transcript, "data-lf-overflows", overflows ? "" : null);
        decided = shape;
      };
      session.gutter = gutter;
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
          /** @type {NodeListOf<HTMLElement>} */
          const messages = transcript.querySelectorAll(":scope > .lf-msg");
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
          gutter();
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
    placeNow(session);
    return session.positionResult.promise;
  };
  // Places the card now, in place of any placement a frame has queued.
  /** @param {Session} session */
  function placeNow(session) {
    cancelRender(session.positionFrame);
    session.positionFrame = 0;
    return placeThreadPreview();
  }
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
    session.stopDraw?.();
    session.end?.stop();
    preview.style.removeProperty("visibility");
    previewSession = null;
    tick(cardRevision);
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

  // The edge a card on `side` holds now (the header's rule): the one it is attached by,
  // but its foot beside its subject while the user writes words in its reply box, where
  // they are (user-place.js, `focusPlace`). Also where they are, if in the card, and
  // whether they type there.
  /** @param {import("./comment-placement.js").Side} side */
  function heldEdge(side) {
    const place = focusPlace();
    const at = place && under(place, preview) ? place : null;
    const typing = typesText(at);
    const words = closestAcross(at, ".lf-thread-reply")?.querySelector(TEXT_FIELD);
    const writing = typing && Boolean(words && "value" in words && words.value);
    const beside = side === "left" || side === "right";
    /** @type {"top" | "foot"} */
    const edge = writing && beside ? "foot" : attachedEdge(side);
    return { edge, typing, at };
  }

  // Whether news at the thread's end, which grows the card at the edge it does not
  // hold, would move what the user is on (thread-card.js, `newsMoves`). Held by its top,
  // the card grows down past its reply row, which the user is on while they write a
  // reply there (replies.js, `replyIsEditing`), not while the caret only rests in the
  // empty box a send or an opening left, so the answer they wait for shows. Held by its
  // foot, it grows up under the head and transcript, which the user is on unless they
  // are in the reply row. A control of the head or transcript the user is on, by focus
  // or a resting pointer (user-place.js, `aimedControls`), is carried by that growth,
  // and beside its subject by the card's rise too, whichever edge it holds.
  /** @param {Session} session */
  function endNewsMoves(session) {
    const { side } = session.side.capture();
    if (!side) return false;
    const { edge, at } = heldEdge(side);
    const inReply = Boolean(at && closestAcross(at, ".lf-thread-reply"));
    const above = aimedControls().some(
      (control) =>
        renderedUnder(control, preview) && !closestAcross(control, ".lf-thread-reply"),
    );
    if (edge === "foot") return !inReply || above;
    return (
      (inReply && replyIsEditing(threadKey(session.item.thread))) ||
      (above && (side === "left" || side === "right"))
    );
  }

  // Placement supplies the outer bounds; the native tracks share them between
  // reading and writing. A scroll that only carries a fitting card writes nothing;
  // clipped contents receive newly available room without requiring a complete fit.
  /** @param {number} room @param {number} cap @param {Reading | null} reading @param {Session} session */
  function measureThreadCard(room, cap, reading, session) {
    preview.style.setProperty("width", layoutPx(room));
    const transcript = session.transcript;
    // Growing a top-held card may reveal new words below, but must not reveal lines
    // the reader had already scrolled past. Leave that scroll travel in its transcript.
    // Follow the tail only after this fit, when the available room is known.
    if (reading?.keepTop && transcript)
      cap = Math.min(
        cap,
        preview.offsetHeight + Math.max(0, scrollLimit(transcript) - reading.scroll),
      );
    const worn = parseFloat(preview.style.getPropertyValue("max-height"));
    const height = preview.offsetHeight;
    const overflow = [
      session.transcript,
      ...previewList.querySelectorAll(REPLY_BOX),
    ].some((box) => box && box.scrollHeight > box.clientHeight + 0.5);
    if (!(worn >= 0) || cap < height - 0.5 || (overflow && cap > height + 0.5))
      preview.style.setProperty("max-height", layoutPx(cap));
    session.gutter?.();
    // A reader at the end stays there through this fit by the transcript's own keeper
    // (`syncPreviewTranscript`).
    if (reading?.latest) showArrival(session, reading.transcript);
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
    const place = commentAttachment({ target, point, passage: words });
    // Floating UI follows the scrollers around what the card stands by, so a card on a
    // row deep in a target follows the box that scrolls that row, not only the target's.
    return { element: place?.element ?? target, place };
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
        // Adoption keeps the editor's attachment, so the card Send grows out of the
        // box stands where it stood. Otherwise the card holds the edge the header's rule
        // names, rising beside its subject where that is its top.
        const held = heldEdge(side);
        const edge = seat.adopted ? attachedEdge(side) : held.edge;
        const rises =
          !seat.adopted && edge === "top" && (side === "left" || side === "right");
        // Held by its foot, or rising, the card's growth lifts its head, which news
        // may do here as in the floating panel's thread view (tests/shift_watch.js,
        // `appendGrowth`).
        keeps(preview, "data-lf-rises", edge === "foot" || rises ? "" : null);
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
              scroll: priorReading?.scroll ?? session.transcript.scrollTop,
              keepTop: stationary && !fresh && edge === "top" && !held.typing,
              latest: session.arriving,
              transcript: session.transcript,
            };
            if (fresh) session.width = null;
            // A card is as wide as the measure, or its room where the room is
            // narrower, whatever its messages hold, so no message that arrives or is
            // typed changes its width and moves its controls. One that Send opened or
            // the user carried keeps that box's width (`session.width`) until its side
            // is chosen again, or the room where the room is narrower.
            const room = Math.min(
              cardMeasure(),
              width,
              (session.width ?? Infinity) / scale.x,
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
          edge,
          rises,
        });
        watch(ui);
        return placementDriver.position(
          ui.computePosition,
          commentReference(place, reference),
          { placement, middleware },
          plane,
          place.element,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        session.arriving = false;
        session.reading = null;
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale } = session.side.landed(position);
        // The card's first spot is the first reading its motion follows from. The card
        // another thread opens travels there from where the last one stood
        // (box-motion.js, `placed`). A card Send opened grows out of the field it
        // replaces, as any box's outline travels: the box paints only its field while
        // it is written, and the user preferred (19 October) a field that opens into
        // its card at Send to a box painted as the card throughout (#3157). The card
        // stands whole under its outline from the first frame, so no word moves.
        const anew = !session.followed;
        if (anew) {
          session.followed = true;
          if (session.sent) following.drawnAt(session.sent.field);
        }
        // An unchanged declaration is the browser's own no-op, and `keeps` is the rest's.
        // A drag the grip carried ends where the placement stands the card.
        following.placed(() => {
          const moved = placementDriver.stand(position);
          carry.placed();
          keeps(preview, "data-lf-thread-placement", THREAD_SIDES[side]);
          return moved;
        }, anew);
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
        if (!session.answering?.())
          keepThreadLanding(previewList.querySelector(".lf-page-thread"));
        session.settled?.();
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
    tick(cardRevision);
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
      arriving: true,
      // The box Send replaced, whose reading the card keeps (`showArrival`) and whose
      // field it grows out of (`placeThreadPreview`).
      sent: origin ? { fromEnd: origin.fromEnd, field: origin.field } : null,
      away: false,
      positionFrame: 0,
      positionResult: null,
      focusPending: null,
      withheldFocus: null,
      transcript: null,
      settled: null,
      answering: null,
      placesEnd: null,
      reading: null,
      gutter: null,
      stopRegion: null,
      stopDraw: null,
      end: null,
      side: commentPlacement(),
      // The width the card stands at for this selection, in client pixels: the box's
      // Send replaced, so the two are one rectangle, or the one it was carried at
      // (`placeThreadPreview`).
      itemView: null,
      width: origin?.box.width ?? null,
      scroller: pageScroller,
      // Whether the card's placement has landed for this selection, whose first spot its
      // motion follows from (`placeThreadPreview`).
      followed: false,
    };
    previewSession = session;
    tick(cardRevision);
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
    // A thread that left the cluster the card shows, as one resolved there leaves it,
    // gives its place to the thread after it, else the one before (`landing`).
    const stood = current.choice.items.findIndex((item) => item.id === wanted);
    const selected =
      threadItems.find((item) => item.id === wanted) ??
      threadItems[Math.min(stood, threadItems.length - 1)] ??
      threadItems[0];
    const arriving = current.threadItem !== selected.id || !current.transcript;
    const session =
      arriving && current.threadItem !== selected.id
        ? select({ ...current, entry, choice, item: selected })
        : current;
    Object.assign(session, { entry, choice, item: selected });
    session.reading = session.transcript && {
      input: inputCount(),
      scroll: session.transcript.scrollTop,
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
      // actions line, which on a card in a narrow room (`--thread-card-min`) already
      // leaves the message heads little room; " of " made it 12px wider, which on a
      // 311px card pushed the actions past the card's start.
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
    if (!arriving && session.transcript) present();
    else {
      present();
      const transcript = session.transcript;
      session.arriving = transcript !== null;
      if (transcript) showArrival(session, transcript);
    }
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
    // Stepping away from a thread ends the editing of its reply, keeping its draft, as
    // the floating panel's leaving a thread does: a press on the card's head line is a
    // press in the thread, which keeps it (thread/replies.js), and the reply going on
    // would carry the card back to the thread it stood in. The step lands where every
    // opening of a thread does (thread/focus.js, `openingPart`).
    dismissReply(threadKey(session.item.thread));
    void openPageThread(item.thread.id);
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
    // The draw follows what it reads until the card draws again or closes, so the
    // follows of the cards a user opens and closes don't pile up.
    session.stopDraw?.();
    const { drawn: rendered, stop } = renderMarginThread(body, shownThread, {
      line: (apart) => {
        setChildren(previewActions, [
          apart.news,
          apart.unread,
          ...(previewNav.hidden ? [] : [previewNav]),
          previewOpenInPanel,
          apart.controls,
          previewClose,
        ]);
        return previewHead;
      },
      // A send from the card is the user's change joining the stream the card shows
      // (box-motion.js, "send"), read before the send draws.
      reply: { options: { sending: following.stream } },
      // The card caps its transcript, which scrolls the thread's messages.
      scroller: (transcript) => transcript,
      endNewsMoves: () => endNewsMoves(session),
      // Whether the reader stands at the end the transcript's keeper follows
      // (scrolling.js, `followEnd`).
      standsAtEnd: () => Boolean(session.end?.standsAtEnd()),
      // The card stands for the thread on the page, where taking back a settlement made
      // in it opens the thread again.
      reader: "page",
      // Resolve stands the user on the thread that took the resolved one's place in the
      // card (`buildThreadCard`), or, where the passage held no other, on the target
      // the closed card stood by, since a resolved thread has no margin card (header).
      // Reopen lands as the thread's own does.
      landing: (resolved) => {
        if (resolved) return null;
        const target = targetFor(previewSession?.entry);
        const mayLand = retainUserIntent({
          source: focused(),
          available: () => previewOpen() || Boolean(target?.isConnected),
        });
        return () => {
          const next = previewOpen()
            ? previewList.querySelector(".lf-page-thread")
            : null;
          const place = next ?? target;
          if (!place) return false;
          return mayLand.handoff(() =>
            focusDestination(place, next ? "move" : "return"),
          );
        };
      },
    });
    session.stopDraw = stop;
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
    openLayer(preview);
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

  // The card a press on its marker opened takes the user where every opening does
  // (thread/focus.js, `openingPart`): into its reply, or onto its thread. Either way the
  // thread lands whole: landing on its reply box would take its transcript to its end,
  // past the turn the card opened on (`showArrival`).
  /** @param {Promise<boolean> | null} positioned @param {{closeControl?: boolean, cause?: import("../focus.js").PlacementCause}} [options] */
  function focusThread(positioned, { closeControl = false, cause = "move" } = {}) {
    if (!positioned) return;
    const session = previewSession;
    if (!session) return;
    deferThreadPreviewFocus(
      positioned,
      () => {
        if (closeControl) {
          focusDestination(previewClose, cause);
          return;
        }
        const thread = previewList.querySelector(".lf-page-thread");
        if (!thread) return;
        const target =
          threadFocusDestination(thread, { part: openingPart() }) ?? thread;
        focusDestination(target, cause);
        scrollThreadIntoView(thread, thread);
      },
      session,
    );
  }

  /** @param {string} name @param {{part?: import("../thread/destination.js").ThreadPart}} [options] */
  function focusTarget(name, { part = null } = {}) {
    const id = threadIdNamed(name);
    const thread = drawnThreadsWithId(previewList, id)[0];
    return thread ? threadFocusDestination(thread, { part, message: name }) : null;
  }

  /** @param {() => void} onDismiss */
  function mount(onDismiss) {
    dismiss = onDismiss;
    previewClose.onclick = onDismiss;
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    // Focus in the transcript lifts the fade over its top (annotation-chrome.css), so
    // the fade never lies over a focused message's ring. Like focus paint (focus.js), the
    // mark follows where the script leaves the user: a script that moves them out of the
    // transcript and back marks nothing.
    /** @type {Element | null} */
    let transcriptFocus = null;
    const markTranscriptFocus = () => {
      const transcript = previewSession?.transcript;
      if (transcript?.parentElement)
        keeps(
          transcript.parentElement,
          "data-lf-transcript-focus",
          transcriptFocus && under(transcriptFocus, transcript) ? "" : null,
        );
    };
    onCurrentLocation((node, cause, left) => {
      transcriptFocus = node;
      afterScript(markTranscriptFocus);
      if (
        node &&
        under(node, preview) &&
        closestAcross(node, ".lf-thread-reply") &&
        cause !== "return" &&
        cause !== "drop"
      )
        scheduleThreadPreviewPosition();
      const row =
        left && under(left, preview) && closestAcross(left, ".lf-thread-reply");
      if (row && !(node && under(node, row))) {
        /** @type {HTMLTextAreaElement | null} */
        const field = row.querySelector(REPLY_BOX);
        if (!field?.value) scheduleThreadPreviewPosition();
      }
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
