/* The panel's keyed Lit list and complete committed presentation reading.
   Native card roots are retained by stable thread identity. Only their ThreadView
   owns generated descendants; retention re-renders values, never captured DOM.
   Count and narrowing paint share the rows' checkpoint and update boundary.
   The list owns the one expanded visible thread and writes every shown card's
   disclosure from that choice, while cards retain their message and editor nodes; a
   card whose title takes focus, by Tab, press or script, and a card the browser opens
   itself, as find-in-page does, become the choice. The cards
   carry no native `name`: its exclusivity closes a card the moment it is named beside
   an open one, which the list's own choice then opens again. This mechanical state
   never publishes a new application epoch. Narrowing keeps the
   selected card when visible and otherwise selects the first visible card. A thread
   that leaves the reading returns selection to the most recent surviving choice, so
   refusing a provisional thread preserves the conversation the user had selected.

   Focus given to the list goes on to that card's title, whatever gave it — `g T`, an
   Escape from the panel's general box, a fold that took the focused card — so
   every key answers for the thread the screen shows selected. The list keeps focus
   itself only while it shows no card, and its ring never outlines one, and no title
   holds focus closed: focus, selection and the open card never part.

   The list also decides when a card leaves it (`keeping`), and news takes no card
   out from in front of the user: a card another actor resolves under Open stays where
   it stands, drawn resolved, until its going would move nothing the user sees. */
import { html, repeat } from "../../vendor/browser-runtime.js";
import { focused } from "../keyboard/scopes.js";
import { RetainedFace } from "../retained-face.js";
import { ThreadView } from "./thread-card.js";
import { draftHasContent } from "../drafts.js";
import { focusThread } from "./focus.js";
import { passOn, retainUserIntent } from "../user-intent.js";
import { layoutChanged } from "../widget-elements.js";
import { nextRender } from "../rendering.js";
import { foldOut, finishFold, isFolding } from "./folding.js";
import { threadKey } from "./model.js";
import { seenRect, whenOffScreen } from "../geometry.js";
import { readApplication } from "../semantic-state.js";

const TAG = "leaf-thread-list";

// Whether this page's ledger holds a gesture of the user's on `thread`: a settlement,
// reply or reaction on one of its messages, a move on a widget one of them holds, or
// the refusal that takes one back.
function gesturedOn(thread) {
  const { unresolved, document } = readApplication();
  const messages = new Set(thread.msgs.map(({ id }) => id));
  return unresolved.some(
    ({ event }) =>
      messages.has(event.parent) ||
      (event.widget &&
        messages.has(document.descriptors.get(event.widget)?.document.message)),
  );
}
const EMPTY_MODEL = Object.freeze({
  rows: Object.freeze([]),
  count: null,
  pageSeats: new Map(),
});

class ThreadListView extends RetainedFace {
  #commands = null;
  #views = new Map();
  #focusListAfterPaint = false;
  #generation = 0;
  #rows = [];
  #retaining = false;
  #rollbackFocus = null;
  #passingFocus = false;
  #selection = [];
  #draftViews = new Set();
  #draftFrame = 0;
  #intent = null;
  #leaving = new Map();

  #visibleRows() {
    const eligible = new Set(
      this.model.rows
        .filter(
          (row) =>
            row.kind === "thread" && row.descriptor.visible && !row.descriptor.folding,
        )
        .map((row) => row.key),
    );
    return this.#rows.filter((row) => row.kind === "thread" && eligible.has(row.key));
  }

  #select(key) {
    this.#selection = [key, ...this.#selection.filter((chosen) => chosen !== key)];
  }

  #expandedRow() {
    const present = new Set(this.model.rows.map((row) => row.key));
    const preferred = this.#selection.find((key) => present.has(key));
    const visible = this.#visibleRows();
    return visible.find((row) => row.key === preferred) ?? visible[0];
  }

  #showExpanded() {
    const chosen = this.#expandedRow();
    if (!chosen) return;
    for (const row of this.#visibleRows())
      row.node.toggleAttribute("open", row === chosen);
  }

  // An open title is still the user's focus stop for the thread. A second press leaves
  // it selected; choosing another title moves disclosure.
  #choose(card) {
    const row = this.#visibleRows().find((row) => row.node === card);
    if (!row) return;
    this.#select(row.key);
    this.#showExpanded();
  }

  // Why a shown card the view no longer admits stays shown, or null where it goes: the
  // narrowing says which threads the view admits (narrowing.js), this says when a card
  // it stops admitting leaves, and the model builder combines the two into one reading.
  // A change of view puts any card away. What took the card out of the view is read in
  // the render that first does, and its card carries the answer while it stays. The
  // user's own gesture on the thread (`gesturedOn`) takes the card in the turn it is
  // drawn, or, while its reply holds words, once the words go ("draft"), so settlement
  // never puts a draft away; a settlement folds it out (willUpdate). Anything else is
  // news ("news"), and its card stays, drawn as the news left it, while its going would
  // move something the user sees: while any of it shows, since every card after it
  // would rise, and, as the card the list shows open, while the panel shows, since
  // another card would open in its place. Out of sight it stays only for its words,
  // with the cause that first excluded it still carried. Its
  // leaving the window asks for the render that lets it go (`#watchKept`), as does its
  // closing when the user opens another card.
  keeping(thread, intent) {
    const key = threadKey(thread);
    const view = this.#views.get(`thread:${key}`);
    if (this.#intent !== intent || !view?.model.visible || view.model.folding)
      return null;
    const news = view.model.kept ? view.model.kept === "news" : !gesturedOn(thread);
    const seen = view.node.open
      ? this.checkVisibility()
      : Boolean(seenRect(view.node, new Map()));
    const draft = draftHasContent("reply:" + key);
    if (news && (seen || draft)) return "news";
    return draft ? "draft" : null;
  }

  #watchKept() {
    const kept = new Set(
      this.model.rows
        .filter((row) => row.kind === "thread" && row.descriptor.kept)
        .map((row) => this.#views.get(row.key).node),
    );
    for (const [node, stop] of this.#leaving)
      if (!kept.has(node)) {
        stop();
        this.#leaving.delete(node);
      }
    for (const node of kept)
      if (!this.#leaving.has(node))
        this.#leaving.set(
          node,
          whenOffScreen([node], () => this.#commands.repaintThread()),
        );
  }

  navigationThreads() {
    return this.#visibleRows().map((row) => row.node);
  }

  // The shown cards in the page's order, whichever order the list stands in.
  inPageOrder(cards) {
    const seats = this.model.pageSeats;
    return [...cards].sort((a, b) => seats.get(a.dataset.id) - seats.get(b.dataset.id));
  }

  revealNavigation(id) {
    const node = this.querySelector(
      `[data-id="${CSS.escape(id)}"], [data-mid="${CSS.escape(id)}"]`,
    );
    const card = node?.closest(".lf-thread");
    const row = this.#rows.find((row) => row.kind === "thread" && row.node === card);
    // Narrowing owns hidden rows. Its completed reveal calls back here; opening
    // one before that would paint no disclosure and invalidate the same transition.
    if (!row || card.hidden) return;
    this.#select(row.key);
    this.#showExpanded();
  }

  // Explicit navigation may name a message whose news has not been drawn yet.
  // Locate it in the complete received reading, then release its retained card.
  showNews(id) {
    const row = this.model.rows.find(
      (row) =>
        row.kind === "thread" &&
        (row.descriptor.id === id ||
          row.descriptor.messages.some((message) => message.id === id)),
    );
    return row ? (this.#views.get(row.key)?.showNews() ?? false) : false;
  }

  constructor() {
    super(EMPTY_MODEL);
    this.addEventListener("focus", () => {
      this.#showExpanded();
      const open = this.#expandedRow();
      if (!open) return;
      this.#passingFocus = true;
      try {
        focusThread(open.node, { preventScroll: true });
      } finally {
        this.#passingFocus = false;
      }
      passOn(this, focused());
    });
    // A title pressed by a pointer takes focus on the way down and opens on its click,
    // where the press's landing and the list's place hold already stand (landing.js,
    // thread-list.js); every other focus opens it as it arrives.
    this.addEventListener("focusin", (event) => {
      const title = event.target;
      if (
        !this.#passingFocus &&
        title.matches?.(".lf-thread-summary") &&
        !title.matches(":active")
      )
        this.#choose(title.parentElement);
    });
  }
  configure(commands, initialModel) {
    if (this.#commands) return;
    this.#commands = commands;
    this.model = initialModel;
    super.commit();
  }

  // Forward gestures paint their complete generated result in their sending turn.
  async present(model) {
    const generation = ++this.#generation;
    if (!this.#rollbackFocus && this.contains(focused())) {
      const node = focused();
      this.#rollbackFocus = {
        node,
        mayRestore: retainUserIntent({ source: node, fallback: this }),
      };
    }
    await this.paint(model, { now: true });
    return generation === this.#generation && this.model === model;
  }

  commit(model) {
    if (this.model !== model) return false;
    super.commit();
    const wanted = new Set(
      model.rows.filter((row) => row.kind === "thread").map((row) => row.key),
    );
    // Unknown counts describe unavailable placeholders, not removed identities.
    // Candidate fallback is only paint; the complete committed reading retires
    // departed choices and adopts the choice its narrowing left visible.
    if (model.count !== null) {
      this.#selection = this.#selection.filter((key) => wanted.has(key));
      const chosen = this.#expandedRow();
      if (chosen) this.#select(chosen.key);
    }
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#rollbackFocus = null;
    return true;
  }

  async retainCommitted(candidate) {
    if (this.model !== candidate) return false;
    const generation = ++this.#generation;
    this.#retaining = true;
    try {
      await this.paint(this.committed, { now: true });
      if (generation !== this.#generation) return false;
      const focus = this.#rollbackFocus;
      if (focus?.node.isConnected && focus.mayRestore())
        focus.node.focus({ preventScroll: true });
      this.#rollbackFocus = null;
      return this.committed;
    } finally {
      this.#retaining = false;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model") || !this.#commands) return;
    this.#focusListAfterPaint ||= this.contains(focused());
    this.#intent = this.model.intent;
    const rows = [];
    const wanted = new Set();
    for (const row of this.model.rows) {
      if (row.kind !== "thread") {
        rows.push(row);
        continue;
      }
      wanted.add(row.key);
      let view = this.#views.get(row.key);
      if (!view) {
        this.#views.set(row.key, (view = new ThreadView("panel", this.#commands.card)));
        // A card opened by something other than the list becomes the choice: a reveal
        // says so in the task that opens it, so the card it replaces closes in the same
        // task; the browser's own opening (find-in-page) is heard on its toggle.
        const opened = () => {
          const row = this.#visibleRows().find((row) => row.node === view.node);
          if (!view.node.open || !row || row.key === this.#expandedRow()?.key) return;
          this.#select(row.key);
          this.#showExpanded();
        };
        view.node.addEventListener("lf-reveal", opened);
        view.node.addEventListener("toggle", () => {
          layoutChanged(this);
          opened();
          // A kept card the user closed by opening another goes, if out of sight.
          if (!view.node.open && view.model.kept) this.#commands.repaintThread();
        });
        view.node.addEventListener("click", (event) => {
          if (event.target.closest(".lf-thread-summary")?.parentElement !== view.node)
            return;
          event.preventDefault();
          this.#choose(view.node);
        });
      }
      let descriptor = row.descriptor;
      const prior = view.model;
      if (this.#retaining || !descriptor.resolved || descriptor.visible)
        finishFold(view.node);
      const folding =
        !this.#retaining &&
        descriptor.resolved &&
        (isFolding(view.node) ||
          (prior &&
            !prior.resolved &&
            !prior.folding &&
            prior.visible &&
            !descriptor.visible &&
            foldOut(view.node, this.#commands.repaintThread)));
      if (folding) {
        view.retire();
        descriptor = Object.freeze({
          ...prior,
          id: descriptor.id,
          folding: true,
          grow: false,
          settlement: Object.freeze({ ...prior.settlement, pending: false }),
        });
        if (view.node.contains(focused())) this.focus({ preventScroll: true });
      }
      view.setNavigation({ draftChanged: () => this.#draftChanged(view) });
      view.present(descriptor);
      rows.push({ kind: "thread", key: row.key, node: view.node });
    }
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    this.#watchKept();
    // The list says it shows nothing once the last card has given its room back. Said
    // while that card still folds, the words stood above it and carried it down.
    const giving = rows.some((row) => row.kind === "thread" && isFolding(row.node));
    this.#rows = giving ? rows.filter((row) => row.kind !== "empty") : rows;
  }

  // A folded row says whether its reply holds a draft. A send empties the box and
  // publishes the message it sent as two steps, so the row repaints in the next frame,
  // from where both leave it, rather than once for the emptied box and again for the
  // message.
  #draftChanged(view) {
    this.#draftViews.add(view);
    this.#draftFrame ||= nextRender(() => {
      this.#draftFrame = 0;
      for (const changed of this.#draftViews)
        if ([...this.#views.values()].includes(changed)) {
          changed.repaint();
        }
      this.#draftViews.clear();
    });
  }

  updated() {
    this.#showExpanded();
    const active = focused();
    const recover = this.#focusListAfterPaint;
    this.#focusListAfterPaint = false;
    if ((recover && !this.contains(active)) || active?.closest?.(".lf-thread[hidden]"))
      this.focus({ preventScroll: true });
    this.#commands?.presentSummary(this.model);
  }

  #row(row) {
    if (row.kind === "thread") return row.node;
    if (row.kind === "empty") return html`<div class="lf-empty">${row.text}</div>`;
    return html`<div class="lf-system" data-id=${row.id}>${row.text}</div>`;
  }
  render() {
    return repeat(
      this.#rows,
      (row) => row.key,
      (row) => this.#row(row),
    );
  }
}
if (!customElements.get(TAG)) customElements.define(TAG, ThreadListView);
export const createThreadListView = () => document.createElement(TAG);
