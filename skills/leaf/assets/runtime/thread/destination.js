/* Core Thread destinations and held identity.

   A registered primary reader supplies its retained destination first. A message
   part needs the reader that renders its native authored content: the primary,
   then Threads. A thread or reply part uses the nearest reader: an open Threads
   panel, otherwise the exact outlet, then a page preview, then a deliberately
   revealed widget seat, then Threads.
   A compact preview keeps held widget arrivals held until its own release gesture.
   The optional preview supplies physical
   opening, placement proof, current focus node and target accompaniment; it owns
   no destination policy. A command retains its original intent through placement
   and returns its actual focus destination. Surface defaults enter the reply,
   compact previews default to the thread, and Threads defaults to the reply.
   `travel: false` keeps the page under the gesture while revealing its destination.
   A native continuation (`focus: false`) returns its presented route under session
   availability even after Tab supersedes positioning; it never takes focus, and the
   original intent alone permits scrolling or another reveal gesture.
   Addressed part and focus are independent. Materializing a thread Question asks
   for its message part without focus; a native editing continuation asks for the
   reply part without focus. Omitting part follows each surface's ordinary route.
   A focused primary arrival uses page travel's ordinary arrival, which clears a
   surface covering the native reader before disclosure, focus and placement. A
   travelling arrival captures its return place before releasing held content or
   changing layout and commits it only after the destination is reached.

   Held identity is the focused Thread across shadow roots. An unheld preview or
   panel conversation may accompany its page target; when focus returns to the body,
   a visible accompanying preview remains the current conversation. Canonical page
   targets always come from anchor placement, independently of whichever view draws a
   Thread. */
import { scrollIntoView } from "../landing-scroll.js";
import { focusDestination, focused } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { replyAvailable } from "./replies.js";
import { allThreads, readThreads } from "./state.js";
import { heldThread } from "./focus.js";
import { showHeld, showHeldThread } from "./held-news.js";
import { revealHeld, surfaceFocusTarget } from "./surfaces.js";
import { reveal } from "../widget-elements.js";
import { renderedUnder } from "../shadow.js";
import { threadNames } from "./model.js";

export function createThreadDestinations({
  placedAt,
  threadIdsAt,
  panelIsOpen,
  showThread,
  scrollToThread,
  arrive,
  prepareTrip,
  preview = null,
}) {
  let presentation = null;
  let opening = null;
  function register(owner, open, reader) {
    if (!(owner instanceof Element) || typeof open !== "function")
      throw new TypeError(
        "A Thread presentation needs an Element owner and an open callback",
      );
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
  const threadHere = () => heldThread() ?? preview?.accompanied() ?? null;
  // Discussion identity precedes the view that realizes it. Reply availability
  // narrows an editable destination without erasing the user's standing thread.
  const threadAtStanding = () => {
    const held = heldThread();
    if (held) return held.dataset.thread ?? held.dataset.id;
    const active = focused();
    const ids = active ? threadIdsAt(active) : [];
    const shown = threadHere();
    const shownId = shown?.dataset.thread ?? shown?.dataset.id;
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

  async function openPageThread(
    id,
    {
      part = null,
      focus = true,
      travel = true,
      flash = true,
      intent = retainUserIntent(),
      transition = null,
    } = {},
  ) {
    if (!intent()) return null;
    const selected = presentation;
    if (selected?.owner.isConnected) {
      const thread = threadNames(readThreads().threads).get(id);
      if (!thread) return null;
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = new Promise((resolve) =>
        abort.signal.addEventListener("abort", () => resolve(null), { once: true }),
      );
      const whileCurrent = (work) => Promise.race([work, cancelled]);
      const request = {
        message:
          part === "message"
            ? (thread.msgs.find((message) => message.id === id)?.key ?? null)
            : null,
        part,
        focus,
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
        focus !== false && travel
          ? prepareTrip({
              landing: () => selected.reader.destination(thread.key, request),
              intent: arriving,
            })
          : null;
      showHeld(id);
      const result = selected.open(thread.key, request);
      const selectedLayout = result?.then ? await whileCurrent(result) : result;
      if (!mayPresent()) return null;
      if (selectedLayout !== false) await whileCurrent(selected.reader.update());
      if (!mayPresent()) return null;
      const destination =
        selectedLayout === false
          ? null
          : selected.reader.destination(thread.key, request);
      if (destination !== null) {
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
                  scroll: travel ? [{ at: current, block: "nearest" }] : [],
                }
              );
            },
            { intent: arriving, departure },
          ),
        );
        return reached ? selected.reader.destination(thread.key, request) : null;
      }
    }
    const mayPresent = () => (focus === false ? intent.available() : intent());
    if (!panelIsOpen() && part !== "message") {
      const localPart = part ?? "reply";
      const openSurface = async () => {
        if (preview) intent.handoff(preview.close);
        if (travel) {
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
                scrollIntoView(current, { block: "nearest" });
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
          opened = preview.open(id, { transition });
        });
      if (opened) {
        if (travel) {
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
    }
    return showThread(id, { part: part ?? "reply", focus, flash, intent });
  }
  return {
    register,
    openPageThread,
    threadFocusTarget,
    threadHere,
    threadAtStanding,
    replyThreadAtStanding,
    threadTarget,
  };
}
