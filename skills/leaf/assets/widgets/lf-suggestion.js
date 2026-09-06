/* lf-suggestion: an edit to content the reader has already seen, offered as a
 * proposal rather than shipped as a fait accompli. Accept or Reject rides the action
 * channel; the next version eventually carries the settled markup.
 *
 * The log owns the absolute outcome, so reloads and tabs converge. Once that outcome
 * stands, the surviving slot remains and the retired slot folds away as trackable
 * motion. Undo remains while that decision can still be withdrawn. The optimistic
 * content and Undo carry visual feedback; a live announcement says the same decision
 * without restating it on screen, and refusal restores actionable failure controls.
 *
 * The suggestion owns only those controls and their semantics. It contributes the row
 * through `registerMarginItem`; the living margin joins it to comment threads,
 * decisions, delivery status, activity, and temporary reaction controls for this same
 * target.
 * That owner hoists and places the one resulting item, measures the rail, docks it when
 * the margin is too narrow, and reads rendered descendants when a project makes the
 * target `display: contents`. A suggestion never creates a second RHS surface or
 * geometry model of its own. */
import {
  actionAvailable,
  actionStands,
  alignText,
  announce,
  commands,
  FOLD_MS,
  marginButton,
  marginButtonState,
  motion,
  offer,
  once,
  quietWord,
  quoted,
  relabel,
  renderRetired,
  registerMarginItem,
  says,
  sendAction,
  shownParts,
  textNodesUnder,
  notice,
  undoableAction,
  watchActions,
  withdraw,
} from "/runtime/widget-api.js";

const WORDS = { accept: "Accept", reject: "Reject" };
const FACE = {
  accept: { icon: "check", tone: "positive", role: "primary" },
  reject: { icon: "cross", tone: "negative", role: "secondary" },
};
const verb = (btn) => (btn.matches(".lf-sug-accept") ? "accept" : "reject");

// ---------- word-level emphasis ----------
// A block replacement asked the reader to eyeball-diff two paragraphs for the words
// that moved. The slots' whole tints stay — they are what a dead copy keeps — and on
// the live page the words that differ deepen, painted through the highlight registry
// so no node is wrapped (Paint; don't wrap) and cleared when the suggestion settles.
// `movedWords` keeps alignment and the similarity threshold in one reading before
// this module turns its offsets into highlight ranges.
const EMPHASIS = { del: "lf-sug-del", ins: "lf-sug-ins" };
const emphasized = new Map(); // suggestion element → {del: Range[], ins: Range[]}

function movedWords(before, after) {
  const runs = alignText(before, after);
  const ink = (text) => text.replace(/\s+/g, "").length;
  const shared = runs
    .filter((run) => run.kind === "same")
    .reduce((total, run) => total + ink(run.text), 0);
  if (!shared || shared * 3 < Math.min(ink(before), ink(after))) return null;

  const del = [];
  const ins = [];
  let oldOffset = 0;
  let newOffset = 0;
  for (const run of runs) {
    const length = run.text.length;
    if (run.kind !== "insert") {
      if (run.kind === "delete" && run.text.trim())
        del.push([oldOffset, oldOffset + length]);
      oldOffset += length;
    }
    if (run.kind !== "delete") {
      if (run.kind === "insert" && run.text.trim())
        ins.push([newOffset, newOffset + length]);
      newOffset += length;
    }
  }
  return { del, ins };
}

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

customElements.define(
  "lf-suggestion",
  class extends HTMLElement {
    #row = null;
    #failureReceipt = null;
    #deciding = null; // the decision in flight, so a second press joins it
    #staging = false; // the synchronous span before that promise exists
    #failed = null;
    #accept = null;
    #reject = null;
    #retry = null;
    #cancelFailure = null;
    #undo = null;
    #undoing = false;
    #margin = null;
    #stopActions = null;

    connectedCallback() {
      // Re-connection — a card dragged to another column, a replay moving one — must
      // restore this target's contribution to the shared Button cluster.
      if (!once(this)) {
        this.#offer();
        this.#watchActions();
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
      // The runtime says it just opened this element's containers (reveal): the row
      // may be waiting on geometry the target only now has, and the caller is about
      // to focus it, so the layout question is answered now rather than at the
      // observer's next frame.
      this.addEventListener("lf-reveal", () =>
        this.#margin?.update({ immediate: true }),
      );
      this.#row = offer("span", "lf-sug-actions");
      this.#row.dataset.lfFor = this.id; // which change it decides, for anyone reading the page
      this.#accept = this.#button("accept");
      this.#reject = this.#button("reject");
      this.#renderControls();
      this.#offer();
      this.#watchActions();
    }

    #watchActions() {
      if (quoted(this) || !this.#row) return;
      this.#stopActions ??= watchActions(this, null, () => {
        if (!this.dataset.lfState) {
          this.#paintAvailability();
          return;
        }
        this.#renderControls();
        this.#margin?.update();
      });
    }

    disconnectedCallback() {
      this.#stopActions?.();
      this.#stopActions = null;
      this.#margin?.unregister();
      this.#margin = null;
      emphasized.delete(this);
      repaintEmphasis();
    }

    #offer() {
      if (!this.#row || this.#margin) return;
      this.#margin = registerMarginItem({
        key: `suggestion:${this.id}`,
        // An accepted deletion (or rejected insertion) has no surviving slot and the
        // suggestion itself leaves layout. Undo still belongs to the containing passage,
        // so that passage becomes its perch while the gesture can be withdrawn.
        target: () =>
          !this.dataset.lfState ||
          shownParts(this).some((part) => part.checkVisibility())
            ? this
            : this.parentElement,
        controls: this.#row,
        // The slots use tint and strike/insert paint to carry their relationship on the
        // page. Away from that paint, concatenating them turns `red` → `blue` into the
        // meaningless `redblue`; give the shared Page-map projection the same relation
        // in words without teaching it this widget's tags.
        subject: () => this.#subject(),
        state: () =>
          this.#failed
            ? "failed"
            : this.#staging || this.#deciding || this.#undoing
              ? "busy"
              : this.dataset.lfState
                ? "settled"
                : "idle",
        items: () =>
          this.dataset.lfState && !undoableAction(this, this.dataset.lfState)
            ? []
            : [
                {
                  id: `suggestion:${this.id}`,
                  // Before settlement this contribution is the Ask, so suppress the shared
                  // Ask at the same target. Afterwards Undo remains in this cluster without
                  // inventing another page-map reading.
                  kind: this.dataset.lfState ? "action" : "ask",
                  ...(this.dataset.lfState ? {} : { represents: true }),
                  text: this.dataset.lfState
                    ? `${this.dataset.lfState === "accept" ? "Accepted" : "Rejected"} suggested change`
                    : "Accept or reject suggested change",
                  activate: () =>
                    this.#row
                      .querySelector(
                        this.#failed
                          ? '[data-lf-button-key="retry"]'
                          : this.dataset.lfState
                            ? '[data-lf-button-key="undo"]'
                            : "[data-lf-offer='button']",
                      )
                      ?.focus({ preventScroll: true }),
                },
              ],
      });
    }

    // Through `offer` like every other injected control, then through marginButton so
    // this widget supplies only the verb and tone. The shared RHS contract supplies
    // its shape, focus treatment, and responsive label behavior.
    #button(outcome) {
      const btn = offer("button", `lf-sug-${outcome}`);
      btn.onclick = () => this.#decide(outcome);
      this.#name(btn, "idle", this.#label());
      return btn;
    }

    // Everything a control says, in the state it is in: its transient verb (from
    // WORDS), and the name that has to carry the change as well. The
    // change's own words come in rather than being read here, because settling
    // retires the slot they live in and a name asked for afterwards would answer the
    // id. Both controls restate together.
    #name(btn, state, change) {
      const kind = verb(btn);
      btn.removeAttribute("data-lf-said");
      marginButton(btn, {
        key: kind,
        ...FACE[kind],
        label: WORDS[kind],
        state,
      });
      btn.setAttribute(
        "aria-label",
        `${kind === "accept" ? "Accept" : "Reject"} the suggested change: ${change}`,
      );
    }

    #paintAvailability = () => {
      for (const btn of [this.#accept, this.#reject]) {
        const available =
          !this.#staging && !this.#deciding && actionAvailable(this, verb(btn));
        const disabled = String(!available);
        if (btn.getAttribute("aria-disabled") !== disabled)
          btn.setAttribute("aria-disabled", disabled);
        const tabIndex = available ? 0 : -1;
        if (btn.tabIndex !== tabIndex) btn.tabIndex = tabIndex;
      }
    };

    #utilityButton({ key, icon, label, tone = "neutral", role, press }) {
      const button = marginButton(offer("button", ""), {
        key,
        icon,
        label,
        tone,
        role,
        state: this.#failed ? "failed" : this.dataset.lfState ? "settled" : "idle",
      });
      button.onclick = press;
      return button;
    }

    #renderControls(
      change = this.#label(),
      { pending = Boolean(this.#staging || this.#deciding) } = {},
    ) {
      if (!this.#row) return;
      const outcome = this.dataset.lfState;
      if (outcome && !this.#failed) {
        this.#undo ??= this.#utilityButton({
          key: "undo",
          icon: "undo",
          label: "Undo",
          role: "primary",
          press: () => this.#undoOutcome(),
        });
        const undoing = Boolean(pending || this.#undoing);
        marginButtonState(this.#undo, undoing ? "busy" : "settled");
        this.#undo.setAttribute("aria-disabled", String(undoing));
        this.#undo.setAttribute(
          "aria-label",
          `Undo ${outcome === "accept" ? "accepting" : "rejecting"} the suggested change: ${change}`,
        );
        delete this.#row.dataset.lfMarginReceipt;
        this.#replaceControls(
          ...(pending || undoableAction(this, outcome) ? [this.#undo] : []),
        );
        return;
      }

      if (this.#failed) {
        this.#failureReceipt ??= document.createElement("span");
        this.#failureReceipt.className = "lf-margin-receipt";
        relabel(
          this.#failureReceipt,
          this.#failed.undo
            ? `Undo failed · ${outcome === "accept" ? "Accepted" : "Rejected"}`
            : "Failed",
          { says: true },
        );
        this.#retry ??= this.#utilityButton({
          key: "retry",
          icon: "retry",
          label: "Retry",
          role: "complete",
          press: () => this.#retryDecision(),
        });
        this.#cancelFailure ??= this.#utilityButton({
          key: "cancel-failure",
          icon: "cross",
          label: "Cancel",
          role: "escape",
          press: () => this.#cancelFailedDecision(),
        });
        for (const control of [this.#retry, this.#cancelFailure])
          marginButtonState(control, "failed");
        this.#row.dataset.lfMarginReceipt = "failed";
        this.#replaceControls(this.#retry, this.#cancelFailure, this.#failureReceipt);
        return;
      }

      delete this.#row.dataset.lfMarginReceipt;
      const state = this.#deciding ? "busy" : "idle";
      for (const button of [this.#accept, this.#reject]) {
        this.#name(button, state, change);
      }
      this.#paintAvailability();
      this.#replaceControls(this.#accept, this.#reject);
    }

    #replaceControls(...wanted) {
      const active = document.activeElement;
      const source = active?.lfForwardedControl ?? active;
      const held = this.#row.contains(source);
      for (const child of [...this.#row.children])
        if (!wanted.includes(child)) child.remove();
      wanted.forEach((child, index) => {
        if (this.#row.children[index] !== child)
          this.#row.insertBefore(child, this.#row.children[index] ?? null);
      });
      if (held && !wanted.includes(source)) {
        this.#margin?.update({ immediate: true });
        wanted
          .find((node) => node.matches(".lf-margin-button") && node.checkVisibility())
          ?.focus({ preventScroll: true });
      }
      commands(
        this,
        "On a suggested change",
        wanted
          .filter((control) => control.matches?.(".lf-margin-button"))
          .map((control) => {
            const label = control.querySelector(
              ":scope > .lf-margin-button-label",
            ).textContent;
            return {
              id: `suggestion.${control.dataset.lfButtonKey}`,
              keys: [],
              control,
              decision: label,
              does: `${label} the suggested change`,
              line: label.toLowerCase(),
              run: () => control.click(),
            };
          }),
        {
          answer: () => {
            if (!this.dataset.lfState) return "";
            return this.dataset.lfState === "accept" ? "Accepted" : "Rejected";
          },
        },
      );
    }

    // What the change is about, for the button's label and failure receipt: the
    // proposal where there is one, since that is what accepting brings about —
    // a deletion has only the markup it would remove.
    #label() {
      const slot =
        this.querySelector(":scope > lf-new") || this.querySelector(":scope > lf-old");
      const text = (slot && says(slot)) || this.id;
      return text.length > 48 ? text.slice(0, 48) + "…" : text;
    }

    #subject() {
      const cut = this.querySelector(":scope > lf-old");
      const put = this.querySelector(":scope > lf-new");
      const before = cut ? says(cut) : "";
      const after = put ? says(put) : "";
      if (before && after) return `${before} → ${after}`;
      return before || after || this.id;
    }

    accept() {
      return this.#decide("accept");
    }

    // A press makes the reversible decision locally and the outbox carries that exact
    // projection until the log accounts for it. A definitive refusal removes the local
    // winner and reconciles the authored state before this continuation paints the repair
    // controls, so the reader returns to a pending suggestion with Failed, Retry, Cancel.
    #decide(outcome) {
      if (this.dataset.lfState) return Promise.resolve(true);
      if (!actionAvailable(this, outcome)) return Promise.resolve(false);
      if (this.#staging || this.#deciding)
        return this.#deciding ?? Promise.resolve(false);
      // Read before deciding: deciding retires a slot, a retired slot leaves the page's
      // reading, and `says` on what has left the reading answers nothing — the notice
      // then named the widget's id instead of the words the user just judged.
      const label = this.#label();
      // Accepting the fix answers the thread it was written for, so the same
      // event carries it: the mapping is snapshotted into the action, because
      // the honoring version retires this wrapper — attribute and all — and a
      // second POST could fail alone, leaving the outcome and the resolution
      // disagreeing with no repair path.
      const comment = this.getAttribute("resolves");
      const detail = outcome === "accept" && comment ? { resolves: comment } : {};
      this.#failed = null;
      // Keep the replacement Undo in the pressed Button's seat while delivery is open.
      // It is present for focus continuity but unavailable until the log gives the
      // gesture the durable id Undo must name.
      this.#staging = true;
      this.#settle(outcome);
      const sent = sendAction(this, outcome, detail, { optimistic: true }).then(
        (accepted) => {
          this.#deciding = null;
          this.removeAttribute("aria-busy");
          if (!accepted) {
            // A definitive refusal is a state the reader can act from. Keep it at the
            // target as Failed, Retry, Cancel; there is no detail disclosure because the
            // transport returned no useful detail beyond the notice it already showed.
            this.#failed = { outcome, label };
            this.#renderControls(label);
            this.#margin?.update();
            return false;
          }
          // Usually the accepted state has already replayed this decision. Paint is
          // still owed if another part of that state failed to render, but not if the
          // same event list also carried a later undo: authored state then stands.
          if (actionStands(accepted)) {
            if (this.dataset.lfState === outcome) {
              this.#renderControls(label);
              this.#margin?.update();
            } else this.#settle(outcome);
          } else {
            this.#renderControls(label);
            this.#margin?.update();
          }
          announce(
            `${outcome === "accept" ? "Accepted" : "Rejected"} suggested change: ${label}`,
          );
          // TODO(2026-09-06): Decide whether accepted work with no active agent pickup
          // needs a distinct post-send presentation.
          return true;
        },
      );
      this.#inFlight(sent, label);
      this.#staging = false;
      return sent;
    }

    // The field refuses a second press while the first is unresolved. A pending result
    // that has not painted also marks the widget busy; an optimistic result instead puts
    // that state on its disabled Undo Button so the settled prose stays legible.
    #inFlight(decision, label = this.#label()) {
      this.#deciding = decision;
      // Optimistic content already says what the press did. Busy belongs to its disabled
      // Undo Button, not as a dimming veil over the settled prose.
      if (decision && !this.dataset.lfState) this.setAttribute("aria-busy", "true");
      else this.removeAttribute("aria-busy");
      this.#renderControls(label);
      this.#margin?.update();
    }

    #retryDecision() {
      const failed = this.#failed;
      if (!failed || this.#deciding) return;
      this.#failed = null;
      if (failed.undo) this.#undoOutcome();
      else this.#decide(failed.outcome);
    }

    #cancelFailedDecision() {
      if (!this.#failed || this.#deciding) return;
      this.#failed = null;
      this.#renderControls();
      this.#margin?.update();
      (this.dataset.lfState ? this.#undo : this.#accept).focus({ preventScroll: true });
    }

    async #undoOutcome() {
      const outcome = this.dataset.lfState;
      if (!outcome || this.#undoing) return;
      if (this.#staging || this.#deciding) {
        notice("Wait for the current change to finish before undoing");
        return;
      }
      const event = undoableAction(this, outcome);
      if (!event) {
        notice("This outcome is no longer available to undo");
        return;
      }
      this.#failed = null;
      this.#undoing = true;
      this.#renderControls();
      this.#margin?.update();
      try {
        if (!(await withdraw(event))) this.#failed = { undo: true };
      } finally {
        this.#undoing = false;
        if (this.isConnected) {
          this.#renderControls();
          this.#margin?.update();
        }
      }
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
      this.#failed = null;
      this.#deciding = null;
      this.removeAttribute("aria-busy");
      this.dataset.lfState = outcome;
      // The retired slot's marker is the layer's rendering of that state, and the
      // theme's one hide rule reads it. The accepted response replays through this
      // method on the gesture's own tab, so it hides the slot in the frame the
      // decision lands; the layer then writes the same mark unconditionally.
      renderRetired(this);
      if (this.#row) {
        // The only remaining circle is Undo, which still acts; the fold and surviving
        // content carry the outcome without leaving another status beside them.
        this.#renderControls(change);
      }
      this.#margin?.update();
      // The emphasis goes with the pending state: a decided suggestion is plain
      // prose. So does the word naming each slot, which is the same fact said to
      // whoever is listening.
      emphasized.delete(this);
      repaintEmphasis();
      this.#voice();
      fold?.();
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
    // is `movedWords`.
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
    // a row on the Asks tray, the label on a comment anchored here. The slots are the
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

    // Its words, for the same askers: the slots' text nodes run together away from the
    // strike and insert paint, and a thread on a rewrite was quoted as
    // "courtyardcovered terrace".
    lfSays() {
      return this.#subject();
    }

    renderState(state) {
      const outcome = state.settlement.value;
      if (outcome) return this.#settle(outcome);
      if (!this.hasAttribute("data-lf-state")) return;
      for (const slot of this.querySelectorAll(":scope > lf-old, :scope > lf-new"))
        for (const animation of slot.getAnimations()) animation.cancel();
      this.removeAttribute("data-lf-state");
      renderRetired(this);
      this.#failed = null;
      this.#deciding = null;
      this.removeAttribute("aria-busy");
      this.#renderControls();
      this.#voice();
      this.#emphasize();
      this.#margin?.update();
    }
  },
);
