/* Core Thread destinations and held identity.

   Where a thread about a passage opens is the user's choice (threads-in-panel.js):
   beside its passage, as a card, until they choose the floating panel with a card's
   Open in panel, and in the panel until its Show on page chooses cards again. Every
   route that names no reader follows the choice: `t` and Shift+t, a press on a
   passage's mark, a row of the panel's lists, the next thread a Resolve there moves on
   to, a link naming the thread, Page Map, and a return to the thread, as taking back a
   settlement does (records/undo.js). The user chose the two places and the two presses that
   switch between them, with cards the default, and adopted a review's rules for the
   rest: the placements Leaf forces (below) never change the choice; a route that
   moves the page into the panel still brings the thread's passage into view (below);
   the choice lasts for the tab, and its two presses say so; and `t` from a thread in
   the panel stays there. That last rule needs no code of its own: under the panel
   choice every route opens a thread there, and under the cards choice only a forced
   placement puts a passage's thread in the panel, from which `t` goes on to the next
   thread's card.

   A registered primary reader is asked first. Its `open(key, request)` may decline,
   returning false: Leaf's own chrome, the floating panel, declines a thread about a
   passage under the cards choice, which opens beside its passage, and takes it under
   the panel's (panel/floating-panel.js, `reveal`). A message whose widgets the primary holds
   goes there even where it declines (messages.js, `authoredHolders`). A part the
   primary declined uses the page's nearest drawing of its thread: the outlet a widget
   seats it in (surfaces.js, `surfaceFocusTarget`), whose Resolved disclosure opens for
   a resolved thread; then a page preview. A message
   part lands on its message there, or on the thread where the message has no row of
   its own (focus.js, `threadFocusDestination`). Where neither shows it, the primary is
   asked again with `request.last` set, which says
   nothing else will show the thread, so the floating panel takes any thread then; a
   second refusal leaves the thread unopened. These are the placements Leaf forces,
   whatever the user chose: a resolved thread, which no card draws; one whose passage
   the page doesn't draw; and every thread about a passage on a window with no room for
   the rail, where no margin card stands (margin-projection.js, the user's choice). A
   thread about the whole page always opens in the panel, which never declines one. The
   primary holds a forced thread only until
   the page can draw it again, as when a wider window brings the rail, or shows the
   passage a narrow one hid: once a thread pass has drawn every surface, it goes back to
   the page, and the user in it goes with it, a reply they are writing carried with its
   caret and undo history (`returnToPage`), though only under the cards choice, since
   under the panel's the page draws no card (margin-projection.js, `showPreview`). A
   route to the page alone
   (`reader: "page"`), Show on page's and that return, asks the primary only to put its
   view away once the page shows the thread (`request.page`), which the floating panel
   does under either choice; where the page shows the thread's place but
   no view of it, a route that travels lands on the place. A route to the primary alone
   (`reader: "primary"`) returns the user to a thread they had there, as a live revision
   carrying the panel's view across does (panel/floating-panel.js, `restoreCurrentLocation`):
   the primary is asked as the last resort is, and keeps the thread once the page could
   draw it, unless it holds it already as a placement Leaf forced (below). A route to a
   card (`reader: "card"`) returns the user to a thread they had read beside its
   passage, as Back to such an entry does (records/thread/address.js): it opens
   as a route under the cards choice does, whatever the choice now, the card standing
   where it can and the placements Leaf forces taking the thread where it can't. A
   route to where a thread stands (`reader: "standing"`) takes the reader of the view
   that shows the thread: the primary where its view does, the page's (`"card"`) where
   a card or a widget's seat does, and none where nothing shows it, which then follows
   the choice. It reads that from the drawing of the thread itself, not of the part
   asked for, which may stand folded inside it; the route then goes as one to that
   reader does, revealing the part and recording the trip as every route does. A draft's
   return fills the box of the view the entry's return opened (records/history.js), and a
   reload's hand-back of the reply being written the box of the view the user writes in
   (features/version.js), so neither moves the thread to where the choice says once the entry's
   record has said where the user stands. A route that asks the primary for a thread it
   already holds leaves the reason it holds it, which belongs to the placement rather
   than the route: one Leaf placed there still goes back to the page once it can.

   A route that travels into the primary brings the thread's passage into view as well
   as the primary's view of it (`taken`): nearest, in the room the floating panel's view
   leaves (dom/geometry.js, `landingInsets`), and not at all where the passage already
   shows. Its departure counts as moving the page only where the passage is out of
   view. Without the landing, a thread in the panel stands apart from the words it is
   about, where comparable products scroll the document to a comment's place. A route
   that doesn't travel, as a press on the passage's words, moves the page only where the
   view now stands over the passage, as far as brings it clear, as a freshly opened card
   may scroll to open clear of its target (browser/AGENTS.md, "A box floating over the
   page grows inside the window"). A thread about an element an agent sent
   in a message has no drawing beside its subject: `openThreadSubject` opens that
   message and lands on the element there.
   A route shows one thread at a time: the primary taking a thread closes the page's
   card, and the page drawing one has the floating panel put away its view of any
   thread as it declines (panel/floating-panel.js, `reveal`), so the reply the field holds
   and a walk's position name the thread the user arrived at. The user chose this,
   so a `t` walk doesn't leave the panel's thread open under a card.
   The optional preview supplies physical
   opening, placement proof, current focus node and target accompaniment; it owns
   no destination policy. A command retains its original intent through placement
   and returns its actual focus destination. A route that names no part lands where
   opening a thread does (focus.js, `openingPart`), on a seat, a card or the primary
   alike: a Page Map row and Show on page, by a press in the reply and by a key on the
   thread.
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
   reply part without focus.
   A focused primary arrival uses page travel's ordinary arrival, which clears a
   surface covering the native reader before disclosure, focus and placement. A
   travelling arrival captures its return place before it releases held content,
   changes layout or asks any reader, since the panel puts its view away as it
   declines a thread the page draws. It commits that place only after the destination
   is reached.

   Held identity is the focused Thread across shadow roots. An unheld conversation
   drawn with its page target, by the preview accompanying the target or by a widget's
   seat beside it, is the current conversation while the user is at that target,
   so every thread key reaches it from there (`threadHere`); when focus returns to the
   body, a visible accompanying preview remains the current conversation. Canonical page targets always come from anchor
   placement, independently of whichever view draws a Thread. */
import { aborted } from "../../base/abort.js";
import { threadDraft } from "../drafts.js";
import { focusDestination, focused, onCurrentLocation } from "../../dom/focus.js";
import { presented } from "../../dom/geometry.js";
import { restrictUserIntent, retainUserIntent } from "../../dom/user-intent.js";
import { replyThreadKey } from "./replies.js";
import { threadNamed } from "./state.js";
import { heldThread, openingPart, threadIn } from "./focus.js";
import { showHeld } from "./held-news.js";
import { surfaceFocusTarget } from "./surfaces.js";
import { reveal } from "../../dom/widget-elements.js";
import { visibleTargetParts } from "../../readings/visible-target-parts.js";
import { renderedUnder, closestAcross } from "../../lib/shadow-tree.js";
import { deleted, discussed, editable } from "../../state/thread/model.js";
import { openMessageEditIn } from "./message-edit.js";
import { authoredHolder } from "./messages.js";
import { drawnThreadId, THREAD } from "./selectors.js";
import { threadPlace as placementOf } from "./placement.js";
import { awaitsDrawing } from "../../readings/anchor-resolution.js";
import type { NavigationStep, Arrive } from "../../dom/arrival-plan.js";
import type { UserIntent } from "../../dom/user-intent.js";
import type { Side } from "@floating-ui/dom";
import type { createPrimaryReader } from "./primary-reader.js";
import type { ThreadPlacements } from "./placement.js";

type ThreadRecord = NonNullable<ReturnType<typeof threadNamed>>;
export type ThreadPart = "thread" | "reply" | "message" | null;
/** Where the comment box stood as Send was pressed, which the card Send opens grows from
 * (annotations/annotation-overlay/composing/floating-response.js, `frame`): its box, its
 * placement as the comment box's placement captured it, which the card's adopts
 * (annotations/annotation-overlay/comment-placement.js, `capture`, `adopt`), the width the
 * card starts at, the field it grows out of, and how far the words stood above their end.
 * A route carries it from the composer to the card. */
export type CapturedPlacement = {
  side: Side | null;
  boundary: readonly [number, number, number, number] | null;
  moved: boolean;
  holds: "left" | "right" | null;
};
export type SendFrame = {
  box: DOMRect;
  placement: CapturedPlacement;
  width: number;
  field: DOMRect;
  fromEnd: number;
};
/** The margin's thread card, where the overlay draws one
 * (annotations/annotation-overlay/margin-projection.js, `threadPreview`). */
type ThreadPreview = {
  accompanied: () => Element | null;
  focusTarget: (
    id: string,
    options: { part: ThreadPart },
  ) => ReturnType<typeof surfaceFocusTarget>;
  close: () => unknown;
  control: (id: string) => Element | null;
  open: (
    id: string,
    options: { origin: SendFrame | null; card: boolean },
  ) => { presented: PromiseLike<unknown> } | null | undefined | false;
};
type PrimaryRequest = {
  part: ThreadPart;
  message: string | null;
  focus: boolean;
  last: boolean;
  page: boolean;
  signal: AbortSignal;
  current: () => boolean;
};
export type OpenPrimary = (
  key: string,
  request: PrimaryRequest,
) => boolean | void | PromiseLike<boolean | void>;
type Presentation = {
  owner: Element;
  open: OpenPrimary;
  reader: ReturnType<typeof createPrimaryReader>;
};
export function createThreadDestinations({
  placedAt,
  threadIdsAt,
  scrollToThread,
  revealThread,
  arrive,
  prepareNavigationStep,
  preview = null,
}: {
  placedAt: ThreadPlacements["placedAt"];
  threadIdsAt: (node: Element) => readonly string[];
  scrollToThread: (
    id: string,
    options: {
      part?: ThreadPart;
      focus?: boolean;
      presented?: PromiseLike<unknown> | null;
      intent?: UserIntent | undefined;
      departure: NavigationStep | null;
      block?: "center" | "nearest";
      drawn?: boolean;
    },
  ) => Promise<boolean>;
  revealThread: (id: string, intent: UserIntent | undefined) => Promise<boolean>;
  arrive: Arrive;
  prepareNavigationStep: () => NavigationStep;
  preview?: ThreadPreview | null;
}) {
  let presentation: Presentation | null = null;
  let opening: AbortController | null = null;
  // The keys of the threads the primary was handed as the last resort (`request.last`),
  // which nothing on the page drew when they were asked for.
  const lastResort = new Set<string>();
  function register(owner: Element, open: OpenPrimary, reader: Presentation["reader"]) {
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
  const threadTarget = (id: string) => placedAt(id)?.place ?? null;
  // Whether the page draws the place a thread is about.
  const placeDrawn = (id: string) => {
    const place = threadTarget(id);
    return place !== null && visibleTargetParts(place).length > 0;
  };
  // Where the thread stands in the page's order, as the walks sort it: its target, or
  // the section its anchor names where the passage no longer resolves.
  const threadPlace = (id: string) => {
    const thread = threadNamed(id);
    return thread ? placementOf(thread, placedAt) : null;
  };
  // The thread the user is at, the one every thread key acts on: the thread they hold,
  // else the one conversation drawn with the place they stand at, which is one place
  // with it (glossary, Current target). The preview accompanying the place draws one,
  // and a widget may seat its threads beside it, as lf-diff does under a line; where
  // several are drawn there, the user is at none of them. Chrome standing at no place
  // is at none. Returning to the page can leave a margin card open with focus on the
  // body, and its visible conversation remains the current one in that state. A walk
  // asks the same of the node its origin was read from (records/current-target.js).
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
  let lastIn: string | null = null;
  onCurrentLocation((node) => {
    lastIn = drawnThreadId(threadIn(node)) ?? lastIn;
  });
  const threadAtCurrentLocation = (active = focused()) => {
    const here = drawnThreadId(threadHere(active));
    if (here) return here;
    const ids = active ? threadIdsAt(active) : [];
    return (ids.some((id) => id === lastIn) ? lastIn : ids[0]) ?? null;
  };
  const addressedPart = (thread: ThreadRecord, id: string, part: ThreadPart) => ({
    part,
    message:
      part === "message"
        ? (thread.msgs.find((message) => message.id === id)?.key ?? null)
        : null,
  });
  // Prefer a shown destination in the same order opening asks: the primary reader,
  // then the page's own surfaces. Otherwise return a retained node to reveal; a
  // hidden primary's retained rows must not mask the page's open card. An arrival on
  // the page (`page`) lands on the page's drawing, never on the primary's view: the
  // primary declined the thread or is about to put its view away, and its view can
  // still draw the message, as On Me's card does, closing as the user arrives, which
  // would leave them on nothing.
  const threadFocusTarget = (
    id: string,
    { part = null, page = false }: { part?: ThreadPart; page?: boolean } = {},
  ) => {
    const thread = threadNamed(id);
    const primary =
      !page && thread && presentation?.owner.isConnected
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

  type OpenThreadOptions = {
    part?: "thread" | "reply" | "message" | null;
    focus?: boolean;
    travel?: boolean;
    history?: boolean;
    scroll?: boolean;
    intent?: ReturnType<typeof retainUserIntent>;
    origin?: SendFrame | null;
    reader?: "page" | "primary" | "card" | "standing" | null;
  };
  async function openPageThread(
    id: string,
    {
      part = null,
      focus = true,
      travel = true,
      history = true,
      scroll = true,
      intent = retainUserIntent(),
      origin = null,
      reader = null,
    }: OpenThreadOptions = {},
  ) {
    if (!intent()) return null;
    part ??= openingPart();
    if (reader === "standing") {
      const shown = threadFocusTarget(id, { part: "thread" });
      reader =
        !shown || !presented(shown)
          ? null
          : presentation?.owner.isConnected && renderedUnder(shown, presentation.owner)
            ? "primary"
            : "card";
    }
    const page = reader === "page";
    const card = reader === "card";
    // A navigation step moves the page, so a destination that may move no scroller takes none.
    const navigationStep = travel && scroll;
    // The return place, read before any reader is asked (the header).
    const departure = navigationStep && history ? prepareNavigationStep() : null;
    const selected = presentation?.owner.isConnected ? presentation : null;
    const thread = threadNamed(id);
    const primary =
      selected && thread && discussed(thread) ? { selected, thread } : null;
    if (selected && !primary) return null;
    // A message whose widgets the primary reader holds is reached there, in whichever
    // of its views draws it, though the reader declines to show the thread.
    const holder = part === "message" ? authoredHolder(id) : null;
    const drawn = Boolean(selected && holder && renderedUnder(holder, selected.owner));
    // Whether the thread is on a part its widget hasn't drawn, or has drawn where the
    // page doesn't show it, as in a file the user closed or a line a diff's search
    // hides, so travel has the widget show the part (`onPage`, `inPrimary`).
    const partUndrawn = () => {
      const anchor = threadNamed(id)?.anchor;
      const placement = placedAt(id);
      return Boolean(
        placement &&
        (anchor?.datum || anchor?.visual) &&
        (awaitsDrawing(anchor, placement) || !placeDrawn(id)),
      );
    };
    // The registered primary reader, asked to show the thread: `last` says nothing on the
    // page will show it if the reader declines, and `resort` that the page could not,
    // so the thread goes back to the page once it can (`returnToPage`).
    function inPrimary(
      { selected, thread }: NonNullable<typeof primary>,
      last: boolean,
      resort = last,
    ) {
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = aborted(abort.signal);
      const whileCurrent = <T>(work: T | PromiseLike<T>) =>
        Promise.race([work, cancelled]);
      const request = {
        ...addressedPart(thread, id, part),
        focus,
        last,
        page: page || card,
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
      // A thread the primary already holds keeps the reason it holds it (the header).
      const holds = selected.reader
        .destination(thread.key, { part: "thread" })
        ?.checkVisibility();
      if (resort) lastResort.add(thread.key);
      else if (!holds) lastResort.delete(thread.key);
      const result = selected.open(thread.key, request);
      if (result === false) lastResort.delete(thread.key);
      // A reader that declines at once is answered at once, so the page's own drawing
      // of the thread opens in the task of the gesture that asked for it (`onPage`), as
      // a walk's card does, rather than after a wait that no longer belongs to it.
      if (result === false && !drawn) return mayPresent() ? DECLINED : null;
      // The reader shows the thread, so the card standing beside another thread's
      // passage goes, in the same task, and one thread stands open.
      if (result !== false && preview) intent.handoff(preview.close);
      // A route that travels brings the passage into view after the reader's view
      // (below); the widget starts drawing its part in the gesture's own task, as on
      // the page (`onPage`), so a search that hid it gives way to this gesture rather
      // than to a wait after it. A thread the primary holds as the last resort goes
      // back to the page once the page draws it (`returnToPage`), so its part is
      // drawn only after the user lands in the reader's view, which hands that
      // return the reply they are writing.
      if (
        result !== false &&
        navigationStep &&
        !lastResort.has(thread.key) &&
        partUndrawn()
      )
        void revealThread(id, intent);
      return taken(result);
      // The reader takes the thread: its layout, then its drawing of it.
      async function taken(result: ReturnType<OpenPrimary>) {
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
        // The user lands in the reader's view at once. The page then brings the
        // thread's passage into view, as travel to its card does (features/anchor-travel.js,
        // `scrollToThread`): after a route that travels, wherever the passage is, the
        // widget holding it drawing it; after one that doesn't, as a press on the
        // passage, only where the page draws it, so a passage the view opened over comes
        // clear of it. Focus stays in the view (the header). The route's departure is
        // planned on the view, a Back step where the user lands in a thread they weren't
        // in (features/anchor-travel.js, `prepareNavigationStep`), and planned again by where the
        // passage's landing puts the passage. It commits once the last landing is
        // reached, so a thread with no passage on the page, one about the whole page or
        // one whose passage a revision removed, is a step as well.
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
            { intent: arriving },
          ),
        );
        if (!reached) return null;
        if (thread.anchor && (navigationStep || (scroll && placeDrawn(thread.id))))
          await whileCurrent(
            scrollToThread(thread.id, {
              part: null,
              focus: false,
              intent: arriving,
              departure,
              block: "nearest",
              drawn: !navigationStep,
            }),
          );
        if (!mayPresent()) return null;
        departure?.commit();
        return selected.reader.destination(thread.key, request);
      }
    }
    // The page's own drawings of the thread: its outlet or seat, a preview. Its
    // arrival lands there, never on the primary's view (`threadFocusTarget`'s `page`).
    async function onPage() {
      const mayPresent = () => (focus === false ? intent.available() : intent());
      // A thread on a part its widget hasn't drawn, or has drawn where the page doesn't
      // show it, as in a file the user closed, moves there or gains a seat beside it
      // once the widget shows the part, so travel has the widget show it before choosing
      // which of the page's drawings shows the thread (readings/anchor-resolution.js,
      // `awaitsDrawing`).
      if (navigationStep && partUndrawn() && !(await revealThread(id, intent)))
        return null;
      // A route to a message is an arrival at it, so a seat holding it back shows it.
      if (part === "message") showHeld(id);
      const openSurface = async () => {
        // A passive continuation keeps the reader's chosen file, tab or disclosure.
        // Its hidden outlet cannot be the route without revealing that subject again.
        const surface = surfaceFocusTarget(id, { part });
        if (!scroll && (!surface || !presented(surface))) return DECLINED;
        if (preview) intent.handoff(preview.close);
        if (navigationStep) {
          // Travel lands on the thread's place, so a disclosure holding the drawing
          // closed there, as a seat's Resolved disclosure holds a resolved thread,
          // opens first.
          if (surface) await reveal(surface, intent).ready;
          if (!mayPresent()) return null;
          if (!(await scrollToThread(id, { part, focus, intent, departure })))
            return null;
        } else if (focus === false) {
          if (scroll) await reveal(surfaceFocusTarget(id, { part }), intent).ready;
          if (!mayPresent()) return null;
        } else if (
          !(await arrive(
            () => {
              const current = surfaceFocusTarget(id, { part });
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
        return surfaceFocusTarget(id, { part });
      };
      if (surfaceFocusTarget(id, { part })) return openSurface();
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
      const invocation: {
        opened: ReturnType<
          NonNullable<Parameters<typeof createThreadDestinations>[0]["preview"]>["open"]
        >;
      } = { opened: null };
      if (preview && (!place || placeDrawn(id)))
        intent.handoff(() => {
          invocation.opened = preview.open(id, { origin, card });
        });
      const opened = invocation.opened;
      if (opened) {
        if (navigationStep) {
          if (
            !(await scrollToThread(id, {
              part,
              focus,
              presented: opened.presented,
              intent,
              departure,
            }))
          )
            return null;
        } else {
          if (!(await opened.presented) || !mayPresent()) return null;
          if (
            focus !== false &&
            !(await arrive(
              () => {
                const current = threadFocusTarget(id, { part, page: true });
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
        return threadFocusTarget(id, { part, page: true });
      }
      return DECLINED;
    }

    if (reader === "primary") {
      const kept = primary ? await inPrimary(primary, true, false) : null;
      return kept === DECLINED || kept === UNDRAWN ? null : kept;
    }
    // A route to the page alone (`reader: "page"`), as Show on page and `returnToPage`
    // are, draws the thread on the page first, and asks the primary only once the page
    // shows it, so it puts its view away as it declines, handing on the reply being
    // written there.
    // Where the page shows the thread's place but draws no view of it, as a window with
    // no room for the rail does (margin-projection.js), a route that travels brings that
    // place into view and lands on the margin control standing for the thread, whose
    // focus traces the place (`refreshHighlight`) after a pointer's press as after a
    // key's, and from which a tap or Enter opens the thread again; with no margin, on the
    // place itself, its current target. Bringing the place into view can draw a view of
    // the thread there after all, as a widget's seat does once the file holding its line
    // loads, replacing the control that stood for it: the route lands in that seat, as on
    // a wide window, at every width.
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
      const control = focus ? (preview?.control(id) ?? null) : null;
      const arrived = await scrollToThread(id, {
        part: null,
        focus: focus && !control,
        intent,
        departure,
      });
      if (!arrived) return null;
      if (focus && surfaceFocusTarget(id, { part })) {
        const seated = await arrive(
          () => {
            const current = surfaceFocusTarget(id, { part });
            return (
              current && {
                where: current,
                focus: current,
                scroll: [{ at: current, block: "nearest" }],
              }
            );
          },
          { intent },
        );
        if (!seated) return null;
        if (primary) await inPrimary(primary, false);
        return surfaceFocusTarget(id, { part });
      }
      if (!control) return threadTarget(id);
      intent.handoff(() => focusDestination(control, "move"));
      return control;
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
      const thread = threadNamed(key);
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
        reader: "page",
      });
    }
  }

  // Where a thread about an element an agent sent in a message goes to its subject: the
  // message stands in for a place on the page (annotations/anchor-placement.js), so the message's
  // thread opens there without moving focus, as a thread ask's does (records/obligations/view.js), and
  // the user lands on the element in it. A thread whose subject stands on the page goes
  // there by opening itself, beside its words.
  async function openThreadSubject(
    id: string,
    {
      intent = retainUserIntent(),
    }: { intent?: ReturnType<typeof retainUserIntent> } = {},
  ) {
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
  async function openThreadDraft(
    context: string,
    intent: ReturnType<typeof retainUserIntent>,
    { travel = true }: { travel?: boolean } = {},
  ) {
    const route = threadDraft(context);
    if (!route) return null;
    const { part, name } = route;
    const thread = threadNamed(name);
    if (!thread) return null;
    if (part === "reply")
      return openPageThread(thread.id, {
        part: "reply",
        intent,
        travel,
        reader: "standing",
      });
    const landed = await openPageThread(name, {
      part: "message",
      intent,
      travel,
      reader: "standing",
    });
    const card = landed && closestAcross(landed, THREAD);
    return card ? openMessageEditIn(card, name) : null;
  }
  // The thread a thread-held draft is written under: the thread a reply is keyed by, or
  // the one holding the message a rewrite is of; none once it has left the log's
  // reading, and none for a rewrite of a message the user may no longer rewrite, as one
  // taken back while an answer stands on it, which opens no editor.
  function threadHolding(context: string) {
    const route = threadDraft(context);
    const thread = route ? threadNamed(route.name) : null;
    if (!thread || route?.part !== "rewrite") return thread;
    const message = thread.msgs.find(({ id }) => id === route.name);
    return message && editable(message) && !deleted(message) ? thread : null;
  }

  return {
    register,
    openPageThread,
    openThreadSubject,
    openThreadDraft,
    returnToPage,
    // Whether the page shows the thread `key` names, or at least its place, so a route
    // to the page alone has somewhere to go: false for a thread whose passage no longer
    // resolves, and for one the primary holds as the last resort while the page draws
    // its place nowhere.
    showsOnPage: (key: string) => {
      const thread = threadNamed(key);
      if (!thread) return true;
      return lastResort.has(key)
        ? placeDrawn(thread.id)
        : threadTarget(thread.id) !== null;
    },
    holdsThreadDraft: (context: string) => Boolean(threadHolding(context)),
    threadFocusTarget,
    threadHere,
    threadAtCurrentLocation,
    threadTarget,
    threadPlace,
  };
}
