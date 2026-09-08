/* Retained comment-panel thread cards and their controls. */
import { isMarked, placedAt, scrollToThread } from "../anchors.js";
import { threadsBox } from "./panel.js";
import { turns } from "./model.js";
import { anchorLabel, msgNode, msgNodeIn, syncMsgNode } from "./messages.js";
import { paintReactStrips } from "./reaction-strips.js";
import { el, reachedForWords } from "../widget-elements.js";
import { panelCovers, setPanel } from "../chrome-layout.js";
import { keys, paintKeys } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { wireReply } from "./replies.js";
import { settlementControl } from "./folding.js";
import { retainPanelLanding, showThread } from "./landing.js";
import { openThreads, threadList } from "./reconcile.js";
import { focusSurface } from "./surfaces.js";

const hasDestination = (id) => isMarked(id) || Boolean(placedAt(id));

// A thread's node is found where it already stands — the open list or the resolved
// disclosure — and kept: the log is append-only, so a kept node only ever gains
// messages and refreshes its clocks. A settlement transition reshapes a node: resolving
// removes the reply box and reopening restores it, so either one rebuilds the node;
// msgBodies carries the rendered bodies across. `grow` animates what this call creates,
// for arrivals into a list the user is already looking at.
// The card standing for this thread, by its id or — while the log is still answering for
// a comment the reader just sent — by the attempt its root carries. The server's event
// carries that attempt back, so the card the send drew keeps its place in the list, the
// focus inside it, and any reply already typed into its box.
const standingCard = (t) =>
  threadsBox.querySelector(`.lf-thread[data-id="${t.root.id}"]`) ??
  (t.root.attempt
    ? threadsBox.querySelector(`.lf-thread[data-attempt="${t.root.attempt}"]`)
    : null);

export function threadNode(t, grow) {
  const existing = standingCard(t);
  const existingResolved = existing && !existing.querySelector(":scope > .lf-compose");
  if (existing && existingResolved === Boolean(t.resolved)) {
    if (existing.dataset.id !== t.root.id) {
      existing.dataset.id = t.root.id;
    }
    const compose = existing.querySelector(":scope > .lf-compose");
    const tail =
      existing.querySelector(":scope > .lf-receipt") ??
      compose ??
      existing.querySelector(":scope > .lf-thread-actions");
    // New messages append before the source-less fallback or thread controls.
    for (const m of turns(t)) {
      let msg = msgNodeIn(existing, m);
      if (!msg) {
        msg = msgNode(m);
        if (grow) msg.classList.add("grow");
        existing.insertBefore(msg, tail);
      }
      syncMsgNode(msg, m);
    }
    paintReactStrips(existing, t);
    return existing;
  }

  const div = el("div", "lf-thread");
  // The card's own name for its thread, read at use rather than captured: the log
  // answering for a comment the reader just sent renames this node in place, and a
  // handler holding the earlier name would go on addressing a thread nothing wears.
  const liveId = () => div.dataset.id;
  div.tabIndex = -1; // t/T focus target; the thread scope's Enter drops into its reply box
  div.dataset.id = t.root.id;
  if (t.root.attempt) div.dataset.attempt = t.root.attempt;
  if (grow) div.classList.add("grow");
  const label = anchorLabel(t.anchor, t.root.about);
  if (label) {
    const quote = el("blockquote", "lf-quote");
    quote.append(el("span", "lf-quote-label", label));
    quote.tabIndex = 0;
    quote.setAttribute("role", "button");
    // The quote is words and a press at once: it says which passage the comment is
    // about, and pressing it travels there. A drag across it is the reader taking the
    // words, so the travel stands down — the reading `offer` makes of its own
    // controls, which this is not one of.
    quote.onclick = (ev) => {
      if (ev.detail !== 0 && reachedForWords(quote)) return;
      // A covering sheet should spend itself only on a real return. `detached` cannot
      // answer that: a resolved thread has no painted mark but keeps the placement it
      // can still travel to. Read the anchor pass's two destination records instead.
      if (!hasDestination(liveId())) return;
      if (panelCovers()) setPanel(false);
      scrollToThread(liveId(), {
        land: () => focusSurface(liveId()),
      });
    };
    keys(quote, "On a comment's quoted passage", [
      {
        id: "passage.return",
        keys: PRESS,
        does: "Return to the quoted passage on the page",
        line: "return to the passage",
        when: () => hasDestination(liveId()),
        run: () => quote.click(),
      },
    ]);
    div.append(quote);
  }
  let resolve = null;
  if (!t.resolved) {
    // Resolve belongs to the whole thread. Keep it beside the thread's quoted address,
    // before any message controls in the keyboard order; a message head says only who
    // wrote that message and when.
    resolve = settlementControl(t, {
      liveId,
      prepareLanding: () => {
        // Resolving removes this card and its focus. Land on the thread that takes its
        // place, or the previous thread when this one was last in the list.
        const mayLand = retainPanelLanding(div);
        const at = openThreads().indexOf(div);
        return () => {
          if (!mayLand()) return;
          const kept = openThreads();
          (kept[at] ?? kept[at - 1] ?? threadsBox).focus({ preventScroll: true });
        };
      },
    });
    div.append(resolve);
  }
  turns(t).forEach((m) => div.append(msgNode(m)));
  paintReactStrips(div, t);
  if (!t.resolved) {
    const row = el("div", "lf-compose");
    const input = document.createElement("textarea");
    input.name = "reply";
    const send = el("button", "lf-btn primary lf-thread-send", "Send");
    row.append(input, send);
    wireReply(t, input, send, liveId);
    div.append(row);
  } else {
    const actions = el("div", "lf-thread-actions");
    const status = el("span");
    if (t.resolved.author === "claude") {
      // Said only where the reader was not the one who closed it. Their own resolve
      // needs no telling: they pressed it, and the disclosure they find it under is
      // already headed "Resolved". A thread closed from the other side settles with
      // nothing in this tab to watch it happen, so the page is the only thing that can
      // say who did.
      const by = t.resolved.agent || "Agent";
      status.append(el("span", "lf-resolved-by", `✓ Resolved by ${by}`));
    }
    const reopen = settlementControl(t, {
      liveId,
      prepareLanding: () => {
        const mayLand = retainPanelLanding(div);
        return () => {
          if (mayLand()) showThread(liveId());
        };
      },
    });
    actions.append(status, reopen);
    div.append(actions);
  }
  return div;
}

// The panel's side of what the anchor pass drew, read off that pass's own record so the
// two views can't disagree: a passage rewritten in a later version has no home to jump to,
// and a dead-looking link is worse than one that says so. Called by the pass that writes
// the record, and again by a narrowing that rebuilt the nodes the record was painted on.
export function paintThreadQuotes() {
  const threads = new Map(threadList().map((t) => [t.root.id, t]));
  for (const div of threadsBox.querySelectorAll(".lf-thread")) {
    const quote = div.querySelector(".lf-quote");
    if (!quote) continue;
    // The words too, for the same reason the class below is repainted here rather than
    // written where the node was built. An element anchor is labelled with its item's
    // own opening words, and the item may be a widget an agent sent — built by this
    // same reconcile and not yet in the document when the node wearing the label was
    // made, so the reading came back empty and the label fell to the bare id. The
    // reconcile keeps a node it has already built, so nothing else ever asked again:
    // `§ off-slip` stood where `§ options · If their release comes and goes…` belonged,
    // for the life of the tab.
    const thread = threads.get(div.dataset.id);
    const said = thread && anchorLabel(thread.anchor, thread.root.about);
    const label = quote.querySelector(":scope > .lf-quote-label");
    if (said && label.textContent !== said) label.textContent = said;
    const outdated = placedAt(div.dataset.id)?.status === "outdated";
    let status = quote.querySelector(":scope > .lf-anchor-status");
    if (outdated && !status) {
      status = el("span", "lf-anchor-status", "Outdated");
      quote.append(status);
    } else if (!outdated) status?.remove();
    // Resolved threads deliberately carry no mark, but retain the placement their
    // folded quote can return to. One reading owns visual, assistive, keyboard, and
    // pointer availability so the same quote never becomes a pointer-only action.
    const found = hasDestination(div.dataset.id);
    quote.classList.toggle("detached", !found);
    quote.setAttribute("aria-disabled", String(!found));
    quote.title = found
      ? outdated
        ? "This comment refers to an earlier data revision"
        : "Jump to this passage"
      : "This passage can't be identified in the version you're viewing";
  }
  paintKeys();
}

// A kept node may still be moved by a later reconcile, and reinsertion restarts CSS
// animations — so the class comes off the moment its animation has run. A node grown
// while its list was off-screen never ran one; the panelOpen gate above is what keeps
// that replay from greeting the panel's next open.
// Wired once the chrome is mounted (chrome.js): the list is the panel's.
export function wireThreadCards() {
  threadsBox.addEventListener("animationend", (ev) =>
    ev.target.classList.remove("grow"),
  );
}
