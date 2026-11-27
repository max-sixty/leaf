/* Controls a module builds, marked so Leaf reads them as controls, and presses that
 * wear one of Leaf's control faces by their role (control-faces.js). DOM constructors
 * and Lit element directives write the same marks, so a template and retained DOM
 * build one control alike. Templates own content, attributes and handlers that these
 * writers do not name. They load in any document; a host without Leaf simply does not
 * interpret the marks.
 *
 * A press the user activates, such as a button, is built by its role (`offerAction`,
 * `offeredAction`, `selectableOffer` with a face), so it wears the face Leaf draws for
 * that kind of press. `offer` and `offered` mark a field, a box of controls, or a
 * press whose look the module draws itself.
 *
 * The marks are attributes and classes Leaf reads off the element. A module that marks
 * its own words writes the same attributes itself (module-plain-elements.md, "Words it
 * writes"):
 *
 * - `lf-ui`, Leaf's chrome, and `lf-ui-face` on a native element, the default Leaf
 *   typography and ink; a custom-element host keeps its component-owned face and state
 *   styling.
 * - `data-lf-gen`, words the page's authored source lacks: the `wrote` reading leaves
 *   them out, and they are a passage cell of their own (readings/passages.js).
 * - `data-lf-offer`, how the press is spelled: the tag or input type for a native
 *   press, the tag for a custom host that opts into its own press contract, the role
 *   for a selectable one, and the empty string for the rest of the chrome a module
 *   builds. The theme's one pressable rule reads its value, and printing drops every
 *   element that wears it, so structure that isn't injected UI is built without these
 *   writers. */
import { Directive, PartType, directive, nothing } from "/vendor/lit.js";
import { keeps } from "./keeps.js";
import { actionClass } from "./control-faces.js";
import { actionName, showAction } from "./icon-paths.js";
import "./role-button-press.js";

// Whether this document runs without Leaf's runtime, where a symbol's `title` is the only
// reading of its name a pointer gets: on Leaf the preview reads its accessible name on
// every route, and the browser shows a title's tooltip in place of it (annotations/preview.js), so a
// writer writes none there. The prepaint marks the root of a page the runtime upgrades
// (`data-lf-interactive`, prepaint.js), the mark a package's own stylesheet reads, and
// takes it off where the runtime can't start.
const titlesName = () => !document.documentElement.hasAttribute("data-lf-interactive");

// Native controls are the ordinary case. A widget gets their activation, disabled state,
// focus behavior, and platform accessibility contract without Leaf recreating any of it:
// ordinary buttons and links need no Leaf activation binding, nor does a
// `selectableOffer` with a button's role (role-button-press.js); one with another role
// registers its widget-specific keys. An input supplies its type here so the type and
// the pressability marker cannot disagree. Custom controls opt in (`pressable`) when
// their host exposes the complete activation method that the go-to sequence can call,
// `focus()` and `click()`.
/** @template {Element} T @param {T} node @param {string} [cls] @param {boolean} [pressable] @returns {T} */
const offerElement = (node, cls, pressable = false) => {
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
// A native control, or a box of controls, built and marked: `offer(tag, className,
// label, inputType, pressable)`, where `inputType` is an input's type and `label` its
// words.
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
// such as a template. A symbol or mark says it as the accessible name, which the preview
// shows with the keys that press it on Leaf (annotations/preview.js), and off Leaf as the `title`
// the browser's tooltip shows (`titlesName`).
/** @template {Element} T @param {T} node @param {LeafActionRole} role
 * @param {string} [cls] @param {string} [label] @param {boolean} [pressable] @returns {T} */
const roleElement = (node, role, cls, label, pressable = false) => {
  offerElement(node, actionClass(role, cls), pressable);
  if (label !== undefined && (role === "symbol" || role === "mark")) {
    keeps(node, "aria-label", label);
    keeps(node, "title", titlesName() ? label : null);
  }
  return node;
};
/** @param {LeafActionRole} role @param {string} [cls] @param {string} [label] */
const buildAction = (role, cls, label) => {
  const node = roleElement(document.createElement("button"), role, cls, label);
  if (label !== undefined && role !== "symbol" && role !== "mark")
    node.textContent = label;
  return node;
};
/** @param {Element} node @param {string} role @param {string} [cls] @param {LeafActionRole} [face] */
const selectableOfferElement = (node, role, cls, face) => {
  keeps(node, "role", role);
  keeps(
    node,
    "class",
    [face && actionClass(face), cls, "lf-ui lf-ui-face"].filter(Boolean).join(" "),
  );
  keeps(node, "data-lf-gen", "1");
  keeps(node, "data-lf-offer", role);
};

// Some page words also act as controls: a tab name, a chosen mark, or the title of a
// settled decision. Chromium and Firefox begin a selection inside a button styled
// `user-select: text`, but WebKit, so Safari and every iOS browser, begins none inside a
// form control whatever its style (notes/browser-support.md, "Selecting words inside a
// button in WebKit"), so those few controls deliberately remain spans, focusable, with
// the role: `selectableOffer(role, className, label, face)`, where `face` is the role whose
// face a press wears, named last as every press names it, as in
// `selectableOffer("button", className, label, "row")`. One with a button's role takes a
// button's Enter and Space from role-button-press.js, with Leaf or without, and any
// other role's widget, such as a tab's, supplies its own keys. Keeping this constructor
// separate makes selectable control text a visible design decision instead of the
// behavior of every injected control.
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
      /** @param {A} _args */
      render(..._args) {
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

// The template form of `offerElement`: `<div ${offered("lf-tools")}>`. It owns the
// element's class and generated-control markers; attributes, values and handlers
// remain ordinary Lit bindings. An input's `type` binding stands before it, so the
// marker reads the type the input has. Both forms use the same chrome anatomy.
export const offered = elementDirective("offered", offerElement);

// A press that wears one of Leaf's control faces is built by its role, never by naming
// the face's classes: `offerAction(role, className, label, {action})` and, in a
// template, `<button ${offeredAction(role, className, label, {action})}></button>`,
// where the template writes any role's words but a symbol's or a mark's.
// `control-faces.js` lists the roles; `className` places the control and never restyles
// its face. A symbol or mark names its `action` (icon-paths.js, `ACTIONS`), whose
// symbol it shows and whose name it says as its accessible name and preview unless
// `label` says more. Whether a page's own press is a word or a symbol stays its
// author's call, so a page's "Done" may stay a word.
/** @param {LeafActionRole} role @param {string | undefined} label @param {string | undefined} action */
function actionFace(role, label, action) {
  if (role !== "symbol" && role !== "mark") {
    if (action !== undefined)
      throw new TypeError(`A ${role} says its label and shows no action's symbol`);
    return { label, action: undefined };
  }
  if (action === undefined) throw new TypeError(`A ${role} names the action it shows`);
  // Asked first, so an unknown action throws before the control is touched.
  const name = actionName(action);
  return { label: label ?? name, action };
}
/** @param {Element} node @param {LeafActionRole} role @param {string} action */
const drawAction = (node, role, action) =>
  showAction(node, action, role === "mark" ? "lf-mark-icon" : "lf-action-icon");
/**
 * @param {LeafActionRole} role @param {string} [className] @param {string} [label]
 * @param {{action?: string}} [options]
 */
export function offerAction(role, className, label, { action } = {}) {
  const face = actionFace(role, label, action);
  const node = buildAction(role, className, face.label);
  if (face.action !== undefined) drawAction(node, role, face.action);
  return node;
}
// The same face, symbol and name written onto an element the caller made, a custom
// host among them, which opts into the press contract as `offer`'s does (`pressable`).
/**
 * @template {Element} T
 * @param {T} node @param {LeafActionRole} role @param {string} [className]
 * @param {string} [label] @param {{action?: string, pressable?: boolean}} [options]
 */
export function offerActionElement(
  node,
  role,
  className,
  label,
  { action, pressable } = {},
) {
  const face = actionFace(role, label, action);
  roleElement(node, role, className, face.label, pressable);
  if (face.action !== undefined) drawAction(node, role, face.action);
  return node;
}
export const offeredAction = elementDirective("offeredAction", offerActionElement);

// The selectable offer's template form, `<span ${selectableOffered(role, className)}>`;
// Lit owns its label and tab stop.
export const selectableOffered = elementDirective(
  "selectableOffered",
  selectableOfferElement,
);

// A role's symbol whose action follows its state, as Expand all turns to Collapse
// all, takes its new symbol and name from its action:
// `nameAction(button, action, {label, className})`. It shows `action`'s symbol and
// says the action's name as accessible name, and off Leaf as title (`titlesName`),
// unless `label` says more, as a symbol role does, so the name and the symbol can't
// drift apart.
/**
 * @param {Element} control @param {string} action
 * @param {{label?: string, className?: string}} [options]
 */
export function nameAction(control, action, { label, className } = {}) {
  const name = label ?? actionName(action);
  keeps(control, "aria-label", name);
  keeps(control, "title", titlesName() ? name : null);
  showAction(control, action, className);
}
