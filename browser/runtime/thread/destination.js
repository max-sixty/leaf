/* Core Thread destinations and held identity.

   A registered primary reader is asked first. Its `open(key, request)` may decline,
   returning false: Leaf's own chrome, the floating panel, declines a thread about a
   passage, which opens beside its passage. A message whose widgets the primary holds
   goes there even where it declines (messages.js, `authoredHolders`). A part the
   primary declined uses the page's nearest drawing of its thread: the exact outlet,
   then a page preview, then a deliberately revealed widget seat; a message part lands
   on its message there. Where none of
   those shows it, the primary is asked again with `request.last` set, which says
   nothing else will show the thread, so the floating panel takes any thread then; a
   second refusal leaves the thread unopened. That is every thread about a passage on a
   window with no room for the rail, where no margin card stands (margin-projection.js,
   the user's choice of 31 October 2026). The primary holds such a thread only until
   the page can draw it again, as when a wider window brings the rail, or shows the
   passage a narrow one hid: once a thread pass has drawn every surface, it goes back to
   the page, and the user in it goes with it, a reply they are writing carried with its
   caret and undo history (`returnToPage`). A route to the page alone (`page`), Show on
   page's and that return, asks the primary only to put its view away once the page
   shows the thread; where the page shows the thread's place but no view of it, a route
   that travels lands on the place. A thread about an element an agent sent
   in a message has no drawing beside its subject: `openThreadSubject` opens that
   message and lands on the element there.
   A route shows one thread at a time: the primary taking a thread closes the page's
   card, and the page drawing one has the floating panel put away its view of any
   thread as it declines (floating-panel.js, `reveal`), so the reply the field holds
   and a walk's position name the thread the user arrived at. The user chose this on
   23 October 2026, after a `t` walk left the panel's thread open under a card.
   A compact preview keeps held widget arrivals held until its own release gesture.
   The optional preview supplies physical
   opening, placement proof, current focus node and target accompaniment; it owns
   no destination policy. A command retains its original intent through placement
   and returns its actual focus destination. Surface defaults enter the reply and
   compact previews default to the thread.
   `travel: false` keeps the page under the gesture while revealing its destination;
   `history: false` arrives at an address the browser already navigated to, revealing
   its passage without adding another return stop.
   `scroll: false` also leaves every scroller where it stands, for a continuation into
   a box the user had scrolled away from.
   A native continuation (`focus: false`) returns its presented route under session
   availability even after Tab supersedes positioning; it never takes focus, and the
   original intent alone permits scrolling or another reveal gesture.
   Addressed part and focus are independent. Materializing a thread obligation asks
   for its message part without focus; a native editing continuation asks for the
   reply part without focus. Omitting part follows each surface's ordinary route.
   A focused primary arrival uses page travel's ordinary arrival, which clears a
   surface covering the native reader before disclosure, focus and placement. A
   travelling arrival captures its return place before releasing held content or
   changing layout and commits it only after the destination is reached.

   Held identity is the focused Thread across shadow roots. An unheld conversation
   drawn with its page target, by the preview accompanying the target or by a widget's
   seat beside it, is the current conversation while the user is at that target,
   so every thread key reaches it from there (`threadHere`); when focus returns to the
   body, a visible accompanying preview remains the current conversation. Canonical page targets always come from anchor
   placement, independently of whichever view draws a Thread. */
import { aborted } from "../abort.js";
import { threadDraft } from "../drafts.js";
import { focused, onCurrentLocation } from "../focus.js";
import { presented } from "../geometry.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { replyThreadKey } from "./replies.js";
import { allThreads, threadIdNamed, threadNamed } from "./state.js";
import { heldThread, threadIn } from "./focus.js";
import { showHeld, showHeldThread } from "./held-news.js";
import { revealHeld, surfaceFocusTarget } from "./surfaces.js";
import { reveal } from "../widget-elements.js";
import { visibleTargetParts } from "../visible-target-parts.js";
import { closestAcross } from "../passages.js";
import { renderedUnder } from "../shadow.js";
import { discussed, threadKey } from "./model.js";
import { openMessageEditIn } from "./message-edit.js";
import { authoredHolder } from "./messages.js";
import { drawnThreadId, THREAD } from "./selectors.js";
import { threadPlace as placementOf } from "./placement.js";

/** @typedef {ReturnType<typeof allThreads>[number]} ThreadRecord */
/** @typedef {"thread" | "reply" | "message" | null} ThreadPart */
/** @typedef {{part: ThreadPart, message: string | null, focus: boolean,
 * last: boolean, signal: AbortSignal, current: () => boolean}} PrimaryRequest */
/** @typedef {(key: string, request: PrimaryRequest) => boolean | void | PromiseLike<boolean | void>} OpenPrimary */
/** @typedef {{owner: Element, open: OpenPrimary,
 * reader: ReturnType<typeof import("./primary-reader.js").createPrimaryReader>}} Presentation */
/** @param {{placedAt: ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["placedAt"],
 * threadIdsAt: (node: Element) => readonly string[],
 * scrollToThread: ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["scrollToThread"],
 * arrive: ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["arrive"],
 * prepareNavigationStep: ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["prepareNavigationStep"],
 * preview?: ReturnType<typeof import("../annotation-overlay/margin-projection.js").createMarginProjection>["threadPreview"] | null}} dependencies */
export function createThreadDestinations({
  placedAt,
  threadIdsAt,
  scrollToThread,
  arrive,
  prepareNavigationStep,
  preview = null,
}) {
  /** @type {Presentation | null} */
  let presentation = null;
  /** @type {AbortController | null} */
  let opening = null;
  // The keys of the threads the primary was handed as the last resort (`request.last`),
  // which nothing on the page drew when they were asked for.
  /** @type {Set<string>} */
  const lastResort = new Set();
  /** @param {Element} owner @param {OpenPrimary} open
   * @param {Presentation["reader"]} reader */
  function register(owner, open, reader) {
    if (presentation) throw new Error("The page already has a Thread presentation");
    const registration = { owner, open, reader };
    presentation = registration;
    return () => {
      if (presentation === registration) {
        presentation = null;
        opening?.abort();
      }
    };
  }
  /** @param {string} id */
  const threadTarget = (id) => placedAt(id)?.place ?? null;
  // Whether the page draws the place a thread is about.
  /** @param {string} id */
  const placeDrawn = (id) => {
    const place = threadTarget(id);
    return place !== null && visibleTargetParts(place).length > 0;
  };
  // Where the thread stands in the page's order, as the list sorts it: its target, or
  // the section its anchor names where the passage no longer resolves.
  /** @param {string} id */
  const threadPlace = (id) => {
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread ? placementOf(thread, placedAt) : null;
  };
  // The thread the user is at, the one every thread key acts on: the thread they hold,
  // else the one conversation drawn with the place they stand at, which is one place
  // with it (glossary, Current target). The preview accompanying the place draws one,
  // and a widget may seat its threads beside it, as lf-diff does under a line; where
  // several are drawn there, the user is at none of them. Chrome standing at no place
  // is at none. Returning to the page can leave a margin card open with focus on the
  // body, and its visible conversation remains the current one in that state. A walk
  // asks the same of the node its origin was read from (current-target.js).
  const threadHere = (active = focused()) => {
    const held = threadIn(active);
    if (held) return held;
    const shown = preview?.accompanied() ?? null;
    if (!active || active === document.body) return shown;
    const ids = threadIdsAt(active);
    const drawn = [
      shown,
      ...ids.map((id) => surfaceFocusTarget(id, { part: "thread" })),
    ]
      .filter((thread) => thread !== null)
      .filter((thread) => ids.some((id) => id === drawnThreadId(thread)));
    return drawn.length === 1 ? drawn[0] : null;
  };
  // Discussion identity precedes the view that realizes it: where no thread is shown,
  // the thread at the place the user was last in, else the first there, so a walk back
  // to a place they let go of returns to the thread they left.
  /** @type {string | null} */
  let lastIn = null;
  onCurrentLocation((node) => {
    lastIn = drawnThreadId(threadIn(node)) ?? lastIn;
  });
  const threadAtCurrentLocation = (active = focused()) => {
    const here = drawnThreadId(threadHere(active));
    if (here) return here;
    const ids = active ? threadIdsAt(active) : [];
    return (ids.some((id) => id === lastIn) ? lastIn : ids[0]) ?? null;
  };
  /** @param {ThreadRecord} thread @param {string} id @param {ThreadPart} part */
  const addressedPart = (thread, id, part) => ({
    part,
    message:
      part === "message"
        ? (thread.msgs.find((message) => message.id === id)?.key ?? null)
        : null,
  });
  // Prefer a shown destination in the same order opening asks: the primary reader,
  // then the page's own surfaces. Otherwise return a retained node to reveal; a
  // hidden primary's retained rows must not mask the page's open card.
  /** @param {string} id @param {{part?: ThreadPart}} [options] */
  const threadFocusTarget = (id, { part = null } = {}) => {
    const thread = threadNamed(id);
    const primary =
      thread && presentation?.owner.isConnected
        ? presentation.reader.destination(thread.key, addressedPart(thread, id, part))
        : null;
    const candidates = [
      primary,
      surfaceFocusTarget(id, { part }),
      preview?.focusTarget(id, { part }),
    ].filter((candidate) => candidate != null);
    return candidates.find(presented) ?? candidates[0] ?? null;
  };

  // What `inPrimary` returns where the primary declined the thread, or took it and drew
  // no destination for it, so another surface may show it; and what `onPage` returns
  // where nothing on the page shows it.
  const DECLINED = Symbol("declined");
  const UNDRAWN = Symbol("undrawn");

  /** @typedef {{part?: "thread" | "reply" | "message" | null,
   * focus?: boolean, travel?: boolean, history?: boolean, scroll?: boolean,
   * intent?: ReturnType<typeof retainUserIntent>, origin?: ReturnType<ReturnType<typeof import("../annotation-overlay/composing/floating-response.js").createFloatingResponsePlacement>["frame"]>,
   * page?: boolean}} OpenThreadOptions */
  /** @param {string} id @param {OpenThreadOptions} [options] */
  async function openPageThread(
    id,
    {
      part = null,
      focus = true,
      travel = true,
      history = true,
      scroll = true,
      intent = retainUserIntent(),
      origin = null,
      page = false,
    } = {},
  ) {
    if (!intent()) return null;
    // A navigation step moves the page, so a destination that may move no scroller takes none.
    const navigationStep = travel && scroll;
    const selected = presentation?.owner.isConnected ? presentation : null;
    const thread = threadNamed(id);
    const primary =
      selected && thread && discussed(thread) ? { selected, thread } : null;
    if (selected && !primary) return null;
    // A message whose widgets the primary reader holds is reached there, in whichever
    // of its views draws it, though the reader declines to show the thread.
    const holder = part === "message" ? authoredHolder(id) : null;
    const drawn = Boolean(selected && holder && renderedUnder(holder, selected.owner));
    // The registered primary reader, asked to show the thread: `last` says nothing on the
    // page will show it if the reader declines.
    /** @param {NonNullable<typeof primary>} primary @param {boolean} last */
    function inPrimary({ selected, thread }, last) {
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = aborted(abort.signal);
      /** @template T @param {T | PromiseLike<T>} work */
      const whileCurrent = (work) => Promise.race([work, cancelled]);
      const request = {
        ...addressedPart(thread, id, part),
        focus,
        last,
        signal: abort.signal,
        current: () =>
          !abort.signal.aborted &&
          presentation === selected &&
          selected.owner.isConnected &&
          (focus === false ? intent.available() : intent()),
      };
      const mayPresent = () =>
        !abort.signal.aborted &&
        presentation === selected &&
        selected.owner.isConnected &&
        (focus === false ? intent.available() : intent());
      const arriving = restrictUserIntent(intent, mayPresent);
      const departure =
        focus !== false && navigationStep && history
          ? prepareNavigationStep({
              landing: () => selected.reader.destination(thread.key, request),
              intent: arriving,
            })
          : null;
      if (last) lastResort.add(thread.key);
      else lastResort.delete(thread.key);
      const result = selected.open(thread.key, request);
      if (result === false) lastResort.delete(thread.key);
      // A reader that declines at once is answered at once, so the page's own drawing
      // of the thread opens in the task of the gesture that asked for it (`onPage`), as
      // a walk's card does, rather than after a wait that no longer belongs to it.
      if (result === false && !drawn) return mayPresent() ? DECLINED : null;
      // The reader shows the thread, so the card standing beside another thread's
      // passage goes, in the same task, and one thread stands open.
      if (result !== false && preview) intent.handoff(preview.close);
      return taken(result);
      // The reader takes the thread: its layout, then its drawing of it.
      /** @param {ReturnType<OpenPrimary>} result */
      async function taken(result) {
        const selectedLayout =
          result instanceof Promise ? await whileCurrent(result) : result;
        if (!mayPresent()) return null;
        if (selectedLayout === false && !drawn) return DECLINED;
        await whileCurrent(selected.reader.update());
        if (!mayPresent()) return null;
        const destination = selected.reader.destination(thread.key, request);
        if (destination === null) return UNDRAWN;
        if (
          !(destination instanceof Element) ||
          !destination.isConnected ||
          !renderedUnder(destination, selected.owner) ||
          !selected.reader.ownsDestination(destination)
        )
          throw new TypeError(
            "A Thread destination must be a retained part of its registered presentation",
          );
        if (focus === false) {
          await whileCurrent(reveal(destination, intent).ready);
          return mayPresent() ? destination : null;
        }
        departure?.plan(destination);
        const reached = await whileCurrent(
          arrive(
            () => {
              const current = selected.reader.destination(thread.key, request);
              return (
                current && {
                  where: current,
                  focus: current,
                  scroll: navigationStep ? [{ at: current, block: "nearest" }] : [],
                }
              );
            },
            { intent: arriving, departure },
          ),
        );
        return reached ? selected.reader.destination(thread.key, request) : null;
      }
    }
    // The page's own drawings of the thread: its outlet, a held seat, a preview.
    async function onPage() {
      const mayPresent = () => (focus === false ? intent.available() : intent());
      const localPart = part ?? "reply";
      // A route to a message is an arrival at it, so a seat holding it back shows it.
      if (part === "message") showHeld(id);
      const openSurface = async () => {
        // A passive continuation keeps the reader's chosen file, tab or disclosure.
        // Its hidden outlet cannot be the route without revealing that subject again.
        const surface = surfaceFocusTarget(id, { part: localPart });
        if (!scroll && (!surface || !presented(surface))) return DECLINED;
        if (preview) intent.handoff(preview.close);
        if (navigationStep) {
          if (!(await scrollToThread(id, { part: localPart, focus, intent, history })))
            return null;
        } else if (focus === false) {
          if (scroll)
            await reveal(surfaceFocusTarget(id, { part: localPart }), intent).ready;
          if (!mayPresent()) return null;
        } else if (
          !(await arrive(
            () => {
              const current = surfaceFocusTarget(id, { part: localPart });
              return (
                current && {
                  where: current,
                  focus: current,
                  scroll: scroll
                    ? [{ at: current, block: "nearest", behavior: "auto" }]
                    : [],
                }
              );
            },
            { intent },
          ))
        )
          return null;
        return surfaceFocusTarget(id, { part: localPart });
      };
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      // A thread a seat holds whole has no node until the seat shows it (held-news.js).
      if (showHeldThread(id) && surfaceFocusTarget(id, { part: localPart }))
        return openSurface();
      // A card stands beside its passage while the passage is drawn
      // (`commentAttachment`), and a card with nowhere to stand never places. A navigation step
      // reveals the passage as it arrives. A thread opened where the user is reveals
      // it here, opening the tab or disclosure that holds it, unless the caller keeps
      // every scroller still, since a tab switch scrolls its strip. A passage that stays
      // hidden leaves the thread to the primary reader.
      const place = preview && !navigationStep ? threadTarget(id) : null;
      if (place && scroll && !placeDrawn(id)) {
        await reveal(place, intent).ready;
        if (!mayPresent()) return null;
      }
      /** @type {{opened: ReturnType<NonNullable<Parameters<typeof createThreadDestinations>[0]["preview"]>["open"]>}} */
      const invocation = { opened: null };
      if (preview && (!place || placeDrawn(id)))
        intent.handoff(() => {
          invocation.opened = preview.open(id, { origin });
        });
      const opened = invocation.opened;
      if (opened) {
        if (navigationStep) {
          if (
            !(await scrollToThread(id, {
              part: part ?? "thread",
              focus,
              presented: opened.presented,
              intent,
              history,
            }))
          )
            return null;
        } else {
          if (!(await opened.presented) || !mayPresent()) return null;
          if (
            focus !== false &&
            !(await arrive(
              () => {
                const current = threadFocusTarget(id, { part });
                return (
                  current && {
                    where: current,
                    focus: current,
                    scroll: scroll ? [{ at: current, block: "nearest" }] : [],
                  }
                );
              },
              { intent },
            ))
          )
            return null;
        }
        return threadFocusTarget(id, { part });
      }
      const held = revealHeld([threadIdNamed(id)]);
      if (held) {
        await held.presented;
        if (!mayPresent()) return null;
      }
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      return DECLINED;
    }

    // A route to the page alone (`page`), as Show on page and `returnToPage` are, draws
    // the thread on the page first, and asks the primary only once the page shows it,
    // so it puts its view away as it declines, handing on the reply being written there.
    // Where the page shows the thread's place but draws no view of it, as a window with
    // no room for the rail does (margin-projection.js), a route that travels lands on
    // that place, its current target, from which its words, its marker or a thread key
    // open the thread again.
    const asked = primary && !page ? inPrimary(primary, false) : DECLINED;
    const first = asked instanceof Promise ? await asked : asked;
    if (first !== DECLINED && first !== UNDRAWN) return first;
    const shown = await onPage();
    if (page) {
      if (shown && shown !== DECLINED) {
        if (primary) await inPrimary(primary, false);
        return shown;
      }
      if (!shown || !navigationStep || !placeDrawn(id)) return null;
      return (await scrollToThread(id, { part: null, focus, intent, history }))
        ? threadTarget(id)
        : null;
    }
    if (shown !== DECLINED) return shown;
    // Only a reader that declined is asked again; one that took the thread has shown it.
    if (!primary || first !== DECLINED) return null;
    const last = await inPrimary(primary, true);
    return last === DECLINED || last === UNDRAWN ? null : last;
  }

  // A thread the primary holds as the last resort goes back to the page once the page
  // can draw it, which each thread pass asks once it has drawn every surface. The page
  // draws it first, and only then does the primary put its view away, so a page that
  // still has nowhere to show it leaves the view standing. The user goes with the thread
  // from where they were in the view: from its reply box, the row itself, carried to the
  // card with its caret and undo history (replies.js, `releaseReplies`), or from the
  // thread to the card's. A user elsewhere stays there, and every scroller stays still,
  // since the user has not moved.
  async function returnToPage() {
    const selected = presentation?.owner.isConnected ? presentation : null;
    if (!selected) return;
    for (const key of [...lastResort]) {
      const thread = allThreads().find((each) => threadKey(each) === key);
      // A view the user has put away holds nothing to give back.
      const drawing = selected.reader.destination(key, { part: "thread" });
      if (!thread || !drawing?.checkVisibility()) {
        lastResort.delete(key);
        continue;
      }
      await openPageThread(thread.id, {
        part: "thread",
        focus:
          replyThreadKey(focused()) !== key &&
          drawnThreadId(heldThread()) === thread.id,
        travel: false,
        scroll: false,
        page: true,
      });
    }
  }

  // Where a thread about an element an agent sent in a message goes to its subject: the
  // message stands in for a place on the page (anchor-placement.js), so the message's
  // thread opens there without moving focus, as a thread ask's does (obligations/view.js), and
  // the user lands on the element in it. A thread whose subject stands on the page goes
  // there by opening itself, beside its words.
  /** @param {string} id @param {{intent?: ReturnType<typeof retainUserIntent>}} [options] */
  async function openThreadSubject(id, { intent = retainUserIntent() } = {}) {
    const held = placedAt(id)?.messageTarget;
    if (!held) return null;
    const { message, element } = held;
    const shown = await openPageThread(message, {
      part: "message",
      focus: false,
      travel: false,
      intent,
    });
    if (!shown || !element.isConnected) return null;
    const arrived = await arrive(
      () =>
        element.isConnected
          ? {
              where: element,
              focus: element,
              scroll: [{ at: element, block: "nearest" }],
            }
          : null,
      { intent },
    );
    return arrived ? element : null;
  }

  // Where a thread holds the user's draft `context`, with its box ready for the caret:
  // the thread's reply box, or the rewrite of one of its messages, which opens on that
  // message where a message part lands (`message-edit.js`).
  // Landed on the thread instead, a long one's landing on its latest turn took the view
  // away from a rewrite it had just opened higher up.
  /** @param {string} context @param {ReturnType<typeof retainUserIntent>} intent */
  async function openThreadDraft(context, intent) {
    const route = threadDraft(context);
    if (!route) return null;
    const thread = threadHoldingRoute(route);
    if (!thread) return null;
    const { part, name } = route;
    if (part === "reply") return openPageThread(thread.id, { part: "reply", intent });
    const landed = await openPageThread(name, { part: "message", intent });
    const card = landed && closestAcross(landed, THREAD);
    return card ? openMessageEditIn(card, name) : null;
  }
  // The thread a thread-held draft is written under: the thread a reply is keyed by, or
  // the one holding the message a rewrite is of; none once it has left the log's reading.
  /** @param {string} context */
  function threadHolding(context) {
    const route = threadDraft(context);
    return route ? threadHoldingRoute(route) : null;
  }
  /** @param {NonNullable<ReturnType<typeof threadDraft>>} route */
  function threadHoldingRoute({ part, name }) {
    return part === "reply"
      ? allThreads().find((each) => threadKey(each) === name)
      : allThreads().find((each) => each.msgs.some(({ id }) => id === name));
  }

  return {
    register,
    openPageThread,
    openThreadSubject,
    openThreadDraft,
    returnToPage,
    // Whether the page shows the thread `key` names, or at least its place, so a route
    // to the page alone has somewhere to go: false only for a thread the primary holds
    // as the last resort while the page draws its place nowhere.
    showsOnPage: (/** @type {string} */ key) => {
      const thread = lastResort.has(key)
        ? allThreads().find((each) => threadKey(each) === key)
        : null;
      return !thread || placeDrawn(thread.id);
    },
    holdsThreadDraft: (/** @type {string} */ context) =>
      Boolean(threadHolding(context)),
    threadFocusTarget,
    threadHere,
    threadAtCurrentLocation,
    threadTarget,
    threadPlace,
  };
}
