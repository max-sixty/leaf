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
 * carries one mark that is both the keyboard path and the state — a toggle reading
 * "choose one" or "choose any" as the group takes one option or several. Once picked,
 * the same mark becomes a check while the option's cell takes a quiet tint. Cards and
 * rows mark a pick alike, tint plus check: the user chose this over a "✓ selected" chip
 * in a live titled card's corner, a word only cards wore, crowding the author's own
 * chips. The checkbox state carries the same fact for a user listening. In an exhibit
 * the mark renders as an image, so authored state keeps the check and an accessible
 * name without pretending it can be pressed.
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
 * The last cell of a page's group is the option the user writes. Submitting it sends an
 * `add` naming the new option and its words, then selects it through the same `choose`
 * action as every other pick (`OptionAddition`, lf-options-addition.js). The option
 * stands on the `add`'s own coordinate, so a later pick leaves it in the group and only
 * undoing the `add` takes it away. It is not a thread: if the agent needs clarification
 * after carrying the option into the page, it can open a separate thread anchored to
 * that option.
 *
 * The keyboard walk stops at options. This widget assigns 1–9 to authored options,
 * then its add field and Done; generated options receive the remaining numbers. Each of
 * them wears its digit in the group's one badge column, Done included: an obligation
 * whose last step showed no key could not be finished by a user reading the keys.
 * Removing or disabling a choice leaves the other bindings intact. Tab remains the
 * platform's path through every control and into that field. There it follows Leaf's
 * shared text-box contract: Shift+Enter writes a newline and Enter adds the option. A
 * generated option joins the walk on replay just like an authored one.
 *
 * In a thread the existing reply box already owns those words, so Enter from a mark
 * continues into that box. Every `multiple` group grows a Done press: each toggle
 * reaches the agent as it lands, so the press is the one statement that the set is
 * whole, posted as an `answer` action naming the options it covers and the picks among
 * them, and the group says its question is answered while that answer stands on the set
 * the group shows (`static answered`). Answered is paint on the press, never a wider
 * word. A second press withdraws that answer through the widget's exact undo, reopening
 * the obligation. The set can still change after either press, and each toggle reaches
 * the agent. A set that changed after Done waits on Done again, since Done said the set
 * it was pressed on was whole and no other: an option a version added asks again with
 * the picks kept, a pick the user changed asks again with the new picks, and a version
 * that rewrites a picked option (`$restated`) takes back the pick, so the question asks
 * again with the picks before it. Only the user's press answers again: a version that
 * removes the one option Done didn't cover leaves the question asking until Done is
 * pressed, though the set Done covered stands again (`obligations.told_facts`). The
 * alternative, Done answering whatever set follows it, could not ask again about an
 * option a version added without taking back every pick (`$restated` on the group).
 *
 * That paint goes on the press and nowhere else, which is a rule rather than a
 * preference. A module writes an attribute in the author's namespace only where the
 * registry declares it as a verb's record form — `selected` is one, so a version can
 * carry a pick and `page check` can hold the markup against the log's fold — and the
 * attributes the entry's schema names are the whole of what else may stand there.
 * Neither the answered paint nor the disclosure's state is such a record: the `answer`
 * verb declares no record form, so no version carries it, and which way this tab left
 * the disclosure is view state no version carries at all. Each is stated once, on the
 * control that carries it — Done's `aria-pressed`, the settled row's `aria-expanded` —
 * and the theme keys on those, leaving the group's own attributes to the author. A
 * copy on the group would also mislead `shallowSigs`, which excludes exactly what no
 * version can assert and so reads any other attribute as state a version wrote.
 *
 * The keyboard path: every mark is a checkbox, so Tab reaches it and Space toggles.
 * From a mark, the runtime's row walk moves among the options: ↑/↓ clamp at the ends,
 * and Home and End land on them. This widget owns 1–9; the obligation view forwards
 * those declarations across the whole obligation. The column is held whether or not a
 * key is in it, which is the theme's half of this. The rows are declared per mark, on
 * the mark rather than on the group — the group holds the option's own argument too,
 * and a scope over the whole subtree would promise to work an option with focus on a
 * link inside one. An armed `g` sequence keeps its own digits without this module
 * asking: its scopes suspend every scope inside them.
 *
 * `settled` retires the decision once it has been made and acted on: the group
 * collapses to one line naming the chosen option, with every option — the chosen one
 * included — behind a disclosure. Nothing is deleted, so the ids, the anchors on them,
 * and check's id-survival rule are all untouched; what's reclaimed is the height. Open
 * or closed is view state for this user, remembered per browser tab (`KeepInTab`)
 * like a lf-tabs tab: opening a settled group is reading, not editing, so it sends no
 * action and no version carries it. Collapsed options wear hidden="until-found", so
 * find-in-page and the runtime's reveal() (a click on a comment's quote) both open the
 * group rather than jumping to an option nobody can see, and while the version diff is
 * on the row wears a Δ count so a change can't hide behind the collapse. A settled
 * group still takes a pick once opened — settling is a sweep, not a lock, and the
 * summary line follows whatever is chosen, including back to a bare "Settled" when the
 * user clears it.
 *
 * Inside an exhibit the group is quoted — exhibited, not offered: the mark is an image,
 * the click is never a pick, there is no cell for an option of the user's own, and an
 * example decision can't be answered. `settled` still collapses there, because quoting
 * gates the action channel and not presentation.
 *
 * Only this module records the pick. Another widget that shows it, as a board card
 * does, reads the group's `choice` output and asks for a pick with the invoker command
 * `--choose` (the registry's `choice` contract). Each option answers with its `value`,
 * or its id where it has none, as an `<option>` answers with its text. The group
 * records the asked pick under the words the sending button says, so Undo names the
 * gesture the user made, and refuses a value two options carry, since that would pick
 * one of them for the user. An exhibit takes no pick, so it refuses every request.
 *
 * How it is drawn: a decorating widget. This is the shape every widget that wraps
 * author-written children takes, lf-tabs' and lf-board's included.
 *
 * - The light DOM is the author's, and the page's record. The author's children stay
 *   where and as they were written; what the widget states there is only its record:
 *   `selected` on each picked option (the `choose` verb's record form), the option
 *   nodes each `add` in force creates (`creates`), and `hidden="until-found"` on what a
 *   closed disclosure hides.
 * - Leaf's controls are drawn by Effect UI in shadow roots (`shadow: true`), and author
 *   content shows through a `<slot>`. The group's root holds the settled row, the add
 *   field and Done. Each option is a small widget of its own, `lf-option`
 *   (lf-option.js), whose root holds its key badge, its mark and its § reference
 *   around the option's slot, since a mark stands inside its option's box. The
 *   registry declares both roots (`shadow`), so the page's readings search them.
 * - The theme restyles those controls through shadow parts: `mark`, `key` and `ref` on
 *   an option; `cell` on each of the group's own cells, with `settled`, `another` or
 *   `done` naming which. A document rule names the part after the host's own state
 *   (`lf-options[multiple] > lf-option::part(mark)`), and widget-shadow.css holds what
 *   one control's look takes from another inside a root (`:host(lf-option) …`), which a
 *   part can't say.
 * - The group's component holds what the user is doing (the disclosure), its `update`
 *   turns gestures into Leaf's services (`RecordAction`, `TakeBack`), and one Mount on
 *   its slot (`ShowChoice`) does what only a host's own code can: it writes the light
 *   DOM record above, gives each option its face (the `face` property, which the
 *   option's widget declares, as a host sets `state`), states the group's key
 *   scope and `choice` output on the host, and hears the host's events — a click on
 *   an option's own words, an invoker command, `beforematch` — as messages. The add
 *   field is an editor Leaf hosts, so a Mount of its own builds it
 *   (lf-options-addition.js). */
import {
  Command,
  Effect,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  aimedAt,
  comparisonChanges,
  elementById,
  focusDestination,
  named,
  nameOf,
  scrollIntoView,
  tabStore,
} from "/runtime/widget-api.js";
import { declare, defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { RecordAction, KeepInTab, TakeBack } from "/runtime/widget-services.js";
import { offerAttributes, pressAttributes } from "/runtime/lib/controls.js";
import { keeps } from "/runtime/lib/keeps.js";
import { addressableWord } from "/runtime/lib/element-word.js";
import { markdownWords } from "/runtime/lib/markdown.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";
import { AddField, addedOptions } from "./lf-options-addition.js";
import { KeyBadge, SECTION, badgeOf, fieldOf, markOf, optionsOf } from "./lf-option.js";
import { SettledRow, settledKey } from "./lf-options-settled.js";

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

/** @param {any} state @returns {{id: string, text: string}[]} */
function additions(state) {
  const added = state?.add;
  if (!added) return [];
  if (!("units" in added)) throw new Error("Added options require their unit records");
  return Object.entries(added.units).map(([id, record]) => {
    const text = /** @type {any} */ (record).detail.text;
    if (typeof text !== "string")
      throw new Error("An added option must contain Markdown text");
    return { id, text };
  });
}

// The set a press of Done answers, which the `answer` action records: the ids of the
// options the group shows (`shown`), its authored ones and the user's, and of those
// picked.
/** @param {any} state @param {readonly string[]} shown */
function doneSet(state, shown) {
  const options = new Set(shown);
  const choose = state?.choose;
  const picked = choose && "value" in choose ? choiceIds(choose.value) : [];
  return {
    options: [...options].sort(),
    picked: picked.filter((id) => options.has(id)).toSorted(),
  };
}

// Whether Done answers the set the group shows now: pressed on every option it shows,
// with the same of them picked. An option a version adds, a pick a version takes back,
// or a pick the user changes after Done leaves it waiting on Done again; an option a
// version removes changes nothing here.
/** @param {any} state @param {readonly string[]} shown */
function isAnswered(state, shown) {
  const answer = state?.answer;
  if (!answer || !("action" in answer) || !answer.action) return false;
  const now = doneSet(state, shown);
  const covered = new Set(choiceIds(answer.detail.options));
  const options = new Set(now.options);
  const then = choiceIds(answer.detail.picked).filter((id) => options.has(id));
  return (
    now.options.every((id) => covered.has(id)) &&
    JSON.stringify(then.toSorted()) === JSON.stringify(now.picked)
  );
}

// The options the author wrote. An option the user added is drawn as an `lf-option`
// too (`data-lf-added`), and stays drawn until the next redraw after its `add` is
// undone, so the user's options are read from the state alone (`additions`).
/** @param {Element} group */
const authoredOptions = (group) =>
  optionsOf(group).filter((option) => !option.hasAttribute("data-lf-added"));

// The ids of the options a group element shows, its authored ones and the user's, for
// the code that holds the element rather than the view's props, as `allOptions` reads
// them from `inputs`.
/** @param {Element} group @param {any} state @returns {string[]} */
const shownOptions = (group, state) => [
  ...new Set([
    ...authoredOptions(group).map((option) => option.id),
    ...additions(state).map(({ id }) => id),
  ]),
];

/** @param {any} state @param {string} verb */
const available = (state, verb) => Boolean(state?.[verb]?.available);

/** @param {any} state @param {readonly string[]} shown */
const doneAvailable = (state, shown) =>
  isAnswered(state, shown)
    ? Boolean(state.answer.undoable)
    : available(state, "answer");

/** The options the author wrote, as the group's `inputs` reads them. */
const Authored = Schema.Struct({
  id: Schema.String,
  label: Schema.String,
  value: Schema.String,
  recommended: Schema.Boolean,
  selected: Schema.Boolean,
  ref: Schema.NullOr(Schema.Struct({ target: Schema.String, text: Schema.String })),
});

const OptionsProps = Schema.Struct({
  ...widgetProps,
  id: Schema.String,
  multiple: Schema.Boolean,
  settled: Schema.Boolean,
  choosable: Schema.Boolean,
  offered: Schema.Boolean,
  card: Schema.Boolean,
  options: Schema.Array(Authored),
  remembered: Schema.Boolean,
  changes: Schema.Number,
});

const OptionsMessage = UiSchema.TaggedEnum({
  Picked: { id: Schema.String },
  Asked: { value: Schema.String, words: Schema.String },
  PressedDone: {},
  ToggledSettled: {},
  Revealed: {},
});

/** Every option the group holds, the author's in their order and then the user's in the
 *  order they added them, each with its name and the value it answers with.
 * @param {any} props */
const allOptions = (props) => [
  ...props.options.map((/** @type {any} */ option) => ({
    ...option,
    name: option.label || option.id,
  })),
  ...additions(props.state)
    .filter(({ id }) => !props.options.some((/** @type {any} */ o) => o.id === id))
    .map(({ id, text }) => ({
      id,
      label: markdownWords(text),
      name: markdownWords(text) || id,
      value: id,
      recommended: false,
      selected: false,
      ref: null,
    })),
];

/** The pick in force: the reading's whole choice where it has one, and the markup's
 *  `selected` where a settled group has no choose projection.
 * @param {any} props @returns {string[]} */
const pickedIds = (props) => [
  ...choiceIds(
    props.state?.choose?.detail?.value ??
      props.options
        .filter((/** @type {any} */ option) => option.selected)
        .map((/** @type {any} */ option) => option.id),
  ),
];

// The group's `choice` output: the one value its pick holds, or none where it holds
// none or several, and every option it can answer with.
/** @param {ReturnType<typeof allOptions>} options @param {Set<string>} picked
 *  @param {boolean} choosing */
const choiceOutput = (options, picked, choosing) => {
  const [only, other] = new Set(
    options.filter((option) => picked.has(option.id)).map((option) => option.value),
  );
  return {
    value: other === undefined ? (only ?? "") : "",
    options: options.map((option) => ({ value: option.value, label: option.name })),
    disabled: !choosing,
  };
};

/** @param {any} model @param {any} props */
const settledOpen = (model, props) => model.open ?? props.remembered;

/** @param {string[]} next @param {string} says */
const choose = (next, says) =>
  RecordAction.make({ verb: "choose", detail: { value: next }, says }).pipe(
    Command.asNoop,
  );

/** @param {any} $ @param {boolean} open */
const openSettled = ($, open) =>
  $.evolve({ open }).run(
    KeepInTab.make({ key: settledKey($.props.id), value: open ? "1" : "0" }).pipe(
      Command.asNoop,
    ),
  );

export const Options = Html.component({
  name: "Options",
  props: OptionsProps,
  // `chose` is the user's own last pick in this tab, which the add field's words
  // remember beside them.
  model: Schema.Struct({
    open: Schema.NullOr(Schema.Boolean),
    chose: Schema.NullOr(Schema.Array(Schema.String)),
  }),
  message: OptionsMessage,
}).make({
  init: () => ({ open: null, chose: null }),
  update: {
    // Toggling is one gesture both ways, so a user who picked by mistake needn't pick
    // something else to get out of it. Without `multiple` the set the toggle starts
    // from is empty, which is what makes a pick replace rather than join.
    Picked: ($, { id }) => {
      const props = $.props;
      if (!props.choosable || !available(props.state, "choose")) return $.model;
      const option = allOptions(props).find((o) => o.id === id);
      if (!option) return $.model;
      const was = pickedIds(props);
      const next = props.multiple ? was.filter((picked) => picked !== id) : [];
      const dropped = was.includes(id);
      if (!dropped) next.push(id);
      const says = !next.length
        ? "Cleared selection"
        : dropped
          ? `Dropped “${option.name}”`
          : `Chose “${option.name}”`;
      return $.evolve({ chose: next }).run(choose(next, says));
    },
    // A `--choose` the group's mount has already matched to one option, or to none for
    // the empty value, recorded under the words the sending button says.
    Asked: ($, { value, words }) => {
      const props = $.props;
      if (!props.choosable || !available(props.state, "choose")) return $.model;
      const ids = allOptions(props)
        .filter((option) => option.value === value)
        .map((option) => option.id);
      return $.run(choose(ids, words));
    },
    // A Done that no longer stands on the set shown answers it again with a Done of its
    // own.
    PressedDone: ($) => {
      const state = $.props.state;
      const shown = allOptions($.props).map(({ id }) => id);
      if (!doneAvailable(state, shown)) return $.model;
      return isAnswered(state, shown)
        ? $.run(TakeBack.make({ verb: "answer" }).pipe(Command.asNoop))
        : $.run(
            RecordAction.make({
              verb: "answer",
              detail: doneSet(state, shown),
              says: "Marked answered",
            }).pipe(Command.asNoop),
          );
    },
    ToggledSettled: ($) => openSettled($, !settledOpen($.model, $.props)),
    Revealed: ($) => (settledOpen($.model, $.props) ? $.model : openSettled($, true)),
  },
  view: (h, model) => {
    const props = h.props;
    const { state, multiple, settled, choosable, offered, card } = props;
    const options = allOptions(props);
    const picked = new Set(pickedIds(props));
    const open = settledOpen(model, props);
    const collapsed = settled && !open;
    const answered = isAnswered(
      state,
      options.map(({ id }) => id),
    );
    const form = card ? "card" : "row";
    const faces = options.map((option, index) => {
      const checked = picked.has(option.id);
      const word = checked ? SELECTED : OPEN[multiple ? "any" : "one"];
      return {
        id: option.id,
        title: option.name,
        recommended: option.recommended,
        face: {
          mark: choosable ? "press" : checked ? "image" : "none",
          checked,
          word,
          name: choosable
            ? `${word}: ${option.name} — option ${index + 1} of ${options.length}`
            : `${SELECTED}: ${option.name}`,
          available: available(state, "choose"),
          ref: option.ref,
          form,
          settled,
        },
      };
    });
    // A view has one root, and this one takes no box, so the group's cells stand in
    // its grid as its light children do.
    return h.div
      .style({ display: "contents" })
      .attr("data-lf-form", form)
      .children(
        settled
          ? SettledRow(h, {
              open,
              names: options
                .filter((option) => picked.has(option.id))
                .map((option) => option.label)
                .filter(Boolean),
              changes: props.changes,
              toggled: OptionsMessage.ToggledSettled(),
            })
          : null,
        h.slot.onMount(
          ShowChoice({
            show: {
              faces,
              authored: props.options.map((option) => option.id),
              added: additions(state),
              collapsed,
              multiple,
              offered,
              numbered: choosable,
              choice: choiceOutput(options, picked, available(state, "choose")),
            },
          }),
        ),
        offered
          ? h.form
              .attrs(offerAttributes("form", "lf-another"))
              .attr("part", "cell another")
              .attr("data-lf-form", form)
              .attr("hidden", collapsed ? "" : undefined)
              .onMount(
                AddField({
                  picked: [...picked],
                  chose: model.chose,
                  added: additions(state).map(({ id }) => id),
                  multiple,
                }),
              )
          : null,
        // The one statement a live channel can't derive: the set is whole. Done is a
        // reversible gesture; its pressed state is the answer action in force. It
        // records the user's answer, so it wears the commit face, which the user chose
        // over the quiet word face every other worded press wears. Its digit is
        // inside the button, as an option's is inside the option, so a press on it is
        // a press on Done; the seat is out of flow, so it moves neither label nor
        // edges. The key scope's row runs it, as a press on the button does.
        choosable && multiple
          ? h
              .el("lf-options-done")
              .attrs(offerAttributes("lf-options-done", "lf-options-done"))
              .attr("part", "cell done")
              .attr("data-lf-form", form)
              .attr("data-lf-joined", "")
              .attr("hidden", collapsed ? "" : undefined)
              .children(
                h.button
                  .attrs(pressAttributes("commit", "lf-done"))
                  .attr(
                    "aria-label",
                    answered
                      ? "Take back Done: reopen these options"
                      : "Done: these picks are complete",
                  )
                  .attr("aria-pressed", String(answered))
                  .children("Done", KeyBadge(h)),
              )
          : null,
      );
  },
});

/** @type {WeakMap<HTMLElement, {added: Map<string, HTMLElement>, end: Comment}>} */
const drawnBy = new WeakMap();

/** What the group states outside its shadow root, kept by its slot's mount. */
class GroupLight {
  /** @type {any} */
  args = null;
  // Bindings name identities, not the current visible order. The authored choices and
  // auxiliary actions are numbered before user-added options arrive, and a removed
  // option keeps its number, so undo never changes another action's binding.
  /** @type {Map<string, number>} */
  #numbers = new Map();
  #scopeKey = "";
  #choiceSaid = "null";
  // The options this group's `add`s drew and the marker after them, kept by the host
  // across mounts, since they stand in its light tree after its root closes: a group
  // put back on the page takes up the nodes it drew rather than drawing them again.
  #drawn;
  /** The face each option was last given, as its words, so an option is told only a
   *  change. @type {WeakMap<Element, string>} */
  #faces = new WeakMap();

  /** @param {HTMLElement} host @param {(message: any) => void} send */
  constructor(host, send) {
    this.host = host;
    this.send = send;
    this.#drawn = drawnBy.get(host) ?? {
      added: new Map(),
      end: document.createComment("added options"),
    };
    drawnBy.set(host, this.#drawn);
    host.addEventListener("click", this.#click);
    host.addEventListener("command", this.#command);
    host.addEventListener("beforematch", this.#reveal, true);
  }

  close() {
    this.host.removeEventListener("click", this.#click);
    this.host.removeEventListener("command", this.#command);
    this.host.removeEventListener("beforematch", this.#reveal, true);
  }

  /** @param {any} args */
  show(args) {
    const first = !this.args;
    this.args = args;
    if (first && args.numbered) {
      for (const id of args.authored) this.#keys(`choose:${id}`);
      if (args.offered) this.#keys("write");
      if (args.multiple) this.#keys("done");
    }
    const drawn = this.#drawn;
    drawn.added = addedOptions(this.host, args.added, drawn.added, drawn.end, () =>
      this.show(this.args),
    );
    const faces = new Map(args.faces.map((/** @type {any} */ f) => [f.id, f.face]));
    for (const option of optionsOf(this.host)) {
      const face = faces.get(option.id);
      if (face) option.toggleAttribute("selected", face.checked);
      const said = JSON.stringify(face);
      if (this.#faces.get(option) !== said) {
        this.#faces.set(option, said);
        /** @type {any} */ (option).face = face;
      }
      if (args.collapsed) keeps(option, "hidden", "until-found");
      else if (option.getAttribute("hidden") === "until-found")
        option.removeAttribute("hidden");
    }
    this.#controls();
    this.#declare();
    this.#hold(args.choice);
  }

  // A settled row controls every option the group holds, the user's added ones too.
  // The options stand in the light tree, which an id the row names in its shadow root
  // can't reach, so the row names them as elements; the added ones are drawn here, so
  // the row is told here, once they stand.
  #controls() {
    const row = /** @type {HTMLElement | null | undefined} */ (
      this.host.shadowRoot?.querySelector(".lf-settled")
    );
    if (!row) return;
    const options = optionsOf(this.host);
    const was = row.ariaControlsElements ?? [];
    if (was.length !== options.length || was.some((el, i) => el !== options[i]))
      row.ariaControlsElements = options;
  }

  /** @param {string} identity */
  #keys(identity) {
    let number = this.#numbers.get(identity);
    if (number === undefined) {
      number = this.#numbers.size + 1;
      this.#numbers.set(identity, number);
    }
    return number <= 9 ? [String(number)] : [];
  }

  // The group owns stable numbered commands; the obligation view forwards those same
  // declarations. The widget declares the number and its local face; the shared
  // keyboard presenter paints whichever declared binding currently reaches the action.
  #declare() {
    const { host, args } = this;
    if (!args.numbered) return;
    const key = JSON.stringify([
      args.faces.map((/** @type {any} */ f) => f.id),
      args.offered,
      args.multiple,
    ]);
    if (key === this.#scopeKey) return;
    this.#scopeKey = key;
    const state = () => /** @type {any} */ (host).state;
    const shown = () => shownOptions(host, state());
    const titles = new Map(
      args.faces.map((/** @type {any} */ { id, title, recommended }) => [
        id,
        { title, recommended },
      ]),
    );
    /** @type {any[]} */
    const rows = optionsOf(host)
      .filter((option) => titles.has(option.id))
      .map((option) => ({
        id: `option.choose-${option.id}`,
        contextKeys: this.#keys(`choose:${option.id}`),
        control: () => markOf(option),
        decision: true,
        bindingBadge: () => badgeOf(option),
        title: titles.get(option.id)?.title,
        recommended: titles.get(option.id)?.recommended,
        when: () => available(state(), "choose"),
        run: () => this.send(OptionsMessage.Picked({ id: option.id })),
      }));
    if (args.offered)
      rows.push({
        id: "option.write",
        contextKeys: this.#keys("write"),
        control: () => fieldOf(host),
        decision: true,
        bindingBadge: () =>
          host.shadowRoot?.querySelector(".lf-another > .lf-key-badge"),
        title: "Another option",
        when: () => available(state(), "choose"),
        run: () => {
          const input = fieldOf(host);
          if (!input) return;
          focusDestination(input, "move");
          scrollIntoView(input, { block: "nearest" });
        },
      });
    const done = host.shadowRoot?.querySelector(".lf-done");
    if (done)
      rows.push({
        id: "option.done",
        contextKeys: this.#keys("done"),
        control: done,
        decision: true,
        commits: true,
        bindingBadge: done.querySelector(".lf-key-badge"),
        title: "Done",
        description: () =>
          isAnswered(state(), shown())
            ? "Take back Done and keep choosing"
            : "Finish choosing options",
        when: () => doneAvailable(state(), shown()),
        run: () => this.send(OptionsMessage.PressedDone()),
      });
    declare(host, { lfCommands: { title: SECTION, rows } });
  }

  // The `choice` output, said with `change` each time it moves.
  /** @param {any} choice */
  #hold(choice) {
    const said = JSON.stringify(choice);
    if (said === this.#choiceSaid) return;
    this.#choiceSaid = said;
    /** @type {any} */ (this.host).choice = choice;
    this.host.dispatchEvent(new Event("change"));
  }

  // A click ending a drag-select belongs to the selection rather than the option. A
  // click something in the option has a use for is not a pick: the user was working
  // the case — flipping a shot, opening a disclosure, following a link — rather than
  // choosing between the options. `aimedAt` is the whole of that question; a press on
  // the mark, which stands in the option's own root, reaches this listener as a press
  // on the option, so it is a pick. The digit takes no pointer, and the mark stands
  // under it on a card and reaches over it on a row (options.css), so a press on the
  // digit lands on the mark.
  #click = (/** @type {MouseEvent} */ event) => {
    const target = event.target;
    if (!this.args?.numbered || !(target instanceof Element)) return;
    const option = target.closest("lf-option");
    if (!option || option.parentElement !== this.host) return;
    if (aimedAt(event, option) !== option) return;
    if (!available(/** @type {any} */ (this.host).state, "choose")) return;
    event.preventDefault();
    this.send(OptionsMessage.Picked({ id: option.id }));
  };

  // Record the pick a `--choose` asks for: the one option whose value the sending
  // button's `value` names, or the empty pick for the empty string, named by the words
  // the button says. Refused where the group takes no such pick.
  #command = (/** @type {Event} */ event) => {
    const { command, source } = /** @type {CommandEvent} */ (event);
    if (command !== "--choose") return;
    const choice = this.args?.choice;
    const matches = (choice?.options ?? []).filter(
      (/** @type {{value: string}} */ option) =>
        source instanceof HTMLButtonElement && option.value === source.value,
    );
    if (
      !(source instanceof HTMLButtonElement) ||
      !choice ||
      choice.disabled ||
      matches.length !== (source.value ? 1 : 0)
    )
      return event.preventDefault();
    this.send(
      OptionsMessage.Asked({
        value: source.value,
        words: source.textContent?.trim() ?? "",
      }),
    );
  };

  #reveal = () => {
    if (this.args?.collapsed) this.send(OptionsMessage.Revealed());
  };
}

const ShowChoice = Mount.makeStream(
  "ShowChoice",
  { args: { show: Schema.Unknown } },
  (/** @type {HTMLSlotElement} */ slot, /** @type {any} */ { show }, changes) =>
    Stream.callback((queue) =>
      Effect.gen(function* () {
        const host = /** @type {HTMLElement} */ (
          /** @type {ShadowRoot} */ (slot.getRootNode()).host
        );
        const light = new GroupLight(host, (message) =>
          Queue.offerUnsafe(queue, message),
        );
        light.show(show);
        yield* Effect.addFinalizer(() => Effect.sync(() => light.close()));
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (/** @type {any} */ next) =>
            Effect.sync(() => light.show(next.show)),
          ),
        );
      }),
    ),
);

// The block an option names, in the words its reference says.
/** @param {Element} option @param {Element} host */
const reference = (option, host) => {
  const target = option.getAttribute("for");
  if (!target) return null;
  const block = elementById(target, host);
  return { target, text: `§ ${nameOf(block) || addressableWord(block) || target}` };
};

defineWidget("lf-options", Options, {
  shadow: true,
  statics: {
    lfPatch: "members",
    // What the obligation was answered with: the picked options' names, the group's own
    // in its order and then the user's in the order they added them. An option the user
    // added is named by the words its `add` carries, and an authored one by its markup.
    // A pick the group can't name gives no words, so the answer reads a bare Answered
    // rather than a wrong name: an option the user added to a group in a thread message
    // is known only to a drawing of that message, and the copy the message keeps while
    // none shows it has only the authored options.
    /** @param {unknown} value @param {Element} group */
    answerWords(value, group) {
      const picked = new Set(choiceIds(value));
      const added = additions(/** @type {any} */ (group).state);
      const authored = optionsOf(group).filter(
        (option) =>
          picked.has(option.id) && !added.some((record) => record.id === option.id),
      );
      const words = added.filter(({ id }) => picked.has(id));
      if (authored.length + words.length < picked.size) return "";
      return (
        [
          ...authored.map((option) => label(option) || option.id),
          ...words.map(({ text }) => markdownWords(text)),
        ].join(", ") || "No options selected"
      );
    },
    // Whether the group's question is answered, its `answered` fact, which Leaf asks
    // after each of its gestures and as a version or another tab's act moves it
    // (`module-state.md`, "Declared widget state"): Done standing on the set the group
    // shows where it takes several options (`isAnswered`), otherwise a pick the user
    // made. Each reads only the user's acts in force, never a selection only the markup
    // holds, so a pick the version writes in answers nothing, as the server reads it.
    /** @param {any} state @param {Element} group */
    answered(state, group) {
      if (group.hasAttribute("multiple"))
        return isAnswered(state, shownOptions(group, state));
      const choose = state.choose;
      return Boolean(
        choose && "action" in choose && choose.action && choiceIds(choose.value).length,
      );
    },
  },
  inputs: (host) => {
    // Quoted material is exhibited, not offered: a sample shows what a decision looks
    // like without taking one. Every other group takes the user's pick.
    const choosable = !host.matches("[data-lf-exhibit] *");
    const authored = authoredOptions(host);
    const named = new Set(authored.map((option) => option.getAttribute("for")));
    const settled = host.hasAttribute("settled");
    return {
      id: host.id,
      multiple: host.hasAttribute("multiple"),
      settled,
      choosable,
      // `closed` answers only from the listed options.
      offered:
        choosable && !closestAcross(host, ".lf-chrome") && !host.hasAttribute("closed"),
      card: authored.some((option) => option.hasAttribute("label")),
      options: authored.map((option) => ({
        id: option.id,
        label: label(option),
        value: optionValue(option),
        recommended: option.hasAttribute("recommended"),
        selected: option.hasAttribute("selected"),
        ref: named.size > 1 ? reference(option, host) : null,
      })),
      remembered: tabStore.get(settledKey(host.id)) === "1",
      changes: settled ? comparisonChanges(host).length : 0,
    };
  },
});
