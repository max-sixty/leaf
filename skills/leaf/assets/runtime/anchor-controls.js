/* Retained controls derived from anchor paint.
 *
 * This view owns visual comment proxies, accessible comment notes, standing reaction
 * controls, and message fragment state. A standing reaction first reveals its dedicated
 * removal action; only that action withdraws the reaction. Commands enter only through
 * the constructor.
 */

import { sameAnchor } from "./anchor-coordinate.js";
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
import { marginElement, registerMarginContribution } from "./margin-elements.js";
import { scheduleMarginLayout } from "./margin-layout.js";
import { pageQueryAll, pageText } from "./passages.js";
import { registry } from "./registry.js";
import { targetElement, targetParts } from "./resolved-target.js";
import { el, offer, reveal } from "./widget-elements.js";

export const NOTE = "lf-mark-note";
const SEAT = "lf-reacts";
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
  presentedControl,
  focused,
}) {
  const visualActionHolders = new WeakMap();
  const reactionSeats = new Map();
  let mounted = false;
  let invalidationQueued = false;

  function syncReactionRemoval(record) {
    for (const mark of record.seat.querySelectorAll(":scope > .lf-react-mark"))
      mark.setAttribute(
        "aria-expanded",
        mark.dataset.event === record.expanded ? "true" : "false",
      );
    for (const remove of record.seat.querySelectorAll(":scope > .lf-react-remove"))
      remove.hidden = remove.dataset.event !== record.expanded;
  }

  function setReactionRemoval(record, eventId, { focus = false } = {}) {
    if (eventId)
      for (const other of reactionSeats.values())
        if (other !== record && other.expanded) {
          other.expanded = null;
          syncReactionRemoval(other);
          other.margin?.update({ immediate: true });
        }
    record.expanded = eventId;
    syncReactionRemoval(record);
    record.margin?.update({ immediate: true });
    if (focus && eventId)
      requestAnimationFrame(() => {
        const remove = record.seat.querySelector(
          `:scope > .lf-react-remove[data-event="${CSS.escape(eventId)}"]`,
        );
        presentedControl(remove)?.focus({ preventScroll: true });
      });
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

  function prepareVisualActions() {
    const groups = new Map();
    const claimed = [];
    const kept = new Set();
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
      for (const target of targets)
        if (!claimed.some((anchor) => sameAnchor(anchor, target.anchor))) {
          claimed.push(target.anchor);
          group.push(target);
        }
    }

    for (const [seat, targets] of groups) {
      if (!targets.length) continue;
      let record = visualActionHolders.get(seat);
      if (!record?.holder.isConnected) {
        record = { holder: offer("span", "lf-visual-actions") };
        visualActionHolders.set(seat, record);
      }
      const { holder } = record;
      const unused = new Set(holder.children);
      const controls = targets.map(({ anchor, label }) => {
        let control = [...unused].find((child) => sameAnchor(child.lfAnchor, anchor));
        if (!control) {
          control = offer("button", "lf-visual-action lf-quiet");
          control.onfocus = () => {
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
          };
          control.onclick = () =>
            commentOnTarget({ anchor: control.lfAnchor }, { origin: control });
        }
        unused.delete(control);
        control.lfAnchor = anchor;
        const name = `Respond to ${label}`;
        if (control.textContent !== name) control.textContent = name;
        return control;
      });
      for (const control of unused) control.remove();
      controls.forEach((control, index) => {
        if (holder.children[index] !== control)
          holder.insertBefore(control, holder.children[index] ?? null);
      });
      // Margin contributions and visual proxies share the authored seat. Keep a stable
      // order and preserve focus when reconciliation has to move a retained holder.
      let after = seat;
      while (after.nextSibling?.matches?.(".lf-margin-cluster[data-lf-external]"))
        after = after.nextSibling;
      if (after.nextSibling !== holder) {
        const held = holder.contains(document.activeElement)
          ? document.activeElement
          : null;
        after.after(holder);
        if (held?.isConnected) held.focus({ preventScroll: true });
      }
      kept.add(holder);
    }
    for (const holder of pageQueryAll(".lf-visual-actions"))
      if (!kept.has(holder)) holder.remove();
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

  // Each target contributes one margin seat containing its standing reactions. The
  // target-to-contribution record is authority because margin layout may move the node.
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
        const seat = el("span", `lf-ui ${SEAT}`);
        seat.dataset.lfGen = "1";
        record = { seat, roots, expanded: null, margin: null };
        reactionSeats.set(at, record);
      }
      const { seat } = record;
      record.roots = roots;
      kept.add(at);
      if (at.id) seat.dataset.lfFor = at.id;
      else seat.removeAttribute("data-lf-for");
      if (!roots.some((root) => root.id === record.expanded)) record.expanded = null;
      const wanted = roots.flatMap((root) => {
        let mark = seat.querySelector(
          `:scope > .lf-react-mark[data-event="${CSS.escape(root.id)}"]`,
        );
        if (!mark) {
          const entry = registry.$reactions.tokens[root.token];
          mark = marginElement(offer("button", "lf-react-mark"), {
            key: `reaction:${root.id}:open`,
            glyph: entry?.glyph ?? root.token,
            label: `${root.token} reaction actions`,
            behavior: "disclosure",
            role: "secondary",
          });
          mark.dataset.event = root.id;
          mark.dataset.token = root.token;
        }
        let remove = seat.querySelector(
          `:scope > .lf-react-remove[data-event="${CSS.escape(root.id)}"]`,
        );
        if (!remove) {
          remove = marginElement(offer("button", "lf-react-remove"), {
            key: `reaction:${root.id}:remove`,
            icon: "cross",
            label: `Remove ${root.token} reaction`,
            tone: "negative",
            role: "secondary",
          });
          remove.dataset.event = root.id;
          remove.hidden = true;
          remove.id = `lf-reaction-remove-${root.id}`;
        }
        mark.setAttribute("aria-controls", remove.id);
        mark.onclick = (event) => {
          const standing = focused();
          setReactionRemoval(record, record.expanded === root.id ? null : root.id, {
            focus:
              event.detail === 0 &&
              (standing === mark || standing?.lfForwardedControl === mark) &&
              standing.matches(":focus-visible, .lf-focus-visible"),
          });
        };
        remove.onclick = () => withdrawReaction(root);
        return [mark, remove];
      });
      for (const child of [...seat.children])
        if (!wanted.includes(child)) child.remove();
      wanted.forEach((mark, index) => {
        if (seat.children[index] !== mark)
          seat.insertBefore(mark, seat.children[index] ?? null);
      });
      syncReactionRemoval(record);
      if (!record.margin)
        record.margin = registerMarginContribution({
          key: "standing-reactions",
          target: at,
          controls: seat,
          items: () =>
            record.roots.map((root) => ({
              id: `reaction:${root.id}`,
              text: `${root.token} reaction actions`,
              activate: () =>
                record.seat
                  .querySelector(`[data-event="${CSS.escape(root.id)}"]`)
                  ?.focus({ preventScroll: true }),
            })),
          side: "after",
          state: () => (record.expanded ? "engaged" : "idle"),
          claim: false,
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
        !event.composedPath().some((node) => {
          const source = node?.lfForwardedControl ?? node;
          return source instanceof Node && record.seat.contains(source);
        })
      )
        setReactionRemoval(record, null);
  };

  const onReactionKeydown = (event) => {
    if (event.key !== "Escape") return;
    const standing = focused();
    const active = standing?.lfForwardedControl ?? standing;
    for (const record of reactionSeats.values()) {
      if (!record.expanded || !record.seat.contains(active)) continue;
      const mark = record.seat.querySelector(
        `:scope > .lf-react-mark[data-event="${CSS.escape(record.expanded)}"]`,
      );
      setReactionRemoval(record, null);
      presentedControl(mark)?.focus({ preventScroll: true });
      event.preventDefault();
      event.stopPropagation();
      return;
    }
  };

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("lf-projection", queueInvalidation);
    document.addEventListener("lf-layout", onLayoutInvalidated);
    document.addEventListener("pointerdown", onOutsideReaction, { capture: true });
    document.addEventListener("keydown", onReactionKeydown, { capture: true });
    messageReferenceRoot.addEventListener("click", onMessageReference);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("lf-projection", queueInvalidation);
      document.removeEventListener("lf-layout", onLayoutInvalidated);
      document.removeEventListener("pointerdown", onOutsideReaction, { capture: true });
      document.removeEventListener("keydown", onReactionKeydown, { capture: true });
      messageReferenceRoot.removeEventListener("click", onMessageReference);
    }
    mounted = false;
    for (const record of reactionSeats.values()) record.margin.unregister();
    reactionSeats.clear();
    for (const holder of pageQueryAll(".lf-visual-actions")) holder.remove();
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
    dockSeats,
    visualActionAnchor,
  };
}
