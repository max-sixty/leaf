/* The option the author did not list: its durable words, the complete choice bound
 * to that draft generation, and the generated option nodes replay reconstructs. */
import {
  loadDraft,
  offer,
  saveDraft,
  sendDraft,
  toast,
  watchDraft,
  wrote,
} from "/runtime/widget-api.js";

const ANOTHER = "Another option";

const optionLabel = (option) => wrote(option);

export class OptionAddition {
  #host;
  #offered;
  #commit;
  #shortcut;
  #context;
  #form = null;
  #input = null;
  #add = null;
  #adding = false;
  #stopDraftWatch = null;

  constructor(host, { offered, commit, shortcut }) {
    this.#host = host;
    this.#offered = offered;
    this.#commit = commit;
    this.#shortcut = shortcut;
    this.#context = `option:${host.id}`;
  }

  connect() {
    if (!this.#offered) return;
    if (!this.#form) this.#buildForm();
    if (!this.#stopDraftWatch) {
      this.#stopDraftWatch = watchDraft(this.#context, (value) => {
        if (!this.#form.isConnected) return this.disconnect();
        this.#input.value = value ?? "";
        this.#sync();
      });
    }
  }

  disconnect() {
    this.#stopDraftWatch?.();
    this.#stopDraftWatch = null;
  }

  get input() {
    return this.#input;
  }

  #buildForm() {
    this.#form = offer("form", "lf-another");
    this.#input = offer("input");
    this.#input.type = "text";
    this.#input.placeholder = ANOTHER;
    this.#input.setAttribute("aria-label", ANOTHER);
    this.#add = offer("button", "lf-btn", "Add");
    this.#add.type = "submit";
    this.#add.setAttribute("aria-label", "Add option");
    const shortcut = offer("span", "lf-address", this.#shortcut);
    shortcut.setAttribute("aria-hidden", "true");
    this.#input.value = loadDraft(this.#context) ?? "";
    this.#input.addEventListener("input", () => {
      this.remember(this.#picked());
      this.#sync();
    });
    this.#form.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.#submit();
    });
    this.#form.append(shortcut, this.#input, this.#add);
    this.#host.append(this.#form);
    this.#sync();
  }

  #sync() {
    const disabled = this.#adding || !this.#input.value.trim();
    this.#add.setAttribute("aria-disabled", String(disabled));
    if (this.#adding) this.#add.setAttribute("aria-busy", "true");
    else this.#add.removeAttribute("aria-busy");
  }

  #picked() {
    return new Set(this.#host.querySelectorAll(":scope > lf-option[chosen]"));
  }

  remember(picked) {
    if (!this.#input) return;
    if (!this.#input.value && loadDraft(this.#context) === null) return;
    saveDraft(this.#context, this.#input.value, this.detailFor(picked));
  }

  #draftChoice(payload) {
    if (
      !payload ||
      !Array.isArray(payload.options) ||
      !payload.options.every((id) => typeof id === "string") ||
      (payload.additions !== undefined &&
        (!payload.additions ||
          typeof payload.additions !== "object" ||
          Array.isArray(payload.additions) ||
          !Object.entries(payload.additions).every(
            ([id, text]) => typeof id === "string" && typeof text === "string",
          )))
    )
      return this.detailFor(this.#picked());
    return {
      options: payload.options,
      ...(Object.keys(payload.additions ?? {}).length
        ? { additions: payload.additions }
        : {}),
    };
  }

  async #submit() {
    if (this.#adding) return;
    const raw = this.#input.value;
    const text = raw.trim();
    if (!text) return toast("Nothing to add — the field is empty");
    this.#adding = true;
    this.#sync();
    try {
      const accepted = await sendDraft(
        this.#context,
        () => this.#input.value === raw,
        (attempt, payload) => {
          const id = `${this.#host.id}-option-${attempt}`;
          const standing = this.#draftChoice(payload);
          const additions = { ...(standing.additions ?? {}), [id]: text };
          const picked = new Set(
            this.#host.hasAttribute("multiple") ? standing.options : [],
          );
          picked.add(id);
          const detail = { options: [...picked], additions };
          return this.#commit(detail, attempt);
        },
      );
      if (accepted) toast(`Added “${text}” — recorded`);
    } finally {
      this.#adding = false;
      this.#sync();
    }
  }

  #additions() {
    return Object.fromEntries(
      [...this.#host.querySelectorAll(":scope > lf-option[data-lf-added]")].map(
        (option) => [option.id, optionLabel(option)],
      ),
    );
  }

  detailFor(picked) {
    const additions = this.#additions();
    return {
      options: [...picked].map((option) => option.id),
      ...(Object.keys(additions).length ? { additions } : {}),
    };
  }

  /* Keep surviving nodes: replay must not discard focus or selection. Return only
   * nodes the selection owner still needs to dress with a mark and key scope. */
  reconcile(additions = {}, fallbackBefore = null) {
    const wanted = new Map(Object.entries(additions));
    for (const option of this.#host.querySelectorAll(
      ":scope > lf-option[data-lf-added]",
    ))
      if (!wanted.has(option.id)) option.remove();

    const created = [];
    for (const [id, text] of wanted) {
      let option = document.getElementById(id);
      if (option && option.parentElement !== this.#host) continue;
      if (!option) {
        option = document.createElement("lf-option");
        option.id = id;
        option.dataset.lfAdded = "";
        option.append(document.createTextNode(text));
        this.#host.insertBefore(option, this.#form ?? fallbackBefore);
        created.push(option);
      } else if (option.hasAttribute("data-lf-added")) {
        const words = [...option.childNodes].find(
          (node) => node.nodeType === Node.TEXT_NODE,
        );
        if (words) words.data = text;
        else option.prepend(document.createTextNode(text));
      }
    }
    return created;
  }
}
