/* Conversation reaction projection and its synchronous Lit owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus. */
import { html, render, repeat } from "../../vendor/browser-runtime.js";
import { registry } from "../registry.js";
import { iconTemplate } from "../icons.js";
import { isAddressable, isReaction } from "./model.js";

export function reactionReading(thread, message, complete) {
  if (
    !complete ||
    thread.resolved ||
    message.author !== "claude" ||
    !isAddressable(message)
  )
    return null;
  const latest = thread.msgs.findLast(
    (item) => item.author === "claude" && isAddressable(item),
  );
  const standing = thread.msgs.filter(
    (item) => isReaction(item) && item.author === "user" && item.parent === message.id,
  );
  if (!Object.keys(registry.$reactions?.tokens ?? {}).length) return null;
  return Object.freeze({
    latest: latest?.id === message.id,
    parent: message.id,
    agent: message.agent || "the agent",
    choices: Object.freeze(
      Object.entries(registry.$reactions?.tokens ?? {}).map(([name, entry]) =>
        Object.freeze({
          name,
          glyph: entry.glyph,
          label: entry.means ? `${name} — ${entry.means}` : name,
          standing: standing.find((item) => item.token === name) ?? null,
        }),
      ),
    ),
  });
}

let ordinal = 0;
export class ReactionStripView {
  #commands;
  #registration = null;
  #model = null;
  #paletteId = `lf-reactions-${++ordinal}`;

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  present(model) {
    this.#model = model;
    this.node.classList.add("lf-react-strip", "lf-react-surface");
    this.node.classList.toggle("lf-open", model.latest);
    this.node.setAttribute("role", "group");
    this.node.setAttribute("aria-label", "React to this reply");
    render(
      html` <button
          type="button"
          class="lf-react-trigger lf-ui"
          data-lf-gen="1"
          data-lf-offer="button"
          aria-expanded="false"
          aria-controls=${this.#paletteId}
          aria-label="Add reaction"
          title="Add reaction"
          @click=${() => this.#registration.toggle()}
        >
          ${iconTemplate("reaction", "lf-react-trigger-icon")}
        </button>
        <span
          class="lf-react-palette"
          id=${this.#paletteId}
          role="group"
          aria-label="Reactions for this reply"
        >
          ${repeat(
            model.choices,
            (choice) => choice.name,
            (choice) =>
              html` <button
                type="button"
                class="lf-chip lf-react lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                data-token=${choice.name}
                title=${choice.label}
                aria-label=${choice.label}
                aria-pressed=${String(Boolean(choice.standing))}
                aria-busy=${String(Boolean(choice.standing?.pending))}
                @click=${() => this.#press(choice.name)}
              >
                <span class="lf-react-glyph">${choice.glyph}</span>
              </button>`,
          )}
        </span>`,
      this.node,
    );
    this.#registration ??= this.#commands.registerSurface(this.node, {
      trigger: this.node.querySelector(".lf-react-trigger"),
      palette: this.node.querySelector(".lf-react-palette"),
      target: "the reply",
    });
    return this.node;
  }

  #press(name) {
    const model = this.#model;
    const choice = model.choices.find((item) => item.name === name);
    const sent = choice.standing
      ? this.#commands.withdraw(choice.standing)
      : this.#commands.sendReaction(
          {
            kind: "reply",
            parent: model.parent,
            revision: this.#commands.currentRevision(),
            token: name,
          },
          null,
          `${model.agent}'s reply`,
        );
    this.#registration.close();
    void sent;
  }

  retire() {
    this.#registration?.close();
  }
}
