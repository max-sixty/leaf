/* lf-option: one alternative of an `lf-options` group, and the controls Leaf draws
 * inside it. It is a decorating widget's member (lf-options.js, "How it is drawn"): the
 * option's own words are the author's and show through its root's `<slot>`, and its
 * root holds the key badge, the mark and the § reference around them, since a mark
 * stands inside its option's box. The group tells each option its face (the `face`
 * property) as a host sets `state`, and records every pick; an option draws what it is
 * told and keys its mark's walk, and records nothing itself.
 *
 * Its own tag and module, since the registry declares its root (`shadow`) as it does
 * the group's: the page's readings, such as Go-to's list of controls, search the roots
 * the registry declares. */
import { Component, Effect, Html, Mount, Schema } from "/vendor/effect-ui.js";
import {
  elementById,
  landInThread,
  placePreview,
  rowWalk,
  threadInput,
} from "/runtime/widget-api.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { offerAttributes } from "/runtime/lib/controls.js";

// The title of the keys a mark and its group answer.
export const SECTION = "In the options";

/** A key badge the keyboard presenter paints. @param {any} h */
export const KeyBadge = (h) =>
  h.span
    .attrs(offerAttributes("span", "lf-key-badge"))
    .attr("aria-hidden", "true")
    .attr("part", "key");

/** What an option shows of the group's state: its mark, as a press, an image of a
 *  pick, or nothing, with the mark's words, and its § reference. */
const Face = Schema.Struct({
  mark: Schema.Literals(["press", "image", "none"]),
  checked: Schema.Boolean,
  word: Schema.String,
  name: Schema.String,
  available: Schema.Boolean,
  ref: Schema.NullOr(Schema.Struct({ target: Schema.String, text: Schema.String })),
  form: Schema.Literals(["card", "row"]),
  settled: Schema.Boolean,
});

// The mark's own scope and a pick's, which read the group as it stands when asked.
/** @param {Element} option */
export const markOf = (option) =>
  /** @type {HTMLElement | null} */ (
    option.shadowRoot?.querySelector(".lf-pick[role=checkbox]") ?? null
  );
/** @param {Element} option */
export const badgeOf = (option) =>
  option.shadowRoot?.querySelector(".lf-key-badge") ?? null;
/** @param {Element} host */
export const optionsOf = (host) =>
  /** @type {HTMLElement[]} */ (
    [...host.children].filter((c) => c.localName === "lf-option")
  );
/** @param {Element} host */
export const fieldOf = (host) =>
  /** @type {HTMLElement | null} */ (
    host.shadowRoot?.querySelector(".lf-another leaf-text") ?? null
  );
// A page obligation owns the ordinary add form below its options. An obligation already
// inside a thread has no second form; its surrounding thread owns the reply.
/** @param {Element} host */
const replyOf = (host) => (fieldOf(host) ? null : threadInput(host));

// Pointing at the mark reads nothing: its round or square corner says whether the group
// takes one option or any, the option's words stand beside it, and the digit drawn on
// its option while focus is in the group says its key. Its name stays a listener's,
// rather than a preview of "choose one", the word its shape stands for.
const noPreview = () => false;

// From a mark, arrows walk the options and Space toggles. Declared on the mark rather
// than the group, because the group holds the option's own argument too — a link, a
// say-box, a tabbed exhibit — and a scope over the whole subtree would promise local
// mechanics from any of them.
const MarkKeys = Mount.make("MarkKeys", {}, (/** @type {HTMLElement} */ mark) =>
  Effect.sync(() => {
    const option = /** @type {ShadowRoot} */ (mark.getRootNode()).host;
    const host = /** @type {HTMLElement} */ (option.parentElement);
    /** @type {any} */ (mark).lfCommands = {
      title: SECTION,
      rows: [
        {
          id: "option.reply",
          keys: ["Enter"],
          title: "reply",
          when: () => Boolean(replyOf(host)),
          // The box hands the user back to the thread it belongs to, and to this option
          // where that thread is nowhere to stand — the route `landInThread` records
          // for exactly that case, and the one Escape out of a text box reads.
          run: () => {
            const reply = replyOf(host);
            if (reply)
              landInThread(reply, { target: mark, line: "back to the options" });
          },
        },
        ...rowWalk({
          id: "option",
          noun: "Option",
          plural: "options",
          rows: () => optionsOf(host).flatMap((o) => markOf(o) ?? []),
        }),
        { id: "option.toggle", keys: [" "], title: "toggle", run: () => mark.click() },
        { id: "option.reach", keys: [], label: "⇥", title: "Reach an option's mark" },
      ],
    };
    mark.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    // The group's scope names this mark as its option's control.
    host.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    return Component.noop;
  }),
);

const OptionFace = Html.component({
  name: "OptionFace",
  props: Schema.Struct({
    ...widgetProps,
    face: Schema.optional(Face),
    option: Schema.Unknown,
  }),
  model: Schema.Struct({}),
  message: Schema.Never,
}).make({
  init: () => ({}),
  update: {},
  view: (h) => {
    const { face } = h.props;
    const option = /** @type {Element} */ (h.props.option);
    const pressable = face?.mark === "press";
    const mark =
      face && face.mark !== "none"
        ? h.span
            .key("mark")
            .attr("class", pressable ? "lf-pick lf-ui" : "lf-pick")
            .attr("part", pressable ? "mark press" : "mark")
            .attr("data-lf-gen", "1")
            .attr("data-lf-offer", pressable ? "checkbox" : undefined)
            .attr("role", pressable ? "checkbox" : "img")
            .attr("aria-label", face.name)
            .attr("aria-checked", pressable ? String(face.checked) : undefined)
            .attr("aria-disabled", pressable ? String(!face.available) : undefined)
            .attr("tabindex", pressable ? (face.available ? "0" : "-1") : undefined)
            .prop("lfPreview", noPreview)
            .children(face.word)
        : null;
    // The mark stands where the user starts reading the label, not at the line's end,
    // which in a full-width group is ~620px from the words it answers for. Both forms
    // place it out of flow, a card in its header and a row in its leading column, so
    // the theme states each form's placement.
    return h.span
      .style({ display: "contents" })
      .attr("data-lf-form", face?.form)
      .attr("data-lf-settled", face?.settled ? "" : undefined)
      .children(
        pressable ? KeyBadge(h).key("key") : null,
        mark && pressable ? mark.onMount(MarkKeys({})) : mark,
        h.slot.key("slot"),
        face?.ref ? Reference(h, face.ref, option).key("ref") : null,
      );
  },
});

// The block this option is about. A pointer, not a voice: it names the block by the name
// the chrome gives it (`nameOf`), else by its word, and by the id only where no block in
// the option's message or on the page answers to it. After § a kind word such as
// "section" says nothing, so the name stands alone, and pointing at it previews the
// block, as a link into the page does (`placePreview`). It is chrome throughout — a
// thing to work and nothing else, so paper drops it.
/** @param {any} h @param {{target: string, text: string}} ref @param {Element} option */
const Reference = (h, { target, text }, option) =>
  h.a
    .attrs(offerAttributes("a", "lf-ref"))
    .attr("part", "ref")
    .attr("href", `#${target}`)
    .prop("lfPreview", () => {
      const block = elementById(target, option);
      return block ? placePreview(block) : null;
    })
    .children(text);

defineWidget("lf-option", OptionFace, {
  shadow: true,
  properties: ["face"],
  inputs: (option) => ({ option }),
});
