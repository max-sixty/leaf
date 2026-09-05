import {
  inChrome,
  inUi,
  matchesWhen,
  quoted,
  textNodesUnder,
} from "/runtime/widget-api.js";
import { openRoots } from "./open-roots.js";

export const failSoftErrors = () =>
  [...document.querySelectorAll(".lf-error")].map((el) => el.textContent.trim());

const PAINT_PROBE = "--_leaf-render-paint-value";
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

const renderedAt = (element) => {
  const ancestors = [];
  for (let current = element; current;) {
    ancestors.push(current);
    current = current.parentElement ?? current.getRootNode().host ?? null;
  }
  const owner =
    ancestors.find((el) => el.id && el.localName.includes("-")) ??
    ancestors.find((el) => el.id) ??
    element;
  return {
    tag: owner.localName,
    id: owner.id,
    part:
      ancestors.find((el) => el.hasAttribute("data-id"))?.getAttribute("data-id") ?? "",
  };
};

// A generated SVG crosses two boundaries before its paint reaches the reader: a widget
// turns authored data into attributes, then the page's cascade resolves their custom
// properties. Resolve each value through a temporary custom property in the element's
// live cascade, then let the browser validate the resulting tokens for that property.
export function invalidPaints() {
  if (!document.querySelector("main")) return [];
  const properties = [
    "color",
    "fill",
    "flood-color",
    "lighting-color",
    "stop-color",
    "stroke",
  ];
  const found = [];
  for (const root of openRoots(document))
    for (const element of root.querySelectorAll(
      "[color], [fill], [flood-color], [lighting-color], [stop-color], [stroke], [style]",
    )) {
      if (element.namespaceURI !== "http://www.w3.org/2000/svg") continue;
      for (const property of properties) {
        const value =
          element.style.getPropertyValue(property).trim() ||
          element.getAttribute(property)?.trim();
        if (!value || !/\bvar\(/i.test(value) || validPaint(element, property, value))
          continue;
        found.push({
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
export const missingUpgrades = (widgets) =>
  Object.entries(widgets)
    .filter(
      ([tag, entry]) =>
        entry["x-upgrade"] && document.querySelector(tag) && !customElements.get(tag),
    )
    .map(([tag]) => tag);
export const missingVisualProviders = (widgets) =>
  Object.entries(widgets)
    .filter(([, entry]) => entry["x-visual"] && typeof entry["x-visual"] === "object")
    .flatMap(([tag]) =>
      [...document.querySelectorAll(tag)].map((el) => ({
        tag,
        id: el.id,
        missing: ["lfVisualPart", "lfVisualPartAt"].filter(
          (name) => typeof el[name] !== "function",
        ),
      })),
    )
    .filter((instance) => instance.missing.length);
export const undeclaredShadowRoots = (registry) => [
  ...new Set(
    [...document.querySelectorAll("*")]
      .filter((el) => el.shadowRoot && !registry[el.localName]?.["x-shadow"])
      .map((el) => `<${el.localName}>`),
  ),
];
export const missingConversations = (widgets) =>
  Object.entries(widgets)
    .filter(([, entry]) => entry["x-conversation"])
    .flatMap(([tag, entry]) =>
      [...document.querySelectorAll(tag)]
        .filter(
          (el) =>
            !inChrome(el) &&
            !quoted(el) &&
            matchesWhen(el, entry["x-conversation"].when),
        )
        .map((el) => ({
          tag,
          id: el.id,
          hosts: [...el.querySelectorAll(".lf-conversation")].filter(
            (host) => host.dataset.lfConversation === el.id,
          ).length,
        })),
    )
    .filter((instance) => instance.hosts !== 1);

// Attributes standing on a widget that its entry never declared. The schema is the
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
// `version check --render` uses to decide whether a version overrules the user.
//
// Deduped and reported per tag and attribute, because one mistake is on every instance.
export function undeclaredAttrs(widgets) {
  // What a module may write without declaring: the platform's own vocabulary for
  // what a control is and how it behaves, and the data-* namespace the runtime and
  // the widgets both paint in. `class` and `style` are the same kind of fact — a
  // look, not a state a version could carry.
  const painted = /^(?:data-|aria-)/;
  const platform = new Set(["role", "class", "style", "hidden", "tabindex"]);
  const all = openRoots(document);
  const found = [];
  for (const [tag, entry] of Object.entries(widgets)) {
    if (!entry.properties) continue;
    for (const root of all)
      for (const el of root.querySelectorAll(tag))
        for (const a of el.attributes)
          if (
            !painted.test(a.name) &&
            !platform.has(a.name) &&
            !(a.name in entry.properties)
          )
            found.push({ tag, id: el.id, attr: a.name });
  }
  return found;
}

// The two sides of the settlement contract, compared on the rendered page. The mark —
// data-lf-state on a holder — is the layer's paint of a logged decision (projection
// reconciliation in leaf.js), and the anchor pass retires slots by it, so whatever it
// says, the page's
// reading obeys. What can still go wrong is a family's, and both failures render
// perfectly: a module that writes the mark where the log decided nothing silences words
// the reader can still see and select, and a settled slot can show its words anyway — a
// later layer's rule outranking the default hide, a module re-showing what it folded —
// leaving the reader selecting words no comment can anchor to, with the refusal
// arriving later, at `leaf comment`, nowhere near the mistake. So the expected outcome
// comes from the file's reading (`decisions`, folded over this version's log), never
// from the page, and the page answers only for what it shows.
//
// The words walk is textNodesUnder with an accepts of its own, on purpose: the anchor
// pass's default accepts already skips a marked holder's slots, so asking it whether
// the retired words are gone would let the mark answer for the screen. What it keeps
// of that reading is the boundary — declared shadow roots, the same trees replay's
// elementById marks across, which is why the holders are found through OPEN_ROOTS
// too — and the chrome test (inUi): a declared label is the page's words, so a
// settled slot still showing one is still showing words. The visibility guards are
// COVERED_WORDS', for its reasons: [hidden] holds until-found content whose boxes
// report as last laid out, and visibility and opacity hide with layout intact. One
// scheme, on the trapped-margin reading's premise — the palettes carry no geometry
// between them. Replay installs a fold's terminal DOM synchronously: the runtime's
// motion() refuses animation while it is projecting state or before presentation.
// The gate's global `pageSettled` fact separately holds independently authored motion
// before any reading starts. This reading stays synchronous: waiting on
// `Animation.finished` here would give page.evaluate a promise the driver cannot
// interrupt if the compositor stops.
export function retiredSlots(holders) {
  const all = openRoots(document);
  const find = (id) => {
    for (const r of all) {
      const el = r.getElementById(id);
      if (el) return el;
    }
    return null;
  };
  const found = [];
  const showing = (slot) => {
    for (const seg of textNodesUnder(slot, (n) => !inUi(n))) {
      const n = seg.node,
        el = n.parentElement;
      if (!n.data.trim()) continue;
      if (el.closest(".lf-chrome, .lf-mark-note, .lf-quiet, [hidden]")) continue;
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
    const at = `<${h.tag} id='${h.id}'>`;
    if (mark !== (h.outcome ?? null)) {
      const log = h.outcome ? "`" + h.outcome + "`" : "no decision";
      found.push(
        `${at} wears data-lf-state=${JSON.stringify(mark)} where the ` +
          `log records ${log} — the mark is the layer's paint of a logged ` +
          `decision, and the anchor pass retires slots by it, so a module may ` +
          `say only what the log decided`,
      );
      continue;
    }
    for (const tag of h.slots)
      for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
        for (const slot of root.querySelectorAll(`:scope > ${tag}`)) {
          const words = showing(slot);
          if (words === null) continue;
          found.push(
            `${at} settled \`${h.outcome}\` and its <${tag}> still ` +
              `shows ${JSON.stringify(words)} — those words have left the ` +
              `page's reading, so the reader can select what no comment can ` +
              `anchor to; the layer hides a retired slot by default, so ` +
              `something in this family is showing it anyway`,
          );
        }
  }
  return found;
}
