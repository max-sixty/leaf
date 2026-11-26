/* Retained controls derived from the canonical current anchor reading.
 *
 * This view owns visual comment proxies and message fragment state. The dedicated
 * anchor-note projection owns accessible comment notes. Visual proxies are keyed Lit
 * controls, one group per drawing's seat, standing on the
 * details shelf with the seat naming the group as its details (features/details-shelf.js). A
 * screen reader reaches them from the drawing; a keyboard reaches the drawing and each
 * declared part through the target picker (`s`). A failed thread presentation withdraws
 * visual proxies until a valid reading replaces them. Commands enter only through the
 * constructor.
 */
import { holdFocus } from "../dom/focus.js";
import { fragmentId } from "../base/anchor-coordinate.js";
import { sameAnchor } from "../base/anchor-coordinate.js";
import { sectionLabel } from "../readings/addressable-names.js";
import { createAnchorNoteProjection } from "./anchor-note-view.js";
import { shelve, unshelve } from "../features/details-shelf.js";
import { html, nothing, render as renderTemplate, repeat } from "/vendor/lit.js";
import {
  fragmentTarget,
  annotationAt,
  resolveAnchor,
  sectionOf,
  unclaimedVisualGesture,
  visualAt,
  visualParts,
  visualTags,
} from "../readings/anchor-resolution.js";
import {
  authoredScope,
  elementById,
  pageDocument,
  pageQueryAll,
  readingElements,
} from "../readings/passages.js";
import { pageUpgraded } from "../base/page-paint.js";
import { kept } from "../state/kept.js";
import { readPart } from "../state/semantic-state.js";
import { isElement, shadowHost, upFrom } from "../lib/shadow-tree.js";
import {
  targetElement,
  targetParts,
  targetSegments,
} from "../readings/resolved-target.js";
import { offer, offeredAction } from "../lib/controls.js";
import { keeps, keepsText } from "../lib/keeps.js";
import { raiseError } from "../transport/errors.js";
import { inChrome } from "../base/ui-marks.js";

const shownDocument = readPart((root) => root.document);
const MSG_REF = '.lf-msg-body a[href^="#"]';
// Why a message's link to a section the shown version lacks goes nowhere.
/** @param {string | null} id */
const missingReference = (id) => `§ ${id} isn't in the version shown`;

/** @typedef {import("../../types/domain.js").Anchor} Anchor */
/** @typedef {{anchor: Anchor, label: string, key: string}} VisualAction */
/** @typedef {HTMLButtonElement & {lfAnchor: Anchor}} VisualActionControl */
/** @typedef {NonNullable<ReturnType<ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>["read"]>>} AnchorReading */
/** @typedef {AnchorReading["readings"][number]} ThreadReading */
/** @param {{
 * commentOnTarget: ReturnType<typeof import("./composing/surface.js").createResponseSurface>["commentOnTarget"],
 * openThread: ReturnType<typeof import("../records/thread/destination.js").createThreadDestinations>["openPageThread"],
 * labelAnchor: typeof import("../records/thread/messages.js").anchorLabel,
 * invalidateThread: () => unknown, invalidatePageGeometry: () => unknown,
 * placement: Pick<ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>, "hearPlaced" | "placedAt">,
 * messageReferenceRoot: Element, draftQuote: Element}} dependencies */

export function createAnchorControls({
  commentOnTarget,
  openThread,
  labelAnchor,
  invalidateThread,
  invalidatePageGeometry,
  placement,
  messageReferenceRoot,
  draftQuote,
}) {
  /** @type {Map<Element, HTMLDivElement>} */
  const visualActionHolders = new Map();
  const anchorNotes = createAnchorNoteProjection({ openThread, labelAnchor });
  let mounted = false;
  /** @type {(() => void) | null} */
  let stopHearing = null;
  // Each thread the last render read, and the blocks it seated the thread's notes at.
  /** @type {Map<string, {thread: ThreadReading["thread"], seats: Element[]}>} */
  let seated = new Map();
  let invalidationQueued = false;
  /** @type {Map<Element, VisualAction[]>} */
  let pendingVisualActions = new Map();

  /** @param {Anchor | null | undefined} anchor */
  const visualActionAnchor = (anchor) => {
    /** @type {VisualActionControl[]} */
    const controls = pageQueryAll(".lf-visual-action");
    return controls.find((control) => sameAnchor(control.lfAnchor, anchor)) ?? null;
  };

  // A proxy group is named by the outer disclosure that controls its drawing's
  // visibility, so a screen reader meets it while the drawing is folded away. Shadow
  // renderers share their host so sibling groups do not reorder on each paint.
  /** @param {Element} candidate */
  function visualActionSeat(candidate) {
    let seat = shadowHost(candidate.getRootNode()) ?? candidate;
    /** @type {Node | null} */
    let current = seat;
    for (; current; current = upFrom(current))
      if (isElement(current) && current.matches("details")) seat = current;
    return seat;
  }

  function visualActionPlan() {
    /** @type {Map<Element, VisualAction[]>} */
    const groups = new Map();
    const claimed = new Set();
    for (const candidate of readingElements(visualTags())) {
      const found = visualAt(candidate);
      if (!found || found.element !== candidate) continue;
      const parts = visualParts(candidate);
      /** @type {Omit<VisualAction, "key">[]} */
      const targets = [
        {
          anchor: { section: found.id },
          label: sectionLabel(elementById(found.id)) || found.id,
        },
        ...parts
          .filter((part) => unclaimedVisualGesture(part.element))
          .map((part) => ({
            anchor: { section: found.id, visual: part.id },
            label: part.label,
          })),
      ];
      const seat = visualActionSeat(candidate);
      const group = groups.get(seat) ?? [];
      groups.set(seat, group);
      for (const target of targets) {
        const key = JSON.stringify([
          target.anchor.section,
          target.anchor.visual ?? null,
        ]);
        if (!claimed.has(key)) {
          claimed.add(key);
          group.push({ ...target, key });
        }
      }
    }
    return groups;
  }

  // What a proxy stands for: the part it responds to, or the picture.
  /** @param {Element} node */
  function visualActionTarget(node) {
    const control = /** @type {VisualActionControl | null} */ (
      node.closest(".lf-visual-action")
    );
    if (!control) return null;
    const current = resolveAnchor(control.lfAnchor);
    return targetParts(current)[0] ?? targetElement(current);
  }

  /** @param {MouseEvent & {currentTarget: VisualActionControl}} event */
  function activateVisualAction(event) {
    const control = event.currentTarget;
    commentOnTarget({ anchor: control.lfAnchor });
  }

  /** @param {VisualAction} target */
  const visualActionTemplate = ({ anchor, label }) => html`
    <button
      ${offeredAction("proxy", "lf-visual-action")}
      tabindex="-1"
      .lfAnchor=${anchor}
      .textContent=${`Respond to ${label}`}
      @click=${activateVisualAction}
    ></button>
  `;

  /** @param {Map<Element, VisualAction[]>} groups */
  function reconcileVisualActions(groups) {
    const kept = new Set();
    for (const [seat, targets] of groups) {
      const first = targets[0];
      if (!first) continue;
      let holder = visualActionHolders.get(seat);
      if (!holder) {
        holder = offer("div", "lf-visual-actions");
        holder.setAttribute("role", "group");
        visualActionHolders.set(seat, holder);
      }
      kept.add(seat);
      const restoreFocus = holdFocus(holder);
      keeps(holder, "aria-label", `Responses to ${first.label}`);
      renderTemplate(
        html`${repeat(targets, ({ key }) => key, visualActionTemplate)}`,
        holder,
      );
      shelve(seat, holder, visualActionTarget);
      restoreFocus?.();
    }
    for (const [seat, holder] of visualActionHolders)
      if (!kept.has(seat)) {
        renderTemplate(nothing, holder);
        unshelve(seat, holder);
        visualActionHolders.delete(seat);
      }
  }

  function publishVisualActions() {
    const groups = pendingVisualActions;
    pendingVisualActions = new Map();
    reconcileVisualActions(groups);
  }

  // The plan is a reading of the page's own pictures, their labels and the parts their
  // widgets register, none of which a thread changes, kept until something it read
  // changes (state/kept.js, `kept`): the page's reading, a visual's parts (state/visual-parts.js), or
  // the document presented or a widget's layout changing, which is what tells of a new
  // press around a picture (readings/anchor-resolution.js, `unclaimedVisualGesture`). A thread
  // pass over an unchanged page keeps the responses it published. The pictures are
  // found in each piece of the page's reading, kept until that piece changes
  // (readings/passages.js, `readingElements`), so planning again after one part of the page
  // changed searches that part alone.
  const plan = kept(visualActionPlan);
  /** @type {Map<Element, VisualAction[]> | null} */
  let planned = null;
  function prepareVisualActions() {
    const next = plan();
    if (next === planned && !pendingVisualActions.size) return;
    planned = next;
    pendingVisualActions = next;
    if (pageUpgraded()) publishVisualActions();
  }

  function withholdVisualActions() {
    planned = null;
    pendingVisualActions = new Map();
    reconcileVisualActions(pendingVisualActions);
  }

  function paintMessageReferences() {
    // Missing targets share the quote's detached meaning, but retain the message
    // link's own contour: muted ink and a dashed underline, its press refused. A live
    // one previews the place it names (place-preview.js), so it carries no title.
    for (const anchor of messageReferenceRoot.querySelectorAll(MSG_REF)) {
      const href = anchor.getAttribute("href");
      if (href === null) throw new Error("A message fragment reference has no href");
      const alive = Boolean(fragmentTarget(href));
      anchor.toggleAttribute("data-lf-detached", !alive);
      keeps(anchor, "aria-disabled", alive ? null : "true");
      keeps(anchor, "title", alive ? null : missingReference(fragmentId(href)));
    }
  }

  /** @param {AnchorReading["draft"]} draft */
  function paintDraft({ open, anchor, about, resolved }) {
    const label = open ? labelAnchor(anchor, about) : "";
    keepsText(draftQuote, label);
    const located = Boolean(resolved && resolved.status !== "outdated");
    draftQuote.classList.toggle("lf-quiet", !label || (located && !about));
  }

  // Where a thread's notes stand, by its placement: at each block its passage spans. A
  // resolved thread, and one the shown version doesn't hold, stand nowhere.
  /** @param {ThreadReading["thread"]} thread @param {ThreadReading["placement"] | undefined} found
   * @returns {Element[]} */
  function seatsOf(thread, found) {
    if (!found || found.status === "outdated" || thread.resolved) return [];
    // A passage seats a note at each block it spans, by the rule its `place` follows:
    // inside a datum, the datum stands for text no block holds.
    const fallback = found.datumElement ? () => found.datumElement : undefined;
    const blocks = targetElement(found)
      ? [found.place]
      : [
          ...new Set(
            targetSegments(found).map((segment) =>
              annotationAt(segment.node, fallback),
            ),
          ),
        ].filter(Boolean);
    /** @type {Element[]} */
    const holders = [];
    for (const holder of blocks.length ? blocks : [sectionOf(thread.anchor)])
      if (holder && !inChrome(holder)) holders.push(holder);
    return holders;
  }
  /** @param {Element[]} a @param {Element[]} b */
  const sameSeats = (a, b) =>
    a.length === b.length && a.every((holder, index) => holder === b[index]);

  /** @param {AnchorReading} reading */
  function render({ readings, draft }) {
    // These controls stand on elements of the shown document: a note's block and the
    // section a message's link names. Reading the document here
    // draws them again when a revision replaces it, as one that writes its own
    // `aria-details` on a commented block it keeps, which the note's relation must then
    // follow (features/details-shelf.js).
    shownDocument();
    /** @type {Map<Element, [string, ...string[]]>} */
    const notes = new Map();
    seated = new Map();
    for (const { thread, placement: found } of readings) {
      const seats = seatsOf(thread, found);
      seated.set(thread.id, { thread, seats });
      for (const holder of seats) {
        const threads = notes.get(holder);
        if (threads) threads.push(thread.id);
        else notes.set(holder, [thread.id]);
      }
    }
    prepareVisualActions();
    anchorNotes.present(notes);
    paintDraft(draft);
    paintMessageReferences();
  }

  function queueInvalidation() {
    if (invalidationQueued) return;
    invalidationQueued = true;
    queueMicrotask(() => {
      invalidationQueued = false;
      if (mounted) invalidateThread();
    });
  }

  /** @param {Event} event */
  const onLayoutInvalidated = (event) => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    invalidatePageGeometry();
    // Authored content asks for a thread pass: its parts can move or be replaced
    // without a publication, and a pass is what marks the new node and asks a widget
    // that seats threads for its outlets again (records/thread/surfaces.js). That is the page,
    // and a message's markup, whose authored document is its body (`authoredScope`)
    // though it stands in the runtime's chrome. The chrome's own scaffolding holds no
    // target, so a Threads card opening or closing asks for none.
    if (inChrome(target) && authoredScope(target) === pageDocument()) return;
    queueInvalidation();
  };

  // A press on a link to a missing section is refused and says why, which its title
  // says only to a resting pointer.
  /** @param {Event} event */
  const onMessageReference = (event) => {
    if (!isElement(event.target)) return;
    const href = event.target.closest(MSG_REF)?.getAttribute("href");
    if (href == null || fragmentTarget(href)) return;
    event.preventDefault();
    raiseError(missingReference(fragmentId(href)));
  };

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("lf-layout", onLayoutInvalidated);
    // A script can move a thread with no widget to announce it, as one that draws its
    // block anew or moves its words into another block does. Placement hears it and
    // names the threads it placed again (anchor-placement.js, `hearPlaced`), and where
    // one of them now seats its note elsewhere than the last render did, a
    // pass seats it there, as a widget's `lf-layout` asks. Words rewritten inside a
    // block, as a counter redrawn each frame, move no seat and ask for none. A thread
    // the last render didn't read is the anchor paint's to present (anchor-paint.js,
    // `replace`).
    stopHearing = placement.hearPlaced(({ threads }) => {
      const moved = threads.some((id) => {
        const was = seated.get(id);
        return (
          was && !sameSeats(was.seats, seatsOf(was.thread, placement.placedAt(id)))
        );
      });
      if (moved) queueInvalidation();
    });
    messageReferenceRoot.addEventListener("click", onMessageReference);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("lf-layout", onLayoutInvalidated);
      stopHearing?.();
      stopHearing = null;
      messageReferenceRoot.removeEventListener("click", onMessageReference);
    }
    mounted = false;
    anchorNotes.destroy();
    withholdVisualActions();
  }

  return {
    mount,
    destroy,
    render,
    publishVisualActions,
    withholdVisualActions,
    visualActionAnchor,
  };
}
