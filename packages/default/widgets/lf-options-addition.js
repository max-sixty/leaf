/* The option the author did not list: its draft, the `add` and `choose` bound to that
 * draft generation, and the option nodes each `add` in force puts in the group.
 *
 * The field is an editor Leaf hosts (`wireInput`, `draft`), which builds its own nodes
 * around the box, so a Mount builds it inside the cell the group's view draws
 * (`AddField`), and records the add and its pick through `RecordAction` itself: the
 * draft hears how the send went, and gives the words back to the box if the log
 * refuses it. The options an `add` creates are the group's record, so they stand in
 * the group's light DOM, after the author's (`addedOptions`). */
import { Component, Effect, Mount, Schema, Stream } from "/vendor/effect-ui.js";
import {
  draft,
  move,
  pageLinks,
  whileConnected,
  wireInput,
} from "/runtime/widget-api.js";
import { RecordAction } from "/runtime/widget-services.js";
import { offer } from "/runtime/lib/controls.js";
import {
  inlineMarkdownFragment,
  loadMarkdown,
  markdownReady,
} from "/runtime/lib/markdown.js";

const ANOTHER = "Another option";

/** @param {Element} host @param {string} verb */
const available = (host, verb) =>
  Boolean(/** @type {any} */ (host).state?.[verb]?.available);

class OptionAddition {
  /** @type {{picked: readonly string[], added: readonly string[], multiple: boolean}} */
  args;
  #stop;

  /** @param {HTMLElement} host @param {HTMLFormElement} form @param {any} args
   *  @param {(args: any) => Effect.Effect<string>} record */
  constructor(host, form, args, record) {
    this.host = host;
    this.args = args;
    this.record = record;
    this.draft = draft(`option:${host.id}`);
    const input = (this.input = offer("leaf-text"));
    input.name = "option";
    input.setAttribute("aria-label", ANOTHER);
    // Its hint is Leaf's words, as every empty box's is (base/voice.js).
    input.setAttribute("data-lf-voice", "leaf");
    // An option's title is one line, so Return adds it from a phone's keyboard too.
    input.toggleAttribute("one-line", true);
    const bindingBadge = offer("span", "lf-key-badge");
    bindingBadge.setAttribute("aria-hidden", "true");
    input.value = this.draft.read()?.text ?? "";
    form.append(bindingBadge, input);
    const sync = (this.sync = wireInput(input, {
      hint: "Add another option…",
      sendClass: "lf-option-add",
      sends: "add and select option",
      action: "add",
      allowsMedia: () => "Images can be added to comments, not options",
      busy: () => !available(host, "choose"),
      hasContent: (raw) => Boolean(raw.trim()),
      save: () => this.remember(),
      send: (text, _raw, owns) => this.#submit(text, owns),
    }));
    sync();
    this.#stop = whileConnected(host, () =>
      this.draft.watch((value) => sync.load(value ?? ""), {
        input,
        box: () => sync.composition().frame,
        // Resume writing (`g i`) comes back to the field, which stands in the group.
        resume: () => ({ where: input, input: () => input }),
      }),
    );
  }

  /** @param {any} args */
  show(args) {
    const picked = args.picked.join(" ") !== this.args.picked.join(" ");
    this.args = args;
    if (picked) this.remember();
    this.sync();
  }

  close() {
    this.#stop();
  }

  // The words being written keep the pick they were written beside, so a resend after
  // a reload picks what the user had picked.
  remember() {
    const { input } = this;
    if (!input.value && this.draft.read() === null) return;
    this.draft.save(input.value, { value: [...this.args.picked] });
  }

  /* The choice the generation recorded, less any option the group no longer holds:
   * an undo since then may have taken back an added option the draft still names, and
   * the door refuses a pick of an option the group lacks. Membership is the authored
   * options and the adds in force of the latest reading, not whatever this tab last
   * painted. */
  /** @param {unknown} payload @returns {string[]} */
  #draftChoice(payload) {
    if (
      !payload ||
      typeof payload !== "object" ||
      !("value" in payload) ||
      !Array.isArray(payload.value) ||
      !payload.value.every((id) => typeof id === "string")
    )
      return [...this.args.picked];
    return payload.value.filter(
      (id) => this.args.added.includes(id) || this.#authored(id),
    );
  }

  /** @param {string} id */
  #authored(id) {
    const option = document.getElementById(id);
    return (
      option !== null &&
      option.parentElement === this.host &&
      !option.hasAttribute("data-lf-added")
    );
  }

  /* The draft's attempt names the option, so a resend after reload names the same one
   * and the log answers it as the same `add`. The pick is absolute state and needs no
   * such identity. A refused `add` answers the draft at once: its words go back to the
   * box while the pick behind it is still in the wire, and the door refuses that pick
   * too, since it names no option the group holds. */
  /** @param {string} text @param {() => boolean} owns */
  async #submit(text, owns) {
    await this.draft.send(owns, (attempt, payload) => {
      const { host } = this;
      if (!available(host, "add") || !available(host, "choose")) return null;
      const option = `${host.id}-option-${attempt}`;
      const picked = new Set(this.args.multiple ? this.#draftChoice(payload) : []);
      picked.add(option);
      const add = Effect.runPromise(
        this.record({
          verb: "add",
          detail: { option, text },
          says: `Added “${text}”`,
          attempt,
        }),
      );
      const pick = Effect.runPromise(
        this.record({
          verb: "choose",
          detail: { value: [...picked] },
          says: `Chose “${text}”`,
        }),
      );
      return add.then(async (added) =>
        added === "admitted"
          ? (await pick) === "admitted"
          : added === "refused"
            ? false
            : null,
      );
    });
  }
}

export const AddField = Mount.make(
  "AddField",
  {
    args: {
      picked: Schema.Array(Schema.String),
      added: Schema.Array(Schema.String),
      multiple: Schema.Boolean,
    },
  },
  (/** @type {HTMLFormElement} */ form, args, changes) =>
    Effect.gen(function* () {
      const record = /** @type {any} */ (yield* RecordAction);
      const host = /** @type {HTMLElement} */ (
        /** @type {ShadowRoot} */ (form.getRootNode()).host
      );
      const addition = new OptionAddition(host, form, args, record);
      yield* Effect.addFinalizer(() => Effect.sync(() => addition.close()));
      yield* Stream.runForEach(changes, (next) =>
        Effect.sync(() => addition.show(next)),
      );
      return Component.noop;
    }),
);

/* The options each `add` in force creates, as the group's own children after the
 * author's, in the order they were added, keyed by id so an option stays the node it
 * was. An added option's words are the user's inline Markdown: until the renderer
 * loads they show as typed, and once it has, they are drawn again where its Markdown
 * changes them. Words drawn once stay as they are while their text does, so the
 * reader's selection in them survives another option changing. */
/** @param {HTMLElement} host @param {readonly {id: string, text: string}[]} added
 *  @param {Map<string, HTMLElement>} drawn @param {Comment} end @param {() => void} redraw
 *  @returns {Map<string, HTMLElement>} */
export function addedOptions(host, added, drawn, end, redraw) {
  if (added.length && !markdownReady())
    loadMarkdown().then((loaded) => loaded && redraw());
  if (end.parentNode !== host) move(host, end, null);
  /** @type {Map<string, HTMLElement>} */
  const next = new Map();
  for (const { id, text } of added) {
    let option = drawn.get(id);
    if (!option) {
      option = document.createElement("lf-option");
      option.id = id;
      option.setAttribute("data-lf-added", "");
    }
    const fragment = inlineMarkdownFragment(text, pageLinks);
    const typed = !fragment.firstElementChild && fragment.textContent === text;
    const key = `${typed}:${text}`;
    if (wordsDrawn.get(option) !== key) {
      wordsDrawn.set(option, key);
      const words = document.createElement("span");
      words.className = "lf-option-words";
      words.setAttribute("data-lf-markdown-words", "");
      words.append(fragment);
      option.replaceChildren(words);
    }
    next.set(id, option);
  }
  for (const [id, option] of drawn) if (!next.has(id)) option.remove();
  let before = /** @type {Node} */ (end);
  for (const option of [...next.values()].reverse()) {
    if (option.nextSibling !== before) move(host, option, before);
    before = option;
  }
  return next;
}

/** The words each added option was last drawn with. @type {WeakMap<Element, string>} */
const wordsDrawn = new WeakMap();
