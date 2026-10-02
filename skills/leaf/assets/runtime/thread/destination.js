/* Core Thread destinations and held identity.

   The open Threads panel wins; otherwise the current exact outlet wins, then an
   available page preview, then Threads. The optional preview supplies physical
   opening, placement proof, current focus node and target accompaniment; it owns
   no destination policy. A command retains its original intent through placement
   and returns its actual focus destination. Surface defaults enter the reply,
   compact previews default to the thread, and Threads defaults to the reply.
   `travel: false` keeps the page under the gesture while revealing its destination.

   Held identity is the focused Thread across shadow roots. An unheld preview or
   panel conversation may accompany its page target. Canonical page targets always
   come from anchor placement, independently of whichever view draws a Thread. */
import { focusDestination } from "../focus.js";
import { scrollBehavior } from "../motion.js";
import { retainUserIntent } from "../user-intent.js";
import { heldThread } from "./focus.js";
import { focusSurface, surfaceFocusTarget } from "./surfaces.js";

export function createThreadDestinations({
  placedAt,
  panelIsOpen,
  showThread,
  scrollToThread,
  preview = null,
}) {
  const threadTarget = (id) => placedAt(id)?.place ?? null;
  const threadHere = () => heldThread() ?? preview?.accompanied() ?? null;
  const threadFocusTarget = (id, { focus = null } = {}) =>
    surfaceFocusTarget(id, { focus }) ?? preview?.focusTarget(id, { focus }) ?? null;

  async function openPageThread(
    id,
    {
      focus = null,
      travel = true,
      intent = retainUserIntent(),
      transition = null,
    } = {},
  ) {
    if (!intent()) return null;
    if (!panelIsOpen()) {
      const localFocus = focus ?? "reply";
      if (surfaceFocusTarget(id, { focus: localFocus })) {
        if (preview) intent.handoff(preview.close);
        if (travel) {
          if (!(await scrollToThread(id, { focus: localFocus, intent }))) return null;
        } else if (!intent.handoff(() => focusSurface(id, { focus: localFocus })))
          return null;
        return surfaceFocusTarget(id, { focus: localFocus });
      }
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
          if (!(await opened.presented) || !intent()) return null;
          const current = threadFocusTarget(id, { focus });
          if (
            !current ||
            !intent.handoff(() => {
              focusDestination(current);
              current.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
            })
          )
            return null;
        }
        return threadFocusTarget(id, { focus });
      }
    }
    return showThread(id, { focus: focus ?? "reply", intent });
  }
  return { openPageThread, threadFocusTarget, threadHere, threadTarget };
}
