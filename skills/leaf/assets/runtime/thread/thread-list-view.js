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
   selected card when visible and otherwise selects the first visible card. Releasing
   an allocation returns selection to the most recent surviving choice, so refusing
   a provisional thread preserves the conversation the user had selected.

   Focus given to the list goes on to the selected card's title or withdrawn notice's
   Dismiss button, whatever gave it — `g T`, Escape from the panel's find box, or a fold
   that took the focused card. The list keeps focus itself only while it shows no
   selected allocation, and its ring never outlines one. No title holds focus closed:
   focus, selection and the open card never part.

   The list also decides when a card leaves it (`keeping`), and news takes no card
   out from in front of the user: a card another actor resolves under Open stays where
   it stands, its card holding the resolution behind its notice (held-news.js) and,
   once shown, drawn resolved in the shape it stood in, until its going would move
   nothing the user sees. One HeldNews owns the complete panel reading, both changes
   inside cards and new cards that would move them. Held arrivals keep their native
   nodes connected but hidden so widget proof and direct destinations remain available;
   the existing card notice or a direct arrival reveals them before focus lands.
   A withdrawn root follows the same lifetime rule, but keeps
   only its measured allocation and a Dismiss notice: its controls disconnect, its
   semantic membership ends, and a selected allocation holds off fallback disclosure.
   Dismissal or choosing another card releases it; changing view or leaving the
   reading releases it under the same geometry and continuity policy as other news. */
import { html, repeat, ref } from "../../vendor/browser-runtime.js";
import { holdFocus, onStanding, focusDestination, focused } from "../focus.js";
import { RetainedFace } from "../retained-face.js";
import { ThreadView } from "./thread-card.js";
import { threadHoldsDraft } from "./replies.js";
import { forwardToThread } from "./focus.js";
import { passOn, retainUserIntent } from "../user-intent.js";
import { layoutChanged } from "../widget-elements.js";
import { isFolding } from "./folding.js";
import { threadKey } from "./model.js";
import { elementBorderFrame, growthIsSeen, whenNone } from "../geometry.js";
import { gesturedOn, HeldNews } from "./held-news.js";
import { PENDING } from "./identity.js";
import { readingIsContinuous } from "../reading-continuity.js";
import { layoutPx } from "../keeps.js";

const TAG = "leaf-thread-list";

const EMPTY_MODEL = Object.freeze({
  rows: Object.freeze([]),
  count: null,
  pageSeats: new Map(),
});

// Whether the user has a reply or a rewrite on its way in `thread`: a message the
// ledger draws under its pending id, or new words standing over one of theirs
// (`foldThreads`). A reaction is a mark, not a turn.
const turnOnItsWay = (thread) =>
  thread.msgs.some(
    (message) =>
      (message.id.startsWith(PENDING) && !message.token) || message.edited?.pending,
  );

class ThreadListView extends RetainedFace {
  #commands = null;
  #views = new Map();
  #restoreFocusAfterPaint = null;
  #generation = 0;
  #rows = [];
  #committedRows = [];
  #retaining = false;
  #rollbackFocus = null;
  #selection = [];
  #intent = null;
  #leaving = new Map();
  #news = new HeldNews(
    this,
    (key) => this.#views.get(`thread:${key}`),
    () => {
      this.requestUpdate("model");
      this.performUpdate();
      this.#commands?.repaintThread();
    },
  );
  #newsCandidate = null;
  #dismissed = new Set();
  #withdrawnFocus = null;

  // An absent root is no longer a thread: disconnect its controls and keep only the
  // allocation the reader stood in. Membership and order come from the complete
  // committed reading, so refusing a candidate restores the same native cards.
  #withWithdrawals(rows, intent) {
    const present = new Set(rows.map((row) => row.key));
    const prior = this.#committedRows;
    const chosen = this.#selection.find((key) =>
      this.#rows.some((row) => row.key === key),
    );
    for (let i = prior.length - 1; i >= 0; i--) {
      const row = prior[i];
      if (present.has(row.key) || this.#dismissed.has(row.key)) continue;
      const drawn = this.#rows.find((drawn) => drawn.key === row.key);
      const node = drawn?.node;
      const view = this.#views.get(row.key);
      if (
        this.#intent !== intent ||
        !readingIsContinuous() ||
        !node?.isConnected ||
        (row.kind !== "withdrawn" &&
          (row.kind !== "thread" ||
            !view?.model.visible ||
            view.model.folding ||
            gesturedOn(row.descriptor.source))) ||
        !(row.key === chosen ? this.checkVisibility() : growthIsSeen(node))
      )
        continue;
      const withdrawn =
        row.kind === "withdrawn"
          ? row
          : Object.freeze({
              kind: "withdrawn",
              key: row.key,
              id: row.descriptor.id,
              topic: row.descriptor.summary.topic,
              extent: elementBorderFrame(node).height,
            });
      const following = prior.slice(i + 1).find((next) => present.has(next.key));
      const preceding = prior
        .slice(0, i)
        .findLast((previous) => present.has(previous.key));
      const at = following
        ? rows.findIndex((next) => next.key === following.key)
        : preceding
          ? rows.findIndex((previous) => previous.key === preceding.key) + 1
          : 0;
      rows.splice(at, 0, withdrawn);
      present.add(row.key);
    }
    return rows.some((row) => row.kind === "withdrawn")
      ? rows.filter((row) => row.kind !== "empty")
      : rows;
  }

  #visibleRows() {
    const eligible = new Set(
      this.model.rows
        .filter(
          (row) =>
            row.kind === "thread" &&
            this.#views.get(row.key)?.model.visible &&
            !this.#views.get(row.key)?.model.folding,
        )
        .map((row) => row.key),
    );
    return this.#rows.filter((row) => row.kind === "thread" && eligible.has(row.key));
  }

  #select(key) {
    const previous = this.#expandedRow();
    this.#selection = [key, ...this.#selection.filter((chosen) => chosen !== key)];
    if (previous?.kind === "withdrawn" && previous.key !== key) {
      this.#dismissed.add(previous.key);
      this.#commands.repaintThread();
    }
  }

  #expandedRow() {
    const present = new Set(this.#rows.map((row) => row.key));
    const preferred = this.#selection.find((key) => present.has(key));
    const visible = this.#visibleRows();
    return (
      this.#rows.find((row) => row.kind === "withdrawn" && row.key === preferred) ??
      visible.find((row) => row.key === preferred) ??
      visible[0]
    );
  }

  #showExpanded() {
    const chosen = this.#expandedRow();
    if (!chosen) return;
    for (const row of this.#visibleRows())
      row.node.toggleAttribute("open", row === chosen);
  }

  // The user's own move onto a card's title chooses the card, whatever route took them
  // there, so the focused thread is always the open one. A press waits for its click
  // (thread-card.js), which lands what it chose, and a return puts them back where they
  // had chosen, or on the card the list shows while a change holds theirs from it,
  // which is no choice of theirs.
  chooseTitle(title) {
    this.#choose(title.parentElement);
  }

  // An open title is still the user's focus stop for the thread. A second press leaves
  // it selected; choosing another title moves disclosure.
  #choose(card) {
    const row = this.#visibleRows().find((row) => row.node === card);
    if (!row) return;
    this.#commands.beforeChoose(card);
    this.#select(row.key);
    this.#showExpanded();
  }

  #dismiss(row) {
    this.#dismissed.add(row.key);
    this.#commands.repaintThread();
  }

  // Why a shown card the view no longer admits stays shown, or null where it goes: the
  // narrowing says which threads the view admits (narrowing.js), this says when a card
  // it stops admitting leaves, and the model builder combines the two into one reading.
  // A change of view puts any card away. What took the card out of the view is read in
  // the render that first does, and its card carries the answer while it stays. The
  // user's own gesture on the thread (`gesturedOn`) takes the card in the turn it is
  // drawn, or, while its reply holds words, once the words go ("draft"), so settlement
  // never puts a draft away; its thread owner folds a settlement out, and widens the
  // view to hold a thread the user's own turn took out of it. Anything else is
  // news ("news"), and its card stays, holding the news (held-news.js) or drawn as the
  // news left it in the shape it stood in, while its going would move something the
  // user sees: while its going would be (geometry.js, `growthIsSeen`), since every
  // card after it would rise, and, as the card the list shows open, while the panel
  // shows, since another card would open in its place. Out of sight it stays only for
  // its words, with the cause that first excluded it still carried. Its going out of
  // sight asks for the render that lets it go (`#watchKept`), as does its closing when
  // the user opens another card.
  keeping(thread, intent) {
    const key = threadKey(thread);
    const view = this.#views.get(`thread:${key}`);
    if (this.#intent !== intent || !view?.model.visible || view.model.folding)
      return null;
    const seen =
      readingIsContinuous() &&
      (view.node.open ? this.checkVisibility() : growthIsSeen(view.node));
    const draft = threadHoldsDraft(
      key,
      thread.msgs.map(({ id }) => id),
    );
    // A turn of the user's own on its way, a reply or a rewrite, makes a card news kept
    // theirs: the turn takes the card out as any turn of theirs does (thread-card.js,
    // `#speak`). A reaction, a move or words not yet sent leave it held for the news.
    const news = view.model.kept
      ? view.model.kept === "news" && !turnOnItsWay(thread)
      : !gesturedOn(thread);
    if (news && (seen || draft)) return "news";
    return draft ? "draft" : null;
  }

  #watchKept() {
    const kept = new Set(
      this.#rows
        .filter(
          (row) =>
            row.kind === "withdrawn" ||
            (row.kind === "thread" && this.#views.get(row.key).model.kept),
        )
        .map((row) => row.node)
        .filter(Boolean),
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
          whenNone([node], growthIsSeen, () => this.#commands.repaintThread()),
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

  // Whether the card drawn for thread or message `id` stands only for the user's own
  // words on their way (`keeping`, "draft"): drawn, though the view leaves it out.
  keepsForWords(id) {
    const row = this.#rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key).ownsMessage(id),
    );
    return Boolean(row) && this.#views.get(row.key).model.kept === "draft";
  }

  revealNavigation(id) {
    const row = this.#rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key).ownsMessage(id),
    );
    // Narrowing owns hidden rows. Its completed reveal calls back here; opening
    // one before that would paint no disclosure and invalidate the same transition.
    if (!row) return;
    this.#select(row.key);
    // A direct destination may be connected for widget proof while its card waits
    // behind news. Choose it before revealing, so that paint opens it once.
    this.#news.showThreads(id);
    if (row.node.hidden) return;
    this.#showExpanded();
  }

  incomingTail(reading, card) {
    const prior = this.committed.rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key)?.node === card,
    );
    const next = prior && reading.rows.find((row) => row.key === prior.key);
    return next?.kind === "thread"
      ? this.#views.get(prior.key).incomingTail(prior.descriptor, next.descriptor)
      : null;
  }

  messageTail(id) {
    const view = [...this.#views.values()].find((view) => view.ownsMessage(id));
    return view?.messageTail(id) ?? null;
  }

  constructor() {
    super(EMPTY_MODEL);
    this.addEventListener("focus", () => {
      this.#showExpanded();
      const open = this.#expandedRow();
      if (!open) return;
      // Handed on with the cause that gave the list its focus (`chooseTitle`).
      if (open.kind === "withdrawn")
        focusDestination(open.node.querySelector("button"), "return");
      else forwardToThread(open.node);
      passOn(this, focused());
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
    this.#newsCandidate?.commit();
    const wanted = new Set(
      model.rows.filter((row) => row.kind === "thread").map((row) => row.key),
    );
    // This committed list is the complete view of known threads, even while its
    // saved inventory count is unknown. Retire refused local choices and preserve
    // withdrawn allocations through the same selection identity path.
    const present = new Set(this.#rows.map((row) => row.key));
    this.#selection = this.#selection.filter((key) => present.has(key));
    this.#dismissed = new Set(
      this.#rows
        .filter((row) => row.kind === "withdrawn" && this.#dismissed.has(row.key))
        .map((row) => row.key),
    );
    const chosen = this.#expandedRow();
    if (chosen) this.#select(chosen.key);
    this.#committedRows = this.#rows.map((row) =>
      row.kind === "thread"
        ? model.rows.find((candidate) => candidate.key === row.key)
        : row.kind === "withdrawn"
          ? Object.freeze({
              kind: row.kind,
              key: row.key,
              id: row.id,
              topic: row.topic,
              extent: row.extent,
            })
          : row,
    );
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
    this.#news.restore();
    try {
      await this.paint(this.committed, { now: true });
      if (generation !== this.#generation) return false;
      const focus = this.#rollbackFocus;
      if (focus?.node.isConnected && focus.mayRestore())
        focusDestination(focus.node, "return");
      this.#rollbackFocus = null;
      return this.committed;
    } finally {
      this.#retaining = false;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model") || !this.#commands) return;
    this.#restoreFocusAfterPaint ??= holdFocus(this);
    // A change of view moves the cards, so they show what they hold.
    const viewChanged = this.#intent !== this.model.intent;
    if (viewChanged || this.#retaining) this.#news.release();
    // News compares with the actual paint, while complete list commit owns the
    // rollback checkpoint. Restoring that checkpoint must restore news with it.
    this.#newsCandidate = this.#news.prepare(
      {
        threads: this.model.rows
          .filter((row) => row.kind === "thread")
          .map((row) => row.descriptor),
      },
      { row: false },
    );
    const drawn = new Map(
      this.#newsCandidate.reading.threads.map((descriptor) => [
        descriptor.key,
        Object.freeze(descriptor),
      ]),
    );
    const rows = [];
    const wanted = new Set();
    // Allocations are mechanical paint state. Reconcile them on every attempt,
    // including a retry after rollback restored a formerly dismissed live card.
    const allocated = this.#retaining
      ? this.#committedRows
      : this.#withWithdrawals([...this.model.rows], this.model.intent);
    this.#intent = this.model.intent;
    for (const row of allocated) {
      if (row.kind !== "thread") {
        if (row.kind === "withdrawn") {
          const previous = this.#rows.find((drawn) => drawn.key === row.key);
          if (previous?.node?.contains(focused())) this.#withdrawnFocus = row.key;
          rows.push({ ...row, node: null });
        } else rows.push(row);
        continue;
      }
      this.#dismissed.delete(row.key);
      wanted.add(row.key);
      let view = this.#views.get(row.key);
      if (!view) {
        this.#views.set(
          row.key,
          (view = new ThreadView("panel", {
            ...this.#commands.card,
            choose: () => this.#choose(view.node),
          })),
        );
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
      }
      const descriptor = drawn.get(row.descriptor.key);
      view.present(descriptor ?? Object.freeze({ ...row.descriptor, visible: false }), {
        retaining: this.#retaining,
        viewChanged,
      });
      rows.push({ kind: "thread", key: row.key, node: view.node });
    }
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    // The list says it shows nothing once the last card has given its room back. Said
    // while that card still folds, the words stood above it and carried it down.
    const giving = rows.some((row) => row.kind === "thread" && isFolding(row.node));
    this.#rows = giving ? rows.filter((row) => row.kind !== "empty") : rows;
  }

  updated() {
    // Lit and the cards have drawn this candidate. Acknowledge it before focus or
    // summary callbacks can synchronously prepare another reading.
    this.#newsCandidate?.painted();
    this.#showExpanded();
    const restore = this.#restoreFocusAfterPaint;
    this.#restoreFocusAfterPaint = null;
    const withdrawn = this.#rows.find(
      (row) => row.kind === "withdrawn" && row.key === this.#withdrawnFocus,
    );
    this.#withdrawnFocus = null;
    restore?.(withdrawn?.node.querySelector("button"), this);
    this.#watchKept();
    this.#commands?.presentSummary(this.model);
  }

  #row(row) {
    if (row.kind === "thread") return row.node;
    if (row.kind === "withdrawn")
      return html`<div
        ${ref((node) => {
          row.node = node;
        })}
        class="lf-thread-withdrawn lf-thread-compact"
        data-withdrawn=${row.id}
        style=${`min-block-size:${layoutPx(row.extent)}`}
      >
        <div class="lf-thread-summary">
          <span class="lf-thread-topic">${row.topic}</span>
          <span class="lf-thread-meta" role="status">Thread withdrawn</span>
          <button
            type="button"
            class="lf-thread-trailing"
            aria-label=${`Dismiss withdrawn thread: ${row.topic}`}
            @click=${() => this.#dismiss(row)}
          >
            Dismiss
          </button>
        </div>
      </div>`;
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

onStanding((node, cause) => {
  if ((cause === "move" || cause === "step") && node?.matches?.(".lf-thread-summary"))
    node.closest(TAG)?.chooseTitle(node);
});
export const createThreadListView = () => document.createElement(TAG);
