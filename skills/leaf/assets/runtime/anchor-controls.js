/* Retained controls derived from the canonical current anchor reading.
 *
 * This view owns visual comment proxies, controls for reactions in force, and message
 * fragment state. The dedicated anchor-note projection owns accessible comment notes.
 * Visual proxies are keyed Lit controls, one group per drawing's seat, standing on the
 * details shelf with the seat naming the group as its details (details-shelf.js). A
 * screen reader reaches them from the drawing; a keyboard reaches the drawing and each
 * declared part through the target picker (`s`). A failed thread presentation withdraws
 * visual proxies until a valid reading replaces them. A reaction in force first reveals
 * its dedicated removal action; only that action withdraws the reaction. Commands enter
 * only through the constructor.
 */
import { scrollIntoView } from "./landing-scroll.js";
import { nextRender } from "./rendering.js";
import { holdFocus } from "./focus.js";
import { fragmentId } from "./initial-render.js";
import { sameAnchor } from "./anchor-coordinate.js";
import { sectionLabel } from "./addressable-names.js";
import { createAnchorNoteProjection } from "./anchor-note-view.js";
import { shelve, unshelve } from "./details-shelf.js";
import {
  html,
  nothing,
  render as renderTemplate,
  repeat,
} from "../vendor/browser-runtime.js";
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
import { elementById, inChrome, pageQueryAll, pageReadingVersion } from "./passages.js";
import { pageUpgraded } from "./page-paint.js";
import { documentChanged, readApplication } from "./semantic-state.js";
import { reactionVocabulary } from "./registry.js";
import { shadowHost, upFrom } from "./shadow.js";
import { targetElement, targetParts, targetSegments } from "./resolved-target.js";
import { offer, reveal } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";
import { retainUserIntent } from "./user-intent.js";
import { bareReaction } from "./thread/model.js";

const MSG_REF = '.lf-msg-body a[href^="#"]';

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
  const visualActionHolders = new Map();
  const reactionSeats = new Map();
  const anchorNotes = createAnchorNoteProjection({ openThread, labelAnchor });
  let mounted = false;
  let invalidationQueued = false;
  let pendingVisualActions = new Map();

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

  const visualActionAnchor = (anchor) =>
    pageQueryAll(".lf-visual-action").find((control) =>
      sameAnchor(control.lfAnchor, anchor),
    ) ?? null;

  // A proxy group is named by the outer disclosure that controls its drawing's
  // visibility, so a screen reader meets it while the drawing is folded away. Shadow
  // renderers share their host so sibling groups do not reorder on each paint.
  function visualActionSeat(candidate) {
    let seat = shadowHost(candidate.getRootNode()) ?? candidate;
    for (let current = seat; current; current = upFrom(current))
      if (current.matches?.("details")) seat = current;
    return seat;
  }

  function visualActionPlan() {
    const groups = new Map();
    const claimed = new Set();
    for (const candidate of pageQueryAll(visualSelector())) {
      const found = visualAt(candidate);
      if (!found || found.element !== candidate) continue;
      const targets = [
        {
          anchor: { section: found.id },
          label: sectionLabel(elementById(found.id)) || found.id,
        },
        ...visualParts(candidate)
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

  function activateVisualAction(event) {
    const control = event.currentTarget;
    commentOnTarget({ anchor: control.lfAnchor });
  }

  const visualActionTemplate = ({ anchor, label }) => html`
    <button
      type="button"
      class="lf-visual-action lf-quiet lf-ui"
      data-lf-gen="1"
      data-lf-offer="button"
      tabindex="-1"
      .lfAnchor=${anchor}
      .textContent=${`Respond to ${label}`}
      @focus=${focusVisualAction}
      @click=${activateVisualAction}
    ></button>
  `;

  function reconcileVisualActions(groups) {
    const kept = new Set();
    for (const [seat, targets] of groups) {
      if (!targets.length) continue;
      let holder = visualActionHolders.get(seat);
      if (!holder) {
        holder = offer("div", "lf-visual-actions");
        holder.setAttribute("role", "group");
        visualActionHolders.set(seat, holder);
      }
      kept.add(seat);
      const restoreFocus = holdFocus(holder);
      keeps(holder, "aria-label", `Responses to ${targets[0].label}`);
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
  let plannedFor = null;
  function prepareVisualActions() {
    const key = [pageReadingVersion(), documentChanged(), readApplication().document];
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
  function seatReactions(seats) {
    const kept = new Set();
    for (const [at, held] of seats) {
      const roots = [...held.before, ...held.inside];
      let record = reactionSeats.get(at);
      const changed =
        !record ||
        record.roots.length !== roots.length ||
        roots.some(
          (root, index) =>
            root.id !== record.roots[index]?.id ||
            root.token !== record.roots[index]?.token,
        );
      if (!record) {
        record = { roots, expanded: null, margin: null, surface: null };
        record.scope = commandScope(
          "On a reaction",
          [
            {
              id: "reaction.removal.close",
              keys: ["Escape"],
              description: "Hide the remove action",
              title: "hide remove",
              when: () => Boolean(record.expanded),
              run: () => {
                const eventId = record.expanded;
                const entryKey = `reaction:${eventId}:open`;
                const surface =
                  ["map", "margin", "inline"].find((candidate) =>
                    [entryKey, `reaction:${eventId}:remove`].some(
                      (key) => record.margin.control(key, candidate) === focused(),
                    ),
                  ) ?? record.surface;
                setReactionRemoval(record, null);
                record.margin.focus(entryKey, "return", surface);
              },
            },
          ],
          { escape: "inner" },
        );
        reactionSeats.set(at, record);
      }
      record.roots = roots;
      kept.add(at);
      if (!roots.some((root) => root.id === record.expanded)) record.expanded = null;
      if (!record.margin)
        record.margin = registerContribution({
          key: "reactions",
          target: at,
          read: () => ({
            side: "after",
            state: record.expanded ? "engaged" : "idle",
            entries: record.roots.flatMap((root) => [
              {
                key: `reaction:${root.id}:open`,
                glyph: reactionVocabulary()[root.token]?.glyph ?? root.token,
                label: `${root.token} reaction actions`,
                behavior: "disclosure",
                rank: "secondary",
                className: "lf-react-mark",
                scope: record.scope,
                relation: {
                  kind: "entries",
                  keys: [`reaction:${root.id}:remove`],
                  expanded: record.expanded === root.id,
                },
              },
              {
                key: `reaction:${root.id}:remove`,
                icon: "cross",
                label: `Remove ${root.token} reaction`,
                tone: "negative",
                rank: "secondary",
                className: "lf-react-remove",
                scope: record.scope,
                visible: record.expanded === root.id,
              },
            ]),
            readings: record.roots.map((root) => ({
              id: `reaction:${root.id}`,
              text: `${root.token} reaction actions`,
              activate: () => record.margin.focus(`reaction:${root.id}:open`, "move"),
            })),
          }),
          activate: (activation, context) => {
            const root = record.roots.find(
              (candidate) =>
                activation === `reaction:${candidate.id}:open` ||
                activation === `reaction:${candidate.id}:remove`,
            );
            if (!root) return;
            if (activation === `reaction:${root.id}:remove`) {
              withdrawReaction(root);
              return;
            }
            record.surface = context.surface ?? null;
            const standing = focused();
            setReactionRemoval(record, record.expanded === root.id ? null : root.id, {
              focus: context.input === "keyboard" && context.origin === standing,
              surface: record.surface,
            });
          },
        });
      else if (changed) record.margin.update();
    }
    for (const [at, record] of reactionSeats)
      if (!kept.has(at)) {
        record.margin.unregister();
        reactionSeats.delete(at);
      }
  }

  function paintMessageReferences() {
    // Missing targets share the quote's detached meaning, but retain the message
    // link's own contour: muted ink and a dashed underline, with its press withheld.
    for (const anchor of messageReferenceRoot.querySelectorAll(MSG_REF)) {
      const href = anchor.getAttribute("href");
      const id = fragmentId(href);
      const alive = Boolean(fragmentTarget(href));
      anchor.classList.toggle("detached", !alive);
      keeps(anchor, "aria-disabled", alive ? null : "true");
      keeps(
        anchor,
        "title",
        alive ? `Jump to § ${id}` : `§ ${id} isn't in the version shown`,
      );
    }
  }

  function paintDraft({ open, anchor, about, resolved }) {
    const label = open ? labelAnchor(anchor, about) : "";
    keepsText(draftQuote, label);
    const located = Boolean(resolved && resolved.status !== "outdated");
    draftQuote.classList.toggle("lf-unseen", !label || (located && !about));
  }

  function render({ readings, draft }) {
    const notes = new Map();
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
        if (holder && !inChrome(holder))
          notes.set(holder, [...(notes.get(holder) ?? []), thread.id]);
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

  const onLayoutInvalidated = (event) => {
    // A page visual's parts can move without its nodes moving, and their registration
    // says so with this signal (visual-parts.js, `update`).
    if (!inChrome(event.target)) plannedFor = null;
    invalidatePageGeometry();
    queueInvalidation();
  };

  const onMessageReference = (event) => {
    const anchor = event.target.closest(MSG_REF);
    if (anchor && !fragmentTarget(anchor.getAttribute("href"))) event.preventDefault();
  };

  const onOutsideReaction = (event) => {
    for (const record of reactionSeats.values())
      if (
        record.expanded &&
        !event.composedPath().some((node) => record.margin.contains(node))
      )
        setReactionRemoval(record, null);
  };

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("lf-layout", onLayoutInvalidated);
    document.addEventListener("pointerdown", onOutsideReaction, { capture: true });
    messageReferenceRoot.addEventListener("click", onMessageReference);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("lf-layout", onLayoutInvalidated);
      document.removeEventListener("pointerdown", onOutsideReaction, { capture: true });
      messageReferenceRoot.removeEventListener("click", onMessageReference);
    }
    mounted = false;
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
