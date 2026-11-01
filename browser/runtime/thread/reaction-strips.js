import { isHTML } from "../shadow-tree.js";
/* Thread reaction projection and its synchronous Lit owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus.
   The strip below a reply's words holds its reactions; its trigger stands with the
   message's other controls at its head (messages.js), which draws `trigger`. */
import { html, ref, render, repeat } from "/runtime/framework.js";
import { HOLDS_WORD } from "../held-word.js";
import { offered, offeredAction } from "../widget-elements.js";

/** @typedef {{registerSurface: ReturnType<typeof import("../reactions.js").createReactionController>["registerReactSurface"],
 * actions: Pick<ReturnType<typeof import("./actions.js").createThreadActions>, "setReaction">,
 * pressed?: () => void}} ReactionCommands */
/** @typedef {NonNullable<ReturnType<typeof import("./messages.js").messageReading>["reactions"]>} ReactionReading */
let ordinal = 0;
export class ReactionStripView {
  #commands;
  /** @type {ReturnType<ReactionCommands["registerSurface"]> | null} */
  #registration = null;
  #palette;
  #paletteId = `lf-reactions-${++ordinal}`;

  /** @param {ReactionCommands} commands */
  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
    this.node.classList.add("lf-react-strip", "lf-react-surface");
    this.#palette = document.createElement("span");
    this.#palette.className = "lf-react-palette";
    this.#palette.id = this.#paletteId;
    this.#palette.popover = "auto";
    this.#palette.setAttribute("role", "group");
    this.#palette.setAttribute("aria-label", "Reactions for this reply");
    this.node.append(this.#palette);
  }

  /** @param {ReactionReading} model */
  present(model) {
    this.node.classList.toggle("lf-open", model.latest);
    render(
      html`
        ${repeat(
          model.choices,
          (choice) => choice.name,
          (choice) =>
            html` <button
              ${offered(`lf-react ${HOLDS_WORD}`)}
              data-token=${choice.name}
              title=${choice.label}
              aria-label=${choice.label}
              aria-pressed=${String(Boolean(choice.inForce))}
              @click=${() => this.#press(model, choice)}
            >
              <span class="lf-react-glyph">${choice.glyph}</span>
            </button>`,
        )}
      `,
      this.#palette,
    );
    return this.node;
  }

  // The list's trigger, which registers the strip with each button it draws: a reply
  // whose reactions go and come back draws a new one.
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
                node.matches(".lf-react[data-token]"),
            )
        )
          return;
        registration.close();
        this.#commands.pressed?.();
      };
    })}
  ></button>`;

  /** @param {ReactionReading} model @param {ReactionReading["choices"][number]} choice */
  #press(model, choice) {
    void this.#commands.actions.setReaction(
      model.thread,
      model.message,
      choice.name,
      !choice.inForce,
    );
  }

  retire() {
    this.#registration?.close();
  }
}
