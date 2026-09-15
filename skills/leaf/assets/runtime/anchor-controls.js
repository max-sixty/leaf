/* Retained controls derived from anchor paint.
 *
 * This view owns visual comment proxies, accessible comment notes, standing reaction
 * controls, and message fragment state. Visual proxies are keyed Lit controls inside
 * stable authored-target holders; their holder placement remains mechanical page state.
 * A standing reaction first reveals its dedicated removal action; only that action
 * withdraws the reaction. Commands enter only through the constructor.
 */

import { sameAnchor } from "./anchor-coordinate.js";
import {
  html,
  nothing,
  render as renderTemplate,
  repeat,
} from "../vendor/browser-runtime.js";
import {
  declaredVisualParts,
  fragmentId,
  parentAcross,
  resolveAnchor,
  unclaimedVisualGesture,
  visualAt,
  visualPart,
  visualSelector,
} from "./anchor-resolution.js";
import { registerMarginContribution } from "./margin-entries.js";
import { commandScope } from "./keyboard/scopes.js";
import { scheduleMarginLayout } from "./margin-layout.js";
import { pageQueryAll, pageText } from "./passages.js";
import { registry } from "./registry.js";
import { targetElement, targetParts } from "./resolved-target.js";
import { el, offer, reveal } from "./widget-elements.js";

const NOTE = "lf-mark-note";
const MSG_REF = '.lf-msg-body a[href^="#"]';

export function createAnchorControls({
  commentOnTarget,
  openThread,
  withdrawReaction,
  labelAnchor,
  invalidateConversation,
  invalidatePageGeometry,
  messageReferenceRoot,
  draftQuote,
  focused,
  paintKeys,
}) {
  const visualActionHolders = new Map();
  const reactionSeats = new Map();
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
    if (focus && eventId)
      requestAnimationFrame(() =>
        record.margin?.focus(`reaction:${eventId}:remove`, surface),
      );
  }

  const visualActionAnchor = (anchor) =>
    pageQueryAll(".lf-visual-action").find((control) =>
      sameAnchor(control.lfAnchor, anchor),
    ) ?? null;

  // A proxy sits after the outer disclosure that controls its visibility. Shadow
  // renderers share their host so sibling holders do not reorder on each paint.
  function visualActionSeat(candidate) {
    let seat =
      candidate.getRootNode() instanceof ShadowRoot
        ? candidate.getRootNode().host
        : candidate;
    for (let current = seat; current; current = parentAcross(current))
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
          label: labelAnchor({ section: found.id }).replace(/^§\s*/, "") || found.id,
        },
        ...[...declaredVisualParts(candidate)].flatMap((token) => {
          const part = visualPart(candidate, token);
          return part && unclaimedVisualGesture(part.element)
            ? [{ anchor: { section: found.id, visual: part.id }, label: part.label }]
            : [];
        }),
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
    let current = resolveAnchor(control.lfAnchor, pageText());
    let element = targetParts(current)[0] ?? targetElement(current);
    if (!element) return;
    reveal(element);
    current = resolveAnchor(control.lfAnchor, pageText());
    element = targetParts(current)[0] ?? targetElement(current);
    element?.scrollIntoView({
      behavior: "instant",
      block: "nearest",
      inline: "nearest",
    });
  }

  function activateVisualAction(event) {
    const control = event.currentTarget;
    commentOnTarget({ anchor: control.lfAnchor }, { origin: control });
  }

  const visualActionTemplate = ({ anchor, label }) => html`
    <button
      type="button"
      class="lf-visual-action lf-quiet lf-ui"
      data-lf-gen="1"
      data-lf-offer="button"
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
      if (!holder?.isConnected) {
        if (holder) renderTemplate(nothing, holder);
        holder = offer("span", "lf-visual-actions");
        visualActionHolders.set(seat, holder);
      }
      kept.add(seat);
      const current = focused();
      const standing = holder.contains(current) ? current : null;
      renderTemplate(
        html`${repeat(targets, ({ key }) => key, visualActionTemplate)}`,
        holder,
      );
      // Margin contributions and visual proxies share the authored seat. Keep a stable
      // order and preserve focus when reconciliation has to move a retained holder.
      let after = seat;
      while (after.nextSibling?.matches?.(".lf-margin-cluster[data-lf-external]"))
        after = after.nextSibling;
      if (after.nextSibling !== holder) after.after(holder);
      if (standing?.isConnected && focused() !== standing)
        standing.focus({ preventScroll: true });
    }
    for (const [seat, holder] of visualActionHolders)
      if (!kept.has(seat)) {
        renderTemplate(nothing, holder);
        holder.remove();
        visualActionHolders.delete(seat);
      }
  }

  function publishVisualActions() {
    const groups = pendingVisualActions;
    pendingVisualActions = new Map();
    reconcileVisualActions(groups);
  }

  function prepareVisualActions() {
    pendingVisualActions = visualActionPlan();
    if (document.body.hasAttribute("data-lf-presented")) publishVisualActions();
  }

  // CSS highlights create no accessibility nodes. One hidden button per containing
  // block states the number of comments without wrapping or splitting authored text.
  function noteMarks(notes) {
    for (const [holder, threadIds] of notes) {
      const note =
        holder.querySelector(`:scope > .${NOTE}`) ??
        holder.appendChild(offer("button", NOTE));
      note.lfThreads = threadIds;
      note.onclick = () => {
        const id = note.lfThreads[0];
        if (id) openThread(id, { focus: "thread" });
      };
      const count = threadIds.length;
      const said = `${count} comment${count === 1 ? "" : "s"}`;
      if (note.textContent !== said) note.textContent = said;
    }
    for (const note of pageQueryAll(`.${NOTE}`))
      if (!notes.has(note.parentElement)) note.remove();
  }

  // Each target contributes its complete standing reaction reading. Only the selected
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
          "On a standing reaction",
          [
            {
              id: "reaction.removal.close",
              keys: ["Escape"],
              does: "Hide the remove action",
              line: "hide remove",
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
                record.margin.focus(entryKey, surface);
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
        record.margin = registerMarginContribution({
          key: "standing-reactions",
          target: at,
          read: () => ({
            side: "after",
            state: record.expanded ? "engaged" : "idle",
            claim: false,
            entries: record.roots.flatMap((root) => [
              {
                key: `reaction:${root.id}:open`,
                glyph: registry.$reactions.tokens[root.token]?.glyph ?? root.token,
                label: `${root.token} reaction actions`,
                staticLabel: root.token,
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
              activate: () => record.margin.focus(`reaction:${root.id}:open`),
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
              focus:
                context.input === "keyboard" &&
                context.origin === standing &&
                standing?.matches(":focus-visible, .lf-focus-visible"),
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
      const id = fragmentId(anchor.getAttribute("href"));
      const alive = Boolean(resolveAnchor({ section: id }));
      anchor.classList.toggle("detached", !alive);
      if (alive) anchor.removeAttribute("aria-disabled");
      else anchor.setAttribute("aria-disabled", "true");
      anchor.title = alive
        ? `Jump to § ${id}`
        : `§ ${id} isn't in the version you're viewing`;
    }
  }

  function paintDraft({ open, anchor, about, marked }) {
    const label = open ? labelAnchor(anchor, about) : "";
    if (draftQuote.textContent !== label) draftQuote.textContent = label;
    draftQuote.classList.toggle("lf-unseen", !label || (marked && !about));
  }

  function render(painted) {
    prepareVisualActions();
    noteMarks(painted.notes);
    seatReactions(painted.reactionSeats);
    paintDraft(painted.draft);
    paintMessageReferences();
  }

  function queueInvalidation() {
    if (invalidationQueued) return;
    invalidationQueued = true;
    queueMicrotask(() => {
      invalidationQueued = false;
      if (mounted) invalidateConversation();
    });
  }

  const onLayoutInvalidated = () => {
    invalidatePageGeometry();
    queueInvalidation();
  };

  const onMessageReference = (event) => {
    const anchor = event.target.closest(MSG_REF);
    if (anchor && !resolveAnchor({ section: fragmentId(anchor.getAttribute("href")) }))
      event.preventDefault();
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
    pendingVisualActions = new Map();
    reconcileVisualActions(new Map());
    for (const note of pageQueryAll(`.${NOTE}`)) note.remove();
  }

  // A layout pass repacks existing seats; it does not restate their contribution and
  // reopen the margin/repaint cycle.
  function dockSeats() {
    if (reactionSeats.size) scheduleMarginLayout();
  }

  return {
    mount,
    destroy,
    render,
    publishVisualActions,
    dockSeats,
    visualActionAnchor,
  };
}
