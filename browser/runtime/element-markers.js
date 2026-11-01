/* The portable home for generated words and control markers. DOM constructors and
 * Lit element directives write the same roles, faces and passage semantics. They load
 * without Leaf's runtime; a host without Leaf simply does not interpret its markers.
 * Templates own content, attributes and handlers that these writers do not name. */
import { Directive, PartType, directive, nothing } from "/vendor/lit.js";
import { keeps } from "./keeps.js";
import { actionClass } from "./control-faces.js";
import { actionOffers } from "./icon-paths.js";
import "./role-button-press.js";

// Native controls are the ordinary case. A widget gets their activation, disabled state,
// focus behavior, and platform accessibility contract without Leaf recreating any of it:
// ordinary buttons and links need no Leaf activation binding, nor does a
// `selectableOffer` with a button's role (role-button-press.js); one with another role
// registers its widget-specific keys. An input supplies its type here so the type and
// the pressability marker cannot disagree. Custom controls opt in when their host exposes
// the complete activation method that the go-to sequence can call.
// Native elements also receive lf-ui-face, the default Leaf typography and ink.
// Custom-element hosts keep their component-owned face and state styling.
/** @template {Element} T @param {T} node @param {string} [cls] @param {boolean} [pressable] @returns {T} */
export const offerElement = (node, cls, pressable = false) => {
  if (node instanceof HTMLButtonElement && !node.hasAttribute("type"))
    keeps(node, "type", "button");
  const face = node.localName.includes("-") ? "" : " lf-ui-face";
  keeps(node, "class", `${cls ? `${cls} ` : ""}lf-ui${face}`);
  keeps(node, "data-lf-gen", "1");
  // Native summary is the browser's disclosure press, without a type property
  // or a specialized HTML element class. Its offer must name that same control.
  keeps(
    node,
    "data-lf-offer",
    pressable
      ? node.localName
      : node instanceof HTMLButtonElement ||
          node.localName === "summary" ||
          (node instanceof HTMLInputElement &&
            ["checkbox", "radio"].includes(node.type))
        ? node instanceof HTMLInputElement || node instanceof HTMLButtonElement
          ? node.type
          : node.localName
        : "",
  );
  return node;
};
// Words an upgrade wrote, which the page's authored source lacks: the `wrote` reading
// leaves them out, and they are a passage cell of their own. `says` is whether they
// are the page speaking (data-lf-said, quotable even inside chrome), a copy of words
// the page says elsewhere ("echo", data-lf-echo), or neither; widget-elements.js,
// over `relabel`, says why each answer matters and why none is assumed.
/**
 * @template {Element} T
 * @param {T} node
 * @param {{says?: boolean | "echo"}} [options]
 * @returns {T}
 */
export const generatedElement = (node, { says } = {}) => {
  if (typeof says !== "boolean" && says !== "echo")
    throw new TypeError(
      `Say whether these words are the page speaking: ` +
        `true, false, or "echo" for a copy of words it says elsewhere`,
    );
  keeps(node, "data-lf-gen", "1");
  // Toggling keeps an x-says span's attribute name (declared-words.js) where it stands.
  node.toggleAttribute("data-lf-said", says === true);
  node.toggleAttribute("data-lf-echo", says === "echo");
  return node;
};
/** @template {keyof HTMLElementTagNameMap} K
 * @overload @param {K} tag @param {string} [cls] @param {string | null} [label]
 * @param {string} [inputType] @param {boolean} [pressable] @returns {HTMLElementTagNameMap[K]} */
/** @overload @param {string} tag @param {string} [cls] @param {string | null} [label]
 * @param {string} [inputType] @param {boolean} [pressable] @returns {HTMLElement} */
/** @param {string} tag @param {string} [cls] @param {string | null} [label]
 * @param {string} [inputType] @param {boolean} [pressable] */
export function offer(tag, cls, label, inputType, pressable = false) {
  const node = document.createElement(tag);
  if (inputType !== undefined) {
    if (tag !== "input")
      throw new TypeError("only an input offer can declare an input type");
    node.setAttribute("type", inputType);
  }
  offerElement(node, cls, pressable);
  if (label !== undefined) node.textContent = label;
  return node;
}
// `label` names the press. A worded role shows it, and `offerAction` writes it as the
// words; the element writer leaves the words to whoever owns the element's content,
// such as a template. A symbol or mark says it as the accessible name and the
// tooltip, `title` where the tooltip says more, such as the key that does the same.
/** @template {Element} T @param {T} node @param {LeafActionRole} role
 * @param {string} [cls] @param {string} [label] @param {{title?: string}} [options] @returns {T} */
const roleElement = (node, role, cls, label, { title = label } = {}) => {
  offerElement(node, actionClass(role, cls));
  if (label !== undefined && (role === "symbol" || role === "mark")) {
    keeps(node, "aria-label", label);
    keeps(node, "title", title);
  }
  return node;
};
/** @param {LeafActionRole} role @param {string} [cls] @param {string} [label] @param {{title?: string}} [options] */
const buildAction = (role, cls, label, options) => {
  const node = roleElement(document.createElement("button"), role, cls, label, options);
  if (label !== undefined && role !== "symbol" && role !== "mark")
    node.textContent = label;
  return node;
};
/** @param {Element} node @param {string} role @param {string} [cls] @param {LeafActionRole} [face] */
export const selectableOfferElement = (node, role, cls, face) => {
  keeps(node, "role", role);
  keeps(
    node,
    "class",
    [face && actionClass(face), cls, "lf-ui lf-ui-face"].filter(Boolean).join(" "),
  );
  keeps(node, "data-lf-gen", "1");
  keeps(node, "data-lf-offer", role);
};

/** @param {string} role @param {string} [cls] @param {string} [label] @param {LeafActionRole} [face] */
export const selectableOffer = (role, cls, label, face) => {
  const node = document.createElement("span");
  selectableOfferElement(node, role, cls, face);
  node.tabIndex = 0;
  if (label !== undefined) node.textContent = label;
  return node;
};

// A template's element part handed to an imperative writer: `${name(...args)}` calls
// `write(element, ...args)` on every render, so a template and retained DOM share one
// writer for the attributes it owns while Lit keeps the element's content and bindings.
/** @template {unknown[]} A @param {string} name @param {(element: Element, ...args: A) => unknown} write */
export function elementDirective(name, write) {
  return directive(
    class extends Directive {
      /** @param {import("/vendor/lit.js").PartInfo} part */
      constructor(part) {
        super(part);
        if (part.type !== PartType.ELEMENT)
          throw new TypeError(`${name} belongs in a template's element part`);
      }
      // The values the template passes, which `update` writes.
      /** @param {A} args */
      render(...args) {
        return nothing;
      }
      /** @param {import("/vendor/lit.js").ElementPart} part @param {A} args */
      update(part, args) {
        write(part.element, ...args);
        return nothing;
      }
    },
  );
}

// The template form of `offer`: `<div ${offered("lf-tools")}>`. It owns the
// element's class and generated-control markers; attributes, values and handlers
// remain ordinary Lit bindings. Both forms use the same chrome anatomy.
export const offered = elementDirective("offered", offerElement);

// A press that wears one of Leaf's control faces is built by its role, never by naming
// the face's classes: `offerAction(role, className, label, {title, action})` and, in a
// template, `<button ${offeredAction(role, className, label, {action})}></button>`.
// `control-faces.js` lists the roles; `className`
// places the control and never restyles its face. A symbol or mark names its `action`
// (icon-paths.js, `ACTIONS`), whose symbol it shows and whose name it says as its
// tooltip and accessible name unless `label` says more.
const { offerAction, offerActionElement: offeredActionElement } = actionOffers({
  offerAction: buildAction,
  offerActionElement: roleElement,
});
export { offerAction, offeredActionElement as offerActionElement };
export const offeredAction = elementDirective("offeredAction", offeredActionElement);

// Some page words also act as controls: a tab name, a chosen mark, or the title of a
// settled decision. WebKit begins no text selection inside a form control, whatever its
// `user-select` (widget-elements.js), so those few controls deliberately remain spans:
// one with a button's role takes a button's keys from role-button-press.js, and any
// other role's widget supplies its own. Keeping this constructor separate makes
// selectable control text a visible design decision instead of the behavior of every
// injected control.
// The selectable offer's template form; Lit owns its label and tab stop.
export const selectableOffered = elementDirective(
  "selectableOffered",
  selectableOfferElement,
);

export const generated = elementDirective("generated", generatedElement);
