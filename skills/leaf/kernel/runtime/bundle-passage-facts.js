import {
  PAGE_PAINT_ATTRIBUTE,
  SAID,
  UI_MARKS,
  decisionFor,
  declaredRoot,
  hostIn,
  inUi,
  overIn,
  pageShadowRoots,
  pageUpgraded,
  refuseShadowRoot,
  registry,
  reportPageError,
  shadowRootsIn,
  uiInside
} from "./bundle-page-paint.js";
import {
  readPart
} from "./bundle-semantic-state.js";
import {
  shadowHost,
  under,
  upFrom
} from "./bundle-sample-visibility.js";

// runtime/passage-facts.js
var COLLAPSE = /[\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
var TEXT_BLOCK = "p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary";
var CONTEXT = 24;

// runtime/text-alignment.js
import { diffArrays } from "/vendor/jsdiff.esm.js";
var textUnits = new Intl.Segmenter(void 0, { granularity: "word" });
var sentenceUnits = new Intl.Segmenter(void 0, {
  granularity: "sentence"
});
var MAX_EDIT_LENGTH = 1e3;
function alignText(before, after, units = textUnits, maxEditLength = MAX_EDIT_LENGTH) {
  const left = [...units.segment(before)].map((part) => part.segment);
  const right = [...units.segment(after)].map((part) => part.segment);
  const runs = [];
  const push = (kind, text) => {
    if (!text) return;
    const last = runs.at(-1);
    if (last?.kind === kind) last.text += text;
    else runs.push({ kind, text });
  };
  let prefix = 0;
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix])
    prefix++;
  let suffix = 0;
  while (prefix + suffix < left.length && prefix + suffix < right.length && left[left.length - suffix - 1] === right[right.length - suffix - 1])
    suffix++;
  push("same", left.slice(0, prefix).join(""));
  const leftEnd = left.length - suffix;
  const rightEnd = right.length - suffix;
  const changes = diffArrays(
    left.slice(prefix, leftEnd),
    right.slice(prefix, rightEnd),
    { maxEditLength }
  );
  if (changes) {
    for (const change of changes) {
      const kind = change.added ? "insert" : change.removed ? "delete" : "same";
      push(kind, change.value.join(""));
    }
  } else {
    push("delete", left.slice(prefix, leftEnd).join(""));
    push("insert", right.slice(prefix, rightEnd).join(""));
  }
  push("same", left.slice(leftEnd).join(""));
  return runs;
}
function alignInlineText(before, after) {
  const coarse = alignText(before, after, sentenceUnits);
  const runs = [];
  const push = (run) => {
    const last = runs.at(-1);
    if (last?.kind === run.kind) last.text += run.text;
    else runs.push({ ...run });
  };
  for (let at = 0; at < coarse.length; at++) {
    const run = coarse[at];
    const replacement = run.kind === "delete" && coarse[at + 1]?.kind === "insert";
    if (!replacement) {
      push(run);
      continue;
    }
    const next = coarse[++at];
    const fine = alignText(run.text, next.text);
    const retained = fine.filter((part) => part.kind === "same").reduce((length, part) => length + part.text.length, 0);
    if (retained >= Math.min(run.text.length, next.text.length) * 0.6)
      fine.forEach(push);
    else {
      push(run);
      push(next);
    }
  }
  return runs;
}

// runtime/words.js
var labelWords = (value) => String(value ?? "").replace(COLLAPSE, " ").trim();
function excerptWords(value, cap) {
  const words = labelWords(value);
  const points = [...words];
  if (points.length <= cap) return words;
  const excerpt = points.slice(0, cap - 1);
  const boundary = excerpt.lastIndexOf(" ");
  const end = boundary >= cap / 2 ? boundary : excerpt.length;
  return `${excerpt.slice(0, end).join("")}\u2026`;
}

// runtime/passages.js
var passageFences = /* @__PURE__ */ new WeakSet();
var verbatimOwnerIdentity = /* @__PURE__ */ new WeakMap();
var verbatimBoundaryIdentity = /* @__PURE__ */ new WeakMap();
var settledReading = null;
var settledDecisions;
var settled = null;
var settledKey = "[]";
function settlements() {
  if (settledDecisions !== registry.$decisions || !settledReading) {
    const decisions = settledDecisions = registry.$decisions;
    settledReading = readPart((root) => {
      const holders = /* @__PURE__ */ new Map();
      for (const [id, { state }] of root.effective.widgets) {
        const tag = root.document.authored.get(id)?.tag;
        const decision = decisions?.[tag];
        const outcome = decision && /** @type {{detail?: {outcome?: string}} | undefined} */
        state[decision.verb]?.detail?.outcome;
        const retires = outcome ? decision.retires[outcome] : null;
        if (retires?.length) holders.set(id, { tag, retires: [...retires] });
      }
      return holders;
    });
  }
  const next = settledReading();
  if (next !== settled) {
    settled = next;
    settledKey = JSON.stringify([...settled]);
  }
  return settled;
}
function retiredSlot(el) {
  const holder = upFrom(el);
  if (!holder?.id || el.ownerDocument !== document) return false;
  const settlement = settlements().get(holder.id);
  return settlement?.tag === holder.localName && settlement.retires.includes(el.localName);
}
function renderRetired(el, outcome) {
  const outcomes = decisionFor(el.localName)?.retires;
  if (!outcomes) return;
  for (const [candidate, tags] of Object.entries(outcomes))
    for (const tag of tags)
      for (const root of [el, ...el.shadowRoot ? [el.shadowRoot] : []])
        for (const slot of root.children)
          if (slot.localName === tag)
            slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, candidate === outcome);
}
function settledAway(el) {
  for (let at = el; at; at = at.parentElement) if (retiredSlot(at)) return true;
  const nodes = [...el.childNodes];
  return nodes.some((n) => n.nodeType === 1 && retiredSlot(n)) && nodes.every(
    (n) => n.nodeType === 1 ? retiredSlot(n) || uiInside(n, el) : n.nodeType !== 3 || !n.data.trim()
  );
}
var GENERATED = ".lf-ui, [data-lf-gen]";
var DATUM = "[data-lf-projection][data-lf-datum]";
var inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
var showsWords = (block) => block.checkVisibility({ visibilityProperty: true });
var leafSurface = (node) => node ? closestAcross(node, ".lf-chrome, [data-lf-runtime]") : null;
var pageWords = (node) => Boolean(node) && !inChrome(node) && !inUi(node);
var bareTextRefusal = (n) => {
  const host = shadowHost(n.getRootNode());
  const at = host ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>` : "a module";
  return new Error(
    `${at} staged bare text into a shadow root: ${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, so the page holds no block, cell or fence for it. Give a module's rendered words an element to sit in.`
  );
};
var elementOver = (n) => {
  if (n.parentElement) return n.parentElement;
  throw bareTextRefusal(n);
};
function refusesBareText(root) {
  let bare = root.firstChild;
  while (bare && bare.nodeType !== Node.TEXT_NODE) bare = bare.nextSibling;
  if (!bare) return false;
  refuseShadowRoot(root);
  const refusal = bareTextRefusal(bare);
  reportPageError(refusal);
  if (!pageUpgraded())
    window.dispatchEvent(
      new CustomEvent("lf-startup-failed", {
        detail: { reason: refusal.message, error: refusal, page: true }
      })
    );
  return true;
}
var frameOf = (node) => {
  for (let a = node?.nodeType === 1 ? node : upFrom(node); a; a = upFrom(a))
    if (a.localName?.startsWith("lf-")) return a;
  return null;
};
var NO_CONTEXT = Object.freeze({
  chrome: false,
  silenced: false,
  generated: false,
  gen: null,
  block: null,
  island: null,
  cells: null
});
var GEN = "[data-lf-gen]";
var ISLAND = "[data-lf-markdown-words]";
var MARKS = [UI_MARKS, GENERATED, ISLAND].join(", ");
var BLOCK_TAGS = new Set(TEXT_BLOCK.split(","));
var chromeMark = (el) => el.matches(UI_MARKS) ? !el.matches(SAID) : null;
var SILENT_TAGS = /* @__PURE__ */ new Set(["script", "style", "textarea"]);
var silences = (el) => SILENT_TAGS.has(el.localName) || retiredSlot(el);
var unmodelled = (el) => {
  const attr = el.getAttribute("data-lf-said");
  return !(attr && registry[el.parentElement?.localName]?.["x-says"]?.[attr]);
};
var fileModelsPassage = (segments) => segments.every(
  ({ node, gen }) => !node.parentElement.isContentEditable && (!gen || !unmodelled(gen))
);
var opaque = (el) => passageFences.has(el);
var editingBoundary = (el) => Boolean(el.isContentEditable) !== Boolean(el.parentElement?.isContentEditable);
function enter(ctx, el, inFrame = true) {
  const marked = el.hasAttributes() && el.matches(MARKS);
  const block = BLOCK_TAGS.has(el.localName);
  const editing = editingBoundary(el);
  const cell = opaque(el) || editing || marked && el.matches(GEN) && unmodelled(el);
  const silent = !ctx.silenced && silences(el);
  if (!marked && !block && !cell && !silent) return ctx;
  const chrome = (marked && inFrame ? chromeMark(el) : null) ?? ctx.chrome;
  const generated = ctx.generated || marked && inFrame && el.matches(GENERATED);
  return {
    chrome,
    silenced: ctx.silenced || silent,
    generated,
    gen: marked && el.matches(GEN) ? el : ctx.gen,
    block: block ? el : ctx.block,
    island: marked && el.matches(ISLAND) ? el : ctx.island,
    cells: cell ? { el, editing, up: ctx.cells } : ctx.cells
  };
}
var crossed = (ctx) => ({
  ...ctx,
  chrome: false,
  silenced: false,
  generated: false,
  gen: null
});
function contextAt(el, frame) {
  const over = [];
  for (let a = el; a; a = upFrom(a)) over.push(a);
  let ctx = NO_CONTEXT;
  let inFrame = !frame;
  for (let i = over.length - 1; i >= 0; i--) {
    const a = over[i];
    if (a === frame) inFrame = true;
    if (a.parentNode?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) ctx = crossed(ctx);
    ctx = enter(ctx, a, inFrame);
  }
  return ctx;
}
var segmentIn = (node, ctx) => ({
  node,
  start: 0,
  end: node.data.length,
  block: ctx.block ?? (ctx.island ? upFrom(ctx.island) : null),
  gen: ctx.gen
});
var READINGS = {
  says: (ctx) => !ctx.chrome && !ctx.silenced,
  wrote: (ctx) => !ctx.generated,
  unsilenced: (ctx) => !ctx.chrome
};
var authored = (root) => {
  const frame = frameOf(root);
  return (n) => !overIn(n.nodeType === 1 ? n : elementOver(n), GENERATED, frame);
};
function walk(root, onText, skip = null, onBreak = null) {
  const frame = frameOf(root);
  const passed = /* @__PURE__ */ new Map();
  const contextOver = (node) => {
    const over = elementOver(node);
    return passed.get(over) ?? contextAt(over, frame);
  };
  const visit = (node, ctx) => {
    if (node.nodeType === Node.ELEMENT_NODE && node.localName === "br") {
      onBreak?.(ctx);
      return;
    }
    for (let child = node.firstChild; child; child = child.nextSibling) {
      if (child.nodeType === Node.TEXT_NODE) {
        if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
        onText(child, ctx);
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE || skip?.(child)) continue;
      const inner = enter(ctx, child);
      if (child.localName === "slot") {
        passed.set(child, inner);
        for (const assigned of child.assignedNodes({ flatten: true }))
          assigned.nodeType === Node.TEXT_NODE ? onText(assigned, contextOver(assigned)) : visit(assigned, enter(contextOver(assigned), assigned));
      } else {
        const declared = declaredRoot(child);
        if (declared && !refusesBareText(declared)) {
          passed.set(child, inner);
          visit(declared, crossed(inner));
        } else visit(child, inner);
      }
    }
  };
  const host = shadowHost(root);
  const start = root.nodeType === Node.ELEMENT_NODE ? contextAt(root, frame) : host ? crossed(contextAt(host, frame)) : NO_CONTEXT;
  visit(root, start);
}
function textNodesUnder(root, reading2 = "says", boundary = null) {
  const keeps = READINGS[reading2];
  const segments = [];
  let breakBefore = false;
  walk(
    root,
    (node, ctx) => {
      if (keeps(ctx)) {
        segments.push({ ...segmentIn(node, ctx), breakBefore });
        breakBefore = false;
      }
    },
    boundary && ((child) => boundary(child, segments.length)),
    (ctx) => {
      if (keeps(ctx)) breakBefore = true;
    }
  );
  return segments;
}
function closestAcross(node, selector) {
  let el = node?.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
  while (el) {
    const hit = el.closest(selector);
    if (hit) return hit;
    el = shadowHost(el.getRootNode());
  }
  return null;
}
var elementById = (id, root = document) => {
  const found = root === document ? document.getElementById(id) : root.querySelector(`[id="${CSS.escape(id)}"]`);
  if (found) return found;
  for (const shadow of shadowRootsIn(root)) {
    const inside = shadow.getElementById(id);
    if (inside) return inside;
  }
  return null;
};
var pageDocument = (doc = document) => doc.querySelector("body > main");
var authoredScope = (node) => closestAcross(node, ".lf-msg-body") ?? pageDocument();
var elementFromPointAcross = (x, y) => {
  let el = document.elementFromPoint(x, y);
  while (el && declaredRoot(el)) {
    const inner = el.shadowRoot.elementFromPoint(x, y);
    if (!inner || inner === el) break;
    el = inner;
  }
  return el;
};
var pageQueryAll = (selector) => [document, ...pageShadowRoots()].flatMap((root) => [
  ...root.querySelectorAll(selector)
]);
function pageRange(sel) {
  const plain = sel.getRangeAt(0);
  if (typeof sel.getComposedRanges !== "function") return plain;
  const shadowRoots = pageShadowRoots();
  if (!shadowRoots.length) return plain;
  const [composed] = sel.getComposedRanges({ shadowRoots });
  if (!composed) return plain;
  const { startContainer, startOffset, endContainer, endOffset } = composed;
  if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
  const range = document.createRange();
  range.setStart(startContainer, startOffset);
  range.setEnd(endContainer, endOffset);
  return range;
}
var writtenSelection = null;
var writtenBackward = false;
function selectEnds(anchor, focus) {
  const selection = getSelection();
  const from = document.createRange(), to = document.createRange();
  from.setStart(.../** @type {[Node, number]} */
  anchor);
  to.setStart(.../** @type {[Node, number]} */
  focus);
  writtenBackward = from.compareBoundaryPoints(Range.START_TO_START, to) > 0;
  selection.setBaseAndExtent(
    .../** @type {[Node, number]} */
    anchor,
    .../** @type {[Node, number]} */
    focus
  );
  writtenSelection = selectionEnds(selection);
}
var selectionEnds = (selection) => {
  const range = selection.rangeCount ? pageRange(selection) : null;
  return [
    selection.anchorNode,
    selection.anchorOffset,
    selection.focusNode,
    selection.focusOffset,
    range?.startContainer,
    range?.startOffset,
    range?.endContainer,
    range?.endOffset
  ];
};
function programmaticSelection(selection) {
  if (!writtenSelection) return false;
  if (selectionEnds(selection).every((end, i) => end === writtenSelection[i]))
    return true;
  writtenSelection = null;
  return false;
}
function selectionBackward(selection, range = pageRange(selection)) {
  if (selection.anchorNode.getRootNode() !== range.commonAncestorContainer.getRootNode())
    return programmaticSelection(selection) ? writtenBackward : selection.direction === "backward";
  const probe = document.createRange();
  probe.setStart(selection.anchorNode, selection.anchorOffset);
  return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}
function coveredBy(range, node) {
  const n = hostIn(node, range.commonAncestorContainer.getRootNode());
  if (!n || !range.intersectsNode(n)) return false;
  if (n !== node) {
    if (range.endContainer === n && range.endOffset === 0) return false;
    if (range.startContainer === n && range.startOffset === n.childNodes.length)
      return false;
  }
  return true;
}
function segmentsIn(range) {
  const segments = [];
  for (const segment of pageText().segments) {
    const { node } = segment;
    if (!coveredBy(range, node)) continue;
    const start = node === range.startContainer ? range.startOffset : 0;
    const end = node === range.endContainer ? range.endOffset : segment.end;
    if (end > start) segments.push({ ...segment, start, end });
  }
  return segments;
}
var blockAt = (node) => {
  const block = closestAcross(node, TEXT_BLOCK);
  if (block) return block;
  const island = closestAcross(node, ISLAND);
  return island ? upFrom(island) : null;
};
var segmentBlock = (segment) => segment.block ?? segment.node.parentElement;
var COLLAPSIBLE = new RegExp(`^(?:${COLLAPSE.source})$`, "u");
function readSegments(segments, mapCharacters) {
  let text = "";
  const units = [];
  let pendingSpace = null;
  const push = (character, start, end) => {
    if (COLLAPSIBLE.test(character)) {
      if (text)
        pendingSpace = pendingSpace ? { start: pendingSpace.start, end } : { start, end };
      return;
    }
    if (pendingSpace) {
      text += " ";
      if (mapCharacters) units.push({ text: " ", ...pendingSpace });
      pendingSpace = null;
    }
    text += character;
    if (mapCharacters) units.push({ text: character, start, end });
  };
  segments.forEach((seg, i) => {
    if (i && (seg.breakBefore || segmentBlock(seg) !== segmentBlock(segments[i - 1]))) {
      const point = { node: seg.node, offset: seg.start };
      push(" ", point, point);
    }
    let offset = seg.start;
    for (const character of seg.node.data.slice(seg.start, seg.end)) {
      const end = offset + character.length;
      push(character, { node: seg.node, offset }, { node: seg.node, offset: end });
      offset = end;
    }
  });
  return mapCharacters ? { text, units } : text;
}
var quoteFrom = (segments) => (
  /** @type {string} */
  readSegments(segments, false)
);
var readingFrom = (segments) => (
  /** @type {{text: string, units: {text: string, start: any, end: any}[]}} */
  readSegments(segments, true)
);
var cut = (text, from, to) => [...text].slice(from, to).join("");
var says = (el) => quoteFrom(textNodesUnder(el));
var wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));
function rangeOf(segments) {
  const range = document.createRange();
  range.setStart(segments[0].node, segments[0].start);
  range.setEnd(segments.at(-1).node, segments.at(-1).end);
  return range;
}
var EDGE = "\0";
function segmentAt({ starts }, i) {
  let lo = 0;
  let hi = starts.length - 1;
  if (hi < 0 || i < starts[0]) return -1;
  while (lo < hi) {
    const mid = lo + hi + 1 >> 1;
    if (starts[mid] <= i) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}
function pointAt(reading2, i) {
  const k = segmentAt(reading2, i);
  if (k === -1) return null;
  const segment = reading2.segments[k];
  const offset = i - reading2.starts[k];
  return offset < segment.end - segment.start ? { node: segment.node, offset: segment.start + offset, segment } : null;
}
function spanOf(reading2, lo, hi) {
  const { segments, starts } = reading2;
  const out = [];
  for (let k = Math.max(0, segmentAt(reading2, lo)); k < segments.length; k++) {
    const seg = segments[k];
    const from = starts[k];
    if (from >= hi) break;
    const a = Math.max(lo, from);
    const b = Math.min(hi, from + seg.end - seg.start);
    if (b > a)
      out.push({
        node: seg.node,
        start: seg.start + a - from,
        end: seg.start + b - from,
        block: seg.block,
        gen: seg.gen,
        breakBefore: seg.breakBefore && a === from
      });
  }
  return out;
}
var holds = (reading2, at, want, before) => {
  const there = neighbourhood(reading2, at, want.length || 1, before);
  if (!want) return there === "";
  return before ? there.endsWith(want) : there.startsWith(want);
};
function neighbourhood(reading2, at, want, before) {
  const { fences } = reading2;
  const edge = before ? fences.filter((f) => f <= at).at(-1) ?? 0 : fences.find((f) => f >= at) ?? reading2.raw.length;
  for (let raw = want * 2; ; raw *= 2) {
    const lo = before ? Math.max(edge, at - raw) : at;
    const hi = before ? at : Math.min(edge, at + raw);
    const text = quoteFrom(spanOf(reading2, lo, hi));
    if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
  }
}
var READING_MARKERS = [
  "class",
  "data-lf-said",
  "data-lf-gen",
  "slot",
  "name",
  "contenteditable"
];
var WATCH_READING = {
  subtree: true,
  childList: true,
  characterData: true,
  attributes: true,
  attributeOldValue: true,
  attributeFilter: READING_MARKERS
};
var reading = null;
var elementReadings = /* @__PURE__ */ new WeakMap();
var readingVocabulary;
var readingSettled;
var watcher = null;
var pageReads = (over) => over?.nodeType !== 1 || READINGS.says(contextAt(over, null));
var holdsSaid = (node) => node.nodeType === 1 && (node.matches(SAID) || node.querySelector(SAID) !== null);
var speaks = (node, read) => read && !(node.nodeType === 1 && chromeMark(node) === true) || holdsSaid(node);
var changesTheReading = (record) => {
  const { target } = record;
  if (record.type === "childList") {
    const read = pageReads(target);
    return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
  }
  if (record.type === "characterData") return pageReads(target.parentNode);
  if (record.attributeName === "class") {
    const was = /(^|\s)lf-ui(\s|$)/.test(record.oldValue ?? "");
    if (was === target.classList.contains("lf-ui")) return false;
  }
  if (record.attributeName === "name" && target.localName !== "slot") return false;
  const wasSaid = record.attributeName === "data-lf-said" && record.oldValue !== null;
  return wasSaid || holdsSaid(target) || pageReads(target.parentNode);
};
var readingVersion = 0;
var forgetReading = () => {
  reading = null;
  elementReadings = /* @__PURE__ */ new WeakMap();
  readingVersion += 1;
};
function pageReadingVersion() {
  catchUpReading();
  return readingVersion;
}
function watchReading() {
  if (watcher) return watcher;
  watcher = new MutationObserver((records) => {
    if (records.some(changesTheReading)) forgetReading();
  });
  watcher.observe(document, WATCH_READING);
  return watcher;
}
function watchPassageRoot(root) {
  watchReading().observe(root, WATCH_READING);
  forgetReading();
}
function fencePassageParts(root, children = root.children) {
  passageFences.add(root);
  for (const child of children) passageFences.add(child);
  forgetReading();
}
function pageText() {
  catchUpReading();
  return reading ??= readPage();
}
function catchUpReading() {
  const moved = watchReading().takeRecords().some(changesTheReading);
  const vocabulary = registry.$layer?.generation;
  settlements();
  if (moved || vocabulary !== readingVocabulary || settledKey !== readingSettled)
    forgetReading();
  readingVocabulary = vocabulary;
  readingSettled = settledKey;
}
function elementReading(element, reading2 = "says") {
  catchUpReading();
  let kept = elementReadings.get(element);
  if (kept?.[reading2] !== void 0) return kept[reading2];
  const value = quoteFrom(textNodesUnder(element, reading2));
  if (element.isConnected && element.ownerDocument === document && pageReads(element)) {
    if (!kept) elementReadings.set(element, kept = {});
    kept[reading2] = value;
  }
  return value;
}
function readPage() {
  const segments = [];
  const cellChains = [];
  const keeps = READINGS.says;
  let breakBefore = false;
  walk(
    document.body,
    (node, ctx) => {
      if (!keeps(ctx)) return;
      segments.push({ ...segmentIn(node, ctx), breakBefore });
      breakBefore = false;
      cellChains.push(ctx.cells);
    },
    null,
    (ctx) => {
      if (keeps(ctx)) breakBefore = true;
    }
  );
  const dynamicWords = /* @__PURE__ */ new Set();
  for (const { gen } of segments) if (gen && unmodelled(gen)) dynamicWords.add(gen);
  const cellOf = (chain) => {
    for (let at = chain; at; at = at.up)
      if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
    return null;
  };
  const parts = [];
  const starts = [];
  const positions = /* @__PURE__ */ new WeakMap();
  const fences = /* @__PURE__ */ new Set();
  let length = 0;
  let previousCell = null;
  segments.forEach((seg, k) => {
    const cell = cellOf(cellChains[k]);
    if (k === 0) {
      if (cell) fences.add(0);
    } else {
      if (cell !== previousCell && (cell || previousCell)) fences.add(length);
      parts.push(seg.breakBefore ? " " : EDGE);
      length += 1;
    }
    starts.push(length);
    positions.set(seg.node, length - seg.start);
    parts.push(seg.node.data);
    length += seg.end - seg.start;
    previousCell = cell;
  });
  if (previousCell) fences.add(length);
  return {
    raw: parts.join(""),
    starts,
    positions,
    fences: [...fences].sort((a, b) => a - b),
    segments
  };
}
function pageBlocks() {
  const text = pageText();
  if (!text.blocks) {
    const seen = /* @__PURE__ */ new Set();
    text.blocks = text.segments.map(({ block }) => block).filter((block) => block && !seen.has(block) && seen.add(block));
  }
  return text.blocks;
}
function spanIn(reading2, segments) {
  const first = segments[0];
  const last = segments.at(-1);
  const start = first ? reading2.positions.get(first.node) + first.start : 0;
  return [start, last ? reading2.positions.get(last.node) + last.end : start];
}
var escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
var LEAD_CAP = 400;
function confirmRest(raw, at, words) {
  let i = at;
  for (const w of words) {
    const gap = i;
    while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw[i]))) i++;
    if (i === gap) return -1;
    for (const ch of w) {
      while (raw[i] === EDGE) i++;
      if (!raw.startsWith(ch, i)) return -1;
      i += ch.length;
    }
  }
  return i;
}
var withinCell = (text, from, to) => !text.fences.some((fence) => from < fence && fence < to);
function findQuote(text, quote, anchor, within) {
  const { raw } = text;
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const lead = [];
  for (let spent = 0; words.length > lead.length; ) {
    const next = words[lead.length];
    if (lead.length && spent + next.length > LEAD_CAP) break;
    lead.push(next);
    spent += next.length + 1;
  }
  const rest = words.slice(lead.length);
  const pattern = new RegExp(
    lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
    "g"
  );
  const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
  const candidates = [];
  const exact = [];
  for (const at of raw.matchAll(pattern)) {
    const stop = confirmRest(raw, at.index + at[0].length, rest);
    if (stop === -1 || !withinCell(text, at.index, stop)) continue;
    if (within && !(under(pointAt(text, at.index).node, within) && under(pointAt(text, stop - 1).node, within)))
      continue;
    const hit = { from: at.index, to: stop };
    candidates.push(hit);
    if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false))
      exact.push(hit);
  }
  const found = exact.length === 1 ? exact[0] : exact.length === 0 && candidates.length === 1 ? candidates[0] : null;
  return found ? spanOf(text, found.from, found.to) : [];
}
function findText(text, query) {
  const words = query.trim().split(/\s+/u).filter(Boolean);
  if (!words.length) return [];
  const pattern = new RegExp(
    words.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
    "giu"
  );
  const out = [];
  for (const match of text.raw.matchAll(pattern)) {
    const from = match.index;
    const to = from + match[0].length;
    if (!withinCell(text, from, to)) continue;
    out.push(spanOf(text, from, to));
  }
  return out;
}
function contextAround(text, segments, { before = 28, after = 28 } = {}) {
  const [start, end] = spanIn(text, segments);
  function side(at, length, backwards) {
    if (!length) return "";
    const budget = length * 2 + 1;
    const neighbourhoodPoints = [...neighbourhood(text, at, budget, backwards)];
    const points = backwards ? neighbourhoodPoints.slice(-budget) : neighbourhoodPoints.slice(0, budget);
    const context = points.join("");
    const boundary = backwards ? points.slice(0, Math.max(0, points.length - length)).join("").length : points.slice(0, length).join("").length;
    const word = textUnits.segment(context).containing(backwards ? boundary : boundary - 1);
    const outer = word?.isWordLike ? backwards ? word.index : word.index + word.segment.length : boundary;
    const reachesEdge = backwards ? outer === 0 : outer === context.length;
    if (reachesEdge && points.length >= budget) {
      const excerpt = excerptWords(
        backwards ? points.toReversed().join("") : context,
        length
      ).slice(0, -1);
      return backwards ? [...excerpt].toReversed().join("") : excerpt;
    }
    return (backwards ? context.slice(outer) : context.slice(0, outer)).trim();
  }
  return { before: side(start, before, true), after: side(end, after, false) };
}
function pageParts(sel) {
  return pageQueryAll(sel).filter((el) => !inChrome(el));
}

export {
  COLLAPSE,
  TEXT_BLOCK,
  CONTEXT,
  textUnits,
  sentenceUnits,
  alignText,
  alignInlineText,
  labelWords,
  excerptWords,
  verbatimOwnerIdentity,
  verbatimBoundaryIdentity,
  renderRetired,
  settledAway,
  DATUM,
  inChrome,
  showsWords,
  leafSurface,
  pageWords,
  elementOver,
  fileModelsPassage,
  authored,
  textNodesUnder,
  closestAcross,
  elementById,
  pageDocument,
  authoredScope,
  elementFromPointAcross,
  pageQueryAll,
  pageRange,
  selectEnds,
  programmaticSelection,
  selectionBackward,
  segmentsIn,
  blockAt,
  segmentBlock,
  quoteFrom,
  readingFrom,
  cut,
  says,
  wrote,
  rangeOf,
  pointAt,
  neighbourhood,
  pageReadingVersion,
  watchPassageRoot,
  fencePassageParts,
  pageText,
  elementReading,
  pageBlocks,
  spanIn,
  findQuote,
  findText,
  contextAround,
  pageParts
};
