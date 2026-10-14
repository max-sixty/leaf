import {
  inChrome,
  watchPassageRoot
} from "./bundle-passage-facts.js";
import {
  PRESS,
  SHADOW_STARTUP_CSS,
  liveStages,
  paintKeysWithin,
  rowArrows,
  shadowRules,
  watchArrivalsIn,
  watchLayers
} from "./bundle-page-paint.js";
import {
  move
} from "./bundle-dom-move.js";
import {
  watchStandingIn
} from "./bundle-sample-visibility.js";

// runtime/stylesheets.js
var sheets = JSON.parse(
  document.querySelector(
    'script[type="application/json"][data-lf-runtime][data-lf-sheets]'
  ).textContent
);
var inBaseLayer = (text) => `@layer lf-base {
${text}
}`;
function constructSheet(text) {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  return sheet;
}
var chromeSheet = constructSheet(sheets.chrome);
var chromeSharedClasses = Object.freeze([
  "lf-aiming",
  "lf-btn",
  "lf-ins-block",
  "lf-over-item",
  "lf-react-mark",
  "lf-skip",
  "lf-ui",
  "lf-version-inline",
  "lf-version-inline-deletion"
]);
var marksSheet = constructSheet(sheets.marks);
var annotationMarkSheets = sheets.annotations ? [constructSheet(sheets.annotations.marks)] : [];
var annotationSheets = sheets.annotations ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets] : [];

// runtime/keyboard/disclosure.js
var disclosureWatch = new MutationObserver((records) => {
  for (const r of records)
    if (
      /** @type {Element} */
      r.target.getAttribute(r.attributeName) !== r.oldValue
    )
      paintKeysWithin(r.target);
});
var watchDisclosures = (root) => disclosureWatch.observe(root, {
  subtree: true,
  attributeFilter: ["open", "aria-expanded"],
  attributeOldValue: true
});
var DISCLOSE = (el) => {
  const open = disclosed(el);
  if (open === null) return [...PRESS, "ArrowLeft", "ArrowRight"];
  const [back, ahead] = rowArrows(el);
  return inChrome(el) ? PRESS : [...PRESS, open ? back : ahead];
};
var DISCLOSURE_SELECTOR = 'details > summary, :is(button, [role="button"])[aria-expanded]';
function disclosed(el) {
  return !el?.matches?.(DISCLOSURE_SELECTOR) ? null : el.matches("details > summary") ? el.parentElement.open : el.getAttribute("aria-expanded") === "true";
}

// runtime/dom-children.js
import { diffArrays } from "/vendor/jsdiff.esm.js";
function setChildren(parent, nodes) {
  setChildLists([[parent, nodes]]);
}
function setChildLists(lists) {
  for (const [parent, nodes] of lists) orderChildren(parent, nodes);
  for (const [parent, nodes] of lists) {
    const keep = new Set(nodes);
    for (const child of [...parent.childNodes]) if (!keep.has(child)) child.remove();
  }
}
function orderChildren(parent, nodes) {
  const owned = new Set(nodes);
  order(parent, nodes, (node) => !owned.has(node));
}
function setRenderedChildren(parent, nodes) {
  const after = document.createDocumentFragment();
  after.append(...nodes);
  patchChildren(parent, parent, after, {
    pairs: new Map([...sourceNodes(parent)].map((node) => [node, node])),
    arrive: (node) => node,
    sameValue: (name, held, wanted) => held === wanted,
    touched: () => {
    },
    declared: () => false,
    same: (held, wanted) => held.isEqualNode(wanted),
    generated: () => false
  });
}
function order(parent, nodes, passed = () => false) {
  const list = [...nodes];
  const stay = staying(parent, list);
  let cursor = parent.firstChild;
  for (const node of list) {
    while (cursor && passed(cursor)) cursor = cursor.nextSibling;
    if (node === cursor) cursor = cursor.nextSibling;
    else if (stay.has(node)) cursor = node.nextSibling;
    else move(parent, node, cursor);
  }
}
function staying(parent, nodes) {
  const places = new Map([...parent.childNodes].map((node, at) => [node, at + 1]));
  const size = places.size;
  const best = new Array(size + 1).fill(-1);
  const weightAt = new Array(size + 1).fill(0);
  const weights = [];
  const previous = [];
  let last = -1;
  nodes.forEach((node, at) => {
    const place = places.get(node);
    if (!place) return;
    let before = -1;
    for (let i = place - 1; i > 0; i -= i & -i)
      if (best[i] >= 0 && (before < 0 || weightAt[i] >= weights[before]))
        before = best[i];
    const weight = (node.nodeType === Node.ELEMENT_NODE ? nodes.length + 1 : 1) + (before < 0 ? 0 : weights[before]);
    weights[at] = weight;
    previous[at] = before;
    for (let i = place; i <= size; i += i & -i)
      if (best[i] < 0 || weight >= weightAt[i]) {
        best[i] = at;
        weightAt[i] = weight;
      }
    if (last < 0 || weight >= weights[last]) last = at;
  });
  const stay = /* @__PURE__ */ new Set();
  for (let at = last; at >= 0; at = previous[at]) stay.add(nodes[at]);
  return stay;
}
function patchTree(before, after, rules) {
  const live = rules.pairs.get(before);
  patchAttributes(live, before, after, rules);
  patchChildren(tree(live), tree(before), tree(after), rules);
}
function patchRetains(before, after, target, rules) {
  if (!target?.isConnected) return false;
  if (!sourceOwns(before, target, rules)) return true;
  return retainedWithin(before, after, target, rules);
}
function sourceOwns(source, target, rules) {
  const owns = (node) => rules.contains(target, rules.pairs.get(node));
  if (owns(source)) return true;
  for (const node of sourceNodes(source)) if (owns(node)) return true;
  return false;
}
function retainedWithin(before, after, target, rules) {
  const live = rules.pairs.get(before);
  if (!live || !sourceOwns(before, target, rules)) return false;
  if (kept(before, after, rules)) return true;
  if (live === target) return false;
  if (before.attributes.length !== after.attributes.length || [...before.attributes].some(
    ({ name, value }) => !after.hasAttribute(name) || !rules.sameValue(name, value, after.getAttribute(name))
  ))
    return false;
  const children = [...tree(before).childNodes];
  const matches = new Map(
    [...matchNodes(children, [...tree(after).childNodes])].map(([wanted, held]) => [
      held,
      wanted
    ])
  );
  for (const held of children) {
    const node = rules.pairs.get(held);
    if (node?.nodeType !== Node.ELEMENT_NODE || !sourceOwns(held, target, rules))
      continue;
    const wanted = matches.get(held);
    if (!wanted) return false;
    const retains = atomic(held, wanted, node, rules) ? kept(held, wanted, rules) : retainedWithin(held, wanted, target, rules);
    if (!retains) return false;
  }
  return true;
}
var tree = (node) => node.localName === "template" ? node.content : node;
function patchAttributes(live, before, after, rules) {
  let changed = false;
  for (const { name, value } of [...before.attributes]) {
    if (after.hasAttribute(name)) continue;
    if (name === "class") live.classList.remove(...tokens(value));
    else live.removeAttribute(name);
    changed = true;
  }
  for (const { name, value } of after.attributes) {
    const held = before.getAttribute(name);
    if (held !== null && rules.sameValue(name, held, value)) continue;
    if (name === "class") {
      live.classList.remove(...tokens(held ?? ""));
      live.classList.add(...tokens(value));
    } else live.setAttribute(name, value);
    changed = true;
  }
  if (changed) rules.touched(live);
}
var tokens = (value) => value.split(/\s+/).filter(Boolean);
function writeText(node, next) {
  const held = node.data;
  if (held === next) return;
  let prefix = 0;
  while (prefix < held.length && prefix < next.length && held[prefix] === next[prefix])
    prefix += 1;
  let suffix = 0;
  while (suffix < held.length - prefix && suffix < next.length - prefix && held[held.length - suffix - 1] === next[next.length - suffix - 1])
    suffix += 1;
  node.replaceData(
    prefix,
    held.length - prefix - suffix,
    next.slice(prefix, next.length - suffix)
  );
}
function evict(before, live, rules) {
  live.remove();
  for (const inner of sourceNodes(before)) {
    const stray = rules.pairs.get(inner);
    if (!stray?.parentNode || live.contains(stray)) continue;
    stray.remove();
  }
}
function* sourceNodes(node) {
  for (const child of tree(node).childNodes) {
    yield child;
    yield* sourceNodes(child);
  }
}
function patchChildren(liveParent, beforeParent, afterParent, rules) {
  const held = [...beforeParent.childNodes];
  const wanted = [...afterParent.childNodes];
  const matches = matchNodes(held, wanted);
  const matched = new Set(matches.values());
  for (const node of held) {
    if (matched.has(node)) continue;
    evict(node, rules.pairs.get(node), rules);
  }
  const placed = [];
  for (const node of wanted) {
    const before = matches.get(node);
    const held2 = before && rules.pairs.get(before);
    const live = held2?.parentNode ? held2 : null;
    if (!live) {
      placed.push(rules.arrive(node, liveParent));
      continue;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) writeText(live, node.data);
    else if (!atomic(before, node, live, rules)) patchTree(before, node, rules);
    else if (!kept(before, node, rules)) {
      evict(before, live, rules);
      placed.push(rules.arrive(node, liveParent));
      continue;
    }
    rules.pairs.set(node, live);
    if (live.parentNode === liveParent) placed.push(live);
  }
  order(liveParent, placed, rules.generated);
}
var atomic = (before, after, live, rules) => rules.declared(before) && !rules.reaches(before, after) || [...tree(before).childNodes].some(
  (node) => rules.pairs.get(node)?.parentNode !== tree(live)
);
var kept = (before, after, rules) => rules.declared(before) ? rules.unchanged(before, after) : rules.same(before, after);
function matchNodes(held, wanted) {
  const matches = /* @__PURE__ */ new Map();
  const matched = /* @__PURE__ */ new Set();
  const byId = /* @__PURE__ */ new Map();
  for (const node of held)
    if (node.nodeType === Node.ELEMENT_NODE && node.id && !byId.has(node.id))
      byId.set(node.id, node);
  for (const node of wanted) {
    if (node.nodeType !== Node.ELEMENT_NODE || !node.id) continue;
    const match = byId.get(node.id);
    if (!match || match.localName !== node.localName || matched.has(match)) continue;
    matches.set(node, match);
    matched.add(match);
  }
  alignRest(
    held.filter((node) => !matched.has(node)),
    wanted.filter((node) => !matches.has(node)),
    matches
  );
  return matches;
}
var COLLAPSE = /\s+/g;
var signature = (node) => {
  if (node.nodeType !== Node.ELEMENT_NODE) return `${node.nodeType}:${node.data}`;
  const words = (node.localName === "template" ? node.content : node).textContent;
  return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};
function alignRest(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  let gapHeld = [];
  let gapWanted = [];
  const closeGap = () => {
    pairInGap(gapHeld, gapWanted, matches);
    gapHeld = [];
    gapWanted = [];
  };
  for (const run of diffArrays(held.map(signature), wanted.map(signature))) {
    const count = run.value.length;
    if (run.added) gapWanted.push(...wanted.slice(wantedAt, wantedAt += count));
    else if (run.removed) gapHeld.push(...held.slice(heldAt, heldAt += count));
    else {
      closeGap();
      for (let at = 0; at < count; at++)
        matches.set(wanted[wantedAt + at], held[heldAt + at]);
      heldAt += count;
      wantedAt += count;
    }
  }
  closeGap();
}
function pairInGap(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
    const count = run.value.length;
    if (run.added) wantedAt += count;
    else if (run.removed) heldAt += count;
    else {
      for (let at = 0; at < count; at++)
        matches.set(wanted[wantedAt + at], held[heldAt + at]);
      heldAt += count;
      wantedAt += count;
    }
  }
}
var interchangeable = (held, wanted) => held.nodeType === wanted.nodeType && (held.nodeType !== Node.ELEMENT_NODE || held.localName === wanted.localName && !(held.id && wanted.id));

// runtime/shadow-stage.js
var widgetSheets = /* @__PURE__ */ new Map();
function registerWidgetStyles(name, text) {
  const existing = widgetSheets.get(name);
  if (existing) return existing;
  const sheet = constructSheet(inBaseLayer(text));
  widgetSheets.set(name, sheet);
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  for (const root of liveStages())
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
  return sheet;
}
var stageStyles = /* @__PURE__ */ new WeakMap();
function shadowStage(host, nodes) {
  const root = host.shadowRoot ?? host.attachShadow({ mode: "open" });
  watchArrivalsIn(root);
  root.adoptedStyleSheets = [
    ...annotationMarkSheets,
    marksSheet,
    ...widgetSheets.values()
  ];
  watchDisclosures(root);
  watchLayers(root);
  watchStandingIn(root);
  const rules = SHADOW_STARTUP_CSS + shadowRules;
  let style = stageStyles.get(root);
  if (style?.textContent !== rules) {
    style = document.createElement("style");
    style.textContent = rules;
    stageStyles.set(root, style);
  }
  setChildren(root, [style, ...nodes]);
  watchPassageRoot(root);
  return root;
}

export {
  inBaseLayer,
  chromeSheet,
  chromeSharedClasses,
  marksSheet,
  annotationMarkSheets,
  annotationSheets,
  watchDisclosures,
  DISCLOSE,
  DISCLOSURE_SELECTOR,
  disclosed,
  setChildren,
  setChildLists,
  orderChildren,
  setRenderedChildren,
  patchTree,
  patchRetains,
  registerWidgetStyles,
  shadowStage
};
