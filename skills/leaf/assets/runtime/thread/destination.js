/* Core Thread destinations and held identity.

   A registered primary reader is asked first. Its `open(key, request)` may decline,
   returning false: Leaf's own chrome, the floating panel, declines a thread about a
   passage, which opens beside its passage. A message part needs the reader that
   renders its native authored content, so it goes to the primary alone. A thread or
   reply part the primary declined uses the page's nearest drawing of it: the exact
   outlet, then a page preview, then a deliberately revealed widget seat. Where none of
   those shows it, the primary is asked again with `request.last` set, which says
   nothing else will show the thread, so the floating panel takes any thread then; a
   second refusal leaves the thread unopened. A thread about an element an agent sent
   in a message has no drawing beside its subject: `openThreadSubject` opens that
   message and lands on the element there.
   A compact preview keeps held widget arrivals held until its own release gesture.
   The optional preview supplies physical
   opening, placement proof, current focus node and target accompaniment; it owns
   no destination policy. A command retains its original intent through placement
   and returns its actual focus destination. Surface defaults enter the reply and
   compact previews default to the thread.
   `travel: false` keeps the page under the gesture while revealing its destination;
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

   Held identity is the focused Thread across shadow roots. An unheld preview
   conversation may accompany its page target; when focus returns to the body,
   a visible accompanying preview remains the current conversation. Canonical page
   targets always come from anchor placement, independently of whichever view draws a
   Thread. */
import { aborted } from "../abort.js";
import { threadDraft } from "../drafts.js";
import { scrollIntoView } from "../landing-scroll.js";
import { focusDestination, focused } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { replyAvailable } from "./replies.js";
import { allThreads, threadNamed } from "./state.js";
import { heldThread } from "./focus.js";
import { showHeldThread } from "./held-news.js";
import { revealHeld, surfaceFocusTarget } from "./surfaces.js";
import { reveal } from "../widget-elements.js";
import { closestAcross } from "../passages.js";
import { renderedUnder } from "../shadow.js";
import { discussed, threadKey } from "./model.js";
import { openMessageEditIn } from "./message-edit.js";
import { messageHolding } from "./messages.js";
import { drawnThreadId, THREAD } from "./selectors.js";
import { threadPlace as placementOf } from "./placement.js";

export function createThreadDestinations({
  placedAt,
  threadIdsAt,
  scrollToThread,
  arrive,
  prepareTrip,
  preview = null,
}) {
  let presentation = null;
  let opening = null;
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
  const threadTarget = (id) => placedAt(id)?.place ?? null;
  // Where the thread stands in the page's order, as the list sorts it: its target, or
  // the section its anchor names where the passage no longer resolves.
  const threadPlace = (id) => {
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread ? placementOf(thread, placedAt) : null;
  };
  const threadHere = () => heldThread() ?? preview?.accompanied() ?? null;
  // Discussion identity precedes the view that realizes it. Reply availability
  // narrows an editable destination without erasing the user's standing thread.
  const threadAtStanding = () => {
    const held = heldThread();
    if (held) return drawnThreadId(held);
    const active = focused();
    const ids = active ? threadIdsAt(active) : [];
    const shown = threadHere();
    const shownId = drawnThreadId(shown);
    // Returning to the page can leave a margin card open with focus on the body.
    // Its visible conversation remains the destination of Comment in that state.
    if ((!active || active === document.body) && shownId) return shownId;
    return ids.includes(shownId) ? shownId : (ids[0] ?? null);
  };
  const replyThreadAtStanding = () => {
    const id = threadAtStanding();
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread && replyAvailable(thread) ? id : null;
  };
  const threadFocusTarget = (id, { part = null } = {}) =>
    part === "message"
      ? null
      : (surfaceFocusTarget(id, { part }) ??
        preview?.focusTarget(id, { part }) ??
        null);

  // What `inPrimary` returns where the primary declined the thread, or took it and drew
  // no destination for it, so another surface may show it; and what `onPage` returns
  // where nothing on the page shows it.
  const DECLINED = Symbol("declined");
  const UNDRAWN = Symbol("undrawn");

  async function openPageThread(
    id,
    {
      part = null,
      focus = true,
      travel = true,
      flash = true,
      scroll = true,
      intent = retainUserIntent(),
      origin = null,
    } = {},
  ) {
    if (!intent()) return null;
    // A trip moves the page, so a destination that may move no scroller takes none.
    const trip = travel && scroll;
    const selected = presentation?.owner.isConnected ? presentation : null;
    const thread = threadNamed(id);
    if (selected && (!thread || !discussed(thread))) return null;
    // The registered primary reader, asked to show the thread: `last` says nothing on the
    // page will show it if the reader declines.
    function inPrimary(last) {
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = aborted(abort.signal);
      const whileCurrent = (work) => Promise.race([work, cancelled]);
      const request = {
        message:
          part === "message"
            ? (thread.msgs.find((message) => message.id === id)?.key ?? null)
            : null,
        part,
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
        focus !== false && trip
          ? prepareTrip({
              landing: () => selected.reader.destination(thread.key, request),
              intent: arriving,
            })
          : null;
      const result = selected.open(thread.key, request);
      // A reader that declines at once is answered at once, so the page's own drawing
      // of the thread opens in the task of the gesture that asked for it (`onPage`), as
      // a walk's card does, rather than after a wait that no longer belongs to it.
      if (result === false) return mayPresent() ? DECLINED : null;
      return taken(result);
      // The reader takes the thread: its layout, then its drawing of it.
      async function taken(result) {
        const selectedLayout = result?.then ? await whileCurrent(result) : result;
        if (!mayPresent()) return null;
        if (selectedLayout === false) return DECLINED;
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
                  scroll: trip ? [{ at: current, block: "nearest" }] : [],
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
      const openSurface = async () => {
        if (preview) intent.handoff(preview.close);
        if (trip) {
          if (!(await scrollToThread(id, { part: localPart, focus, intent })))
            return null;
        } else {
          await reveal(surfaceFocusTarget(id, { part: localPart }), intent).ready;
          const current = surfaceFocusTarget(id, { part: localPart });
          if (
            !current ||
            !mayPresent() ||
            (focus !== false &&
              !intent.handoff(() => {
                focusDestination(current, "move");
                if (scroll) scrollIntoView(current, { block: "nearest" });
              }))
          )
            return null;
        }
        return surfaceFocusTarget(id, { part: localPart });
      };
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      // A thread a seat holds whole has no node until the seat shows it (held-news.js).
      if (showHeldThread(id) && surfaceFocusTarget(id, { part: localPart }))
        return openSurface();
      let opened = null;
      if (preview)
        intent.handoff(() => {
          opened = preview.open(id, { origin });
        });
      if (opened) {
        if (trip) {
          if (
            !(await scrollToThread(id, {
              part: part ?? "thread",
              focus,
              presented: opened.presented,
              intent,
            }))
          )
            return null;
        } else {
          if (!(await opened.presented) || !mayPresent()) return null;
          const current = threadFocusTarget(id, { part });
          if (
            !current ||
            !mayPresent() ||
            (focus !== false &&
              !intent.handoff(() => {
                focusDestination(current, "move");
                if (scroll)
                  scrollIntoView(current, {
                    behavior: scrollBehavior(),
                    block: "nearest",
                  });
              }))
          )
            return null;
        }
        return threadFocusTarget(id, { part });
      }
      const held = revealHeld([id]);
      if (held) {
        await held.presented;
        if (!mayPresent()) return null;
      }
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      return DECLINED;
    }

    const asked = selected ? inPrimary(false) : DECLINED;
    const first = asked instanceof Promise ? await asked : asked;
    if (first !== DECLINED && first !== UNDRAWN) return first;
    if (part !== "message") {
      const shown = await onPage();
      if (shown !== DECLINED) return shown;
    }
    // Only a reader that declined is asked again; one that took the thread has shown it.
    if (!selected || first !== DECLINED) return null;
    const shown = await inPrimary(true);
    return shown === DECLINED || shown === UNDRAWN ? null : shown;
  }

  // Where a thread about an element an agent sent in a message goes to its subject: the
  // message stands in for a place on the page (anchor-placement.js), so the message's
  // thread opens there without moving focus, as a thread ask's does (obligations/view.js), and
  // the user lands on the element in it. A thread whose subject stands on the page goes
  // there by opening itself, beside its words.
  async function openThreadSubject(id, { intent = retainUserIntent() } = {}) {
    const message = placedAt(id)?.message;
    if (!message) return null;
    const { element } = messageHolding(threadNamed(id).anchor.section);
    const shown = await openPageThread(message, {
      part: "message",
      focus: false,
      travel: false,
      intent,
    });
    if (!shown || !element.isConnected) return null;
    const arrived = await arrive(
      () =>
        element.isConnected && {
          where: element,
          focus: element,
          scroll: [{ at: element, block: "nearest" }],
        },
      { intent },
    );
    return arrived ? element : null;
  }

  // Where a thread holds the user's draft `context`, with its box ready for the caret:
  // the thread's reply box, or the rewrite of one of its messages, which opens on that
  // message where a message part lands, in the primary reader (`message-edit.js`).
  // Landed on the thread instead, a long one's landing on its latest turn took the view
  // away from a rewrite it had just opened higher up.
  async function openThreadDraft(context, intent) {
    const thread = threadHolding(context);
    if (!thread) return null;
    const { part, name } = threadDraft(context);
    if (part === "reply") return openPageThread(thread.id, { part: "reply", intent });
    const landed = await openPageThread(name, { part: "message", intent });
    const card = landed && closestAcross(landed, THREAD);
    return card ? openMessageEditIn(card, name) : null;
  }
  // The thread a thread-held draft is written under: the thread a reply is keyed by, or
  // the one holding the message a rewrite is of; none once it has left the log's reading.
  function threadHolding(context) {
    const { part, name } = threadDraft(context);
    return part === "reply"
      ? allThreads().find((each) => threadKey(each) === name)
      : allThreads().find((each) => each.msgs.some(({ id }) => id === name));
  }

  return {
    register,
    openPageThread,
    openThreadSubject,
    openThreadDraft,
    holdsThreadDraft: (context) => Boolean(threadHolding(context)),
    threadFocusTarget,
    threadHere,
    threadAtStanding,
    replyThreadAtStanding,
    threadTarget,
    threadPlace,
  };
}
