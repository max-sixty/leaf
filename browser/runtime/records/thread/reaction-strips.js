// Compiled from reaction-strips.ts by build/typescript.mjs; edit that file.
import { isHTML } from "../../lib/shadow-tree.js";
/* Thread reaction projection and its synchronous Lit owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus.
   The strip below a reply's words holds its reactions, each a toggle whose emoji is its
   face and, read by its Unicode name, its accessible name; its trigger stands with the
   message's other controls at its head (messages.js), which draws `trigger`. */
import { html, ref, render, repeat } from "/vendor/lit.js";
import { offeredAction } from "../../lib/controls.js";

let ordinal = 0;
export class ReactionStripView {
  #commands;
  #registration = null;
  #palette;
  #paletteId = `lf-reactions-${++ordinal}`;

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
    this.node.classList.add("lf-react-strip", "lf-react-surface");
    this.#palette = document.createElement("span");
    this.#palette.className = "lf-react-palette lf-popover";
    this.#palette.id = this.#paletteId;
    this.#palette.popover = "auto";
    this.#palette.setAttribute("role", "group");
    this.#palette.setAttribute("aria-label", "Reactions for this reply");
    this.node.append(this.#palette);
  }

  present(model) {
    this.node.classList.toggle("lf-open", model.latest);
    render(
      html`
        ${repeat(
          model.choices,
          (choice) => choice.emoji,
          (choice) =>
            html` <button
              ${offeredAction("reaction", "lf-react")}
              data-lf-emoji=${choice.emoji}
              aria-pressed=${String(Boolean(choice.inForce))}
              @click=${() => this.#press(model, choice)}
            >
              <span class="lf-react-glyph">${choice.emoji}</span>
            </button>`,
        )}
      `,
      this.#palette,
    );
    return this.node;
  }

  // The list's trigger, which registers the strip with each button it draws: a reply
  // whose reactions go and come back draws a new one. Its `aria-expanded` is the layer
  // stack's to keep as the list opens and closes (dom/keyboard/layer-stack.js).
  trigger = html`<button
    ${offeredAction("symbol", "lf-msg-control lf-react-trigger", undefined, {
      action: "react",
    })}
    aria-expanded="false"
    aria-controls=${this.#paletteId}
    ${ref((trigger) => {
      if (!isHTML(trigger, "button")) return;
      const registration = this.#commands.registerSurface(this.node, {
        trigger,
        palette: this.#palette,
      });
      this.#registration = registration;
      trigger.addEventListener("click", () => registration.toggle());
      this.#palette.ontoggle = (event) => {
        if (event.newState === "closed") registration.close();
      };
      this.node.onclick = (event) => {
        if (
          !event
            .composedPath()
            .some(
              (node) =>
                node instanceof HTMLButtonElement &&
                node.matches(".lf-react[data-lf-emoji]"),
            )
        )
          return;
        registration.close();
        this.#commands.pressed?.();
      };
    })}
  ></button>`;

  #press(model, choice) {
    void this.#commands.actions.setReaction(
      model.thread,
      model.message,
      choice.emoji,
      !choice.inForce,
    );
  }

  retire() {
    this.#registration?.close();
  }
}
