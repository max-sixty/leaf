/* Core Thread destinations and held identity.

   The open Threads panel wins; otherwise the current exact outlet wins, then an
   available page preview, then a deliberately revealed widget seat, then Threads.
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

   An arrival first shows what any seat holds of the thread (`showHeld`, held-news.js).
   `carried` restores a reply whose surface stopped drawing it; no gesture asked for
   that conversation, so this continuation leaves its held news in place.

   Held identity is the focused Thread across shadow roots. An unheld preview or
   panel conversation may accompany its page target; when focus returns to the body,
   a visible accompanying preview remains the current conversation. Canonical page
   targets always come from anchor placement, independently of whichever view draws a
   Thread. */
import { focusDestination } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { retainUserIntent } from "../user-intent.js";
import { focused } from "../keyboard/scopes.js";
import { replyAvailable } from "./replies.js";
import { allThreads } from "./state.js";
import { heldThread } from "./focus.js";
import { showHeld } from "./held-news.js";
import { revealHeld, surfaceFocusTarget } from "./surfaces.js";
import { reveal } from "../widget-elements.js";

export function createThreadDestinations({
  placedAt,
  threadIdsAt,
  panelIsOpen,
  showThread,
  scrollToThread,
  preview = null,
}) {
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
      carried = false,
    } = {},
  ) {
    if (!intent()) return null;
    const mayPresent = () => (focus === false ? intent.available() : intent());
    if (!carried) showHeld(id);
    if (!panelIsOpen() && focus !== "message") {
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
                focusDestination(current);
                current.scrollIntoView({ block: "nearest" });
              }))
          )
            return null;
        }
        return surfaceFocusTarget(id, { focus: localFocus });
      };
      if (surfaceFocusTarget(id, { focus: localFocus })) return openSurface();
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
                focusDestination(current);
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
    return showThread(id, { focus: focus ?? "reply", flash, intent, carried });
  }
  return {
    openPageThread,
    threadFocusTarget,
    threadHere,
    threadAtStanding,
    replyThreadAtStanding,
    threadTarget,
  };
}
