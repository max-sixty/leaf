/* Core Thread destinations and held identity.

   A registered primary reader supplies its retained destination first. Without
   that destination, the open Threads panel wins; otherwise the exact outlet wins,
   then a page preview, then a deliberately revealed widget seat, then Threads.
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
   A native continuation needs the reader that owns its live widgets, so it
   bypasses compact previews just as an explicit message arrival does.

   Held identity is the focused Thread across shadow roots. An unheld preview or
   panel conversation may accompany its page target; when focus returns to the body,
   a visible accompanying preview remains the current conversation. Canonical page
   targets always come from anchor placement, independently of whichever view draws a
   Thread. */
import { focusDestination, focused } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { retainUserIntent } from "../user-intent.js";
import { replyAvailable } from "./replies.js";
import { allThreads, readThreads } from "./state.js";
import { heldThread } from "./focus.js";
import { showHeldThread } from "./held-news.js";
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
  const threadFocusTarget = (id, { focus = null } = {}) =>
    focus === "message"
      ? null
      : (surfaceFocusTarget(id, { focus }) ??
        preview?.focusTarget(id, { focus }) ??
        null);

  async function openPageThread(
    id,
    {
      focus = null,
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
      const request = {
        message: focus === "message" ? id : null,
        focus,
        signal: abort.signal,
        current: () =>
          !abort.signal.aborted &&
          presentation === selected &&
          selected.owner.isConnected &&
          (focus === false ? intent.available() : intent()),
      };
      const result = selected.open(thread.key, request);
      const destination = result?.then
        ? await Promise.race([
            result,
            new Promise((resolve) =>
              abort.signal.addEventListener("abort", () => resolve(null), {
                once: true,
              }),
            ),
          ])
        : result;
      const mayPresent = () =>
        !abort.signal.aborted &&
        presentation === selected &&
        selected.owner.isConnected &&
        (focus === false ? intent.available() : intent());
      if (!mayPresent()) return null;
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
        await reveal(destination, intent).ready;
        if (!mayPresent()) return null;
        if (focus !== false)
          intent.handoff(() => {
            focusDestination(destination, "move");
            if (travel)
              destination.scrollIntoView({
                behavior: scrollBehavior(),
                block: "nearest",
              });
          });
        return destination;
      }
    }
    const mayPresent = () => (focus === false ? intent.available() : intent());
    if (!panelIsOpen() && focus !== "message" && focus !== false) {
      const localFocus = focus ?? "reply";
      const openSurface = async () => {
        if (preview) intent.handoff(preview.close);
        if (travel) {
          if (!(await scrollToThread(id, { focus: localFocus, intent }))) return null;
        } else {
          await reveal(surfaceFocusTarget(id, { focus: localFocus }), intent).ready;
          const current = surfaceFocusTarget(id, { focus: localFocus });
          if (
            !current ||
            !mayPresent() ||
            (focus !== false &&
              !intent.handoff(() => {
                focusDestination(current, "move");
                current.scrollIntoView({ block: "nearest" });
              }))
          )
            return null;
        }
        return surfaceFocusTarget(id, { focus: localFocus });
      };
      if (surfaceFocusTarget(id, { focus: localFocus })) return openSurface();
      // A thread a seat holds whole has no node until the seat shows it (held-news.js).
      if (showHeldThread(id) && surfaceFocusTarget(id, { focus: localFocus }))
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
              focus: focus ?? "thread",
              presented: opened.presented,
              intent,
            }))
          )
            return null;
        } else {
          if (!(await opened.presented) || !mayPresent()) return null;
          const current = threadFocusTarget(id, { focus });
          if (
            !current ||
            !mayPresent() ||
            (focus !== false &&
              !intent.handoff(() => {
                focusDestination(current, "move");
                current.scrollIntoView({
                  behavior: scrollBehavior(),
                  block: "nearest",
                });
              }))
          )
            return null;
        }
        return threadFocusTarget(id, { focus });
      }
      const held = revealHeld([id]);
      if (held) {
        await held.presented;
        if (!mayPresent()) return null;
      }
      if (surfaceFocusTarget(id, { focus: localFocus })) return openSurface();
    }
    return showThread(id, { focus: focus ?? "reply", flash, intent });
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
