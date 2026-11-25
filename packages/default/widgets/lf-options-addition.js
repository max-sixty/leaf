/* The option the author did not list: its draft, the `add` and `choose` bound to that
 * draft generation, and the option nodes each `add` in force puts in the group.
 *
 * The field is a text `<input>` of the widget's own, alone in its form, since an
 * option's words are one line: Return submits the form from every keyboard, a phone's
 * included, whose key says Send, and the browser drops a line break pasted into it, as
 * it does in any one-line field. Leaf keeps its words (`draft`), so they outlive a
 * reload, a revision and the tab, and a refused add gives them back.
 *
 * Rejected: a textarea, whose words wrap as the option's will, since a phone's Return
 * writes a line break there unless a press of Leaf's own adds the option. */
import { guard, html, render, repeat } from "/vendor/lit.js";
import { draft, pageLinks } from "/runtime/widget-api.js";
import { move } from "/runtime/lib/dom-move.js";
import { offer } from "/runtime/lib/controls.js";
import {
  inlineMarkdownFragment,
  loadMarkdown,
  markdownReady,
} from "/runtime/lib/markdown.js";

const ANOTHER = "Another option";

/** @typedef {{form: HTMLFormElement, input: HTMLInputElement, bindingBadge: HTMLSpanElement}} OptionEditor */

export class OptionAddition {
  #host;
  #offered;
  #commit;
  #draft;
  /** @type {OptionEditor | null} */
  #ui = null;
  /** @type {Set<string>} */
  #inForce = new Set();
  /** @type {Comment | null} */
  #end = null;
  /** @type {(() => void) | null} */
  #unwatch = null;

  /** @param {import("/runtime/lib/leaf-element.js").LeafElement} host
   * @param {{offered: boolean, available: () => boolean, commit: (added: {option: string, text: string}, choice: {value: string[]}, attempt: string) => unknown}} options */
  constructor(host, { offered, available, commit }) {
    this.#host = host;
    this.#offered = offered;
    this.available = available;
    this.#commit = commit;
    this.#draft = draft(`option:${host.id}`);
  }

  /** Whether the group takes an unlisted answer at all, so its group reserves the
   * field's binding only then. */
  get offered() {
    return this.#offered;
  }

  // The group's connection: the field follows its draft while the group stands.
  connect() {
    if (!this.#offered) return;
    const ui = (this.#ui ??= this.#buildForm());
    this.disconnect();
    this.#unwatch = this.#draft.watch(
      (value) => {
        // Writing the value a box already holds would move its caret to the end.
        if (ui.input.value !== (value ?? "")) ui.input.value = value ?? "";
      },
      {
        input: ui.input,
        box: () => ui.form,
        // Resume writing (`g i`) comes back to the field, which stands in the group.
        resume: () => ({ where: ui.input, input: () => ui.input }),
      },
    );
  }

  disconnect() {
    this.#unwatch?.();
    this.#unwatch = null;
  }

  get input() {
    return this.#ui?.input ?? null;
  }

  get bindingBadge() {
    return this.#ui?.bindingBadge ?? null;
  }

  /** @returns {OptionEditor} */
  #buildForm() {
    const form = offer("form", "lf-another");
    const input = offer("input");
    input.type = "text";
    input.name = "option";
    input.autocomplete = "off";
    input.placeholder = "Add another option…";
    input.enterKeyHint = "send";
    input.setAttribute("aria-label", ANOTHER);
    const bindingBadge = offer("span", "lf-key-badge");
    bindingBadge.setAttribute("aria-hidden", "true");
    input.value = this.#draft.read()?.text ?? "";
    form.append(bindingBadge, input);
    // Return adds the option in the keypress's own task, as Send does in Leaf's boxes;
    // a keyboard still composing a word leaves it to the form's own submission.
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.isComposing) return;
      event.preventDefault();
      form.requestSubmit();
    });
    input.addEventListener("input", () => this.remember(this.#picked()));
    // A press in the field's row beside its words, its digit's column included, is a
    // press on the field, as one on a label is.
    form.addEventListener("click", (event) => {
      if (event.target === form) input.focus();
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const raw = input.value;
      const text = raw.trim();
      if (text && this.available()) void this.#submit(text, () => input.value === raw);
    });
    this.#host.append(form);
    return { form, input, bindingBadge };
  }

  #picked() {
    return new Set(this.#host.querySelectorAll(":scope > lf-option[selected]"));
  }

  /** @param {Iterable<Element>} picked */
  remember(picked) {
    const input = this.input;
    if (!input) return;
    if (!input.value && this.#draft.read() === null) return;
    this.#draft.save(input.value, this.detailFor(picked));
  }

  /* The choice the generation recorded, less any option the group no longer holds:
   * an undo since then may have taken back an added option the draft still names, and
   * the door refuses a pick of an option the group lacks. Membership is the authored
   * options and the adds in force of the latest reading, not whatever this tab last
   * painted. */
  /** @param {unknown} payload */
  #draftChoice(payload) {
    if (
      !payload ||
      typeof payload !== "object" ||
      !("value" in payload) ||
      !Array.isArray(payload.value) ||
      !payload.value.every((id) => typeof id === "string")
    )
      return this.detailFor(this.#picked());
    return {
      value: payload.value.filter((id) => this.#inForce.has(id) || this.#authored(id)),
    };
  }

  /** @param {string} id */
  #authored(id) {
    const option = document.getElementById(id);
    return (
      option !== null &&
      option.parentElement === this.#host &&
      !option.hasAttribute("data-lf-added")
    );
  }

  /* The draft's attempt names the option, so a resend after reload names the same one
   * and the log answers it as the same `add`. The pick is absolute state and needs no
   * such identity. */
  /** @param {string} text @param {() => boolean} owns */
  async #submit(text, owns) {
    await this.#draft.send(owns, (attempt, payload) => {
      const id = `${this.#host.id}-option-${attempt}`;
      const choice = this.#draftChoice(payload);
      const picked = new Set(this.#host.hasAttribute("multiple") ? choice.value : []);
      picked.add(id);
      return this.#commit({ option: id, text }, { value: [...picked] }, attempt);
    });
  }

  /** @param {Iterable<Element>} picked */
  detailFor(picked) {
    return { value: [...picked].map((option) => option.id) };
  }

  /* Lit owns only the generated option range. Its keyed rows stay direct children
   * of the group, before the persistent draft editor; authored options and their
   * evidence are outside that range. Guarding Markdown keeps its text nodes and the
   * reader's selection when another option changes. An added option's words are the
   * user's inline Markdown: until the renderer loads they show as typed, and once it
   * has, the group draws again those whose Markdown changes them. */
  /** @param {Readonly<Record<string, string>>} [added] @param {Node | null} [fallbackBefore] */
  render(added = {}, fallbackBefore = null) {
    const options = Object.entries(added);
    if (options.length && !markdownReady())
      loadMarkdown().then((loaded) => loaded && this.#host.requestUpdate());
    this.#inForce = new Set(options.map(([id]) => id));
    if (!this.#end) {
      this.#end = document.createComment("added options");
      move(this.#host, this.#end, this.#ui?.form ?? fallbackBefore);
    }
    render(
      repeat(
        options,
        ([id]) => id,
        ([id, text]) => {
          const words = inlineMarkdownFragment(text, pageLinks);
          const typed = !words.firstElementChild && words.textContent === text;
          return html`<lf-option id=${id} data-lf-added>
            <span class="lf-option-words" data-lf-markdown-words
              >${guard([text, typed], () => words)}</span
            >
          </lf-option>`;
        },
      ),
      this.#host,
      { renderBefore: this.#end },
    );
  }
}
