/* lf-options: a question the reader answers. The theme draws both of its forms and
 * this module makes them answerable — without it the markup still reads as a decision,
 * and nothing here is load-bearing on the look.
 *
 * Which form a group takes is a fact about its options, decided in CSS and never here:
 * an option leading with a <strong> title argues its own case and is a card on a row of
 * its own, and a group whose options are bare labels is a question *about* the page,
 * drawn as compact rows.
 * The difference this module sees is only what a row adds — `for`, the id of the block
 * the row names, rendered as a reference the reader can follow. It points and never
 * speaks: the label stays written in the markup, so the file's reading of the page
 * holds every word the page shows.
 *
 * `choose` takes the reader's pick. Every option carries one injected mark that is both
 * the keyboard path and the state — a toggle reading "choose one" or "choose any" as the
 * group takes one option or several. Once picked, the same mark becomes a check while
 * the option's cell takes a quiet tint. Presentation follows the form: a titled live card
 * exposes "selected" as compact header state, while a row keeps only its check. The
 * checkbox state carries the same fact for a reader listening. Outside a `choose` group
 * the mark renders as an image-like span, so authored state keeps the check and an
 * accessible name without pretending it can be pressed.
 *
 * The pick is a set, whatever the group allows. `multiple` lets it hold more than one
 * and clicking toggles each option in or out; without it a click makes that option the
 * only pick and clicking it again empties the set. One shape either way — the action
 * states the whole set, absolutely, so replaying this tab's own pick is a no-op and a
 * second tab converges rather than drifting. A click the whole option takes is one
 * nothing in the option wanted: a drag that ended here is that selection's, and a press
 * on the evidence an option argues from — a shot to flip, a disclosure to open, a link
 * to follow — belongs to what it landed on (`worksInside`).
 *
 * The last cell of a page choose group is the option the reader writes. Submitting it
 * appends a real option and selects it through the same `choose` action as every other
 * pick. The action carries the complete generated option set as well as the selection,
 * so replay, a later ordinary pick, and undo all reconstruct one absolute state. It is
 * not a conversation: if the agent needs clarification after carrying the option into
 * the page, it can open a separate thread anchored to that option.
 *
 * The keyboard walk stops at options. Ask digits choose each authored option, then enter
 * the add field when a digit remains among the Ask's nine contextual bindings. Tab remains the
 * platform's path through every control and into that field. There it follows Leaf's
 * shared text-box contract: Enter writes a newline and Mod+Enter adds the option. A
 * generated option joins the walk on replay just like an authored one.
 *
 * In a thread the existing reply box already owns those words, so Enter from a mark
 * continues into that box and a `multiple` group grows a Done press instead: every
 * toggle reaches the agent as it lands, so the press is the one statement that the set
 * is whole, posted as an `answer` action and held as the thread decision's closing
 * condition (x-awaits.until). Answered is paint on the press, never a wider word, and the
 * set can still change after — each later toggle still reaches the agent, who reads the log.
 *
 * That paint goes on the press and nowhere else, which is a rule rather than a
 * preference. A module writes an attribute in the author's namespace only where the
 * registry declares it as a verb's record form — `chosen` is one, so a version can
 * carry a pick and `version check` can hold the markup against the log's fold — and
 * the entry's `additionalProperties: false` is the whole of what else may stand
 * there. This module wrote two that nothing declared. `answered` recorded the
 * thread-only `answer` verb, and a thread's markup is frozen in the log, so no
 * version could ever have honored a record of it; `open` recorded which way this
 * tab last left the disclosure, which no version carries at all. Each was a second
 * copy of a fact the module already states on the control that carries it — the
 * mark's `aria-checked`, the row's `aria-expanded` — so the theme keys on those,
 * the way lf-tabs' strip already does, and the group's own attributes are the
 * author's again. What the copies cost was a reader that believed them:
 * `shallowSigs` excludes exactly what no version can assert, and read both of these
 * as state a version had written.
 *
 * The keyboard path: every mark is a checkbox, so Tab reaches it and Space toggles. From a
 * mark, ↑/↓ walk the options (a clamp at the ends, not a wrap). The Ask owns 1–9 across
 * the whole question and projects them onto the option cells. The column is held whether
 * or not a key is in it, which is the theme's half of this. The rows are
 * declared per mark, on the mark rather than on the group — the group holds the option's
 * own argument too, and a scope over the whole subtree would promise to work an option with
 * focus on a link inside one. An armed `g` sequence keeps its own digits without this module
 * asking: its scopes suspend every scope inside them, where each widget used to have to
 * remember the question.
 *
 * `settled` retires the decision once it has been made and acted on: the group collapses
 * to one line naming the chosen option, with every option — the chosen one included —
 * behind a disclosure. Nothing is deleted, so the ids, the anchors on them, and check's
 * id-survival rule are all untouched; what's reclaimed is the height. Open or closed is
 * view state for this reader, remembered per browser tab in tabStore like a lf-tabs
 * tab: opening a settled group is reading, not editing, so it sends no action and no
 * version carries it. Collapsed options wear hidden="until-found", so find-in-page and
 * the runtime's reveal() (a click on a comment's quote) both open the group rather than
 * jumping to an option nobody can see, and while the version diff is on the row wears a
 * Δ count so a change can't hide behind the collapse. A settled group still takes a pick
 * once opened — settling is a sweep, not a lock, and the summary line follows whatever is
 * chosen, including back to a bare "Settled" when the reader clears it.
 *
 * Inside an exhibit the group is quoted — exhibited, not offered — so it takes the
 * same path as a group that never declared `choose`: the mark is a span, the click
 * handler is never wired, there is no cell for an option of the reader's own, and an
 * example decision can't be answered. `settled` still collapses there, because quoting
 * gates the action channel and not presentation.
 *
 * Authored content is never replaced, so there is no failSoft. */
import { OptionAddition } from "./lf-options-addition.js";
import { SettledOptions } from "./lf-options-settled.js";
import {
  LitElement,
  beginWalk,
  conversationInput,
  focused,
  html,
  inChrome,
  commands,
  landInConversation,
  listWalkPosition,
  offer,
  quoted,
  reachedForWords,
  notice,
  walkRows,
  widgetController,
  worksInside,
  wrote,
} from "/runtime/widget-api.js";

// What an option is called, in either form: its title where it leads with one, and its
// own words where the label is all it has. `wrote` rather than `says`, because a picked
// option's mark is the page speaking and belongs to what the reader can point at — not
// to the option's name, which is what every caller here wants. A settled title's answer
// to an option with neither is to say "Settled" rather than name an id nobody wrote.
const label = (option) => wrote(option.querySelector(":scope > strong") ?? option);

// The offer, and how many of the group it takes. A group's prose stays deliberately silent,
// while the control states arity in the two registers it has: corner shape for the eye and
// this word in the aria-label below. The open word stays visually silent in every form. A
// reader who hears "choose any" knows the next press adds where "choose one" would have
// replaced, and knows it while the question is still open rather than after answering it.
const OPEN = { one: "choose one", any: "choose any" };
const SELECTED = "selected";

const SECTION = "In a question's options";
const MARK_TAG = "lf-option-control";
const DONE_TAG = "lf-options-done";

class OptionControl extends LitElement {
  static properties = {
    available: { attribute: false },
    label: { attribute: false },
    position: { attribute: false },
    pressable: { attribute: false },
    selected: { attribute: false },
    total: { attribute: false },
    word: { attribute: false },
  };

  constructor() {
    super();
    this.available = false;
    this.label = "";
    this.position = 0;
    this.pressable = false;
    this.selected = false;
    this.total = 0;
    this.word = "";
  }

  createRenderRoot() {
    return this;
  }

  willUpdate() {
    this.classList.toggle("lf-ui", this.pressable);
    this.dataset.lfGen = "1";
    this.toggleAttribute("data-lf-said", false);
    this.toggleAttribute("data-lf-echo", false);
    if (!this.pressable) {
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", `${SELECTED}: ${this.label}`);
      this.removeAttribute("aria-checked");
      this.removeAttribute("aria-disabled");
      this.removeAttribute("data-lf-offer");
      this.removeAttribute("data-lf-selectable-offer");
      this.removeAttribute("tabindex");
      return;
    }
    this.setAttribute("role", "checkbox");
    this.setAttribute(
      "aria-label",
      `${this.word}: ${this.label} — option ${this.position} of ${this.total}`,
    );
    this.setAttribute("aria-checked", String(this.selected));
    this.setAttribute("aria-disabled", String(!this.available));
    this.dataset.lfOffer = "checkbox";
    this.dataset.lfSelectableOffer = "";
    this.tabIndex = this.available ? 0 : -1;
  }

  render() {
    return html`${this.word}`;
  }
}

class DoneControl extends LitElement {
  static properties = {
    activate: { attribute: false },
    answered: { attribute: false },
    available: { attribute: false },
    busy: { attribute: false },
  };

  constructor() {
    super();
    this.activate = null;
    this.answered = false;
    this.available = false;
    this.busy = false;
  }

  createRenderRoot() {
    return this;
  }

  get control() {
    return this.querySelector(":scope > .lf-done");
  }

  get bindingBadge() {
    return this.control?.querySelector(":scope > .lf-key-badge") ?? null;
  }

  updated() {
    if (this.busy) this.control?.setAttribute("aria-busy", "true");
    else this.control?.removeAttribute("aria-busy");
  }

  render() {
    return html`<button
      type="button"
      class="lf-btn lf-done lf-ui"
      data-lf-gen="1"
      data-lf-offer="button"
      aria-label="Done: my picks here are complete"
      aria-pressed=${String(this.answered)}
      aria-disabled=${String(!this.available)}
      tabindex=${this.available ? 0 : -1}
      @click=${this.activate}
    >
      <span
        class="lf-key-badge lf-ui"
        data-lf-gen="1"
        data-lf-offer=""
        aria-hidden="true"
      ></span
      >Done
    </button>`;
  }
}

if (!customElements.get(MARK_TAG)) customElements.define(MARK_TAG, OptionControl);
if (!customElements.get(DONE_TAG)) customElements.define(DONE_TAG, DoneControl);

customElements.define(
  "lf-options",
  class extends LitElement {
    static properties = {
      reading: { attribute: false },
    };

    #addition = null;
    #answering = null;
    #choosable = false;
    #controller = null;
    #controls = new Map();
    #done = null;
    #keysDirty = false;
    #settled = null;
    #stateKey = null;
    #stop = null;
    #wired = false;

    constructor() {
      super();
      this.reading = null;
    }

    // This holder has no generated region of its own. A detached render root lets Lit
    // schedule its presentation lifecycle without inserting a false option-group cell;
    // each generated child control owns its own light-DOM template below.
    createRenderRoot() {
      return document.createDocumentFragment();
    }

    connectedCallback() {
      // An exhibited or purely structural group has no semantic identity: it renders
      // the authored alternatives, but owns no selection and therefore has no captured
      // widget descriptor. Only a live or settled decision enters the controller path.
      const exhibited = quoted(this);
      super.connectedCallback();
      if (!this.#wired) this.#wire(exhibited);
      this.#addition?.connect();
      this.#settled?.connect();
      if (!exhibited && (this.hasAttribute("choose") || this.hasAttribute("settled"))) {
        this.#controller ??= widgetController(this);
        this.#stop ??= this.#controller.subscribe(this.#present);
      } else {
        this.#presentAuthored();
      }
    }

    #wire(exhibited) {
      this.#wired = true;
      // Quoted material is exhibited, not offered, so a specimen renders exactly like a
      // group that was never choosable: it shows what a decision looks like without
      // taking one.
      this.#choosable = this.hasAttribute("choose") && !exhibited;
      for (const option of this.#options()) this.#reference(option);
      // Without `choose` there is nothing to press: the mark still reports the
      // document's state, as a span.
      for (const option of this.#options())
        if (this.#choosable || option.hasAttribute("chosen"))
          this.#control(option, this.#choosable);
      this.#addition = new OptionAddition(this, {
        offered: this.#choosable && !inChrome(this),
        available: () => this.#available("choose"),
        commit: (detail, attempt) => {
          if (!this.#available("choose")) return null;
          return this.#dispatch("choose", detail, attempt)?.delivery ?? null;
        },
      });
      if (this.#choosable) {
        if (this.hasAttribute("multiple") && inChrome(this)) this.#doneRow();
        this.#keysDirty = true;
      }
      if (this.hasAttribute("settled")) {
        this.#settled = new SettledOptions(this, { label });
      }
      if (!this.#choosable) return;
      this.addEventListener("click", (e) => {
        // A click ending a drag-select belongs to the selection rather than the option.
        const option = e.target.closest?.("lf-option");
        if (!option || option.parentElement !== this) return;
        if (e.detail !== 0 && reachedForWords(option)) return;
        // A click something in the option has a use for is not a pick: the reader was
        // working the case — flipping a shot, opening a disclosure, following a link —
        // rather than choosing between the options. `worksInside` is the whole of that
        // question, and what it cannot answer is which of the controls in here this
        // module put there: the mark is the pick's own control, and the digit stands in
        // the column beside it, so a press on either is aimed at this option after all.
        const inner = worksInside(e.target, option);
        if (inner && !inner.matches(".lf-pick, .lf-key-badge")) return;
        if (!this.#available("choose")) return;
        const was = this.#picked();
        // Toggling is one gesture both ways, so a reader who picked by mistake needn't
        // pick something else to get out of it. Without `multiple` the set the toggle
        // starts from is empty, which is what makes a pick replace rather than join.
        const next = new Set(this.hasAttribute("multiple") ? was : []);
        if (was.has(option)) next.delete(option);
        else next.add(option);
        this.#addition.remember(next);
        const name = label(option) || option.id;
        const said = !next.size
          ? "Cleared selection"
          : next.has(option)
            ? `Chose “${name}”`
            : `Dropped “${name}”`;
        this.#dispatch("choose", this.#addition.detailFor(next))?.delivery.then(
          (ok) => {
            if (ok) notice(`${said} — sent`);
          },
        );
      });
    }

    #available(verb) {
      return Boolean(this.reading?.actions[verb]?.available);
    }

    #dispatch(verb, detail, attempt) {
      const sent = this.#controller?.dispatch({
        kind: "action",
        verb,
        detail,
        ...(attempt && { attempt }),
      });
      if (sent) this.#present(sent.reading);
      return sent;
    }

    #options() {
      return this.querySelectorAll(":scope > lf-option");
    }

    #picked() {
      const ids = new Set(
        this.reading?.state.selection?.detail.options ?? this.#authoredChoice().options,
      );
      return new Set([...this.#options()].filter((option) => ids.has(option.id)));
    }

    #marks() {
      return [...this.#options()]
        .map((option) => this.#controls.get(option))
        .filter((view) => view?.pressable && view.isConnected);
    }

    // A page question owns the ordinary add form below its options. A question already
    // inside a conversation has no second form; its surrounding thread owns the reply.
    #reply() {
      return this.#addition.input ? null : conversationInput(this);
    }

    // The one statement a live channel can't derive: the set is whole. One press,
    // one `answer` action, and the decision this group stands as is discharged
    // (x-awaits.until). One-way — a later toggle still reaches the agent, so there
    // is nothing to take back — and the answer is paint rather than a fold, so
    // the pressed control's own line holds still.
    #doneRow() {
      this.#done = offer(DONE_TAG, "lf-options-done");
      this.#done.activate = () => void this.#answer();
      this.append(this.#done);
    }

    // The press paints the completed answer before the log replies. The outbox carries
    // that recordless facet beside recorded actions and refusal restores the prior state.
    // The promise still makes one press one action however many times the button is hit
    // while the first is in the wire.
    #answer() {
      if (this.#answering) return this.#answering;
      if (!this.#available("answer")) return Promise.resolve(false);
      const dispatched = this.#dispatch("answer", {});
      if (!dispatched) return Promise.resolve(false);
      const sent = dispatched.delivery.then((accepted) => {
        if (!accepted) return false; // reconciliation restored the prior state
        // Usually replay has painted the accepted answer already. Repeat the absolute
        // paint for a partial render, but never over a same-read undo of this action.
        this.#present(this.#controller.read());
        notice("Marked answered — sent");
        return true;
      });
      this.#answering = sent;
      this.#syncDone();
      this.requestUpdate();
      const clear = () => {
        if (this.#answering !== sent) return;
        this.#answering = null;
        this.#syncDone();
        this.requestUpdate();
      };
      sent.then(clear, clear);
      return sent;
    }

    #syncDone() {
      if (!this.#done) return;
      this.#done.available = this.#available("answer");
      this.#done.answered = this.reading?.state.completion?.value === "answer";
      this.#done.busy = Boolean(this.#answering);
    }

    #refreshAvailability() {
      const available = this.#available("choose");
      for (const mark of this.#marks()) mark.available = available;
      this.#addition?.refresh();
      this.#syncDone();
    }

    // From a mark, ↑/↓ walk the options and Space toggles. The mark's own scope
    // declares only those local mechanics (plus the thread's existing reply route).
    // The group contributes its ordered answer controls once, and core assigns their
    // contextual Ask bindings without the package maintaining a second digit map.
    #keys() {
      for (const bindingBadge of this.querySelectorAll(
        ":scope > lf-option > .lf-key-badge",
      ))
        bindingBadge.remove();
      const marks = this.#marks();
      const answerRows = [];
      for (const [index, mark] of marks.entries()) {
        const option = mark.parentElement;
        // The widget owns the card-local placement anchor; the Ask projection decides
        // whether this action receives one of its finite bindings and writes that binding
        // into the empty face. The package keeps no copy of core's capacity.
        const bindingBadge = offer("span", "lf-key-badge");
        bindingBadge.setAttribute("aria-hidden", "true");
        option.prepend(bindingBadge);
        answerRows.push({
          id: `option.choose-${index + 1}`,
          keys: [],
          control: mark,
          decision: label(option) || option.id,
          bindingBadge,
          does: `Toggle option ${index + 1}`,
          line: label(option) || option.id,
          run: () => mark.click(),
        });

        // Declared on the mark rather than the group, because the group holds the
        // option's own argument too — a link, a say-box, a tabbed exhibit — and a scope
        // over the whole subtree would promise local mechanics from any of them.
        commands(mark, SECTION, [
          {
            id: "option.reply",
            keys: ["Enter"],
            does: "Reply in this thread",
            line: "reply",
            when: () => Boolean(this.#reply()),
            returnFrame: () => {
              const box = this.#reply();
              const thread = box?.closest(
                ".lf-thread, .lf-conversation-thread, .lf-conversation",
              );
              return {
                active: () => Boolean(thread?.contains(focused())),
                close: () => box?.blur(),
                does: "Return to the option",
                line: "back to option",
              };
            },
            run: () =>
              landInConversation(this.#reply(), {
                target: mark,
                line: "back to question",
              }),
          },
          {
            id: "option.walk",
            keys: ["ArrowUp", "ArrowDown"],
            routes: [
              {
                id: "option.previous",
                binding: "ArrowUp",
                does: "Previous option",
              },
              { id: "option.next", binding: "ArrowDown", does: "Next option" },
            ],
            does: "Walk the options",
            line: "walk the options",
            lineWhen: false,
            repeat: true,
            run: (binding) => {
              walkRows(marks, binding === "ArrowDown" ? 1 : -1);
              const picked = [...this.#options()].map((option) =>
                option.hasAttribute("chosen"),
              );
              const answered = this.#done?.control?.getAttribute("aria-pressed");
              beginWalk("option", "Option", () => {
                const options = [...this.#options()];
                if (
                  options.length !== picked.length ||
                  options.some(
                    (option, index) => option.hasAttribute("chosen") !== picked[index],
                  ) ||
                  this.#done?.control?.getAttribute("aria-pressed") !== answered
                )
                  return null;
                return listWalkPosition(this.#marks(), focused());
              });
            },
          },
          {
            id: "option.toggle",
            keys: [" "],
            does: "Toggle the focused option",
            line: "toggle",
            lineWhen: false,
            run: () => mark.click(),
          },
          {
            id: "option.reach",
            keys: [],
            label: "⇥",
            does: "Reach an option's mark",
          },
        ]);
      }
      if (this.#addition.input)
        answerRows.push({
          id: "option.write",
          keys: [],
          control: this.#addition.input,
          decision: "Another option",
          bindingBadge: this.#addition.bindingBadge,
          does: "Write another option",
          line: "write another option",
          run: () => this.#addition.input.focus(),
        });
      if (this.#done)
        answerRows.push({
          id: "option.done",
          keys: [],
          control: this.#done.control,
          decision: "Done",
          bindingBadge: this.#done.bindingBadge,
          does: "Finish choosing options",
          line: "done",
          run: () => this.#done.control.click(),
        });
      commands(this, SECTION, answerRows, {
        answer: () =>
          [...this.#picked()].map((option) => label(option) || option.id).join(", ") ||
          "No options selected",
      });
    }

    // The block this option is about. A pointer, not a voice: its text is the id it
    // names, which is the same way the thread panel writes an element anchor, and
    // chrome throughout — a thing to work and nothing else, so paper drops it.
    #reference(option) {
      const target = option.getAttribute("for");
      if (!target) return;
      const ref = offer("a", "lf-ref", `§ ${target}`);
      ref.href = `#${target}`;
      option.append(ref);
    }

    // Each generated mark owns its Lit rendering while the authored option remains the
    // direct child whose identity, words, anchors, and nested evidence stay untouched.
    #control(option, pressable) {
      let mark = this.#controls.get(option);
      if (mark) return mark;
      mark = offer(MARK_TAG, "lf-pick");
      mark.pressable = pressable;
      this.#controls.set(option, mark);
      // First, so the row form's table puts it in the cell before the words. A card
      // places its mark out of flow in the header and cannot see this, so one insertion
      // serves both forms and the theme states each form's placement as it already did.
      // The mark ends every row at the column the label opens at, where the reader is
      // reading; it stood at the line's end, ~620px away from the words it answers for
      // in a full-width group, and a group that took several answers drew its boxes
      // there while a single-pick card drew none at all.
      option.prepend(mark);
      this.#keysDirty ||= pressable;
      return mark;
    }

    #syncChoice(detail) {
      const options = [...this.#options()];
      const picked = new Set(detail.options);
      for (const [option] of this.#controls)
        if (option.parentElement !== this) this.#controls.delete(option);
      for (const [index, option] of options.entries()) {
        const selected = picked.has(option.id);
        option.toggleAttribute("chosen", selected);
        if (!this.#choosable && !this.#controls.has(option) && !selected) continue;
        const mark = this.#control(option, this.#choosable);
        const word = selected
          ? SELECTED
          : OPEN[this.hasAttribute("multiple") ? "any" : "one"];
        mark.available = this.#choosable && this.#available("choose");
        mark.label = label(option) || option.id;
        mark.position = index + 1;
        mark.pressable = this.#choosable;
        mark.selected = selected;
        mark.total = options.length;
        mark.word = word;
      }
      this.#settled?.sync();
    }

    #presentAuthored() {
      this.#syncChoice(this.#authoredChoice());
      this.requestUpdate();
    }

    #authoredChoice() {
      return {
        options: [...this.#options()]
          .filter((option) => option.hasAttribute("chosen"))
          .map((option) => option.id),
      };
    }

    #present = (reading) => {
      this.reading = reading;
      this.#refreshAvailability();
      const state = reading.state;
      const stateKey = JSON.stringify([
        state.selection?.detail ?? null,
        state.completion?.value ?? null,
      ]);
      if ((state.selection || state.completion) && stateKey !== this.#stateKey) {
        this.#stateKey = stateKey;
        document.dispatchEvent(new CustomEvent("lf-answered"));
      }
    };

    renderState(state) {
      // Authored facets are captured after upgrade because widgets may arrange their
      // source nodes while connecting. Until that typed facet publishes, state has no
      // selection at all; preserve the authored initial condition. A reading that does
      // carry a selection is always authoritative, including accepted replay.
      const detail = state.selection?.detail ?? this.#authoredChoice();
      for (const option of this.#addition.reconcile(detail.additions ?? {}, this.#done))
        this.#control(option, this.#choosable);
      this.#syncChoice(detail);
    }

    async getUpdateComplete() {
      const complete = await super.getUpdateComplete();
      await Promise.all([
        ...[...this.#controls.values()].map((control) => control.updateComplete),
        ...(this.#done ? [this.#done.updateComplete] : []),
      ]);
      if (this.#keysDirty) {
        this.#keysDirty = false;
        this.#keys();
      }
      return complete;
    }

    disconnectedCallback() {
      this.#stop?.();
      this.#stop = null;
      this.#addition?.disconnect();
      this.#settled?.disconnect();
      super.disconnectedCallback();
    }

    render() {
      return html``;
    }

    lfWord() {
      return "options";
    }
  },
);
