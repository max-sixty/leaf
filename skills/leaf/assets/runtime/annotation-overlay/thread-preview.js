/* Contextual thread preview: a card with a nested conversation lifetime.

   One Floating UI driver follows this card across conversation changes and stops
   when the card closes. Each selected conversation owns its originating control,
   reading region, held edge, pending placement/focus, and growth out of the comment
   box Send replaced (`growOut`). Replacing it retires that work before margin
   preparation can synchronously render again.
   A retained refresh preserves the selection's reading and draft continuity.
   Margin disclosure remains the margin's; selection records only whether a walk
   opened a cluster so its end can return that disclosure.

   ThreadView owns conversation rendering; comment-placement owns placement policy.
   The card stands where its comment box stood: level with the quoted words or pointed
   row, beside the target when its minimum fits, past its cluster when its full measure
   fits, otherwise across that cluster or above/below the target. A detached thread
   stands by its cluster. Floating UI follows that attachment within the reading region
   or viewport, under the chrome; regions clip it at their edges. A scroll never closes
   the card: it leaves with its target and comes back with it. A target hidden by the
   document withholds the card's native draft and focus until it is drawn again.

   A selection holds its placement side, its width and one edge. The width is the
   comment box's where Send opened the card, else the one the card first stood at, or
   was carried at, so a longer line arriving wraps inside it rather than carrying the
   controls at its far edge; only a narrower room narrows it.
   Reading and draft growth hold the top; a turn joining while drafting/sending holds
   the reply's foot, as does a card above its target; what a press in the card shows
   in its transcript keeps the pressed spot still, until the user's next input or a
   change they did not make. Another selection chooses afresh. Floating UI supplies
   room at that edge; native grid tracks share it between transcript and reply, growing
   to their words before scrolling. Reply continuity retains removed turns as flexible
   space and lets the transcript yield writing room without losing the visible lines.

   Placement changes geometry, never rebuilds contents. Retained state reads hold the
   reader's message and scroll position; another thread opens at its latest message,
   and the thread a comment's Send opened where the box's words stood (`showArrival`).
   A new/growing agent turn follows only at the tail. Landing, Send and stepping may
   move the reading; keepThreadLanding retains their destination through fitting until
   a newer reading gesture ends that authority. Size is fitted before paint, so a sent
   reply does not grow twice. Margin standing and its keyboard ladder own dismissal
   and target landing; the card keeps Send's focus on the thread that received it. */
import { atScrollEnd, moveScrollerBy, scrollToEnd } from "../scrolling.js";
import { cancelRender, nextRender } from "../rendering.js";
import { spokenSubject } from "../contribution-model.js";
import { labelWords } from "../words.js";
import { THREAD_CARD } from "./margin-layout.js";
import {
  focusDestination,
  holdFocus,
  inputCount,
  onStanding,
  onUserInput,
  focused,
  tabStops,
} from "../focus.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { closeControl, el, offer } from "../widget-elements.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "../keeps.js";
import { setChildren } from "../dom-children.js";
import { move } from "../dom-move.js";
import { effectiveScroller, registerReadingRegion } from "../reading-regions.js";
import { declareOffFlowSurface } from "../off-flow.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { reducedMotion } from "../motion.js";
import { closestAcross } from "../passages.js";
import { threadIdNamed } from "../thread/state.js";
import { turns } from "../thread/model.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { iconElement } from "../icons.js";
import { anchorLabel } from "../thread/messages.js";
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
import { floatingPlacement, floatingUi } from "./floating.js";
import { surfaceGrip } from "./surface-grip.js";
import { placeKeeper } from "../user-place.js";
import { renderedOrder, renderedUnder, under } from "../shadow.js";
import { keys } from "../keyboard/scopes.js";
import { retainUserIntent } from "../user-intent.js";
import { threadFocusDestination } from "../thread/focus.js";
import { claimSeatReplies } from "../thread/inline.js";
import { releaseReplies } from "../thread/replies.js";
import { keepThreadLanding, showLatestTurn } from "../thread/reply-landing.js";
import { strongestWorkflow } from "../thread/workflow.js";
import { writingIn } from "../thread/replies.js";

// A margin card's reply box.
const REPLY_BOX = `.lf-thread-reply ${TEXT_FIELD}`;
// Where a reading region cuts the card, inward from each of its edges.
const CUT_EDGES = [
  "--lf-cut-top",
  "--lf-cut-right",
  "--lf-cut-bottom",
  "--lf-cut-left",
];

export function createThreadPreview({
  inventory,
  renderMarginThread,
  placedAt,
  openPageThread,
  scrollThreadIntoView,
  scrollToElement,
  onClose,
}) {
  const { targetFor, entryPoint, entryPlace, sourceItem } = inventory;
  // The card is the margin's, as the cluster it hangs from is, rather than a layer over
  // the page: a top-layer popover made every press on the page a light dismissal and
  // tiered the keyboard over it, so standing on the passage it discusses took it down.
  // It shows while the user stands at its target (`followStanding`).
  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = THREAD_CARD;
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
  const previewPrevious = offer(
    "button",
    "lf-btn lf-icon-action lf-margin-preview-step",
  );
  previewPrevious.append(iconElement("previous", "lf-action-icon"));
  previewPrevious.setAttribute("aria-label", "Previous thread");
  previewPrevious.title = "Previous thread";
  const previewNext = offer("button", "lf-btn lf-icon-action lf-margin-preview-step");
  previewNext.append(iconElement("next", "lf-action-icon"));
  previewNext.setAttribute("aria-label", "Next thread");
  previewNext.title = "Next thread";
  previewNav.append(previewPrevious, previewPosition, previewNext);
  const previewList = el("div", "lf-margin-preview-list");
  // Carried by its grip, the card stands where the user drops it, relative to what it is
  // about, at the width it was carried at, until its placement chooses afresh.
  const carry = surfaceGrip({
    surface: preview,
    bounds: () => commentBoundary({ region: previewSession?.region }),
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
  preview.append(carry.grip, previewList);
  // The card follows the margin entry it hangs from (`session.control`) in the Tab
  // order, as a popover follows its invoker: Tab on the entry enters the card, Shift+Tab
  // from before the card's first stop returns to the entry, and Tab past the card's last
  // stop, or Shift+Tab from the entry, goes on from the entry as though the card weren't
  // there. The browser's own order doesn't: the card stands in the chrome after the
  // page and just before the margin, so Shift+Tab out of it reached the page's last
  // stop, which scrolled the page there and, standing away from the card's target,
  // closed the card. To pass over the card, a row puts the user on the entry, or on the
  // card's own box just before the margin, and leaves the browser to take the step from
  // there, as the floating panel's menu does.
  const opener = () =>
    previewSession?.control?.checkVisibility() ? previewSession.control : null;
  const onOpener = () => Boolean(opener()) && focused() === opener();
  // The stops in `root` before (-1) or after (1) `at`, in the browser's order.
  const stopsBeside = (root, at, side) =>
    tabStops(root).filter(
      (stop) =>
        stop !== at &&
        !renderedUnder(at, stop) &&
        Math.sign(renderedOrder(stop, at)) === side,
    );
  const atCardEdge = (side) =>
    Boolean(opener()) && stopsBeside(preview, focused(), side).length === 0;
  keys(preview, null, [
    {
      id: "margin.card.back",
      keys: ["Shift+Tab"],
      title: "back to the margin entry",
      description: "Leave the thread card for the margin entry it hangs from",
      repeat: true,
      runFromCommandReference: false,
      when: () => atCardEdge(-1),
      run: () => focusDestination(opener(), "step"),
    },
    {
      id: "margin.card.onward",
      keys: ["Tab"],
      title: "on past the margin entry",
      description: "Leave the thread card for the stop after the margin entry",
      native: true,
      repeat: true,
      runFromCommandReference: false,
      when: () => atCardEdge(1),
      run: () => focusDestination(opener(), "return"),
    },
  ]);
  // The entry's half, which the margin declares on its rows.
  const openerKeys = [
    {
      id: "margin.card.enter",
      keys: ["Tab"],
      title: "into the thread card",
      description: "Enter the thread card the margin entry opened",
      repeat: true,
      runFromCommandReference: false,
      when: () => onOpener() && tabStops(preview).length > 0,
      run: () => focusDestination(tabStops(preview)[0], "step"),
    },
    {
      id: "margin.card.over",
      keys: ["Shift+Tab"],
      title: "back past the thread card",
      description: "Go back from the margin entry to the stop before it",
      native: true,
      repeat: true,
      runFromCommandReference: false,
      when: () =>
        onOpener() && under(stopsBeside(chromeRoot, opener(), -1).at(-1), preview),
      run: () => focusDestination(preview, "return"),
    },
  ];
  // A press in the card changes what it shows from where the user pressed, so the
  // placement that change causes keeps the pressed spot still (`holding`'s `pressed`)
  // until the user's next input. The press, by pointer, touch or key, is read at the input
  // edge, before its handlers change the card: each element on its path, from the
  // card's top, so a control the press removes, as its notice is, gives way to the
  // nearest one still drawn.
  onUserInput((event) => {
    // A tap counts its `touchstart` after its `pointerdown`, so it is read again there.
    if (
      !previewSession ||
      !["pointerdown", "touchstart", "keydown"].includes(event.type)
    )
      return;
    const path = event.composedPath();
    if (!path.includes(preview)) return;
    const top = preview.getBoundingClientRect().top;
    previewSession.pressed = {
      input: inputCount(),
      path: path
        .filter(
          (node) =>
            node instanceof Element && node !== preview && preview.contains(node),
        )
        .map((node) => ({ node, offset: node.getBoundingClientRect().top - top })),
    };
  });
  let previewRegionMounted = false;
  // The card's transcript is re-rendered on every reading of its thread; a message holds
  // the user's place in it under the event id it is rendered with (user-place.js).
  function syncPreviewTranscript() {
    const transcript = previewList.querySelector(".lf-thread-transcript");
    if (transcript === previewSession.transcript) return;
    previewSession.stopRegion?.();
    previewSession.stopRegion = null;
    previewSession.transcript = transcript;
    previewSession.place = transcript
      ? placeKeeper(transcript, {
          items: ".lf-msg[data-event]",
          identity: (message) => message.dataset.event,
        })
      : null;
    if (previewRegionMounted && transcript)
      previewSession.stopRegion = registerReadingRegion({
        id: THREAD_CARD,
        host: preview,
        body: transcript,
      });
  }
  let previewSession = null;
  const placementDriver = floatingPlacement({
    floating: preview,
    update: () => scheduleThreadPreviewPosition(),
  });

  // A placement lands in the microtasks after it starts, before the frame paints. One
  // that cannot land yet — its owner not connected, no room — is answered by a later
  // placement, or by the close that abandons it.
  const placedThreadPreview = () => {
    previewSession.positionResult ??= Promise.withResolvers();
    cancelRender(previewSession.positionFrame);
    previewSession.positionFrame = 0;
    placeThreadPreview();
    return previewSession.positionResult.promise;
  };
  // Floating UI follows what moves the card's target: its scroll containers, the window
  // and visual viewport, and the target and card changing size or moving.
  // A card that stays open keeps its spot while its next placement is worked out from
  // nothing it held: the edge it was held by, the frame queued, and any answer in flight
  // are dropped, and the placement rewrites only what moved. A card with no spot yet is
  // unplaced, and chrome.css keeps an unplaced card unseen and out of reach.
  function forgetThreadPreviewPlacement() {
    placementDriver.supersede();
    cancelRender(previewSession.positionFrame);
    previewSession.positionFrame = 0;
    previewSession.side.forget();
    previewSession.away = false;
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
  function deferThreadPreviewFocus(positioned, focus) {
    const mayFocus = retainUserIntent();
    const session = previewSession;
    const pending = { holding: focused() };
    previewSession.focusPending = pending;
    void positioned?.then((placed) => {
      if (previewSession !== session || session.focusPending !== pending) return;
      previewSession.focusPending = null;
      const holdingGone =
        focused() === document.body &&
        (!pending.holding?.isConnected || !pending.holding?.checkVisibility());
      if (placed && (focused() === pending.holding || holdingGone))
        mayFocus.handoff(focus);
    });
  }

  // How far past its border box the card paints: its shadow's furthest offset, blur and
  // spread, in its own pixels.
  function paintReach(card) {
    const shadows = getComputedStyle(card).boxShadow.split(/,(?![^(]*\))/);
    return Math.max(
      0,
      ...shadows.map((shadow) => {
        const [x = 0, y = 0, blur = 0, spread = 0] = (
          shadow.match(/-?[\d.]+px/g) ?? []
        ).map(parseFloat);
        return Math.max(Math.abs(x), Math.abs(y)) + blur + spread;
      }),
    );
  }
  // Placement supplies the outer bounds; the native tracks share them between
  // reading and writing. A scroll that only carries a fitting card writes nothing;
  // clipped contents receive newly available room without requiring a complete fit.
  function measureThreadCard(room, cap, reading) {
    preview.style.setProperty("--lf-thread-width", layoutPx(room));
    const worn = parseFloat(preview.style.getPropertyValue("--lf-thread-max-height"));
    const height = preview.offsetHeight;
    const overflow = [
      previewSession.transcript,
      ...previewList.querySelectorAll(REPLY_BOX),
    ].some((box) => box && box.scrollHeight > box.clientHeight + 0.5);
    if (!(worn >= 0) || cap < height - 0.5 || (overflow && cap > height + 0.5))
      preview.style.setProperty("--lf-thread-max-height", layoutPx(cap));
    if (reading?.latest) showArrival(previewSession);
    else if (reading?.end) scrollToEnd(previewSession.transcript);
    return preview.getBoundingClientRect().height;
  }
  // A card opens on its latest turn, at that turn's start. A card Send opened stands
  // its words as far above its end as the box it replaces stood them, which shares
  // its text column and its foot, so the words the user was reading stay where they
  // were.
  function showArrival(session) {
    if (!session.sent) return showLatestTurn(session.transcript);
    scrollToEnd(session.transcript);
    moveScrollerBy(session.transcript, -session.sent.fromEnd);
  }
  // The selected transcript's unconstrained extent changes with turns, not editor
  // lines. Keep its fractional local height alongside the native overflow reading;
  // rounding the whole measurement makes an unchanged turn look newly arrived.
  function measureTranscript() {
    return previewSession.transcript
      ? parseFloat(getComputedStyle(previewSession.transcript).height) +
          previewSession.transcript.scrollHeight -
          previewSession.transcript.clientHeight
      : 0;
  }
  // The row the card hangs from where its thread has no target to stand by. A row the
  // rail has no room for is withheld and has no box; it stands by the row's target
  // instead, at the row inside it the cluster would stand level with (pointed-place.js).
  function threadCardCluster(session) {
    const row = session.control.closest("[data-lf-margin-for]") ?? session.control;
    if (row.checkVisibility()) return row;
    return entryPlace(session.entry) ?? row;
  }
  // The thread the card shows, and the first line of the words it quotes, if it does.
  const threadCardThread = (session) => {
    const item = session.entry?.items.find(
      (candidate) => candidate.id === session.threadItem,
    );
    return item ? sourceItem(item)?.thread : null;
  };
  // What the card stands by, read as the comment box reads it (comment-placement.js):
  // its target's shown box, or the row a pointing gesture named in it, and the line it
  // stands level with, a quoted passage's first. A thread with no target stands by its
  // cluster.
  function threadCardPlace(session) {
    const target = targetFor(session.entry);
    const point = entryPoint(session.entry);
    if (!target) {
      const cluster = threadCardCluster(session);
      const box = cluster.getBoundingClientRect();
      return {
        element: cluster,
        clear: box,
        extent: box,
        row: box.top,
        margin: null,
        region: null,
        scroller: effectiveScroller(cluster),
      };
    }
    const thread = threadCardThread(session);
    const words =
      !point && thread?.anchor?.quote ? passageGeometry(placedAt(thread.id)) : null;
    return commentAttachment({ target, point, passage: words });
  }
  const THREAD_SIDES = { right: "right", left: "left", bottom: "below", top: "above" };
  // Where the card stands is comment-placement.js's rule, the one the comment box stands
  // by, so a sent comment's card opens where its box stood. Beyond it the card holds its
  // place as its thread changes: it keeps the top while the user reads or writes a new
  // line, and its foot, with the reply row on it, after a turn joins the transcript as
  // the user drafts, whether one arrives or they sent it, so the box they type in stays
  // put through subsequent sizing passes. A card over its target grows up from its
  // foot (`holding`, comment-placement.js). The boundary caps the card at the room from
  // its held edge. Drafting grows the editor into that room, then scrolls its words
  // rather than carrying the card.
  function placeThreadPreview() {
    const session = previewSession;
    if (!session || !session.control?.isConnected) return false;
    const placement = placementDriver.begin();
    let reading = null;
    const stillCurrent = () =>
      previewSession === session &&
      placementDriver.current(placement) &&
      session.control?.isConnected;
    const place = threadCardPlace(session);
    // Floating UI follows what moves what the card stands by, so a card with no room yet
    // is placed once something gives it some.
    const element = place?.element ?? targetFor(session.entry);
    const watch = (ui) =>
      placementDriver.watch(
        element,
        {
          contextElement: element,
          getBoundingClientRect: () =>
            threadCardPlace(session)?.clear ?? element.getBoundingClientRect(),
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
    const thread = threadCardThread(session);
    const latest = thread && turns(thread).at(-1);
    const replyEditor = previewList.querySelector(REPLY_BOX);
    // Drafting is standing anywhere in the reply's row, Send included, holding words in
    // it, or a send of the user's still on its way. The send takes the user out of the
    // box it empties (`landSent`), and the turn it adds must not move the reply row or
    // Send from under the press.
    const sending =
      latest?.author === "user" &&
      strongestWorkflow(latest.workflows)?.stage === "sending";
    const drafting = writingIn(replyEditor, sending);
    const boundary = commentBoundary({ region: place.region });
    session.region = place.region;
    if (!boundary.width || !boundary.height) {
      void floatingUi().then((ui) => stillCurrent() && watch(ui));
      return false;
    }
    const scroller = place.scroller;
    const { side, fresh, hold } = session.side.choose({
      clear: place.clear,
      row: place.row,
      column: place.column,
      extent: place.extent,
      boundary,
      scroller,
      coarse: coarsePointer.matches,
    });
    const pressed =
      session.pressed?.input === inputCount()
        ? session.pressed.path.find(({ node }) => node.checkVisibility())
        : null;
    const held = session.side.holding({
      fresh,
      hold,
      transcript: measureTranscript(),
      drafting,
      latest,
      draftText: replyEditor?.value ?? "",
      pressed: pressed && {
        input: session.pressed.input,
        moved:
          Math.abs(
            pressed.node.getBoundingClientRect().top -
              preview.getBoundingClientRect().top -
              pressed.offset,
          ) > 0.5,
      },
    });
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        const { reference, placement, middleware, plane } = session.side.options(ui, {
          clear: place.clear,
          row: place.row,
          lastRow: place.lastRow,
          column: place.column,
          margin: place.margin,
          boundary,
          fit({ width, height, stood, scale }) {
            if (!stillCurrent()) return;
            // Capture when fitting actually starts, after the module load and any
            // Send landing. Hold this reading through every middleware measurement:
            // an intermediate cap must not turn an earlier offset into end-following.
            reading ??= session.transcript && {
              end: !fresh && atScrollEnd(session.transcript),
              latest: session.arriving,
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
            // last moved where that is more. This cap holds for reading and writing alike:
            // a growing editor uses the room below its top, then scrolls internally.
            const fitted = measureThreadCard(room, Math.max(stood, height), reading);
            // Fitting the width settles wrapping before opening the card spends
            // scroll travel. A scroll supersedes this answer's attachment geometry.
            if (
              fresh &&
              (side === "top" || side === "bottom") &&
              makeRoom(side, place.clear, place.extent, fitted, boundary, scroller)
            ) {
              session.side.scrolled();
              placeThreadPreview();
            }
          },
          hold: () => session.side.heldAt(held),
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
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale } = session.side.landed(position);
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
        // cuts the words. An edge further out than the card paints cuts nothing, and
        // stands at that reach, so a scroll that moves it there writes nothing. Each
        // edge's cut is its own property, which the card's clip and its growth out of
        // the comment box both read (annotation-chrome.css).
        const region = boundary.inRegion;
        const cuts = region
          ? [
              (region.top - card.top) / scale.y,
              (card.right - region.right) / scale.x,
              (card.bottom - region.bottom) / scale.y,
              (region.left - card.left) / scale.x,
            ].map((cut) => layoutPx(Math.max(cut, -paintReach(preview))))
          : [];
        CUT_EDGES.forEach((edge, i) => {
          if (region) preview.style.setProperty(edge, cuts[i]);
          else preview.style.removeProperty(edge);
        });
        keeps(preview, "data-lf-thread-placement", THREAD_SIDES[side]);
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
  // The card hangs from another entry, and a user standing on the entry it hung from goes
  // with it: the same place, the thread's own entry, under a new control.
  function transferThreadCard(button, carry = focused() === previewSession?.control) {
    if (previewSession?.control === button) return;
    forgetThreadPreviewPlacement();
    previewSession.control = button;
    if (carry) focusDestination(button, "return");
  }

  /** @param {{
   *   entry: any,
   *   threadItem: string,
   *   control: any,
   *   origin?: any,
   *   accompanies: any,
   *   forced?: boolean,
   *   disclosed?: boolean,
   * }} chosen */
  function select({
    entry,
    threadItem,
    control,
    origin,
    accompanies,
    forced = false,
    disclosed = false,
  }) {
    retirePreviewSession();
    previewSession = {
      entry,
      threadItem,
      control,
      accompanies,
      forced,
      disclosed,
      preparing: false,
      latest: null,
      arriving: true,
      // The box Send replaced, whose reading the card keeps (`showArrival`).
      sent: origin && { fromEnd: origin.fromEnd },
      away: false,
      positionFrame: 0,
      positionResult: null,
      focusPending: null,
      withheldFocus: null,
      transcript: null,
      place: null,
      stopRegion: null,
      side: commentPlacement(),
      // The width the card stands at for this selection, in client pixels: the box's
      // Send replaced, so the two are one rectangle, else the one it first stood at, or
      // was carried at (`placeThreadPreview`). Sized by itself, Firefox stood a one-line
      // comment's card 13px wider than its box.
      width: origin?.box.width ?? null,
      region: null,
      // The user's latest press in the card, while it is their latest input (`holding`).
      pressed: null,
    };
    if (origin) previewSession.side.adopt(origin);
    return previewSession;
  }

  function buildThreadCard(entry, requestedItem = null) {
    const restoreFocus = holdFocus(preview);
    const focusedItem = restoreFocus
      ? (focused(document)?.closest?.("[data-lf-margin-entry]")?.lfMarginItem ?? null)
      : null;
    const threadItems = entry.items.filter((item) => item.kind === "comment");
    const wanted = requestedItem ?? previewSession.threadItem ?? focusedItem;
    const selected = threadItems.find((item) => item.id === wanted) ?? threadItems[0];
    const arriving =
      previewSession.threadItem !== selected.id || !previewSession.transcript;
    if (previewSession.threadItem !== selected.id)
      select({ ...selection(), entry, threadItem: selected.id });
    else previewSession.entry = entry;
    const session = previewSession;
    const latest = turns(sourceItem(selected).thread).at(-1);
    const messageSelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-transcript > .lf-msg";
    const replySelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-reply";
    const lastShown = [...previewList.querySelectorAll(messageSelector)].at(-1);
    const lastBox = lastShown?.getBoundingClientRect();
    const listBox = session.transcript?.getBoundingClientRect();
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
      atScrollEnd(session.transcript);
    const present = () => {
      const targetHeading =
        targetFor(entry)?.querySelector(":scope > strong")?.textContent;
      // A target with a heading is named by it. One without — an aside, a paragraph —
      // is headed by the passage the selected thread quotes, as the panel heads it: a card
      // headed "aside · The fallback cookie is read-only…" over a comment on the aside's
      // last sentence was a third name for one thread, and the least exact.
      const quoted = sourceItem(selected)?.thread?.anchor
        ? anchorLabel(
            sourceItem(selected).thread.anchor,
            sourceItem(selected).thread.root.about,
          )
        : null;
      const title = labelWords(targetHeading || quoted || entry.title);
      keeps(preview, "aria-label", `Thread for ${spokenSubject(title)}`);
      keepsHidden(previewNav, threadItems.length < 2);
      const selectedIndex = Math.max(0, threadItems.indexOf(selected));
      keepsText(previewPosition, `${selectedIndex + 1}/${threadItems.length}`);
      previewPrevious.toggleAttribute("disabled", selectedIndex === 0);
      previewNext.toggleAttribute("disabled", selectedIndex === threadItems.length - 1);
      const item = selected ? previewItemNode(selected) : null;
      setChildren(previewList, item ? [item] : []);
      // The thread renders before the card shows it, and takes the reply being written
      // in it once it stands in the document (thread/inline.js, `claimSeatReplies`).
      if (item) claimSeatReplies(item.querySelector(":scope > .lf-margin-thread-body"));
      syncPreviewTranscript();
      // The list holds the one thread the card shows, so a user whose place in a thread
      // the rebuild took lands on that thread; a step button it hid hands them to Close.
      restoreFocus?.(
        focusedItem && previewList.querySelector(".lf-page-thread"),
        previewClose,
      );
    };
    if (!arriving && session.place) session.place.around(present);
    else {
      present();
      session.arriving = Boolean(session.transcript);
      if (session.arriving) showArrival(session);
    }
    session.latest = latest && { id: latest.id, text: latest.text };
    if (follow) scrollToEnd(session.transcript);
  }

  function stepPreviewThread(step) {
    if (!previewSession) return;
    const threadItems = previewSession.entry.items.filter(
      (item) => item.kind === "comment",
    );
    const current = threadItems.findIndex(
      (item) => item.id === previewSession.threadItem,
    );
    const next = Math.max(0, Math.min(threadItems.length - 1, current + step));
    if (next === current || !threadItems[next]) return;
    const positioned = show({ ...selection(), threadItem: threadItems[next].id });
    focusThread(positioned);
  }
  function previewItemNode(item) {
    let node = [...previewList.children].find(
      (candidate) => candidate.lfMarginItem === item.id,
    );
    if (!node?.classList.contains("lf-margin-thread")) {
      node?.remove();
      node = el("section", "lf-margin-thread");
      const body = el("div", "lf-margin-thread-body");
      node.append(body);
    }
    renderMarginThread(
      node.querySelector(":scope > .lf-margin-thread-body"),
      sourceItem(item).thread,
      {
        nav: previewNav.hidden ? null : previewNav,
        close: previewClose,
        // The edge news would grow the card from (comment-placement.js, `edgeFor`).
        heldEdge: (turn) => previewSession?.side.edgeFor(turn) ?? "top",
        // A resolved thread with no draft has no margin card, so resolving closes it and
        // hands the user to its target, and a resolve that no longer stands opens the
        // card on the thread again, while the margin is still where threads open.
        prepareLanding: () => {
          const target = targetFor(previewSession?.entry);
          const thread = sourceItem(item).thread.id;
          const mayLand = retainUserIntent({
            source: focused(),
            available: () => Boolean(target?.isConnected),
          });
          return {
            optimistic: () => {
              if (previewOpen()) return false;
              return mayLand.handoff(() => focusDestination(target, "return"));
            },
            reverse: async (may = mayLand) => {
              await whenDocumentPresented();
              return (
                may() &&
                mayLand.available() &&
                Boolean(await openPageThread(thread, { part: "thread", intent: may }))
              );
            },
          };
        },
      },
    );
    keeps(node, "data-lf-margin-entry", item.id);
    node.lfMarginItem = item.id;
    return node;
  }

  // The card's threads the margin no longer holds give up the reply being written in
  // them, whether the card is open or closed (thread/replies.js, `releaseReplies`). A
  // thread still in the margin keeps it, for the card to show again.
  function releaseLeft(items) {
    for (const node of previewList.children)
      if (!items.has(node.lfMarginItem)) releaseReplies(node);
  }

  function selection() {
    if (!previewSession) return null;
    const { entry, threadItem, control, accompanies, forced, disclosed } =
      previewSession;
    return Object.freeze({
      entry,
      threadItem,
      control,
      accompanies,
      forced,
      disclosed,
    });
  }

  function show({
    entry,
    threadItem = null,
    control = null,
    origin = null,
    accompanies = false,
    forced = false,
    disclosed = false,
    prepare = null,
  }) {
    const items = entry.items.filter((item) => item.kind === "comment");
    const selected = items.find((item) => item.id === threadItem) ?? items[0];
    const retained =
      previewSession?.entry.key === entry.key &&
      previewSession.threadItem === selected.id;
    const session = retained
      ? previewSession
      : select({
          entry,
          threadItem: selected.id,
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
    buildThreadCard(entry, selected.id);
    const positioned = placedThreadPreview();
    return session.sent ? growOut(session, positioned) : positioned;
  }

  // A card Send opened grows out of the comment box it replaces, once it stands
  // (`data-lf-grows`, annotation-chrome.css).
  function growOut(session, positioned) {
    return positioned.then((placed) => {
      if (placed && previewSession === session && !reducedMotion())
        keeps(preview, "data-lf-grows", "");
      return placed;
    });
  }
  preview.addEventListener("animationend", (event) => {
    if (event.target === preview) keeps(preview, "data-lf-grows", null);
  });

  function refresh(entry, control, carry = focused() === previewSession?.control) {
    if (!previewSession || previewSession.preparing) return;
    transferThreadCard(control, carry);
    buildThreadCard(entry);
    placeThreadPreview();
  }

  function close() {
    if (!previewSession) return;
    const closed = selection();
    retirePreviewSession();
    placementDriver.stop();
    delete preview.dataset.lfThreadPlacement;
    for (const edge of CUT_EDGES) preview.style.removeProperty(edge);
    keepsHidden(preview, true);
    onClose(closed);
  }

  function focusThread(positioned, { closeControl = false, cause = "move" } = {}) {
    if (!positioned) return;
    deferThreadPreviewFocus(positioned, () => {
      const target = closeControl
        ? previewClose
        : previewList.querySelector(".lf-page-thread");
      if (!target) return;
      focusDestination(target, cause);
      if (!closeControl) scrollThreadIntoView(target, target);
    });
  }

  function focusTarget(name, { part = null } = {}) {
    const id = threadIdNamed(name);
    const thread = [...previewList.querySelectorAll(".lf-page-thread")].find(
      (candidate) => candidate.dataset.thread === id,
    );
    return thread
      ? threadFocusDestination(thread, { part: part ?? "thread", message: name })
      : null;
  }

  function mount(onDismiss) {
    previewClose.onclick = onDismiss;
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    onStanding((node, cause, left) => {
      const row =
        left && under(left, preview) && closestAcross(left, ".lf-thread-reply");
      if (row && !(node && under(node, row)) && !row.querySelector(REPLY_BOX)?.value)
        scheduleThreadPreviewPosition();
    });
    declareOffFlowSurface(preview, {
      bringBack: (behavior) =>
        scrollToElement(
          entryPlace(previewSession?.entry) ?? previewSession?.control,
          behavior,
          "nearest",
        ),
    });
    move(chromeRoot, preview, chromeForeground);
    previewRegionMounted = true;
    if (previewSession) syncPreviewTranscript();
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
    // Whether the user stands in the card's reply box.
    replying: () =>
      under(focused(), preview) && Boolean(closestAcross(focused(), REPLY_BOX)),
    // Whether the open card has somewhere to stand (`threadCardPlace`).
    stands: () => Boolean(previewSession && threadCardPlace(previewSession)),
    place: placeThreadPreview,
    schedulePosition: scheduleThreadPreviewPosition,
    mount,
  };
}
