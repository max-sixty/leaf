import { inChrome, matchesWhen, quoted, TEXT_BOX } from "/runtime/widget-api.js";
import {
  ADDRESSABLE,
  textNodesUnder,
  commandDeclarationsWithin,
  commandRoutes,
  pageDocument,
  upFrom,
  userScrollport,
  visualPartProblems,
} from "/runtime/check-api.js";
import { at as locate } from "./locate.js";
import { openRoots } from "./open-roots.js";

const PAINT_PROBE = "--_leaf-render-paint-value";
/** @param {HTMLElement | SVGElement} element @param {string} property @param {string} value */
const validPaint = (element, property, value) => {
  const hadStyle = element.hasAttribute("style");
  const prior = element.style.getPropertyValue(PAINT_PROBE);
  const priority = element.style.getPropertyPriority(PAINT_PROBE);
  try {
    element.style.setProperty(PAINT_PROBE, value);
    const resolved = getComputedStyle(element).getPropertyValue(PAINT_PROBE).trim();
    return resolved !== "" && CSS.supports(property, resolved);
  } finally {
    if (prior) element.style.setProperty(PAINT_PROBE, prior, priority);
    else element.style.removeProperty(PAINT_PROBE);
    if (!hadStyle && !element.getAttribute("style")) element.removeAttribute("style");
  }
};

/** @param {Element} element */
const renderedAt = (element) => {
  const ancestors = [];
  /** @type {Element | null} */
  let current = element;
  for (; current;) {
    ancestors.push(current);
    current = upFrom(current);
  }
  const owner =
    ancestors.find((el) => el.matches(ADDRESSABLE) && el.localName.includes("-")) ??
    ancestors.find((el) => el.matches(ADDRESSABLE)) ??
    element;
  return {
    at: locate(owner),
    part:
      ancestors.find((el) => el.hasAttribute("data-id"))?.getAttribute("data-id") ?? "",
  };
};

// A generated SVG crosses two boundaries before its paint reaches the user: a widget
// turns authored data into attributes, then the page's cascade resolves their custom
// properties. Resolve each value through a temporary custom property in the element's
// live cascade, then let the browser validate the resulting tokens for that property.
export function invalidPaints() {
  if (!pageDocument()) return [];
  const properties = [
    "color",
    "fill",
    "flood-color",
    "lighting-color",
    "stop-color",
    "stroke",
  ];
  const found = [];
  /** @param {Element} element @returns {element is SVGElement} */
  const svgElement = (element) => element.namespaceURI === "http://www.w3.org/2000/svg";
  for (const root of openRoots(document))
    for (const element of root.querySelectorAll(
      "[color], [fill], [flood-color], [lighting-color], [stop-color], [stroke], [style]",
    )) {
      if (!svgElement(element)) continue;
      for (const property of properties) {
        const value =
          element.style.getPropertyValue(property).trim() ||
          element.getAttribute(property)?.trim();
        if (!value || !/\bvar\(/i.test(value) || validPaint(element, property, value))
          continue;
        found.push({
          code: "invalid-paint",
          ...renderedAt(element),
          element: element.localName,
          property,
          value,
        });
      }
    }
  return found;
}

// A widget this page uses whose module never defined its element. The page's own
// occurrences are the population, because a page imports the modules its markup asks for
// and no others (widget-loader.js) — asked of the whole declared vocabulary this reports
// every tag the page simply does not contain. `document`, not `main`, so a widget frozen
// into an agent's reply answers here too. That a declared module exists at all is a layer
// fact and `package check` holds it; this is the page's half.
/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations */
export const missingUpgrades = (declarations) =>
  Object.entries(declarations)
    .filter(
      ([tag, entry]) =>
        entry["x-upgrade"] && document.querySelector(tag) && !customElements.get(tag),
    )
    .map(([tag]) => tag);
// visual-parts.js reads each declaration, so a part the gate accepts is one the page
// can anchor and travel to.
/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations */
export const invalidVisualProviders = (declarations) =>
  Object.entries(declarations)
    .filter(([, entry]) => entry["x-visual"])
    .flatMap(([tag, entry]) =>
      [...document.querySelectorAll(tag)].map((el) => ({
        code: "visual-parts",
        at: locate(el),
        problems: visualPartProblems(el, entry["x-visual"]),
      })),
    )
    .filter((instance) => instance.problems.length);
/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations */
export const missingThreads = (declarations) =>
  Object.entries(declarations)
    .flatMap(([tag, entry]) => {
      const seat = entry["x-thread-seat"];
      if (!seat) return [];
      return [...document.querySelectorAll(tag)]
        .filter((el) => !inChrome(el) && !quoted(el) && matchesWhen(el, seat.when))
        .map((el) => ({
          code: "missing-thread-seat",
          at: locate(el),
          hosts: [
            .../** @type {NodeListOf<HTMLElement>} */ (
              el.querySelectorAll(".lf-thread-seat")
            ),
          ].filter((host) => host.dataset.lfThreadSeat === el.id).length,
        }));
    })
    .filter((instance) => instance.hosts !== 1);

// Attributes on a widget that its entry never declared. The schema is the
// whole of the author's namespace — `additionalProperties: false` on every tag — and
// the static lint holds an authored document to it. What no source reading can see is the
// other writer: a module, which upgrades the element and may leave anything it likes on
// it. So a module writes in that namespace only where the registry declares the
// attribute as a verb's record form (`chosen`, `status`), which is what makes the write
// a statement the log's fold, the state gate and construction-linked inspection can all read.
// Everything else it needs to mark goes where the module's own words go — the chrome it
// built, in the platform's vocabulary (aria-*, role, hidden, tabindex) or under data-*,
// which is the layer's and a widget's alike.
//
// lf-options had two of the other kind, and both were quiet. `answered` recorded a verb
// only a thread can post, and a thread's markup is frozen in the log, so no version
// could ever have honored a record of it; `open` recorded which way this tab last left
// a disclosure, which no version carries at all. Neither reached a consumer, and the
// one reader that did see them read them wrong: shallowSigs excludes exactly the
// attributes no version can assert, and its exclusion list is the runtime's own paint —
// so a widget writing beside it is counted as state the author wrote, in the reading
// `page check --render` uses to decide whether a version overrules the user.
//
// Deduped and reported per tag and attribute, because one mistake is on every instance.
/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations */
export function undeclaredAttrs(declarations) {
  // What a module may write without declaring: the platform's own vocabulary for
  // what a control is and how it behaves, and the data-* namespace the runtime and
  // the widgets both paint in. `class` and `style` are the same kind of fact — a
  // look, not a state a version could carry — and `title`, `lang` and `dir`, which
  // the page may write on any element (`validation/instances.py`), describe one.
  const painted = /^(?:data-|aria-)/;
  const platform = new Set([
    "role",
    "class",
    "style",
    "title",
    "lang",
    "dir",
    "hidden",
    "tabindex",
  ]);
  const all = openRoots(document);
  const found = [];
  for (const [tag, entry] of Object.entries(declarations)) {
    if (!entry.properties) continue;
    for (const root of all)
      for (const el of root.querySelectorAll(tag))
        for (const a of el.attributes)
          if (
            !painted.test(a.name) &&
            !platform.has(a.name) &&
            !(a.name in entry.properties)
          )
            found.push({ code: "undeclared-attr", at: locate(el), tag, attr: a.name });
  }
  return found;
}

// The two sides of the settlement contract, compared on the rendered page. The mark —
// data-lf-state on a holder — is the layer's paint of a logged decision
// (`projection/presentation.js`, `paintSettlements`) for CSS to style; the anchor pass
// retires slots by the application's reading of the same decision, never by the mark.
// What can still go wrong is a family's, and both failures render perfectly: a module
// that writes the mark where the log decided nothing styles words as settled that the
// page still reads, and a settled slot can show its words anyway — a later layer's
// rule outranking the default hide, a module re-showing what it folded — leaving the
// user selecting words no comment can anchor to, with the refusal arriving later, at
// `leaf thread create`, nowhere near the mistake. So the expected outcome comes from the
// file's reading (`decisions`, folded over this version's log), never from the page,
// and the page answers only for what it shows.
//
// The words walk is textNodesUnder's `unsilenced` reading, on purpose: the anchor
// pass's `says` already skips a settled holder's slots, so asking it whether the
// retired words are gone would let the decision answer for the screen. What it keeps
// of that reading is the boundary — declared shadow roots, the same trees replay's
// elementById marks across, which is why the holders are found through OPEN_ROOTS
// too — and the chrome test: a declared label is the page's words, so a
// settled slot still showing one is still showing words. The visibility guards are
// COVERED_WORDS', for its reasons: [hidden] holds until-found content whose boxes
// report as last laid out, and visibility and opacity hide with layout intact. One
// scheme, since the palettes carry no geometry between them. Replay installs a fold's terminal DOM synchronously: the runtime's
// motion() refuses animation while it is projecting state or before presentation.
// The gate's global `pageSettled` fact separately holds independently authored motion
// before any reading starts. This reading stays synchronous: waiting on
// `Animation.finished` here would give page.evaluate a promise the driver cannot
// interrupt if the compositor stops.
/** @param {{id: string, outcome?: string | null, slots: string[]}[]} holders */
export function retiredSlots(holders) {
  const all = openRoots(document);
  const find = (/** @type {string} */ id) => {
    for (const r of all) {
      const el = r.getElementById(id);
      if (el) return el;
    }
    return null;
  };
  const found = [];
  const showing = (/** @type {Element} */ slot) => {
    for (const seg of textNodesUnder(slot, "unsilenced")) {
      const n = seg.node,
        el = n.parentElement;
      if (!n.data.trim() || !el) continue;
      if (el.closest(".lf-chrome, .lf-quiet, [hidden]")) continue;
      if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
        continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const box of range.getClientRects())
        if (box.width > 1 && box.height > 1) return n.data.trim().slice(0, 40);
    }
    return null;
  };
  for (const h of holders) {
    const el = find(h.id);
    if (!el || inChrome(el) || quoted(el)) continue;
    const mark = el.getAttribute("data-lf-state");
    const at = locate(el);
    if (mark !== (h.outcome ?? null)) {
      found.push({ code: "settlement-mark", at, mark, outcome: h.outcome });
      continue;
    }
    for (const tag of h.slots)
      for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
        for (const slot of root.querySelectorAll(`:scope > ${tag}`)) {
          const words = showing(slot);
          if (words === null) continue;
          found.push({
            code: "retired-slot",
            at,
            outcome: h.outcome,
            slot: tag,
            words,
          });
        }
  }
  return found;
}

// A box change smaller than this is layout rounding rather than a widget changing size.
const ROUNDING = 1;

// Whether the page shows an element: a node it hides once presented, as a tab strip
// hides its inactive panels, has no box of its own to keep.
/** @param {Element} element */
const shown = (element) =>
  element.isConnected && !element.closest("[hidden]") && element.checkVisibility();

/** @typedef {import("../../../browser/types/render-checks.js").FirstBox} FirstBox */
/** @typedef {Pick<DOMRectReadOnly, "width" | "height">} Box */
/** @typedef {{element: HTMLElement, first: FirstBox, now: Box}} SizeReading */
/** @param {SizeReading} holder @param {SizeReading[]} inside */
const withFirstSizes = (holder, inside) => {
  /** @type {[HTMLElement, string | null][]} */
  const kept = inside.map(({ element }) => [element, element.getAttribute("style")]);
  for (const { element, first } of inside) {
    /** @type {[string, string][]} */
    const writes = [
      // No padding or border, which would hold the box open past the size given.
      ["box-sizing", "border-box"],
      ["padding", "0"],
      ["border-width", "0"],
      ["width", `${first.width}px`],
      ["min-width", "0"],
      ["max-width", "none"],
      ["height", `${first.height}px`],
      ["min-height", "0"],
      ["max-height", "none"],
    ];
    for (const [property, value] of writes)
      element.style.setProperty(property, value, "important");
  }
  const { width, height } = holder.element.getBoundingClientRect();
  for (const [element, style] of kept)
    if (style === null) element.removeAttribute("style");
    else element.setAttribute("style", style);
  return { width, height };
};

// Each authored widget whose border box changed between the pre-upgrade box and
// its presented box (`firstBoxes` in driver.js). A holder is left out only where
// putting the changed widgets inside it back to their first sizes puts its own box
// back, which proves the change was theirs: an lf-ask that grew by exactly what its
// options grew is not named beside them, and one that also grew on its own, in its
// flow or in a size it sets itself, is. An inline widget runs through its holder's
// lines, which no size puts back, so nothing proves its holder's change was the
// widget's, and the holder is named beside it. A widget hidden now is left to the
// widget that hid it, whose own box carries the change.
export function changedBoxes() {
  const readings = globalThis.__leafRenderDriver
    .firstBoxes()
    .filter(({ element }) => shown(element))
    .map((first) => {
      const { width, height } = first.element.getBoundingClientRect();
      return { element: first.element, first, now: { width, height } };
    });
  const differs = (/** @type {Box} */ box, /** @type {Box} */ first) =>
    Math.abs(box.width - first.width) >= ROUNDING ||
    Math.abs(box.height - first.height) >= ROUNDING;
  const changed = readings.filter((reading) => differs(reading.now, reading.first));
  const own = (/** @type {SizeReading} */ holder) => {
    const inside = changed.filter(
      (reading) => reading !== holder && holder.element.contains(reading.element),
    );
    const outermost = inside.filter(
      (reading) =>
        !inside.some(
          (other) => other !== reading && other.element.contains(reading.element),
        ),
    );
    if (!outermost.length) return true;
    if (outermost.some(({ element }) => getComputedStyle(element).display === "inline"))
      return true;
    return differs(withFirstSizes(holder, outermost), holder.first);
  };
  return changed.filter(own).map(({ element, first, now }) => ({
    tag: element.localName,
    id: element.id,
    first: { width: first.width, height: first.height },
    now,
  }));
}

// How tall a block `heldScrollers` adds to a box: taller than any widget's own bound.
const ADDED_BLOCK = 4000;
const WRITTEN_IN = `input, select, ${TEXT_BOX}`;

// Whether `box`'s CSS asks it to scroll vertically. Beside an `auto` inline axis CSS
// computes a `visible` block axis to `auto`, so a box that scrolls only sideways reads
// as a vertical scroller too; with its inline axis set back to `visible` for one read,
// only an asked-for vertical scroll remains.
/** @param {HTMLElement} box */
const asksVerticalScroll = (box) => {
  const style = box.getAttribute("style");
  box.style.setProperty("overflow-x", "visible", "important");
  const asked = userScrollport(getComputedStyle(box).overflowY);
  if (style === null) box.removeAttribute("style");
  else box.setAttribute("style", style);
  return asked;
};

/** @param {Element} box */
const overflowsVertically = (box) => box.scrollHeight > box.clientHeight + ROUNDING;

// Each box in one of `tags`' widgets that holds its own height and scrolls inside it
// without saying so. A widget in ordinary flow grows with its content, and a box that
// needs a scroll of its own declares `--lf-holds-height: 1`, as a bounded block does
// (browser/AGENTS.md, "The page holds still under the user's aim").
//
// A box that scrolls vertically now holds its height, whatever it asked for. A box
// whose CSS asks for vertical scrolling but whose content fits is asked again with more
// content: a tall block is added at its end and taken away in the same task, and a box
// that then overflows kept a height its content did not decide, whether a theme's
// height, a grid track or a percentage of a held parent set it. So an empty widget whose
// rows the log has not supplied yet answers as a full one would, and a box that grows
// into the block, from a minimum height or beside a taller sibling, is not named. A box
// that asks only for sideways scrolling is not asked again, since its height may be its
// drawing's.
//
// A box is its nearest Leaf widget's, across shadow roots, so a vendored component's
// scroller answers to the widget that placed it. A field the user writes in keeps its
// own box as they type, so form controls, text fields and editable regions are left
// out. This writes the page, so only a page nothing reads again, such as the report's
// page of worked examples, is read this way.
/** @param {string[]} tags */
export function heldScrollers(tags) {
  const main = pageDocument();
  if (!main) return [];
  const own = new Set(tags);
  const found = [];
  for (const tree of openRoots(main))
    for (const box of tree.querySelectorAll("*")) {
      if (
        !(box instanceof HTMLElement) ||
        box.matches(WRITTEN_IN) ||
        box.isContentEditable
      )
        continue;
      const style = getComputedStyle(box);
      if (
        !userScrollport(style.overflowY) ||
        /^(inline|contents|none)$/.test(style.display) ||
        style.getPropertyValue("--lf-holds-height").trim() === "1" ||
        !shown(box)
      )
        continue;
      /** @type {Element | null} */
      let owner = box;
      while (owner && !owner.localName.startsWith("lf-")) owner = upFrom(owner);
      if (!owner || !own.has(owner.localName)) continue;
      let held = overflowsVertically(box);
      if (!held && asksVerticalScroll(box)) {
        const block = document.createElement("div");
        block.style.cssText =
          `display: block; flex: none; block-size: ${ADDED_BLOCK}px; ` +
          "inline-size: 0; margin: 0; padding: 0; border: 0";
        (box.shadowRoot ?? box).append(block);
        held = overflowsVertically(box);
        block.remove();
      }
      if (held)
        found.push({
          tag: owner.localName,
          id: owner.id,
          at: locate(box),
          height: box.clientHeight,
        });
    }
  return found;
}

// Each command in one of `tags`' widgets that declares context keys and no
// `bindingBadge`. Context keys are the widget's aliases for pressing a control from
// elsewhere, as an obligation forwards its digits; a key the page never shows works only
// for a user who already knows it (module-input.md, "Commands and keyboard
// routes"). A route without its own `bindingBadge` takes its row's. The reading is the
// declaration, not the keys reachable now, so a command whose keys depend on state is
// read the same in every state. A command belongs to the nearest Leaf widget holding
// the element that declared it, as a box does in `heldScrollers`, so a dependency's
// widget nested in one of `tags`' answers for its own commands.
/** @param {string[]} tags */
export function unshownContextKeys(tags) {
  const own = new Set(tags);
  const found = [];
  const seen = new Set();
  for (const { source, scope } of commandDeclarationsWithin(document.body)) {
    /** @type {Element | null} */
    let owner = source;
    while (owner && !owner.localName.startsWith("lf-")) owner = upFrom(owner);
    if (!owner || !own.has(owner.localName)) continue;
    for (const row of scope.rows)
      for (const command of [row, ...commandRoutes(row)]) {
        if (command.contextKeys === undefined) continue;
        const badge =
          command.bindingBadge !== undefined ? command.bindingBadge : row.bindingBadge;
        if (badge !== undefined) continue;
        const key = `${owner.localName}#${owner.id}#${command.id}`;
        if (seen.has(key)) continue;
        seen.add(key);
        found.push({ tag: owner.localName, id: owner.id, command: command.id });
      }
  }
  return found;
}
