/* Retained controls derived from the canonical current anchor reading.
 *
 * This view owns visual comment proxies, controls for reactions in force, and message
 * fragment state. The dedicated anchor-note projection owns accessible comment notes.
 * Visual proxies are keyed Lit controls, one group per drawing's seat, standing on the
 * details shelf with the seat naming the group as its details (details-shelf.js). A
 * screen reader reaches them from the drawing; a keyboard reaches the drawing and each
 * declared part through the target picker (`s`). A failed thread presentation withdraws
 * visual proxies until a valid reading replaces them. A reaction in force first reveals
 * its dedicated removal action; only that action withdraws the reaction. The removal
 * wears the neutral undo icon and says "Undo", the word of every other control that takes
 * a gesture back, because removing a reaction is an undo of it. A red ✕ read as "close
 * this", nearly matched the ❌ reaction, and caught phone taps meant to dismiss the
 * cluster; Max chose undo over it on 23 October 2026. Commands enter only through the
 * constructor.
 */
import { scrollIntoView } from "./landing-scroll.js";
import { nextRender } from "./rendering.js";
import { holdFocus, onPressAway } from "./focus.js";
import { fragmentId } from "./anchor-coordinate.js";
import { sameAnchor } from "./anchor-coordinate.js";
import { sectionLabel } from "./addressable-names.js";
import { createAnchorNoteProjection } from "./anchor-note-view.js";
import { shelve, unshelve } from "./details-shelf.js";
import { html, nothing, render as renderTemplate, repeat } from "/runtime/framework.js";
import {
  fragmentTarget,
  annotationAt,
  lightSeat,
  resolveAnchor,
  sectionOf,
  unclaimedVisualGesture,
  visualAt,
  visualParts,
  visualSelector,
} from "./anchor-resolution.js";
import { registerContribution } from "./contributions.js";
import { commandScope } from "./keyboard/scopes.js";
import {
  authoredScope,
  elementById,
  inChrome,
  pageDocument,
  pageQueryAll,
  pageReadingVersion,
} from "./passages.js";
import { pageUpgraded } from "./page-paint.js";
import { documentChanged, readPart } from "./semantic-state.js";
import { tokenEntry } from "./registry.js";
import { isElement } from "./shadow-tree.js";
import { shadowHost, upFrom } from "./shadow.js";
import { targetElement, targetParts, targetSegments } from "./resolved-target.js";
import { offer, offered, reveal } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";
import { retainUserIntent } from "./user-intent.js";
import { bareReaction } from "./thread/model.js";
import { raiseError } from "./errors.js";

const shownDocument = readPart((root) => root.document);
const MSG_REF = '.lf-msg-body a[href^="#"]';
// Why a message's link to a section the shown version lacks goes nowhere.
/** @param {string | null} id */
const missingReference = (id) => `§ ${id} isn't in the version shown`;

/** @typedef {import("../types/domain.js").Anchor} Anchor */
/** @typedef {import("./thread/thread-card.js").ThreadRecord["root"] & {token: string}} ReactionRoot */
/** @typedef {{before: ReactionRoot[], inside: ReactionRoot[]}} ReactionGroup */
/** @typedef {{anchor: Anchor, label: string, key: string}} VisualAction */
/** @typedef {HTMLButtonElement & {lfAnchor: Anchor}} VisualActionControl */
/** @typedef {NonNullable<ReturnType<ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>["read"]>>} AnchorReading */
/** @param {{
 * commentOnTarget: ReturnType<typeof import("./composing/surface.js").createResponseSurface>["commentOnTarget"],
 * openThread: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openPageThread"],
 * withdrawReaction: ReturnType<typeof import("./undo.js").createUndo>["withdraw"],
 * labelAnchor: typeof import("./thread/messages.js").anchorLabel,
 * invalidateThread: () => unknown, invalidatePageGeometry: () => unknown,
 * messageReferenceRoot: Element, draftQuote: Element, focused: typeof import("./focus.js").focused,
 * paintKeys: typeof import("./keyboard/scopes.js").paintKeys}} dependencies */

export function createAnchorControls({
  commentOnTarget,
  openThread,
  withdrawReaction,
  labelAnchor,
  invalidateThread,
  invalidatePageGeometry,
  messageReferenceRoot,
  draftQuote,
  focused,
  paintKeys,
}) {
  /** @type {Map<Element, HTMLDivElement>} */
  const visualActionHolders = new Map();
  /** @type {Map<Element, ReactionSeat>} */
  const reactionSeats = new Map();
  const anchorNotes = createAnchorNoteProjection({ openThread, labelAnchor });
  /** @type {ReturnType<typeof onPressAway> | null} */
  let mounted = null;
  let invalidationQueued = false;
  /** @type {Map<Element, VisualAction[]>} */
  let pendingVisualActions = new Map();

  /** @param {ReactionSeat} record @param {string | null} eventId
   * @param {{focus?: boolean, surface?: import("./contributions.js").ContributionSurface | null}} [options] */
  function setReactionRemoval(record, eventId, { focus = false, surface = null } = {}) {
    if (eventId)
      for (const other of reactionSeats.values())
        if (other !== record && other.expanded) {
          other.expanded = null;
          other.margin?.update({ immediate: true });
        }
    record.expanded = eventId;
    record.margin?.update({ immediate: true });
    paintKeys();
    if (!focus || !eventId) return;
    // The remove action draws on the next render; a newer input the user gave meanwhile
    // keeps them where it put them.
    const mayFocus = retainUserIntent();
    nextRender(() =>
      mayFocus.handoff(() =>
        record.margin?.focus(`reaction:${eventId}:remove`, "move", surface),
      ),
    );
  }

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
    for (const candidate of pageQueryAll(visualSelector())) {
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

  /** @param {FocusEvent & {currentTarget: VisualActionControl}} event */
  function focusVisualAction(event) {
    const control = event.currentTarget;
    let current = resolveAnchor(control.lfAnchor);
    let element = targetParts(current)[0] ?? targetElement(current);
    if (!element) return;
    reveal(element, retainUserIntent());
    current = resolveAnchor(control.lfAnchor);
    element = targetParts(current)[0] ?? targetElement(current);
    scrollIntoView(element, {
      behavior: "instant",
      block: "nearest",
    });
  }

  /** @param {MouseEvent & {currentTarget: VisualActionControl}} event */
  function activateVisualAction(event) {
    const control = event.currentTarget;
    commentOnTarget({ anchor: control.lfAnchor });
  }

  /** @param {VisualAction} target */
  const visualActionTemplate = ({ anchor, label }) => html`
    <button
      ${offered("lf-visual-action lf-quiet")}
      tabindex="-1"
      .lfAnchor=${anchor}
      .textContent=${`Respond to ${label}`}
      @focus=${focusVisualAction}
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
      shelve(seat, holder);
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
  // widgets register, none of which a thread changes. It is planned again when the page
  // might have: its words moved (passages.js, `pageReadingVersion`), a caller said the
  // document changed (`presentDocument`), the shown document was replaced, or a visual
  // signalled new parts (`onLayoutInvalidated`). A thread pass over an unchanged page keeps
  // the responses it published.
  /** @type {[ReturnType<typeof pageReadingVersion>, ReturnType<typeof documentChanged>, ReturnType<typeof shownDocument>] | null} */
  let plannedFor = null;
  function prepareVisualActions() {
    /** @type {NonNullable<typeof plannedFor>} */
    const key = [pageReadingVersion(), documentChanged(), shownDocument()];
    if (
      plannedFor?.every((part, index) => part === key[index]) &&
      !pendingVisualActions.size
    )
      return;
    plannedFor = key;
    pendingVisualActions = visualActionPlan();
    if (pageUpgraded()) publishVisualActions();
  }

  function withholdVisualActions() {
    plannedFor = null;
    pendingVisualActions = new Map();
    reconcileVisualActions(pendingVisualActions);
  }

  // Each target contributes its complete reading of its reactions in force. Only the selected
  // removal disclosure is local state; both rendered surfaces read the same entry keys.
  class ReactionSeat {
    /** @type {readonly ReactionRoot[]} */
    roots;
    /** @type {string | null} */
    expanded = null;
    /** @type {import("./contributions.js").ContributionSurface | null} */
    surface = null;
    /** @type {ReturnType<typeof commandScope>} */
    scope;
    /** @type {ReturnType<typeof registerContribution>} */
    margin;
    /** @param {readonly ReactionRoot[]} roots @param {Element} at */
    constructor(roots, at) {
      this.roots = roots;
      this.scope = commandScope(
        "On a reaction",
        [
          {
            id: "reaction.removal.close",
            keys: ["Escape"],
            title: "hide remove",
            when: () => Boolean(this.expanded),
            run: () => {
              const eventId = this.expanded;
              const entryKey = `reaction:${eventId}:open`;
              /** @type {readonly import("./contributions.js").ContributionSurface[]} */
              const surfaces = ["map", "margin", "inline"];
              const surface =
                surfaces.find((candidate) =>
                  [entryKey, `reaction:${eventId}:remove`].some(
                    (key) => this.margin.control(key, candidate) === focused(),
                  ),
                ) ?? this.surface;
              setReactionRemoval(this, null);
              this.margin.focus(entryKey, "return", surface);
            },
          },
        ],
        { escape: "inner" },
      );
      this.margin = registerContribution({
        key: "reactions",
        target: at,
        read: () => ({
          side: "after",
          state: this.expanded ? "engaged" : "idle",
          entries: this.roots.flatMap((root) => [
            {
              key: `reaction:${root.id}:open`,
              glyph: tokenEntry(root.token)?.glyph ?? root.token,
              label: `${root.token} reaction actions`,
              behavior: "disclosure",
              rank: "secondary",
              className: "lf-react-mark",
              scope: this.scope,
              relation: {
                kind: "entries",
                keys: [`reaction:${root.id}:remove`],
                expanded: this.expanded === root.id,
              },
            },
            {
              key: `reaction:${root.id}:remove`,
              action: "undo",
              label: `Undo ${root.token} reaction`,
              rank: "secondary",
              className: "lf-react-remove",
              scope: this.scope,
              visible: this.expanded === root.id,
            },
          ]),
          readings: this.roots.map((root) => ({
            id: `reaction:${root.id}`,
            text: `${root.token} reaction actions`,
            activate: () => this.margin.focus(`reaction:${root.id}:open`, "move"),
          })),
        }),
        activate: (activation, context) => {
          const root = this.roots.find(
            (candidate) =>
              activation === `reaction:${candidate.id}:open` ||
              activation === `reaction:${candidate.id}:remove`,
          );
          if (!root) return;
          if (activation === `reaction:${root.id}:remove`) {
            withdrawReaction(root);
            return;
          }
          this.surface = context.surface ?? null;
          const currentLocation = focused();
          setReactionRemoval(this, this.expanded === root.id ? null : root.id, {
            focus: context.input === "keyboard" && context.origin === currentLocation,
            surface: this.surface,
          });
        },
      });
    }
  }

  /** @param {Map<Element, ReactionGroup>} seats */
  function seatReactions(seats) {
    const kept = new Set();
    for (const [at, held] of seats) {
      const roots = [...held.before, ...held.inside];
      const record = reactionSeats.get(at);
      kept.add(at);
      if (!record) {
        reactionSeats.set(at, new ReactionSeat(roots, at));
        continue;
      }
      const changed =
        record.roots.length !== roots.length ||
        roots.some(
          (root, index) =>
            root.id !== record.roots[index]?.id ||
            root.token !== record.roots[index]?.token,
        );
      record.roots = roots;
      if (!roots.some((root) => root.id === record.expanded)) record.expanded = null;
      if (changed) record.margin.update();
    }
    for (const [at, record] of reactionSeats)
      if (!kept.has(at)) {
        record.margin.unregister();
        reactionSeats.delete(at);
      }
  }

  function paintMessageReferences() {
    // Missing targets share the quote's detached meaning, but retain the message
    // link's own contour: muted ink and a dashed underline, its press refused.
    for (const anchor of messageReferenceRoot.querySelectorAll(MSG_REF)) {
      const href = anchor.getAttribute("href");
      if (href === null) throw new Error("A message fragment reference has no href");
      const id = fragmentId(href);
      const alive = Boolean(fragmentTarget(href));
      anchor.classList.toggle("detached", !alive);
      keeps(anchor, "aria-disabled", alive ? null : "true");
      keeps(anchor, "title", alive ? `Jump to § ${id}` : missingReference(id));
    }
  }

  /** @param {AnchorReading["draft"]} draft */
  function paintDraft({ open, anchor, about, resolved }) {
    const label = open ? labelAnchor(anchor, about) : "";
    keepsText(draftQuote, label);
    const located = Boolean(resolved && resolved.status !== "outdated");
    draftQuote.classList.toggle("lf-quiet", !label || (located && !about));
  }

  /** @param {AnchorReading} reading */
  function render({ readings, draft }) {
    /** @type {Map<Element, [string, ...string[]]>} */
    const notes = new Map();
    /** @type {Map<Element, ReactionGroup>} */
    const reactions = new Map();
    for (const { thread, placement: found } of readings) {
      if (found.status === "outdated" || thread.resolved) continue;
      if (bareReaction(thread)) {
        // An element target's receipt goes before it, as does a passage seated at a
        // shadow host; a light-DOM passage's receipt goes inside its seat.
        const element = Boolean(targetElement(found));
        const at = element ? found.place : lightSeat(found.place);
        const before = element || at !== found.place;
        if (at && !inChrome(at)) {
          const held = reactions.get(at) ?? { before: [], inside: [] };
          held[before ? "before" : "inside"].push(thread.root);
          reactions.set(at, held);
        }
        continue;
      }
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
      for (const holder of blocks.length ? blocks : [sectionOf(thread.anchor)])
        if (holder && !inChrome(holder)) {
          const threads = notes.get(holder);
          if (threads) threads.push(thread.id);
          else notes.set(holder, [thread.id]);
        }
    }
    prepareVisualActions();
    anchorNotes.present(notes);
    seatReactions(reactions);
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
    // without a publication, and a pass is what marks the new node. That is the page,
    // and a message's markup, whose authored document is its body (`authoredScope`)
    // though it stands in the runtime's chrome. The chrome's own scaffolding holds no
    // target, so a Threads card opening or closing asks for none.
    if (inChrome(target) && authoredScope(target) === pageDocument()) return;
    // Only the page holds the visuals whose actions the pass plans (visual-parts.js,
    // `update`).
    if (!inChrome(target)) plannedFor = null;
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

  // A press away from a reaction whose removal stands offered takes the offer back
  // (focus.js, `onPressAway`).
  /** @param {readonly EventTarget[]} path */
  const offeredAway = (path) =>
    [...reactionSeats.values()].filter(
      (record) =>
        record.expanded &&
        !path.some((node) => node instanceof Node && record.margin.contains(node)),
    );

  function mount() {
    if (mounted) return;
    document.addEventListener("lf-layout", onLayoutInvalidated);
    mounted = onPressAway(
      (path) => offeredAway(path).length > 0,
      (path) => {
        for (const record of offeredAway(path)) setReactionRemoval(record, null);
      },
    );
    messageReferenceRoot.addEventListener("click", onMessageReference);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("lf-layout", onLayoutInvalidated);
      mounted();
      messageReferenceRoot.removeEventListener("click", onMessageReference);
    }
    mounted = null;
    for (const record of reactionSeats.values()) record.margin.unregister();
    reactionSeats.clear();
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
