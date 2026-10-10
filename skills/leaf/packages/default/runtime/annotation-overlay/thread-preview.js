/* Contextual thread preview: a card with a nested conversation lifetime.

   One Floating UI driver follows this card across conversation changes and stops
   when the card closes. Each selected conversation owns its originating control,
   reading region, held edge, pending placement/focus, and reveal motion. Replacing
   it retires that work before margin preparation can synchronously render again.
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

   A selection holds its placement side and one edge. Reading and draft growth hold
   the top; a turn joining while drafting/sending holds the reply's foot, as does a
   card above its target. Another selection chooses afresh. Floating UI supplies room
   at that edge; native grid tracks share it between transcript and reply, growing to
   their words before scrolling. Reply continuity retains removed turns as flexible
   space and lets the transcript yield writing room without losing the visible lines.

   Placement changes geometry, never rebuilds contents. Retained state reads hold the
   reader's message and scroll position; another thread opens at its latest message.
   A new/growing agent turn follows only at the tail. Landing, Send and stepping may
   move the reading; keepThreadLanding retains their destination through fitting until
   a newer reading gesture ends that authority. Size is fitted before paint, so a sent
   reply does not grow twice. Margin standing and its keyboard ladder own dismissal
   and target landing; the card keeps Send's focus on the thread that received it. */
import { atScrollEnd, scrollToEnd } from "/runtime/scrolling.js";
import { cancelRender, nextRender } from "/runtime/rendering.js";
import { labelWords, spokenSubject } from "/runtime/contribution-model.js";
import { THREAD_CARD } from "./margin-layout.js";
import { mapButton } from "/runtime/page-map-dialog.js";
import { focusDestination, holdFocus, onStanding, focused } from "/runtime/focus.js";
import { TEXT_FIELD } from "/runtime/control-selectors.js";
import { closeControl, el, offer } from "/runtime/widget-elements.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "/runtime/keeps.js";
import { setChildren } from "/runtime/dom-children.js";
import { effectiveScroller, registerReadingRegion } from "/runtime/reading-regions.js";
import { declareOffFlowSurface } from "/runtime/off-flow.js";
import { chromeRoot, chromeForeground } from "/runtime/chrome.js";
import { motion } from "/runtime/motion.js";
import { closestAcross } from "/runtime/passages.js";
import { allThreads } from "/runtime/thread/state.js";
import { threadNames, turns } from "/runtime/thread/model.js";
import { whenDocumentPresented } from "/runtime/semantic-state.js";
import { iconElement } from "/runtime/icons.js";
import { anchorLabel } from "/runtime/thread/messages.js";
import { bannerControlDoor } from "/runtime/banner-toolbar.js";
import { coarsePointer } from "/runtime/pointer.js";
import {
  cardMeasure,
  cardMinimum,
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
  makeRoom,
} from "./comment-placement.js";
import { passageGeometry } from "/runtime/resolved-target.js";
import { floatingPlacement, floatingUi } from "./floating.js";
import { placeKeeper } from "/runtime/user-place.js";
import { under } from "/runtime/shadow.js";
import { retainUserIntent } from "/runtime/user-intent.js";
import { threadFocusDestination } from "/runtime/thread/focus.js";
import { keepThreadLanding, showLatestTurn } from "/runtime/thread/reply-landing.js";
import { strongestWorkflow } from "/runtime/thread/workflow.js";

// A margin card's reply box.
const REPLY_BOX = `.lf-thread-reply ${TEXT_FIELD}`;

export function createThreadPreview({
  inventory,
  renderMarginThread,
  placedAt,
  openPageThread,
  panelIsOpen,
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
  preview.append(previewList);
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

  // The submitted composer and a developer replay describe the same starting box; the
  // transition owns that geometry contract instead of making either caller duplicate it.
  function threadTransitionOrigin(element, frame) {
    if (!frame) return null;
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      frame,
      left: box.left,
      top: box.top,
      width: box.width,
      height: box.height,
      messageMeasure: element.writingInlineSize,
      messageHeight: parseFloat(style.height),
      endRoom: element.endRoom ?? "none",
      scroll: element.scrollTop,
    };
  }

  // The real message is legible from the first frame; only its surrounding frame
  // grows. No copied words, translation, scaling, or second placement at motion's end.
  function transitionThread(origin) {
    const target = preview.getBoundingClientRect();
    const style = getComputedStyle(preview);
    const scale = {
      x: target.width / parseFloat(style.width),
      y: target.height / parseFloat(style.height),
    };
    const inset = [
      (origin.top - target.top) / scale.y,
      (target.right - origin.left - origin.width) / scale.x,
      (target.bottom - origin.top - origin.height) / scale.y,
      (origin.left - target.left) / scale.x,
    ];
    return motion(
      preview,
      [
        { clipPath: `inset(${inset.map(layoutPx).join(" ")} round 6px)` },
        { clipPath: preview.style.clipPath || "inset(0px round 10px)" },
      ],
      240,
    );
  }

  function revealThread(origin, positioned) {
    const session = previewSession;
    session.transition?.motion?.cancel();
    const transition = { motion: null };
    session.transition = transition;
    return positioned.then((placed) => {
      if (!placed || previewSession !== session || session.transition !== transition)
        return false;
      transition.motion = transitionThread(origin);
      return true;
    });
  }

  function carryCommentFrame(origin) {
    previewSession.messageViewport?.stopRegion?.();
    previewSession.messageViewport = origin && {
      scroll: origin.scroll,
      body: null,
      stopRegion: null,
    };
    keeps(
      preview,
      "data-lf-comment-frame",
      previewSession.messageViewport && origin.endRoom,
    );
    const properties = {
      "--lf-comment-width": previewSession.messageViewport && `${origin.frame.width}px`,
      "--lf-comment-message-measure":
        previewSession.messageViewport && `${origin.messageMeasure}px`,
      "--lf-comment-message-height":
        previewSession.messageViewport && `${origin.messageHeight}px`,
    };
    for (const [name, value] of Object.entries(properties))
      if (value) preview.style.setProperty(name, value);
      else preview.style.removeProperty(name);
  }

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
    const session = previewSession;
    if (!session) return;
    carryCommentFrame(null);
    session.transition?.motion?.cancel();
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
    const pending = { holding: document.activeElement };
    previewSession.focusPending = pending;
    void positioned?.then((placed) => {
      if (previewSession !== session || session.focusPending !== pending) return;
      previewSession.focusPending = null;
      const holdingGone =
        document.activeElement === document.body &&
        (!pending.holding?.isConnected || !pending.holding?.checkVisibility());
      if (placed && (document.activeElement === pending.holding || holdingGone))
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
    preview.style.setProperty("--lf-thread-width", `${room}px`);
    const worn = parseFloat(preview.style.getPropertyValue("--lf-thread-max-height"));
    const height = preview.offsetHeight;
    const overflow = [
      previewSession.transcript,
      ...previewList.querySelectorAll(REPLY_BOX),
    ].some((box) => box && box.scrollHeight > box.clientHeight + 0.5);
    if (!(worn >= 0) || cap < height - 0.5 || (overflow && cap > height + 0.5))
      preview.style.setProperty("--lf-thread-max-height", `${cap}px`);
    if (reading?.latest) showLatestTurn(previewSession.transcript);
    else if (reading?.end) scrollToEnd(previewSession.transcript);
    return preview.getBoundingClientRect().height;
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
    const drafting = Boolean(
      replyEditor?.checkVisibility() &&
      (replyEditor.closest(".lf-thread-reply").contains(document.activeElement) ||
        replyEditor.value !== "" ||
        sending),
    );
    const boundary = commentBoundary({ region: place.region });
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
    const held = session.side.holding({
      fresh,
      hold,
      transcript: measureTranscript(),
      drafting,
      latest,
      draftText: replyEditor?.value ?? "",
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
          fit({ width, height, scale }) {
            if (!stillCurrent()) return;
            // Capture when fitting actually starts, after the module load and any
            // Send landing. Hold this reading through every middleware measurement:
            // an intermediate cap must not turn an earlier offset into end-following.
            reading ??= session.transcript && {
              end: !fresh && atScrollEnd(session.transcript),
              latest: session.arriving,
            };
            const room = Math.min(cardMeasure(), width);
            preview.style.setProperty(
              "--lf-thread-min-width",
              `${Math.min(cardMinimum(), room)}px`,
            );
            // Choosing its spot, the card is capped by the boundary alone, and slides
            // inside it rather than shrinking. Held, it has the room from its held edge
            // to the boundary's far edge, with that edge inside the boundary as far as
            // its last height puts it. This cap holds for reading and writing alike:
            // a growing editor uses the room below its top, then scrolls internally.
            const minimum = session.side.heldHeight() / scale.y;
            const fitted = measureThreadCard(room, Math.max(minimum, height), reading);
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
        if (session.messageViewport) {
          const body = previewList.querySelector(
            ".lf-msg > .lf-msg-body > .lf-msg-text",
          );
          if (body && body !== session.messageViewport.body) {
            session.messageViewport.stopRegion?.();
            body.scrollTop = session.messageViewport.scroll;
            session.messageViewport.body = body;
            // Adoption retains the editor's viewport inside the transcript. It is
            // a reading region of its own while that inner viewport stands.
            session.messageViewport.stopRegion = registerReadingRegion({
              id: `${THREAD_CARD}:submitted`,
              host: body,
              body,
            });
          }
        }
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale } = session.side.landed(position);
        // An unchanged declaration is the browser's own no-op, and `keeps` is the rest's.
        placementDriver.stand(position);
        preview.style.removeProperty("visibility");
        session.withheldFocus?.();
        session.withheldFocus = null;
        const card = placementDriver.clientBox(position);
        session.away = card.bottom <= boundary.top || card.top >= boundary.bottom;
        // Leaving with what it is about, the card passes under the chrome, which stacks
        // over it, and a reading region it stands in cuts it at the region's edge as it
        // cuts the words. An edge further out than the card paints cuts nothing, and
        // stands at that reach, so a scroll that moves it there writes nothing.
        const region = boundary.inRegion;
        if (region) {
          const reach = -paintReach(preview);
          const inset = [
            (region.top - card.top) / scale.y,
            (card.right - region.right) / scale.x,
            (card.bottom - region.bottom) / scale.y,
            (region.left - card.left) / scale.x,
          ].map((cut) => Math.max(cut, reach));
          preview.style.clipPath = `inset(${inset.map(layoutPx).join(" ")})`;
        } else preview.style.removeProperty("clip-path");
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
    if (!session || session.positionFrame) return;
    session.positionFrame = nextRender(() => {
      session.positionFrame = 0;
      if (previewSession === session) placeThreadPreview();
    });
  }
  // The card hangs from another entry, and a user standing on the entry it hung from goes
  // with it: the same place, the thread's own entry, under a new control.
  function transferThreadCard(
    button,
    carry = document.activeElement === previewSession?.control,
  ) {
    if (previewSession?.control === button) return;
    forgetThreadPreviewPlacement();
    previewSession.control = button;
    if (carry) focusDestination(button, "return");
  }

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
      away: false,
      positionFrame: 0,
      positionResult: null,
      focusPending: null,
      withheldFocus: null,
      transition: null,
      messageViewport: null,
      transcript: null,
      place: null,
      stopRegion: null,
      side: commentPlacement(),
    };
    carryCommentFrame(origin);
    if (origin) previewSession.side.adopt(origin.frame);
    return previewSession;
  }

  function buildThreadCard(entry, requestedItem = null) {
    const restoreFocus = holdFocus(preview);
    const focusedItem = restoreFocus
      ? (document.activeElement.closest?.("[data-lf-margin-entry]")?.lfMarginItem ??
        null)
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
      setChildren(previewList, selected ? [previewItemNode(selected)] : []);
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
      if (session.arriving) showLatestTurn(session.transcript);
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
        // A resolved thread with no draft has no margin card, so resolving closes it and
        // hands the user to its target, and a resolve that no longer stands opens the
        // card on the thread again, while the margin is still where threads open.
        prepareLanding: () => {
          const target = targetFor(previewSession?.entry);
          const thread = sourceItem(item).thread.id;
          const mayLand = retainUserIntent({
            source: focused(),
            available: () => Boolean(target?.isConnected) && !panelIsOpen(),
            fallback: bannerControlDoor(mapButton),
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
    return origin ? revealThread(origin, positioned) : positioned;
  }

  function refresh(
    entry,
    control,
    carry = document.activeElement === previewSession?.control,
  ) {
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
    preview.style.removeProperty("clip-path");
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

  function focusTarget(id, { part = null } = {}) {
    id = threadNames(allThreads()).get(id)?.id ?? id;
    const thread = [...previewList.querySelectorAll(".lf-page-thread")].find(
      (candidate) => candidate.dataset.thread === id,
    );
    return thread ? threadFocusDestination(thread, { part: part ?? "thread" }) : null;
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
    chromeRoot.insertBefore(preview, chromeForeground);
    previewRegionMounted = true;
    if (previewSession) syncPreviewTranscript();
  }

  return {
    element: preview,
    isOpen: previewOpen,
    selection,
    show,
    refresh,
    close,
    focusThread,
    focusTarget,
    thread: () => previewList.querySelector(".lf-page-thread"),
    accompanied: () =>
      previewSession && !previewSession.away
        ? previewList.querySelector(".lf-page-thread")
        : null,
    closeFocused: () => focused() === previewClose,
    threadTransitionOrigin,
    place: placeThreadPreview,
    schedulePosition: scheduleThreadPreviewPosition,
    mount,
  };
}
