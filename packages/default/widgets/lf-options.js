/* lf-options: an obligation the user answers. The theme draws both of its forms and
 * this module makes them answerable — without it the markup still reads as a decision,
 * and nothing here is load-bearing on the look.
 *
 * Which form a group takes is a fact about its options, decided in CSS and never here:
 * an option with a `label` argues its own case and is a card on a row of its own, and a
 * group whose options are bare labels is an obligation *about* the page, drawn as
 * compact rows. A card's `label` is its name and nothing draws it: the card shows the
 * title its author writes in it, as a group shows the heading written in it. Max chose
 * this over drawing the label as the card's title, since a name Leaf reads is data
 * apart from the title the page shows; it costs the name written twice, and On Me
 * shows a card's name alone, since no rule may pick a sentence out of the author's
 * markup.
 * The difference this module sees is only what a row adds — `for`, the id of the block
 * the row names, rendered as a reference the user can follow where the group's rows
 * name different blocks. Rows that all name one block draw none, since that block
 * usually stands just above the question and its name on every row repeats a place the
 * reader already has. It points and never speaks: the label stays written in the
 * markup, so the file's reading of the page holds every word the page shows.
 *
 * A group takes the user's pick, with no attribute to say so; only an exhibit shows
 * one that takes none (below). Rejected: an attribute that makes a group take picks
 * (`required` or `choose`), since nearly every group would carry it, and one written
 * without it draws cards nobody can press while `page check` passes. Every option
 * carries one injected mark that is both the keyboard path and the state — a toggle
 * reading "choose one" or "choose any" as the group takes one option or several. Once
 * picked, the same mark becomes a check while the option's cell takes a quiet tint.
 * Cards and rows mark a pick alike, tint plus check: the user chose this over a
 * "✓ selected" chip in a live titled card's corner, a word only cards wore, crowding
 * the author's own chips. The checkbox state carries the same fact for a user
 * listening. In an exhibit the mark renders as an image-like span, so authored state
 * keeps the check and an accessible name without pretending it can be pressed.
 *
 * The pick is a set, whatever the group allows. `multiple` lets it hold more than one
 * and clicking toggles each option in or out; without it a click makes that option the
 * only pick and clicking it again empties the set. One shape either way — the action
 * states the whole set, absolutely, so replaying this tab's own pick is a no-op and a
 * second tab converges rather than drifting. A click the whole option takes is one
 * nothing in the option wanted: a drag that ended here is that selection's, and a press
 * on the evidence an option argues from — a shot to flip, a disclosure to open, a link
 * to follow — belongs to what it landed on (`aimedAt`).
 *
 * The last cell of a page's group is the option the user writes. Submitting it
 * sends an `add` naming the new option and its words, then selects it through the same
 * `choose` action as every other pick. The option stands on the `add`'s own coordinate,
 * so a later pick leaves it in the group and only undoing the `add` takes it away. It is
 * not a thread: if the agent needs clarification after carrying the option into
 * the page, it can open a separate thread anchored to that option.
 *
 * The keyboard walk stops at options. This widget assigns 1–9 to authored options,
 * then its add field and Done; generated options receive the remaining numbers. Each
 * of them wears its digit in the group's one badge column, Done included: an obligation
 * whose last step showed no key could not be finished by a user reading the keys.
 * Removing or disabling a choice leaves the other bindings intact. Tab remains the
 * platform's path through every control and into that field. There it follows Leaf's
 * shared text-box contract: Shift+Enter writes a newline and Enter adds the option. A
 * generated option joins the walk on replay just like an authored one.
 *
 * In a thread the existing reply box already owns those words, so Enter from a mark
 * continues into that box. Every `multiple` group grows a Done press: each toggle
 * reaches the agent as it lands, so the press is the one statement that the set is
 * whole, posted as an `answer` action, and the group says its question is answered
 * while that answer stands (`static answered`). Answered is paint on the press, never a wider word. A
 * second press withdraws that answer through the widget's exact undo, reopening the
 * obligation; the set can still change after either press, and each toggle reaches the
 * agent.
 *
 * That paint goes on the press and nowhere else, which is a rule rather than a
 * preference. A module writes an attribute in the author's namespace only where the
 * registry declares it as a verb's record form — `selected` is one, so a version can
 * carry a pick and `page check` can hold the markup against the log's fold — and
 * the attributes the entry's schema names are the whole of what else may stand
 * there. Neither the answered paint nor the disclosure's state is such a record: the
 * `answer` verb declares no record form, so no version carries it, and which way this
 * tab left the disclosure is view state no version carries at all. Each is stated
 * once, on the control that carries it — Done's `aria-pressed`, the settled row's
 * `aria-expanded` — and the theme keys on those, as lf-tabs' strip does,
 * leaving the group's own attributes to the author. A copy on the group would also
 * mislead `shallowSigs`, which excludes exactly what no version can assert and so
 * reads any other attribute as state a version wrote.
 *
 * The keyboard path: every mark is a checkbox, so Tab reaches it and Space toggles. From a
 * mark, the runtime's row walk moves among the options: ↑/↓ clamp at the ends, and Home and
 * End land on them. This widget owns 1–9; the obligation view forwards those declarations across the
 * whole obligation. The column is held whether or not a key is in it, which is the theme's
 * half of this. The rows are
 * declared per mark, on the mark rather than on the group — the group holds the option's
 * own argument too, and a scope over the whole subtree would promise to work an option with
 * focus on a link inside one. An armed `g` sequence keeps its own digits without this module
 * asking: its scopes suspend every scope inside them.
 *
 * `settled` retires the decision once it has been made and acted on: the group collapses
 * to one line naming the chosen option, with every option — the chosen one included —
 * behind a disclosure. Nothing is deleted, so the ids, the anchors on them, and check's
 * id-survival rule are all untouched; what's reclaimed is the height. Open or closed is
 * view state for this user, remembered per browser tab in tabStore like a lf-tabs
 * tab: opening a settled group is reading, not editing, so it sends no action and no
 * version carries it. Collapsed options wear hidden="until-found", so find-in-page and
 * the runtime's reveal() (a click on a comment's quote) both open the group rather than
 * jumping to an option nobody can see, and while the version diff is on the row wears a
 * Δ count so a change can't hide behind the collapse. A settled group still takes a pick
 * once opened — settling is a sweep, not a lock, and the summary line follows whatever is
 * chosen, including back to a bare "Settled" when the user clears it.
 *
 * Inside an exhibit the group is quoted — exhibited, not offered: the mark is a span,
 * the click handler is never wired, there is no cell for an option of the user's own,
 * and an example decision can't be answered. `settled` still collapses there, because
 * quoting gates the action channel and not presentation.
 *
 * Authored children stay in place, as their author wrote them. An option the user
 * adds shows its words as inline Markdown (`OptionAddition`).
 *
 * Only this module records the pick. Another widget that shows it, as a board card
 * does, reads the group's `choice` output and asks for a pick with the invoker command
 * `--choose` (the registry's `choice` contract). Each option answers with its `value`,
 * or its id where it has none, as an `<option>` answers with its text. The group
 * records the asked pick under the words the sending button says, so Undo names the
 * gesture the user made, and refuses a value two options carry, since that would pick
 * one of them for the user. An exhibit takes no pick, so it refuses every request. */
import { OptionAddition } from "./lf-options-addition.js";
import { SettledOptions } from "./lf-options-settled.js";
import { nothing } from "/vendor/lit.js";
import {
  aimedAt,
  nameOf,
  elementById,
  threadInput,
  landInThread,
  placePreview,
  rowWalk,
  named,
  focusDestination,
  scrollIntoView,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { addressableWord } from "/runtime/lib/element-word.js";
import { markdownWords } from "/runtime/lib/markdown.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";

// What an option is called, in either form: a card's `label`, and a compact option's
// own words, which are all it has. `named` rather than `says`, because a picked option's
// mark is the page speaking and belongs to what the user can point at — not to the
// option's name, which is what every caller here wants. A settled title's answer to an
// option with neither is to say "Settled" rather than name an id nobody wrote.
/** @param {Element} option */
const label = (option) => option.getAttribute("label")?.trim() || named(option);

// The value an option answers with in the group's `choice`: its `value`, else its id.
/** @param {Element} option */
const optionValue = (option) => option.getAttribute("value") || option.id;

// The option the page advises is `recommended`, and the group says so wherever the
// option is answered away from its card.
/** @param {Element} option */
const recommended = (option) => option.hasAttribute("recommended");

// The offer, and how many of the group it takes. A group's prose stays deliberately silent,
// while the control states arity in the two registers it has: corner shape for the eye and
// this word in the aria-label below. The open word stays visually silent in every form. A
// user who hears "choose any" knows the next press adds where "choose one" would have
// replaced, and knows it while the obligation is still open rather than after answering it.
const OPEN = { one: "choose one", any: "choose any" };
const SELECTED = "selected";

/** @param {unknown} value @returns {readonly string[]} */
function choiceIds(value) {
  if (!Array.isArray(value))
    throw new Error("An option choice must contain option ids");
  /** @type {unknown[]} */
  const ids = value;
  if (!ids.every((id) => typeof id === "string"))
    throw new Error("An option choice must contain string ids");
  return ids;
}

/** @param {import("../../../browser/runtime/host/widget-controller.js").WidgetReading["state"] | null | undefined} state */
function additions(state) {
  const added = state?.add;
  if (!added) return [];
  if (!("units" in added)) throw new Error("Added options require their unit records");
  return Object.entries(added.units).map(([id, record]) => {
    const text = record.detail.text;
    if (typeof text !== "string")
      throw new Error("An added option must contain Markdown text");
    return { id, text };
  });
}

/** @param {import("../../../browser/runtime/host/widget-controller.js").WidgetReading["state"] | null | undefined} state */
function isAnswered(state) {
  const answer = state?.answer;
  return answer && "action" in answer ? Boolean(answer.action) : false;
}

const SECTION = "In the options";
const MARK_TAG = "lf-option-control";
const DONE_TAG = "lf-options-done";
// The group's render paints retained controls on the authored options. These generated
// hosts carry no authored content and need no reactive element lifecycle of their own.

customElements.define(
  "lf-options",
  class extends LeafElement {
    // What the obligation was answered with: the picked options' names, the group's own in its
    // order and then the user's in the order they added them. An option the user added
    // is named by the words its `add` carries, and an authored one by its markup. A
    // pick the group can't name gives no words, so the answer reads a bare Answered
    // rather than a wrong name: an option the user added to a group in a thread message
    // is known only to a drawing of that message, and the copy the message keeps while
    // none shows it has only the authored options.
    /** @param {unknown} value @param {Element} group */
    static answerWords(value, group) {
      const picked = new Set(choiceIds(value));
      const added = additions(group instanceof LeafElement ? group.state : null);
      const authored = [...group.querySelectorAll(":scope > lf-option")].filter(
        (option) =>
          picked.has(option.id) && !added.some((record) => record.id === option.id),
      );
      const named = added.filter(({ id }) => picked.has(id));
      if (authored.length + named.length < picked.size) return "";
      return (
        [
          ...authored.map((option) => label(option) || option.id),
          ...named.map(({ text }) => markdownWords(text)),
        ].join(", ") || "No options selected"
      );
    }

    // Whether the group's question is answered, which Leaf asks after each of its
    // gestures (`module-state.md`, "Declared widget state"): Done pressed where the
    // group takes several options, otherwise a pick the user made. Each reads only the
    // user's acts in force, never a selection only the markup holds, so a pick the
    // version writes in answers nothing, as the server reads it.
    /** @param {import("../../../browser/runtime/host/widget-controller.js").WidgetReading["state"]} state @param {Element} group */
    static answered(state, group) {
      if (group.hasAttribute("multiple")) return isAnswered(state);
      const choose = state.choose;
      return Boolean(
        choose && "action" in choose && choose.action && choiceIds(choose.value).length,
      );
    }

    // The `choice` output, said with `change` each time it moves.
    /** @type {{value: string, options: {value: string, label: string}[], disabled: boolean} | null} */
    choice = null;
    #choiceSaid = "null";

    /** @type {OptionAddition | undefined} */
    #additionOwner;
    #choosable = false;
    /** @type {Map<HTMLElement, HTMLElement>} */
    #controls = new Map();
    /** @type {Map<string, number>} */
    #contextNumbers = new Map();
    /** @type {{host: HTMLElement, control: HTMLButtonElement, bindingBadge: HTMLSpanElement} | null} */
    #done = null;
    /** @type {SettledOptions | null} */
    #settled = null;
    #keyed = false;

    get #addition() {
      return (this.#additionOwner ??= new OptionAddition(this, {
        // `closed` answers only from the listed options.
        offered:
          this.#choosable &&
          !closestAcross(this, ".lf-chrome") &&
          !this.hasAttribute("closed"),
        available: () => this.#available("choose"),
        commit: (added, choice, attempt) => {
          if (!this.#available("add") || !this.#available("choose")) return null;
          const add = this.#dispatch("add", added, attempt, `Added “${added.text}”`);
          if (!add) return null;
          const pick = this.#dispatch("choose", choice, null, `Chose “${added.text}”`);
          // A refused `add` answers the draft at once: its words go back to the box
          // while the pick behind it is still in the wire, and the door refuses that
          // pick too, since it names no option the group holds.
          return add.then((added) => (added && pick ? pick : added));
        },
      }));
    }

    // An exhibited group has no semantic identity: it renders the authored
    // alternatives, but owns no selection, so it has no reading. Only a live or
    // settled decision has one.
    setup() {
      this.#wire(this.matches("[data-lf-exhibit] *"));
    }

    connectedCallback() {
      super.connectedCallback();
      this.#addition.connect();
      if (this.#choosable && this.hasAttribute("multiple") && !this.#done)
        this.#doneRow();
      this.#settled?.connect();
      if (!this.#keyed && this.#choosable) {
        this.#keyed = true;
        this.#keys();
      }
    }

    /** @param {boolean} exhibited */
    #wire(exhibited) {
      // Quoted material is exhibited, not offered: a sample shows what a decision
      // looks like without taking one. Every other group takes the user's pick.
      this.#choosable = !exhibited;
      // Bindings name identities, not the current visible order. Reserve the authored
      // choices and auxiliary actions before user-added options arrive, and retain a
      // removed option's number so undo never changes another action's binding.
      if (this.#choosable) {
        for (const option of this.#options()) this.#contextKeys(`choose:${option.id}`);
        if (this.#addition.offered) this.#contextKeys("write");
        if (this.hasAttribute("multiple")) this.#contextKeys("done");
      }
      const named = new Set(
        [...this.#options()].map((option) => option.getAttribute("for")),
      );
      if (named.size > 1) for (const option of this.#options()) this.#reference(option);
      // An exhibit has nothing to press: the mark still reports the document's state,
      // as a span.
      for (const option of this.#options())
        if (this.#choosable || option.hasAttribute("selected"))
          this.#control(option, this.#choosable);
      void this.#addition;
      if (this.hasAttribute("settled")) {
        this.#settled = new SettledOptions(this, { label });
      }
      this.addEventListener("command", (event) => {
        const { command, source } = /** @type {CommandEvent} */ (event);
        if (command === "--choose" && !this.#choose(source)) event.preventDefault();
      });
      if (!this.#choosable) return;
      this.addEventListener("click", (e) => {
        // A click ending a drag-select belongs to the selection rather than the option.
        const target = e.target;
        if (!(target instanceof Element)) return;
        const option = target.closest("lf-option");
        if (!option || option.parentElement !== this) return;
        // A click something in the option has a use for is not a pick: the user was
        // working the case — flipping a shot, opening a disclosure, following a link —
        // rather than choosing between the options. `aimedAt` is the whole of that
        // question, and what it cannot answer is which of the controls in here this
        // module put there: the mark is the pick's own control, so a press on it is
        // aimed at this option after all. The digit takes no pointer, and the mark
        // stands under it on a card and reaches over it on a row (options.css), so a
        // press on the digit lands on the mark.
        const at = aimedAt(e, option);
        if (at !== option && !at?.matches(".lf-pick")) return;
        if (!this.#available("choose")) return;
        e.preventDefault();
        const was = this.#picked();
        // Toggling is one gesture both ways, so a user who picked by mistake needn't
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
        this.#dispatch("choose", this.#addition.detailFor(next), null, said);
      });
    }

    // Record the pick a `--choose` asks for: the one option whose value the sending
    // button's `value` names, or the empty pick for the empty string, named by the words
    // the button says. False where the group takes no such pick.
    /** @param {Element | null} source */
    #choose(source) {
      if (
        !(source instanceof HTMLButtonElement) ||
        !this.choice ||
        this.choice.disabled
      )
        return false;
      const next = new Set(
        [...this.#options()].filter((option) => optionValue(option) === source.value),
      );
      if (next.size !== (source.value ? 1 : 0)) return false;
      this.#addition.remember(next);
      const words = source.textContent?.trim() ?? "";
      return Boolean(
        this.#dispatch("choose", this.#addition.detailFor(next), null, words),
      );
    }

    /** @param {ReadonlySet<string>} picked */
    #holdChoice(picked) {
      const options = [...this.#options()];
      const [only, other] = new Set(
        options.filter((option) => picked.has(option.id)).map(optionValue),
      );
      const choice = {
        value: other === undefined ? (only ?? "") : "",
        options: options.map((option) => ({
          value: optionValue(option),
          label: label(option) || option.id,
        })),
        disabled: !this.#available("choose"),
      };
      const said = JSON.stringify(choice);
      if (said === this.#choiceSaid) return;
      this.#choiceSaid = said;
      this.choice = choice;
      this.dispatchEvent(new Event("change"));
    }

    /** @param {string} verb */
    #available(verb) {
      return Boolean(this.state?.[verb]?.available);
    }

    /** @param {string} verb @param {Record<string, unknown>} detail @param {string | null} [attempt] @param {string} [says] */
    #dispatch(verb, detail, attempt = null, says = "") {
      return this.record(verb, detail, { says, attempt });
    }

    /** @returns {NodeListOf<HTMLElement>} */
    #options() {
      return this.querySelectorAll(":scope > lf-option");
    }

    #picked() {
      const ids = new Set(
        choiceIds(this.state?.choose?.detail?.value ?? this.#authoredChoice().value),
      );
      return new Set([...this.#options()].filter((option) => ids.has(option.id)));
    }

    #marks() {
      if (!this.#choosable) return [];
      return [...this.#options()].flatMap((option) => {
        const mark = this.#controls.get(option);
        return mark?.isConnected ? [{ option, mark }] : [];
      });
    }

    // A page obligation owns the ordinary add form below its options. An obligation already
    // inside a thread has no second form; its surrounding thread owns the reply.
    #reply() {
      return this.#addition.input ? null : threadInput(this);
    }

    // The one statement a live channel can't derive: the set is whole. Done is a
    // reversible gesture; its pressed state is the answer action in force. It records
    // the user's answer, so it wears the commit face, which the user chose over the
    // quiet word face every other worded press wears. Its digit
    // is inside the button, as an option's is inside the option, so a press on it is a
    // press on Done; the seat is out of flow, so it moves neither label nor edges.
    #doneRow() {
      const host = offer(DONE_TAG, "lf-options-done");
      // Done fills its cell, a joined run of one press that takes the cell's corners
      // (controls.css, `data-lf-joined`), which options.css states for each form.
      host.dataset.lfJoined = "";
      const button = offerAction("commit", "lf-done", "Done");
      const bindingBadge = offer("span", "lf-key-badge");
      bindingBadge.setAttribute("aria-hidden", "true");
      button.append(bindingBadge);
      host.append(button);
      this.append(host);
      this.#done = { host, control: button, bindingBadge };
    }

    #doneAvailable() {
      const answer = this.state?.answer;
      return isAnswered(this.state)
        ? Boolean(answer && "undoable" in answer && answer.undoable)
        : this.#available("answer");
    }

    // The press paints its result before the log replies, and Done's face derives from
    // that result, so a second press does what the button then says.
    #answer() {
      if (!this.#doneAvailable()) return;
      if (isAnswered(this.state)) this.takeBack("answer");
      else this.#dispatch("answer", {}, null, "Marked answered");
      this.#syncDone();
    }

    #syncDone() {
      if (!this.#done) return;
      const answered = Boolean(isAnswered(this.state));
      keeps(
        this.#done.control,
        "aria-label",
        answered
          ? "Take back Done: reopen these options"
          : "Done: these picks are complete",
      );
      keeps(this.#done.control, "aria-pressed", String(answered));
    }

    #refreshAvailability() {
      const available = this.#available("choose");
      for (const { mark } of this.#marks()) {
        keeps(mark, "aria-disabled", !available);
        keeps(mark, "tabindex", available ? 0 : -1);
      }
      this.#addition.refresh();
      this.#syncDone();
    }

    // Numbers stay with identities until this widget instance leaves, including a
    // removed choice the user can restore with undo.
    /** @param {string} identity */
    #contextKeys(identity) {
      let number = this.#contextNumbers.get(identity);
      if (number === undefined) {
        number = this.#contextNumbers.size + 1;
        this.#contextNumbers.set(identity, number);
      }
      return number <= 9 ? [String(number)] : [];
    }

    // From a mark, arrows walk the options and Space toggles. The group owns stable
    // numbered commands; the obligation view forwards those same declarations.
    #keys() {
      const marks = this.#marks();
      /** @type {import("/runtime/dom/keyboard/bindings.js").Command[]} */
      const answerRows = [];
      for (const { option, mark } of marks) {
        // The widget declares the number and its local face; the shared keyboard
        // presenter paints whichever declared binding currently reaches this action.
        let bindingBadge = option.querySelector(":scope > .lf-key-badge");
        if (!bindingBadge) {
          bindingBadge = offer("span", "lf-key-badge");
          bindingBadge.setAttribute("aria-hidden", "true");
          option.prepend(bindingBadge);
        }
        answerRows.push({
          id: `option.choose-${option.id}`,
          contextKeys: this.#contextKeys(`choose:${option.id}`),
          control: mark,
          decision: true,
          bindingBadge,
          title: label(option) || option.id,
          recommended: recommended(option),
          when: () => this.#available("choose"),
          run: () => mark.click(),
        });

        // Declared on the mark rather than the group, because the group holds the
        // option's own argument too — a link, a say-box, a tabbed exhibit — and a scope
        // over the whole subtree would promise local mechanics from any of them.
        mark.lfCommands = {
          title: SECTION,
          rows: [
            {
              id: "option.reply",
              keys: ["Enter"],
              title: "reply",
              when: () => Boolean(this.#reply()),
              // The box hands the user back to the thread it belongs to, and to
              // this option where that thread is nowhere to stand — the route
              // `landInThread` records for exactly that case, and the one Escape
              // out of a text box reads.
              run: () => {
                const reply = this.#reply();
                if (reply)
                  landInThread(reply, { target: mark, line: "back to the options" });
              },
            },
            ...rowWalk({
              id: "option",
              noun: "Option",
              plural: "options",
              rows: () => this.#marks().map(({ mark }) => mark),
            }),
            {
              id: "option.toggle",
              keys: [" "],
              title: "toggle",
              run: () => mark.click(),
            },
            {
              id: "option.reach",
              keys: [],
              label: "⇥",
              title: "Reach an option's mark",
            },
          ],
        };
        mark.dispatchEvent(
          new CustomEvent("lf-commands", { bubbles: true, composed: true }),
        );
      }
      const input = this.#addition.input;
      if (input)
        answerRows.push({
          id: "option.write",
          contextKeys: this.#contextKeys("write"),
          control: input,
          decision: true,
          bindingBadge: this.#addition.bindingBadge,
          title: "Another option",
          when: () => this.#available("choose"),
          run: () => {
            focusDestination(input, "move");
            scrollIntoView(input, { block: "nearest" });
          },
        });
      const done = this.#done;
      if (done)
        answerRows.push({
          id: "option.done",
          contextKeys: this.#contextKeys("done"),
          control: done.control,
          decision: true,
          commits: true,
          bindingBadge: done.bindingBadge,
          title: "Done",
          description: () =>
            isAnswered(this.state)
              ? "Take back Done and keep choosing"
              : "Finish choosing options",
          when: () => this.#doneAvailable(),
          run: () => this.#answer(),
        });
      this.lfCommands = { title: SECTION, rows: answerRows };
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    // The block this option is about. A pointer, not a voice: it names the block by the
    // name the chrome gives it (`nameOf`), else by its word, and by the id only where no
    // block in the option's message or on the page answers to it. After § a kind word
    // such as "section" says nothing, so the name stands alone, and pointing at it
    // previews the block, as a link into the page does (`placePreview`). It is chrome
    // throughout — a thing to work and nothing else, so paper drops it.
    /** @param {Element} option */
    #reference(option) {
      const target = option.getAttribute("for");
      if (!target) return;
      const block = elementById(target, this);
      const label = `§ ${nameOf(block) || addressableWord(block) || target}`;
      const ref = offer("a", "lf-ref", label);
      ref.href = `#${target}`;
      ref.lfPreview = () => {
        const named = elementById(target, this);
        return named ? placePreview(named) : null;
      };
      option.append(ref);
    }

    // Generated controls are retained DOM. `render()` paints them synchronously
    // while authored options keep their identities, words, and nested evidence.
    /** @param {HTMLElement} option @param {boolean} pressable */
    #control(option, pressable) {
      let mark = this.#controls.get(option);
      if (mark) return mark;
      mark = offer(MARK_TAG, "lf-pick");
      mark.classList.toggle("lf-ui", pressable);
      keeps(mark, "role", pressable ? "checkbox" : "img");
      keeps(mark, "data-lf-offer", pressable ? "checkbox" : null);
      // Pointing at the mark reads nothing: its round or square corner says whether the
      // group takes one option or any, the option's words stand beside it, and the digit
      // drawn on its option while focus is in the group says its key. Its name stays a
      // listener's, rather than a preview of "choose one", the word its shape stands
      // for.
      mark.lfPreview = () => false;
      this.#controls.set(option, mark);
      // First, before the option's words. Both forms place the mark out of flow, a card
      // in its header and a row in its leading column, so one insertion serves both and
      // the theme states each form's placement.
      // The mark stands where the user starts reading the label, not at the line's
      // end, which in a full-width group is ~620px from the words it answers for.
      option.prepend(mark);
      return mark;
    }

    /** @param {{value: readonly string[]}} detail */
    #syncChoice(detail) {
      const options = [...this.#options()];
      const picked = new Set(detail.value);
      let controlsChanged = false;
      for (const [option] of this.#controls)
        if (option.parentElement !== this) {
          this.#controls.delete(option);
          controlsChanged = true;
        }
      for (const [index, option] of options.entries()) {
        const selected = picked.has(option.id);
        option.toggleAttribute("selected", selected);
        if (!this.#choosable && !this.#controls.has(option) && !selected) continue;
        if (!this.#controls.has(option)) controlsChanged = true;
        const mark = this.#control(option, this.#choosable);
        const word = selected
          ? SELECTED
          : OPEN[this.hasAttribute("multiple") ? "any" : "one"];
        const name = label(option) || option.id;
        keepsText(mark, word);
        keeps(
          mark,
          "aria-label",
          this.#choosable
            ? `${word}: ${name} — option ${index + 1} of ${options.length}`
            : `${SELECTED}: ${name}`,
        );
        if (this.#choosable) keeps(mark, "aria-checked", selected);
      }
      this.#settled?.sync();
      if (controlsChanged && this.#choosable) this.#keys();
    }

    #authoredChoice() {
      return {
        value: [...this.#options()]
          .filter((option) => option.hasAttribute("selected"))
          .map((option) => option.id),
      };
    }

    render() {
      const { state } = this;
      if (!state) {
        this.#syncChoice(this.#authoredChoice());
        return nothing;
      }
      // A settled group may have no choose projection, so its authored attributes
      // supply the selection. A live group's complete choice is authoritative,
      // including accepted replay.
      const detail = {
        value: choiceIds(state.choose?.detail?.value ?? this.#authoredChoice().value),
      };
      const added = Object.fromEntries(
        additions(state).map(({ id, text }) => [id, text]),
      );
      this.#addition.render(added, this.#done?.host ?? null);
      this.#syncChoice(detail);
      this.#refreshAvailability();
      this.#holdChoice(new Set(detail.value));
      return nothing;
    }
  },
);
