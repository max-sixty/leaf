/* lf-suggestion: Claude's edit to content the user has already seen, offered
 * as a proposal rather than shipped as a fait accompli. The user accepts or
 * rejects it in place; the outcome rides the action channel lf-board opened, and
 * the next version carries the settled markup.
 *
 * Deciding is the end of the matter on screen: the element settles to the
 * surviving slot as soon as the log has taken the decision (the theme drops every
 * mark from it), long before the honoring version exists — the live view is the
 * version plus the user's actions replayed on it. So applyAction states an
 * absolute outcome, which makes a reload, a second tab, and the sender itself all
 * converge on the same view. A pick can be cleared by clicking its mark again; a
 * decision can't. Changing your mind is a comment, and the version reverses it.
 *
 * What deciding must not be is the page rearranging itself under the hand that
 * pressed. It was both. A block change is a struck old paragraph over a tinted
 * new one, so accepting took 179 measured pixels out of the middle of the page in
 * one frame, and everything below jumped up under the pointer; and the row the
 * user had just pressed cleared itself in the same frame, leaving a corner toast
 * as the only evidence that anything had been done at all. Two rules answer it,
 * both of them already written down. Where something has to move it moves as
 * motion, so the retired slot folds over a fifth of a second and the eye follows
 * the sentence to where it went. And the pressed control's own line holds still:
 * the row stays, the control the user pressed says what it did ("✓ Accepted"),
 * and its pair goes without giving up its room. The rail is reserved for the
 * page's life whether or not any row is left in it, so the standing record costs
 * nothing that was going to be reclaimed — and a reader who looks back at the
 * margin can see which changes they took.
 *
 * The word a decision leaves behind has its room from the start: a control that
 * took the room for two more glyphs at the moment it was pressed would move its
 * neighbour on the one line where nothing may. Each control reserves the width of
 * its own decided word as the row is built (reserve), measured in the control's
 * live face rather than stated as a number, so the reservation re-measures itself
 * when the font moves — and the one table below is what the controls write and
 * what they reserve, so the two cannot drift.
 *
 * Placement: the controls hang in the theme's rail, off the column's right edge,
 * on the line the change starts. Two elements say that, because one box cannot.
 * The row is the column's own child, inserted after the block the change sits
 * in: `left: 100%` is the page margin only where the column is the containing
 * block, and inside a positioned widget — a board card — it is that card's edge,
 * which no measurement can undo. Its line comes from a CSS anchor, an empty span
 * the widget prepends to itself and the row names: `top: anchor(top)` is the line
 * that span sits on, mid-sentence included, and the page reflows underneath with
 * both riding along. Hoisted, the row still meets the reader and the tab order
 * beside the change it decides, because it follows that change's own block.
 *
 * The span was there first because the wrapper generated no box to anchor from, and
 * it stays now that the wrapper has one. Which form the wrapper takes is a
 * stylesheet's to say, and a project layer says it again; a span the widget builds
 * for itself is the one thing it can anchor from whatever a layer decides. Anchoring
 * off the wrapper reads correctly on the shipped theme and takes the controls off the
 * page entirely under a layer that makes it `display: contents`, because
 * `checkVisibility()` is false for an element with no box: every row goes to
 * `lf-waiting`, and a change nobody can accept is worse than one with no ring.
 *
 * That margin is the theme's rail, reserved by a page that carries a row at all;
 * measuring is what finds it, not what makes it. Three things are measured, all by
 * one observer serving every suggestion on the page: whether the change is on
 * screen — one inside a collapsed container (a closed <details>, a tab that isn't
 * showing) has no line to hang on, and its row waits, hidden, for the reflow that
 * opens it; whether the page is wide enough to hold the row beside the column
 * (below the rail's breakpoint it keeps its whole width, and an open comment panel
 * takes the rest), where it isn't the row docks into flow where it was hoisted to,
 * a control line under the block it follows; and whether two rows land on top of
 * each other, which a translate nudges apart without touching layout. */
import {
  actionStands,
  agentName,
  FOLD_MS,
  motion,
  movedWords,
  offer,
  once,
  quietWord,
  quoted,
  relabel,
  renderRetired,
  reserve,
  says,
  sendAction,
  textNodesUnder,
  toast,
} from "/leaf.js";

// Each control's word in both states — what #name writes, and what the control
// reserves room for, out of the one table so neither can outgrow the other.
const WORDS = {
  accept: ["✓ Accept", "✓ Accepted"],
  reject: ["✗ Reject", "✗ Rejected"],
};
const verb = (btn) => (btn.matches(".lf-sug-accept") ? "accept" : "reject");

// Every row on the page against the anchor it hangs from, so one observer serves
// all of them and the pass can ask each whether its change is on screen.
const rows = new Map();
let pending = 0;
let observer = null;
let observedColumn = null;
let railStated = false; // --rail is measured off the first row and holds for the page

const schedule = () => {
  cancelAnimationFrame(pending);
  pending = requestAnimationFrame(relayout);
};

// What the row hangs off, and so also what it hangs in.
const column = () => document.querySelector("main") || document.body;

function observeLayout() {
  const nextColumn = column();
  if (!observer) {
    observer = new ResizeObserver(schedule);
    observer.observe(document.body);
  }
  if (observedColumn === nextColumn) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = nextColumn;
  observer.observe(observedColumn);
}

// ---------- word-level emphasis ----------
// A block replacement asked the reader to eyeball-diff two paragraphs for the words
// that moved. The slots' whole tints stay — they are what a dead copy keeps — and on
// the live page the words that differ deepen, painted through the highlight registry
// so no node is wrapped (Paint; don't wrap) and cleared when the suggestion settles.
// movedWords is the layer's one answer to which words differ (lf-diff marks a paired
// diff line through it), so a second differ here would be a second answer to one
// question — and a second threshold to tune.
const EMPHASIS = { del: "lf-sug-del", ins: "lf-sug-ins" };
const emphasized = new Map(); // suggestion element → {del: Range[], ins: Range[]}

function repaintEmphasis() {
  for (const [kind, name] of Object.entries(EMPHASIS)) {
    const ranges = [...emphasized.values()].flatMap((e) => e[kind]);
    // Under the comment marks (priority -1): a passage the reader pointed at
    // outranks the widget's own emphasis wherever the two overlap.
    CSS.highlights.set(name, Object.assign(new Highlight(...ranges), { priority: -1 }));
  }
}

// [from, to) offsets in a slot's concatenated text → Ranges over its text nodes.
function toRanges(segments, spans) {
  const ranges = [];
  for (const [from, to] of spans) {
    const range = document.createRange();
    let pos = 0;
    let started = false;
    for (const seg of segments) {
      const len = seg.end - seg.start;
      if (!started && from < pos + len) {
        range.setStart(seg.node, seg.start + (from - pos));
        started = true;
      }
      if (started && to <= pos + len) {
        range.setEnd(seg.node, seg.start + (to - pos));
        ranges.push(range);
        break;
      }
      pos += len;
    }
  }
  return ranges;
}

// Undock every row, bring back the ones that were waiting, clear the nudges, then
// decide again from a clean layout. A row keeps the margin only if its change is
// rendered — an anchor that isn't leaves it hanging beside the block it was
// hoisted to rather than beside the change — and only if the page is wide enough
// to hold it there: body's own right edge is the page's, since the open comment
// panel is cleared by body's margin (syncLayout). The rest dock into flow.
const GAP = 4;
function relayout() {
  for (const row of rows.keys()) {
    row.classList.remove("lf-docked", "lf-waiting");
    row.style.transform = "";
  }
  const room = document.body.getBoundingClientRect().right;
  // Measure every row before moving any: docking one changes the flow the others
  // sit in, so a decision taken mid-pass reads a half-applied layout.
  const measured = [...rows].map(([row, anchor]) => ({
    row,
    rect: row.getBoundingClientRect(),
    // Whether the change is rendered at all, asked rather than measured: the anchor
    // is an empty span with nothing to measure, and a collapsed container reports its
    // content's last rendered geometry rather than nothing, so a rect could not say.
    shown: anchor.checkVisibility(),
  }));
  const inMargin = [];
  for (const { row, rect, shown } of measured) {
    if (!shown) row.classList.add("lf-waiting");
    else if (rect.right > room) row.classList.add("lf-docked");
    else inMargin.push(row);
  }
  // Those still in the margin walk down the page, each pushed clear of the one
  // above. Re-measured, because docking moved the text they hang beside — and
  // carried here as a list, rather than read back off the class just written.
  const placed = inMargin
    .map((row) => ({ row, rect: row.getBoundingClientRect() }))
    .sort((a, b) => a.rect.top - b.rect.top);
  let floor = -Infinity;
  for (const { row, rect } of placed) {
    const push = Math.max(0, floor + GAP - rect.top);
    if (push) row.style.transform = `translateY(${push}px)`;
    floor = rect.top + push + rect.height;
  }
}

customElements.define(
  "lf-suggestion",
  class extends HTMLElement {
    #row = null;
    #anchor = null;
    #deciding = null; // the decision in flight, so a second press joins it

    connectedCallback() {
      // Re-connection — a card dragged to another column, a replay moving one —
      // must be harmless, and the row is no longer in the subtree that moves, so
      // hanging it again is what carries it along (the emphasis ranges ride the
      // text nodes and move with them).
      if (!once(this)) {
        this.#hang();
        if (this.#row) observeLayout();
        return;
      }
      // Presentation, not input, so an exhibited pending change gets it too:
      // quoting gates the action channel, never what a change looks like.
      this.#emphasize();
      this.#voice();
      // Quoted material is exhibited, not offered: a suggestion inside an
      // exhibit shows what a pending change looks like, so it keeps the marks
      // the theme draws and never grows controls to decide it with.
      if (quoted(this)) return;
      // The line the change starts on, named for the row to hang from. Empty, so
      // it takes no space and says nothing; ids match [a-z0-9-] and `version check` keeps
      // them unique, so the id is already the dashed-ident the name needs.
      this.#anchor = offer("span", "lf-sug-line");
      this.#anchor.style.anchorName = `--sug-${this.id}`;
      this.prepend(this.#anchor);
      // The runtime says it just opened this element's containers (reveal): the row
      // may be waiting on geometry the anchor only now has, and the caller is about
      // to focus it, so the layout question is answered now rather than at the
      // observer's next frame.
      this.addEventListener("lf-reveal", () => relayout());
      this.#row = offer("span", "lf-sug-actions");
      this.#row.style.positionAnchor = `--sug-${this.id}`;
      this.#row.dataset.lfFor = this.id; // which change it decides, for anyone reading the page
      this.#row.append(this.#button("accept"), this.#button("reject"));
      this.#hang();
      // In the document now, so each control measures its decided word in the face it
      // actually renders in and floors itself there — the line the press is made on
      // holds still when the word changes (see the module header).
      for (const btn of this.#row.querySelectorAll(":scope > [role='button']"))
        reserve(btn, WORDS[verb(btn)]);
      // The rail is the row it holds: measured off the first row once its controls
      // hold their decided words' room, and stated on the root element — the page's
      // own inline style, so an exported copy keeps the value it was rendered with.
      // theme.css spends it (body's padding-right) and deliberately states no number.
      if (!railStated) {
        railStated = true;
        const width =
          this.#row.getBoundingClientRect().width +
          parseFloat(getComputedStyle(this.#row).marginLeft);
        document.documentElement.style.setProperty("--rail", Math.ceil(width) + "px");
      }
      // The body's box carries the horizontal question (viewport, comment panel);
      // the current main's carries the vertical one, since anything that moves content
      // down the page changes its height. A live version replaces that main, so the one
      // shared observer follows it rather than retaining the detached version.
      observeLayout();
    }

    disconnectedCallback() {
      rows.delete(this.#row);
      this.#row?.remove(); // it is no longer in the subtree that took it before
      if (!rows.size) {
        observer?.disconnect();
        observer = null;
        observedColumn = null;
      }
      emphasized.delete(this);
      repaintEmphasis();
      schedule();
    }

    // The row belongs to the column rather than to the change, so that `left:
    // 100%` means the page margin (see the header). It goes after the change's
    // own top-level block, which is the reader's and the tab order's place for
    // it. A suggestion authored outside the column — `version check` accepts prose
    // anywhere in body — has none of that margin to reach, and keeps its row
    // beside itself; the measurement then docks it like any row without room.
    #hang() {
      if (!this.#row) return; // a quoted one grew none
      const col = column();
      let perch = this;
      while (perch.parentElement !== col && col.contains(perch.parentElement))
        perch = perch.parentElement;
      perch.after(this.#row);
      rows.set(this.#row, this.#anchor);
      schedule();
    }

    // Through `offer` like every other injected control, so the markers and the
    // element are the runtime's one answer rather than this widget's: "✓ Accept" is
    // a thing to do, and a press is a span (see offer) whatever it says. lf-pill is
    // the margin's shape, the runtime's word too.
    #button(outcome) {
      const btn = offer("button", `lf-pill lf-sug-${outcome}`);
      btn.onclick = () => this.#decide(outcome);
      this.#name(btn, false, this.#label());
      return btn;
    }

    // Everything a control says, in the state it is in: the word it shows (from
    // WORDS, the same table its reservation is measured from), and the name that has
    // to carry the change as well, since the visible word says only the outcome. The
    // change's own words come in rather than being read here, because settling
    // retires the slot they live in and a name asked for afterwards would answer the
    // id. Both controls restate together — the pair's word flips too, unseen inside
    // its hidden box and inside the room both reserved.
    #name(btn, decided, change) {
      const kind = verb(btn);
      // A decided control's word is the page speaking — "✓ Accepted" states which way
      // the decision went, the way a pick mark's "chosen" states which option won — so
      // it is quotable, and paper and a copy keep the record where they drop the offer.
      // Only the control matching the outcome: its pair flips too, unseen inside its
      // hidden box, and words nobody can see are nobody's to quote.
      relabel(btn, WORDS[kind][decided ? 1 : 0], {
        says: decided && this.#row?.dataset.lfOutcome === kind,
      });
      btn.setAttribute(
        "aria-label",
        `${kind === "accept" ? "Accept" : "Reject"}${decided ? "ed" : ""} the suggested change: ${change}`,
      );
      // A decision is the end of the matter, so the record it leaves is a record and
      // not a control: it keeps its place and its focus ring, and refuses a press the
      // way #decide already does.
      btn.setAttribute("aria-disabled", String(decided));
    }

    // What the change is about, for the button's label and the toast: the
    // proposal where there is one, since that is what accepting brings about —
    // a deletion has only the markup it would remove.
    #label() {
      const slot =
        this.querySelector(":scope > lf-new") || this.querySelector(":scope > lf-old");
      const text = (slot && says(slot)) || this.id;
      return text.length > 48 ? text.slice(0, 48) + "…" : text;
    }

    accept() {
      return this.#decide("accept");
    }

    // A press asks for the decision; the log makes it, and only then does the page
    // show it. A suggestion can wait because its decision is terminal — the slot
    // retires, the controls stop offering, no later gesture computes from any of
    // it — so nothing is owed the reader during the round trip, and the round trip
    // is local. What waiting buys is the absence of the other half: a settled
    // suggestion the server never took had to be un-settled in front of the reader,
    // a frame of "✓ Accepted" over a fold that started and stopped. The rule that
    // decides which gestures wait, and what waiting costs, are in CLAUDE.md.
    #decide(outcome) {
      if (this.dataset.lfState) return Promise.resolve(true);
      // The decided state used to be this guard on its own, written in the frame of
      // the press. It now lands when the log takes the decision, and the gap between
      // press and answer is exactly wide enough for a second press to make a second
      // decision beside the first — two lines in the log for one act.
      if (this.#deciding) return this.#deciding;
      // Read before deciding: deciding retires a slot, a retired slot leaves the page's
      // reading, and `says` on what has left the reading answers nothing — the toast
      // then named the widget's id instead of the words the user just judged.
      const label = this.#label();
      // Accepting the fix answers the thread it was written for, so the same
      // event carries it: the mapping is snapshotted into the action, because
      // the honoring version retires this wrapper — attribute and all — and a
      // second POST could fail alone, leaving the outcome and the resolution
      // disagreeing with no repair path.
      const comment = this.getAttribute("resolves");
      const detail = outcome === "accept" && comment ? { resolves: comment } : {};
      const sent = sendAction(this, outcome, detail).then((accepted) => {
        this.#inFlight(null);
        if (!accepted) return false; // unsent means unrecorded, and nothing was painted
        // Usually the accepted state has already replayed this decision. Paint is
        // still owed if another part of that state failed to render, but not if the
        // same event list also carried a later undo: authored state then stands.
        if (actionStands(accepted)) this.#settle(outcome);
        toast(
          `${outcome === "accept" ? "Accepted" : "Rejected"} “${label}” — sent to ${agentName()}`,
        );
        return true;
      });
      this.#inFlight(sent);
      return sent;
    }

    // One fact said twice, because it is owed to two audiences. The field is what
    // refuses the second press above. The attribute is the platform's own word for a
    // surface mid-update — the layer paints it (leaf.js) and a screen reader holds
    // its announcements until it clears, so the labels are read once, as what they
    // ended up saying. Said here rather than at the two ends of the send, so the two
    // cannot come apart; `lf-draft` says the same word for the same reason.
    #inFlight(decision) {
      this.#deciding = decision;
      if (decision) this.setAttribute("aria-busy", "true");
      else this.removeAttribute("aria-busy");
    }

    #settle(outcome) {
      // A settle that changes nothing does nothing, which is what makes the poll's
      // replay of this tab's own decision the no-op an absolute action promises to be.
      // The attribute was idempotent on its own and the fold is not: replayed, it
      // folded a slot that had already folded, from a height it no longer had.
      if (this.dataset.lfState === outcome) return;
      // Read before the state moves: deciding retires the slot, and its words leave
      // the page's reading with it.
      const change = this.#label();
      const fold = this.#fold(outcome);
      this.dataset.lfState = outcome;
      // The retired slot's marker is the layer's rendering of that state, and the
      // theme's one hide rule reads it. The accepted response replays through this
      // method on the gesture's own tab, so it hides the slot in the frame the
      // decision lands; the layer then writes the same mark unconditionally.
      renderRetired(this);
      if (this.#row) {
        // The row stays; what changes is which of the two controls is speaking. A
        // quoted one grew none.
        this.#row.dataset.lfOutcome = outcome;
        for (const btn of this.#row.querySelectorAll(":scope > [role='button']"))
          this.#name(btn, true, change);
      }
      // The emphasis goes with the pending state: a decided suggestion is plain
      // prose. So does the word naming each slot, which is the same fact said to
      // whoever is listening.
      emphasized.delete(this);
      repaintEmphasis();
      this.#voice();
      fold?.();
      schedule(); // the rows below may no longer need the nudge they had
      // The banner's count of what the page is still asking is derived from the page,
      // so tell it the page changed rather than making it poll the DOM.
      document.dispatchEvent(new CustomEvent("lf-answered"));
    }

    // The retired slot's room, given back as motion rather than taken in a frame. Only
    // where there is room worth following: a slot holding block content is the case that
    // moves the page, and an inline one swaps a few words inside a line the reader is
    // looking at.
    //
    // Measured before the decision and played after it, so the state the rest of the
    // page reads is true from the first frame — the log has it, the banner's count has
    // it, a second tab converging on it has it — while the pixels catch up. The inline
    // display outranks the rule that hides the slot for exactly as long as the fold
    // lasts, and nothing but this function writes it.
    //
    // The height is stated as a border box, whatever the slot's own sizing is. The
    // measurement to hand is the rendered box (padding included, since the block form
    // pads its slots), and starting a content-box height there would open the fold two
    // pixels taller than the paragraph it is replacing — a jump on the first frame, in
    // the one animation written to remove one.
    #fold(outcome) {
      const going = this.querySelector(
        outcome === "accept" ? ":scope > lf-old" : ":scope > lf-new",
      );
      if (!going) return null;
      const style = getComputedStyle(going);
      if (style.display !== "block") return null;
      const from = {
        height: going.getBoundingClientRect().height + "px",
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        paddingTop: style.paddingTop,
        paddingBottom: style.paddingBottom,
        opacity: 1,
      };
      const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
      to.opacity = 0;
      return () => {
        going.style.display = "block";
        going.style.boxSizing = "border-box";
        going.style.overflow = "hidden";
        const played = motion(going, [from, to], FOLD_MS);
        const done = () => {
          going.style.display = "";
          going.style.boxSizing = "";
          going.style.overflow = "";
        };
        // A fold interrupted — the element taken out from under it — rejects
        // `finished`. Caught, so it is not an unhandled rejection, and the hand-back
        // runs either way. A reader who asked for less motion gets no animation at
        // all (motion returns null), so the hand-back runs at once and the collapse
        // is the frame the decision lands in.
        played ? played.finished.then(done, done) : done();
      };
    }

    // Which slot is which, for a reader listening. A struck red run and a green one
    // are the whole of what says "these words are going" and "these are the proposal",
    // and none of it is text: a screen reader reads the sentence twice, the two
    // readings contradicting each other, with nothing to say that either is a change.
    // Worst on the case the emphasis below hands back for the same reason — an
    // insert- or delete-only change, where the tint is the entire story and a listener
    // hears one perfectly ordinary sentence.
    //
    // ARIA's own names for the two, said as text, because text is the one thing every
    // screen reader announces in every mode — the bargain the mark note struck, and
    // why role="deletion" is not what stands here. It follows the state exactly as the
    // emphasis does: a decided suggestion is plain prose, so the surviving slot gives
    // up this word along with its marks.
    //
    // "proposed", because the word is only ever on a slot nobody has decided and has to
    // say so itself. Pendingness was encoded as the word's presence, which is the one
    // thing no reader can perceive — there is no settled slot alongside to compare it
    // against — and `deletion` is ARIA's name for the act already carried out, so a
    // listener heard a change announced as made while the page was still asking. The
    // theme shows this word wherever the ✓/✗ row is not there to say the same thing.
    #voice() {
      const decided = Boolean(this.dataset.lfState);
      for (const [tag, word] of [
        ["lf-old", "proposed deletion"],
        ["lf-new", "proposed insertion"],
      ])
        for (const slot of this.querySelectorAll(`:scope > ${tag}`))
          quietWord(slot, decided ? "" : word);
    }

    // The words that moved, as ranges over both slots' own text nodes. Which words
    // those are, and whether the pair shares enough ink to be worth marking at all,
    // is `movedWords` — one answer for every widget that deepens a change, since
    // lf-diff asks the same question of every diff line it might pair, and settles the
    // pairing on the same reading (blockPairs).
    #emphasize() {
      if (this.dataset.lfState) return;
      const oldSlot = this.querySelector(":scope > lf-old");
      const newSlot = this.querySelector(":scope > lf-new");
      if (!oldSlot || !newSlot) return; // insert- or delete-only: the tint is the story
      const [oldSegs, newSegs] = [oldSlot, newSlot].map((slot) => textNodesUnder(slot));
      const read = (segs) =>
        segs.map((s) => s.node.data.slice(s.start, s.end)).join("");
      const moved = movedWords(read(oldSegs), read(newSegs));
      if (!moved) return;
      emphasized.set(this, {
        del: toRanges(oldSegs, moved.del),
        ins: toRanges(newSegs, moved.ins),
      });
      repaintEmphasis();
    }

    // Which of the three changes this is, for anything naming it away from the page:
    // a row on the asks tray, the label on a comment anchored here. The slots are the
    // whole of the answer — both is a rewrite, lf-new alone inserts, lf-old alone
    // deletes — and it is the reading #voice already speaks on the slots themselves,
    // said once for the element. A settled suggestion keeps the word it had: the
    // retired half stays in the markup, and a decision changed the outcome rather than
    // the kind of thing that was proposed.
    lfWord() {
      const cut = this.querySelector(":scope > lf-old");
      const put = this.querySelector(":scope > lf-new");
      return cut && put ? "rewrite" : put ? "insertion" : "deletion";
    }

    // accept | reject: the outcome is absolute, so replaying the sender's own
    // action is a no-op and a second tab lands in the same state.
    applyAction(action) {
      if (action === "accept" || action === "reject") this.#settle(action);
    }
  },
);
