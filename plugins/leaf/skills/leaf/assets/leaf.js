/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: one module
 * owning both the widget layer and the comment layer.
 *
 * Widget layer: reads /registry.json (vendored per page) and dynamically imports one
 * module per tag marked x-upgrade — element-widgets need no JS at all; the theme's CSS
 * renders them. It also renders the attributes the registry marks x-says as real text
 * (renderSaid), for every widget alike: a word the page says has to be a word the
 * user can select. Upgrades flush before the first anchor pass, so comment quotes
 * always search the enhanced DOM. Widget modules import only the small helper surface
 * they need from here.
 *
 * Actions: an interactive widget (lf-board) reports the user editing the document
 * through it as an `action` event — sendAction posts it, `leaf wait` prints it,
 * and `leaf ack` records that the complete wait batch reached model context. The
 * live view is the version plus every action recorded up to it, replayed on each poll:
 * authored markup is what a widget was before anyone touched it, the log is every
 * transition since, and the log wins. A decision therefore outlives the version it
 * was made on, without the page's author having to copy it into the next one by
 * hand. When a version does mean to overrule one — the content the decision was
 * about got rewritten — `version check` makes the author say so (see restatement_errors in
 * interact.py); it is never inferred from the markup's silence. Widgets opt in via an
 * applyAction(action, detail) method stating an absolute value, so a reload keeps the
 * user's drag and a second tab follows along live.
 *
 * Comment layer: talks to interact.py's server — polls GET /api/state, posts events to
 * POST /api/event. Everything it injects is namespaced .lf-* and marked .lf-ui, and it
 * styles itself from the theme's tokens so it themes with the page.
 *
 * .lf-ui is the chrome face — the system-ui look that says "this is not the document" —
 * and it is anchoring's answer only where nothing nearer speaks. A label the widget
 * declares the page's own words (relabel's data-lf-said) is nearer, and wins: a heading
 * in a chrome-looking row and a tab's name inside its own strip button are both passages
 * a user can point at. Reading the class as the whole answer is what left a user
 * able to see a draft's heading and unable to comment on it. A widget's own label, note
 * or badge outside any control declares nothing at all: data-lf-gen alone keeps it out of
 * the diff and in reach of the anchor pass. CLAUDE.md carries why.
 *
 * Paper reads both: a control a widget injected (data-lf-offer) has nothing on paper to
 * be pressed, so it goes, unless its own label is one of the page's words. Keying print
 * on .lf-ui instead cost a printed decision the only words that stated it (see
 * CLAUDE.md), because a pick mark is a control and a statement at once. render_version
 * compares the two media and reports what a page says on screen and not on paper.
 *
 * A control that says one of the page's words is never a <button>: Chrome starts no
 * pointer selection inside a form control, so its label would be unreachable however it is
 * marked. `offer` builds every press as a span wearing role="button" for that reason, and
 * wires the keys the UA would have given it.
 *
 * Passages and anchors: a comment points at an anchor (a section id, a quote, and the
 * neighbouring words where there are any). resolveAnchor is the only place the page is
 * searched and paintAnchors the only place it is marked; CLAUDE.md carries why.
 *
 * Never lose user text (CLAUDE.md): every unsent draft — the general box, each per-thread
 * reply, the selection composer (text + its anchor), a widget's box for words, and an
 * in-place draft edit — persists to the reader's own store (draftStore) on input. It
 * survives reload, version navigation and the close of the tab it was typed in, and every
 * tab open on the page shows one copy of it: a keystroke lands in the store and the
 * store's own event carries it to the rest (watchDraft), so a draft cleared by a send in
 * one tab arrives in the others as a box that has sent rather than as words gone missing.
 * A draft's attempt follows every request into the append-locked log. Two tabs may POST
 * the same generation together, but both receive the one event that attempt identifies;
 * a retry after a sender dies returns it too. Cleanup tombstones only that generation, so
 * a later edit remains. The same path serves general and selection comments, question
 * messages and replies, and lf-draft actions.
 *
 * Versions: an unpinned page follows the newest version, navigating to each revision as
 * Claude ships it. Picking an older version pins the view (?pin in the URL); a pinned
 * page stays put and offers the newest version as a chip instead. One control on the bar
 * holds all of it — the version being read, the list of the rest with what each changed,
 * and the press on any older one that marks that change on the page.
 *
 * Composing: every textarea behaves identically — saves its draft on each keystroke,
 * sends on ⌘/Ctrl+Enter — because they are all wired through wireInput. Growing with
 * its content is the stylesheet's job: `field-sizing: content` on the one text-box rule,
 * which a widget's own box opts into by wearing `lf-ui`. No script measures a textarea,
 * so none can leave one momentarily too small for its own text — the shape of bug that
 * flashes a scrollbar per keystroke. The thread list is reconciled, never rebuilt: a
 * poll adds what arrived and touches nothing the user already holds, so scroll,
 * focus and caret keep themselves because the nodes holding them survive. News moves
 * nothing; a send reveals the message it just landed — the panel scrolls to it and
 * flashes its thread, the same answer a click on a page mark gets — and ends in the
 * composer it was sent from. A composer open on a selection keeps that passage marked
 * in the page until it closes, because focusing the box drops the browser's own
 * selection — and that mark is what says which passage the box is on, so the box only
 * quotes the passage back when this version no longer has one to mark. Whether the box
 * is up is state the stylesheet renders, never state read back off the stylesheet.
 *
 * Scrolling: the document scrolls body, not the viewport, and body's margin keeps its
 * box clear of the open panel. Two scroll regions side by side, each scrollbar drawn
 * inside its own region — a viewport-scrolled document would paint its scrollbar over
 * the panel, stacked on the panel's own. Reading position goes through pageScroller.
 * The browser's own scroll keys are left alone (Space, arrows, Home/End, PageUp/Down);
 * d and u are the runtime's, stepping half the visible page at the browser's own paging
 * pace through whichever of the two regions the reader's own scrolling moves.
 *
 * Keyboard: one register, and every surface is a projection of it. A row binds keys and
 * says what pressing one does; a scope is where the keyboard means something particular,
 * and scopes nest. One dispatcher walks the stack innermost-first, so a focused control's
 * keys shadow the page's without either knowing about the other, and `only` stops the walk
 * where a scope owns the keyboard whole — a box words are typed into, the reference
 * overlay. The register is the only way a key enters the runtime: `keys(el, title, rows)`
 * is what a widget calls, and the dispatcher it feeds is the layer's one keydown listener
 * bar the aim chord's modifier latch. The full vocabulary — what a row's cells mean, and
 * how a scope's `when` differs from a row's — is written where the register is defined.
 *
 * One key sequence exists: g arms a mode in which a letter names one of the page's
 * lists — its comments, its asks, its links — and a digit is a place in that list,
 * so `g c 2` is the second reply box and `g l 3` the third link on screen. Which lists
 * there are is one table (ADDRESSES) and no consumer branches on which one is aimed at.
 * Each member of the named list wears its digit as a chip while the window stands, and any
 * other key disarms it and keeps its ordinary meaning, which the dispatcher spells as
 * disarming and walking the stack again. Escape is a binding like any other, and the rung
 * is whichever scope in reach binds it first, so backing out is one layer per press and
 * the promise cannot drift from the press.
 *
 * What a key would do right now is state the user can read, not recall. The key line (one
 * quiet fixed line, bottom left) renders the stack outward and drops what the room cannot
 * hold, `?` last and always, so what a narrow window costs is the page's keys and what it
 * keeps is the scope the reader stands in. The "?" overlay names every scope the page has,
 * live rows only. The line is aria-hidden: it is the eye's copy of facts spoken elsewhere
 * — placeholders speak each box's address, announce() speaks each stage of the chord and a
 * grabbed card's keys, the overlay speaks the whole reference.
 *
 * A message arrives as logged and renders here, in the same vendored layer that owns
 * the panel's styles — the two version together, and no wire vocabulary exists beyond
 * the log's own. Its text is Markdown, rendered with every raw tag escaped to the
 * characters it was written in, so prose that says `Vec<T>` keeps its own words and
 * text cannot inject markup. A widget rides the event's `markup` field instead, whose
 * one door is the CLI gate (`leaf comment`/`leaf reply` validate it against the
 * vendored registry; the browser door refuses the field), so what lands here is
 * injected as validated. A suggestion's text renders verbatim: its characters are
 * bound for the page as typed.
 *
 * A fragment link in a message ([the group](#d-channel)) points at an element of the
 * page, and the browser's own navigation is the travel — collapsed content wears
 * hidden="until-found", so the jump opens the tab or settled group holding it. The
 * runtime adds only the half the platform has no answer for: a comment outlives the
 * version it was written on, so a reference to an id this one hasn't got wears the
 * detached face a stranded quote wears, and its press is refused (paintAnchors). */

// ---------- widget layer ----------

let agent = "Claude";
export const agentName = () => agent;

// Attributes the runtime itself may paint onto elements the page owns. This is the
// replay signature's one exclusion vocabulary as well as the source each writer uses:
// a new kind of paint therefore has one place to join. The rest of data-lf-* is not
// implicitly ours — a widget can carry real state there, and replay must see it. The
// settlement mark (data-lf-state) is deliberately in that rest: the layer paints it
// (markSettled), but a module may paint it too as its own gesture's state, and the
// replay signature must keep seeing it — its own gate is RETIRED_SLOTS, not the sigs.
const PAGE_PAINT_ATTRIBUTE = Object.freeze({
  class: "class",
  ask: "data-lf-ask",
  done: "data-lf-done",
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  replayWrote: "data-lf-replay-wrote",
  reportWrote: "data-lf-report-wrote",
  applied: "data-lf-applied",
  pending: "data-lf-pending",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  wide: "data-lf-wide",
});
const PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));

// A modal is promoted into the top layer and makes the rest of the document inert. Both
// facts escape an ancestor paint gate: hiding it with CSS alone would still disable the
// Comments chrome that deliberately remains usable while first replay waits. Custom
// widgets load after this module, so turn authored-main showModal() calls into measurable,
// non-modal dialogs until replay has produced the page. A widget can still close one
// while waiting; only a connected, still-open dialog whose post-replay place is visible
// is promoted, so replay retiring its authored branch cannot resurrect stale UI on top.
const nativeDialogShow = HTMLDialogElement.prototype.show;
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativeDialogClose = HTMLDialogElement.prototype.close;
const deferredModals = new Set();
const inAuthoredMain = (node) => {
  const main = document.querySelector("body > main");
  for (let at = node; at;) {
    if (at === main) return true;
    if (at.parentElement) at = at.parentElement;
    else {
      const root = at.getRootNode();
      at = root instanceof ShadowRoot ? root.host : null;
    }
  }
  return false;
};
HTMLDialogElement.prototype.showModal = function () {
  if (
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) &&
    inAuthoredMain(this)
  ) {
    if (!this.open) nativeDialogShow.call(this);
    deferredModals.add(this);
    return;
  }
  return nativeDialogShowModal.call(this);
};
HTMLDialogElement.prototype.show = function () {
  deferredModals.delete(this);
  return nativeDialogShow.call(this);
};
HTMLDialogElement.prototype.close = function (returnValue) {
  deferredModals.delete(this);
  return nativeDialogClose.call(this, returnValue);
};
function promoteDeferredModals() {
  for (const dialog of deferredModals) {
    if (
      !dialog.isConnected ||
      !dialog.open ||
      !inAuthoredMain(dialog) ||
      !dialog.checkVisibility({ opacityProperty: true, visibilityProperty: true })
    ) {
      dialog.removeAttribute("open");
      continue;
    }
    // Removing the non-modal state directly emits no spurious close event; the widget
    // asked for one opening, and this is that opening finally becoming modal.
    dialog.removeAttribute("open");
    nativeDialogShowModal.call(dialog);
  }
  deferredModals.clear();
}
// One-shot guard for connectedCallback: re-connection (a parent wrapping or moving an
// already-upgraded child) must be harmless, so upgrade order can't matter.
export function once(el) {
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) return false;
  el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
  return true;
}

// A data widget's body: the <pre> the content model requires, never the element's own
// textContent. The two used to be the same string and are not once the element holds a
// child — an HTML formatter is free to put the <pre> on its own line, and the newline
// and indent before it are the element's text too. Line one is load-bearing in every
// notation here, so that indent is not untidiness downstream: a diff's file header, a
// tree's root and mermaid's graph type stop parsing, and a walkthrough's `hi` ranges
// and note anchors all point one line off.
export const dataBody = (el) => el.querySelector(":scope > pre").textContent;

// A failed upgrade becomes a visible error box rather than a blank page.
export function failSoft(el, err, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = `<${el.tagName.toLowerCase()}> failed: ${err?.message || err}`;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  el.replaceChildren(box);
}

// The page's one door to the log, spelled once. Two callers reach it — `post`, which
// orders the reader's own gestures through it, and the error report below, which
// deliberately doesn't — and what they share is the request rather than anything about
// the sending: same path, same method, same encoding, so a door that moved would move
// for both. Whether a send waits on the one before it belongs to the caller.
const vendoredLayerGeneration = "__LEAF_LAYER_GENERATION__";
let layerGeneration = vendoredLayerGeneration;
let revealLayer;
const layerReady = new Promise((resolve) => (revealLayer = resolve));
let layerReloading = false;
function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  if (!layerReloading) {
    layerReloading = true;
    location.reload();
  }
  return false;
}

const postEvent = async (event) => {
  await layerReady;
  const response = await fetch("/api/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Leaf-Layer": layerGeneration,
    },
    body: JSON.stringify(event),
  });
  const responseGeneration = response.headers.get("Leaf-Layer");
  if (response.ok && responseGeneration && !sameLayer(responseGeneration)) return null;
  return response;
};

// The page reporting itself broken, to the party who can fix it: the agent
// authored the page and its widgets, and before this the only route for a
// live-session fault was the reader pasting a console nobody told them to
// open. The event lands in the log as kind "error", author "page" — the
// watcher hears it beside comments and reports; the reader's pending count
// never claims it. Deduped per message per load (a reload may repeat one —
// bounded noise over silence), capped so a fault in a loop cannot flood the
// log, and sent bare rather than through post(): a poll fault reporting
// itself through the poll would recurse, and nothing here needs the answer.
// Not part of the helper surface a module gets: an upgrade that throws is already on
// this path through window.error, and a widget that wants to say so itself has
// failSoft, which puts the message where the reader is looking.
const reportedErrors = new Set();
function reportPageError(text) {
  console.error(`leaf: ${text}`);
  if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
  reportedErrors.add(text);
  postEvent({
    kind: "error",
    text,
    ...(VNUM != null && { version: VNUM }),
  }).catch(() => {});
}
window.addEventListener("error", (e) => {
  // Chrome also puts ResizeObserver loop notices on window.error without an
  // exception. This one live page cannot tell an occasional scheduling notice
  // from a layout feedback loop, so it persists neither in the reader's log. The
  // render gate and test navigation take one complete confirming reading and
  // report a notice that recurs there.
  if (e.message?.startsWith("ResizeObserver loop")) return;
  reportPageError(`${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) =>
  reportPageError(String(e.reason?.stack ?? e.reason)),
);

// An upgrade whose work is async (lf-diagram's mermaid render) registers its
// promise here, so the runtime can hold the view restore and first anchor pass
// until the page's geometry has settled. Rejections are the widget's own
// fail-soft path; settling ignores them.
const settling = [];
export function settle(promise) {
  settling.push(promise);
}

// ---------- where a page's versions are ----------
// A page directory's versions are served as siblings under its own root:
// versions/v1.html, v2.html… Three things read that path — which version this document
// is, where another version of it is, and which page a tab's working state belongs
// to — so the shape is spelled once here rather than three times, and a document served
// under a directory of its own cannot have one of them agreeing with its URL while the
// next two contradict it.
const VERSION_PATH = /\/versions\/v([1-9]\d*)\.html$/;
// Where another version is: beside this one. It was "/versions/vN.html" at the three
// seats that travel, which is a claim about where the page directory sits — true of a
// server serving one page at a root of its own, and of nothing else. The published site
// serves every example from one vendored layer with each page under its own directory,
// and there each absolute jump left the page for a root that serves nothing. Resolved
// against the document, the travel agrees with the path the version number itself was
// read off, which is the one form that cannot disagree with what this document is.
const versionUrl = (version) => `v${version}.html`;
// Which page this document belongs to, as a prefix for what the tab keeps: "" wherever a
// server serves one page at its own root, so every key below is spelled exactly as it was.
// Two leaf pages on one origin is what needs it — web storage is the origin's, so the
// reading position a reader left on one example was handed back on the next, at an offset
// that meant nothing there.
const PAGE_SCOPE = location.pathname.replace(VERSION_PATH, "");

// ---------- what the page keeps, and what a store may refuse ----------
// Reading or writing web storage throws outright where the browser has it switched off —
// a locked-down profile, a private window on some engines — and nothing kept here is
// worth breaking the page for: a reader who cannot save which tab they were on still
// gets the page. Said once, because a policy spelled at each caller is a policy free to
// be spelled differently at the next one, and eleven of them had accumulated across the
// runtime and two widget modules.
//
// Which store is the part worth reading at a call site, and naming them is what puts it
// there. `tabStore` is this window's working state and dies with the tab — the reading
// position, which panel of a widget stands open, whether design mode is on — because each
// of those is about the window rather than about the page. `draftStore` is what the user
// typed and hasn't sent: it outlives the tab, because closing one is the ordinary end of
// a tab here, and every tab shows one live copy of it (see the draft section below).
// `readerStore` is this reader's standing preference across pages, which is the chrome
// they arrange and expect to find arranged. Anything two tabs must *agree* about is none
// of the three: it goes in the log.
//
// Values are the store's own vocabulary, strings and null, so nothing here has an
// opinion about encoding: an absent key reads back as null, and writing null removes it.
const stored = (backing, scope = "") => ({
  read(key) {
    try {
      return { available: true, value: backing.getItem(scope + key) };
    } catch {
      return { available: false, value: null };
    }
  },
  get(key) {
    return this.read(key).value;
  },
  set(key, value) {
    try {
      if (value === null) backing.removeItem(scope + key);
      else backing.setItem(scope + key, value);
      return true;
    } catch {
      /* a page that cannot remember still renders */
      return false;
    }
  },
  // Where this store puts a key, as the platform's own two names for its stores plus
  // the key the backing actually holds. Only the browser gate asks: it seeds a store
  // before the page has run, so it cannot ask a store that does not exist yet, and the
  // alternative is a second copy of the scope rule kept over there to go stale.
  where(key) {
    return {
      store: backing === sessionStorage ? "session" : "local",
      key: scope + key,
    };
  },
  // What this scope holds, spelled as the callers spell it. The drafts are what needs
  // it: a composer's key is the passage it is on, so which draft to reopen at load is a
  // question about the set rather than about a key someone already knows.
  keys() {
    try {
      return Object.keys(backing)
        .filter((key) => key.startsWith(scope))
        .map((key) => key.slice(scope.length));
    } catch {
      return [];
    }
  },
});
// Two of the three are scoped to the page (PAGE_SCOPE), and the odd one out is the reason
// there are three backings: what the reader arranges is theirs wherever they are reading,
// while what they typed here belongs to this page. tabStore is the only one on the helper
// surface, because only widgets keep working state (lf-tabs' open panel, lf-options'
// collapsed group) — a module reaches its drafts through saveDraft/watchDraft, the chrome
// the reader arranges is the runtime's own, and an export nothing imports is a promise
// nobody asked for.
export const tabStore = stored(sessionStorage, PAGE_SCOPE);
const draftStore = stored(localStorage, PAGE_SCOPE);
const readerStore = stored(localStorage);

// ---------- syntax ----------
// Code is colored in the browser, at upgrade, and the spans land in the DOM — which is
// what makes one answer serve the served page and the standalone one, where the script
// is gone and only markup and CSS remain. Colouring it in Python instead would put the
// spans in the file, and the file is what Claude writes the next version from.
//
// What a page ends up wearing is leaf's own vocabulary, not the tokenizer's: six
// roles on one data-lf-syn attribute, styled from --syn-* like every other surface, so
// both color schemes come from the same token block the rest of the theme uses. The
// bundle's ~50 scopes collapse here, at the one place that knows both — a page that
// carried hljs-* classes would have pinned that library into every version ever written.
// Anything unmapped keeps the block's ink, so a scope this table forgets reads plain
// rather than reading wrong.
// Every key is a scope one of the bundled grammars actually emits; operator, punctuation,
// emphasis and strong are left out on purpose, because a block reads calmer with its
// syntax uncoloured and its prose unstyled.
// A line per role rather than per scope, so the collapse is what the table shows.
// prettier-ignore
const SYNTAX_ROLE = {
  comment: "cm", quote: "cm", doctag: "cm",
  keyword: "kw", literal: "kw", built_in: "kw", type: "kw", bullet: "kw",
  string: "st", regexp: "st", "char": "st", subst: "st", "template-variable": "st",
  code: "st", link: "st",
  number: "nu",
  title: "fn", meta: "fn", section: "fn",
  name: "ty", tag: "ty", attr: "ty", attribute: "ty", property: "ty", variable: "ty",
  params: "ty", symbol: "ty", "selector-tag": "ty", "selector-id": "ty",
  "selector-class": "ty", "selector-attr": "ty", "selector-pseudo": "ty",
  addition: "ins", deletion: "del",
};

let hljsReady;
// Lazily, once, and only on a page that has code to color: the bundle is 75 KB and most
// pages have none.
const loadHljs = () =>
  (hljsReady ??= import("/vendor/highlight.esm.js").then((m) => m.default));

// Code as [{text, role}] — a flat run in source order, roles from the table above and
// null where the block's own ink is the answer. A list rather than markup because the two
// callers build different DOM from it: a plain <pre> emits one span per token, lf-code
// interleaves the line spans it numbers. A declared language is validated by `version check` against the
// registry's $languages.names, so an unknown one here means the vendored bundle was built
// from a different list — thrown, caught by the caller's failSoft, and reported by the
// render gate, which fails on a console error.
export async function syntax(source, lang) {
  const hljs = await loadHljs();
  if (!hljs.getLanguage(lang))
    throw new Error(
      `no ${lang} in /vendor/highlight.esm.js — rebuild it from registry.json's $languages.names`,
    );
  const holder = document.createElement("template");
  holder.innerHTML = hljs.highlight(source, {
    language: lang,
    ignoreIllegals: true,
  }).value;
  const tokens = [];
  const walk = (node, role) => {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) tokens.push({ text: child.data, role });
      // Scopes nest (an html tag holds its own name and attrs); the innermost that this
      // table knows wins, and one it doesn't inherits rather than clearing.
      else walk(child, roleOf(child) ?? role);
    }
  };
  walk(holder.content, null);
  // The vendored tokenizer's output is data entering, so it is checked once, here, and
  // indexed everywhere after: that the tokens partition the source exactly. Three things
  // rest on it — lf-code numbers its lines by counting newlines in them, `hi` and each
  // note's `at` address those numbers, and the anchor pass reads the spans as the text
  // the file holds — and a dropped character slides all three with nothing on screen
  // saying so. Failing here fails the block soft to its plain source, and the console
  // error fails the render gate, which is what puts it in front of whoever can drop the
  // language declaration.
  if (tokens.map((t) => t.text).join("") !== source)
    throw new Error(`the ${lang} tokenizer did not return the source unchanged`);
  return tokens;
}

// hljs writes `class="hljs-title function_"`: the scope prefixed, then its sub-scopes bare.
// Only the prefixed one is a scope name, and `char.escape` arrives as `hljs-char escape_`.
const roleOf = (el) => {
  for (const cls of el.classList)
    if (cls.startsWith("hljs-")) return SYNTAX_ROLE[cls.slice(5)];
  return undefined;
};

// Tokens as nodes: one span per role, and the bare text where none applies, so nothing
// lands in the DOM that says nothing. Both callers build from here — a <pre> replacing its
// own children, lf-code appending into the line it is numbering — because a second place
// writing the same span is a second place to forget the attribute.
export const synNodes = (tokens) =>
  tokens.map(({ text, role }) => {
    if (!role) return document.createTextNode(text);
    const span = document.createElement("span");
    span.dataset.lfSyn = role;
    span.textContent = text;
    return span;
  });

// Tokens re-cut so none crosses a newline: one array of {text, role} per line, in source
// order. The tokenizer's runs and a line are two different spans of the same characters,
// and this is where they are reconciled — for lf-code, whose lines are what it numbers,
// and for lf-diff, whose lines are what it tints. Both tokenize a whole run and cut it
// afterwards rather than colouring a line at a time, because a token can span a newline:
// a docstring coloured line by line restarts the tokenizer inside itself and reads its
// second line as code.
export function tokenLines(tokens) {
  const lines = [[]];
  for (const { text, role } of tokens) {
    const parts = text.split("\n");
    parts.forEach((part, i) => {
      if (i) lines.push([]);
      if (part) lines.at(-1).push({ text: part, role });
    });
  }
  return lines;
}

// What a filename says it holds, or undefined where the registry's table has no answer
// and the block stays the colour of its own ink. The only place a language is derived
// rather than declared: a unified diff spans files, so lf-diff has no `language` to read and
// each file's path is the diff's own statement about what it is. Still a declaration —
// the rule that nothing is inferred is about source *text*, which no path is. The table
// is the registry's ($languages), beside the enum it has to agree with, rather than a
// second list here.
export const langForPath = (path) =>
  registry.$languages.paths[
    path.split("/").pop().split(".").slice(1).pop()?.toLowerCase()
  ];

// The page's own code blocks: <pre><code class="language-python">. The class is the
// universal one — what every Markdown renderer emits, and what `version check` validates — so a
// block Claude wrote anywhere else needs no translation to land here. lf-code declares
// `language` instead, because a custom element's vocabulary is the registry's to state.
//
// The spans change no text: a <span> is no text block, so the anchor pass reads exactly
// the run of characters it read before. That is what lets this run over the document
// without the file's reading of the same page needing to know it happened.
const LANGUAGE_CLASS = /(?:^|\s)language-([\w+.#-]+)(?=\s|$)/;
async function highlightBlocks(root) {
  const blocks = [];
  for (const code of root.querySelectorAll("pre > code[class]")) {
    const lang = code.className.match(LANGUAGE_CLASS)?.[1];
    if (lang) blocks.push([code, lang]);
  }
  if (!blocks.length) return;
  for (const [code, lang] of blocks) {
    try {
      code.replaceChildren(...synNodes(await syntax(code.textContent, lang)));
    } catch (err) {
      console.error(
        `leaf: <pre><code class="language-${lang}"> failed to highlight`,
        err,
      );
    }
  }
}

// The theme's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS — smooth scrolls here, Web-Animations moves in widgets — checks
// this instead.
export const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
export const SCROLL = REDUCED ? "instant" : "smooth";

// Web-Animations motion goes through here, so a reader who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. The board's FLIP and the folds (FOLD_MS) are the motions the product makes;
// they share one ease and one held-end-frame contract.
export function motion(el, keyframes, ms) {
  // First replay happens behind the presentation boundary. Its state should be the
  // first frame the reader sees, not a motion from authored state they never saw; it
  // collapses exactly as reduced motion does. This one shared check reaches folds and
  // FLIP alike without a widget learning whether the page has been presented.
  if (REDUCED || !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented))
    return null;
  const played = el.animate(keyframes, {
    duration: ms,
    easing: "ease",
    fill: "forwards",
  });
  // Hold the last frame until the caller's direct `finished.then(cleanup)` has made
  // that frame true in DOM/CSS, then release the effect. The extra microtask is the
  // ordering: our reaction was registered first, so cancelling in it would expose the
  // unanimated box before the caller removed, hid or restated it. A FLIP has no cleanup
  // because its underlying placement already is its last frame; it still leaves no
  // filled animation behind. Cancellation is already the release, and the rejection
  // arm consumes it so an interrupted move reports no unhandled promise.
  played.finished.then(
    () => queueMicrotask(() => played.cancel()),
    () => {},
  );
  return played;
}

// How long room takes to go back. Long enough that the eye can follow a paragraph's
// worth of page closing, short enough that the act still reads as having happened at
// the press: the board's own FLIP is 150ms over a card's width, and this is a taller
// distance travelled by the whole column below it. One number, because the product
// makes this motion twice for one reason — a decided suggestion's retired slot and a
// resolved thread's place in the list are both room the reader watches come back —
// and two numbers would be that reason written down twice, free to disagree.
export const FOLD_MS = 220;

// Mention, not use: a widget inside one the registry marks x-exhibit is quoted
// material. An interactive widget consults this before wiring anything that would carry
// input back (a choose path, a drag grip), so an exhibit never takes the user's edits.
// Presentational upgrades and view state run regardless — a quoted diagram still
// renders, a quoted settled group still collapses.
export function quoted(el) {
  const exhibits = tagsDeclaring((entry) => entry["x-exhibit"]);
  return exhibits.length > 0 && el.closest(exhibits.join(",")) !== null;
}

// What a page's own markup works: a link to follow, a control to set, a disclosure to
// open, a player to start. HTML's interactive content is where this comes from rather
// than a list anyone here may add to, and it differs in two places, both about whether a
// click can arrive. `summary` stands for `details`, because only the summary is the press
// and the body under it is prose the reader may point at like any other. And nothing
// embedded (`iframe`, `embed`, `object`): a click inside one never crosses into this
// document, so listing them would guard a gesture no listener out here can see.
const WORKS = "a, audio, button, input, label, select, summary, textarea, video";

// A container that takes a gesture on its whole box has to tell one aimed at itself from
// one aimed at what it holds. This is the second: the nearest thing between `node` and
// `container` that has a use for the gesture, or null where the container is the aim.
//
// It exists because an option's case is now argued inside the option — a screenshot pair
// to flip, a disclosure to open, tabs to walk — while the whole card is what takes the
// pick. Reading the evidence then cast a vote: a click on a tab chose that option, and one
// on a shot's `after` radio chose it and cleared it again, two decisions the reader never
// made and only the log to show for them. Fail closed, because a pick is sent the moment
// it is made: a gesture nobody can prove was a choice is not one.
//
// Two vocabularies, because a container holds two kinds of thing. A widget it merely
// contains is its own world, and that is every lf-* tag bar the parts the registry says
// this container is made of (x-parent) — declared rather than listed, so the twelfth
// widget is covered by its entry and a widget whose gesture lands on its own words rather
// than on chrome (lf-draft's double-click) is covered with the rest. Inert ones go in with
// them: a diagram is evidence the reader studies with the pointer on it, and which
// evidence happens to carry a control is nothing they can see.
//
// `data-lf-offer` then catches the controls that belong to no widget — the runtime's own
// hidden line saying how many comments a block holds, which a screen reader reaches by
// Tab and which used to cast a vote on the way into the thread. It catches the container's
// own apparatus too, which no rule here could tell from the rest; a container excludes
// its own, being the only thing that can name them.
export function worksInside(node, container) {
  // The closure, not one level: "what this container is made of" includes a
  // part's own parts — a column's cards are the board's, and one level deep a
  // grandchild part would land in `held` and swallow the gesture.
  const parts = new Set([container.localName]);
  for (let grew = true; grew;) {
    grew = false;
    for (const tag of tagsDeclaring((entry) =>
      (entry["x-parent"] ?? []).some((parent) => parts.has(parent)),
    ))
      if (!parts.has(tag)) {
        parts.add(tag);
        grew = true;
      }
  }
  const held = tagsDeclaring(() => true).filter((tag) => !parts.has(tag));
  // `closest` walks past the container to the root, so a match has to be read back
  // against it: an ordinary pick on an option's prose finds the enclosing group, which
  // is a widget the option does not hold but is above it rather than inside it. And
  // `contains` counts an element as containing itself, so the container is ruled out by
  // name — the question is what stands between the two, and a container that is itself
  // a thing to work would otherwise answer with itself and never take a gesture again.
  const inner = node.closest([...held, WORKS, "[data-lf-offer]"].join(","));
  return inner && inner !== container && container.contains(inner) ? inner : null;
}

// The chrome a widget injects: a control, or the box that holds controls. Three
// markers, one per question asked of it — `lf-ui` for the runtime's look, which
// anchoring reads where no label speaks nearer; `data-lf-gen` so the diff looks away; `data-lf-offer`
// for a thing to work, which paper drops because there is nothing there to press.
// A widget writes none of the three by hand: they are what make an element chrome,
// and one of them going missing is invisible until something breaks.
//
// "button" names a thing to press, not the element. A real <button> is a wall a
// pointer's selection cannot cross — Chrome starts no selection inside a form
// control and `user-select: text` does not move it — so any word inside one is
// unreachable to a user whatever it is marked, and a control's label turns out
// to be one of the page's own words often enough (a tab's name, the card a settled
// group carries, the mark on a chosen option) that a widget cannot be trusted to
// have picked the element with that in mind. So a press is a span wearing the role,
// and the keys the UA would have supplied are wired once below. Nothing these controls
// do needed the element: no forms, no submit, and no `disabled` — which a widget's press
// therefore cannot have (the .lf-btn:disabled rule is the runtime's own buttons').
export function offer(tag, cls, label) {
  const press = tag === "button";
  const node = document.createElement(press ? "span" : tag);
  if (press) {
    node.setAttribute("role", "button");
    node.tabIndex = 0; // and the tabindex attribute is what says "a press" below
  }
  node.className = cls ? `${cls} lf-ui` : "lf-ui";
  node.dataset.lfGen = "1";
  node.dataset.lfOffer = "";
  if (label !== undefined) node.textContent = label;
  return node;
}

// The keys a <button> came with and a span does not — Enter and Space activate — are the
// CONTROL scope in the keyboard section below, one declaration covering every press any
// widget builds. It was a listener of its own, and the surfaces had no channel to it: the
// largest hole a survey of this runtime found was that Space activates nine classes of
// control across core and five widgets and only one of them ever said so. As a scope it is
// named once in the reference, and named on the line exactly while the reader stands on
// one — which is where the walk through the page's asks puts them.

// A drag that ends on a control is that selection's mouseup, not a press: the
// user was reaching for the words, and a control whose label is one of the
// page's own words is exactly where they reach. Here rather than in each widget,
// because `offer` is what made the thing pressable — the same reason the markers
// live there. A keyboard activation (detail 0) is never a drag.
//
// The question is whether *this* click's mouseup is where the selection stopped, so
// it reads the selection's focus end — the character the pointer was on when the
// button came up. Asking instead whether the selection contains the control is a
// question about the DOM, and it answers yes for any selection running over the
// control: a suggestion's row is the column's own child, in flow between the block
// holding the change and the next one, so a user who read across the change and
// then reached for Accept pressed a control that had gone dead — and stayed dead,
// because a press that refuses a drag (`user-select: none`) never collapses the
// selection that deadened it either.
document.addEventListener(
  "click",
  (ev) => {
    if (ev.detail === 0) return;
    const control = ev.target.closest?.("[data-lf-offer]");
    const sel = getSelection();
    if (control && sel && !sel.isCollapsed && control.contains(sel.focusNode)) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  },
  true,
);

// A control's label, and which kind of word it is. Most are things to do — "Save",
// "choose", a grip — and go with the rest of the UI on paper, out of reach of a
// quote. Some are the page speaking: a pick mark reading "chosen" is the only place
// the page says which option it carries, and a tab's name is the panel's only name
// once the strip exists. One element wears both over its life, so the kind is
// restated on every write rather than settled at birth.
//
// This writes one marker and one only: data-lf-said, the page speaking. Anchoring
// takes it over the `.lf-ui` box around it — that box is a look, the chrome face, and
// it was standing in for a permission the user has no category for — and paper
// reads it beside data-lf-offer to keep a control whose label is one of the page's own
// words. data-lf-gen goes on either way, because the diff parses the base version
// unupgraded and would read any label as text that version lacked.
//
// It leaves data-lf-offer alone, which it used to clear. That attribute is what `offer`
// made: this is a control a widget injected, true for the mark's whole life however it
// is worded, and three passes ask it (print, the drag guard above, the render gate).
// Clearing it here made "paper drops this" the meaning and left the other two unable to
// see a control — a drag across a picked card's mark was a press again, and only
// lf-options' own guard on the card stood between that and clearing the pick.
//
// `says` has no default, because the answer a caller doesn't give is the one that
// costs a printed page its words, and silently. Refusing throws where the widget
// upgrades, which the console reports and the render gate reads back as a finding
// — the loud direction, in front of whoever wrote the label.
export function relabel(node, label, { says } = {}) {
  if (typeof says !== "boolean")
    throw new TypeError(
      `relabel(${label}): say whether this label is the page speaking`,
    );
  node.textContent = label;
  node.dataset.lfGen = "1";
  node.toggleAttribute("data-lf-said", says);
}

// A word for a reader listening, silent on screen: real text — the one thing every
// screen reader announces in every mode — placed after the element's leading title,
// wearing .lf-ui (an invisible word is apparatus the anchor pass must not offer),
// .lf-quiet (the shared clip), and data-lf-gen (the diff looks away). One writer per
// element, and the empty word removes what stands: a fact the page has stopped painting
// must stop being said too, so a caller states the whole of what this element says
// quietly and never appends to it. lf-task and lf-milestone each hand-copied this idiom
// before it was one, and the copies had already diverged on whether a stale word was
// removed first — which is now renderQuiet's to state for every widget that declares it.
//
// Which writer an element gets follows from the declaration, and the two sets do not
// meet: renderQuiet has the elements the registry names (x-paints) and those the runtime
// paints a retraction on, and a module has only the parts it builds or the ones no
// declaration can reach — a suggestion's two slots, a code line. Declaring x-paints on a
// tag whose module also writes one here would leave both removing the other's word on
// every poll, which the reader would hear as the element re-reading itself.
export function quietWord(el, word) {
  const title = el.querySelector(":scope > strong");
  const seat = title ? title.nextSibling : el.firstChild;
  const standing = el.querySelector(":scope > .lf-quiet");
  if (standing) {
    // Nothing to say that isn't already said, in the place it belongs: a screen
    // reader rebuilds its buffer from the mutations, so a pass that finds the page
    // as it left it re-reads the element to whoever is on it for no reason. The seat
    // is part of that — a module that rebuilds its chip row between two runs of this
    // leaves the word standing behind it, and the fix is to move it, not to leave it
    // where the rebuild happened to put it.
    if (standing === seat && standing.textContent === word) return;
    standing.remove();
  }
  if (!word) return;
  const span = Object.assign(document.createElement("span"), {
    className: "lf-ui lf-quiet",
    textContent: word,
  });
  span.dataset.lfGen = "1";
  el.insertBefore(span, title ? title.nextSibling : el.firstChild);
}

// Room for a word not yet said, taken from the words themselves. A control that will
// rewrite its own label ("✓ Accept" to "✓ Accepted", a count gaining a digit) must
// hold the widest word's room from the start, or the press rewrites the one line a
// press may not move. Stating that room as a number is a measurement that stops
// being true silently when the words or the font change, so the control measures the
// words instead — in its own box and its own computed face, at load — and floors
// itself there. The two sweeps (a press, and the poll) stay the check that the words
// listed here are the words the writers actually write.
//
// Measured in place: text-only controls, swapped and restored synchronously, so no
// frame paints mid-swap. Stood out of flow for the moment — absolute, hidden — so a
// control whose news hasn't arrived yet (display: none) measures all the same and
// its neighbours don't feel the fitting. Sized by its words alone while it stands
// there, its own width cleared along with its place: a stated width can mean "and grow
// past this" in flow — a table cell laid out at `width: 0` takes what its content
// needs — where out of flow it is simply obeyed, and the widest word then measures as
// whatever padding the control has.
export function reserve(control, labels) {
  const stood = { text: control.textContent, css: control.style.cssText };
  Object.assign(control.style, {
    minWidth: "0",
    width: "auto",
    display: "inline-block",
    position: "absolute",
    visibility: "hidden",
  });
  let widest = 0;
  for (const label of labels) {
    control.textContent = label;
    widest = Math.max(widest, control.getBoundingClientRect().width);
  }
  control.textContent = stood.text;
  control.style.cssText = stood.css;
  control.style.minWidth = Math.ceil(widest) + "px";
}

// The element the document scrolls: body, not the viewport (see the stylesheet below,
// and Scrolling in the module header). Anything that reads a reading position, sets
// one, or hands a scroll container to a library uses this — window.scrollY is always 0
// here, and document.scrollingElement still names the html element, which no longer
// scrolls. Vendored libraries that resolve the scroller themselves are the trap:
// SortableJS walks up from the dragged card and, on reaching body, hands back
// document.scrollingElement, so lf-board passes this in rather than letting it guess.
export const pageScroller = document.body;

// A widget's report of the user editing the document through it (a card dragged
// between columns). The caller has already applied the edit to its own DOM; the
// poll's replay re-applies it once (see applyActions), which is why applyAction
// implementations must state an absolute placement, never a relative mutation.
//
// The outbox is the one representation of a gesture the page has made and the log has
// not authoritatively answered yet. It orders every user event, gives replay the widget
// ids it must leave alone, and tells undo/navigation whether any action is unresolved.
// A second pending map used to mirror part of the same lifecycle and then needed a
// protocol of its own to agree with the send queue and the polling loop.
const outbox = [];
const actionPending = (widget) =>
  outbox.some(
    (entry) =>
      entry.event.kind === "action" &&
      (widget === undefined || entry.event.widget === widget),
  );
export async function sendAction(el, action, detail, { attempt } = {}) {
  // The exhibit rule enforced at the layer's own door, not left to each module
  // remembering quoted(): an exhibited widget is a mention, and a gesture on a
  // mention must not become a decision Claude reads. Failing closed costs a
  // press that does nothing; the console error makes a module that wired one
  // a finding of the render gate.
  if (quoted(el)) {
    console.error(
      `leaf: <${el.localName}> is exhibited (x-exhibit); action ${action} refused`,
    );
    return null;
  }
  return post({
    kind: "action",
    version: VNUM,
    widget: el.id,
    action,
    detail,
    ...(attempt && { attempt }),
  });
}

// The page seat of a widget's conversation (x-conversation). A module places the seat;
// the comment layer fills it from the whole log. Before a thread exists it is a box for
// an answer the widget's own controls do not cover. Sending starts an ordinary comment
// thread anchored exactly on the widget; the next poll replaces the box with that same
// thread's inline textual view, while the panel keeps the complete view including any
// interactive reply markup.
//
// A widget standing inside a thread gets no seat: the containing thread already owns
// the reply box, and no version carries the nested widget id an anchored root would need.
// The declaration is checked at the helper boundary so a module cannot quietly place a
// conversation for a tag whose registry says nothing about one.
export function conversationBox(el, hint) {
  if (inChrome(el) || quoted(el)) return null;
  const declaration = registry[el.localName]?.["x-conversation"];
  if (!declaration || !matchesWhen(el, declaration.when))
    throw new TypeError(
      `<${el.localName}> placed a conversation outside its x-conversation predicate`,
    );
  if (!el.id)
    throw new TypeError(`<${el.localName}> needs an id to own a conversation`);
  const box = offer("div", "lf-conversation");
  box.dataset.lfConversation = el.id;
  const row = offer("div", "lf-say");
  const ta = offer("textarea");
  const send = offer("button", "lf-btn primary", "Send");
  const ctx = "say:" + el.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta, send);
  const sync = wireInput(ta, {
    hint,
    sends: "send",
    sendBtn: send,
    save: (v) => saveDraft(ctx, v),
    send: async (text, raw) => {
      if (
        !(await sendDraft(
          ctx,
          () => ta.value === raw,
          (attempt) =>
            post({
              kind: "comment",
              version: VNUM,
              anchor: { section: el.id },
              text,
              attempt,
            }),
        ))
      )
        return;
      showToast(`Sent to ${agent}`);
    },
  });
  sync();
  // Keep the first-message box reachable even while an existing exact-section
  // thread has displaced it. A draft edited in another tab can then restore the box
  // instead of surviving only in storage with no surface left to send it from.
  box.lfFirstMessage = row;
  const off = watchDraft(ctx, (value) => {
    if (!box.isConnected) return off();
    const text = value ?? "";
    if (ta.value !== text) ta.value = text;
    sync();
    renderPanel();
  });
  box.append(row);
  return box;
}

// Transient confirmation ("Moved to Doing — sent to Claude"), styled and placed by
// the comment layer. Announced too: toast routes through the live region.
export function toast(msg) {
  showToast(msg);
}

// Announce to assistive tech without a visual: the runtime's polite live region.
// Cleared first so repeating a message (two identical moves) re-announces.
export function announce(msg) {
  liveEl.textContent = "";
  setTimeout(() => (liveEl.textContent = msg), 30);
}

// ---------- the key register ----------
// One register. A row binds keys and says what pressing one does, and every surface is a
// projection of it — the dispatcher, the key line, the "?" overlay, a control's tooltip
// and what announce() speaks all read the same object. So no surface can name a key the
// register does not answer, and no binding can exist that no surface will show. The
// register's own scopes and the dispatcher that walks them are in the keyboard section
// below; what is here is the vocabulary they and the widget modules share.
//
// A row:
//   keys  — the bindings it answers: "d", "Escape", "Mod+Enter", "Shift+a", " ".
//           A function where the set is the page's (an option group's 1–N).
//   label — how it renders. Computed from `keys` unless the row is a chord whose second
//           half is another scope's row, and then built from that row rather than typed.
//   does  — the overlay's sentence.
//   line  — the line's word: a row carrying one stands on the key line, and a row that has
//           a `run` must carry one. That is the failure this register was built for, at
//           its smallest — `d` and `u` pressed, and no always-visible surface named them,
//           because the field was optional and its absence read exactly like a decision.
//           A row with no `run` may carry one all the same, since a press can be real and
//           immediate without being the runtime's: Enter opens the focused leaf because
//           the row is a link. What carries no word is reference, named in the "?"
//           overlay and never promised as the next press — F7, ⌥ click, a draft's
//           double-click.
//   when  — its liveness. The one predicate every surface asks.
//   run   — the press, taking the binding that fired.
//   repeat— whether holding the key repeats the press. Off by default: a held `]` was a
//           page navigation per repeat, and a held pick a `choose` per repeat.
//
// A scope is where the keyboard means something particular — the page, a focused thread,
// a card grip, a box being typed in. It declares its rows and where it holds, and where it
// holds is two questions:
//   the page HAS this scope  → the "?" overlay lists it
//   the reader is IN it now  → the key line renders it
// Both were already asked, by a pair of calls a widget made beside a listener of its own,
// so the display list and the dispatch were separate objects: a grip that answered Space
// said Enter on every surface, and three sites had to remember to re-declare on a state
// change. A row's `when` is the row's own liveness and says nothing about where the reader
// is; the scope answers that, and a row never restates it.

// Which platform's spelling, and which modifier is the chord's. Up here rather than beside
// the text inputs because the spelling table below is the first thing that needs it.
const MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

// How a key is spelled, in one column. The line said "esc" where the overlay said "Esc"
// for the same binding, and lf-options declared one pair of arrows twice, as "↑ / ↓" and
// "↑ ↓" — which is what a spelling kept per surface costs.
const GLYPH = {
  Enter: "⏎",
  " ": "space",
  Escape: "esc",
  ArrowUp: "↑",
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
  Home: "home",
  End: "end",
  Tab: "⇥",
  // Mod is the platform's own send modifier, and the matcher takes either it or Ctrl
  // (below): the chip says ⌘⏎ on a Mac and Ctrl+⏎ answers there too. A key that works
  // beyond what a surface promises is not a surface promising what does not work, which
  // is the rule this layer keeps.
  Mod: MAC ? "⌘" : "Ctrl",
  Shift: MAC ? "⇧" : "Shift",
  Alt: MAC ? "⌥" : "Alt",
};
// The modifiers the matcher implements, which is the whole of what a binding may carry.
// Read off `answers` rather than chosen here, so the list cannot claim more than the
// dispatcher does — a fourth name would have to be taught to both.
const MODIFIERS = ["Mod", "Alt", "Shift"];
// One reading of a binding's syntax, for the three questions asked of it: how it is
// spelled, whether a press answers it, and whether a text box's letters cover it. Three
// hand-agreed splits is one representation too few — the moment one of them had to state
// the modifier set, the other two were free to disagree about what a modifier is.
const parsed = (binding) => {
  const mods = binding.split("+");
  return { key: mods.pop(), mods };
};
// A modifier joins its key with nothing between them where its glyph is a symbol and with
// a + where it is a word, so "⌘⏎" and "Ctrl+⏎" are each their own platform's spelling.
// Shift on a letter is the letter's own uppercase, which is how a keyboard draws it and
// how this page's reference always has: the binding says Shift+a because that is what the
// dispatcher must ask for, and the chip says A because that is what the reader presses.
const spell = (binding) => {
  const { key, mods } = parsed(binding);
  if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key))
    return key.toUpperCase();
  return mods.reduceRight((rest, mod) => {
    const glyph = GLYPH[mod] ?? mod;
    return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
  }, GLYPH[key] ?? key);
};
// A cell is read where it is painted, never where it is written, so it may be a function
// of the page. That is what lets a key whose meaning moves say the meaning it has: the
// surfaces render this press rather than the set of presses the key could be.
const word = (cell) => (typeof cell === "function" ? cell() : cell);
const bindings = (row) => word(row.keys) ?? [];
// A row's rendering is made of its own bindings, so it cannot advertise a key it does not
// answer. Three rows existed only to carry a partner key — `u`, `k` and `]`, each
// invisible on both surfaces and reachable only through a sibling's hand-typed "d / u" —
// and folded into the rows that name them when this replaced those labels.
export const labelOf = (row) => word(row.label) ?? bindings(row).map(spell).join(" / ");
// Whether a row is live right now, asked through one predicate by the dispatcher, the line
// and the overlay alike, so no surface can promise a press the dispatcher refuses. A guard
// inside `run` instead is a liveness no surface can see.
const live = (row) => !row.when || row.when();

// Does this press answer this binding? Modifiers are matched exactly, so ⌘D is the
// browser's bookmark rather than half a page down, and ⌥ stays the aim chord's alone.
//
// A letter matches on its lowercase with Shift asked for separately, because caps lock
// writes an uppercase key out of an unshifted press and reads an unshifted one out of a
// shifted press. Read off the glyph, `A` would be the answer that ends the matter for
// every ask on the page: a reader with caps lock on gets it from a bare letter they
// meant as a letter, and can no longer reach it with the Shift the chip names. Asking
// for the modifier is what makes the chip true in both directions.
function answers(binding, ev) {
  const { key, mods } = parsed(binding);
  if (mods.includes("Mod") !== (ev.metaKey || ev.ctrlKey)) return false;
  if (mods.includes("Alt") !== ev.altKey) return false;
  const shift = mods.includes("Shift");
  if (key.length === 1 && key.toLowerCase() !== key.toUpperCase())
    return ev.key.toLowerCase() === key.toLowerCase() && ev.shiftKey === shift;
  // A punctuation key is reached with Shift on some layouts and without it on others
  // ("?" is Shift+/ here and a key of its own there), so its Shift is the layout's
  // business rather than the binding's.
  return ev.key === key && (!shift || ev.shiftKey);
}

// Checked where a scope is declared, which is the edge this data enters at: a row that
// presses must carry the word the line says over it. This is the whole failure the
// register was built for, wearing its smallest form — `d`/`u` stepped half a page for as
// long as the runtime has had them and no always-visible surface ever named them, because
// the word was an optional field and its absence read exactly like a decision. So the
// absence is refused rather than defaulted: falling back to the reference's sentence would
// have kept the row visible and spent the room of the four behind it, and there is nothing
// to compute a short word from. A row with no `run` is asked for none, since the press it
// names is not the runtime's — it either belongs to the platform, and says a word anyway
// because Enter really does open the focused leaf, or it is not a key at all.
// The other way a declaration can promise a press nothing will make, and the quieter one.
// `answers` asks after the three modifiers by name and treats every other prefix as absent,
// so a binding written `Ctrl+k` or `Cmd+Enter` is not a key that never fires — it is a
// different key that does. `Ctrl+k` spells itself "Ctrl+k" on both surfaces, matches a bare
// `k`, and refuses the press the chip is naming. A key on screen is a key that works, and
// nothing was reading the half of a binding that decides which key it is.
function checked(rows, where) {
  rows.forEach((row, i) => {
    if (row.run && !row.line)
      throw new Error(
        `leaf: row ${i} of ${where} presses with no word for the key line`,
      );
    for (const binding of bindings(row))
      for (const mod of parsed(binding).mods)
        if (!MODIFIERS.includes(mod))
          throw new Error(
            `leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier ` +
              `this dispatcher answers (${MODIFIERS.join(", ")})`,
          );
  });
  return rows;
}

// What activates a focused button, stated once because it is the platform's fact and not
// any one row's. Five rows spelled it by hand — the runtime's own control scope, a card
// grip in each of its two states, an option's pick mark, and the version menu's row — and
// the fifth spelled it short, naming Enter over a real <button> that answers Space too. A
// near-copy that has to change whenever the original does is a primitive not yet extracted,
// and the drift here was invisible: the key worked and the page under-promised it.
//
// A link is the case that keeps this honest. Enter follows an <a> and Space scrolls the
// page, so the leaves board binds Enter alone and is right to — the shared fact is what a
// button answers, not what a control does.
export const PRESS = ["Enter", " "];

// A clamped walk over a list of focusable rows: the row `dir` steps to from wherever
// focus stands, or the end it is already on. Clamped rather than wrapping, because ↓ on
// the last row must land where it already stands — the press stays the panel's, so the
// list doesn't scroll out from under a walk that reached its end, which is also how j/k
// walks threads. A walk that wraps is a fact about that walk (lf-tabs, per the ARIA tabs
// pattern) and states its own; this is the one two panels share. It hands back the row it
// landed on, for a walk that does more than move — the versions menu states a comparison
// from it, and against the row focus was on, since the clamped press moved nothing.
const walkRows = (rows, dir) => {
  const row =
    rows[
      Math.max(0, Math.min(rows.length - 1, rows.indexOf(document.activeElement) + dir))
    ];
  row?.focus();
  return row;
};

// The scopes declared against an element — a WeakMap, so a scope leaves with the element
// that owns it — and, for the overlay, their rows gathered under each title. A section is
// its sentences: the tenth grip on a page says what the first one says, so it is one
// section, while a widget whose keys are declared in two places (a draft's way in, and the
// editor it opens) contributes to one section from both.
// Two contributors to one section are live where either is, and the reader is in it where
// either says so — a `when` or an `at` nobody wrote means always, which is what makes the
// first contributor's silence carry rather than the second's answer.
const either = (a, b) => (a && b ? () => a() || b() : undefined);
// The same or, for a predicate whose silence means no rather than yes: what any contributor
// claims, the section claims. `either`'s identity is the wrong one here, and using it was
// this file's own bug one field over — a scope's claim deleted by a contributor that stated
// none, which is what `In a text box` is, the typing scope claiming the keys that put a
// character in a box and every wired box contributing a second section under its title
// claiming nothing. Takes the binding its callers take, where `when` and `at` take none.
const anyOf = (a, b) => (a && b ? (...args) => a(...args) || b(...args) : (a ?? b));
const elementScopes = new WeakMap();
const declaredScopes = new Map(); // title → section
const sentence = (row) => (typeof row.does === "string" ? row.does : row);
const bySentence = (rows) => rows.map((row) => [sentence(row), row]);
// One section per title, gathered from every contributor. Written once because the gathering
// happens twice and used to be spelled three times: here at declaration, where a widget's
// contributors arrive an upgraded element at a time, and at each open of the reference, where
// core's scopes and the widgets' are gathered into one list of sections. The rules above are
// this function — rows keyed by sentence, `when` and `at` joined by or — and a near-copy of a
// merge is a merge that drifts on the day one of the three learns something.
function merge(sections, { title, when, at, claims, rows }) {
  const seen = sections.get(title);
  if (!seen) {
    sections.set(title, { title, when, at, claims, rows: new Map(rows) });
    return;
  }
  for (const [key, row] of rows) seen.rows.set(key, row);
  seen.when = either(seen.when, when);
  seen.at = either(seen.at, at);
  // The claim travels because the reference reads it: a section that takes the keyboard
  // whole is one the reader is in or is not near at all, and its rows are then read by
  // their own liveness (showHelp). Dropped here, the chord's section arrived claiming
  // nothing, was listed whole, and named a list the page had not got — a fact stated on
  // the scope and lost on the way to the one surface that asks for it.
  seen.claims = anyOf(seen.claims, claims);
}

/** Declare a scope's keys where the code implementing them is.
 *
 * `where` is the element focus must be inside, `title` names the scope in the "?" overlay
 * (null for one the reference has no room to name), `rows` are its bindings, and `when` is
 * whether the page has this scope at all.
 *
 * A scope's `when` and a row's `when` are different questions, and keeping them apart is
 * what lets one declaration feed both surfaces. The scope's is the capability — does this
 * machine have neighbours to walk, does this page have a second version — and it gates the
 * reference. The row's is whether this press would move now — is a card held, has this
 * thread a box to reply into — and it gates the line, where the reader is standing in the
 * scope and can see the answer. So the reference names `r` wherever the page has threads,
 * which is what a reader learning the keyboard needs, and the line offers it only on a
 * thread that has something to resolve, which is what "a key on screen is a key that
 * works" asks for. One `when` answering both left `r` and Enter live over the whole page,
 * where the press no-opped.
 *
 * A control whose keys change with its state declares every state's rows at once, each
 * gated by its own row `when`, and calls paintKeys() when the state moves — a grab is
 * Enter on an already-focused grip, so no focus event would repaint the line.
 *
 * Registering at upgrade rather than at module load is what keeps the reference honest:
 * every x-upgrade module loads on every page, so a scope declared at the top level is help
 * for a widget the page hasn't got. The scope leaves with its element; there is no
 * withdrawal, because a control that stops answering a key says so in the row's `when`,
 * where every surface can read it.
 *
 * Returns the rows, so a widget that says its own keys out loud — a grip announcing what a
 * grabbed card answers — reads them back off the declaration rather than restating them.
 */
export function keys(where, title, rows, when) {
  elementScopes.set(where, {
    title,
    el: where,
    rows: checked(rows, title ?? "a scope"),
    when,
  });
  if (title) merge(declaredScopes, { title, when, rows: bySentence(rows) });
  paintHere();
  return rows;
}
/** What a scope answers right now, as a listener hears it read out — key names rather than
 * the chips the eye reads, since a screen reader renders "esc" literally. Off the register,
 * so an announcement cannot name a key the rows stopped binding.
 */
export const saying = (rows) =>
  rows
    .filter(live)
    .map((row) => `${spoken(row)} ${word(row.line)}`)
    .join(", ");
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the line's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the chord's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
const spoken = (row) =>
  word(row.label) ??
  bindings(row)
    .map((b) => (b === " " ? "Space" : b))
    .join(" or ");
/** Repaint the surfaces after a state change no focus event reports. */
export const paintKeys = () => paintHere();

// Where the reader is standing, painted: the ring on the ask they are in, and the line
// saying what the next press does from there. One repaint, because it is one question —
// both readings are of the focus and the open-ask list, and every signal that moves either
// (a focus move, an answer taken, a poll, a widget's own state) moves both.
//
// Coalesced to a frame: a focus move is a focusout then a focusin, and painting between
// them would flash the scope of nowhere and drop the ring for a frame. Here rather than
// beside the renders it schedules, because the scopes core declares call it as the module
// evaluates, which is before the line has an element to draw into — the frame is what puts
// the first paint after both.
let herePending = false;
function paintHere() {
  if (herePending) return;
  herePending = true;
  requestAnimationFrame(() => {
    herePending = false;
    markHere();
    // The chips are where the reader can go, beside the ring saying where they are and the
    // line saying what the next press does — one paint, because it is one question, and
    // because a chip repainted by its own door alone went stale on the door it did not
    // have: a poll that retires an ask moves the list under an armed window, and only the
    // panel's own render was calling the chip pass.
    paintAddresses();
    renderLine();
  });
}

// Where the reader is standing, which is not what `document.activeElement` answers: focus
// inside a shadow tree retargets to the host, so every question the register asks about
// the focused element got the widget instead of the control. A staged control found no
// scope of its own, matched no control scope, and would have had a press aimed at its
// host. The climb out of a tree was written long ago (upFrom); the descent into one was
// not, and the comment below promised it anyway — lf-diff's per-file disclosure declared
// its keys and no surface said a word about them.
const focused = () => {
  let el = document.activeElement;
  while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
  return el;
};

// The element scopes covering a node, innermost first — the climb crosses a shadow
// boundary the way `closest` climbs inside one, so a widget staging its controls in a
// shadow tree declares them the same way.
function scopesFor(node) {
  const found = [];
  for (let a = node; a; a = upFrom(a)) {
    const scope = elementScopes.get(a);
    if (scope) found.push(scope);
  }
  return found;
}
// Whether the focused control has claimed Escape for itself. Asked of the control's own
// scopes and not of the stack, because both callers mean "this press already has an owner
// where the reader is standing": the chord refuses to arm there, and focus entering one
// disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
// question asked of the whole stack would answer yes almost everywhere and the chord would
// never arm at all.
const claimsEsc = (node) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
  );

// How a widget collapses content it may need to show again (lf-tabs' inactive
// panels, a settled lf-options' cards): hidden="until-found", so find-in-page
// and fragment navigation still reach it — `beforematch` fires and the widget
// reopens what it owns. It is only a hide where the UA supports it (it rides
// content-visibility, and the theme's display:block outranks the boolean
// [hidden] rule) — without beforematch, fall back to plain boolean hidden,
// which the theme hides itself; the widget still collapses and reopens, ⌘F
// just can't see in.
export const HIDDEN = "onbeforematch" in document.body ? "until-found" : "";

// A scroll target can sit inside a collapsed container — a closed <details>, an
// inactive tab. Opening what the platform owns (details) and letting a container
// widget open what it owns (the lf-reveal event; lf-tabs listens) gives the
// target geometry before the scroll. Called before every scroll-to-content.
function reveal(el) {
  for (let a = el; a; a = a.parentElement) {
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    if (a.hidden) a.dispatchEvent(new CustomEvent("lf-reveal"));
  }
  // The containers are open; now tell the target itself. A widget whose chrome waits
  // on its container's geometry (a suggestion's hoisted row hides while its anchor
  // has none) settles synchronously on this, ahead of what the caller does next —
  // stepAsk focuses that chrome in this same task, and an async settle left the
  // focus on the previous ask's control while the announce said otherwise.
  el.dispatchEvent(new CustomEvent("lf-reveal"));
}

// The vocabulary, vendored per page: which tags a module upgrades, and which of their
// attributes are words the page says (see renderSaid). Empty only during the real
// fetch interval, when the already-wired chrome can legitimately be used; a failed
// fetch still rejects startup rather than becoming an empty vocabulary.
let registry = {};
let anchoringReady = false;
// The file-side passage reader fences an upgraded element and each of its original
// direct children when the registry cannot promise its body is verbatim. Remember
// those parts before custom-element definitions can add or move anything, so the
// browser can stop captured context at the same seams after every upgrade has run.
const opaquePassageRoots = new WeakSet();
const opaquePassageParts = new WeakSet();

// The vocabulary's widgets: every entry under a tag, and never a `$` entry. Those are
// the layer's own facts, and one of them ($keys) is spelled in the x- keys' own names —
// so a sweep that picked widgets by "declares x-says" without asking the tag took it
// for a widget called $keys, and querySelectorAll refused the name. Every walk over the
// registry that means widgets goes through here.
const widgetEntries = () =>
  Object.entries(registry).filter(([tag]) => tag.startsWith("lf-"));
// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is an x- key
// they carry, so the twelfth widget is covered by its entry alone — the alternative
// keeps working perfectly on the widget it was taught and silently does nothing for the
// next one.
const tagsDeclaring = (holds) =>
  widgetEntries()
    .filter(([, entry]) => holds(entry))
    .map(([tag]) => tag);
// The registry's shared predicate vocabulary: every declared attribute holds one of
// the admitted values. A boolean asks whether a flag is present; other values compare
// with the attribute's text. The lint holds each value to the attribute's schema.
export const matchesWhen = (el, when) =>
  Object.entries(when ?? {}).every(([attr, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? el.hasAttribute(attr) === value
        : el.getAttribute(attr) === value,
    ),
  );

// The open shadow roots under some root that hold the page's own words, from what the
// registry declares rather than from a sweep of every element: an x-shadow widget is
// making a promise about whose words those are, and a root some other library happened
// to attach is not covered by it. `getComposedRanges` is told exactly these, so what the
// capture can see and what the reading walks are one list.
//
// Which root to look under is the axis, because the whole document is not the only
// answer: a message arriving in the panel carries widget markup that upgrades in a
// subtree, so a pass over that subtree has the same boundary to cross and no document
// to ask about.
const shadowRootsIn = (root) =>
  tagsDeclaring((entry) => entry["x-shadow"])
    .flatMap((tag) => [...root.querySelectorAll(tag)])
    .map((host) => host.shadowRoot)
    .filter(Boolean);
const pageShadowRoots = () => shadowRootsIn(document);

// The theme's rules for shadow trees, sliced out once at load (see the markers in
// theme.css). Read from the theme rather than written here so a project that overrides
// the theme overrides these with it — and fetched during the upgrade, before any module
// renders, so the stage below can stay synchronous for its callers.
let shadowRules = "";
const SHADOW_CSS = /\/\* lf-shadow:start \*\/([\s\S]*?)\/\* lf-shadow:end \*\//;
// A top-layer element no longer composites through its light/shadow ancestors, so the
// document's main gate cannot hide a dialog promoted out of an x-shadow widget. Every
// legitimate page shadow tree is built here; put the same subtree boundary inside it,
// in an anonymous first layer so later widget stylesheet rules cannot outrank it.
const SHADOW_PRESENTATION_CSS = `
@layer {
  @media screen {
    :host-context(body:not([data-lf-presented])) *,
    :host-context(body:not([data-lf-presented])) *::backdrop {
      visibility: hidden !important;
      opacity: 0 !important;
      interactivity: inert !important;
      pointer-events: none !important;
    }
  }
}`;
async function loadShadowRules() {
  const response = await fetch("/theme.css");
  if (!response.ok) throw new Error(`leaf: theme failed to load (${response.status})`);
  // Refused rather than defaulted to nothing. A project theme that drops the markers
  // still styles the document, so the page looks right everywhere except inside the
  // widgets this slice feeds — which would arrive unstyled with no error anywhere, the
  // failure that reads as a widget nobody finished rather than as a theme missing a
  // block. Whichever theme is vendored, either it carries these or the page says so.
  const found = SHADOW_CSS.exec(await response.text());
  if (!found)
    throw new Error(
      "leaf: the theme carries no /* lf-shadow:start */…/* lf-shadow:end */ block, " +
        "which is where the rules an x-shadow widget renders under are read from",
    );
  shadowRules = found[1];
}

// The stage an x-shadow widget renders into. A module never calls attachShadow itself,
// because the marks the runtime paints come from a registry that is the document's while
// the ::highlight() rules styling them are not — they reach no shadow tree. A root
// attached anywhere else would show words the reader can select and no mark could ever
// paint, which is the one failure this whole capability exists to avoid.
//
// The two sheets arrive differently on purpose. The theme's rules go in as a <style>
// element, because that is markup and a copy keeps it; the marks are adopted, because
// they are the live comment layer, which a copy drops with the rest of the chrome — an
// adopted sheet is in no element's markup and would not survive the export either way.
//
// It takes the nodes rather than handing back a root to fill, so the style cannot be
// left out: a module that wrote its own children would replace the one thing holding its
// look, and it would look right in exactly the session where someone remembered. Same
// reasoning as renderSaid — a rule each widget has to remember is a rule that gets
// forgotten, and the forgetting is invisible until a page ships without it.
let markSheet;
export function shadowStage(host, nodes) {
  if (!markSheet) {
    markSheet = new CSSStyleSheet();
    markSheet.replaceSync(MARK_RULES);
  }
  // serializable, because a copy is rendered DOM with the scripts dropped and a shadow
  // root is in no element's outerHTML: exported without this, a diff leaves an empty
  // element where its lines were, which is the one medium that cannot be re-rendered
  // later. With it, `version export` writes a declarative <template shadowrootmode>
  // the browser rebuilds on open, with nothing running.
  const root =
    host.shadowRoot ?? host.attachShadow({ mode: "open", serializable: true });
  root.adoptedStyleSheets = [markSheet];
  const style = document.createElement("style");
  style.textContent = SHADOW_PRESENTATION_CSS + shadowRules;
  root.replaceChildren(style, ...nodes);
  return root;
}

function rememberPassageParts() {
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
  ))
    for (const root of document.querySelectorAll(tag)) {
      opaquePassageRoots.add(root);
      for (const child of root.children) opaquePassageParts.add(child);
    }
}

async function upgradeWidgets() {
  const response = await fetch("/registry.json");
  if (!response.ok)
    throw new Error(`leaf: registry failed to load (${response.status})`);
  const responseGeneration = response.headers.get("Leaf-Layer");
  if (responseGeneration && !sameLayer(responseGeneration)) return;
  registry = await response.json();
  const registryGeneration = registry.$layer?.generation;
  if (typeof registryGeneration !== "string" || !registryGeneration)
    throw new Error("leaf: registry lacks $layer.generation");
  if (!sameLayer(registryGeneration)) return;
  if (
    !registry.$events?.kinds ||
    !registry.$languages?.names ||
    !registry.$languages?.paths ||
    !registry.$tones?.names
  )
    throw new Error("leaf: registry lacks $events, $languages or $tones");
  revealLayer();
  rememberPassageParts();
  rememberAuthoredMarkup();
  markWide(document.body);
  // Before the modules import, because a widget's first render asks for these rules and
  // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
  if (tagsDeclaring((entry) => entry["x-shadow"]).length) await loadShadowRules();
  await Promise.all(
    tagsDeclaring((entry) => entry["x-upgrade"]).map((tag) =>
      import(`/widgets/${tag}.js`).catch((err) =>
        reportPageError(`widget ${tag} failed to load: ${err?.message ?? err}`),
      ),
    ),
  );
  settle(dress(document.body));
  // Importing defined the elements and ran their connectedCallbacks; async ones
  // registered their work via settle(). Wait it out so geometry is final.
  await Promise.allSettled(settling);
  // After the wait, because the box a widget scrolls is a box its module built: run this
  // with the rest of the upgrade and a diff's pre and a code block's are half there.
  reachScrollers(document.body);
}

// What an upgraded subtree owes beyond its module's own work: the words a widget says
// through an attribute rendered as real text, the facts it paints spoken, and its
// code — and the page's own <pre><code> blocks, alongside the widgets and for the same
// reason: the tokenizer is vendored, so a page has it exactly when it has a widget
// layer at all. Written once because it happens twice, over the page at the upgrade and
// over a widget rebuilt from the version's markup (rebuild), and a near-copy of it
// would go stale the day the vocabulary grows a fourth pass.
function dress(root) {
  renderSaid(root);
  renderQuiet(root);
  return highlightBlocks(root);
}

// Which widgets may stand wider than the column, from what they declare. Prose is set to
// a measure and stays at it; a board's columns and a diagram's graph are as wide as what
// they hold, and a page carrying one had to be either a cramped board or a page whose
// every paragraph was widened to suit it. Neither is a choice a page should have to make,
// so the widget kind says which it is (x-wide) and the theme spends the room the layout
// measured (--lf-room, syncLayout). The value is the kind the entry declares, and the
// theme's `[data-lf-wide="box"]` and `[data-lf-wide="drawing"]` rules read it.
//
// An attribute, because the theme cannot read the registry — the same arrangement x-says
// already has with data-lf-said, and what carries the breakout into an exported copy,
// which runs no script but keeps the markup. It is the runtime's paint on the page's own
// element, so it joins PAGE_PAINT_ATTRIBUTES: the version diff reads the live DOM against
// a file nothing has painted, and an attribute missing from that exclusion list is a
// change the author never made. Written before the modules import, because the width is
// the box each of them renders into, and written over the page alone: the room this
// hands out is the document's, and the one place a widget renders outside the document
// is a thread's message, where the room is the panel's (see msgNode).
function markWide(root) {
  for (const tag of tagsDeclaring((entry) => entry["x-wide"]))
    for (const el of root.querySelectorAll(tag))
      el.setAttribute(PAGE_PAINT_ATTRIBUTE.wide, registry[tag]["x-wide"]);
}

// Words a widget says through an attribute — a metric's number, an event's time, an
// option's chip band — rendered as text the user can reach. The theme renders the same
// words with `content: attr()`, and a pseudo-element's glyphs are in no text node: no
// selection can cover them, so no comment can be anchored on them, and the page shows
// text you can read and can't point at. Not the widget author's to remember, either: the
// registry names the attributes (x-says) and one pass renders them, so a widget cannot
// render a word the user can't quote.
//
// Each value goes at the edge its pseudo-element occupied (before = first child, after =
// last) — the only placement a pseudo could ever have had, and so the line past which a
// widget writes its own (lf-milestone's chips are a list and sit mid-element;
// lf-column's heading is its list's accessible name, which this pass knows nothing
// about). Those write the same data-lf-said span, and the guard below means the two
// compose rather than race. The pass runs after the upgrades, so a module that rebuilds
// its own body can't wipe a span put there first.
//
// The theme's pseudo rules stay, as the rendering a page carrying no script at all still
// gets (docs/how-it-works.html is one); they stand down where this pass has been, asked
// by :has(), so the two are never both on. The span is data-lf-gen and not .lf-ui: the
// diff parses the base version unupgraded and must not read it as text that version
// lacked, and the user must be able to quote it.
//
// data-lf-said names the attribute here and stands bare on a label relabel wrote, because
// the two are one claim — these words are the page's, whoever rendered them. The anchor
// pass reads the marker alone; the value is for whoever means one attribute in
// particular, which is this pass (so it writes no second span over its own) and the
// theme, whose every rule names the attribute it styles rather than matching the bare
// marker.
function renderSaid(root) {
  for (const [tag, entry] of widgetEntries()) {
    if (!entry["x-says"]) continue;
    for (const el of root.querySelectorAll(tag))
      for (const [attr, edge] of Object.entries(entry["x-says"])) {
        const text = el.getAttribute(attr);
        if (text === null || el.querySelector(`:scope > [data-lf-said="${attr}"]`))
          continue;
        const span = document.createElement("span");
        span.dataset.lfSaid = attr;
        span.dataset.lfGen = "1";
        span.textContent = text;
        // At the edge of the element's own words rather than of the element, which are the
        // same place on a page carrying no script and not once a module has injected
        // chrome of its own. These are the page speaking, so they belong beside the page's
        // other words: an option's risk chip landed past the pick mark that ends a compact
        // row — outside the apparatus the row runs to its line's end, and on the far side
        // of it from where the file's reading of that same version has it.
        const own = [...el.childNodes].filter(
          (n) => !(n.nodeType === 1 && n.dataset.lfGen),
        );
        el.insertBefore(
          span,
          (edge === "before" ? own[0] : own.at(-1)?.nextSibling) ?? null,
        );
      }
  }
}

// What a widget paints and never words. A task's status marker, a milestone's dot, an
// event's kind band, the accent ring on the recommended option: each is a fact the eye
// reads off paint alone, so a reader listening is handed every word around it and nothing
// of the fact itself — done sounded like blocked, and the page's own recommendation was
// invisible to the reader most in need of it. Same reasoning as renderSaid, one rung
// quieter: the registry names the attributes (x-paints) and one pass speaks them, because
// left to each module it is a thing to remember, and lf-event and lf-option, which have no
// module at all, could never have remembered it.
//
// The value is the word, or the attribute's own name where the value is empty: an enum
// means what it says (`blocked`), and a flag attribute means what it is called
// (`recommended`), which is the whole of what its ring says to the eye.
//
// The runtime's own restatement paint is said here too — the same failure under a
// different owner, and the one the code that paints it already calls a debt: a decision
// undone looks exactly like one never made, and the outline stating the difference states
// it in ink alone. It composes into the element's one quiet span rather than taking a
// second, so the two cannot fight over the place, and every quiet word on the page is
// written by one call whichever facts it is carrying.
//
// Its two neighbours in that vocabulary stay silent, and the line between them is what
// the paint is the only copy of. A retraction is one: nothing else on the page says the
// decision was undone. data-lf-pending and data-lf-reported are not — each marks a state
// whose substance is already in words, the control's own ("✓ Accepted", "your pick") or
// the status this pass speaks, and adds only that no version carries it yet. Saying that
// on every decided element for the rest of the session would be a second sentence about
// every one of them, for a fact no reader is owed the way they are owed a retraction.
function quietFacts(el) {
  const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated)
    ? ["rewritten since your decision"]
    : [];
  for (const attr of registry[el.localName]?.["x-paints"] ?? [])
    if (el.hasAttribute(attr)) words.push(el.getAttribute(attr) || attr);
  return words.join(", ");
}

function renderQuiet(root) {
  const painting = [
    ...tagsDeclaring((entry) => entry["x-paints"]),
    `[${PAGE_PAINT_ATTRIBUTE.restated}]`,
  ].join(", ");
  for (const el of root.querySelectorAll(painting)) quietWord(el, quietFacts(el));
}

// Anything a mouse can scroll, a keyboard can reach. A `pre` too wide for the column
// scrolls, and a user working from the keyboard had no way at all to the half of the
// line off the right of it — which is a phone's every code block, since the column there
// is 372px and a line of code is not. Asked of the computed overflow rather than of a list
// of tags, so a widget that scrolls is covered by scrolling and the twelfth one needs no
// entry, and it reaches the runtime's own boxes on the same terms as the page's — and
// into the trees an x-shadow widget renders in, which the walk alone does not enter.
//
// Asked of the content first, because a box holding a control of its own is already
// reachable (lf-board, through its grips) and a tab stop over the whole board would
// stand between the user and the card they were tabbing to.
//
// Two things every caller owes it, both learned by getting them wrong. It runs after a
// widget has rendered rather than as one stages, because the look a scroll box has is
// the theme's `:host(.lf-rendered)` rule and a widget adds that class once its render
// returns — so a sweep at `shadowStage` time reads a box the stylesheet has not reached
// and tags nothing. And it runs on a tree that is in the document, because
// `getComputedStyle` answers "" for every property of a detached element, which is the
// silent version of the same failure: a sweep that walks everything and tags nothing.
const FOCUSABLE =
  'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
function reachScrollers(root) {
  for (const scope of [root, ...shadowRootsIn(root)])
    for (const el of scope.querySelectorAll("*")) {
      if (el.tabIndex >= 0) continue;
      const style = getComputedStyle(el);
      if (
        !/^(auto|scroll)$/.test(style.overflowX) &&
        !/^(auto|scroll)$/.test(style.overflowY)
      )
        continue;
      if (!el.querySelector(FOCUSABLE)) el.tabIndex = 0;
    }
}

// ---------- comment layer ----------

const VERSION_MATCH = location.pathname.match(VERSION_PATH);
const VNUM = VERSION_MATCH ? parseInt(VERSION_MATCH[1], 10) : null;
const PINNED = new URLSearchParams(location.search).has("pin");
// Sign-off is the page's ask, not standing chrome: the approve button exists only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own ask.
const SIGNOFF =
  document.querySelector('meta[name="lf-review"]')?.content === "sign-off";
const POLL_MS = 2000;
// The panel's width, and so also the strip the page yields to it and the breakpoint
// under which yielding one is worse than being covered by it. One number, written
// into the stylesheet below rather than read back off the panel: the two have to
// agree, and the panel measures zero for as long as it is closed, which is exactly
// when the page most needs to know how wide it will be. 420 since threads carry
// questions — option rows are the one thread content that can't scroll or scale
// its width away, and 360 crowded them.
const PANEL_W = 420;
// The window under which yielding the strip is worse than being covered by it, as a
// query rather than a number, because three things ask it: the rule that takes the strip,
// the rule that hands scrolling to the sheet instead, and the runtime, for what follows
// from which of those the page is under. Written as the covering half, since that is the
// half the runtime asks about; the strip is its complement, spelled `not` where it is
// taken.
const COVERING = `(width <= ${PANEL_W * 2}px)`;
// The left edge's width, and the window below which its board covers the page rather than
// standing beside it — the same bargain the comment panel makes on the right, struck at
// the same ratio, so a reader who has learned one edge has learned the other.
const EDGE_W = 300;
const EDGE_COVERING = `(width <= ${EDGE_W * 2}px)`;
// The width the theme wants a page's box to have before it takes a strip of it for the
// margin (theme.css's --strip-min, stated there because that is where the strips and
// their breakpoints are). Read blind: the runtime reports how wide the box is against
// the number the theme states and never learns which idiom spends it. A theme without
// the token leaves this NaN, every comparison against it false, and the media query
// alone deciding — which is the same answer a page with no runtime already gets.
const STRIP_MIN = parseFloat(
  getComputedStyle(document.documentElement).getPropertyValue("--strip-min"),
);

// ---------- styles ----------
/* A marked passage is painted, not wrapped (see paintAnchors), so its rules reach it
   through the highlight registry — which styles glyphs, so the underline stands in for
   a border and the pointer's cursor comes from a class the hit-test puts on body. A
   posted thread's mark wears the comment layer's own violet (--mark-ink and the wash
   beside it, which is the same colour a marked element's ring is drawn in); the open
   composer's draft wears the accent, and outranks it where they overlap. Not dashed —
   dashed means detached.

   Stated once and installed twice, because the registry is the document's and the
   ::highlight() rule is not: a rule in the document styles no glyph inside a shadow
   tree, so a widget that renders the page's words into one (x-shadow) adopts this same
   text (`markSheet`). Two copies of these declarations would be two chances for a mark
   to mean one thing in the document and another inside a diff. */
const MARK_RULES = `
  ::highlight(lf-mark) { background-color: var(--mark);
    text-decoration: underline 2px solid var(--mark-ink); text-underline-offset: 3px; }
  ::highlight(lf-mark-hover) { background-color: var(--mark-strong); }
  ::highlight(lf-pending) { background-color: color-mix(in srgb, var(--accent) 20%, transparent);
    text-decoration: underline 2px solid var(--accent); text-underline-offset: 3px; }`;
const style = document.createElement("style");
style.textContent = `
  /* The document and the panel are two scroll regions side by side. If the document
     scrolled the viewport, its scrollbar would paint at the viewport's right edge —
     over the panel, in the same few pixels as the panel's own, so the two thumbs
     stack. Body owns the document's scroll instead, and syncLayout keeps its box
     clear of the panel, which puts each region's scrollbar inside that region.

     The gutter is stable because the column is measured off it: a page that grows
     past the window mid-session — a suggestion accepted, a panel of tabs opened —
     would otherwise gain a scrollbar, and the column would re-centre in what was
     left. Stated rather than measured, because it can't be measured here: macOS
     draws overlay scrollbars, which take no room and reserve none, so on this
     machine the declaration is a no-op and the shift it prevents cannot be made to
     happen (neither scrollbar-width nor a styled ::-webkit-scrollbar nor
     --disable-features=OverlayScrollbar brings a room-taking one back). It is kept
     on the platforms where scrollbars do take room, which is most of them, and on
     the reasoning that reserving a gutter never costs more than the shift not
     reserving it produces.

     All of it is the live page's, and it is withheld from the other two media the way
     every other affordance is. A copy has no panel to sit beside and no session to
     grow in, and it carried the whole arrangement anyway: body scrolled it, reserving
     a gutter against a change that can no longer happen and holding 54px of scroll
     padding under a banner the file hasn't got — so wherever a scrollbar takes room
     the copy's column sat 7.5px left of the centre of a page it had all of. Nothing
     on this machine could say so, the declarations being no-ops here; the runner said
     it, on every example at once. That is what pins this now
     (test_an_exported_example_stands_on_its_own, and scripts/linux-suite.sh is where
     to watch it fail), and paper needs no rule of its own, never having been handed
     the arrangement to undo. Spelled :where(), because these declarations are the only
     statement their properties get and the plain form would hand every one of them a
     class the body rule below never had. */
  @media screen {
    :where(html:not(.lf-copy)) {
      height: 100%;
      overflow: hidden;
      body { height: 100%; overflow-y: auto; scrollbar-gutter: stable;
             scroll-padding-top: calc(var(--lf-banner-h) + 12px); }
      /* The banner stands over the head of the document, so the page's first lines get
         room rather than starting under it, and the key line reserves the same at the
         foot (syncLayout). Both are boxes in the flow rather than padding on body, which
         is the box the room a wide widget spends is measured from — CLAUDE.md's "The one
         writer may not write the box the layout is measured from" carries why. A box also
         adds to whatever padding the page declares at this edge, where a rule here would
         replace it, and it is withheld from paper by the block it sits in: written as
         padding it stayed behind, holding 42px of blank over the first line of every
         printed page for a bar that was not on it. */
      body::before { content: ""; display: block; height: var(--lf-head, 0px); }
    }
  }
  /* position: relative makes body — the scroll container — the containing block for
     the two floats that point into the document (the 💬 button and the composer), so
     the browser scrolls them with the passage they stand beside. */
  /* The banner's height, said once. Everything at the top edge derives from it — the
     bar itself, the panel starting under it, the focus-revealed mark note, the
     scroll padding that keeps an anchored jump out from beneath it (plus air) — and
     the room the document leaves for it is measured off the rendered bar (see the
     append below) rather than restated. */
  /* The chrome's line box, said once, because one control in the banner cannot be
     told it. Chrome computes a select's inner height from its own metrics and
     refuses line-height outright — the computed value stays normal however the
     rule is written — so the chooser stood 3.3px shorter than every button beside
     it, centred, and read as sunk into the row. Its height is stated instead, from
     this and its own padding (see the chooser's rule), which is the same number
     .lf-btn arrives at through the line box. Stated in one place so the two cannot
     come apart: a third copy of 1.45 is exactly the drift the reserve comment below
     is about, and this one would show as the chooser sinking again. */
  body { --lf-banner-h: 42px; --lf-ui-lh: 1.45; }
  body { position: relative; box-sizing: border-box; }
  /* The strip the panel takes is given up as motion rather than as a jump, so the eye
     can follow the sentence it was reading to where it went. Keyed on the stamp that
     says the document is done becoming itself, because until then every margin the
     page has is one it arrived with: a panel restored open would otherwise slide into
     place on load, and a version switch is a load, so every revision would arrive
     sliding sideways under a user who asked for a revision and not for motion.
     The stamp lands at the end of the start chain, long after the restore. Reduced
     motion is handled globally by the theme's guard. */
  body[${PAGE_PAINT_ATTRIBUTE.upgraded}="1"] {
    transition: margin-right .18s ease, margin-left .18s ease; }
  /* The strip itself, and — where there is no room to yield one — the page handing
     scrolling over to the sheet that covers it instead. A margin, not padding: body is
     the document's scroll container, so this is what ends its box, and its scrollbar, at
     the panel's edge rather than under it. Under a covering sheet one wheel gesture still
     moves one region, and the region is the thread list; the page holds its place for
     when the sheet closes — a hidden-overflow scroller keeps its position, and still
     moves for a j/k walk or a version switch restoring where the user was, so the passage
     behind the sheet is the one the panel is talking about.

     The cascade's, though syncLayout is the layout's one writer, because body's box is
     the one thing that writer may not write: it runs from an observation of that box, and
     a write from inside that round is a resize of what was just reported — the round
     breaks, and Chrome says so on the window's error channel and nowhere else (CLAUDE.md,
     "The one writer may not write the box the layout is measured from"). Written in JS it
     survived on a coincidence: the margin transitions, so the used value did not move
     until the frame after the write, and the round the write landed in closed intact. A
     stylesheet is where a fact about the shape of the page belongs anyway, and the panel
     states only that it is open.

     The strip comes out of the page rather than being held aside for it, which makes
     opening the panel the largest movement in the product: the column re-centres by half
     the panel's width, and on a window narrow enough to lose width as well it rewraps
     every line. Both are carried as motion rather than as a jump — the transition above,
     keyed on the stamp for the reasons given there — because an eye can follow a sentence
     that slides and cannot find one that teleports. */
  @media screen and (not ${COVERING}) {
    body[data-lf-panel] { margin-right: ${PANEL_W}px; }
  }
  @media screen and ${COVERING} {
    body[data-lf-panel] { overflow-y: hidden; }
  }
  /* The asks board takes its room out of the page the same way, and the leaves board
     beside it does not. That is not an inconsistency between two twins: a leaf's row is
     a way out of this page and an ask's row is a way around it, so pressing an ask's row
     scrolls the document to the ask and stands you on the control that answers it — and
     a board lying over the document would be hiding the very thing it just sent you to.
     A 300px board and a 720px column overlap on any window under about 1320px, which is
     most of them, so this is the common case rather than the narrow one.

     The rule names the board and not the edge for that reason, off the one attribute
     showEdge writes to say which board is up. Everything else about the strip — that it
     comes out of the page rather than being held aside, that it is carried as motion,
     what it costs on a window narrow enough to rewrap — is the panel's story above,
     told once for both sides. */
  @media screen and (not ${EDGE_COVERING}) {
    body[data-lf-edge="asks"] { margin-left: ${EDGE_W}px; }
  }
  @media screen and ${EDGE_COVERING} {
    body[data-lf-edge="asks"] { overflow-y: hidden; }
  }
  /* Rules at this level are the shared vocabulary: classes whose whole job is
     elements the page owns — a widget's controls wear lf-ui and lf-btn, and the
     runtime marks the page's own elements (lf-mark-el, lf-ins-block). Adding one
     widens the vocabulary; a rule that styles the runtime's own layer goes in the
     @scope block below instead. */
  .lf-ui { font-family: var(--sans); font-size: var(--t-5); line-height: var(--lf-ui-lh); color: var(--ink); box-sizing: border-box; }
  .lf-ui *, .lf-ui *::before, .lf-ui *::after { box-sizing: inherit; }
  /* Clearing the UA's form-control face is a different kind of declaration from
     choosing one, so the clearing lives in a layer, which any unlayered choice
     outranks whatever its specificity. That makes unrepresentable what used to be a
     cascade race: a control wearing .lf-ui itself takes the chrome face from its own
     class instead of inheriting past it into the document's serif (the 💬 button shipped
     that way, at 17px), and the one control whose face is deliberately the document's —
     lf-draft's editor, which must match the body it replaces — states so unlayered in
     the theme and wins that. A layered rule still outranks the UA's, which is all the
     clearing ever needed. */
  @layer lf-reset {
    .lf-btn, .lf-ui textarea, textarea.lf-ui { font: inherit; }
  }
  /* A press a widget injects is a span wearing role="button" (see offer), so the two
     things a <button> came with are stated here. The box, because an inline span drops
     vertical padding out of the line — only .lf-btn needs it, since every other press
     is a flex item or positioned. And the drag: a real button refused one, which is
     worth keeping wherever the control's words are the runtime's, and is exactly what
     must not happen where one of them is the page's. So the selection goes off only
     where nothing under the press is said: a descendant cannot win it back, since
     user-select none on an ancestor takes the whole subtree out of a pointer's reach
     whatever the descendant declares. */
  .lf-btn { padding: 4px 10px; border: 1px solid var(--border-2); border-radius: 6px; background: var(--card); cursor: pointer; white-space: nowrap; color: inherit; display: inline-block; }
  .lf-ui[role="button"]:not([data-lf-said]):not(:has([data-lf-said])) { user-select: none; -webkit-user-select: none; }
  .lf-btn:hover { background: var(--chip); }
  .lf-btn.primary { background: var(--accent); border-color: var(--accent); color: var(--paper); }
  .lf-btn.primary:hover { filter: brightness(.92); }
  /* Two selectors, two mechanisms, one look: the platform's own on the banner's real
     buttons, and the attribute wireInput sets, which is the only one a span press can
     wear. */
  .lf-btn:disabled, .lf-btn[aria-disabled="true"] { opacity: .55; cursor: default; }
  .lf-btn.on { border-color: var(--accent); color: var(--accent); background: var(--chip); }
  /* The margin's press. Two shapes cover every labelled press the product makes: .lf-btn
     in the runtime's furniture, and this pill out in the page margin, where a control
     stands beside the reader's own words and hairline scale is what keeps it from
     shouting over them. Stated once, at document level, because the margin's controls
     live on both sides of the chrome's scope line — the runtime's 💬 and a suggestion's
     ✓ Accept often share a line, and two hand-matched copies of this look were held
     together only by a test. A decided suggestion re-states background and cursor over
     these; its rules carry the attribute the decision wrote, so they outrank this.

     The look is the pill's and the hand is the press's, which is one rule apart and was
     one rule too few. Not every wearer is a control — the composer's head says which
     page it is writing about in a pill of the same make — so a shape stating the hand
     itself put one under a label that answers nothing. It reads the two ways a press is
     spelled here: the platform's element, and the attribute offer() writes on a span. */
  /* Words for a reader listening, silent on screen: real text, the one thing every
     screen reader announces in every mode, clipped to nothing where paint already says
     the same fact to the eye (renderQuiet, and lf-code's highlighted lines). Worn with
     .lf-ui, since an invisible word is apparatus the anchor pass must not offer — a
     quote resolved into a clipped box would paint a mark nobody can see. Out of flow,
     so it holds no room; the covered-words gate skips this class the way it skips the
     runtime's own .lf-mark-note, whose clip this is.

     And out of the selection, which the clip does not do on its own: a word standing
     among the page's own words is inside any selection drawn across them, so the
     runtime's reading skipped it and the user's clipboard did not — a copied task line
     came away carrying the word "done", and a copied code block would carry
     "highlighted" into whatever editor it was bound for. .lf-mark-note answered this
     the day it was written; the clip it shares had not. */
  .lf-quiet { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; user-select: none; -webkit-user-select: none; }
  .lf-pill { font-size: var(--t-6); line-height: 1.7; padding: 0 8px; border: 1px solid var(--border-2); border-radius: 999px; background: var(--card); color: var(--ink-2); white-space: nowrap; }
  .lf-pill:is(button, [role="button"]) { cursor: pointer; }
  .lf-pill:is(button, [role="button"]):hover { background: var(--chip); }
  /* A gesture the log has not answered yet, in the platform's own word for it, which
     is why no tag is named here: any widget that says aria-busy is painted, and
     lf-draft was saying it to screen readers alone before this rule existed.

     Delayed, and that is the whole design. A press paints nothing until the log
     takes it, which locally is about 40ms — a look that appeared and left inside
     that window would be a second flicker put where the first one was removed. Past
     the delay there is something to say, and the cases where there is are the ones
     that need it: a heavy page, or a reader who reached a --host page across a
     network. So the surface goes quiet only once the wait has run long enough to
     notice, and a fast answer never shows this rule at all. The reduced-motion guard
     (theme.css) zeroes the duration and leaves the delay standing, which is the right
     reading of it: the fade is what a reader asked not to have, the waiting is not.

     Opacity and the cursor, never geometry: the line a press is made on holds still
     (lf-suggestion.js), and a busy surface that reflowed would move the control out
     from under the pointer that just pressed it. */
  [aria-busy="true"] { animation: lf-runtime-4f3c2a8d-working 140ms linear 200ms both; }
  [aria-busy="true"], [aria-busy="true"] :is(button, [role="button"]) { cursor: progress; }
  /* Standing on a press, in the band everything else the reader stands on is drawn in
     (--here-ring). The two shapes were the last places on the product still wearing the
     browser's own ring: a reader who backed out of the panel landed on Comments in
     Chrome's blue, beside an ask wearing the page's accent, with nothing saying the two
     rectangles meant one thing.

     Each states its own gap, because they stand at different densities and the ring may
     not reach its neighbour: the standing gap is what a box with room around it takes,
     the composer's row puts 6px between two buttons, and a suggestion's pills sit 4px
     apart out in the margin. The pill's rule was the suggestion family's, which is a
     family stating a fact about a shape the runtime owns — its own rules there are for
     what a decided suggestion adds, and a focus ring is nothing a decision changes. */
  .lf-btn:focus-visible { outline: var(--here-ring); outline-offset: 2px; }
  .lf-pill:focus-visible { outline: var(--here-ring); outline-offset: 1px; }
  /* The keyboard address: the digit that reaches this thing right now, worn as a chip
     off its holder's corner so an address arriving moves nothing. The g chord paints one
     on every member of the list it has aimed at and an option wears the one a pick
     answers, which is the same promise made on the two sides of the chrome's scope line —
     so it is stated here, at the level both can reach, rather than as the twelve
     declarations each once carried. They had not drifted; nothing was going to say so if
     they did. What a wearer keeps is where its chip sits and when it shows — the chord's
     stand in a layer of their own, placed on each member's visible corner, an option's in
     a column that option holds for it. This rule dresses; theirs place and paint.

     Its two numbers are off the ladder because they are the disc rather than the type:
     a 17px circle with a 1px ring leaves 15px of interior, which is the line the digit
     is centred on, and 11px is a digit that sits in that interior with room around it.
     Set at the apparatus rung the glyph would crowd the ring it is drawn inside, the
     way the pick mark's ✓ would. */
  .lf-address { display: none; width: 17px; height: 17px; border: 1px solid var(--accent); border-radius: 50%; background: var(--card); color: var(--accent); font-size: 11px; line-height: 15px; text-align: center; z-index: 1; }
  /* The leaf text box, in one rule. field-sizing does the growing, so no script
     measures a textarea: the JS that did had to reset height to auto to re-measure,
     which made the box briefly too small for its own text on every keystroke — and a
     box that overflows, however briefly, flashes a scrollbar. Past max-height the
     scrollbar is real and stays — and the ceiling is the viewport's share, not a count
     of lines: 200px stopped a long comment at ten lines with the screen mostly empty.
     Both selectors: the panel's boxes sit inside .lf-ui, a widget's own box wears the
     class itself. */
  .lf-ui textarea, textarea.lf-ui { padding: 8px 10px; border: 1px solid var(--border-2); border-radius: 6px; background: var(--card); color: inherit; resize: none; field-sizing: content; max-height: 50vh; overflow-y: auto; }
  .lf-ui textarea:focus, textarea.lf-ui:focus { outline: none; border-color: color-mix(in srgb, var(--accent) 45%, var(--card)); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent); }
${MARK_RULES}
  body.lf-over-mark { cursor: pointer; }
  /* Holding ⌥ changes what a click means, and nothing on the page said so — the chord's
     whole cost is that it is invisible. Two things say it, and the division matters:
     the item under the pointer wears the aim's box (.lf-aim, in the chrome's scope
     block), which answers *which*, and the cursor answers
     *whether*. crosshair was tried and read as a cross — an icon for closing something,
     not for aiming at it — and copy, alias and a menu each name an action this isn't.
     What is left is the pair this page already spends on that same distinction one line
     above: the hand where a press acts, the arrow where it doesn't. Armed, a press acts
     exactly where there is an item under it and on nothing where there isn't
     (claimPress), so those two states are those two cursors, and the hand promises no
     more than the box beside it does.
     The plain arrow alone was the first answer and it under-promised. It says only "not
     a text selection", which is the half a reader can already infer from the box,
     and it says the same thing over a gap a press does nothing in as over the paragraph
     a press would take whole — so the one question the box leaves ("would this
     click do anything?") was the one the cursor declined to answer, and a user held the
     key and asked it out loud.
     Derived at the paint, off the value refreshAim resolved for the box, so there
     is one answer to what the aim is on rather than a second reading free to disagree
     with what is drawn.
     What this does not reach is a control that states a cursor of its own — a
     suggestion's ✓ Accept, an option row — which goes on showing its hand while an armed
     press is being swallowed above it. Inherited declarations lose to declared ones, so
     covering that means either an important universal rule or naming this container at
     document level to hold the chrome out of it, and both are worse than the case: the
     box is absent there, which is the honest half of the answer, and the control's
     hand says what it always says rather than something new and wrong.
     One declaration on the body, inherited, rather than a rule reaching down the page:
     naming .lf-chrome here to hold the chrome out would put that class into the
     document-level surface, and the class the chrome is rooted at is not vocabulary a
     widget wears. The chrome holds itself out instead, from inside its own scope. */
  body:is(.lf-aiming, .lf-design) { cursor: default; }
  body:is(.lf-aiming, .lf-design).lf-over-item { cursor: pointer; }
  /* One pixel, just inside the border box, because both sides of that edge belong to
     somebody else. Outside it, the mark belongs to whatever encloses the element: a board
     scrolls (overflow-x: auto), its columns sit flush against its padding box on three
     sides, and a mark drawn outside a column was clipped down to the single vertical line
     that fell in the gutter. Deeper inside, it belongs to what the element paints over
     itself: an outline is painted before positioned descendants, so a container whose cells
     carry a background — every choose group, since lf-option is relative — wipes out
     whatever of the mark reaches past its own border. Containers are exactly what element
     anchoring is for, so neither is a corner, and the second was what a reader reported: a
     2px mark two pixels in came out a hairline on three sides of the group they had just
     commented on and stayed 2px along the bottom, where the last cell stops short, so the
     box was thicker at the bottom than the top. One pixel in is inside every ancestor's
     clip and, wherever the element has a border of its own, outside every child's paint,
     which is 72 of the 73 markable elements measured across the examples — the odd one a
     mermaid node whose fractional width antialiases a device pixel either way.
     The 73rd is the shape this does not reach, and it is worth naming because the fix
     stops there rather than because it arrived with it: an element with no border of its
     own whose positioned child is flush to the border box has no such band, so lf-shot
     paints its frame over the mark's left and right and the reader gets a rule above and
     below the figure and nothing down its sides. That was equally true at 2px two pixels
     in — nothing here regressed it — and it is not reachable from a stylesheet, since the
     only band left is outside, where a scrolling ancestor takes it. What would reach it is
     a widget declaring that it paints to its own edge, and no widget needs to yet.
     A hairline is not a fainter mark than the 2px was: --mark-ink clears 9.0:1 on the
     paper where the burnt orange it replaced cleared 3.4, so this reads as an annotation
     where a saturated 2px rectangle read as a validation error. It takes the element's own
     corner radius rather than restating one, which is what the radius here used to
     override. */
  .lf-mark-el { outline: 1px solid var(--mark-ink); outline-offset: -1px; cursor: pointer; }
  /* The draft's own passage — a standing annotation like the posted mark, which is why
     it may share the hairline where the ⌥ aim's promise may not (the .lf-aim rule in
     the scope block says why). Only the colour separates it from a posted mark, and the
     colour moved: the burnt orange stood 77 ΔE from the accent and --mark-ink stands
     24, both now at a hairline. What keeps the two apart is no longer the paint alone —
     an open composer is on screen whenever this one is, and an element a thread already
     marks keeps the posted colour rather than taking this (paintAnchors), so the pair
     never contend on one element. */
  .lf-mark-el.lf-pending { outline-color: var(--accent); cursor: auto; }
  /* Armed, a press on a thread-marked element is the aim's, not the thread's, so the
     hand here is the aim's answer rather than the thread's: it stands where the aim has
     an item and comes off where it hasn't, which is the same promise the body is making
     and not the mark's own "open this thread". */
  body:is(.lf-aiming, .lf-design) .lf-mark-el { cursor: default; }
  body:is(.lf-aiming, .lf-design).lf-over-item .lf-mark-el { cursor: pointer; }
  /* The one runtime word living inside the page's own elements, so its hiding cannot
     come from the chrome's scoped .lf-unseen — the same recipe, restated at document
     level. It becomes a skip-link-style control on focus: a reader who hears the count
     can enter its first thread, then j/k through the rest. user-select keeps it out of
     a selection, so the runtime's own words never enter a captured quote. */
  .lf-mark-note { position: absolute; width: 1px; height: 1px; padding: 0; border: 0;
    overflow: hidden; clip-path: inset(50%); user-select: none; }
  .lf-mark-note:focus-visible { position: fixed; z-index: 9050;
    top: calc(var(--lf-banner-h) + 6px); left: 8px;
    width: auto; height: auto; padding: 6px 10px; overflow: visible; clip-path: none;
    border: 1px solid var(--accent); border-radius: var(--r); background: var(--card);
    color: var(--ink); box-shadow: 0 8px 24px rgba(0,0,0,.12); }
  .lf-ins-block { background: var(--add-tint); box-shadow: 0 0 0 4px var(--add-tint); border-radius: 2px; }
  /* The open ask the reader is standing in (markHere), worn by the ask rather than by
     whichever of its controls holds the focus — they are standing in the whole thing,
     however they got there. Exactly one ask wears it at a time: every shipped widget
     draws one box for it to paint on, and one a page styles boxless hangs it on the
     boxes its contents make (shownParts). While the asks board is open, its row mirrors
     the same fact on the second surface. It is an outline like every other mark the
     runtime paints on the page's own elements: it moves nothing on arriving, and it
     keeps its place for nothing, being the element's own paint rather than a box in
     the chrome that would have to chase it down every scroll, reflow and drag. */
  [${PAGE_PAINT_ATTRIBUTE.ask}] { outline: var(--here-ring); outline-offset: var(--here-ring-gap); }
  /* Paper takes no input, so what a widget injects to be worked goes: the control,
     and the box that holds controls. What stays is a control whose label is one of
     the page's own words — a pick mark reading "chosen" is the only place the page
     says which option it carries — which is why this keys on the declaration each
     label makes (see relabel) rather than on .lf-ui, whose question is anchoring's.
     Asked of the control itself, not of what it holds: a settled group's disclosure
     names the chosen card, and that word is worth keeping on screen where the row is
     the only place it stands and worth dropping on paper, where the cards are open
     underneath saying it themselves. An exported copy strikes the same bargain on the
     same two markers, and takes the control out of the document rather than hiding it,
     which paper cannot do (BAKE). The runtime's own layer hides as one thing, in the
     @scope block below. */
  @media print { [data-lf-offer]:not([data-lf-said]) { display: none !important; } }
  /* Keyframe names are document-global even beside an @scope block. The stable salt
     makes this runtime-private in the one CSS namespace scoping cannot protect. */
  @keyframes lf-runtime-4f3c2a8d-pulse { 50% { opacity: .35; } }
  @keyframes lf-runtime-4f3c2a8d-working { to { opacity: .5; } }
  @keyframes lf-runtime-4f3c2a8d-flash {
    0% { background: var(--hi-tint); } 100% { background: var(--card); }
  }
  @keyframes lf-runtime-4f3c2a8d-grow {
    0% { opacity: 0; transform: translateY(-6px) scale(.985); }
  }
  /* Everything below is private to the chrome, scoped to the runtime's own container:
     no widget or page class can match a rule here, whatever it is named. (lf-tabs once
     marked itself lf-live — this block's name for the visually-hidden live region —
     and every tabbed page clipped to a pixel.) */
  @scope (.lf-chrome) {
    /* The layer is the runtime's, not the document's, so it never prints — one rule
       for all of it, rather than each piece remembering. :scope is the container
       itself, which is why this can't be written at document level without widening
       the shared vocabulary by a class only the runtime ever wears. */
    @media print { :scope { display: none; } }
    /* What the layer inherits from the document, answered at the layer's root, because
       the document below is a page of prose and this is not it.

       cursor, because the page's own body may be armed for ⌥ aiming — a statement about
       the document, not about anything in here. Stated on this side so the document side
       needs no mention of this container's class, which would widen the shared vocabulary
       by a name no widget ever wears.

       The face, so anything in here that misses .lf-ui still inherits the chrome's
       rather than the document's. The reset layer (above) is what keeps a control that
       *wears* the class from walking past it — the 💬 button once inherited straight
       into the page's serif at 17px that way — and this is the same answer for the
       text around the controls. */
    :scope { cursor: auto;
      font-family: var(--sans); font-size: var(--t-5); line-height: var(--lf-ui-lh); }
    .lf-banner { position: fixed; top: 0; left: 0; right: 0; z-index: 9000; height: var(--lf-banner-h);
      display: flex; align-items: center; gap: 10px; padding: 0 14px;
      background: var(--veil); backdrop-filter: blur(6px); border-bottom: 1px solid var(--rule); }
    .lf-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted-2); flex: none; }
    .lf-dot.working { background: var(--accent);
      animation: lf-runtime-4f3c2a8d-pulse 1.4s ease-in-out infinite; }
    .lf-dot.listening { background: var(--ok); }
    .lf-dot.away { background: var(--warn); }
    .lf-dot.offline { background: var(--danger); }
    .lf-status-text { color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
    .lf-status-text .lf-age { color: var(--muted); }
    .lf-spacer { flex: 1; min-width: 0; }
    /* This row is packed to the right against the spacer, and that decides who pays for
       a control changing size: it moves itself and everything to its left, while
       everything to its right keeps its place. Three of these rewrite their own words —
       "✓ Approved" is narrower than "✓ Looks good", and two of them count something
       that gains a digit — so each holds room for the widest it may say, taken from the
       words themselves (the reserve calls where the banner is built) rather than stated
       here as numbers. Three numbers stood here once and all three quietly stopped
       covering the day --t-5 moved from 13.5px to 14px; a reservation the control
       measures in its own live face at load has no number to go stale. The two sweeps —
       a press, and the poll — stay the check that the words reserved are the words the
       writers actually write.

       The chooser was the one control here that had to state a width, because its label
       carried the version's note and a note has no widest to reserve. It says the version
       and, while a comparison is standing, a Δ — two words, both enumerable — so it is
       floored at its own like the rest, and no number on this row is a fact about a font
       any more. */
    @layer lf-reset {
      .lf-thread-action { font: inherit; }
    }
    /* The chooser's menu: fixed under the button it hangs off, anchored rather than
       measured, so nothing recomputes a position when the row's contents change width.
       It is the only place the version notes are, so a row wraps to hold one whole —
       the reason a menu is worth having over a control whose closed label and open list
       are forced to be the same string. Capped at the viewport's remaining height and
       scrolling inside itself, since a page's versions are unbounded.

       Two columns, because a version and what it changed are one row's two halves: the
       note says it in words and the Δ marks it on the page. That press was a second
       control out on the bar, naming a second version number beside the chooser's, and
       the two together said no more than either — a reader could tell that v2 and v3
       were both being mentioned and not what either mention was for. The pair are grid
       siblings rather than a wrapper each, because a role="menu" owns menuitems and a
       div between them is a claim about ARIA that nothing here needed to make. */
    .lf-version { anchor-name: --lf-version-btn; }
    .lf-version-menu { position: fixed; position-anchor: --lf-version-btn;
      top: calc(anchor(bottom) + 6px); right: anchor(right); z-index: 8950;
      display: none; grid-template-columns: 1fr auto; align-items: start;
      min-width: anchor-size(width);
      max-width: min(360px, calc(100vw - 16px));
      max-height: calc(100vh - var(--lf-banner-h) - 20px); overflow-y: auto;
      overscroll-behavior: contain;
      background: var(--card); border: 1px solid var(--border-2); border-radius: var(--r);
      box-shadow: 0 8px 24px rgba(0,0,0,.12); padding: 4px; }
    .lf-version-menu.open { display: grid; }
    /* Left-aligned text in a control that is otherwise a press: the rows are a list to
       read down, and a centred note re-ragged on every line is not one. */
    .lf-version-row { grid-column: 1; position: relative;
      display: flex; flex-direction: column; gap: 1px; align-items: start;
      text-align: left; padding: 6px 8px; border: 0; border-radius: 4px;
      background: none; color: inherit; cursor: pointer; width: 100%; }
    .lf-version-row:hover { background: var(--chip); }
    .lf-version-row:focus-visible { outline: var(--here-ring); outline-offset: -2px; }
    /* The version being read wears the accent rather than a fill, so the row the
       pointer is over stays the one that looks pressable. */
    .lf-version-row[aria-current] .lf-version-num { color: var(--accent); font-weight: 600; }
    .lf-version-num { white-space: nowrap; }
    .lf-version-note { color: var(--muted); font-size: var(--t-6); }
    /* The comparison a row offers: mark what changed between that version and the one
       being read. It draws its own box rather than waiting for a hover to draw one,
       which is the same rule a group taking a pick keeps: a form may decide how it
       looks and may not decide whether it says it takes an answer, and a wash that
       arrives on hover arrives after the reader has committed the pointer. Lit from
       aria-checked rather than a class of its own, the state being the button's to
       state — a menuitem may not be pressed, a menu's toggle being a
       menuitemcheckbox, which axe said of the aria-pressed this started as on the one
       page in the suite that asks with the menu standing open. */
    .lf-version-diff { grid-column: 2; margin: 4px 2px 0 4px; padding: 3px 8px;
      border: 1px solid var(--rule); border-radius: 4px; background: none;
      color: var(--ink-2); cursor: pointer; font-size: var(--t-6); line-height: 1.4; }
    .lf-version-diff:hover { border-color: var(--border-2); background: var(--chip); }
    .lf-version-diff:focus-visible { outline: var(--here-ring); outline-offset: -2px; }
    .lf-version-diff[aria-checked="true"] { border-color: var(--accent); color: var(--accent);
      background: var(--chip); }
    /* A diff is a span rather than a point — everything that changed across the versions
       from its base to the one being read — and a base three versions back says something
       very different from the one before. The rail is that span, drawn down the rows it
       covers: inside the row's own box, so it is paint and moves nothing, and drawn on
       the rows rather than the presses because the rows are the run that touch. */
    .lf-version-row.lf-compared::before { content: ""; position: absolute;
      left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent); }
    /* The leaves panel: the comment panel's mirror on the left, a board of the
       machine's live pages that stands while the reader works. Fixed over the content —
       opening it moves nothing — and its own scroll region, so one wheel gesture moves
       one region. */
    .lf-others-panel { position: fixed; top: var(--lf-banner-h); left: 0; bottom: 0; z-index: 8900;
      width: min(300px, 100vw); background: var(--card); border-right: 1px solid var(--rule);
      display: none; padding: 6px 4px; overflow-y: auto; overscroll-behavior: contain; }
    .lf-others-panel.open { display: block; }
    .lf-others-row { display: block; padding: 8px 10px; border-radius: 6px; color: inherit;
      text-decoration: none; }
    a.lf-others-row:hover { background: var(--chip); }
    .lf-others-row:focus-visible { outline: var(--here-ring); outline-offset: -2px; }
    .lf-others-head { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .lf-others-title { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden;
      text-overflow: ellipsis; }
    /* Indented past the dot's 9px and its 8px gap, so the line reads under the title;
       one line, ellipsized, so a detail growing repaints its own words and moves
       nothing. */
    .lf-others-line { color: var(--ink-2); margin-left: 17px; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }
    /* The asks board: the leaves board's twin, on the same edge and one at a time with it
       (showEdge), because the two are the same furniture at two scopes. Every metric here
       is that board's, said once for both — a reader who has both keys should not find
       two different regions where they learned one. What differs is the row: a leaf's row
       is a link out to another page, and an ask's is a press that moves this one, so it is
       a button and takes the button's own reset. */
    .lf-asks-panel { position: fixed; top: var(--lf-banner-h); left: 0; bottom: 0; z-index: 8900;
      width: min(${EDGE_W}px, 100vw); background: var(--card); border-right: 1px solid var(--rule);
      display: none; padding: 6px 4px; overflow-y: auto; overscroll-behavior: contain; }
    .lf-asks-panel.open { display: block; }
    .lf-asks-row { display: block; width: 100%; text-align: left; padding: 8px 10px;
      border: 0; border-radius: 6px; background: none; color: inherit; font: inherit;
      cursor: pointer; }
    .lf-asks-row:hover { background: var(--chip); }
    .lf-asks-row:focus-visible { outline: var(--here-ring); outline-offset: -2px; }
    /* What kind of thing is asking, in the apparatus voice, over the ask's own words in
       the page's. Two lines, because they are two claims: the kind is the runtime's word
       for the element and the words below it are the page's own. */
    .lf-asks-kind { display: block; color: var(--muted); font-size: var(--t-6);
      text-transform: uppercase; letter-spacing: .05em; }
    /* Three lines at most, then ellipsized: an ask's opening words are a name here, and a
       name that runs to eight lines stops being one — while a single line would cut most
       questions off before they said which question they were. */
    .lf-asks-says { display: -webkit-box; -webkit-box-orient: vertical;
      -webkit-line-clamp: 3; overflow: hidden; }
    /* The one control on the right of the row that may give, because it is the leftmost
       of them and giving there moves nothing; the status text, off at the other end, is
       the other. The rest are .lf-btn, floored at their own words by nowrap — the chooser
       was the exception, so a row with no room left took the width it states back off it,
       which put every reservation above back in play on any narrow enough window. */
    .lf-latest-chip { background: var(--warn-tint); border: 1px solid var(--warn); color: var(--warn-ink); border-radius: 6px; padding: 3px 8px; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
    .lf-panel { position: fixed; top: var(--lf-banner-h); right: 0; bottom: 0; width: min(${PANEL_W}px, 100vw); z-index: 8900;
      background: var(--card); border-left: 1px solid var(--rule); display: none; flex-direction: column; }
    .lf-panel.open { display: flex; }
    .lf-panel-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--rule); font-weight: 600; }
    /* contain: reaching the end of the thread list must not start scrolling the page
       behind it — one wheel gesture moves one region.
       The frame is declared because the inset is read at both ends of a scroll region:
       the list opened 10px above its first thread and stopped 22px under the last, the
       last thread's own 12px having nowhere to collapse to. See theme.css. */
    .lf-threads { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 10px 14px; --lf-frame: 1; }
    /* An Escape rung lands here (general box → the list), so the rung is visible. */
    .lf-threads:focus-visible { outline: var(--here-ring); outline-offset: -2px; }
    .lf-empty { color: var(--muted); padding: 18px 4px; }
    /* A thread and the room a resolved one is still giving back (foldOut) are the same
       box, so the fold starts from the box the reader was looking at rather than from
       a second description of it. What .lf-going adds is the clip the fold needs and
       the outcome said in paint: the box is on its way out and may not also state
       that in metrics the fold is animating. */
    .lf-thread, .lf-going { --lf-thread-pad: 10px; position: relative; border: 1px solid var(--rule); border-radius: var(--r); padding: var(--lf-thread-pad); margin-bottom: 12px; --lf-frame: 1; }
    .lf-going { overflow: hidden; box-sizing: border-box; }
    /* The outcome rides the closing edge, so it is legible for the whole fold rather
       than for the frame before the box swallows it: the actions row is the thread's
       last line, and a fold from the bottom takes it first. Pinned to the box's own
       bottom padding, which is where it already sits in flow, so the fold starts from
       the layout the reader was looking at and nothing shifts on the press. It occludes
       what it passes (background) rather than reading through it, and it says the
       outcome in ink, since the metrics here are what the fold is animating. */
    .lf-going .lf-thread-actions { position: absolute; inset: auto var(--lf-thread-pad) var(--lf-thread-pad); background: var(--card); }
    .lf-going .lf-thread-send { visibility: hidden; }
    .lf-going .lf-resolve { color: var(--ok); }
    .lf-thread.flash { animation: lf-runtime-4f3c2a8d-flash 1.2s ease-out; }
    /* An arrival the reconcile added while the user was watching. Motion, not a
       jump: nothing above it moves, and the newcomer settles rather than appears. */
    .lf-thread.grow, .lf-msg.grow { animation: lf-runtime-4f3c2a8d-grow .32s cubic-bezier(.2,.7,.3,1); }
    .lf-thread:focus-visible { outline: var(--here-ring); outline-offset: 2px; }
    .lf-quote { margin: 0 0 8px; padding: 2px 8px; border-left: 3px solid var(--mark-ink); color: var(--muted); font-style: italic; cursor: pointer; overflow-wrap: anywhere; }
    .lf-quote:hover { color: var(--ink-2); }
    /* A quote is the passage, and a passage is as long as the reader's selection — a
       paragraph of it in a 320px column buries the words written about it. So the panel
       names the passage in three lines and the page shows the rest: the mark is already
       on it, and the quote is what one clicks to go there. The composer's copy is
       scrolled rather than clipped a few rules down, because it stands alone in a box
       the reader is typing into and has no thread beneath it to bury. */
    .lf-thread .lf-quote { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
    .lf-quote.detached { border-left-style: dashed; border-left-color: var(--border-2); color: var(--muted-2); cursor: default; }
    /* Out of the picture, still in the accessibility tree — see the composer's quote in
       paintAnchors for the one thing that wears this and why. */
    .lf-unseen { position: absolute; width: 1px; height: 1px; padding: 0; border: 0; overflow: hidden; clip-path: inset(50%); }
    .lf-msg { margin: 8px 0; }
    /* Who and when, on one line above the words: apparatus, so the row states the
       apparatus rung once and the two differ by weight and ink rather than by size. They
       carried 12.5px and 11.5px, a pixel apart for no reason either could give, and the
       11.5 was --t-6 written out. */
    .lf-msg-head { display: flex; gap: 6px; align-items: baseline; font-size: var(--t-6); }
    .lf-msg.claude .lf-msg-head b { color: var(--accent); }
    .lf-msg time { color: var(--muted-2); }
    /* A message body is rendered Markdown, which is why this dresses a box and not a
       paragraph. The theme's element rules are at document level and reach in here, so a
       reply's lists, code, quotes and tables already read as the page's do; what is left
       is the panel's narrower column — tighter blocks, headings that don't shout at
       360px, and no margin where the body meets its own head. */
    .lf-msg-body { margin: 2px 0 0; overflow-wrap: anywhere; }
    /* A streamed message still arriving wears a pulsing caret after its last
       words. Generated with empty content — paint, not words, so no reading of
       the page (a screen reader, the clipboard) picks it up — and only while
       the page presents as working (syncMsg): a chain the agent abandoned reads
       as a finished message rather than a promise nobody is keeping. */
    .lf-msg.lf-streaming .lf-msg-body::after { content: ""; display: inline-block; width: 2px; height: 1em; margin-left: 2px; vertical-align: text-bottom; background: var(--accent); animation: lf-stream-caret 1s steps(2, jump-none) infinite; }
    @keyframes lf-stream-caret { 50% { opacity: 0; } }
    .lf-msg-body > :first-child { margin-top: 0; }
    .lf-msg-body > :last-child { margin-bottom: 0; }
    .lf-msg-body :is(p, ul, ol, pre, blockquote, table, hr) { margin: 6px 0; }
    /* Prose here breaks anywhere, because the thing a reply overflows on is a URL
       no wrap can help. A table is the one block in a reply with somewhere else to
       put the width — the theme makes it scroll inside itself — so breaking its
       cells to save that room spends the alignment the table was written for:
       "12,000" arrived as "12,0" over "00", in a column of figures to compare. */
    .lf-msg-body :is(th, td) { overflow-wrap: normal; }
    .lf-msg-body :is(h1, h2, h3, h4, h5, h6) { margin: 8px 0 4px; font-size: var(--t-5); }
    .lf-msg-body li { margin: 2px 0; }
    .lf-msg-body pre { padding: 8px 10px; }
    .lf-msg-body blockquote { padding: 2px 10px; }
    /* A reference to an element this version hasn't got, wearing the same word the
       quote above wears for the same fact. The whole text-decoration shorthand,
       because a widget's § reference (lf-ref) undressed its underline and a style
       alone would paint nothing there. paintAnchors is the one writer. */
    .lf-msg-body a.detached { color: var(--muted-2); text-decoration: underline dashed; cursor: default; }
    .lf-compose { display: block; margin-top: 8px; }
    .lf-compose textarea { display: block; width: 100%; min-width: 0; }
    /* The general Send stays beside its field; a thread gives the field its own row. */
    .lf-general { display: flex; gap: 6px; margin-top: 8px; align-items: flex-end; }
    .lf-general textarea { flex: 1; min-width: 0; }
    .lf-thread-actions { display: flex; justify-content: space-between; margin-top: 8px; }
    .lf-thread-action { border: none; background: none; color: var(--muted); cursor: pointer; }
    .lf-thread-action:hover { color: var(--ok); }
    .lf-resolved-by { color: var(--muted); }
    .lf-general { padding: 10px 14px; border-top: 1px solid var(--rule); }
    .lf-details { margin-top: 6px; color: var(--muted); background: none; border: none; padding: 0; }
    .lf-system { color: var(--ok); margin: 8px 0; }
    /* The two floats that point at the page live in the document's coordinate space
       (absolute, body their containing block), because what they point at does: a
       composer that held its viewport spot while the page scrolled sat pinned over
       whatever arrived under it, no longer beside the item it was about. Everything
       else here is the viewport's own chrome and stays fixed. Below the banner's
       9000, so a float scrolled to the top slides under the bar, not over it. */
    /* The 💬 stands out on the page, beside the reader's own words and in the same
       margin a change's ✓ Accept hangs in — often on the same line, which is how the
       two came to be compared. It used to answer that comparison badly: a solid accent
       rectangle at the chrome's own size against two hairline pills, so the page's
       margin held two idioms four centimetres apart and the louder one was the one
       raised over the reader's sentence. Where a control stands decides which it
       wears. In the runtime's own furniture — the banner, the panel, the composer — a
       press is a .lf-btn and looks like one; out in the margin it is a .lf-pill, the
       marginal mark stated once at document level where the theme's margin controls
       wear it too.

       The shadow is the one thing this control adds, and it earns it: this is the only
       pill that floats over the page's own content rather than standing in the empty
       rail, so it says so rather than relying on a hairline to separate it from
       whatever it happens to be over. */
    .lf-fab { position: absolute; z-index: 8950; display: none;
      box-shadow: 0 2px 6px rgba(0,0,0,.14); }
    /* The ⌥ aim's promise: the item a press would take, whole. Drawn here in the
       chrome's own layer rather than painted onto the element, because no band of a
       page element is reliably the runtime's to paint in — the mark comment at
       document level holds the inventory (outside the border, an enclosing scroller
       clips; inside it, a choose group's own cells paint over; the border band is
       wherever the widget's own border already is). A standing mark can live with the
       hairline that survives all that, because an annotation is something a reader
       can hunt for. A promise cannot: it answers a held key at a glance, and over a
       card whose 1px border is already the accent — every recommended option — the
       arm changed nothing a reader could see, which was reported as no box at all.
       The layer over the page is the runtime's by construction, so the aim is stated
       there instead, from the aimed element's geometry: a veil that says how much a
       press takes and a ring that says where it stops, over everything the page can
       paint — an lf-shot frame flush to its own edges included. pointer-events
       stands down so the press this box promises, and every elementFromPoint behind
       the promise, still lands on the item under it. Document-anchored like the
       floats above (place), so a scroll moves it with the page between the events
       that re-derive it; under the floats themselves, which are chrome the reader
       works rather than paint about the page. */
    .lf-aim { position: absolute; z-index: 8920; display: none; pointer-events: none;
      border: 2px solid var(--accent);
      background: color-mix(in srgb, var(--accent) 8%, transparent); }
    .lf-composer { position: absolute; z-index: 8950; display: none; width: 320px; background: var(--card);
      border: 1px solid var(--border-2); border-radius: var(--r); box-shadow: 0 8px 24px rgba(0,0,0,.12); padding: 10px; }
    /* A stranded quote is the whole passage, and the box is 320px wide. Only while showing:
       on the hidden one this would out-specify .lf-unseen's own overflow. */
    .lf-composer .lf-quote:not(.lf-unseen) { max-height: 4.2em; overflow-y: auto; }
    .lf-suggest-row { display: none; align-items: center; gap: 6px; margin: 0 0 6px; color: var(--muted); font-size: var(--t-6); cursor: pointer; }
    .lf-suggest-row input { margin: 0; accent-color: var(--accent); }
    .lf-suggest-label { font-size: var(--t-6); letter-spacing: .05em; text-transform: uppercase; color: var(--ok-ink); margin: 4px 0 2px; }
    /* A suggestion renders verbatim — its characters are what the next version
       carries (see msgNode) — so this is where they keep their own line breaks. */
    .lf-msg-body.lf-suggest-body { background: var(--add-tint); padding: 4px 8px;
      border-radius: 6px; white-space: pre-wrap; }
    .lf-composer textarea { width: 100%; min-height: 56px; }
    .lf-composer-row { display: flex; justify-content: flex-end; gap: 6px; margin-top: 6px; }
    .lf-toast { position: fixed; bottom: 18px; right: 18px; z-index: 9200; max-width: calc(100vw - 36px);
      overflow-wrap: anywhere; background: var(--ink); color: var(--paper); padding: 9px 14px;
      border-radius: var(--r); opacity: 0; transition: opacity .25s, right .18s ease; pointer-events: none; }
    .lf-toast.show { opacity: .95; }
    .lf-toast.clickable { pointer-events: auto; cursor: pointer; }
    .lf-live { position: fixed; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
    .lf-help { position: fixed; z-index: 9300; top: 50%; left: 50%; transform: translate(-50%, -50%);
      width: min(420px, calc(100vw - 32px)); max-height: 80vh; overflow-y: auto; display: none;
      background: var(--card); border: 1px solid var(--border-2); border-radius: var(--r);
      box-shadow: 0 12px 32px rgba(0,0,0,.18); padding: 14px 18px; }
    .lf-help.open { display: block; }
    .lf-help-title { font-weight: 600; margin-bottom: 10px; }
    .lf-help h3 { margin: 12px 0 4px; font-size: var(--t-6); font-weight: 600;
      text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
    .lf-help table { width: 100%; border-collapse: collapse; }
    .lf-help td { padding: 3px 0; vertical-align: baseline; }
    .lf-help td:first-child { width: 84px; white-space: nowrap; }
    /* The glyph states its own ink rather than taking the line's. A key chip is the
       one word on either surface the reader has to read to press anything, and on
       --chip the surrounding line's --muted came to 4.46:1 — under AA, and quietly,
       since the line is aria-hidden and the corpus sweep walks pages with it empty.
       --ink-2 clears it on both schemes. The words beside the chips keep --muted:
       they sit on --card, which it clears.

       One size for both surfaces, because a key chip is one thing wherever the reader
       meets it — the same reason .lf-address is stated once for the panel and the page.
       It is the apparatus rung, where the 12px it held was half a pixel off one. */
    .lf-help kbd, .lf-keyline kbd { font-family: ui-monospace, monospace; font-size: var(--t-6); background: var(--chip);
      color: var(--ink-2);
      border: 1px solid var(--border-2); border-radius: 4px; padding: 1px 6px; }
    /* The key line: what a key does right now, rendered from the register the
       dispatcher walks (see the module docstring). Floating chrome nothing presses
       (pointer-events none) and the eye's copy of facts spoken elsewhere
       (aria-hidden), so it owes the press sweep nothing; syncLayout lifts it over a
       covering sheet the way it lifts the toast, and body reserves its height so
       the document's last lines never end under it. The overflow is the backstop
       under renderLine's own measured drop, for a window too narrow to hold even the
       chips it keeps — it was the whole mechanism once, and a chip clipped mid-word
       reads as a bug where a dropped one reads as a legend. */
    .lf-keyline { position: fixed; left: 18px; bottom: 14px; z-index: 8940; pointer-events: none;
      display: flex; gap: 12px; align-items: baseline; max-width: calc(100vw - 36px);
      overflow: hidden; color: var(--muted); font-size: var(--t-6); white-space: nowrap;
      background: var(--card); border: 1px solid var(--rule); border-radius: var(--r);
      padding: 5px 10px; }
    .lf-keyline:empty { display: none; }
    .lf-keyline .lf-key { display: inline-flex; gap: 5px; align-items: baseline; }
    .lf-keyline kbd.armed { border-color: var(--accent); color: var(--accent); }
    /* Design mode: the reader is commenting on the layer rather than the page, and for
       as long as they are the page shows its bones. Every item — a widget, a section, a
       heading with an id — wears a legend box: a dashed hairline in the chrome's layer,
       drawn from the item's geometry the way the aim's box is (paintLegend), one pixel
       outside the border box so a thread's mark, one pixel inside it, still shows
       through. Every item but a widget's parts wears its name above the box's corner
       too — the tag and id a fix is written against, the words the composer and the
       thread will carry — and the parts (a card, an option, a milestone: what x-parent
       declares) keep the hairline alone and are named under the pointer, or a board
       would wear a tag on every card and say nothing. Dashed rather than solid because
       the solid hairline is the mark's (.lf-mark-el), and a legend is not an
       annotation. Under the pointer the aim's box lifts one item out of the legend
       (.lf-aim) and its full name — the control's word included — floats where the tag
       stood (.lf-inspect); the banner takes an accent wash so the mode reads at the top
       edge as well. Nothing here is something to press: pointer-events stands down so a
       click still lands on the item the box outlines. */
    /* The g chord's addresses: a chip per member of the list it has aimed at, in a layer
       of the chrome's own so a digit can be hung on a link set mid-sentence without a
       span being written into the paragraph. Fixed, because the members are in three
       different scrollers — the document, the comment panel, a board's own overflow — and
       one layer that follows none of them is what lets a single pass place them all from
       the viewport rects it just read; the pass runs again when anything scrolls under
       it. Each chip is centred on the corner its member starts at — the first line of an
       inline that wraps, not the whole box it spans — half in and half out, the place a
       reply box's chip has always been drawn. Nothing here is something to press. */
    .lf-addresses { position: fixed; inset: 0; z-index: 9070; pointer-events: none; }
    .lf-addresses > .lf-address { position: absolute; display: block;
      transform: translate(-50%, -50%); }
    /* Under the banner there is no room to straddle the corner, so the chip hangs below
       the covered edge instead — the same step the legend's tag makes, and the same class
       name, because it is the same fact about the same bar. */
    .lf-addresses > .lf-address.lf-in { transform: translate(-50%, 0); }
    .lf-legend-box { position: absolute; z-index: 8910; pointer-events: none;
      box-sizing: border-box;
      border: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent); }
    .lf-legend-tag { position: absolute; left: -1px; bottom: 100%; max-width: 40vw;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      padding: 0 5px; border-radius: 3px 3px 0 0; font-size: var(--t-6); line-height: 1.5;
      background: color-mix(in srgb, var(--accent) 12%, var(--card)); color: var(--accent);
      border: 1px solid color-mix(in srgb, var(--accent) 55%, transparent); border-bottom: 0; }
    /* Under the banner there is no room above the box, so the tag sits inside its
       corner instead. */
    .lf-legend-box.lf-in .lf-legend-tag { bottom: auto; top: 0; border: 0;
      border-radius: 0 0 3px 0; }
    .lf-banner.lf-designing { background: color-mix(in srgb, var(--accent) 14%, var(--veil)); }
    /* Document-anchored like the box it names (paintInspect adds the scroll), so the
       two move together between the events that re-derive them. */
    .lf-inspect { position: absolute; z-index: 9060; pointer-events: none; display: none;
      max-width: 60vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      padding: 1px 6px; border-radius: 3px; font-size: var(--t-6); line-height: 1.5;
      background: var(--accent); color: var(--paper); }
    .lf-inspect.lf-shown { display: block; }
  }
`;
document.head.appendChild(style);

// ---------- scaffold ----------
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

const banner = el("div", "lf-ui lf-banner");
const dot = el("span", "lf-dot");
const statusText = el("span", "lf-status-text", "Connecting…");
// The controls the banner's news arrives as, each present only while it has
// something to say. Room a control has once taken is room it keeps for the rest of the
// page's life: before it first appears there is nothing to hold, so a page that never
// falls behind pays nothing for the chip, and once one has stood somewhere the others
// can't close ranks over it — a second tab deciding the last pending suggestion took the
// ✓ Accept all away and slid the New-version chip 148px right, under whoever was
// reaching for it. Reserving from the start instead would hold room on every row for news
// that page will never get, which shows as a gap the moment one of them is there and its
// neighbour isn't; reserving nothing is the movement. This spends only where the
// alternative is a control moving, and only on the pages that got the news.
//
// One setter stating the whole outcome, per showComposer and showFab, so no caller has
// to know which of the two ways of being absent this control is currently in.
const showNews = (control, on) => {
  if (on) control.dataset.lfStood = "1";
  control.style.display = on || control.dataset.lfStood ? "" : "none";
  control.style.visibility = on ? "" : "hidden";
};
const latestChip = el("button", "lf-ui lf-btn lf-latest-chip", "");
// The keyboard reaches this through the chooser rather than past it: v opens the menu, and
// the letter again takes the newest version. The chip names that motion, spelled from the
// two rows that make it rather than typed out beside them.
latestChip.title = "Open the newest version";
// What the page is still waiting on the reader for, and the way to the next one — the
// same list n/p step and the "?" overlay names, counted here so a reader who
// has not scrolled that far still knows there is something to answer.
const asksBtn = el("button", "lf-btn lf-asks", "");
asksBtn.title = "Go to the next thing this page is waiting on you for";
// The machine's live leaves and what each is doing: a left panel of rows, each a
// link opening that page in its own tab, judged by the same `presented` the banner
// answers with, from the same facts — `others` on /api/state carries them for every
// live page, and every URL in the list carries only the key this reader already
// holds, since there is one key for the machine (`host_key`). The current page heads
// the list as a marked, unlinked row, so the panel reads as the whole machine. A
// status board's point is being live, so rows reconcile on every poll, keyed by URL —
// the stable identity, since address, port and key all survive a restart — and a
// status change repaints the row's own dot and words without moving it.
const othersBtn = el("button", "lf-btn lf-others", "");
othersBtn.title = "Leaves live on this machine, and what each is doing";
// A nav, because navigation is what it is and a bare div may not carry the
// aria-label the card needs (axe: aria-prohibited-attr, serious).
const othersPanel = el("nav", "lf-ui lf-others-panel");
othersPanel.setAttribute("aria-label", "Leaves on this machine");
let others = [];
// A board of the page's own open asks, on the same edge: one row per thing the page is
// waiting on the reader for, in the order the page asks them. The list is openAsks() and
// nothing else, so a widget joins the board by declaring x-awaits and no row here knows
// what kind of thing it is standing for.
const asksPanel = el("nav", "lf-ui lf-asks-panel");
asksPanel.setAttribute("aria-label", "What this page is waiting on you for");

// The left edge holds one board at a time. Leaves and asks are the same furniture asking
// at two scopes — which page needs me, and what this page needs of me — and each has to
// stand while the reader works, which is the whole reason either is a fixed edge rather
// than a menu over the page. So which one is up is one fact held in one place. A boolean
// per board would be one guarantee written twice, and the two would first disagree on the
// day a third surface opened one without closing the other; the reader would then have
// two boards over one edge with the lower one unreachable.
//
// Registered rather than listed, for the same reason the widgets are: the toggle, the
// press, the reload and the Escape rung all read this map, so a third board joins by
// registering and none of them names a board to do its job.
const edges = new Map();
const EDGE_KEY = "lf-edge-board";
// The board survives a reload like the comment panel does (see PANEL_KEY): reloading is
// not resetting, and a board someone stood up to watch stays stood. Null until the
// restore at the foot of this module puts it back, which it does by opening the board
// the way a press does. Reading the store into this declaration instead is what made
// registration a second opener, and a second opener here can reach almost nothing: it
// runs while this module is still evaluating, so the page's own asks — declared
// thousands of lines below — are not initialized yet, and the reader who had left the
// board standing got a ReferenceError where their page should have been.
let edgeUp = null;
const openEdge = (key) => edgeUp === key;
function showEdge(key) {
  if (edgeUp === key) return;
  edgeUp = key;
  for (const [name, { panel, btn, paint }] of edges) {
    const open = name === key;
    btn.setAttribute("aria-expanded", String(open));
    if (open) {
      // Filled before it is shown, so the board is its own list from the first frame of
      // the slide rather than a blank card that populates a moment later. The way down
      // is the mirror of it, below: emptied once it is hidden, never before, or the
      // reader watches the list they just closed blank out and an empty card slide away.
      paint?.();
      panel.classList.add("open");
      motion(
        panel,
        [{ transform: "translateX(-100%)" }, { transform: "translateX(0)" }],
        200,
      );
    } else if (panel.classList.contains("open")) {
      // Slid out before hidden, and hidden only if still closed on arrival — a
      // reopen mid-slide leaves the panel standing rather than racing the finish.
      const out = motion(
        panel,
        [{ transform: "translateX(0)" }, { transform: "translateX(-100%)" }],
        160,
      );
      const hide = () => {
        if (edgeUp === name) return; // reopened mid-slide; it stays up, list and all
        panel.classList.remove("open");
        paint?.();
      };
      if (out) out.finished.then(hide, () => {});
      else hide();
      if (panel.contains(document.activeElement)) btn.focus();
    }
  }
  readerStore.set(EDGE_KEY, key ?? "");
  // Which board is up, on the document, so the stylesheet can say what each one costs the
  // page's own box. One writer for it, here, beside the one variable that holds the fact.
  if (key) document.body.dataset.lfEdge = key;
  else delete document.body.dataset.lfEdge;
  paintHere();
}
// Registration and nothing else: no board is up while this module is evaluating, and
// the one the reader left standing goes up in the restore section at the foot of the
// file, through showEdge. So there is one opener, and every fact that carries "this
// board is up" is written where it is decided.
function edgeIs(key, panel, btn, paint) {
  edges.set(key, { panel, btn, paint });
  btn.onclick = () => showEdge(openEdge(key) ? null : key);
  btn.setAttribute("aria-expanded", "false");
}
edgeIs("leaves", othersPanel, othersBtn);
edgeIs("asks", asksPanel, asksBtn, () => renderAsks(openAsks()));
// A persisted board is state-dependent chrome: Asks folds the log and Leaves comes from
// the first state response. Keep the remembered intent in edgeUp, but restore its pixels
// only once that response has produced the page's presentation. Unlike showEdge, this
// first paint does not animate — it is part of the page arriving, not a reader gesture.
function restoreEdge() {
  if (!edgeUp) return;
  const edge = edges.get(edgeUp);
  if (!edge) return;
  edge.btn.setAttribute("aria-expanded", "true");
  edge.paint?.();
  edge.panel.classList.add("open");
  document.body.dataset.lfEdge = edgeUp;
}
// Each board's one offer: something to show, or the board already standing — the key that
// opened it must still close it, and its button must still be pressable. The button's
// visibility and the key both ask the board's own predicate, so the two surfaces cannot
// disagree about whether there is a board to open. A leaves board of one — the page the
// reader is already on — is not worth a control; an asks board of none is the same.
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const boardOffered = () => pagePresented() && (others.length > 0 || openEdge("leaves"));
const asksOffered = () =>
  pagePresented() && (openAsks().length > 0 || openEdge("asks"));
// The board's own scope. The walk is the board's rather than the page's, because ArrowUp
// and ArrowDown anywhere else are the page's own scroll and stay so; Enter is the
// browser's, a row being a link, and the row says so with no `run` to give. The reader
// arrives here by key — `l` lands focus on the first neighbour — so the scope names what
// activating does rather than leaving it to the platform's own contract.
const othersLinks = () => [...othersPanel.querySelectorAll("a.lf-others-row")];
const askRows = () => [...asksPanel.querySelectorAll("button.lf-asks-row")];
// The asks board's own walk, the leaves board's twin: ArrowUp and ArrowDown are the page's
// scroll everywhere else and the board's here, and Enter is the platform's, a row being a
// button — so the scope names what walking does and leaves the press to the button.
keys(asksPanel, "In the asks board", [
  {
    keys: ["ArrowUp", "ArrowDown"],
    does: "Walk the asks",
    line: "walk the asks",
    repeat: true,
    run: (binding) => walkRows(askRows(), binding === "ArrowDown" ? 1 : -1),
  },
  {
    keys: ["Enter"],
    does: "Go to this ask and stand on the control that answers it",
  },
]);
keys(
  othersPanel,
  "In the leaves panel",
  [
    {
      keys: ["ArrowUp", "ArrowDown"],
      does: "Walk the leaves",
      line: "walk the leaves",
      repeat: true,
      run: (binding) => walkRows(othersLinks(), binding === "ArrowDown" ? 1 : -1),
    },
    // Enter is the browser's here, the row being a link — no `run`, because binding it
    // would click a control the platform has already activated. It carries a word all the
    // same: the press is real and immediate where the reader is standing, which is what
    // the line is for.
    { keys: ["Enter"], does: "Open that leaf in a tab", line: "open it in a tab" },
  ],
  boardOffered, // the scope's own liveness: a board with something to walk
);
// A row's whole account of a page: the dot's tone and one line of words, from the
// same judgment the banner's sentences come from — the judgment is shared, the
// wording is the seat's.
const TONE = {
  working: "working",
  listening: "listening",
  away: "away",
  unheld: "",
  unattended: "",
  closed: "",
};
function rowPresence(entry) {
  const { kind, quiet, detail } = presented(entry);
  // The same join for both kinds that have words of their own. The reader opens this
  // panel to find which page needs them, so a bare `Awaits` beside a neighbour's
  // `Working — recording the demo` said least about the one row they are here to act
  // on: three pages waiting rendered as three identical rows, and which to go to
  // first is the whole question the panel was opened to answer.
  const stated = (word) => word + (detail ? " — " + detail : "");
  const line =
    kind === "working"
      ? stated("Working")
      : kind === "listening"
        ? stated("Awaits")
        : kind === "away"
          ? quiet
            ? `Quiet (${ago(entry.status.ts)})`
            : "Away"
          : kind === "unheld"
            ? "Unheld"
            : kind === "unattended"
              ? "Unattended"
              : "Closed";
  return { tone: TONE[kind], line };
}
// The whole of what the board knows about one page, for its hover. Everything drawn
// on a row is cut to the panel's fixed width — the title ellipsizes, the line
// ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
// session behind the leaf is working. A title is a sentence somebody wrote and two
// pages a week apart share one; the work each came out of is the thing the reader
// already holds in their head, so it is worth the room a hover has and a row hasn't.
//
// One tooltip for the row rather than one per part. The innermost title wins where two
// overlap, so a title left on the line would answer the hover most likely to be asking
// this question — a reader pointing at the words that ran out of room — with the one
// part of the account they can already read.
const rowAccount = (entry, title, line) =>
  [
    title,
    entry.session_cwd,
    line,
    // The reader's own words that page's agent hasn't taken in. The banner says this
    // number for this page; the board says it for every page, which is the seat's
    // whole point — a leaf holding something of yours that nobody has read is a
    // reason to go there, and nothing else on the row says so.
    entry.pending && `${entry.pending} update${entry.pending === 1 ? "" : "s"} waiting`,
  ]
    .filter(Boolean)
    .join("\n");
const othersRows = new Map(); // keyed by URL; the self row under its own key
function renderOthers(state) {
  // An older server ships no list, which is an empty one. A closed leaf is not
  // one of the machine's live pages and drops out of the board on the poll that says
  // so: its server stays up so the page stays readable — a standing one for good —
  // so nothing else would ever take the row off, and a count the reader glances at
  // to find who needs them would silently become a tally of everything that has run
  // here. Judged by the same `presented` the rows read, never by a second reading of
  // the status the server ships. This page's own row is not in the list and so is
  // never dropped: a reader looking at a closed page is still looking at it.
  others = (state.others ?? []).filter((entry) => presented(entry).kind !== "closed");
  // While the panel stands its button stands too, whatever the count just did.
  showNews(othersBtn, boardOffered());
  const wanted = [
    { key: "self", title: document.title, entry: state },
    ...others.map((entry) => ({ key: entry.url, title: entry.title, entry })),
  ];
  // The button names the board it opens, so the count is these rows — the list the
  // press will show, headed by this page's own row — and never arithmetic beside
  // them. "Other leaves" counted the neighbours alone, one off the list it
  // promised: a machine with one neighbour said (1) over a board of two.
  othersBtn.textContent = `All leaves (${wanted.length})`;
  let anchor = null; // the row before this one, so order holds without rebuilding
  for (const { key, title, entry } of wanted) {
    let row = othersRows.get(key);
    if (!row) {
      // The self row is a marked div — the reader is already here, so there is
      // nothing to open; every other row is a link to its page's own tab.
      row =
        key === "self"
          ? el("div", "lf-others-row lf-others-self")
          : Object.assign(el("a", "lf-others-row"), {
              href: key,
              target: "_blank",
              rel: "noopener",
            });
      const head = el("div", "lf-others-head");
      head.append(el("span", "lf-dot"), el("span", "lf-others-title"));
      if (key === "self") head.append(el("span", "lf-pill", "this page"));
      row.append(head, el("div", "lf-others-line"));
      othersRows.set(key, row);
    }
    const { tone, line } = rowPresence(entry);
    const [rowDot, rowTitle] = row.querySelectorAll(".lf-dot, .lf-others-title");
    const rowLine = row.querySelector(".lf-others-line");
    // Written only on change: an unchanged poll must not feed the mutation stream
    // a screen reader rebuilds its buffer on.
    const dotCls = "lf-dot" + (tone ? " " + tone : "");
    if (rowDot.className !== dotCls) rowDot.className = dotCls;
    if (rowTitle.textContent !== title) rowTitle.textContent = title;
    if (rowLine.textContent !== line) rowLine.textContent = line;
    // Everything the row was too narrow to say, on the row itself (see rowAccount).
    const account = rowAccount(entry, title, line);
    if (row.title !== account) row.title = account;
    const place = anchor ? anchor.nextElementSibling : othersPanel.firstElementChild;
    if (place !== row) othersPanel.insertBefore(row, place);
    anchor = row;
  }
  for (const [key, row] of othersRows)
    if (!wanted.some((w) => w.key === key)) {
      row.remove();
      othersRows.delete(key);
    }
}
for (const control of [latestChip, asksBtn, othersBtn]) showNews(control, false);
// The version chooser: a press that says which version this is, and a menu that says
// what each one was and what it changed. It was a <select>, and the two things that
// cost were both the control's rather than the styling's. A select takes its inner
// height from Chrome's own metrics and refuses line-height, so it could never stand
// level with the buttons beside it; and its closed label is its selected option's whole
// text, so the note had to be in both places or neither — 190px of bar, the widest
// control on the row, for about nine characters of a note that then ellipsized. A press
// states the version alone, and the menu is the only place the notes are, where a row
// can wrap and carry one whole.
//
// The diff was a second press beside it, and everything the two shared was in the
// menu already. It named the previous version because a control with one label can
// offer one base, and the previous version is the least useful of them on a page that
// ships a version whenever the work moves: what the reader wants marked is what has
// changed since they last looked, which is as far back as they were away. The base is
// the menu's to say, so every version older than this one offers itself as one.
//
// Which version this is, is the document's own answer (VNUM, off the path), so the
// press says it now rather than standing empty until the first poll answers, and the
// only word it ever rewrites is the Δ that says a comparison is standing — enumerable,
// so the room for it is taken from the words themselves at load (reserve) and the
// control still cannot move the row. It is a word rather than the accent alone because
// a reader who leaves a comparison on and scrolls into a stretch that changed nothing
// has only this control to read it back off, and a colour is not a thing a screen
// reader announces.
const versionLabel = (comparing) =>
  (comparing ? "Δ " : "") + (VNUM === null ? "▾" : `v${VNUM} ▾`);
const versionBtn = el("button", "lf-btn lf-version", versionLabel(false));
versionBtn.setAttribute("aria-haspopup", "menu");
versionBtn.setAttribute("aria-expanded", "false");
const versionMenu = el("div", "lf-ui lf-version-menu");
versionMenu.setAttribute("role", "menu");
versionMenu.setAttribute("aria-label", "Versions");
let versionMenuOpen = false;
// The walk is the versions, not every press in the menu.
const versionRows = () => [...versionMenu.querySelectorAll(".lf-version-row")];
// One setter stating the whole outcome, per showComposer and showFab: nothing reads
// the class back to find out whether the menu is up.
function showVersionMenu(open) {
  versionMenuOpen = open;
  versionMenu.classList.toggle("open", open);
  versionBtn.setAttribute("aria-expanded", String(open));
  // Opening lands on the version being read, so the menu's own keys are the next
  // press rather than a Tab-hunt — the same move o makes into the leaves board.
  //
  // Or on the standing base, where a comparison is up, because inside this menu the focused
  // row *is* the base (the walk below). Landing on the version being read instead left the
  // two disagreeing at the one moment the reader cannot see it coming: their first arrow
  // press would have moved the base off the version they had marked from to the neighbour of
  // the one they are reading, silently, with the marks redrawn to match.
  if (open)
    (
      versionRows().find(
        (r) => r.dataset.lfVersion === String(diffOn ? diffBase : VNUM),
      ) ?? versionRows()[0]
    )?.focus();
  else if (versionMenu.contains(document.activeElement)) versionBtn.focus();
  paintHere();
}
versionBtn.onclick = () => showVersionMenu(!versionMenuOpen);
// The menu's own scope. The walk is the menu's rather than the page's, because ArrowUp and
// ArrowDown anywhere else are the page's own scroll; ⏎ is the browser's, a row being a
// button, and the row says so with no `run`. A row's Δ is the same comparison for the
// pointer, which has no walk to state it with, and takes no key of its own.
//
// v is the second half of the motion that opened the menu, and the one row worth a key of
// its own: the newest version is where the walk ends, and where a reader who came for the
// current state is going. The letter is the menu's here for the walk's own kind of reason
// — outside it, v is already the chooser — and being the inner scope's is what shadows the
// page's v, where the two listeners used to depend on one consuming the press.
//
// The scope is live while there is a list to walk, so the reference stops naming the menu
// on a page with one version — the liveness a widget's section gets for free by loading
// only where its widget is.
const NEWEST = {
  keys: ["v"],
  does: "Open the newest version",
  line: "open the newest version",
  // Through its own row's press, so the key leaves the menu by the door the pointer uses —
  // the menu closes and the pin lifts, both goVersion's and showVersionMenu's to say,
  // neither restated here. There is always a row to press: the scope holds only with focus
  // inside the menu, and an open lands focus on a row.
  run: () => versionRows().at(-1).click(),
};
keys(
  versionMenu,
  "In the versions menu",
  [
    {
      keys: ["ArrowUp", "ArrowDown"],
      // The walk marks as it goes, which is what the list is for: the note says in words
      // what a version changed and the page behind the menu then says it in the passages
      // themselves, without the reader having to leave the list to find out. A note is
      // Claude's sentence about a version and the marks are the version's own account of
      // itself, so reading them together is the only way to tell the two apart.
      does: "Walk the versions, marking what changed since the one you are on",
      line: "walk — marking changes",
      repeat: true,
      run: (binding) => {
        const was = document.activeElement;
        const row = walkRows(versionRows(), binding === "ArrowDown" ? 1 : -1);
        // A press at either end lands on the row it started from, and now that the walk
        // states a comparison, landing is not free — it would re-fetch the base and toast
        // its count again for a press that moved nothing.
        if (!row || row === was) return;
        // The comparison the row states: its own version as the base, or none at all where
        // that version is not older than the one being read. So the reader walks up to mark
        // from further back and back down to stop, and the row that stops it is the version
        // they are reading — the end of the walk in the direction they came from, which is
        // why it needs no key of its own and no reader has to be told where it is — and,
        // the page having no key for a comparison, the whole of the way off one.
        const version = +row.dataset.lfVersion;
        if (comparable(version)) showComparison(version);
        else setDiff(false);
      },
    },
    // The browser's own, the row being a real <button> — no `run`, or the press would click
    // a control the platform has already activated. The word is the line's all the same,
    // and the keys are the shared fact rather than this row's reading of it: spelled by
    // hand, it said Enter and left Space unnamed on a control that answers both.
    { keys: PRESS, does: "Open that version", line: "open that version" },
    NEWEST,
  ],
  () => versions.length > 1,
);
// The way out is the menu standing, not the reader being inside it: a menu opened and
// then Tabbed out of is still over the page, and an Escape that could not reach it left
// the reader closing the panel underneath instead. So the rung is a mode rather than the
// element scope's — which is what every other layer that can outlive its own focus does
// (the composer holds a draft the reader clicked away from; the leaves board stands while
// focus is on the button that opened it). The menu's walk stays the element scope's,
// because a walk has nothing to walk unless focus is on a row.
const VERSIONS = {
  title: "In the versions menu",
  // The same capability the menu's own scope states: a section gathers its liveness from
  // every contributor, so a mode that stays silent about it would speak for all of them.
  when: () => versions.length > 1,
  at: () => versionMenuOpen,
  // A mode over the page suspends the page, which the two modes above this one always did
  // and this one did not — so a reader in the middle of choosing a version could press `l`
  // and take focus out of the menu into the leaves board, `d` and scroll a page they were
  // not looking at, or `c` and open the composer under the list. None of it fails loudly:
  // the press does exactly what it says on a page the reader has stopped reading. The
  // worst of them was a page-level key that set a comparison base, which the walk they
  // were standing in then disagreed with — that key is the menu's own business now, and
  // the claim is what would have held it either way. The claim is also what narrows
  // the line to the menu's own keys, so what the mode takes and what it offers are one
  // statement rather than a suspension the surfaces have to be told about separately.
  claims: allButTheReference,
  rows: [
    {
      keys: ["Escape"],
      does: "Close the versions menu",
      line: "close versions",
      run: () => showVersionMenu(false),
    },
  ],
};
const toggleBtn = el("button", "lf-btn lf-comments", "Comments");
toggleBtn.title = "Show or hide the comment panel";
toggleBtn.setAttribute("aria-expanded", "false");
const approveBtn = el("button", "lf-btn primary lf-signoff", "✓ Looks good");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's ask is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
approveBtn.disabled = true;
banner.append(
  dot,
  statusText,
  el("span", "lf-spacer"),
  othersBtn,
  latestChip,
  asksBtn,
  versionBtn,
  toggleBtn,
);
if (SIGNOFF) banner.append(approveBtn);

const panel = el("aside", "lf-ui lf-panel");
const panelHead = el("div", "lf-panel-head");
const closeBtn = Object.assign(el("button", "lf-btn", "×"), {
  title: "Close (Esc)",
  onclick: () => setPanel(false),
});
closeBtn.setAttribute("aria-label", "Close comments");
panelHead.append(el("span", "", "Comments"), closeBtn);
const threadsBox = el("div", "lf-threads");
// An Escape rung: backing out of the general box lands on the list (visible ring,
// j/k walk on from it) rather than on nothing. -1 keeps it out of the Tab order.
threadsBox.tabIndex = -1;
const generalRow = el("div", "lf-general");
const generalInput = document.createElement("textarea");
const generalSend = el("button", "lf-btn primary", "Send");
generalRow.append(generalInput, generalSend);
panel.append(panelHead, threadsBox, generalRow);

const fab = el("button", "lf-ui lf-pill lf-fab", "💬 Comment");
// The aim's box (see its rule above). Empty and pointer-inert, so it says nothing to a
// screen reader and takes nothing from the press it promises; refreshAim is its one
// writer, and data-for is the aimed id stated where a test can read the promise.
const aimBox = el("div", "lf-ui lf-aim");
const composer = el("div", "lf-ui lf-composer");
// Only ever shown detached — paintAnchors, its one writer, keeps it out of sight while
// the page is marking the passage. lf-ui on the element itself, not just on the composer
// around it: this is the only injected chrome carrying an id, and "which section is this
// in" is asked as `[id]:not(.lf-ui)` of the element rather than of its ancestors, so
// without the class it answers that question with itself.
const composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
// Suggestion mode: the box holds replacement text for the quoted passage
// instead of a remark — Claude accepts it verbatim into the next version.
const suggestRow = el("label", "lf-suggest-row");
const suggestCheck = document.createElement("input");
suggestCheck.type = "checkbox";
suggestRow.append(suggestCheck, document.createTextNode("Suggest replacement text"));
const composerInput = document.createElement("textarea");
// The mark is a paint, and a paint is nothing to a screen reader (see "Paint; don't wrap"
// in CLAUDE.md). So what the box is anchored to travels as the box's own description,
// announced on focus — which is more than the visible quote ever said, since nothing
// pointed a reader at it.
composerInput.setAttribute("aria-describedby", composerQuote.id);
const composerRow = el("div", "lf-composer-row");
const composerCancel = el("button", "lf-btn", "Cancel");
const composerSend = el("button", "lf-btn primary", "Comment");
composerRow.append(composerCancel, composerSend);
composer.append(composerQuote, suggestRow, composerInput, composerRow);
const toastEl = el("div", "lf-ui lf-toast");
const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");
const helpEl = el("div", "lf-ui lf-help");
helpEl.setAttribute("role", "dialog");
helpEl.setAttribute("aria-label", "Keyboard reference");
helpEl.tabIndex = -1; // focused on open, so the dialog isn't silent to a screen reader
// The key line — the register's rendering; aria-hidden per the module docstring (the
// eye's copy of facts spoken by placeholders, announce() and the "?" overlay).
const keylineEl = el("div", "lf-ui lf-keyline");
keylineEl.setAttribute("aria-hidden", "true");

// The name of what the pointer is over in design mode, floated at its corner. Chrome
// nothing presses (pointer-events none, in the stylesheet); refreshAim is its one
// writer (paintInspect), beside the box it names.
const inspectEl = el("div", "lf-ui lf-inspect");
inspectEl.setAttribute("aria-hidden", "true");
// Design mode's legend: a box for every item on the page while the mode stands, drawn
// here in the chrome's layer (paintLegend, its one writer). Paint about the page, so it
// says nothing to a screen reader — the mode's announcement and the names under the
// pointer are the spoken copy.
const legendRoot = el("div", "lf-ui lf-legend");
legendRoot.setAttribute("aria-hidden", "true");
// The g chord's addresses: a numbered chip on every member of the list it has aimed at,
// drawn here for the same reason the legend is (paintAddresses, its one writer). The eye's
// copy of what the chord announces, so it says nothing to a screen reader.
const addressBoard = el("div", "lf-ui lf-addresses");
addressBoard.setAttribute("aria-hidden", "true");
// The runtime's parts, named: a design comment can point at one, and an anchor names an
// element by id, so each part that is a thing to point at carries a stable one under the
// runtime's own prefix. `[id]:not(.lf-ui)` — how the anchor pass asks which section a
// passage is in — still passes over them, every one wearing lf-ui. What has no id is
// what nobody comments on: the toast, the live region, the scope root itself.
for (const [part, id] of [
  [banner, "lf-banner"],
  [versionMenu, "lf-versions"],
  [othersPanel, "lf-leaves"],
  [asksPanel, "lf-asks"],
  [panel, "lf-comments"],
  [fab, "lf-comment-button"],
  [composer, "lf-composer"],
  [helpEl, "lf-help"],
  [keylineEl, "lf-keyline"],
])
  part.id = id;
// The one scope root for the chrome's private rules: they match nothing outside
// this container. A div, not a lf-* element — the render gate reads a lf-* ancestor
// as "inside a widget", and the runtime's layer is inside none.
const chromeRoot = el("div", "lf-chrome");
chromeRoot.append(
  banner,
  versionMenu,
  othersPanel,
  asksPanel,
  panel,
  legendRoot,
  addressBoard,
  aimBox,
  fab,
  composer,
  toastEl,
  liveEl,
  helpEl,
  keylineEl,
  inspectEl,
);
document.body.append(chromeRoot);
// The controls that rewrite their own words hold the widest of them now, measured in
// the face the banner just rendered them in (see the stylesheet's banner comment).
// The counters hold the widest they reach anywhere below a thousand, so no count
// they write can move them — a page with a thousand open threads, or a machine with
// a thousand live pages, is not one anyone hands a user.
if (SIGNOFF) reserve(approveBtn, ["✓ Looks good", "✓ Approved"]);
reserve(versionBtn, [versionLabel(false), versionLabel(true)]);
reserve(toggleBtn, ["Comments", "Comments (999)"]);
reserve(asksBtn, ["Asks (999)"]);
reserve(othersBtn, ["All leaves (999)"]);
// The room the head of the document leaves for the bar, measured off the bar as
// rendered rather than stated as a number — --lf-banner-h is what the bar is drawn to
// and a second copy of it here would be a release behind it the day either moved. What
// spends this, and why it is spent as a box rather than as body's own padding, is the
// rule above that reads it. The key line's reservation at the foot is the same
// arrangement, written by syncLayout because it is the same measurement every time the
// line's height changes.
document.body.style.setProperty("--lf-head", banner.offsetHeight + "px");

// ---------- state ----------
let events = [];
// Until the first state answer, [] means "not read", not "no comments". Keep that
// distinction for a Comments panel restored or opened during startup; its General
// composer stays usable while the log-derived list says what it is waiting for.
let statePhase = "waiting";
let lastEventSeq = -1;
let lastVersionsKey = "";
let latestVersion = null;
let versions = [];
let agentMsgCount = -1;
let panelOpen = false;
let pendingAnchor = null;

// The fold answers where state stands; this answers how it got there. Widgets receive
// their own absolute events in log order, bounded by the version being viewed. A reply
// widget lives in the chrome rather than in a version, so its frozen log markup sees the
// whole sequence. Returning fresh event copies keeps the private event store private.
//
// One walk, two channels. A widget with an agent channel (x-report) asks the same
// question of the log a widget with a reviewer channel (x-state) does, and the only
// difference is which kind it reads and what ends an entry: an action is settled once
// replay has applied it, a report once no note has answered it. Written twice, the two
// would be a near-copy that has to change together — and the report half is the one
// carrying a timestamp anybody renders, so it is the half that would drift.
function sequence(widget, verb, kind, live) {
  return events
    .filter(
      (event) =>
        event.kind === kind &&
        event.widget === widget.id &&
        (!verb || event.action === verb) &&
        (inChrome(widget) || event.version <= VNUM) &&
        live(event),
    )
    .map((event) => structuredClone(event));
}

export const actionSequence = (widget, action) =>
  sequence(widget, action, "action", (e) => appliedActions.has(e.seq));

// Every report a worker has made about this widget, newest last. `ts` is what a module
// usually wants here: when the log heard from that worker, which is the one statement
// about freshness no author can write down, because a version states it once and the
// page then stands for hours saying so.
//
// Unfiltered, where the action half takes only what replay has settled, and the two
// asymmetries are the same rule read in each channel. An action's liveness is replay's,
// because a widget that deferred one under live input has a body that does not hold it
// yet and must not narrate it. A report's liveness is the *fold's* — answered by a
// version, and `reportFold` is what asks that — while a consumer asking when the log
// last heard from this worker is asking about the log and not about the fold.
//
// Filtering the answered ones out here was the same words meaning two things, and it
// broke on the system's own happy path. Publishing absorbs reports by id, so an
// orchestrator that adjudicates diligently blanked every row's elapsed line at every
// publish — and disarmed the call-out with it. The reader needs it most in exactly the
// case that then became unreachable: a worker that claimed work, had that claim written
// into a version, and died silently after.
export const reportSequence = (widget, verb) =>
  sequence(widget, verb, "report", () => true);

// When the version being read was published — the floor under any statement about how
// fresh what the page says is. A row nobody has reported on is not a row of unknown age:
// its words were asserted when this version landed, and are exactly that old.
//
// Without the floor, silence renders as nothing at all, which is the one direction a
// freshness line must never fail in. A fleet whose workers all died at six in the
// evening, on a page republished at six, shows five rows claiming work and no elapsed
// line anywhere at eight the next morning — a dead fleet reading healthy, which is the
// claim-nobody-revises failure the banner's own judgment exists to answer, reintroduced
// one section below the banner.
export const publishedAt = () => {
  let ts = null;
  for (const e of events) if (e.kind === "note" && e.version === VNUM) ts = e.ts;
  return ts;
};

// Subscribe after replay has had the last word for a poll. The sequences expose only
// what replay has settled, so a widget that deferred under live input never narrates
// a state its body does not hold. The callback also runs immediately, so a module owns
// its complete rendering in one function whether the first state arrived before or
// after it connected — and again on every poll, whether or not the log grew, which is
// what lets a rendering of elapsed time stay true without a timer of its own.
const watch = (read, callback) => {
  const update = () => callback(read());
  document.addEventListener("lf-actions", update);
  update();
  return () => document.removeEventListener("lf-actions", update);
};

export const watchActions = (widget, action, callback) =>
  watch(() => actionSequence(widget, action), callback);

export const watchReports = (widget, verb, callback) =>
  watch(() => reportSequence(widget, verb), callback);

// ---------- draft persistence ----------
// Text the user typed but hasn't sent must survive navigation, reload, version switches,
// server death — and the tab itself. That last one is where this store came from: each
// round's reply hands the URL over again and the user opens the page from the turn in
// front of them, so a page's tabs accumulate and the one holding a half-written sentence
// is as likely to be closed as any other. Tab-local storage carried a draft through
// everything but the one gesture nobody thinks of as destructive.
//
// So the store is the reader's, and one draft has one copy: every box showing it, in
// every tab, is a view of the store, and the store's own `storage` event carries a
// keystroke from the tab that made it to the rest (watchDraft). A copy per tab was the
// alternative and it fails in the direction that loses words — two tabs each holding a
// different half of one thought, and whichever is closed takes its half.
//
// The stored value is one record, not raw words plus lock markers: {text, attempt, base}
// while active and {attempt, base, settled:true} afterward. `base` is the shared attempt this
// edit descended from, or null when the store was absent. A new edit always mints a new
// attempt but a chain of failed local writes keeps the same base. That provenance is
// what lets the branch survive news settling its predecessor without letting it overwrite
// an unrelated generation another tab durably wrote later.
//
// A new attempt is minted even when its words equal an earlier message. The tombstone
// rather than key removal is
// what makes asymmetric removeItem behavior irrelevant, and the attempt is what lets the
// log recognize the same gesture after the tab holding the browser lock has died.
//
// Storage failures never break typing (`stored`). Every local save updates the document
// cache first and then tries the one record write, so a successful set followed by a
// failed get remains sendable, and a failed newer set cannot be erased by news settling
// the older shared attempt. The log still outranks both: an attempt already present in
// `events` is settled whatever stale active record storage hands back on reload.
const DRAFT = "lf-draft:";
const DRAFT_NEWS = "lf-drafts";
const draftCache = new Map(); // context -> {record, durable}
const tellDraft = (ctx, value) =>
  document.dispatchEvent(new CustomEvent(DRAFT_NEWS, { detail: { ctx, value } }));
const parseDraftRecord = (value) => {
  if (typeof value !== "string") return null;
  try {
    const record = JSON.parse(value);
    if (
      !record ||
      typeof record !== "object" ||
      typeof record.attempt !== "string" ||
      !(record.base === null || typeof record.base === "string") ||
      (record.settled === true
        ? Object.keys(record).some(
            (key) => !["attempt", "base", "settled"].includes(key),
          )
        : typeof record.text !== "string" ||
          Object.keys(record).some((key) => !["attempt", "text", "base"].includes(key)))
    )
      return null;
    return record;
  } catch {
    return null;
  }
};
const attemptAccepted = (attempt) => events.some((event) => event.attempt === attempt);
const writeDraftRecord = (ctx, record) =>
  draftStore.set(DRAFT + ctx, JSON.stringify(record));
const rawDraftRecord = (ctx) => {
  if (draftCache.has(ctx)) return draftCache.get(ctx).record;
  const read = draftStore.read(DRAFT + ctx);
  const record = read.available ? parseDraftRecord(read.value) : null;
  if (record) draftCache.set(ctx, { record, durable: true });
  return record;
};
const sameDraftRecord = (left, right) =>
  (left === null && right === null) ||
  (left !== null && right !== null && JSON.stringify(left) === JSON.stringify(right));
// Refresh is a reconciliation as real as a storage event. Publish an adopted shared
// generation after the current call returns, so every mounted view follows the cache
// without making a composer's synchronous close clear itself recursively.
const projectDraftRecord = (ctx, record) =>
  queueMicrotask(() => {
    const current = draftCache.get(ctx)?.record ?? null;
    if (!sameDraftRecord(current, record)) return;
    const active = current && !current.settled && !attemptAccepted(current.attempt);
    tellDraft(ctx, active ? current.text : null);
  });
// A nondurable branch may replace exactly the shared generation it was editing, not
// merely whatever record happens to be there when a failed writer becomes writable
// again. A tombstone for that base is the older branch settling; it still cannot erase
// the newer local words. An unrelated attempt is later shared ownership and wins.
const sharedIsBaseOf = (branch, shared) =>
  branch.base === null ? shared === null : shared?.attempt === branch.base;
// A durable cache is a rendering convenience, never a claim that storage still holds
// that generation. Refresh it immediately before sending or settling. If the
// read itself is refused, the cache is the only copy available. A nondurable branch wins
// only over its own base; unrelated shared news wins even when its storage event was
// delayed or suppressed.
const refreshDraftRecord = (ctx) => {
  const cached = draftCache.get(ctx);
  const read = draftStore.read(DRAFT + ctx);
  if (!read.available) return cached?.record ?? null;
  const shared = parseDraftRecord(read.value);
  if (cached && !cached.durable) {
    if (sameDraftRecord(cached.record, shared)) {
      cached.durable = true;
      return cached.record;
    }
    if (sharedIsBaseOf(cached.record, shared)) {
      if (cached.record.settled) cached.durable = writeDraftRecord(ctx, cached.record);
      return cached.record;
    }
  }
  const changed = Boolean(cached && !sameDraftRecord(cached.record, shared));
  if (shared) draftCache.set(ctx, { record: shared, durable: true });
  else draftCache.delete(ctx);
  if (changed) projectDraftRecord(ctx, shared);
  return shared;
};
const activeDraftRecord = (ctx) => {
  const record = rawDraftRecord(ctx);
  return record && !record.settled && !attemptAccepted(record.attempt) ? record : null;
};
// Every tombstone is an ownership claim, whether it follows Send, Cancel, a widget
// action, or a poll that observed the attempt in the log. Re-read shared storage before
// making that claim so a stale view cannot settle a newer durable generation. A refused
// read and a nondurable local edit still use the document cache, their only copy.
const settleDraft = (ctx, attempt) => {
  const current = refreshDraftRecord(ctx);
  if (!current || current.settled || current.attempt !== attempt) return false;
  const currentDurable = draftCache.get(ctx)?.durable;
  // If this write fails, the cache tombstone still descends from whatever the active
  // branch could replace. If it succeeds, the tombstone itself is the new shared
  // generation and later edits descend from its attempt.
  const storedRecord = { attempt, base: attempt, settled: true };
  const durable = writeDraftRecord(ctx, storedRecord);
  const record = durable
    ? storedRecord
    : {
        attempt,
        base: currentDurable ? current.attempt : current.base,
        settled: true,
      };
  draftCache.set(ctx, { record, durable });
  return true;
};
const newAttempt = () => {
  const bytes = new Uint8Array(16);
  // Unlike randomUUID(), getRandomValues is available when leaf is served over plain
  // HTTP to a stated/LAN host as well as in a secure localhost context.
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
};
export const saveDraft = (ctx, text) => {
  const cached = draftCache.get(ctx);
  const previous = rawDraftRecord(ctx);
  // A series of local edits whose writes all fail is one branch from the last shared
  // generation, not a chain that progressively forgets what it may replace.
  const base =
    cached && !cached.durable && previous ? previous.base : (previous?.attempt ?? null);
  const record = { text, attempt: newAttempt(), base };
  const durable = writeDraftRecord(ctx, record);
  draftCache.set(ctx, { record, durable });
  return durable;
};
export const clearDraft = (ctx) => {
  const current = rawDraftRecord(ctx);
  if (!current || current.settled) {
    draftCache.delete(ctx);
    return false;
  }
  return settleDraft(ctx, current.attempt);
};
export const loadDraft = (ctx) => activeDraftRecord(ctx)?.text ?? null;
const draftContexts = () =>
  new Set([
    ...draftCache.keys(),
    ...draftStore
      .keys()
      .filter((key) => key.startsWith(DRAFT))
      .map((key) => key.slice(DRAFT.length)),
  ]);

// The log is authoritative over a stale active storage record. Run after each poll so a
// remove-resistant record from an accepted send becomes a tombstone in every live tab;
// activeDraftRecord already masks it during the write attempt itself.
function settleAcceptedDrafts() {
  for (const ctx of draftContexts()) {
    const record = refreshDraftRecord(ctx);
    if (
      record &&
      !record.settled &&
      attemptAccepted(record.attempt) &&
      settleDraft(ctx, record.attempt)
    )
      tellDraft(ctx, null);
  }
}

// One draft generation has one attempt across every tab showing this page. Two tabs may
// POST it together; the append-locked log returns the same event to both. The attempt is
// also what lets a replacement tab recover after the first sender dies.
//
// Attempt and exact untrimmed text are rechecked immediately before POST. A successful
// older send settles only that generation; any later edit has a fresh attempt and remains
// standing.
export async function sendDraft(ctx, owns, send) {
  const before = activeDraftRecord(ctx);
  const refreshed = refreshDraftRecord(ctx);
  const current =
    refreshed && !refreshed.settled && !attemptAccepted(refreshed.attempt)
      ? refreshed
      : null;
  if (
    !before ||
    !current ||
    current.attempt !== before.attempt ||
    current.text !== before.text ||
    !owns()
  )
    return null;
  const sent = await send(current.attempt);
  if (sent && settleDraft(ctx, current.attempt)) tellDraft(ctx, null);
  return sent;
}

// A draft written in another view, routed to whatever is showing it here. The document is
// the bus, as it is for replayed actions (watchActions), and that is what supplies the
// index this needs — from a draft's context to the box on screen — without a map of our
// own to hold in step with the panel: a box that has left the document takes its view off
// with it (mirrorDraft). The callback takes the store's vocabulary, so the words now
// standing arrive as a string and a settlement as null.
//
// It does not run on subscribe, which is where this parts company with watchActions. The
// draft a box opens with and the news that another tab changed one are different facts,
// and the boxes answer them differently: a draft editor opens on recovery at load and
// stays shut for a keystroke made elsewhere, because news arriving has no gesture behind
// it and so may move nothing.
export function watchDraft(ctx, callback) {
  const update = (ev) => ev.detail.ctx === ctx && callback(ev.detail.value);
  document.addEventListener(DRAFT_NEWS, update);
  return () => document.removeEventListener(DRAFT_NEWS, update);
}
addEventListener("storage", (ev) => {
  const prefix = PAGE_SCOPE + DRAFT;
  // Null where the whole store was cleared, and every key of another page on this origin
  // besides — a published site serves each example from one root.
  if (!ev.key?.startsWith(prefix)) return;
  const ctx = ev.key.slice(prefix.length);
  const incoming = parseDraftRecord(ev.newValue);
  const cached = draftCache.get(ctx);
  const current = cached?.record;
  // Reconcile the same way the lock callback does. A nondurable branch can reassert
  // itself over its base (including that base's tombstone), but unrelated active news
  // is a later shared generation and retires the local branch.
  if (current && !cached.durable) {
    if (sameDraftRecord(current, incoming)) cached.durable = true;
    else if (sharedIsBaseOf(current, incoming)) {
      cached.durable = writeDraftRecord(ctx, current);
      return;
    }
  }
  if (incoming) draftCache.set(ctx, { record: incoming, durable: true });
  else draftCache.delete(ctx);
  const active = incoming && !incoming.settled && !attemptAccepted(incoming.attempt);
  tellDraft(ctx, active ? incoming.text : null);
});

// One box's view of one draft: the plain boxes, which have nothing to render about a
// draft but its words, so a settlement and an emptying leave the same empty box. The
// value is written only where it differs, because writing .value on a focused box moves
// the caret to the end of it; the box grows to fit either way, sizing being the
// stylesheet's (wireInput). sync() is what makes the Send button agree with what is now
// in the box.
//
// A box out of the document drops its view at the next word it would have shown, rather
// than at the moment it leaves — the one box that ever leaves is a reply box going with
// its resolved thread, and asking the panel to say so would be the index this design is
// for not keeping. What the check has to hold is that such a box never renders and never
// doubles the live one: a thread a retraction reopens is a second box on the same
// context, and the one that is still in the document is the one that paints.
function mirrorDraft(ta, sync, ctx) {
  const off = watchDraft(ctx, (value) => {
    if (!ta.isConnected) return off();
    const text = value ?? "";
    if (ta.value === text) return;
    ta.value = text;
    sync();
  });
}
// Reply drafts are never pruned. A thread resolving is not a discard: another
// tab's Resolve, or this tab accepting a suggestion whose action `resolves`,
// used to sweep an unsent reply out of storage — words going missing, where the
// norm is that Cancel is the only discard. A thread a retraction reopens finds
// the draft where it was left.

// Panel open/closed is remembered too: a version switch reloads the document, and
// reopening the panel by hand after every revision gets old fast.
const PANEL_KEY = "lf-panel-open";
// Whether the panel stands over the page rather than beside it — the same fact as which
// of the two rules that take the strip the page is under, and as which region the
// reader's own scrolling moves. Asked of the query rather than stored, so no reader of it
// can hold an answer from a window that has gone.
const covering = matchMedia(COVERING);
const panelCovers = () => panelOpen && covering.matches;
// The strip the panel holds, which is the panel's width until the window is too narrow
// to give one up — one expression, because the margin the rule takes and the room
// measured against it have to mean the same thing by it.
const panelStrip = () => (panelOpen && !panelCovers() ? PANEL_W : 0);
// Whether the page still has room for the margin the theme's idioms hang in. The strips
// are granted by a media query, which asks the window; the page's box is the window less
// whatever the panel holds of it, and this is the only thing that knows the difference. So
// it asks the theme's own floor of the box and vetoes the grant where the room has gone —
// a fact about the page rather than about any idiom that spends it. Without it a 1024px
// window with the panel beside it left a page carrying sidenotes a 151px column, painting
// its widest widgets out past the edge of one, and neither `version check --render` nor
// the render suite can see that posture: both open a 1200px window with no panel in it.
//
// Its own function, and not syncLayout's, because the strip it vetoes is body's own
// padding (theme.css) and syncLayout runs from an observation of that box — CLAUDE.md's
// "The one writer may not write the box the layout is measured from", and the same reason
// the strip the panel takes is a rule in the stylesheet above. Moving it costs nothing,
// because neither fact it turns on is a reading of that box: the window states one and the
// panel the other, and each arrives on an occasion of its own.
//
// The strip is stated rather than measured off body, whose clientWidth is the box itself
// and would be the natural reading. The margin transitions, so a measurement taken during
// the slide is the posture flipping and flipping back across a fifth of a second, which is
// a page rewrapping its notes into the margin and out of it while the panel opens. Stated,
// it is the width being arrived at.
function stateStrip() {
  document.body.toggleAttribute(
    "data-lf-cramped",
    document.documentElement.clientWidth - panelStrip() < STRIP_MIN,
  );
}
addEventListener("resize", stateStrip);
// Every writer here is a writer of the chrome, so nothing this function does resizes the
// box it reads: the strip the page yields to the panel is the stylesheet's, and the strip
// it yields to a margin idiom is stated above.
function syncLayout() {
  const panelBeside = panelOpen && !panelCovers();
  // The toast lives in the same corner as the panel's Send button. Beside a wide
  // panel it steps left; over a covering sheet it stays inside the viewport and
  // rises above the whole composer, including a textarea grown by an unsent draft.
  toastEl.style.right = (panelBeside ? PANEL_W + 18 : 18) + "px";
  toastEl.style.bottom = (panelCovers() ? generalRow.offsetHeight + 18 : 18) + "px";
  // The key line takes the toast's lift over a covering sheet, or the sheet's own
  // composer stands on the words saying what Esc will do to it.
  keylineEl.style.bottom = (panelCovers() ? generalRow.offsetHeight + 14 : 14) + "px";
  // One line stands over two scroll regions, so one measurement is what they both
  // reserve — off the rendered line rather than stated as a number, which is what
  // keeps it true when the line's face or its padding moves.
  const clear = keylineEl.offsetHeight + 20 + "px";
  // The document's, taken as the chrome container's own box rather than as padding on
  // body: body's padding comes out of the box the room is measured from (stateRoom), so
  // writing it here made this function a writer of the box it reads, and every page that
  // watched that box — three do — was one change in the line's height from a
  // ResizeObserver loop on the window's error channel. CLAUDE.md's "The one writer may not
  // write the box the layout is measured from" carries the whole of it. The container is
  // in the flow, holds nothing but out-of-flow chrome, and is watched by nobody, so what
  // it takes is room the document has and no measurement's business.
  chromeRoot.style.paddingBottom = clear;
  // The board is the page's other scroll region, in the corner the line is written
  // into, so it reserves the same room — and states it twice, because its list reaches
  // the bottom two ways that take their room from different places. A wheel to the end
  // reads the padding. A walk's own scroll reads none of it: scroll-padding is what a
  // scroll-into-view stops short of, and without it the last row's clearance is however
  // far Chrome happens to overshoot, which is a fact about row height and not about the
  // line standing there. Stepping the line clear instead was the other answer, and it
  // takes the board's width off the line's: a busy scope already fills a laptop's, so
  // the room it gives up is chips clipped off the right-hand end.
  othersPanel.style.paddingBottom = clear;
  othersPanel.style.scrollPaddingBottom = clear;
  stateRoom(panelStrip());
  syncFloats();
}
// The room a widget declared wide may take: the document's own content box, less the
// gutter the column already gives its prose, so a breakout is centred on the column's
// axis and stops where the page stops.
//
// Measured, and measured here, because the panel is the thing no stylesheet can see: it
// is 420px of the window while it is open and nothing in CSS says so, and a rule written
// against 100vw would also spend the rail a suggestion hangs in and the classic scrollbar
// this platform doesn't draw. The three of them come off body's own box for free. That box
// is watched (layoutSizes), so the room is restated whenever it changes shape whatever
// changed it, for the same reason the floats are placed again.
//
// The gutter is read off the column rather than stated, since 24px is theme.css's number
// and a second copy here would be a release behind it. Below the column's own width the
// two coincide exactly, so the rule that spends this is a no-op on a narrow window rather
// than a case anyone has to write.
//
// The strip the panel holds is the one part of that box which isn't settled when this
// runs: it is handed over as motion, so body's margin is still the old one for the length
// of the transition and the box in front of us is neither the width the page has nor the
// one it is going to. Both readings are wrong, in opposite directions and at different
// prices, so the room takes whichever of the two is smaller and the page never owes room
// it hasn't got. Opening, that is the width being arrived at, stated at once: the strip
// is being taken away, and an exhibit that waited out the slide would spend it hanging
// over the panel with a sideways scrollbar underneath. Closing, it is the width in front
// of us: the strip is coming back, and an exhibit that took it before the page had it
// scrolled sideways for a fifth of a second every time the panel was dismissed — which
// is what the suggestion sweep caught, on a window narrow enough for the returning strip
// to matter. What is given back is picked up as it is given: the box is watched, so every
// frame of the slide is a reading of it, and the growth lands the frame the room is real.
function stateRoom(strip) {
  const main = document.querySelector("main");
  if (!main) return;
  const body = getComputedStyle(document.body);
  const column = getComputedStyle(main);
  const room =
    document.body.clientWidth -
    Math.max(0, strip - parseFloat(body.marginRight)) -
    parseFloat(body.paddingLeft) -
    parseFloat(body.paddingRight) -
    parseFloat(column.paddingLeft) -
    parseFloat(column.paddingRight);
  document.documentElement.style.setProperty(
    "--lf-room",
    Math.max(0, Math.floor(room)) + "px",
  );
}
// The floats live in the document, and syncLayout is where its box changes shape — the
// panel takes or returns its strip, a resize moves every rect, the composer's own
// textarea grows under typing — so whatever float is up is placed again against the
// new geometry: the composer from its own marks (a detached one re-clamps where it
// stands), the button from the live selection where one still stands, and by
// re-clamping alone where none does. Skipping this leaves a float placed at a wide
// window's edge overhanging the box a panel then narrows, and an absolute child past
// body's client box is sideways-scrollable overflow: the document panned 328px left
// under a trackpad, with the composer standing on the panel that had displaced it.
function syncFloats() {
  if (composerOpen) {
    const box = composer.getBoundingClientRect();
    placeComposer(box.left, box.top);
  }
  if (fabAnchor?.quote && pageSelection()) updateFab();
  else if (fabAnchor) {
    const box = fab.getBoundingClientRect();
    placeClear(fab, box.left, box.top);
  }
}
function setPanel(open) {
  // Closing while focus is inside would drop it on body, the user's place
  // lost silently; it lands on the one control that reopens what just closed.
  if (!open && panel.contains(document.activeElement))
    toggleBtn.focus({ preventScroll: true });
  panelOpen = open;
  // Twice, the two readers being on opposite sides of the chrome's own scope: the class
  // shows the panel, from a rule inside it, and the attribute is what the page yields its
  // strip to, from a rule outside. A document-level rule naming .lf-panel would be a name
  // a page could coin and take the strip with, which is the leak
  // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
  // body, beside data-lf-cramped.
  panel.classList.toggle("open", open);
  document.body.toggleAttribute("data-lf-panel", open);
  toggleBtn.setAttribute("aria-expanded", String(open));
  // Both of the page's answers to the panel are made here rather than left to the
  // observation, and for the same reason at each: the strip the idioms hang in is body's
  // own padding, which the observation's writer may not touch, and the chrome's posture
  // over a covering sheet follows an open that moves body's box by nothing at all — the
  // sheet stands over the page, so there is no observation to deliver.
  stateStrip();
  syncLayout();
  readerStore.set(PANEL_KEY, open ? "1" : "0");
  if (open) {
    renderPanel();
    syncGeneral(); // a restored draft has to reach the Send button's disabled state
  }
  paintHere();
}
toggleBtn.onclick = () => setPanel(!panelOpen);
addEventListener("resize", pageShifted);
// field-sizing and every other rendered-size change feed the one geometry writer —
// the key line included, whose height is the room the chrome reserves under it.
const layoutSizes = new ResizeObserver(syncLayout);
// The page's own box, which is what the room is measured from and what the floats hang
// in. Watched rather than derived, because an enumeration of the occasions the box moves
// fails twice over. It cannot be complete: the room followed such a list once — the
// panel, the window, the one call at the end of upgrade — and a widget that took a margin
// any other way got no restatement at all. And each entry on it is read at a moment
// somebody chose, which the panel's strip breaks by being motion: read where the slide
// began and again where it was expected to end, a slide the reader interrupted was
// answered at neither. Watching is every frame of it, the last frame included, and the
// window comes with them — body is the window's own height and width here, so a `resize`
// listener beside this would be one fact arriving twice. Nothing this observer calls may
// write this box, which is what the key line's reservation being a flow box and the
// panel's strip being the cascade's are both about.
layoutSizes.observe(document.body);
layoutSizes.observe(generalRow);
layoutSizes.observe(keylineEl);
// The composer grows under typing (field-sizing), and a box placed above its passage
// grows downward, back over the mark it was moved off — so its own resize re-places it.
layoutSizes.observe(composer);

let toastTimer = 0;
function showToast(msg, onClick) {
  announce(msg);
  toastEl.textContent = msg;
  syncLayout();
  toastEl.onclick = onClick || null;
  toastEl.classList.add("show");
  toastEl.classList.toggle("clickable", Boolean(onClick));
  clearTimeout(toastTimer);
  // Drop `clickable` on the way out too: a faded-but-clickable toast is an invisible
  // target sitting over the corner of the page.
  toastTimer = setTimeout(() => {
    toastEl.classList.remove("show", "clickable");
    toastEl.onclick = null;
  }, 4000);
}

// Returns the event the server minted — the id is the sender's only handle on the
// thread or message it just created, which is what revealThread is handed — or null
// when the server definitively refused it. Every event carries one browser-minted
// attempt, so a lost answer is retried without becoming a second gesture.
//
// The outbox sends one at a time because the log's order is the order the reader acted
// in and concurrent requests are not. It is also the page's only record of unresolved
// work: an action in this list is the widget replay leaves alone and the fact that keeps
// undo dead. A separate promise chain plus a pending-widget map used to describe those
// same records twice, then reconcile them through a later poll.
//
// A successful POST returns the server's state through the event it accepted. The page
// therefore crosses one boundary, not "append succeeded" followed by "a GET happened
// to read it": when an entry leaves this list, its caller has the minted event and this
// page has read a log containing it. A periodic poll may observe the attempt first after
// a response is lost; that is the same durable answer and ends the retry.
const retryPause = () => new Promise((resolve) => setTimeout(resolve, POLL_MS));
let drainingOutbox = false;
async function deliver(entry) {
  let announced = false;
  for (;;) {
    const { event } = entry;
    const alreadyAccepted = events.find(
      (candidate) => candidate.attempt === event.attempt,
    );
    if (alreadyAccepted) return alreadyAccepted;
    let res;
    try {
      res = await postEvent(event);
    } catch {
      if (!announced) showToast("Connection lost — retrying your change…");
      announced = true;
      await retryPause();
      continue;
    }
    // A newer layer is taking this tab over, and `postEvent` has already started the
    // reload. The server refused to read this body in a vocabulary it no longer
    // speaks, so nothing was appended and there is nothing here to retry: the page
    // comes back from the log, under the layer it is reloading into.
    if (!res) return null;
    let answer;
    try {
      answer = await res.json();
    } catch {
      if (!announced) showToast("Couldn't read the answer — retrying your change…");
      announced = true;
      await retryPause();
      continue;
    }
    const acceptedEvent = answer?.state?.events?.find(
      (candidate) => candidate.attempt === event.attempt,
    );
    if (res.ok && answer?.ok === true && acceptedEvent) {
      // The send succeeded the moment the answer named the accepted event. A fault
      // rendering that state is its own news and must not re-send: the next poll
      // paints it, and re-posting an attempt the log already holds is a request the
      // server can only answer the same way. Where the throw lands before the events
      // are stored, the retry would not even end at the top of this loop — the
      // attempt is in no list to be found — so the page would post forever and this
      // gesture would never settle.
      try {
        await receiveState(answer.state);
      } catch (error) {
        console.error("leaf: state in event response", error);
      }
      return acceptedEvent;
    }
    if (
      answer?.final === true &&
      answer.attempt === event.attempt &&
      answer.ok === false
    ) {
      showToast(`Couldn't send — ${answer.error || "the server refused it"}`);
      return null;
    }
    if (!announced) showToast("Server answer was incomplete — retrying your change…");
    announced = true;
    await retryPause();
  }
}
async function drainOutbox() {
  if (drainingOutbox) return;
  drainingOutbox = true;
  try {
    while (outbox.length) {
      const entry = outbox[0];
      const answer = await deliver(entry);
      outbox.shift();
      // The list is an input to the key line and no focus/mouse event accompanies
      // either edge. Repaint before resolving the caller, whose own settlement may
      // move a second row on the same frame.
      paintKeys();
      entry.resolve(answer);
    }
  } finally {
    drainingOutbox = false;
  }
}
function post(event) {
  const attempted = { ...event, attempt: event.attempt || newAttempt() };
  const answer = new Promise((resolve) => {
    outbox.push({ event: attempted, resolve });
  });
  paintKeys();
  void drainOutbox();
  return answer;
}

// ---------- text inputs ----------
// One helper wires every composer: the general box, each per-thread reply, and the
// selection composer. They persist a draft on each keystroke, send on ⌘/Ctrl+Enter, and
// can't be double-sent by an impatient second click. Growing with their content is the
// stylesheet's job (field-sizing), not this file's.
// Returns a sync() the caller runs after setting .value programmatically, so the send
// button agrees with what's in the box.
// The send binding, and the register's spelling of it: the placeholder, the button's
// tooltip and the row a box declares all read one string, where the constant they used to
// share sat beside a listener that bound the chord independently.
const SEND = "Mod+Enter";
const SEND_KEYS = spell(SEND);
// `sends` is the word the box's own send row says — "send", "suggest", "comment" — since
// a composer in suggestion mode and a thread's reply are the same binding doing different
// things, and the row is where the surfaces read that from.
function wireInput(
  ta,
  { hint, address, save, send, sendBtn, sends, busy = () => false },
) {
  // The hint goes in the placeholder, where it's visible exactly while the box is
  // empty and can't be found any other way; the button's tooltip spells the send key
  // out. The send shortcut is focus-scoped, so only the focused box may claim it —
  // unfocused, the placeholder carries the box's own address instead (the chord
  // that reaches it), where the box has one. hint is a function where the
  // label changes under a live box (the composer's suggest mode); address is always
  // one, because a thread's number renumbers as earlier threads resolve while its box
  // stands.
  const label = () => (typeof hint === "function" ? hint() : hint);
  const paint = () => {
    const suffix = document.activeElement === ta ? SEND_KEYS : address?.();
    ta.placeholder = suffix ? `${label()} · ${suffix}` : label();
  };
  ta.addEventListener("focus", paint);
  ta.addEventListener("blur", paint);
  sendBtn.title = `Send (${SEND_KEYS})`;
  let sending = false;
  // aria-disabled rather than the property, because a widget's send button is a span
  // wearing role="button" (see offer) and a span has no `disabled` to set — it would
  // have looked live while submit() below refused it. The attribute reads on either
  // element, and the guard in submit() is what actually holds; a focusable button
  // saying it can't send yet is better than one the reader can't reach to find out.
  const sync = () => {
    paint();
    sendBtn.setAttribute(
      "aria-disabled",
      String(sending || busy() || !ta.value.trim()),
    );
  };
  paint();
  const submit = async () => {
    if (sending || busy()) return;
    // A send key on an empty box answered with silence reads as a send that
    // happened — the blind drive believed exactly that. Say the nothing out loud
    // (the toast announces too).
    const raw = ta.value;
    const text = raw.trim();
    if (!text) return showToast("Nothing to send — the box is empty");
    sending = true;
    sync();
    try {
      await send(text, raw);
    } finally {
      sending = false;
      sync();
    }
  };
  ta.addEventListener("input", () => {
    save(ta.value);
    sync();
  });
  // The box's own scope: one row, so the key line's word, the "?" overlay's sentence and
  // the press are the same object. Every box the runtime wires gets it — the general box,
  // each thread's reply, the selection composer, a widget conversation — where the reference
  // used to carry one row saying "in the focused composer" for a chord that fires in all
  // of them.
  // The sentence is the same in every box, so the reference names the binding once however
  // many boxes the page holds; the word is this box's, because what the press does here is
  // what the line is for — a composer in suggestion mode and a thread's reply are one
  // binding doing two things.
  keys(ta, "In a text box", [
    { keys: [SEND], does: "Send what you have typed", line: sends, run: submit },
  ]);
  sendBtn.addEventListener("click", submit);
  return sync;
}

// ---------- time ----------
// Elapsed, in the page's one wording. Exported for the same reason quietSince is: a
// widget rendering how long since it heard from someone is saying the sentence the
// banner and the leaves panel already say, and a second spelling of it — "12 min ago"
// against "12m ago", or a different rounding at the hour — would read as two clocks on
// one page. The coarseness is the point: elapsed time is a fact the reader acts on at a
// glance, and a ticking second hand is precision nobody asked for over a number nobody
// can trust to the second anyway.
export const ago = (ts) => {
  if (!ts) return "";
  const secs = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
  if (secs < 45) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
};

// ---------- threads ----------
// The log with each streamed message folded whole, in log order — the mirror of
// interact.py's fold_messages, and the panel's one message reading. A chain is a
// head (a claude comment or reply carrying `more` while unfinished) plus append
// events naming it in `continues`, each chunk's text concatenating raw onto the
// head's. The fold leaves `more` on the folded head exactly while the chain is
// open, which is what the streaming mark reads; heads are copied, never mutated,
// because `events` is the log's own list. An append whose head a torn log lost
// attaches to nothing and is dropped.
function foldMessages(evts) {
  const folded = [];
  const heads = new Map();
  for (let e of evts) {
    if (e.kind === "append") {
      const head = heads.get(e.continues);
      if (!head) continue;
      head.text += e.text;
      if (e.markup) head.markup = e.markup;
      if (e.more) head.more = true;
      else delete head.more;
      continue;
    }
    if ((e.kind === "comment" || e.kind === "reply") && e.more) {
      e = { ...e };
      heads.set(e.id, e);
    }
    folded.push(e);
  }
  return folded;
}

function buildThreads() {
  const threads = new Map();
  const threadFor = new Map();
  // The whole log, not this version's window: a conversation is not version-scoped, so
  // the panel shows the same threads whichever version is pinned and a retraction
  // settles a thread's state from wherever it was declared. interact.py's callers pass
  // upto=None for the same reason. Replay windows to VNUM instead, and on any version
  // but the newest the two are meant to disagree — the rule binds both sites, so it is
  // stated once in the skill's CLAUDE.md, under "A pinned version scopes the document,
  // never the conversation".
  const floors = retractionFloors(Infinity);
  const withdrawn = takenBack();
  // widget id -> its last action the log still lets stand: not one the reader took
  // back, not one a version retracted under it. The widget is what an ask is
  // (x-awaits), so what answers one is that widget's own last word; and it is the
  // only key the log carries by itself, which is why stateFold cannot be borrowed for
  // this — foldable() drops an action whose widget the page no longer holds, and the
  // version that honors a decision retires the widget that made it, precisely when the
  // thread it settled most needs to stay settled. x-state holds a verb declaring
  // `resolves` to a widget-absolute unit so the two keys are the same one.
  const answers = new Map();
  for (const e of events)
    if (
      e.kind === "action" &&
      !withdrawn.has(e.id) &&
      !retractedIds(e, floors, elementById(e.widget)).length
    )
      answers.set(e.widget, e);
  for (const e of foldMessages(events)) {
    // A gesture the reader took back settles nothing, whichever way it settled: the
    // log holds it and no reading of the log stands on it. The same sentence
    // interact.py's build_threads reads, because it is the same reading.
    if (withdrawn.has(e.id)) continue;
    if (e.kind === "comment") {
      // `resolved` is the event that settled the thread, or null. Either side can
      // close one, so a flag beside a second field naming who would be two readings
      // of one fact; the settling event answers both and carries its own author.
      const thread = { root: e, msgs: [e], resolved: null };
      threads.set(e.id, thread);
      threadFor.set(e.id, thread);
      continue;
    }
    // A widget's standing answer settles the thread it names. The answer snapshots
    // the thread it was made in, because the honoring version retires the wrapper
    // that held the mapping and one atomic event can't half-arrive the way a second
    // POST could — so the log is the only place that pairing survives.
    //
    // Read off the detail rather than the verb, because the naming is the
    // mechanism's and the verb is a member's: `accept` stood here once, which was
    // exactly right for the one widget that says that word and silently nothing
    // for the next widget whose answer closes the question it was asked in. That
    // is the failure the widget list's norm names — it arrives as a feature
    // nobody wired up rather than as an error. A verb carries only the detail
    // keys its entry declares (additionalProperties: false), so a `resolves` is
    // one on purpose, and an answer that settles no thread carries none.
    //
    // Standing is every way the log currently holds an answer: not retracted by a
    // version that rewrote what the decision rested on (`restated`), not taken back
    // by the reader (the skip above), and not superseded by a later action on the
    // same widget. Without that last one, a
    // reject after an accept left the reader's question filed away as answered by
    // the fix they had just turned down, while the fold reported the suggestion
    // rejected: the log held one thing, the panel showed another, and nothing on
    // either side said so.
    //
    // Settled at the answer's own place in the walk rather than after it: a resolve
    // pressed between two decisions is the last word on the thread, and a
    // superseded answer has nothing to clear because it never stood.
    if (e.kind === "action") {
      const answered = threads.get(e.detail.resolves);
      if (answered && answers.get(e.widget) === e) answered.resolved = e;
      continue;
    }
    if (e.kind === "reply") {
      const thread = threadFor.get(e.parent);
      thread.msgs.push(e);
      threadFor.set(e.id, thread);
    } else if (e.kind === "resolve") {
      threadFor.get(e.parent).resolved = e;
    } else if (e.kind === "unresolve") {
      threadFor.get(e.parent).resolved = null;
    }
  }
  return [...threads.values()];
}

const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Lazily, like the tokenizer: a page is usually handed over before anyone has said
// anything, and one with no messages never pays the parse. poll() awaits this before
// the panel builds a body, which is what keeps msgNode synchronous.
//
// Raw HTML — block and inline both route through the one `html` renderer — escapes to
// the characters it was written in: prose says `Vec<T>`, and a message injects widgets
// only through its gate-validated `markup` field, never through text. breaks: a single
// newline is a line break, because a message is typed prose and nobody types two
// spaces to mean the line they just ended.
// Plain escaped text until the renderer arrives, so a failed vendor import
// degrades a body's Markdown to its own words instead of refusing the poll
// that carries it.
let renderMarkdown = (text) => escapeHtml(text);
let markedReady;
const loadMarked = () =>
  (markedReady ??= import("/vendor/marked.esm.js")
    .then((m) => {
      const md = new m.Marked({
        breaks: true,
        renderer: { html: (t) => escapeHtml(t.text) },
      });
      renderMarkdown = (text) => md.parse(text);
    })
    .catch((error) => {
      // Retry on a later poll rather than caching the rejection for the life
      // of the load — one transient failure otherwise left every body plain.
      markedReady = undefined;
      reportPageError(`markdown renderer failed to load: ${error?.message ?? error}`);
    }));

// Bodies are cached per event id and re-adopted when a thread node is rebuilt — which
// the reconcile leaves one occasion for, a thread resolving: the log is append-only so
// a closed message's text never changes, and re-adopting the node keeps a widget in a
// reply (a rendered diagram) from re-upgrading across that rebuild. An open streamed
// message is the one message whose text still grows, so it stays out of the cache
// until its chain closes (syncMsg).
const msgBodies = new Map();
// Whether the page presents as working — presented(state).kind, set by poll();
// the streaming caret reads it, so a chain the agent abandoned stops promising.
let agentWorking = false;
function buildMsgBody(m) {
  const body = el("div", "lf-msg-body");
  if (m.suggestion) {
    // Verbatim: a suggestion's characters are bound for the page as typed, and a
    // rendering would show an italic where the next version carries the asterisks.
    body.classList.add("lf-suggest-body");
    body.textContent = m.text;
  } else {
    body.innerHTML = renderMarkdown(m.text);
    // The widget markup beside the text, injected as the CLI gate validated it.
    // Already-defined widgets upgrade on insertion; the passes below don't come
    // along with them — the said and quiet passes write a widget's declared words,
    // spoken and silent, and a fenced block is a <pre><code class="language-…">
    // like any the page holds.
    //
    // markWide is the pass that deliberately stays behind, and the reason is what
    // it hands out: the room the *document* has, which is not the room in here. A
    // diagram in a reply is a widget the vocabulary calls wide, and marked as one
    // it would lay itself out to the page's measure inside a 420px panel. The room
    // a message has is the message's, and it already has it.
    if (m.markup) body.insertAdjacentHTML("beforeend", m.markup);
    renderSaid(body);
    renderQuiet(body);
    // Not settle()d: that queue holds the page's geometry still for the first anchor
    // pass, and a message colors in the panel, where no anchor is captured and nothing
    // waits. Each block already fails soft to its own plain source.
    highlightBlocks(body);
  }
  return body;
}

// A streamed message grows in place. While its chain is open the body renders
// again whenever more text arrived, and the close renders once more — the chunk
// that closes may carry the message's markup — banks the now-immutable body in
// msgBodies, and drops the open mark. A message that was never open returns at
// the first guard, so the reconcile's promise to closed messages (untouched
// nodes, surviving focus and selection) is unchanged; re-rendering an open one
// is safe for the same reason it is cheap — no markup until the close, so no
// upgraded widget is torn down mid-render, and the caret mark is paint, not
// layout. The mark shows only while the page presents as working: a chain the
// agent abandoned reads as a finished message rather than a promise nobody is
// keeping.
function syncMsg(msg, m) {
  const open = Boolean(m.more);
  if (msg.dataset.lfOpen !== "1" && !open) return;
  if (msg.dataset.lfLen !== String(m.text.length) || !open) {
    const body = buildMsgBody(m);
    msg.querySelector(":scope > .lf-msg-body").replaceWith(body);
    msg.dataset.lfLen = String(m.text.length);
    if (!open) msgBodies.set(m.id, body);
  }
  if (!open) delete msg.dataset.lfOpen;
  msg.classList.toggle("lf-streaming", open && agentWorking);
}

// The caret's other writer, for the half no event reaches: the page's status
// can move with nothing new in the log — the agent going idle, a working claim
// aging out — and the reconcile above only runs when events arrive. So a flip
// in the presented state sweeps the open messages directly; both writers state
// the same outcome from the same two facts, so they cannot disagree.
function paintStreaming() {
  for (const msg of document.querySelectorAll('.lf-msg[data-lf-open="1"]'))
    msg.classList.toggle("lf-streaming", agentWorking);
}

function msgNode(m) {
  const div = el("div", `lf-msg ${m.author}`);
  div.dataset.mid = m.id; // the reconcile's key, and revealThread's address for it
  const head = el("div", "lf-msg-head");
  head.append(
    el("b", "", m.author === "claude" ? m.agent || "Agent" : "You"),
    el("time", "", ago(m.ts)),
  );
  let body = msgBodies.get(m.id);
  if (!body) {
    body = buildMsgBody(m);
    // Cached only once its chain is closed (syncMsg banks it): chunks are
    // immutable, so a closed message is immutable, which is the cache's contract.
    if (!m.more) msgBodies.set(m.id, body); // the id is server-minted, on every event
  }
  div.dataset.lfLen = String(m.text.length);
  if (m.more) {
    div.dataset.lfOpen = "1";
    div.classList.toggle("lf-streaming", agentWorking);
  }
  div.append(head);
  if (m.suggestion) div.append(el("div", "lf-suggest-label", "suggested replacement"));
  div.append(body);
  return div;
}

// How an anchor reads where it has to be printed rather than pointed at — every thread in
// the panel, and the open composer when the page has no passage left to mark. A quote-less
// anchor points at an element (a diagram or image commented on by click rather than by
// selection) and names its section instead of quoting it. One function, so the two places
// can't come to say it differently.
//
// An id is the page's name for an item and not the user's. `card-migration` says
// nothing they wrote, and pointing at an item is an ordinary gesture rather than the
// diagram's special case, so anchors reading this way are ordinary in the panel too.
// An element anchor is labelled with the item's own opening words, and falls
// back to the id where this version has no such element. The kind goes before the words
// because the two together are a name, where the words alone read as a quote the thread
// does not hold.
//
// A design comment (`about: "layer"`) reads "layer ·" first, because what follows names
// the thing whose look or behaviour is in question rather than the words on it: the
// control the press landed on where it landed on one (`part`), then the item — a
// widget by its tag and id, a runtime part by its name — since a design comment's
// subject is the element itself and its opening words would read as a quote.
function anchorLabel(anchor, about) {
  if (about === "layer") {
    const item = anchor?.section ? elementById(anchor.section) : null;
    const name = item ? designName(item) : anchor?.section || "the page";
    const on = anchor?.part ? `${anchor.part} · ${name}` : name;
    return anchor?.quote ? `layer · ${on} · “${anchor.quote}”` : `layer · ${on}`;
  }
  if (anchor?.quote) return `“${anchor.quote}”`;
  if (!anchor?.section) return "";
  const item = elementById(anchor.section);
  const says = itemSays(item);
  return `§ ${says ? `${itemWord(item)} · ${says}` : anchor.section}`;
}

// The open threads, in the order j/k walk and `g c` addresses. The list is the panel's own
// children rather than a record kept beside them: a thread the log settles is renamed out
// of them in that frame (foldOut), which takes it out of the walk, out of the addresses and
// out of r's press in one stroke. A map of id → address stood here once, written by
// renderThreads and read back by the chip and the placeholder — one list held twice, and
// the copy free to be a reconcile behind the panel it described.
const openThreads = () => [...threadsBox.querySelectorAll(":scope > .lf-thread")];

// The reconcile's one mover, shared by the list and the resolved disclosure: make
// `parent`'s children `nodes`, in that order, touching nothing already in its place.
// Not touching it matters beyond economy: reinserting a node restarts its CSS
// animations, drops any focus and caret inside it, and swaps it out from under a
// pressed pointer, which swallows the click. Stale nodes go first for the same
// reason — with one removed mid-list, everything after it is exactly one place
// forward, so the walk keeps those where they stand instead of reinserting each.
function setChildren(parent, nodes) {
  const keep = new Set(nodes);
  for (const child of [...parent.children]) if (!keep.has(child)) child.remove();
  let cursor = parent.firstChild;
  for (const node of nodes) {
    if (node === cursor) cursor = cursor.nextSibling;
    else parent.insertBefore(node, cursor);
  }
}

const emptyNote = el(
  "div",
  "lf-empty",
  "No comments yet. Select any text on the page to comment on it, or use the box below.",
);
const waitingNote = el("div", "lf-empty", "Loading current comments…");

// A terminal event's row, keyed like everything else in the list so its clock can
// refresh in place.
function systemNode(e, text) {
  let div = threadsBox.querySelector(`:scope > .lf-system[data-id="${e.id}"]`);
  if (!div) {
    div = el("div", "lf-system");
    div.dataset.id = e.id;
  }
  if (div.textContent !== text) div.textContent = text;
  return div;
}

// The resolved disclosure, one <details> for the page's life: the user's
// open/closed toggle is the browser's state, and it survives arrivals only if the
// element does — the rebuild this replaced snapped it shut on every one.
let resolvedBox = null;

// A thread has one send in flight even though its reply draft has two views. wireInput's
// private hold is still the right scope for every other composer, which has one control;
// a reply adds this thread-scoped hold and announces it on the document bus so both Send
// controls render the same fact. The promise is the post itself, because a queue would
// serialize the duplicate rather than refuse it.
const REPLY_FLIGHT_NEWS = "lf-reply-flight";
const replyFlights = new Map(); // thread id -> post in flight
const replyBusy = (id) => replyFlights.has(id);
const tellReplyFlight = (id) =>
  document.dispatchEvent(new CustomEvent(REPLY_FLIGHT_NEWS, { detail: { id } }));

function mirrorReplyFlight(ta, sync, id) {
  const update = (ev) => {
    if (ev.detail.id !== id) return;
    if (!ta.isConnected) return document.removeEventListener(REPLY_FLIGHT_NEWS, update);
    sync();
  };
  document.addEventListener(REPLY_FLIGHT_NEWS, update);
}

async function sendReply(t, text, raw, owns) {
  const id = t.root.id;
  if (replyBusy(id)) return null;
  const draftCtx = "reply:" + id;
  const flight = sendDraft(draftCtx, owns, (attempt) =>
    post({
      kind: "reply",
      parent: id,
      version: VNUM,
      text,
      attempt,
    }),
  );
  replyFlights.set(id, flight);
  tellReplyFlight(id);
  try {
    return await flight;
  } finally {
    replyFlights.delete(id);
    tellReplyFlight(id);
  }
}

// One reply draft and one send path, however many views the thread has. The panel adds
// an address and reveals the sent message; an inline conversation supplies neither.
// Everything else — persistence, mirroring, the wire event and the focus landing — is
// the thread's and is therefore stated once.
function wireReply(t, input, send, { address, landed } = {}) {
  const draftCtx = "reply:" + t.root.id;
  input.value = loadDraft(draftCtx) ?? "";
  const sync = wireInput(input, {
    hint: "Reply",
    sends: "send",
    address,
    sendBtn: send,
    busy: () => replyBusy(t.root.id),
    // localStorage notifies other tabs but skips this document. A conversation's
    // inline and panel boxes are two views here, so reply drafts take the same bus
    // directly. Other draft kinds still have one view per document.
    save: (v) => {
      saveDraft(draftCtx, v);
      tellDraft(draftCtx, v);
    },
    send: async (text, raw) => {
      const sent = await sendReply(t, text, raw, () => input.value === raw);
      if (!sent) return;
      landed?.(sent);
      landTyping(input);
    },
  });
  sync();
  mirrorDraft(input, sync, draftCtx);
  mirrorReplyFlight(input, sync, t.root.id);
  return sync;
}

function conversationMessageNode(thread, message) {
  let node = thread.querySelector(
    `:scope > .lf-conversation-msg[data-event="${message.id}"]`,
  );
  if (node) {
    const time = node.querySelector("time");
    const when = ago(message.ts);
    if (time.textContent !== when) time.textContent = when;
    return node;
  }
  node = offer("div", `lf-conversation-msg ${message.author}`);
  node.dataset.event = message.id;
  const head = el("div", "lf-conversation-head");
  head.append(
    el("b", "", message.author === "claude" ? message.agent || "Agent" : "You"),
    el("time", "", ago(message.ts)),
  );
  const body = el("div", "lf-conversation-body");
  if (message.suggestion) body.textContent = message.text;
  else body.innerHTML = renderMarkdown(message.text);
  node.append(head, body);
  if (message.markup) {
    const open = offer("button", "lf-btn lf-conversation-open", "Open in Comments");
    open.onclick = () => revealThread(message.id);
    node.append(open);
  }
  return node;
}

function conversationThreadNode(host, t) {
  let thread = host.querySelector(
    `:scope > .lf-conversation-thread[data-thread="${t.root.id}"]`,
  );
  if (!thread) {
    thread = offer("div", "lf-conversation-thread");
    thread.dataset.thread = t.root.id;
    thread.tabIndex = -1;
  }
  const messages = t.msgs.map((message) => conversationMessageNode(thread, message));
  let tail;
  if (t.resolved) {
    const compose = thread.querySelector(":scope > .lf-say");
    if (compose?.contains(focused())) thread.focus({ preventScroll: true });
    tail = thread.querySelector(":scope > .lf-conversation-resolved");
    const settledBy =
      t.resolved.author === "claude"
        ? `✓ Resolved by ${t.resolved.agent || "Agent"}`
        : "✓ Resolved";
    if (!tail) tail = offer("div", "lf-conversation-resolved");
    if (tail.textContent !== settledBy) tail.textContent = settledBy;
  } else {
    tail = thread.querySelector(":scope > .lf-say");
    if (!tail) {
      tail = offer("div", "lf-say");
      const input = offer("textarea");
      const send = offer("button", "lf-btn primary", "Send");
      tail.append(input, send);
      wireReply(t, input, send);
    }
  }
  setChildren(thread, [...messages, tail]);
  return thread;
}

function renderConversations(threads) {
  for (const host of document.querySelectorAll(
    ".lf-conversation[data-lf-conversation]",
  )) {
    const owner = elementById(host.dataset.lfConversation);
    const owned = threads.filter((thread) => {
      const anchor = thread.root.anchor;
      return (
        !thread.root.about &&
        anchor?.section === owner.id &&
        Object.keys(anchor).length === 1
      );
    });
    // Before the first comment, conversationBox's first-message composer is already
    // the complete view. An externally arriving root may find unsent first-message
    // words here, so the root does not get to take their only box: presence in the
    // draft store (including "") keeps it after the existing threads until a successful
    // send settles it. A box with no draft gives way to the conversation immediately.
    if (!owned.length) continue;
    const first = host.lfFirstMessage;
    const pending = loadDraft("say:" + owner.id) !== null ? first : null;
    setChildren(host, [
      ...owned.map((thread) => conversationThreadNode(host, thread)),
      ...(pending ? [pending] : []),
    ]);
  }
}

// A thread's node is found where it already stands — the open list or the resolved
// disclosure — and kept: the log is append-only, so a kept node only ever gains
// messages and refreshes its clocks. A settlement transition reshapes a node: resolving
// removes the reply box and reopening restores it, so either one rebuilds the node;
// msgBodies carries the rendered bodies across. `grow` animates what this call creates,
// for arrivals into a list the user is already looking at.
function threadNode(t, grow) {
  const existing = threadsBox.querySelector(`.lf-thread[data-id="${t.root.id}"]`);
  const existingResolved = existing && !existing.querySelector(":scope > .lf-compose");
  if (existing && existingResolved === Boolean(t.resolved)) {
    const compose = existing.querySelector(":scope > .lf-compose");
    const tail = compose ?? existing.querySelector(":scope > .lf-thread-actions");
    for (const m of t.msgs) {
      let msg = existing.querySelector(`:scope > .lf-msg[data-mid="${m.id}"]`);
      if (!msg) {
        msg = msgNode(m);
        if (grow) msg.classList.add("grow");
        existing.insertBefore(msg, tail);
      }
      // The head's clock, not any <time> a reply's own markup might carry.
      const time = msg.querySelector(":scope > .lf-msg-head time");
      const when = ago(m.ts);
      if (time.textContent !== when) time.textContent = when;
      syncMsg(msg, m);
    }
    return existing;
  }

  const div = el("div", "lf-thread");
  div.tabIndex = -1; // j/k focus target; the thread scope's Enter drops into its reply box
  div.dataset.id = t.root.id;
  if (grow) div.classList.add("grow");
  const label = anchorLabel(t.root.anchor, t.root.about);
  if (label) {
    const quote = el("blockquote", "lf-quote", label);
    quote.onclick = () => scrollToThread(t.root.id);
    div.append(quote);
  }
  t.msgs.forEach((m) => div.append(msgNode(m)));
  if (!t.resolved) {
    const row = el("div", "lf-compose");
    const input = document.createElement("textarea");
    const send = el("button", "lf-btn primary lf-thread-send", "Send");
    row.append(input);
    div.lfSync = wireReply(t, input, send, {
      // The box's address, spoken by its own placeholder at all times ("Reply · g c 2")
      // — which is what a screen reader hears, the chip the chord paints being the eye's
      // copy of the same fact. Read off the list rather than off a number written here,
      // because the address is positional: resolving an early thread renumbers every one
      // after it without touching their nodes, and renderThreads repaints them all.
      address: () => {
        const num = addressed(COMMENTS).indexOf(div) + 1;
        return num ? addressLabel(COMMENTS, num) : "";
      },
      landed: (sent) => revealThread(sent.id),
    });
    const actions = el("div", "lf-thread-actions");
    const resolve = el("button", "lf-btn lf-resolve", "Resolve");
    // Resolving takes this node out of the open list and focus with it — the blind
    // drive fell to body here. Land where j would have gone: the thread that now
    // holds this one's place, else the previous, else the list. Which is read after
    // the trip, off the list the fold has already left (foldOut renames the node the
    // frame the log settles it), so the landing is a thread rather than the room the
    // pressed one is still giving back.
    // Disabled for the flight (the bulk-answer buttons' shape): the r key repeats while
    // held, and every repeat before the poll replaces this node would post the
    // same resolve again. Re-enabled for the one path that keeps the node — a
    // send that failed, where the press must stay pressable; where it went through,
    // the fold has made the whole node inert and there is nothing to re-enable into.
    resolve.onclick = async () => {
      const at = openThreads().indexOf(div);
      resolve.disabled = true;
      try {
        await post({ kind: "resolve", parent: t.root.id });
      } finally {
        resolve.disabled = false;
      }
      const kept = openThreads();
      (kept[at] ?? kept[at - 1] ?? threadsBox).focus({ preventScroll: true });
    };
    actions.append(send, resolve);
    div.append(row, actions);
  } else {
    const actions = el("div", "lf-thread-actions");
    const status = el("span");
    if (t.resolved.author === "claude") {
      // Said only where the reader was not the one who closed it. Their own resolve
      // needs no telling: they pressed it, and the disclosure they find it under is
      // already headed "Resolved". A thread closed from the other side settles with
      // nothing in this tab to watch it happen, so the page is the only thing that can
      // say who did.
      const by = t.resolved.agent || "Agent";
      status.append(el("span", "lf-resolved-by", `✓ Resolved by ${by}`));
    }
    const reopen = el("button", "lf-reopen lf-thread-action", "Reopen");
    reopen.onclick = async () => {
      reopen.disabled = true;
      try {
        await post({ kind: "unresolve", parent: t.root.id });
      } finally {
        reopen.disabled = false;
      }
      threadsBox
        .querySelector(`:scope > .lf-thread[data-id="${t.root.id}"]`)
        ?.focus({ preventScroll: true });
      revealThread(t.root.id);
    };
    actions.append(status, reopen);
    div.append(actions);
  }
  return div;
}

// A thread the log has resolved and the open list is still holding. Its place is not
// given up in the frame the log settles it: the node stays where it stood, says what
// was done to it on the control that was pressed, and folds, so the threads under it
// rise where the eye can follow instead of arriving somewhere else. The disclosure
// gets the thread when the fold is over, which is what keeps one node per thread the
// whole way through.
//
// Driven from the reconcile rather than from the press, because the log is what
// resolves a thread and a resolve with no gesture behind it — a second tab's, or the
// agent's — takes the same room out of the same list. That is the case that needs the
// motion more: nothing in this tab moved, so the fold is the only thing saying so.
//
// Everything that walks the list asks for .lf-thread, so the one rename takes the
// node out of j/k, out of the g addresses, out of r's press and out of what the panel
// repaints, in a stroke: what stands there is room, not a thread. `inert` says the
// same to the pointer and the tab order, so the fold can't be pressed a second time
// or typed into on its way out.
//
// Null where there is nothing to fold: a thread this page never drew open, or a
// reader who asked for less motion, for whom the room goes in the frame it always did.
const folding = new Map(); // thread id -> the node folding out of the open list
function foldOut(t) {
  const going = folding.get(t.root.id);
  // For as long as it stands in the list, which is the whole of what the record
  // claims. A reader who reopens a thread mid-fold has that render drop the folding
  // node from the list, and the entry left behind names a node in nothing: handed
  // back when they settle the thread again, it would stand a spent animation where
  // the thread is, saying what the thread said before it reopened, and the thread
  // would leave with no fold at all. The node's own connectedness is that fact, read
  // here rather than written from wherever a node leaves the list, which is the
  // difference between one writer and every caller of setChildren remembering.
  // Dropped rather than passed over, because the two returns below leave without
  // setting one, and an entry over a thread nothing is folding hides that thread
  // from the disclosure that should be holding it by then.
  if (going?.isConnected) return going;
  folding.delete(t.root.id);
  const node = threadsBox.querySelector(`:scope > .lf-thread[data-id="${t.root.id}"]`);
  if (!node) return null;
  // Measured before anything about the node changes, and stated as a border box —
  // the measurement to hand is the rendered one, and .lf-going sizes to match. The
  // border and padding go with the height because border-box floors the box at
  // their sum: left standing, they would hold 22px open under a height of zero.
  const style = getComputedStyle(node);
  const from = {
    height: node.getBoundingClientRect().height + "px",
    marginBottom: style.marginBottom,
    borderTopWidth: style.borderTopWidth,
    borderBottomWidth: style.borderBottomWidth,
    paddingTop: style.paddingTop,
    paddingBottom: style.paddingBottom,
    opacity: 1,
  };
  const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
  to.opacity = 0;
  const played = motion(node, [from, to], FOLD_MS);
  if (!played) return null;
  // The control the press was made on states the outcome where it stood. It needs no
  // reservation for the longer word: Send and Resolve hold the two edges, so the
  // longer outcome takes room from the gap and moves neither edge. Send stays in the
  // row with visibility hidden, keeping the same room without reading as live.
  node.querySelector(":scope > .lf-thread-actions > .lf-resolve").textContent =
    "✓ Resolved";
  node.className = "lf-going";
  node.inert = true;
  // A key on screen is a key that works, and this box's placeholder was still
  // offering the address the thread under it has just taken: the repaint every other
  // reply box gets is the trailing loop's, which asks for .lf-thread and so no longer
  // finds this one. Painted here, from the same map, at the one moment the answer
  // changes — the address is gone the frame the log settles the thread, and what the
  // box says on its way out is "Reply" and no promise.
  node.lfSync();
  folding.set(t.root.id, node);
  // Straight off the promise, and nothing between: motion() holds the last keyframe
  // while this direct reaction makes that frame true by removing the node, then its
  // shared reaction releases the effect. Deferring this cleanup past that contract
  // would put the whole thread back before it goes. What holds the line is
  // test_the_fold_never_paints_a_frame_that_undoes_the_last, since no held frame can
  // see it.
  played.finished.then(() => {
    // This node's own entry, never whatever the thread's key holds now: a fold the
    // line above superseded is still running, and the older one finishing must not
    // take the live one's record with it.
    if (folding.get(t.root.id) === node) folding.delete(t.root.id);
    node.remove();
    renderPanel();
  });
  return node;
}

// The DOM is the one record of what's rendered, reconciled against the log: nodes the
// list already holds are kept, and only what the log changed is added, moved, or
// dropped. The rebuild this replaced destroyed every node on every render and then
// hand-restored the reader's place — scroll offset, focused thread, caret — and what
// no restore could give back was identity: nothing could animate, one send route kept
// focus and the other dropped it, and a user's own comment landed below the fold
// of a list put back exactly where it was. Nodes surviving is what deleted all of it.
function renderThreads(threads) {
  const open = threads.filter((t) => !t.resolved);
  const resolved = threads.filter((t) => t.resolved);
  // Newcomers settle in (`grow`) only when the user already has the list in front
  // of them: the first populated render is the page loading, not news arriving, and a
  // node animated while the panel is closed would replay the moment it opens.
  // (Reduced motion isn't asked here: grow is a CSS animation, and those are the
  // theme's one global guard's to stop.)
  const grow = panelOpen && Boolean(threadsBox.querySelector(":scope > .lf-thread"));

  const wanted = [];
  if (!threads.length) wanted.push(emptyNote);
  // Walked in the log's order rather than the open list's, because a thread on its way
  // out still stands between its neighbours while it folds (foldOut) and the two
  // orders are the same walk with one of them filtered. The first nine open threads
  // are addressable (g c 1–9), in the order j/k walk; past nine, digits stop and j/k
  // still reach everything. A folding thread takes no address and is walked by
  // nothing: the log has already settled it, and only its room is still here.
  for (const t of threads) {
    if (t.resolved) {
      const going = foldOut(t);
      if (going) wanted.push(going);
      continue;
    }
    wanted.push(threadNode(t, grow));
  }
  for (const e of events) {
    if (e.kind === "done") wanted.push(systemNode(e, `✓ Approved ${ago(e.ts)}`));
  }
  if (resolved.length) {
    if (!resolvedBox) {
      resolvedBox = el("details", "lf-details");
      resolvedBox.append(el("summary"));
    }
    const summary = resolvedBox.firstChild;
    // Counted off the log, listed off the page: a thread still folding out of the
    // open list is resolved and says so in the count from the first frame, and is
    // rebuilt in here when its fold is done rather than standing in two places at
    // once.
    const said = `Resolved (${resolved.length})`;
    if (summary.textContent !== said) summary.textContent = said;
    setChildren(resolvedBox, [
      summary,
      ...resolved
        .filter((t) => !folding.has(t.root.id))
        .map((t) => threadNode(t, false)),
    ]);
    wanted.push(resolvedBox);
  }
  setChildren(threadsBox, wanted);
  // A comment carries whatever widget markup the gate allows, so the panel holds the
  // same scroll boxes the page does, in a column half the width — and reachScrollers
  // wants two things that are only true here, after this line. A message body is built
  // detached, where `getComputedStyle` answers "" for every property, so a sweep at the
  // point the body is filled tagged nothing at all and had done since it was written,
  // reading like coverage the whole time. And a widget in that body upgrades on being
  // connected, not on being written, so the queue it registers its render with
  // (`settling`) has the promise only once this reconcile has appended it — which is
  // why the wait is here rather than a snapshot taken earlier. The queue is read, never
  // joined: nothing about the page's own first anchor pass waits on a message.
  Promise.allSettled(settling).then(() => reachScrollers(threadsBox));

  // Each reply box speaks its own address, repainted after ordering because resolving an
  // early thread renumbers everything after it — and read off the list this reconcile has
  // just written, which is why the loop is here and not where the boxes were built.
  for (const div of openThreads()) div.lfSync();
  toggleBtn.textContent = `Comments (${open.length})`;
  paintHere(); // the j/k and g rows, and an armed window's chips, stand on this list
}

// A kept node may still be moved by a later reconcile, and reinsertion restarts CSS
// animations — so the class comes off the moment its animation has run. A node grown
// while its list was off-screen never ran one; the panelOpen gate above is what keeps
// that replay from greeting the panel's next open.
threadsBox.addEventListener("animationend", (ev) => ev.target.classList.remove("grow"));

// The panel and the page marks are two views of the same threads, and the paint pass
// reports back to the list renderThreads just reconciled — always render them as a pair.
function renderPanel() {
  if (statePhase !== "ready") {
    waitingNote.textContent =
      statePhase === "offline"
        ? "Current comments are unavailable while the server is offline."
        : "Loading current comments…";
    setChildren(threadsBox, [waitingNote]);
    toggleBtn.textContent = "Comments";
    paintHere();
    return;
  }
  const threads = buildThreads();
  renderThreads(threads);
  renderConversations(threads);
  paintAnchors(threads);
}

// One answer to "show me that thread", whoever asks: a click on a mark out on the page
// and a send that just landed both come here, with a thread's id or a message's. The
// panel scrolls its own list — moving the page to a thread's passage is scrollToThread,
// a different question — and flashes the thread. The flash takes over from a running
// grow explicitly: both classes bind the element's one animation declaration, and the
// send's confirmation is the one the gesture asked for.
function revealThread(id) {
  setPanel(true);
  const node = threadsBox.querySelector(
    `.lf-thread[data-id="${id}"], .lf-msg[data-mid="${id}"]`,
  );
  if (!node) return;
  const thread = node.closest(".lf-thread");
  node.scrollIntoView({
    behavior: SCROLL,
    block: node === thread ? "center" : "nearest",
  });
  thread.classList.remove("grow");
  thread.classList.add("flash");
  setTimeout(() => thread.classList.remove("flash"), 1300);
}

// ---------- passages ----------
// A passage is a list of {node, start, end} segments, and everything that reads the page's
// text speaks in them: the search for a quote, the capture of one, the landmark a version
// change rides on, the version diff's block keys. One shape means one answer to what the
// page says. The bugs this layer kept having were all a second answer disagreeing with the
// first — what a selection rendered as versus what the document holds — and a second
// answer is what there is now no room for.
//
// Two skip lists, because two jobs genuinely differ, and the difference is the whole
// reason .lf-ui and data-lf-gen are two markers rather than one. Anchoring skips the
// runtime's own words, inline scripts, and the stylesheet a rendered diagram carries
// inside its <svg>: a quote holding text the search skips is a quote nothing can find
// again. The version diff additionally skips content an upgrade generated, because the
// base document parses unupgraded and would never match it. So generated text the page
// authored — a widget's label, an attribute renderSaid rendered — is diff-invisible and
// quotable, which is the pair a user expects: they can point at it, and it doesn't
// read as a change nobody wrote.
//
// A decided suggestion's retired slot goes with them. Its markup is still in the
// document — the honoring version is what finally drops it — but the user has
// removed it, and the live view is the version plus their decisions. Text nobody can
// see is text nobody can mean: without this a comment made on a passage then accepted
// away kept reading as attached in the panel and jumped nowhere, and a quote from
// elsewhere could match inside the invisible half of a replacement.
//
// Which slots retire is the registry's to say, so this and interact.py's reading of the
// same page follow one declaration: x-retired-when names the decision that removes the
// element, x-parent the wrapper the decision is recorded on.
// Computed once — but only once the registry has loaded: the aim listeners are
// live from module evaluation, and a mousemove in the upgrade window would
// otherwise seed the cache from the empty pre-fetch registry and disable the
// retired-slot skip for the life of the page. It used to be rebuilt per
// candidate ancestor per mousemove (itemAt's aim walk).
let retiredSlotsMemo;
function retiredSlots() {
  if (retiredSlotsMemo != null) return retiredSlotsMemo;
  // One selector per holder, never the array interpolated: `x-parent` is a list, and
  // `${list}` joins it with a comma, so a slot naming two holders wrote a selector
  // *list* whose first member was a bare tag — every instance of the first holder read
  // as a retired slot, decided or not, and the pair that was meant matched nothing.
  const value = widgetEntries()
    .filter(([, entry]) => entry["x-retired-when"])
    .flatMap(([tag, entry]) =>
      entry["x-parent"].map(
        (parent) => `${parent}[data-lf-state="${entry["x-retired-when"]}"] > ${tag}`,
      ),
    )
    .join(", ");
  if (Object.keys(registry).length) retiredSlotsMemo = value;
  return value;
}
// The same relation read the other way: holder tag → each settling outcome and the
// slot tags that leave the page under it. Replay reads it to paint the settlement
// (markSettled, renderRetired), so which verbs settle a holder is the registry's fact
// here exactly as it is in the selector above. Same registry-loaded guard, for the
// same aim-window reason.
let settlementSlotsMemo;
function settlementSlots() {
  if (settlementSlotsMemo != null) return settlementSlotsMemo;
  const value = {};
  for (const [tag, entry] of widgetEntries().filter(([, e]) => e["x-retired-when"]))
    for (const parent of entry["x-parent"])
      ((value[parent] ??= {})[entry["x-retired-when"]] ??= []).push(tag);
  if (Object.keys(registry).length) settlementSlotsMemo = value;
  return value;
}

// The rendering of a settlement, in one place for the two occasions that paint it —
// replay (markSettled) and a module saying its own gesture (lf-suggestion's #settle):
// reads the holder's mark and paints data-lf-retired onto the slots the standing
// outcome retires, clearing it from the rest. One static theme rule hides the marked
// slots, so a family a project declares hides what a settlement removes the day it
// declares it — by-name rules in theme.css were the closed list wearing CSS's
// clothes — and the same pair of marker and rule is what carries the disappearance
// into an exported copy, which keeps markup and stylesheet and drops every module.
export function renderRetired(el) {
  const outcomes = settlementSlots()[el.localName];
  if (!outcomes) return;
  const mark = el.getAttribute("data-lf-state");
  for (const [outcome, tags] of Object.entries(outcomes))
    for (const tag of tags)
      for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
        for (const slot of root.querySelectorAll(`:scope > ${tag}`))
          slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, outcome === mark);
}
// What no label can speak through, however it is marked: an inline script, the
// stylesheet a rendered diagram carries inside its <svg>, and a slot the user's
// decision took off the page. Chrome is the rest of what the anchor pass skips and
// the one part a label yields — it is a look, and a look cannot make a word the
// runtime's.
let silencedMemo;
function silenced() {
  if (silencedMemo) return silencedMemo;
  const retired = retiredSlots();
  const value = ["script", "style", ...(retired ? [retired] : [])].join(", ");
  // Same registry-loaded guard as retiredSlots, for the same aim-window reason.
  if (Object.keys(registry).length) silencedMemo = value;
  return value;
}

// An element the user's decision took off the page, asked of an element rather
// than of text: a retired slot (or anything inside one), or a decided element the
// retirement emptied — a deletion accepted, an insertion refused — whose every child
// is now a retired slot or the runtime's own chrome, with no text of its own. The
// same declaration the anchor pass skips text by answers both (`inUi`, so a child
// that is a declared label counts as words still showing), and so an element anchor
// and a quote cannot disagree about what left the page.
function settledAway(el) {
  const retired = retiredSlots();
  if (!retired) return false;
  if (el.closest(retired)) return true;
  const nodes = [...el.childNodes];
  return (
    nodes.some((n) => n.nodeType === 1 && n.matches(retired)) &&
    nodes.every((n) =>
      n.nodeType === 1
        ? n.matches(retired) || inUi(n)
        : n.nodeType !== 3 || !n.data.trim(),
    )
  );
}
const GENERATED = ".lf-ui, [data-lf-gen]";
// A label a widget declared as the page speaking (relabel), which the anchor pass reads
// over the chrome it sits in.
const SAID = "[data-lf-said]";
// The same question one node at a time: is this the runtime's own chrome rather than the
// document? Every affordance asks it before acting on where the pointer or the caret is.
// The nearest element that answers wins: a declared label is the page's words inside the
// control it labels, and a control nested inside one is chrome again. `.lf-ui` alone was
// the answer once, and it is a look — which is how a user ended up reading a heading
// they could not point at, twice.
export const inUi = (node) => {
  const near = (node?.nodeType === 1 ? node : node?.parentElement)?.closest(
    `.lf-ui, ${SAID}`,
  );
  return Boolean(near) && !near.matches(SAID);
};
// A different question the class also used to answer, and not a question about looks at
// all: which document is this element in? The runtime's layer is one container, so a
// widget inside a reply — markup frozen in the log, carried by no version — is exactly
// what that container holds, and the reading position is a place in the page rather than
// in the panel over it. `.lf-ui` reached those elements and a widget's own controls out
// on the page besides, which is the look standing in for the place.
// Across the boundary for the same reason the climb below is: the marker lives out in
// the document, so a node inside a widget's shadow tree can only reach it by leaving the
// tree, and a widget staged inside a reply would otherwise read as page content.
export const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
const TEXT_BLOCK =
  "p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary";
// The two readings, each one predicate over a text node and named for the question it
// answers. Anchoring reads what the user can point at: not the runtime's own words —
// `inUi`, which a declared label answers for itself — and nothing behind a wall no label
// speaks through, so a pick mark inside a slot the user accepted away is gone with
// the slot, its marker notwithstanding. The diff reads what the base version holds, and
// the base parses unupgraded, so everything an upgrade generated goes, a declared label
// included: the version being compared against has none.
//
// Built per walk rather than per node, because the retired half of the wall is read out
// of the registry each time it is asked for.
// A text node's parent is an element, and all four readings of these nodes say so:
// the two below, pageText's cell walk and snapOut's seam. Written four ways it was four
// answers to one question, three of them asserting the parent and one quietly admitting
// a node without one — which is a claim about the page nothing backs: what a widget
// stages into a shadow root is the only text these walks reach with no element over it,
// and a module staging a bare text node would be handing the page words no cell, no
// fence and no block. So the assertion is one function, and refusing is what it does.
//
// It refuses in the words of the mistake, which is the half that was missing. Throwing
// out of the pass the render gate reads the console for is the loud direction, and the
// throw was `Cannot read properties of null (reading 'closest')` on a page showing
// nothing at all — naming neither the widget that staged the text nor what was wrong
// with it. A refusal whose message is a property name reaches its author as the runtime
// being broken, which is the one thing it isn't.
const elementOver = (n) => {
  if (n.parentElement) return n.parentElement;
  const host = n.getRootNode()?.host;
  const at = host
    ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>`
    : "a module";
  throw new Error(
    `${at} staged bare text into a shadow root: ` +
      `${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, ` +
      `so the page holds no block, cell or fence for it. Give a module's rendered ` +
      `words an element to sit in.`,
  );
};
const quotable = () => {
  const gone = silenced();
  return (n) => !inUi(n) && !elementOver(n).closest(gone);
};
const authored = () => (n) => !elementOver(n).closest(GENERATED);
// The composed tree, not the light one: a widget that renders the page's words into an
// open shadow root (x-shadow) shows the reader what its shadow tree holds, and a host's
// own children stop rendering the moment it has one. A TreeWalker sees none of that — it
// stops dead at the boundary — so the walk is written out, and it is the same walk in
// both directions: a host's shadow root stands in for its children, a <slot> stands for
// what was assigned to it, and everything else is the light DOM it always was. Nothing
// here asks which widget it is looking at; a document with no shadow roots in it walks
// exactly as it did before.
//
// The order is what earns the recursion. `pageText` builds one string in reading order
// and indexes every position into it, so shadow text has to arrive at the host's own
// place in that string — not appended from a second walk, which would put a diff's lines
// after the page's last paragraph and every neighbour of theirs a lie.
export function textNodesUnder(rootEl, accepts = quotable()) {
  const segments = [];
  const visit = (node) => {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        if (accepts(child))
          segments.push({ node: child, start: 0, end: child.data.length });
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) continue;
      if (child.localName === "slot")
        for (const assigned of child.assignedNodes({ flatten: true }))
          assigned.nodeType === Node.TEXT_NODE
            ? accepts(assigned) &&
              segments.push({
                node: assigned,
                start: 0,
                end: assigned.data.length,
              })
            : visit(assigned);
      else {
        // Only a root the registry declares (x-shadow): the capture asks
        // getComposedRanges for exactly the declared ones, and every climb
        // crosses exactly those — so a walk that entered any open root read
        // words the anchor side could never place, and a widget's undeclared
        // root anchored quotes astray instead of staying opaque. The render gate
        // names an undeclared root; this leaves its words alone.
        const declared = child.shadowRoot && registry[child.localName]?.["x-shadow"];
        visit(declared ? child.shadowRoot : child);
      }
    }
  };
  visit(rootEl);
  return segments;
}

// One step towards the document from any node, shadow boundary included: the ordinary
// parent within a tree, and the host where a tree runs out. Every question the runtime
// asks about where a node sits — which section, which block, which passage cell, whether
// it is chrome — is asked of the page, and a climb that stops at a shadow root answers
// about the widget's own markup instead.
const upFrom = (node) => node.parentElement ?? node.getRootNode()?.host ?? null;

// contains() stops at a boundary the same way, and this is the one that decides whether a
// quote is found at all: a section holding an x-shadow widget does not contain the words
// that widget renders, so narrowing a search to that section threw away every candidate
// inside it and the passage resolved to nothing — the anchor captured, the mark never
// painted. Asked of each tree on the way out, so the section contains what it renders.
const containsAcross = (ancestor, node) => {
  for (let n = node; n; n = n.getRootNode()?.host ?? null)
    if (ancestor.contains(n)) return true;
  return false;
};

// closest() stops at a shadow boundary, so a node inside a widget's shadow tree can't
// reach the section that holds it or the chrome marker above it — both out in the
// document. Same climb as upFrom, asked with a selector at each tree it passes through.
function closestAcross(node, selector) {
  let el = node?.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
  while (el) {
    const hit = el.closest(selector);
    if (hit) return hit;
    el = el.getRootNode()?.host ?? null;
  }
  return null;
}

// getElementById searches the document tree alone, which is the same boundary again and
// the one every question the runtime asks by id runs into: which element an anchor names,
// what an action rests on, which unit a fold paints, which ask a key steps to. A widget
// that stages its authored children into a shadow tree takes their ids in there with it,
// and each of those answers would come back null and quietly do nothing — the anchor
// captured, the mark never painted, no error anywhere. The document first, because that
// is where everything but a staged widget's own parts lives, and only the roots the
// registry declares after it, so the walk sees what the capture saw.
const elementById = (id) => {
  const found = document.getElementById(id);
  if (found) return found;
  for (const root of pageShadowRoots()) {
    const inside = root.getElementById(id);
    if (inside) return inside;
  }
  return null;
};

// elementFromPoint retargets to the host for a point over a shadow tree, so it names the
// widget rather than the thing in it, and each root answers for its own. Asked only where
// the question is which element exactly the pointer is over (markAt, deciding which of
// several marks it touched). Where the question is which *item* the reader is aiming at,
// the host is the right answer and this is the wrong helper: aiming at a diff means the
// diff, whose rows are nothing anyone can anchor on (aimedItem).
const elementFromPointAcross = (x, y) => {
  let el = document.elementFromPoint(x, y);
  while (el?.shadowRoot) {
    const inner = el.shadowRoot.elementFromPoint(x, y);
    if (!inner || inner === el) break;
    el = inner;
  }
  return el;
};

// A pass that clears its own marks before repainting has to sweep everywhere it can
// write, and `elementById` above is what widened that: a mark placed on a staged element
// sits in a tree `document.querySelectorAll` never enters, so the clear would miss it and
// the mark outlive the reason for it. Only the runtime's own marks are read back this
// way. Which widgets the page holds is a different question and still the document's:
// a widget staged inside another's tree is a nesting the registry's x-parent contract
// does not model, and answering it here would be inventing that contract in a sweep.
const pageQueryAll = (selector) =>
  [document, ...pageShadowRoots()].flatMap((root) => [
    ...root.querySelectorAll(selector),
  ]);

// The range the reader actually drew. Chrome keeps the legacy Range in the light DOM: a
// drag wholly inside a widget's shadow tree comes back with `commonAncestorContainer` at
// BODY and its ends clamped to the host, so `sel.toString()` says the right words while
// every node the capture would index says the wrong place. That is the one failure mode
// worth naming twice — not a refusal, which the fence rule turns into a message to the
// author, but a quote anchored somewhere the reader never pointed.
//
// `getComposedRanges` is the only thing that answers truthfully, and it answers only for
// the roots it is handed, which is why the declaration (x-shadow) and not a sweep decides
// what is passed. A selection that starts in one tree and ends in another is left to the
// light-DOM range on purpose: a Range cannot hold ends in two roots, and a quote running
// from the page's prose into a widget's shadow is exactly what the fences already refuse.
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

// Whether a range covers a node, asked so a shadow tree answers the same as the light
// DOM it renders in place of. `intersectsNode` compares within one tree, so every node
// inside an x-shadow widget says no to a range drawn out in the document — and a drag
// from the paragraph above a diff to the one below it would come back holding the two
// paragraphs joined, with the lines the reader dragged straight over missing from the
// quote and still sitting between them in the reading, so the search could never find
// it. The tree renders where its host stands, so the host is what the question is really
// about: climb to whichever ancestor shares the range's root, and ask there.
function coveredBy(range, node) {
  const root = range.commonAncestorContainer.getRootNode();
  let n = node;
  while (n && n.getRootNode() !== root) n = n.getRootNode().host;
  return Boolean(n) && range.intersectsNode(n);
}

// The segments a selection covers, clipped to where it starts and ends.
function segmentsIn(range) {
  const root = range.commonAncestorContainer;
  const whole = textNodesUnder(
    root.nodeType === Node.ELEMENT_NODE ? root : root.parentElement,
  );
  const segments = [];
  for (const { node, end: length } of whole) {
    if (!coveredBy(range, node)) continue;
    const start = node === range.startContainer ? range.startOffset : 0;
    const end = node === range.endContainer ? range.endOffset : length;
    if (end > start) segments.push({ node, start, end });
  }
  return segments;
}

// Segments as prose — what a comment stores as its quote, and what a reading position
// remembers. A space goes in wherever a block boundary falls between two segments, so a
// passage crossing two paragraphs doesn't read as one run-on word. Whitespace collapses,
// since the same passage carries the author's line wraps in the source and the rendering's
// on screen. Sliced by code point, because half a surrogate pair is a character no UTF-8
// file can hold. Where the spaces landed is cosmetic to the search: a quote's own
// whitespace is elastic to findQuote, so nothing downstream depends on this.
// The block a node reads as part of, and null where it belongs to no block of its own —
// which is a different answer from "its parent", and the two callers want different ones.
const blockAt = (node) => closestAcross(node, TEXT_BLOCK);
const blockOf = (node) => blockAt(node) ?? upFrom(node);
// One collapse class, stated outright and spelled to the same set interact.py's
// COLLAPSE_CHARS enumerates: JS's \s and Python's str.isspace() disagree at the
// edges — U+FEFF is whitespace to JS alone, U+0085 and U+001C–001F to Python
// alone — and a page carrying one of those in prose read differently on the two
// sides, so a `leaf comment` quote could be written against text this runtime
// never produces. (trim() removes exactly this class, so it needs no twin.)
const COLLAPSE =
  /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
function quoteFrom(segments) {
  let text = "";
  segments.forEach((seg, i) => {
    if (i && blockOf(seg.node) !== blockOf(segments[i - 1].node)) text += " ";
    text += seg.node.data.slice(seg.start, seg.end);
  });
  return [...text.replace(COLLAPSE, " ").trim()].join("");
}
// Cutting one to length is the caller's business and always by code point: half a surrogate
// pair is a character no UTF-8 file can hold, and a quote is written to one.
const cut = (text, from, to) => [...text].slice(from, to).join("");

// One lossless text alignment for every widget that needs to explain a sequence of
// whole-text states. Segmenter keeps words and punctuation in the language-aware
// units this runtime already assumes; a linear-space Hirschberg walk supplies the
// ordered shared spine. Its quadratic *time* is capped: after stripping a common
// prefix and suffix, a very large divergent middle is one replacement instead of a
// page-freezing attempt at fine-grained alignment. Joining same+delete reconstructs
// `before`, and joining same+insert reconstructs `after`, exactly.
const textUnits = new Intl.Segmenter(undefined, { granularity: "word" });
const ALIGN_CELLS = 1_000_000;

function lcsRow(left, lo, hi, right, rlo, rhi, reverse) {
  const width = rhi - rlo;
  let previous = new Uint32Array(width + 1);
  for (let at = 0; at < hi - lo; at++) {
    const current = new Uint32Array(width + 1);
    const word = reverse ? left[hi - at - 1] : left[lo + at];
    for (let across = 1; across <= width; across++) {
      const other = reverse ? right[rhi - across] : right[rlo + across - 1];
      current[across] =
        word === other
          ? previous[across - 1] + 1
          : Math.max(previous[across], current[across - 1]);
    }
    previous = current;
  }
  return previous;
}

function lcsMatches(left, lo, hi, right, rlo, rhi, matches) {
  if (lo === hi || rlo === rhi) return;
  if (hi - lo === 1) {
    for (let at = rlo; at < rhi; at++)
      if (left[lo] === right[at]) {
        matches.push([lo, at]);
        break;
      }
    return;
  }

  const middle = lo + Math.floor((hi - lo) / 2);
  let split = 0;
  {
    const forward = lcsRow(left, lo, middle, right, rlo, rhi, false);
    const backward = lcsRow(left, middle, hi, right, rlo, rhi, true);
    let best = -1;
    const width = rhi - rlo;
    for (let at = 0; at <= width; at++) {
      const score = forward[at] + backward[width - at];
      if (score > best) {
        best = score;
        split = at;
      }
    }
  }
  lcsMatches(left, lo, middle, right, rlo, rlo + split, matches);
  lcsMatches(left, middle, hi, right, rlo + split, rhi, matches);
}

export function alignText(before, after) {
  const left = [...textUnits.segment(before)].map((part) => part.segment);
  const right = [...textUnits.segment(after)].map((part) => part.segment);
  const runs = [];
  const push = (kind, text) => {
    if (!text) return;
    const last = runs.at(-1);
    if (last?.kind === kind) last.text += text;
    else runs.push({ kind, text });
  };

  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  )
    prefix++;
  let suffix = 0;
  while (
    prefix + suffix < left.length &&
    prefix + suffix < right.length &&
    left[left.length - suffix - 1] === right[right.length - suffix - 1]
  )
    suffix++;

  push("same", left.slice(0, prefix).join(""));
  const leftEnd = left.length - suffix;
  const rightEnd = right.length - suffix;
  const matches = [];
  if ((leftEnd - prefix) * (rightEnd - prefix) <= ALIGN_CELLS)
    lcsMatches(left, prefix, leftEnd, right, prefix, rightEnd, matches);

  let i = prefix;
  let j = prefix;
  for (const [li, rj] of matches) {
    push("delete", left.slice(i, li).join(""));
    push("insert", right.slice(j, rj).join(""));
    push("same", left[li]);
    i = li + 1;
    j = rj + 1;
  }
  push("delete", left.slice(i, leftEnd).join(""));
  push("insert", right.slice(j, rightEnd).join(""));
  push("same", left.slice(leftEnd).join(""));
  return runs;
}

// The words that moved between two texts: `{del, ins, shared}` — spans as [from, to) into
// `before` and into `after`, and the ink the two hold in common — or null where the pair
// shares too little of it to be worth marking. A wholesale swap is a replacement rather
// than an edit, and emphasis over everything says nothing the change's own tint already
// did — the similarity gate every mature diff view applies. Whitespace-only runs advance
// the cursors and mark nothing: reformatted markup is not a changed word.
//
// Sharing nothing is a replacement whatever the lengths are, and the ratio cannot say so
// on its own: where one side has no ink the smaller side is zero, so every pair clears a
// bar standing at zero. A deletion over an added blank line went through with its whole
// body marked as words that had moved — the one shape the gate exists to refuse.
//
// `shared` is the gate's own reading of how much of the pair stood still. lf-diff has a
// second question to put to it — of the additions in a change block, which one does this
// deletion answer — and settles it by comparing candidates on this number. Unsaid, it would
// have been recovered downstream from the spans, and that is a second definition of the
// same ink, one edit from disagreeing with this one.
//
// The alignment is taken here rather than passed in, because both consumers ask the same
// question and only the painting differs — lf-suggestion paints ranges through the
// highlight registry, lf-diff wraps spans, ::highlight() not reaching into a shadow tree.
// Written twice it would be two thresholds, and the reader would meet whichever was tuned
// last.
export function movedWords(before, after) {
  const runs = alignText(before, after);
  const ink = (text) => text.replace(/\s+/g, "").length;
  const shared = runs
    .filter((run) => run.kind === "same")
    .reduce((n, run) => n + ink(run.text), 0);
  if (!shared || shared * 3 < Math.min(ink(before), ink(after))) return null;
  const del = [];
  const ins = [];
  let o = 0;
  let n = 0;
  for (const run of runs) {
    const len = run.text.length;
    if (run.kind !== "insert") {
      if (run.kind === "delete" && run.text.trim()) del.push([o, o + len]);
      o += len;
    }
    if (run.kind !== "delete") {
      if (run.kind === "insert" && run.text.trim()) ins.push([n, n + len]);
      n += len;
    }
  }
  return { del, ins, shared };
}

// What an element says, read the way this file reads the page everywhere else. A widget
// wanting the words in one of its own slots asks for them here rather than through
// `textContent`, because the two differ: the paint pass writes a hidden line into any text
// block that carries a comment, including blocks inside a widget, and `textContent` returns
// it. A suggestion labelled that way offered to accept “Retry three times. 1 comment”.
export const says = (el) => quoteFrom(textNodesUnder(el));
// The other question, and a different answer: what the *author* wrote here, with
// everything an upgrade generated left out. The version diff asks it because the base
// version it compares against has no generated nodes at all; a widget asks it to name
// one of its own parts, where `says` would hand back the widget's own declared labels
// along with the words — a picked row's mark is the page speaking, so it is in the
// reading a user points at and out of the row's name.
export const wrote = (el) => quoteFrom(textNodesUnder(el, authored()));

// A passage as one Range: what paints it, and what measures it for a scroll.
function rangeOf(segments) {
  const range = document.createRange();
  range.setStart(segments[0].node, segments[0].start);
  range.setEnd(segments.at(-1).node, segments.at(-1).end);
  return range;
}

// Find `quote` among `segments`; returns the segments it covers, or none. The quote's own
// whitespace is treated as elastic and the page's is not, which is the asymmetry the
// problem actually has. The same passage gets written down with a break where the source
// wrapped it, with one where the rendering broke a block, and with none where two blocks
// abut, so a gap in the quote has to match any gap in the page or none at all — otherwise
// every producer has to agree on whitespace, and that agreement is the one this file kept
// getting wrong. The converse is not true: where the quote runs two words together the
// page may not, or a short quote starts matching inside longer words — "never" finding the
// tail of "on every", in a different paragraph.
// So a gap has to match *something* that separates words. Whitespace is one; an element
// boundary is the other, and it leaves no character behind, which is why the raw text is
// built with one standing in for it. Between the characters of a single word only a
// boundary may fall — `<strong>bold</strong>text` reads as one word and is quoted as one —
// and without that floor a gap could match nothing at all, so "set up" would find "setup"
// in an earlier sentence and anchor there for good.
const EDGE = "\u0000"; // no document holds one, so it can't collide with page text
// A quote names text, not a place, and a page is free to say the same thing twice. Where it
// does, the words on either side decide which occurrence was meant. A unified diff holds
// the same line on both sides by construction, so without this, commenting on a fixed line
// marked the broken one — the user's objection attached to the code they were objecting
// to, and stored that way. Section scoping cannot reach it, because both sides of a diff
// live under one id. Context rather than an offset: an offset goes stale silently when the
// page is revised, while neighbours can be checked against the page as it now stands — see
// `holds` for what checking them means, and what it deliberately refuses to do.
// Anchors written before this carry none: their quote resolves only when it has a
// single candidate, since there is no evidence that can identify one repeated copy.
// The characters of raw[lo..hi) as segments, so a neighbourhood can be read back with the
// same function that wrote it down. Edges hold no character and are simply absent.
function spanOf(origin, lo, hi) {
  const out = [];
  for (let i = Math.max(0, lo); i < Math.min(origin.length, hi); i++) {
    const at = origin[i];
    if (!at) continue;
    const last = out.at(-1);
    if (last && last.node === at.node && last.end === at.offset)
      last.end = at.offset + 1;
    else out.push({ node: at.node, start: at.offset, end: at.offset + 1 });
  }
  return out;
}
// Context identifies a passage only when its neighbours are still exactly what they were.
// A partial match is not weak evidence for the right copy — it is evidence the page moved
// on, and acting on it is how a comment ends up somewhere it was never made: a version that
// rewrote the sentence beside the anchored copy left an untouched copy elsewhere matching
// better, and the comment followed it there. Demanding the whole stored context prevents
// that: without one exact contextual match, only a quote with a sole candidate resolves;
// repeated candidates detach rather than inheriting document order.
//
// Rare, not impossible. The bar is however much was stored, and the capture reads the
// neighbours out of the whole document — a section is a filter on where a passage may sit,
// not on what surrounds it — so both sides are full except against the document's own
// ends. Anchors written before context reached past the section carry a side clipped at
// that edge; they confirm at that shorter bar, which is the bar they were stored under.
//
// The bar is what the capture actually produces, not a number picked to fit: across every
// selection in the shipped examples, an unmodified page confirms its stored context in full.
//
// An empty side is the case worth stating, because reading it as an absent constraint is
// what sends a comment to a copy it was never made on. The capture reads the whole
// document, so a side comes out empty only where the passage had nothing at all beside it:
// the top or bottom of the page, the one place no capture can give two sides to. That is
// not a missing constraint but the tightest one there is, and it is checkable — a candidate
// confirms it by also having nothing there, which exactly one occurrence does. Refusing to
// read it that way handed the last copy's mark to the first.
const holds = ({ origin, fences }, at, want, before) => {
  // One character is all it takes to refute an empty side, and asking for none would answer
  // with none: doubling zero never grows.
  const there = neighbourhood(origin, fences, at, want.length || 1, before);
  if (!want) return there === "";
  return before ? there.endsWith(want) : there.startsWith(want);
};
// As much collapsed text as the caller asked for, however much raw text that takes.
// A fixed raw budget reads less than the capture wrote wherever whitespace runs dense — an
// indented line inside a <pre> — and the right occurrence then confirms none of its own
// neighbours.
//
// Counted in code points, which is the unit both captures write in: `cut` slices the
// window this returns by code point, and interact.py's reading of the same passage slices
// a Python string, which has no other unit. Counting code units here stopped the growth
// early on any neighbourhood holding an emoji — the window reached 24 of them while
// holding 23 characters — so the browser stored a prefix a character short of the one the
// file's reading stores for that same passage, and the two captures wrote different
// anchors for one passage. `holds` asks in the other unit (`want.length`, the stored
// string's own, which is what its endsWith compares in), and that is an over-ask this can
// only over-satisfy: reaching N code points takes at least N code units, so its window is
// never the one short of confirming that a repeated anchor would detach over.
function neighbourhood(origin, fences, at, want, before) {
  const edge = before
    ? (fences.filter((f) => f <= at).at(-1) ?? 0)
    : (fences.find((f) => f >= at) ?? origin.length);
  for (let raw = want * 2; ; raw *= 2) {
    const lo = before ? Math.max(edge, at - raw) : at;
    const hi = before ? at : Math.min(edge, at + raw);
    const text = quoteFrom(spanOf(origin, lo, hi));
    if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
  }
}
// What the page says, once, as one string with a way back to the nodes it came from. Built
// per pass rather than per anchor: every anchor a pass places is asking about the same
// document, and the pass is what fixes which document that is — resolving each against its
// own fresh reading would let two marks in one pass answer for two different pages, since a
// widget can upgrade between them. Forty threads on a 13k-character page also spent it
// forty times: 9.3ms of index building per pass, besides the forty tree walks feeding
// it, against 1.5ms for the one read that replaces them.
function pageText() {
  let raw = "";
  const origin = []; // origin[i] = {node, offset} for raw[i]; null for an edge
  const positions = new WeakMap(); // text node -> its offset-zero position in raw
  const fences = new Set();
  const segments = textNodesUnder(document.body);

  // Generated page-words that the registry does not model are their own passage
  // cells. Controls and the hidden comment count contain no accepted text and never
  // become fences; x-says spans are already present in the file-side reading.
  const dynamicWords = new WeakSet();
  for (const seg of segments) {
    const generated = elementOver(seg.node).closest("[data-lf-gen]");
    if (!generated) continue;
    const attr = generated.getAttribute("data-lf-said");
    const hostEntry = registry[generated.parentElement?.localName];
    const declared = attr && hostEntry?.["x-says"]?.[attr];
    if (!declared) dynamicWords.add(generated);
  }
  // Climbing crosses the shadow boundary (upFrom), and that is what keeps an x-shadow
  // widget fenced. The parts were remembered off the light DOM before any module ran,
  // so nothing inside a shadow tree is in either set; a climb that stopped at the root
  // would put a diff's lines in no cell at all, which reads as ordinary page prose and
  // lets a quote run from the paragraph above straight into the first changed line. One
  // move further up finds the host, which is the opaque root it always was.
  const cellOf = (node) => {
    for (let el = upFrom(node); el; el = upFrom(el)) {
      if (dynamicWords.has(el)) return el;
      if (opaquePassageParts.has(el) || opaquePassageRoots.has(el)) return el;
    }
    return null;
  };

  let previousCell = null;
  let started = false;
  for (const seg of segments) {
    const cell = cellOf(seg.node);
    if (!started) {
      if (cell) fences.add(0);
      started = true;
    } else {
      if (cell !== previousCell && (cell || previousCell)) fences.add(raw.length);
      origin.push(null);
      raw += EDGE;
    }
    positions.set(seg.node, raw.length - seg.start);
    for (let i = seg.start; i < seg.end; i++) {
      origin.push({ node: seg.node, offset: i });
      raw += seg.node.data[i];
    }
    previousCell = cell;
  }
  if (previousCell) fences.add(raw.length);
  return { raw, origin, positions, fences: [...fences].sort((a, b) => a - b) };
}
// Where a passage's segments start and stop in that reading, as [start, stop). A passage
// is `{node, start, end}` segments and every question about the region it covers is asked
// in the reading's own coordinates, so the join between the two is one function — the
// capture writing an anchor's neighbours and the snap widening a drag both ask it. No
// segments is the document's own start: a selection that covers no quotable character has
// a position and no extent.
function spanIn(reading, segments) {
  const first = segments[0];
  const last = segments.at(-1);
  const start = first ? reading.positions.get(first.node) + first.start : 0;
  return [start, last ? reading.positions.get(last.node) + last.end : start];
}
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// How much of a quote the search compiles into its pattern. The bound is the pattern's,
// never the passage's: one expression covering every word of a long passage is a term
// per character, and V8 refuses to compile one that long at all — a ceiling a reader
// reaches by selecting a page and pressing c. Measured on the gallery: 1.3ms at this
// length, 11.6ms at five thousand characters, and a SyntaxError at twelve. So the lead
// finds the candidates and the rest of the quote is walked against the text from each,
// which is a comparison per character rather than a term, and the search stays flat in
// the passage's length instead of ending at a wall.
const LEAD_CAP = 400;
// The rest of a quote, matched from `at` by the pattern's own rules: any run of
// whitespace or edges between words, an edge free to fall between two characters of
// one. Answers where the passage ends, or -1 where the text stops saying it.
function confirmRest(raw, at, words) {
  let i = at;
  for (const w of words) {
    const gap = i;
    while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw[i]))) i++;
    if (i === gap) return -1; // two words the text runs together are not these two
    for (const ch of w) {
      while (raw[i] === EDGE) i++;
      if (!raw.startsWith(ch, i)) return -1;
      i += ch.length;
    }
  }
  return i;
}
function findQuote(text, quote, anchor, within) {
  const { raw, origin } = text;
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  // Whole words up to the cap, and never none: a single word longer than it is still
  // the only lead there is, and one that spent the cap exactly is not worth a term
  // the walk would take anyway.
  const lead = [];
  for (let spent = 0; words.length > lead.length;) {
    const next = words[lead.length];
    if (lead.length && spent + next.length > LEAD_CAP) break;
    lead.push(next);
    spent += next.length + 1;
  }
  const rest = words.slice(lead.length);
  const pattern = new RegExp(
    lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
    "g",
  );
  // A unique exact-context occurrence wins. If no context survives, a sole quote
  // occurrence is still identifiable; two are not. Document order is not identity:
  // guessing the first copy after the intended one's neighbours changed quietly moves
  // a comment to words it was never made on. matchAll steps past each lead, so two
  // occurrences overlapping within it are one candidate — which is the lead's own
  // repetition and not the passage's, since the walk still has to confirm the rest.
  const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
  const candidates = [];
  const exact = [];
  for (const at of raw.matchAll(pattern)) {
    const stop = confirmRest(raw, at.index + at[0].length, rest);
    if (stop === -1) continue;
    if (
      within &&
      !(
        containsAcross(within, origin[at.index].node) &&
        containsAcross(within, origin[stop - 1].node)
      )
    )
      continue;
    const hit = { from: at.index, to: stop };
    candidates.push(hit);
    if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false))
      exact.push(hit);
  }
  const found =
    exact.length === 1
      ? exact[0]
      : exact.length === 0 && candidates.length === 1
        ? candidates[0]
        : null;
  // The characters the match covers, cut out of the index the same way a neighbourhood is —
  // walking the segments a second time to rebuild the span would be a second answer to
  // "which text is this", and the two disagree wherever an edge falls inside the match.
  return found ? spanOf(origin, found.from, found.to) : [];
}

// ---------- view continuity ----------
// Following a new version is a navigation, so without help the reader lands at the top
// of a fresh document mid-session, standing nowhere in the walk they were making. Where
// they are rides across in tabStore — per-tab like unsent drafts, because a place in a
// page belongs to a tab and shouldn't outlive it. Two things are recorded, because
// askPosition reads two the runtime can write down: the passage they were reading, and
// the ask the n/p walk had stepped them to. The passage travels as a landmark rather
// than a pixel offset, since content moves between versions: re-find it by its text
// within its section, then the section alone, and only fall back to the raw offset when
// neither survived the revision. The panel's own open state is restored separately
// (PANEL_KEY); because that runs first, the column is already reflowed by the time we
// scroll.
const VIEW_KEY = "lf-view";

// The page's own text blocks the reader can see, in document order, with the rect of each
// one's first line — one reading of what is in front of them, for the two questions that
// ask it: which passage a version change should land them back on (below), and where a
// walk over the page's asks starts when they have pointed at nothing (askPosition).
// A block's landmark is the top of its first line (a range), not its border box; restore
// measures the matched text the same way, so the line box's leading cancels out.
function* blocksOnScreen() {
  for (const block of document.querySelectorAll(TEXT_BLOCK)) {
    // [hidden] needs an explicit skip: hidden="until-found" resolves to
    // content-visibility, under which descendants still report real rects —
    // but what's behind an inactive tab isn't what the reader is reading.
    if (inChrome(block) || block.closest("[hidden]")) continue;
    const range = document.createRange();
    range.selectNodeContents(block);
    const rect = range.getBoundingClientRect();
    if (rect.height && rect.bottom > 42) yield [block, rect]; // 42 = banner height
  }
}
// The quote and the section it's searched in come from the same block, or the search is
// filtered to a section the text isn't in and can only ever fail — restore then falls back
// to the section, which doesn't absorb content added above the reader inside it.
function captureView() {
  const view = { v: VNUM, y: pageScroller.scrollTop };
  // Where the ask walk left off, which is the reader's place stated more exactly than
  // any block can state it — the walk put them there on purpose. It is a variable in a
  // module the navigation is about to throw away, so this is the only way it survives
  // the document being replaced. The ring is not recorded beside it: it is painted from
  // the focus, and a reader arriving at a fresh document is standing on the page.
  view.ask = landed?.id;
  for (const [block, rect] of blocksOnScreen()) {
    const section = block.closest("[id]");
    if (!view.section && section) {
      // The first on-screen block's section, kept only until a quotable block supplies
      // its own: a page with nothing quotable on screen still has somewhere to land.
      view.section = section.id;
      view.sectionTop = shownBox(section).top;
    }
    // Written down the way a comment's quote is, so the search that re-finds it is
    // looking for a string of the same kind.
    const text = cut(quoteFrom(textNodesUnder(block)), 0, LANDMARK_CAP);
    // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
    if (text.length >= 24) {
      // Unconditionally, so a quotable block under no section clears the earlier one
      // rather than sending the search into a subtree its text isn't in.
      view.section = section?.id;
      view.sectionTop = section && shownBox(section).top;
      view.quote = text;
      view.quoteTop = rect.top;
      break;
    }
  }
  return view;
}

// A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
// animating from the top of a fresh document is worse than the jump it replaces. Moving to
// a mark the reader asked for is the other case, and says so.
const jumpBy = (dy, behavior = "instant") =>
  pageScroller.scrollBy({ top: dy, behavior });
function restoreView(view) {
  // Where the walk left off, put back before the scroll below restores the coarser
  // reading of the same fact — and put back whether or not this version answered that
  // ask, since an ask the reader has not stepped off is still the one they would step
  // from. The document's own lookup rather than elementById: the ask list is the
  // document's (openAsks), and a landing inside a shadow tree is one askStep could never
  // measure against. A thread's ask is not here yet — the panel is rebuilt from the log
  // on the first poll, which is behind this — so the record answers for the page's asks
  // and says nothing about the panel's, rather than restoring a second time later over a
  // walk the reader has made since.
  landed = (view.ask && document.getElementById(view.ask)) || null;
  const text = pageText();
  const found = view.quote && resolveAnchor(view, text);
  if (found?.segments) {
    reveal(found.segments[0].node.parentElement); // the passage may sit behind a tab
    jumpBy(rangeOf(found.segments).getBoundingClientRect().top - view.quoteTop);
    return;
  }
  const section = resolveAnchor({ section: view.section }, text)?.element;
  if (section) {
    reveal(section);
    // The shown reading on both sides of the subtraction, because the landmark is
    // whatever id stands nearest the block the reader was on, and a section that
    // generates no box of its own is one a suggestion wrapping whole sections leaves
    // there. Read raw, both sides come back 0 and the correction is 0 — so the restore
    // that had somewhere to land did nothing, silently, and left the reader at the top.
    jumpBy(shownBox(section).top - view.sectionTop);
  } else pageScroller.scrollTo({ top: view.y, behavior: "instant" });
}

// ---------- anchors ----------
// An anchor names a passage: a section id, a quote, or both. Resolving one is the only
// place the page is searched, so the three things that read a passage back — a thread's
// mark, the composer's own, and the reading position a version change rides on — cannot
// disagree about where to look. A quoteless anchor has no text to paint and resolves to
// its element instead.
// The search always reads the whole document — the same text the capture wrote the
// neighbours from — and the section the anchor names filters where a candidate may sit.
// A section the page no longer has filters nothing, so the quote is still looked for
// everywhere, which is all a stale section ever meant.
// Which element an anchor names, asked in one place: the element it resolves to when it
// carries no quote, the subtree a candidate has to sit inside when it does, and the holder
// of the line saying a passage carries a comment are all this question.
const sectionOf = (anchor) => (anchor.section ? elementById(anchor.section) : null);

// ---------- pointing at an item ----------
// One gesture reaches any item: ⌥-click — direct aim, no selection, no chrome, and the
// only route to an item whose words are all inside controls. A plain click reaches the
// visuals, which have no text to select. Two more routes were tried and cut: a rule in
// the margin raised by hovering, too strong for what it offered and placed at the
// item's own left edge, which is the page's margin only for an item the page happens
// to have left-aligned; and a row of chips beside the 💬 offering the selection's
// enclosing chain ("⬚ paragraph", "⬚ section") — a correction nobody had asked for,
// paid in chrome beside every selection a user made.
//
// What both write is the anchor leaf already has. A comment on an element is
// {section: <id>} with no quote — the shape a click on a diagram has made since the
// beginning — so none of this is a new representation, a new event field, or a second
// thing for a version to carry. What is missing is only the gesture, and how the panel
// says which item a thread is on.
//
// An item is an element the author gave an id, outside the runtime's own layer and
// outside the panel (a reply's frozen widget markup carries ids of its own). `version
// check` holds every id across versions, which is exactly why an anchor naming one
// survives a rewrite that takes a quote down with it. An id under the runtime's own
// prefix is not the author's — a module coins one for what it draws (a diagram's svg
// wears `lf-mermaid-N`, numbered by draw order) — so an anchor on it names nothing a
// version holds and something the next load may number differently. The item is the
// element around it, which is the widget.
const ITEM = '[id]:not(.lf-ui):not([id^="lf-"])';
// Whether an element is an item: what the aim walks up to, and what the legend draws a
// box for — one predicate, so the two cannot disagree about what is on the page. Never
// one the user's decision settled off the page: the aim's paint already refused those,
// and a press answered by a different predicate anchored a composer to a retired
// element — a box about nothing, promised by nothing. And never one inside a widget
// that renders as a picture (x-visual): a diagram's nodes carry the ids its renderer
// coined — `root-1`, `actor0`, under no prefix of ours — and an anchor on one names
// nothing a version holds. The entry says the click's anchor is the widget rather than
// a generated part inside it, and the aim is a click; the plain-click path already
// took the outermost visual, and the aim named the node under the pointer.
function isItem(at) {
  if (!at.matches(ITEM) || inChrome(at) || inUi(at) || settledAway(at)) return false;
  const visual = tagsDeclaring((e) => e["x-visual"]).join(",");
  return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}
// The innermost item: a card rather than its column, the column rather than the board —
// the smallest thing under the pointer is the thing pointed at. The walk continues
// upward past what is not one, because the enclosing item is what is on screen.
function itemAt(node) {
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  for (; at; at = at.parentElement) if (isItem(at)) return at;
  return null;
}
// What to call an item, in a word the user reads beside a thread's § label. A widget
// names itself: its tag minus the prefix is already the word the vocabulary chose
// ("card", "option", "column"), so the twelfth widget gets a name here without core
// hearing about it.
//
// The page's own elements have no such word. A tag is markup rather than English, and a
// label reading "§ p · …" over ordinary prose names the thing to a browser and to nobody
// else. So HTML's tags get the nouns a reader would use, and an unlisted one falls back
// to its tag, which is worse than a word and better than nothing.
const HTML_WORDS = {
  p: "paragraph",
  li: "item",
  tr: "row",
  td: "cell",
  th: "cell",
  figure: "figure",
  blockquote: "quote",
  pre: "block",
  section: "section",
  article: "section",
  aside: "aside",
  ul: "list",
  ol: "list",
  dl: "list",
  table: "table",
  details: "note",
  h1: "heading",
  h2: "heading",
  h3: "heading",
  h4: "heading",
  h5: "heading",
  h6: "heading",
};
function itemWord(item) {
  if (!item) return "";
  const tag = item.tagName.toLowerCase();
  // A widget whose kind is not its tag says which it is. Three shapes of change are all
  // <lf-suggestion>, and naming each of them by the tag put a deletion on the asks board
  // under the words it proposed to remove, reading exactly like the insertion above it.
  // Asked only where an entry says there is something to ask, and answered only by an
  // element that has upgraded — before that, and for every widget that declares nothing,
  // the tag is the word.
  if (registry[tag]?.["x-word"] === "module") {
    const own = item.lfWord?.();
    if (own) return own;
  }
  if (tag.startsWith("lf-")) return tag.slice(3);
  // A <pre> is a block of something and the something is in the markup: the documented
  // shape for source is <pre><code class="language-*">, and a <pre> without the <code> is
  // the shape for what isn't source — a transcript, a stack trace, command output. So the
  // word is read rather than assumed, and a user who calls it a code block is offered
  // one.
  if (tag === "pre") return item.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}
// The item's own opening words, read the way anchoring reads everything else — so a label
// a widget declared as the page speaking is in it and the runtime's own chrome (the hidden
// "2 comments" line) is not. Cut back to a word boundary and marked as cut, because a label
// ending mid-word reads as a quote that lost its tail rather than as a name for the thing.
const ITEM_SAYS_CAP = 52;
function itemSays(item) {
  if (!item || inChrome(item)) return "";
  const whole = quoteFrom(textNodesUnder(item));
  if ([...whole].length <= ITEM_SAYS_CAP) return whole;
  const short = cut(whole, 0, ITEM_SAYS_CAP);
  const at = short.lastIndexOf(" ");
  return (at > ITEM_SAYS_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
}
function resolveAnchor(anchor, text) {
  // An element anchor asks a different question — whether the section is still on the
  // user's page — and the whole page is not an answer to it. Existence alone isn't
  // either: a decided element whose markup settles to nothing is present in the
  // document and absent from the screen, and an anchor held to it read as attached
  // while outlining nothing.
  if (!anchor.quote) {
    const section = sectionOf(anchor);
    return section && !settledAway(section) ? { element: section } : null;
  }
  const segments = findQuote(text, anchor.quote, anchor, sectionOf(anchor));
  return segments.length ? { segments } : null;
}

// Every mark the page wears, drawn by one pass, so ownership of an element both a thread
// and the open composer point at is a branch inside a loop rather than an agreement
// between functions ("One writer per thing" in CLAUDE.md, and why).
//
// One range per segment, never one spanning the passage: a single range would paint back
// over everything the search stepped around on the way — a widget's Choose button, a drag
// grip, a diagram's generated stylesheet.
//
// Keyed by thread, not by mark: a passage is several segments and two comments may land on
// the same element, so mark → thread loses one of them — and losing it told the panel the
// passage wasn't in this version while it sat outlined on screen. Every consumer but the
// hit-test asks "where is thread X", and that is now the direction the map runs.
const MARK = "lf-mark";
const PENDING = "lf-pending";
const NOTE = "lf-mark-note";
const marked = new Map(); // thread id -> (Range | Element)[]: the pass's record of what it drew
let pendingMarks = []; // the same record for the open composer's own passage
let pendingOutline = []; // the elements the open draft outlines, owned by nobody else
// What the pointer would take, in whichever arming stands — the ⌥ aim's item, or design
// mode's target: the element, and the control's word where the pointer is on one — and
// null when neither is armed. One answer for the box, the cursor and the name.
function aimTarget() {
  if (aiming) {
    const item = aimedItem();
    return item ? { el: item, part: "" } : null;
  }
  if (designOn && pointer.x >= 0)
    return designTarget(document.elementFromPoint(pointer.x, pointer.y));
  return null;
}
// What a container lets the reader see of what it holds, or null where it shows all of
// it. Overflow is one of three ways to draw nothing past an edge: paint containment and
// content-visibility both clip while overflow computes `visible`, and a box under either
// would be drawn at a rect the reader never sees. The band itself is the padding box less
// whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
// nothing about either, and a box drawn under a border is drawn nowhere as surely as one
// past the edge.
//
// `version check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
export function shownBand(el) {
  const s = getComputedStyle(el);
  if (
    s.overflowX === "visible" &&
    s.overflowY === "visible" &&
    !/paint|strict|content/.test(s.contain) &&
    s.contentVisibility === "visible"
  )
    return null;
  const b = el.getBoundingClientRect();
  const left = b.left + el.clientLeft,
    top = b.top + el.clientTop;
  return {
    left,
    top,
    right: left + el.clientWidth,
    bottom: top + el.clientHeight,
  };
}
// The box an element shows as. An element that generates none of its own — a
// display: contents wrapper — shows as what its contents paint, so its bounds are
// theirs, and a range asks the platform for that union in one read. Its own rect is
// (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
// reads as a real place at the top of the page, so whatever measured it travelled there.
//
// No widget in the vocabulary is one now — lf-suggestion was, and its theme comment
// carries what that cost — but the wrong answer is the platform's rather than that
// widget's: a page or a project layer styles any wrapper this way in a line. This
// lived inside the legend's own reading once, where it stood as a fact about the
// legend rather than about elements, which is exactly why the travel went on asking
// the element directly and centred the top of the document. One answer to "where is
// this element", so there is no second way to ask.
export function shownBox(el) {
  const r = el.getBoundingClientRect();
  if (r.width || r.height) return r;
  const contents = document.createRange();
  contents.selectNodeContents(el);
  return contents.getBoundingClientRect();
}
// The same reading in elements rather than pixels, for the marks the runtime paints on
// the page's own elements: an outline needs a box to hang on, so a mark aimed at a
// boxless element goes to the boxes its contents make. Read from the platform rather
// than from the registry, because generating no box is not a fact about which widget
// this is — any wrapper in any layer can do it, and CSS has no selector that says so.
//
// Area, where shownBox asks only for a box, because the two want different things of
// one: bounds are bounds whichever dimension is flat, while a ring is only worth hanging
// where it can be seen.
//
// The runtime's own chrome leaves by name rather than on that test. Area read as though
// it were doing the job, and it was doing it by luck: a suggestion hangs its controls off
// a span with no width, so the apparatus fell out on its own. The line saying how many
// comments a block holds is clipped to a pixel and has one — so an ask that had been
// commented on wore its ring on the runtime's word about the page rather than on the
// page, and the pixel it hung from moves the first time a comment lands. `inUi` is that
// question already asked, declared labels and all, and it is the one the anchor pass puts
// to a text node — so what a mark hangs on and what a quote may name cannot come apart.
export function shownParts(el) {
  const r = el.getBoundingClientRect();
  if (r.width && r.height) return [el];
  return [...el.children]
    .filter((child) => !inUi(child))
    .flatMap((child) => shownParts(child));
}
// An item's bounds, held to what the page shows of them: the rect a box in the chrome's
// layer is drawn from, for the aim's box and the legend's alike. The layer is one no
// ancestor's clip can reach — that is the point of it — so the box owes the clips an
// answer of its own: an option's table box runs on under its group's overflow: hidden,
// and a card half-scrolled out of a board is half gone. A box drawn from the raw rect
// claims pixels the page has already refused, over the neighbour standing in them.
// body is the page's own scroller, so its edge is one of these too: what is scrolled
// off screen has no rect, and a legend draws boxes for what is on it and nothing for
// the rest.
//
// The walk stops at a box the viewport holds rather than the document: nothing above a
// `position: fixed` element clips it, so the ancestors past that one are answering about a
// flow the element left. Every box in the chrome is behind one — the comment panel is
// fixed, and body is the page's scroller narrowed to the column beside it — so a reply box
// measured through body's band came back wholly clipped away, at any window wide enough for
// the panel to stand beside the page rather than over it. The one caller before this asked
// only about the page's own items, none of which is ever inside a fixed box, which is why
// the walk could be written as "every ancestor" and read as complete.
//
// Which leaves the viewport itself, applied to everything: for a box in the page it is
// what body's own band already said, and for one in a fixed layer it is the whole of what
// clips it.
//
// `clips` caches each ancestor's answer for one pass: the legend asks for every item
// on the page in one breath, and the items share their scrollers, so what a pass spends
// on the walk is two style reads per ancestor rather than two per item per ancestor.
function shownRect(item, clips) {
  return clipped(shownBox(item), item, clips);
}
// Where a member begins, as the reader sees it: the first of the boxes it paints that
// survives the clips, rather than the bounds of all of them. They are the same box for
// anything in flow and different for an inline that wraps, whose bounds run from the
// column's left margin to its right — so a digit placed on that corner sat four hundred
// pixels from the link it addressed, a line above it, on top of somebody else's sentence.
// `shownBox`'s union answers "how much room does this take", which is what a legend box and
// an aim outline want; this answers "where does it start", which is what anything hung on a
// corner wants. The first that survives rather than the first outright, since a link whose
// opening line has scrolled away still has a corner on the line below it.
const startsAt = (item, clips) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clipped(box, item, clips))
    .find(Boolean);
};
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above want the same walk over different boxes.
function clipped(box, item, clips) {
  let left = Math.max(box.left, 0),
    top = Math.max(box.top, 0),
    right = Math.min(box.right, innerWidth),
    bottom = Math.min(box.bottom, innerHeight);
  // From the box itself, not from its parent: an element is not clipped by its own
  // overflow — that clips what it holds — so its band is skipped and only its position is
  // read. Starting at the parent instead asked the question of every ancestor of a fixed
  // box and never of the box, which is the same bug one level up: in design mode the aim
  // resolves the comment panel itself, and the panel measured through body's band came
  // back wholly clipped away, so a mode whose row promises a click on the chrome drew
  // nothing over the chrome.
  for (let a = item; a; a = a.parentElement) {
    let c = clips.get(a);
    if (c === undefined)
      clips.set(
        a,
        (c = {
          band: shownBand(a),
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          fixed: getComputedStyle(a).position === "fixed",
        }),
      );
    if (a !== item && c.band) {
      left = Math.max(left, c.band.left);
      top = Math.max(top, c.band.top);
      right = Math.min(right, c.band.right);
      bottom = Math.min(bottom, c.band.bottom);
    }
    if (c.fixed) break;
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}
// The aim's one writer, and the whole of its paint: the box in the chrome's layer
// (aimBox), the cursor's half of the same promise, and in design mode the name of what
// the box is on. Everything is derived fresh on every ask — the aimed item, lf-over-item,
// the box's geometry — because a latch here was a second answer to the question the
// press asks fresh, and a replay repainted it stale. Synchronous, not coalesced to a
// frame the way refreshHover is: the keydown that arms the page is followed by the press
// in the same gesture, and a promise a frame behind the arm is one the press can outrun.
// What each ask costs is one hit-test and one rect walk, which is what the repaint gate
// this replaced already spent per event on deciding whether to run a far dearer pass.
function refreshAim() {
  const target = aimTarget();
  const aimed = target?.el ?? null;
  // The cursor's half, written where the box's half is decided, so the hand cannot
  // stand over a press the paint knows takes nothing. `aiming` alone says the page
  // is armed; this says the aim has landed on something.
  document.body.classList.toggle("lf-over-item", Boolean(aimed));
  const r = aimed && shownRect(aimed, new Map());
  if (!r) {
    aimBox.style.display = "none";
    aimBox.removeAttribute("data-for");
    paintInspect(null);
    return;
  }
  const { left, top, right, bottom } = r;
  aimBox.setAttribute("data-for", aimed.id);
  // The item's own corner radius, so the ring hugs the corner the item draws.
  Object.assign(aimBox.style, {
    display: "block",
    left: left + "px",
    top: top + pageScroller.scrollTop + "px",
    width: right - left + "px",
    height: bottom - top + "px",
    borderRadius: getComputedStyle(aimed).borderRadius,
  });
  paintInspect(designOn ? target : null, { left, top });
}
// The name of what design mode is aimed at, at the box's top-left corner — above it
// where there is room, inside it where there isn't (the banner sits at the top edge).
// Document-anchored like the box, so a scroll moves the two together between the events
// that re-derive them.
function paintInspect(target, corner) {
  inspectEl.classList.toggle("lf-shown", Boolean(target));
  if (!target) return;
  const name = target.part
    ? `${target.part} · ${designName(target.el)}`
    : designName(target.el);
  if (inspectEl.textContent !== name) inspectEl.textContent = name;
  const above = corner.top - inspectEl.offsetHeight - 2;
  inspectEl.style.left = `${Math.max(2, corner.left)}px`;
  inspectEl.style.top = `${(above >= 0 ? above : corner.top + 2) + pageScroller.scrollTop}px`;
}
const pointer = { x: -1, y: -1 }; // last seen, so a repaint can re-answer the hover
let hovering = null;
let hoverQueued = false;
const marksOf = (id) => marked.get(id) ?? [];
const allMarks = () => [...marked.values()].flat();
// What a reader who cannot see the paint is told. A highlight is glyphs, not an element, so
// it builds no accessibility node — where a <mark> wrapper was a `mark` node, the paint is
// nothing at all, and a passage carrying a comment reads exactly like one that doesn't.
// Neither relation ARIA offers brings it back on something not focusable: NVDA ignores
// aria-describedby there in browse mode and reports none of the labelling attributes on a
// bare p or div at all, VoiceOver reads it only on an interactive, image or landmark role,
// and aria-details is supported unevenly and says only that details exist. What every
// screen reader announces in every mode is text, so the fact is carried as text — one
// hidden, unselectable line inside whatever holds the mark, saying how many comments are
// on it.
//
// Coarser than the mark, and deliberately: it names the block a passage sits in rather than
// the passage, because naming the passage means wrapping it, and wrapping is what a redraw
// between a mousedown and its mouseup turns into a swallowed click. The panel still carries
// each thread's own quote. Written only where the text differs from what is already there,
// because a screen reader rebuilds its buffer on every mutation and this pass runs on every
// poll.
function noteMarks(noted) {
  for (const [holder, threadIds] of noted) {
    const note =
      holder.querySelector(`:scope > .${NOTE}`) ??
      holder.appendChild(offer("button", NOTE));
    note.lfThreads = threadIds;
    note.onclick = () => {
      setPanel(true);
      const id = note.lfThreads.find((threadId) =>
        threadsBox.querySelector(`:scope > .lf-thread[data-id="${threadId}"]`),
      );
      const thread =
        id && threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`);
      if (!thread) return;
      thread.focus({ preventScroll: true });
      thread.scrollIntoView({ behavior: SCROLL, block: "nearest" });
      scrollToThread(id);
    };
    const n = threadIds.length;
    const said = `${n} comment${n === 1 ? "" : "s"}`;
    if (note.textContent !== said) note.textContent = said;
  }
  for (const note of pageQueryAll(`.${NOTE}`))
    if (!noted.has(note.parentElement)) note.remove();
}

function paintAnchors(threads = buildThreads()) {
  if (!anchoringReady) return;
  for (const where of allMarks())
    if (where instanceof Element) where.classList.remove("lf-mark-el");
  for (const el of pendingOutline) el.classList.remove("lf-mark-el", PENDING);
  marked.clear();
  pendingOutline = [];

  const text = pageText(); // read once, for every anchor this pass places
  const posted = [];
  const noted = new Map(); // element -> ordered thread ids marking something inside it
  for (const t of threads) {
    if (t.resolved || !t.root.anchor) continue;
    const found = resolveAnchor(t.root.anchor, text);
    if (!found) continue;
    if (found.element) {
      // The boxes the element shows through, for the same reason the ask ring hangs on
      // those: an outline needs a box, and a wrapper that generates none took its ring
      // to the document's origin and drew nothing there. The record is what the pass
      // clears, what the pointer hit-tests, and what the composer stands off, so all
      // three follow the paint by holding the parts rather than the element.
      const parts = shownParts(found.element);
      for (const part of parts) part.classList.add("lf-mark-el");
      marked.set(t.root.id, parts);
    } else {
      const ranges = found.segments.map((seg) => rangeOf([seg]));
      marked.set(t.root.id, ranges);
      posted.push(...ranges);
    }
    // Where the line goes: every block the passage crosses, so the reader of any of them
    // hears it — or, for a passage that sits in no block of its own, the element the
    // anchor names, which is where the runtime already puts chrome a widget has to live
    // with (a card's drag grip). Never the inline run or the body div in between, because
    // a widget reads those back as its own: lf-draft seeds the editor a user types
    // into from its body div, and a line inside it is chrome in the text they send back.
    const blocks = found.element
      ? [found.element]
      : [...new Set(found.segments.map((seg) => blockAt(seg.node)))].filter(Boolean);
    // Not inside the chrome: the line is the runtime's word inside the page's own
    // blocks, and a design comment on a runtime part is on chrome the panel already
    // reads out — a hidden button in the key line's aria-hidden box would be focusable
    // content nobody is told about.
    for (const holder of blocks.length ? blocks : [sectionOf(t.root.anchor)])
      if (holder && !inChrome(holder))
        noted.set(holder, [...(noted.get(holder) ?? []), t.root.id]);
  }

  // The composer's own passage, in the accent rather than the mark's own ink, so a draft
  // never reads as a posted comment. An element a thread already outlines keeps the posted
  // colour: there is one outline to give, and the thread's is the clickable one.
  //
  // The ⌥ aim does not wear this paint, though it is the same fact one step earlier:
  // a promise has to interrupt where an annotation may whisper, so the aim has a box
  // of its own in the chrome's layer (refreshAim, and the .lf-aim rule's account of
  // why). An open composer doesn't stand the aim down — a press while the box is up
  // re-anchors it to the aimed item (openOnItem) — so the two can show at once, which
  // is the true state: where the draft stands, and where a press would move it.
  const draft =
    composerOpen && pendingAnchor ? resolveAnchor(pendingAnchor, text) : null;
  // Where the draft's passage is, recorded the way the threads' is, because placeComposer
  // has to keep the box off it. An element a thread already outlines belongs
  // in the record too — it is marked, just in the posted colour rather than the accent.
  pendingMarks = draft
    ? draft.element
      ? shownParts(draft.element)
      : draft.segments.map((seg) => rangeOf([seg]))
    : [];
  const pending = [];
  if (draft?.element) {
    // Part by part, because a thread's outline is claimed the same way: the draft takes
    // whichever boxes are still free and leaves the rest in the posted colour. The record
    // above is the parts too, so placeComposer stands the box off the passage the reader
    // can see rather than off a wrapper whose rect sits at the top of the document.
    const taken = allMarks();
    for (const part of pendingMarks)
      if (!taken.includes(part)) {
        part.classList.add("lf-mark-el", PENDING);
        pendingOutline.push(part);
      }
  }
  if (draft?.segments) pending.push(...pendingMarks);

  // The composer's echo of its own passage, decided here because here is where it is known
  // whether the page is showing that passage. Usually it is — the box opens beside the words
  // it just marked, and printing them inside it says the same sentence twice, side by side.
  // So the quote is the fallback rather than the statement: it shows where the mark can't,
  // which is where this version no longer holds the passage — a draft the user carried
  // onto a newer version, whose text survived the trip when its passage didn't. Dashed and
  // muted, the panel's detached treatment, for the same fact.
  //
  // Scrolled out of view looks like that case and is not: the passage is still there, one
  // scroll back, and the reader put it there seconds ago. A quote coming and going with the
  // scroll position would resize the box under the hands typing in it.
  //
  // Out of sight is not gone: a painted mark has no accessibility exposure at all, so the
  // quote stays in the tree as the box's description whichever way it renders. Written only
  // when it changes, because assigning textContent replaces the node even with the same
  // string, and this pass reruns whenever a comment arrives — a stranded quote is the only
  // copy of that passage left, so it is text a user may be selecting to keep.
  const label = composerOpen ? anchorLabel(pendingAnchor, pendingAbout) : "";
  if (composerQuote.textContent !== label) composerQuote.textContent = label;
  // A design comment's label stays: the outline says which element, and only the words
  // say the comment is about the layer and which control the press landed on.
  composerQuote.classList.toggle(
    "lf-unseen",
    !label || (Boolean(draft) && !pendingAbout),
  );

  // A draft outranks a posted mark where they overlap; the hover outranks both, so the
  // passage under the pointer answers the pointer.
  CSS.highlights.set(MARK, new Highlight(...posted));
  CSS.highlights.set(
    PENDING,
    Object.assign(new Highlight(...pending), { priority: 2 }),
  );
  noteMarks(noted); // and the same fact for a reader who can't see any of it
  pageShifted(); // the content moved: the hover, a held aim's promise, the legend ask again

  // The panel's side of the same fact, read off the pass's own record so the two views
  // can't disagree: a passage rewritten in a later version has no home to jump to, and a
  // dead-looking link is worse than one that says so.
  for (const div of openThreads()) {
    const quote = div.querySelector(".lf-quote");
    if (!quote) continue;
    const found = marked.has(div.dataset.id);
    quote.classList.toggle("detached", !found);
    quote.title = found
      ? "Jump to this passage"
      : "This passage can't be identified in the version you're viewing";
  }

  // A message pointing at the page — [the group](#d-channel) — travels by the
  // browser's own fragment navigation, which is already the whole feature within one
  // document: collapsed content wears hidden="until-found", so the jump fires
  // beforematch and the owning tab or settled group opens itself. Opened in a new tab
  // it is an arrival rather than a jump, and landArrival is what answers it there.
  // What the browser has no answer for is the id
  // this version hasn't got. A comment outlives the version it was written on, so
  // that happens without anyone doing anything wrong — and unmarked, the reference
  // reads live, moves nothing on the press, and leaves a fragment nobody holds in the
  // URL for the next load to honor. So it wears the same detached face a quote whose
  // passage left the page wears, asked of the same resolveAnchor, and its press is
  // taken rather than spent. aria-disabled because the title only reaches a pointer.
  for (const a of panel.querySelectorAll(MSG_REF)) {
    const id = fragmentId(a.getAttribute("href"));
    const alive = Boolean(resolveAnchor({ section: id }));
    a.classList.toggle("detached", !alive);
    if (alive) a.removeAttribute("aria-disabled");
    else a.setAttribute("aria-disabled", "true");
    a.title = alive ? `Jump to § ${id}` : `§ ${id} isn't in the version you're viewing`;
  }
}

// A reference a message makes into the page: its own Markdown link, or one a widget
// in its frozen markup writes (a lf-option's `for`). One selector, so what the paint
// above dresses and what the press below refuses are the same set.
const MSG_REF = '.lf-msg-body a[href^="#"]';
// The id a fragment names. An href holds it as the renderer percent-encoded it and
// location.hash as the browser did; the document holds it as written. A malformed
// escape ("#100%") keeps its own characters. One reading for both, because a reference
// the panel paints and a URL the page arrived at name their element the same way.
function fragmentId(fragment) {
  const raw = fragment.slice(1);
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}
// The only press this layer takes from the browser: a reference this version can't
// follow. Everything else — the travel, the reveal, the back button — is the
// platform's, and an exported copy keeps it by having a real href to jump through.
panel.addEventListener("click", (ev) => {
  const a = ev.target.closest(MSG_REF);
  if (a && !resolveAnchor({ section: fragmentId(a.getAttribute("href")) }))
    ev.preventDefault();
});

// Which thread's mark is under a point. A painted range is not an element, so the pointer
// finds it by the boxes the range occupies rather than by hit-testing the DOM — asking for
// the caret position instead would claim the empty space past the end of a short line.
function markAt(x, y) {
  const over = document.elementFromPoint(x, y);
  if (inUi(over)) return null;
  // The retargeted element answers the chrome question, whose subject is which layer the
  // pointer is in; an element mark needs the tree's own answer, because a host contains
  // every mark staged inside it and so tells none of them apart.
  const deep = elementFromPointAcross(x, y);
  for (const [id, marks] of marked)
    for (const where of marks) {
      const hit =
        where instanceof Range
          ? [...where.getClientRects()].some(
              (r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom,
            )
          : containsAcross(where, deep);
      if (hit) return id;
    }
  return null;
}

// Bring an element of the document to the middle — a thread's element anchor, a page
// ask n/p step to. The document scroller's, so an element standing in the
// panel's own list is its region's to centre rather than this one's. reveal first,
// since opening a tab or a settled group moves everything below it. The arithmetic is the range branch's below, because "the middle"
// means the viewport's: scrollIntoView measures against the scroller's own
// scroll-padding-top — declared so a native fragment jump clears the banner — and every
// "center" through it therefore landed 27px low. An element taller than the viewport has
// no middle to show, and centring one puts its opening words above the top edge, so it
// takes that same banner clearance instead and the reader starts at the start.
//
// It glides, because a page the reader is already holding is one the motion keeps their
// place in — the same reason a restore doesn't (jumpBy). An arrival passes "instant" for
// exactly that reason: a document that appeared a moment ago holds no place to keep, so
// the glide would be animating from nowhere.
function scrollToElement(el, behavior = SCROLL) {
  reveal(el);
  el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
  const rect = shownBox(el);
  const clear = parseFloat(getComputedStyle(pageScroller).scrollPaddingTop) || 0;
  jumpBy(rect.top - Math.max((innerHeight - rect.height) / 2, clear), behavior);
}

// Move to where a thread is painted, if it still is — asked of the pass's own record, so the
// panel and the page can't disagree about whether the passage survived. A painted range has
// no element to scroll into view, so its own box does the work.
function scrollToThread(id) {
  const where = marksOf(id)[0];
  if (!where) return;
  if (!(where instanceof Range)) {
    scrollToElement(where);
    return;
  }
  const holder = where.startContainer.parentElement;
  reveal(holder);
  // Sideways first, and only as far as it takes: a passage inside a wide `pre` or a
  // rendered diagram sits in a box with its own horizontal scroll, which the vertical
  // jump below cannot reach — scrolling to it in one axis leaves it off-screen in the other.
  holder.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
  const rect = where.getBoundingClientRect();
  jumpBy(rect.top - (innerHeight - rect.height) / 2, SCROLL);
}

// Pointer feedback a wrapped <mark> got from :hover and cursor: pointer, neither of which
// ::highlight() can carry — it styles glyphs, not boxes. Same hit-test as the click, so
// what lights up is what would open. It is a function of where the pointer is and what the
// page's geometry is, so everything that moves either asks again: the pointer moving, the
// page scrolling under a still pointer, and the pass redrawing the ranges themselves.
const HOVER = "lf-mark-hover";
function paintHover(id) {
  hovering = id;
  document.body.classList.toggle("lf-over-mark", Boolean(id));
  const ranges = marksOf(id).filter((where) => where instanceof Range);
  CSS.highlights.set(HOVER, Object.assign(new Highlight(...ranges), { priority: 1 }));
}
// Coalesced to a frame: scroll outruns layout, the hit-test reads layout, and a repaint
// asks from inside a pass that must stay cheap enough to run from a mousedown.
function refreshHover() {
  if (hoverQueued || (!marked.size && !hovering)) return;
  hoverQueued = true;
  requestAnimationFrame(() => {
    hoverQueued = false;
    const id = markAt(pointer.x, pointer.y);
    if (id !== hovering) paintHover(id);
  });
}
document.addEventListener("mousemove", (ev) => {
  pointer.x = ev.clientX;
  pointer.y = ev.clientY;
  refreshHover();
});
// The page moving under a parked pointer is the pointer moving over the page: what a
// press would take, whether a mark is under the hand, and where every legend box
// stands can all change with no mouse event to say so, and a box left over the old
// item promises a press the click no longer makes. One repaint set for every door
// that says so — a scroll, a window resize, a replay's marks landing (paintAnchors),
// a widget's FLIP settling, and the reflows only the legend's observers hear, the
// panel opening re-centring the column among them.
function pageShifted() {
  refreshHover();
  refreshAim();
  // A board scrolled sideways carries its cards out from under their boxes, and the
  // page scrolled brings items into view that had no box yet (shownRect).
  queueLegend();
}
// At the document and at capture, because scroll does not bubble and body is not the
// page's only scroller: a board scrolls its columns sideways, and a card carried under
// a parked pointer that way is the same fact as the page scrolling under it. Capture is
// the one place every scroller's event passes.
document.addEventListener("scroll", pageShifted, { capture: true, passive: true });

// ---------- selection → comment ----------
// Floating UI stays inside the document's own box, which is body's client box: it
// already ends at the open panel's edge (syncLayout's margin) and inside a classic
// scrollbar's gutter, so a float clamped to it can't hand body a sideways scrollbar
// by overhanging either. The covering sheet is the one strip that box no longer
// states — body keeps its full width under it — so the sheet's own width comes off
// here, and a float raised from the strip beside it can't stand over the thread list.
const rightEdge = () =>
  (panelCovers() ? innerWidth - panel.offsetWidth : pageScroller.clientWidth) - 8;
// The floats live in the document — they scroll with the passage they stand beside —
// while every caller reasons in viewport terms: rects, the pointer, the banner's 48px.
// So the one writer of their position is where the coordinates change space: clamp in
// the viewport, store in the document.
function place(node, left, top) {
  node.style.left = Math.max(8, Math.min(left, rightEdge() - node.offsetWidth)) + "px";
  node.style.top =
    Math.max(48, Math.min(top, innerHeight - node.offsetHeight - 8)) +
    pageScroller.scrollTop +
    "px";
}
// The composer's first choice of a place is the column's margin, beside the passage:
// the document is one centred column, so the margin holds no words by construction,
// and the mark and the box then stand side by side — where the box opened instead at
// the gesture (the fab, the ⌥-click's pointer), it stood on the page's own text next
// to the passage, which is the one thing a 320px card over a 720px column can't avoid
// doing there. placeClear steps it down past any control the page hangs out in that
// same margin (a suggestion's Accept/Reject row).
//
// Where the margin is too narrow for the box — a laptop window, the panel open — it
// has one thing left to stay clear of: its own mark. That mark is the only thing
// naming the passage the box is about, so a box standing on all of it is a box about
// nothing. Not "no overlap" — the box has always covered the tail of a long passage
// and that reads fine — but every rect hidden is the case to move for, and it is a
// case that happens: a restored draft reappears near the top of the viewport, and the
// reading position puts the passage it was made on back in the same place.
// Below the passage where the viewport has room, above it otherwise; place()'s own
// clamp has the last word, so a passage too tall for either side simply keeps the
// better spot.
function placeComposer(left, top) {
  place(composer, left, top);
  const rects = pendingMarks.flatMap((where) =>
    where instanceof Range
      ? [...where.getClientRects()]
      : [where.getBoundingClientRect()],
  );
  const box = composer.getBoundingClientRect();
  const column = document.querySelector("main")?.getBoundingClientRect();
  if (rects.length && column && column.right + 8 + box.width <= rightEdge())
    return placeClear(composer, column.right + 8, Math.min(...rects.map((r) => r.top)));
  // Vertically only: the document never scrolls sideways and body's margin keeps it clear
  // of the panel, so off-screen means scrolled past, and a mark scrolled past is not one
  // this box is standing on.
  const onScreen = (r) => r.bottom > 48 && r.top < innerHeight;
  const behindBox = (r) =>
    r.left >= box.left &&
    r.right <= box.right &&
    r.top >= box.top &&
    r.bottom <= box.bottom;
  // A passage and a thing want different rules here, because
  // they are read differently. Covering the tail of a quote is fine — the user has read
  // it, and the mark still names where it starts. A card, a column, a metric is judged as
  // one object, so a box standing anywhere on it is a box between them and the thing they
  // are writing about. ⌥-click made that plain by opening the composer under the pointer,
  // which is by definition inside what was clicked.
  const whole = pendingMarks.some((where) => where instanceof Element);
  const touching = (r) =>
    r.left < box.right &&
    box.left < r.right &&
    r.top < box.bottom &&
    box.top < r.bottom;
  const clear = whole
    ? !rects.some((r) => onScreen(r) && touching(r))
    : rects.some((r) => onScreen(r) && !behindBox(r));
  if (!rects.length || clear) return;
  const below = Math.max(...rects.map((r) => r.bottom)) + 8;
  const above = Math.min(...rects.map((r) => r.top)) - box.height - 8;
  if (below + box.height <= innerHeight - 8) return place(composer, left, below);
  if (above >= 48) return place(composer, left, above);
  // Neither end has room, which a tall thing reaches easily: a board column is most of the
  // viewport before the box's own height is counted, and place()'s clamp would haul the box
  // back over it — the very thing this is here to stop. So go beside instead, even where
  // the margin is narrower than the box wants; the side is chosen rather than clamped,
  // because the clamp keeps a box on screen by sliding it left, back over the thing it
  // is avoiding.
  const rightOf = Math.max(...rects.map((r) => r.right)) + 8;
  const leftOf = Math.min(...rects.map((r) => r.left)) - box.width - 8;
  place(composer, rightOf + box.width <= rightEdge() ? rightOf : leftOf, top);
}
// The anchor a selection makes: the enclosing section, and the passage as the document
// holds it. Not the selection's own toString(), which is what the reader sees rendered —
// text-transform uppercases an eyebrow or a table header, and the runtime's own chrome
// inside the passage comes along — and a quote the search can't find is no highlight while
// composing and a comment that posts permanently detached. A selection with nothing
// quotable in it yields no quote, which makes it an element anchor on its section: what
// such a selection meant anyway.
//
// The whole of it, however long. A cap here read as an economy and was a claim: the
// stored quote is the passage, so the mark paints it and the comment is on it, and a
// reader who selected a paragraph past the cap got a comment on its opening and a
// highlight that shrank to match — silently, on most of the paragraphs a leaf page
// holds. What the cap was really bounding is the search's pattern, which is where the
// bound now lives (LEAD_CAP), so nothing has to be given up to keep it cheap.
const LANDMARK_CAP = 160;
// How much of a passage's surroundings an anchor writes down. Only the capture decides
// this; the search asks for whatever a given anchor happens to hold.
const CONTEXT = 24;
function selectionAnchor(sel) {
  const range = pageRange(sel);
  const node = range.commonAncestorContainer;
  const holder = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  const section = closestAcross(holder, "[id]:not(.lf-ui)")?.id || null;
  // The neighbours come from the same indexed reading the search uses and stop at
  // the same opaque-widget fences as the file-side capture. The browser knows words
  // a module generated and may quote them; it does not pretend the file can confirm
  // context across their seam.
  const segments = segmentsIn(range);
  const quote = quoteFrom(segments);
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  const prefix = cut(
    neighbourhood(reading.origin, reading.fences, start, CONTEXT, true),
    -CONTEXT,
    Infinity,
  );
  const suffix = cut(
    neighbourhood(reading.origin, reading.fences, stop, CONTEXT, false),
    0,
    CONTEXT,
  );
  // Only what there is. A passage against the document's own edge has no neighbour on
  // that side, and writing that down as an empty string puts a field in the event that
  // never says anything.
  return {
    section,
    quote,
    ...(prefix && { prefix }),
    ...(suffix && { suffix }),
  };
}

// Controls the page is standing on its own account, as against the ones in the runtime's
// layer: a reply's widget is markup frozen in the log, and the layer's own buttons are
// what floating chrome is allowed to sit beside. `data-lf-offer` is what makes a thing
// pressable (`offer`), so this asks after any widget's controls without naming one.
//
// The line saying how many comments a block holds is the one control out here that is
// still the layer's. It wears the marker because a screen reader reaches it by Tab, and
// it is clipped to a pixel where it stands (it only takes a box on focus, fixed under
// the banner) — so a float stepping down past it steps around nothing anyone can see,
// which is exactly the movement this walk exists to prevent.
const pageControls = () =>
  [...document.querySelectorAll(`[data-lf-offer]:not(.${NOTE})`)].filter(
    (c) => !inChrome(c),
  );

// The 💬 button carries the anchor it would open a composer on, so raising it and acting
// on it can't come to different conclusions about what the reader picked. Visibility is
// derived from that anchor and never read back off the stylesheet.
const beside = (rect) => [rect.right + 6, rect.top - 6];
// A float has one more thing to stay clear of, and it is the same kind of thing the
// composer's mark is: a control standing on the page. The floats float and they don't.
// A selection runs to the column's right edge on any line it fills, so `beside` puts
// the button in the margin — which is where a suggestion hangs the row deciding the
// change that selection just covered. The user's own gesture then hid the Accept
// they were reaching for, and the press that would have dismissed the button was the
// press it was covering. The composer's margin placement stands in the same column of
// rows, so it takes the same walk.
//
// Down, and past each in turn, because the margin runs down the page: clearing one row
// can land on the next, and walking a sorted list is the step the rows themselves take to
// nudge apart. place()'s clamp still has the last word, so a float with nowhere left to
// go keeps the best spot rather than leaving the screen.
function placeClear(node, left, top) {
  place(node, left, top);
  const box = node.getBoundingClientRect();
  const sharing = pageControls()
    .map((c) => c.getBoundingClientRect())
    .filter((r) => r.width && r.left < box.right && box.left < r.right)
    .sort((a, b) => a.top - b.top);
  let y = box.top;
  for (const r of sharing) if (r.top < y + box.height && y < r.bottom) y = r.bottom + 6;
  if (y !== box.top) place(node, left, y);
}
let fabAnchor = null;
function showFab(anchor, left, top) {
  fabAnchor = anchor;
  fab.style.display = anchor ? "block" : "none";
  if (anchor) placeClear(fab, left, top);
  paintHere(); // the c row names this anchor, so the line is one more rendering of it
}
// The one way an item under a gesture becomes the composer's anchor, so no two routes
// can come to write different anchors for the same press.
function openOnItem(item, from) {
  showFab(null);
  openComposer({ section: item.id }, "", from.left, from.top);
}
// The button follows the selection. What counts as one is measured on the quote it would
// store, not on the selection's own toString(): those are different strings, and gating on
// the one the reader sees while storing the one the document holds lets a two-character
// quote through behind a rendered three-character selection — a quote short enough to match
// almost anywhere.
const MIN_QUOTE = 3;
// A selection of the page's own words, as against none, a bare caret, or one made inside
// the runtime's own layer. That is the line between a user reaching for a passage and
// one working the chrome, and it is the question every caller here is really asking.
const pageSelection = () => {
  const sel = getSelection();
  return sel && !sel.isCollapsed && !inUi(sel.anchorNode) ? sel : null;
};
// Where a send ends is where typing continues, and the reader has the last word on it.
// A send is a round trip, so this step lands whenever the server answers — long after
// the gesture on a loaded machine — and focusing a box collapses whatever the page had
// selected. A passage picked out while the send was in the wire is a later gesture and
// stands, for the same reason a later edit does. It has less recourse than the edit:
// nothing re-decides the 💬 until the reader gestures again, so the words in front of
// them stop being something to comment on, and no surface says why. Stated once, for
// the three boxes a send can land in, because it is one fact about a send landing.
//
// A box is the whole of it, which is why this is named for typing rather than for
// focus. The panel's other two landings — a resolve and a reopen, each behind a round
// trip of its own — put the reader on a thread node instead, and Chrome collapses the
// selection for a landing that takes a caret, not a control as such — a button and a
// select leave it standing, and so does a `tabindex="-1"` div. Same
// shape, then, and not the same steal: those two keep the standing place a control
// that folds away with its thread owes the reader.
function landTyping(box) {
  if (!pageSelection()) box?.focus({ preventScroll: true });
}
// A drag stops where the hand stopped, not where the reader aimed: a release two glyphs
// short of a word's end meant the word, and the capture would store the fragment as if
// the fragment were the point. So the pointer path grows a selection outward — never
// inward — until each end sits on a boundary of the same word units the runtime already
// reads sequences by (textUnits), and only where the end fell strictly inside a
// word-like unit. An end resting on a boundary, in space, or against punctuation stays
// exactly where the reader put it, and keyboard selections never come here at all:
// shift-arrow is the reader being precise, and precision is not a thing to correct.
//
// One end, because the two are the same question asked at two places, and the words are
// read in the indexed text every other reading of the page uses. That is what keeps a
// snap from claiming what the capture would refuse: a word never continues across a
// fence, and never across a block seam, which is where the collapse writes the space the
// markup doesn't hold. One seam is snapping's own, past what the collapse knows: where
// machine-placed words (data-lf-gen) stand flush against the author's — a chip row is
// written with no space after the title it follows — the two runs read as one word, and
// growing across that seam would hand a selection of the chip the title too.
function snapOut(reading, at, back) {
  const { raw, origin, fences } = reading;
  const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= at) ?? raw.length;
  const spoke = (o) => elementOver(o.node).closest("[data-lf-gen]");
  // An EDGE's neighbours are the nearest characters, not the nearest cells: an empty
  // text node is an empty segment, which puts two EDGEs flush, and every reader of
  // `origin` steps over its nulls.
  const joined = (i) => {
    if (origin[i] !== null) return true;
    let a = i - 1;
    while (origin[a] === null) a--;
    let b = i + 1;
    while (b < origin.length && origin[b] === null) b++;
    const prev = origin[a];
    const next = origin[b];
    if (!prev || !next) return false;
    return blockOf(prev.node) === blockOf(next.node) && spoke(prev) === spoke(next);
  };
  const inRun = (i) => !/\s/.test(raw[i]) && joined(i);
  let lo = at;
  while (lo > behind && inRun(lo - 1)) lo--;
  let hi = at;
  while (hi < ahead && inRun(hi)) hi++;
  let run = "";
  let boundary = 0; // the end's own index within `run`
  const from = []; // from[i] = the raw index run[i] came from; an EDGE holds no character
  for (let i = lo; i < hi; i++) {
    if (origin[i] === null) continue;
    if (i < at) boundary++;
    from.push(i);
    run += raw[i];
  }
  const word = textUnits.segment(run).containing(boundary);
  if (!word || word.index >= boundary || !word.isWordLike) return at;
  return back ? from[word.index] : from[word.index + word.segment.length - 1] + 1;
}
// An end the snap didn't move keeps the boundary the browser gave it: a drag out into
// chrome ends past the last quotable character, and rewriting that end from the reading
// would pull the visible selection off words the reader chose to cover. The gesture's
// direction survives too, or the shift-click that next extends the selection would
// extend it from the wrong end.
function snapSelection() {
  if (!anchoringReady) return;
  const sel = pageSelection();
  if (!sel) return;
  const range = pageRange(sel);
  const segments = segmentsIn(range);
  if (!segments.length) return;
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  const lo = snapOut(reading, start, true);
  const hi = snapOut(reading, stop, false);
  if (lo === start && hi === stop) return;
  const head =
    lo === start
      ? [range.startContainer, range.startOffset]
      : [reading.origin[lo].node, reading.origin[lo].offset];
  const tail =
    hi === stop
      ? [range.endContainer, range.endOffset]
      : [reading.origin[hi - 1].node, reading.origin[hi - 1].offset + 1];
  // Backward means the anchor sits past the range's start — asked of boundary points,
  // because node order misreads containment: a focus on the element holding the anchor's
  // text node both precedes and contains it.
  //
  // Both points have to be in one tree to be compared at all. Inside an x-shadow widget
  // they are not: the selection's own anchorNode is the light-DOM one Chrome clamped to
  // the host, while the range is the composed one this snapped from, and comparing them
  // throws rather than answering. A selection that never left the widget has no direction
  // worth recovering — there is one text node under the pointer either way — so it snaps
  // forward, which is what a drag inside one block does regardless.
  const probe = document.createRange();
  probe.setStart(sel.anchorNode, sel.anchorOffset);
  const comparable =
    sel.anchorNode.getRootNode() === range.commonAncestorContainer.getRootNode();
  const backward =
    comparable && probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
  if (backward) sel.setBaseAndExtent(...tail, ...head);
  else sel.setBaseAndExtent(...head, ...tail);
}
// What the button is on, decided here alone. The selection is read fresh; a visual find —
// a clicked diagram or image, which has no text to select — comes in from the click that
// found it, and a qualifying selection outranks it. The last branch is why order between
// that click and the update queued behind its mouseup never matters: no selection speaks
// for an element anchor, so the selection's absence takes down only a quote, and the
// queued re-decide lands on the same outcome.
function updateFab(visual) {
  if (!anchoringReady) {
    showFab(null);
    return;
  }
  const sel = pageSelection();
  const anchor = sel ? selectionAnchor(sel) : null;
  if (anchor?.quote.length >= MIN_QUOTE)
    showFab(anchor, ...beside(pageRange(sel).getBoundingClientRect()));
  else if (visual) showFab({ section: visual.id }, visual.x + 6, visual.y - 40);
  else if (fabAnchor?.quote) showFab(null);
}
// Where the pointer stopped is not the question; where the selection is, is. The guard
// exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
// can't re-decide the button out from under an open draft. A drag that ends on a widget's
// control is the opposite case: the user was selecting that control's label, and a
// tab's name runs to within a few pixels of the strip button's padding, so the mouseup
// lands on chrome while the selection is the page's. The snap runs in the same queued
// step that raises the button, so the button lands beside the selection as snapped and
// the capture reads the one the reader is looking at — and only for the primary
// button, because a right button's release precedes its context menu, and growing the
// selection there rewrites what Copy was aimed at.
document.addEventListener("mouseup", (ev) => {
  if (inUi(ev.target) && !pageSelection()) return;
  setTimeout(() => {
    if (ev.button === 0) snapSelection();
    updateFab();
  });
});
// Selections made from the keyboard (shift-arrows, ⌘A) deserve the same button. Typing in
// a box never does, whatever is selected elsewhere.
document.addEventListener("keyup", (ev) => {
  if (takesLetters(ev.target)) return;
  if (inUi(ev.target) && !pageSelection()) return;
  setTimeout(updateFab);
});
// Floating chrome getting out of the way of a press somewhere else, which is a fact about
// the press rather than about who receives it: the aim takes a press away from the page
// (see claimPress) and must not take this with it, or the keyboard reference stays up over
// the composer that press just opened. Hence one function, called from both.
// The two side panels are absent from it on purpose. A float answers the press in front
// of it and stands down behind it; the comment panel and the leaves board are
// workspaces the reader stood up, kept through a reload (PANEL_KEY, EDGE_KEY) and so
// through a click all the more — a board any press removes cannot be watched while
// working, which is the board's point. Each closes by its own button, its key, or Esc.
function standDown(target) {
  if (!target.closest?.(".lf-fab, .lf-composer")) {
    showFab(null);
    // Keep a composer that holds unsent text open so a stray click can't drop it;
    // Cancel discards explicitly, and the draft is persisted regardless. Asked only of a
    // composer that is up, so an ordinary press in the page repaints nothing.
    if (composerOpen && !composerInput.value) hideComposer();
  }
  if (helpOpen && !target.closest?.(".lf-help")) showHelp(false);
  // The press on the button itself is its own toggle, so it is not an outside click;
  // without that the open and this close would both run and the menu could never open.
  if (versionMenuOpen && !target.closest?.(".lf-version-menu, .lf-version"))
    showVersionMenu(false);
}
document.addEventListener("mousedown", (ev) => standDown(ev.target));

// What a click on the page means, decided once. A mark under the pointer opens its thread;
// otherwise a diagram or image is a find handed to updateFab, which raises the same 💬
// button on an element anchor — the id the visual lives under — unless a selection
// outranks it.
//
// Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
// each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
// the document out from under the second, which then missed the very mark it had just
// opened and raised the comment button on top of it — leaving an element anchor set, which
// midComposition() reads, so the page quietly stopped following new versions. The rule this
// file already carries covers it: a guard that reads state another function wrote is a sign
// the two are one function.
// What a click anchors on whole, because there is no text in it to select: the page's
// own pictures, and every widget that declares it renders as one.
const visualSel = () =>
  [...tagsDeclaring((e) => e["x-visual"]), "svg", "img", "figure"].join(",");
// While ⌥ is held the page shows what a click would take — the item under
// the pointer wears the aim's box (refreshAim), so the chord
// answers "which" before the click rather than asking the user to press and find out.
// `aiming` is the state and the class is a rendering of it; nothing reads the class back.
//
// It comes off on blur as well as on keyup, because the chord that switches windows takes
// the keyup with it, and a page left armed under nobody's hand is a claim the user
// cannot dismiss.
let aiming = false;
// The aim chord, declared once: the key listeners, the press guard (claimPress) and the
// reference's row all read this object. It is the register's one row that is not a key —
// a modifier held while the pointer clicks — so it binds nothing and carries no press, and
// the rule that keeps it off the key line is the same one that keeps F7 off it. The label
// is spelled from the modifier through the register's own table rather than written out
// twice in two platforms' glyphs.
const AIM = {
  modifier: "Alt",
  keys: [],
  label: `${spell("Alt")} click`,
  does: "Comment on the item under the pointer, whole",
};
// What the pointer is over, asked of the page rather than of an event, so pressing the key
// without moving the mouse answers too — the user holds ⌥ to find out what they would
// get, and the answer cannot wait for them to jiggle the mouse first. An open composer
// is no reason to say nothing: the press still acts (it re-anchors the box), so the
// promise still paints — what stood down here left that one press made blind.
function aimedItem() {
  if (pointer.x < 0) return null;
  const at = document.elementFromPoint(pointer.x, pointer.y);
  return at && !inChrome(at) ? itemAt(at) : null;
}
function setAiming(on) {
  aiming = on;
  document.body.classList.toggle("lf-aiming", on);
  refreshAim();
}
addEventListener("keydown", (ev) => ev.key === AIM.modifier && setAiming(true));
addEventListener("keyup", (ev) => ev.key === AIM.modifier && setAiming(false));
addEventListener("blur", () => setAiming(false));
// The keydown above can go unheard: a page reloaded under a held key — the poll following
// a new version — never hears it, and claimPress reads live modifier state, so every
// press on the new page was claimed while nothing could paint the promise. Mouse events
// carry that same live state, so the move re-derives the arm from the freshest carrier,
// through the one setter, rather than trusting the latch.
document.addEventListener("mousemove", (ev) => {
  const held = ev.getModifierState(AIM.modifier);
  if (held !== aiming) setAiming(held);
  else refreshAim();
});

// ⌥-click means the item under the pointer, whatever it holds. It costs the page no
// chrome and the user no selection, and it reaches an item whose words are all
// inside a control. What it costs is discoverability, which the cursor answers as far as
// a modifier can: while the key is down the pointer says a click will aim.
//
// The press it aims with is the aim's alone, so it is taken at capture — ahead of every
// handler out on the page, and of the browser's own defaults. Read on the way back up
// instead, it was a press the page had already had: ⌥-clicking an option card opened the
// composer *and* picked the option, sending Claude a decision the user never made,
// and ⌥-clicking a tab's name aimed at the widget while switching the panel under it.
// Every widget that takes a press had it, because none of them was ever told. The box
// is the promise, and a press keeps it by being the only thing the press does.
//
// Claimed at the press rather than judged at the click, because the press is where ⌥
// states what the user meant. A key released before the button comes back up would
// otherwise leave a press already taken from the page doing nothing at all.
//
// What is armed is the page rather than the items on it: an armed press aims where there
// is an item under it, and acts on nothing where there isn't. That is what the cursor is
// already saying, over everything the chrome doesn't hold out of it. Falling through to
// the page instead would leave the user reading the box to find out which of the
// two a press is about to be — and a suggestion's ✓ Accept hangs in the page's own
// column, outside the element it decides, so there is nothing above it to aim at and
// getting that wrong sends Claude a decision.
//
// A press is its down, its up and the click they make, a double press one event more, and
// the aim takes every one of them: which a widget listens on is not something the runtime
// can know, and lf-draft already opens its editor on the second mousedown rather than on
// the dblclick, for reasons of its own.
const PRESS_EVENTS = [
  "pointerdown",
  "mousedown",
  "pointerup",
  "mouseup",
  "click",
  "dblclick",
];
// The press the aim has taken — {item} for the ⌥ aim, {design} for design mode — until
// the next one starts.
let aimedPress = null;
function claimPress(ev) {
  // Made and dropped at the same moment, which is the start of a press: a drag already
  // under way when the key goes down keeps the events it is waiting for, and one that
  // ends after the aim's own press can still be ended.
  if (ev.type === "pointerdown") {
    const aim = ev.getModifierState(AIM.modifier) && !inChrome(ev.target);
    const design = !aim && designPress(ev.target) ? designTarget(ev.target) : null;
    aimedPress = aim ? { item: itemAt(ev.target) } : design ? { design } : null;
    if (aimedPress) standDown(ev.target);
  }
  if (!aimedPress) return;
  // A click carrying no press belongs to the control it is on rather than to a press that
  // has already finished: `offer` calls click() to supply the keys a span doesn't come
  // with, and the user's Enter must reach the control they are on whatever the last
  // press was.
  if (ev.type === "click" && !ev.detail) return;
  // Not on pointerdown, whose cancellation takes the mouse events with it — the click this
  // aim ends on included. On mousedown, which is where the selection, the focus and a
  // native drag would start, and on the click, since ⌥ on a link is a download.
  if (ev.type === "mousedown" || ev.type === "click") ev.preventDefault();
  ev.stopPropagation();
  if (ev.type !== "click") return;
  const from = { left: ev.clientX + 6, top: ev.clientY - 40 };
  if (aimedPress.item) openOnItem(aimedPress.item, from);
  else if (aimedPress.design) openOnDesign(aimedPress.design, from);
}
for (const type of PRESS_EVENTS) document.addEventListener(type, claimPress, true);

// ---------- design mode ----------
// The reader commenting on the layer rather than the page: what a widget looks like or
// does, a control, the runtime's own chrome. A mode rather than a chord, because it is
// entered for a batch of remarks and changes what a press means everywhere: a press
// comments on what it lands on and does nothing else, so a card can be pointed at
// without moving it and a pick mark without picking. Prose keeps the browser's
// selection — words are still the way to point at words — and a plain click on prose
// comments on the block it is in. `designOn` is the state; the body class, the banner's
// wash, the toggle's pressed face and the name under the pointer are its renderings,
// written by the one setter, and every comment opened while it stands carries
// `about: "layer"`, which is how the agent tells a remark about the layer from one about
// the page's words.
let designOn = false;
// Kept per tab across a reload, the way the panel's open state is (PANEL_KEY): a version
// landing mid-batch reloads the document, and a reader put out of the mode by news they
// didn't ask for is a mode error the page made for them. Working state of this tab, so
// the tab's store rather than the reader's.
const DESIGN_KEY = "lf-design";
function setDesign(on, { spoken = true } = {}) {
  designOn = on;
  document.body.classList.toggle("lf-design", on);
  banner.classList.toggle("lf-designing", on);
  tabStore.set(DESIGN_KEY, on ? "1" : null);
  // The renderings above are the eye's copy; the mode change is spoken, or it is silent
  // to exactly the reader who can't see them. Restoring after a reload changes nothing
  // the reader did, so it says nothing.
  if (spoken)
    announce(
      on
        ? "Design mode: a click comments on what it lands on — a widget, a control, the chrome. Escape leaves."
        : "Design mode off",
    );
  syncGeneral(); // the general box's hint says which of the two it posts
  refreshAim(); // the box and the name follow the mode, not only the pointer
  paintLegend(); // and so does the legend — with the class, not a frame behind it
  paintHere();
}

// The legend: what is on the page, shown while the mode stands rather than found by
// hovering. One box per item in the chrome's layer (the stylesheet's .lf-legend-box
// says what it looks like and why), and on every item but a widget's parts the
// item's name — the words a design comment on it will carry (designName). The parts
// keep the hairline alone: a board's cards each have an id and each is a target, but a
// tag on every card names nothing a reader can't see and hides what they can.
//
// Painted whole from the page on every ask, like the aim's box, because a legend is a
// reading of the page and a box kept from a previous reading is a claim about a page
// that has since moved. What moves it: a scroll (a board's sideways one included), a
// replay (paintAnchors), a resize, the page's markup changing under it (legendMoves —
// a diagram finishing its draw, a details opening, a card dragged), and a size
// changing with no mutation to say so (legendSizes — an image landing inside an item,
// a font swapping in), body's own among them: the panel opening narrows body and
// re-centres the column, and a column that keeps its width moves every block without
// resizing one, which is why the items' own observations were not enough. Coalesced to
// a frame off those doors; the mode change paints in place, so the class and the
// legend land together.
//
// Reads before writes, in two passes: a box's geometry is a DOM write, and an item's
// rect read after one is a layout forced per item — the thrash a legend of a few
// hundred boxes cannot afford on every scroll frame. So the box set is settled first,
// every rect is read, and only then is anything placed.
const legendBoxes = new Map(); // item → { box, radius, tagW }
const legendSizes = new ResizeObserver(() => pageShifted());
const legendMoves = new MutationObserver((records) => {
  // The legend's own writes are mutations too, inside the chrome; a repaint that heard
  // itself would never stop.
  if (records.some((r) => !inChrome(r.target))) pageShifted();
});
let legendQueued = false;
let legendTagH = 0; // one tag's height, measured once: where a box's top is nearer the banner than this, the tag sits inside
function queueLegend() {
  if (!designOn || legendQueued) return;
  legendQueued = true;
  requestAnimationFrame(() => {
    legendQueued = false;
    paintLegend();
  });
}
function paintLegend() {
  if (!designOn) {
    legendRoot.replaceChildren();
    legendBoxes.clear();
    legendSizes.disconnect();
    legendMoves.disconnect();
    return;
  }
  legendSizes.observe(document.body);
  legendMoves.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  const items = [...document.querySelectorAll(ITEM)].filter(isItem);
  // The set: a box for every item, in document order so a part's box paints over its
  // widget's, and no box for an item the page no longer holds.
  const present = new Set(items);
  for (const [item, { box }] of legendBoxes)
    if (!present.has(item)) {
      box.remove();
      legendBoxes.delete(item);
      legendSizes.unobserve(item);
    }
  // A widget's part is what its entry says it is — a tag declaring x-parent has a
  // holder, and is what the holder is made of — rather than what stands inside a
  // widget: a tab holds a whole page, and every heading and paragraph of that page is
  // the author's, and named.
  const parts = new Set(tagsDeclaring((e) => e["x-parent"]));
  for (const item of items) {
    if (legendBoxes.has(item)) continue;
    const box = el("div", "lf-legend-box");
    box.dataset.for = item.id; // which item, stated where a test can read it (as .lf-aim's)
    if (!parts.has(item.tagName.toLowerCase()))
      box.append(el("span", "lf-legend-tag", designName(item)));
    legendBoxes.set(item, { box });
    legendRoot.append(box);
    legendSizes.observe(item);
  }
  // The reads.
  const clips = new Map();
  const under = banner.getBoundingClientRect().bottom;
  const scrollTop = pageScroller.scrollTop;
  const placed = items.map((item) => {
    const entry = legendBoxes.get(item);
    entry.radius ??= getComputedStyle(item).borderRadius;
    if (!legendTagH && entry.box.firstChild)
      legendTagH = entry.box.firstChild.getBoundingClientRect().height;
    // A tag's width is its text's (nowrap) under a viewport-relative cap (40vw), so
    // it is re-measured while shown rather than cached: a width taken in a narrow
    // window understates the tag after a resize, and a missed step is the garble
    // this pass exists to prevent. A box hidden by an earlier write measures zero,
    // so it keeps its last answer until the pass after it shows again.
    if (entry.box.style.display !== "none")
      entry.tagW = entry.box.firstChild ? entry.box.firstChild.offsetWidth : 0;
    return [entry, shownRect(item, clips)];
  });
  // The writes. Names that would land on one spot step apart: a suggestion and the
  // block it wraps share a top-left corner, and two tags written there garble both —
  // the longer peeking out past the shorter as fragments of a word nobody wrote. The
  // later tag (document order, so the part's over its widget's) steps away from the
  // corner by tag heights until it stands clear.
  const said = []; // tag boxes already placed this pass, in viewport coordinates
  for (const [{ box, radius, tagW }, r] of placed) {
    if (!r) {
      box.style.display = "none";
      continue;
    }
    Object.assign(box.style, {
      display: "block",
      left: r.left - 1 + "px",
      top: r.top - 1 + scrollTop + "px",
      width: r.right - r.left + 2 + "px",
      height: r.bottom - r.top + 2 + "px",
      borderRadius: radius,
    });
    const inward = r.top - legendTagH < under;
    box.classList.toggle("lf-in", inward);
    if (!tagW) continue;
    const left = r.left - 1;
    const step = inward ? legendTagH : -legendTagH;
    let top = inward ? r.top : r.top - legendTagH;
    let moved = 0;
    while (
      said.some(
        (t) =>
          left < t.left + t.width &&
          t.left < left + tagW &&
          top < t.top + legendTagH &&
          t.top < top + legendTagH,
      )
    ) {
      top += step;
      moved += step;
    }
    box.firstChild.style.transform = moved ? `translateY(${moved}px)` : "";
    said.push({ left, top, width: tagW });
  }
}

// What a design press is about: the nearest thing with an id — a page item, the same
// answer the ⌥ aim gives, or inside the chrome the part the runtime named — and the
// control the press landed on where it landed on one, since "the grip" and "the card"
// are different remarks. Nothing where the press is the mode's own machinery: the
// composer being typed into, the 💬 that opens it, the name floating under the pointer.
const DESIGN_OWN = ".lf-composer, .lf-fab, .lf-inspect";
const CONTROLS =
  "[data-lf-offer], button, [role=button], a, select, summary, input, textarea, label";
function designTarget(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || closestAcross(at, DESIGN_OWN)) return null;
  const el = inChrome(at) ? closestAcross(at, "[id]") : itemAt(at);
  if (!el) return null;
  const control = closestAcross(at, CONTROLS);
  const part =
    control && control !== el && containsAcross(el, control)
      ? controlWord(control)
      : "";
  return { el, part };
}
// A control's word for the label: what it says to a screen reader, else what it shows,
// else what it is.
const CONTROL_WORD_CAP = 24;
function controlWord(control) {
  const said =
    control.getAttribute("aria-label") ||
    control.textContent.replace(/\s+/g, " ").trim();
  if (!said) return control.tagName.toLowerCase();
  return [...said].length > CONTROL_WORD_CAP
    ? cut(said, 0, CONTROL_WORD_CAP) + "…"
    : said;
}
// The name a design target wears — under the pointer, in the composer, beside its
// thread. A widget is its tag and id, because both are what a fix is written against; a
// page element takes the reader's word for its kind; a runtime part is its name, the id
// minus the runtime's prefix.
function designName(el) {
  if (inChrome(el)) return el.id.replace(/^lf-/, "").replace(/-/g, " ");
  const tag = el.tagName.toLowerCase();
  return `${tag.startsWith("lf-") ? tag : itemWord(el)} · ${el.id}`;
}
// Which presses the mode takes at the press, ahead of the page: everything but prose. A
// widget, a control, a picture, the chrome — none has words to select and each has
// something a press would otherwise do, and the mode's promise is that it does none of
// it. Prose is left to the browser, so a drag still selects, and the click that ends a
// plain press on it reaches the handler below rather than being taken here.
const PRESSED = () =>
  [...tagsDeclaring(() => true), CONTROLS, "svg", "img", "figure"].join(",");
const designPress = (target) =>
  designOn &&
  Boolean(designTarget(target)) &&
  (inChrome(target) || Boolean(closestAcross(target, PRESSED())));
// The one way a design target becomes the composer's anchor: the element by id, and the
// control's word where the press landed on one.
function openOnDesign({ el, part }, from) {
  showFab(null);
  openComposer({ section: el.id, ...(part && { part }) }, "", from.left, from.top);
}

document.addEventListener("click", (ev) => {
  if (inUi(ev.target)) return;
  // A press design mode did not take at the press is a press on prose: a drag that
  // selected words has the 💬 (updateFab, on the mouseup) and is not a click on the
  // block; a plain click comments on the block it landed in.
  if (designOn) {
    if (pageSelection()) return;
    const target = designTarget(ev.target);
    if (target) openOnDesign(target, { left: ev.clientX + 6, top: ev.clientY - 40 });
    return;
  }
  const threadId = markAt(ev.clientX, ev.clientY);
  if (threadId) return revealThread(threadId);
  if (ev.target.closest?.("a")) return;
  const sel = visualSel();
  let visual = ev.target.closest?.(sel);
  if (!visual) return;
  // Outermost visual: a rendered diagram's inner svg carries a generated id;
  // the anchor belongs to the widget (or figure) that holds it.
  while (visual.parentElement?.closest(sel)) visual = visual.parentElement.closest(sel);
  const id = visual.closest("[id]:not(.lf-ui)")?.id;
  if (!id) return;
  updateFab({ id, x: ev.clientX, y: ev.clientY });
});

// What the open composer's comment is about: "layer" for one opened in design mode, so
// the anchor chosen there — a widget, a control, a runtime part — posts with the word
// that says so. Decided at the open, where the anchor is, and carried with the draft: a
// draft on the banner is about the layer however the mode stands by the time it is sent.
let pendingAbout = null;
// The composer's draft is keyed by the passage it is on. Under one key — which is what it
// was while a draft lived and died in one tab — two tabs composing on different passages
// would each overwrite the other's words, so the key says which passage and the record
// says the rest: the anchor itself (a version that drops the passage still has to say
// what the draft was about), the mode it was written in, and when it was last touched,
// which is what picks the one to reopen at load.
const COMPOSER_KEY = "composer:";
const composerCtx = (anchor) =>
  COMPOSER_KEY +
  JSON.stringify(
    ["section", "quote", "prefix", "suffix", "part"].map((key) => anchor?.[key] ?? ""),
  );
const saveComposerDraft = () =>
  saveDraft(
    composerCtx(pendingAnchor),
    JSON.stringify({
      text: composerInput.value,
      anchor: pendingAnchor,
      suggest: suggestCheck.checked,
      about: pendingAbout,
      touched: Date.now(),
    }),
  );
// An open box the reader emptied keeps its record, which is what tells another tab's
// composer on that passage that this one is merely empty rather than settled — and leaves
// nothing to reopen on. So the draft to come back to is the most recently touched one
// that still holds words.
function pendingComposer() {
  let best = null;
  for (const ctx of draftContexts()) {
    if (!ctx.startsWith(COMPOSER_KEY)) continue;
    let record;
    // Parsed under its own guard: a record that no longer parses costs the reader that
    // one draft, where throwing would cost them the page, at module top level.
    try {
      record = JSON.parse(loadDraft(ctx));
    } catch {
      continue;
    }
    if (record?.text && (!best || record.touched > best.touched)) best = record;
  }
  return best;
}
const syncComposer = wireInput(composerInput, {
  hint: () =>
    suggestCheck.checked
      ? "Replacement text"
      : pendingAbout
        ? "About the layer"
        : "Your comment",
  sends: () => (suggestCheck.checked ? "suggest" : "comment"),
  sendBtn: composerSend,
  save: saveComposerDraft,
  send: async (text, raw) => {
    const anchor = structuredClone(pendingAnchor);
    const ctx = composerCtx(anchor);
    const suggestion = suggestCheck.checked;
    const about = pendingAbout;
    const sent = await sendDraft(
      ctx,
      () => composerCtx(pendingAnchor) === ctx && composerInput.value === raw,
      (attempt) => {
        const event = { kind: "comment", version: VNUM, anchor, text, attempt };
        if (suggestion) event.suggestion = true;
        if (about) event.about = about;
        return post(event);
      },
    );
    if (!sent) return;
    // A later edit is still the reader's standing gesture. The earlier comment may
    // render in the panel, but it may not close or move the composer holding that edit.
    if (loadDraft(ctx) !== null) return;
    revealThread(sent.id);
    // The composer this was sent from is gone with the send; the thread it became
    // carries the same conversation, so its reply box is where typing continues.
    landTyping(threadsBox.querySelector(`.lf-thread[data-id="${sent.id}"] textarea`));
  },
});
// The composer's suggest-mode rendering — the offer of it, the button label and the
// placeholder — derived from the standing state in one place, so the four paths that
// set that state (toggle, open, close, another tab's keystroke) can't each restate
// half of it. The placeholder itself is wireInput's to write; syncComposer repaints it
// from the hint above.
function syncSuggestMode() {
  // A suggestion is replacement text for a passage of the page; a remark about the
  // layer proposes no words, whatever it quotes.
  suggestRow.style.display = pendingAnchor?.quote && !pendingAbout ? "flex" : "none";
  composerSend.textContent = suggestCheck.checked ? "Suggest" : "Comment";
  syncComposer();
  paintHere(); // the line's send row says which of the two the box will do
}
suggestCheck.onchange = () => {
  // Entering suggestion mode seeds the box with the passage to edit in place.
  if (suggestCheck.checked && !composerInput.value.trim() && pendingAnchor?.quote) {
    composerInput.value = seededQuote = pendingAnchor.quote;
    syncComposer();
  }
  syncSuggestMode();
  saveComposerDraft();
};

// Whether the composer is up, and the only thing that decides it. The stylesheet renders
// this state; nothing reads it back, because the rendering has a third value the state
// doesn't — display is "" before the first open, which is neither "block" nor "none", and
// a guard testing for one of them ran on every mousedown in the page and swallowed the
// click. Painting hangs off the same call, so the mark and the box are up together.
let composerOpen = false;
function showComposer(open) {
  composerOpen = open;
  composer.style.display = open ? "block" : "none";
  // The reader's own selection is gone by now — focusing a textarea drops it — so this
  // mark is the only thing left pointing at the passage being quoted.
  paintAnchors();
  paintHere();
}

// The quote suggestion mode auto-seeded, so reopening on a new anchor can tell
// machine seed from user text: the seed belongs to its old anchor and is dropped;
// anything the user typed or edited rides forward — never lose user text.
let seededQuote = "";
// `about` defaults to the mode standing at the open — a composer opened in design mode
// is about the layer — and a restored draft passes the word it was saved with.
function openComposer(
  anchor,
  text,
  left,
  top,
  suggest = false,
  about = designOn ? "layer" : null,
) {
  if (composerInput.value === seededQuote) composerInput.value = "";
  seededQuote = "";
  const ctx = composerCtx(anchor || null);
  // A draft already standing on this passage is what the box opens with — one left hidden
  // here, or one being typed in another tab — unless the caller brought words of its own
  // or the box is already carrying some.
  const held = text || composerInput.value ? null : loadDraft(ctx);
  if (held) ({ text, suggest, about } = JSON.parse(held));
  // The draft moves with the box, and one draft is one record: the passage the words were
  // on lets go of them as they arrive on the next one. A press that re-anchors an open
  // draft is where this lands, and a key left standing there would hand the same words
  // back on the old passage at the next load.
  if (composerCtx(pendingAnchor) !== ctx) clearDraft(composerCtx(pendingAnchor));
  pendingAnchor = anchor || null;
  pendingAbout = about;
  composerInput.value = text || composerInput.value;
  suggestCheck.checked = Boolean(suggest);
  syncSuggestMode();
  // before placing: a hidden box has no height to fit, and the pass inside this call is
  // both what decides whether the quote takes up some of that height and what records
  // where the passage is that the box has to stay off.
  showComposer(true);
  syncComposer();
  placeComposer(left, top);
  composerInput.focus();
  watchComposer();
  // The store hears about the anchor now, not at the next keystroke: saving only on
  // input left a re-anchored draft stored against the anchor the press had just moved
  // it off, and a reload between the press and the next character quietly un-made the
  // move.
  saveComposerDraft();
}
// The box is one view of the draft standing on this passage, and it follows the plain
// boxes' rule with one thing of its own: the composer is chrome as well as a box, so a
// draft settled in another tab — sent, or discarded — leaves it nothing to be open about
// and it goes down. The subscription moves with the anchor, because the key does.
let composerWatch = null;
function watchComposer() {
  composerWatch?.();
  composerWatch = watchDraft(composerCtx(pendingAnchor), (value) => {
    if (value === null) return closeComposer();
    const { text, suggest, about } = JSON.parse(value);
    if (composerInput.value !== text) {
      composerInput.value = text;
      // Whatever stood here is another tab's words now, not this box's machine seed.
      seededQuote = "";
    }
    // The whole record, not the words alone: the mode a draft was written in rides with
    // it (pendingAbout, above), so a box taking up those words sends them under the word
    // they were written with. Design mode is this tab's and the draft's about is not.
    pendingAbout = about;
    suggestCheck.checked = Boolean(suggest);
    syncSuggestMode();
  });
}
// Hiding keeps the draft and closing discards it, but the mark goes down with the box
// either way: a marked passage with no composer on screen points at nothing.
const hideComposer = () => showComposer(false);
function closeComposer() {
  clearDraft(composerCtx(pendingAnchor)); // before the anchor goes: the key is the anchor
  composerWatch?.();
  composerWatch = null;
  composerInput.value = "";
  seededQuote = "";
  suggestCheck.checked = false;
  pendingAnchor = null;
  pendingAbout = null;
  syncSuggestMode(); // after the state it renders, which is now all of it
  hideComposer();
}

// The button opens the composer where it stands, on the anchor it is carrying. Where it
// stands, and not where it was asked for: placement moves it — down past the controls it
// would cover, and off the viewport's edges — so the two are no longer the same point,
// and handing on the asked-for one put the composer straight back over the row the button
// had just stepped off.
fab.onclick = () => {
  if (!fabAnchor) return;
  const anchor = fabAnchor;
  const { left, top } = fab.getBoundingClientRect();
  showFab(null);
  openComposer(anchor, "", left, top);
};
// Cancel discards. Escape and outside clicks only hide, keeping the draft either way.
composerCancel.onclick = closeComposer;

const syncGeneral = wireInput(generalInput, {
  // The box has no anchor to decide it at an open, so what it posts is decided at the
  // send, by the mode standing then — and the hint says which, so the reader typing in
  // design mode knows their remark is about the layer as a whole.
  hint: () => (designOn ? "Comment on the layer" : "Comment on the page"),
  sends: "send",
  sendBtn: generalSend,
  save: (v) => saveDraft("general", v),
  send: async (text, raw) => {
    const event = { kind: "comment", version: VNUM, text };
    if (designOn) event.about = "layer";
    const sent = await sendDraft(
      "general",
      () => generalInput.value === raw,
      (attempt) => post({ ...event, attempt }),
    );
    if (!sent) return;
    revealThread(sent.id);
    landTyping(generalInput); // both send routes end where typing was
  },
});
mirrorDraft(generalInput, syncGeneral, "general");

let approving = false;
function paintApproval() {
  const approved = events.some((e) => e.kind === "done");
  approveBtn.disabled =
    approving ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
    approved;
  approveBtn.textContent = approved ? "✓ Approved" : "✓ Looks good";
}
approveBtn.onclick = async () => {
  if (approving) return;
  approving = true;
  approveBtn.setAttribute("aria-busy", "true");
  paintApproval();
  try {
    await post({ kind: "done", version: VNUM, text: "Looks good" });
  } finally {
    approving = false;
    approveBtn.removeAttribute("aria-busy");
    paintApproval();
  }
};

// ---------- keyboard ----------
// The register's scopes, and the one dispatcher that walks them. What a row and a scope
// are is written where the vocabulary is defined (the key register, above).
//
// The stack is innermost-first: the g chord and the help overlay above everything, then
// whatever element scopes focus stands inside, then the page's own modes and the page. The
// line walks it outward, the dispatcher matches down it, and a row sharing any binding with
// one already named is skipped — so a focused control's keys shadow the page's without
// either knowing about the other, and no press is promised twice. `only` stops both walks
// where a scope owns the keyboard whole: a box words are typed into, and the reference
// overlay. Both walks read the one flag, where two guards in two functions had drifted.
//
// Escape is a binding like any other. It was a ladder of its own — a says/out pair per
// branch of a scene() function, plus a hand-written sentence in the reference that listed
// six of its eight rungs — and as a row the rung is whichever scope in reach binds it
// first, said and run off one object. What that retires is a contract a widget used to
// keep by hand: a control declaring its own Escape had to consume the press, or the
// runtime's ladder ran behind it and closed the panel under a line that promised one
// action. The dispatcher runs the innermost rung and no other, so the promise is
// structural.

// ---------- the g chord: the page's addresses ----------
// g arms a mode in which a letter names one of the page's lists and a digit is a place in
// it: `g c 2` is the second open comment's reply box, `g a 1` the first thing the page is
// waiting on, `g l 3` the third link. Naming a list shows it — the panel opens for the
// comments — and each of its addressable members then wears its digit as a chip, so the
// addresses are on screen wherever the reader is looking. A digit consumes the mode; so
// does Escape, and so does focus entering a box. Any other key disarms and then runs with
// its ordinary meaning, which the dispatcher spells as disarming and walking the stack
// again rather than as a rule of its own — a mistyped g therefore costs the reader nothing
// beyond the press their next key was going to make anyway.
//
// The chord was one list deep once — g then a digit, and the digit meant a reply box —
// which spent the whole of a leader on the one list that had asked for it first. The letter
// is what opens that: a second list costs a letter rather than a second chord, and the line
// says `g` alone rather than a range that only ever counted threads.
//
// Which lists there are is this table and nothing else. The chord's scope, the chips, the
// line's words and the reference are all readings of it, so a fourth list is an entry here
// rather than an edit to four consumers, and nothing that reads the table asks which list
// it is holding. One place names a list at all, and it is not a reader of the table: a
// member with a surface of its own has to say which list that surface belongs to, which is
// the reply box's placeholder (COMMENTS, below). An entry says its letter, the word every surface calls the list by, the sentence
// the reference reads, its members in address order, and how to arrive at one. `spot` is
// where the chip hangs when that is not the member itself — a comment's address belongs on
// the box the digit lands in, not on the thread's far corner.
// What the document holds, in reading order, as against what the chrome holds: the banner,
// the versions and the leaves board have keys of their own, and a comment's message is the
// panel's rather than the page's. The addresses and the scopes that name a platform key
// read the page through here alike, so a part `g` sends the reader to is exactly a part the
// reference says they can stand on.
//
// The whole document and not the parts on screen, which is the tempting reading and the
// wrong one twice over. An address that counted what is in the window is an address that
// means a different link at every scroll position, so a reader who has just learnt that the
// PR is `g l 2` is wrong a moment later; and it would put the key line's own truth on the
// scroll, since a row that goes dead as the page moves is a row the line has to be
// repainted to stop promising — a paint measured at 1.3ms on the gallery, on every scroll
// frame of every page, for one row. Document order costs the pages holding more than nine
// links their tail, which is the bound every list here has.
//
// Above the table rather than beside the other readings below it, because an entry
// holds the function itself and the array literal reads it as the module evaluates.
const pageParts = (sel) =>
  [...document.querySelectorAll(sel)].filter((el) => !inChrome(el));
const pageLinks = () => pageParts("a[href]");
// The summaries rather than the boxes they head: a summary is what the reader stands on,
// what a chip sits beside, and the only part of a disclosure the platform gives a key to —
// so a <details> whose author wrote no summary has nothing here to address. Every
// disclosure and not the shut ones, for the reason above: a list counting what is shut
// means a different section the moment one of them opens.
const pageDisclosures = () => pageParts("details > summary");

// How many members of a list a digit can reach. The bound is the keyboard's — ten digits,
// one of them no ordinal — and not any list's, so it is stated once here rather than in
// each entry.
const ADDRESS_CAP = 9;
// The one entry with a name of its own, because one of its members has a standing
// surface to speak its address on: a reply box's placeholder says "Reply · g c 2" at
// all times, and the panel builds that box (threadNode). Every other list is reached
// through the table.
const COMMENTS = {
  key: "c",
  word: "comments",
  does: "Go to the nth open comment's reply box",
  list: openThreads,
  spot: (thread) => thread.querySelector(":scope > .lf-compose"),
  // What it takes to show this list: the panel holds it and draws nothing while closed, so
  // a letter that named it and left the panel shut painted no chip at all. An entry whose
  // members are on the page states none.
  reveal: () => setPanel(true),
  // stepThread-to-nth and its Enter in one press. The box by its place in the thread and
  // not the first textarea inside it, a message being free to carry a widget with one of
  // its own — a draft's open editor stands before the reply box in the DOM.
  go: (thread) => {
    thread
      .querySelector(":scope > .lf-compose textarea")
      .focus({ preventScroll: true });
    thread.scrollIntoView({ behavior: SCROLL, block: "nearest" });
    scrollToThread(thread.dataset.id);
  },
};
const ADDRESSES = [
  COMMENTS,
  {
    key: "a",
    word: "asks",
    does: "Go to the nth thing this page is waiting on you for",
    // The list n/p walk, addressed rather than stepped: one reading, so the digit and the
    // walk cannot disagree about which ask is the third one. The arrival is handed that
    // whole list and not the nine a digit can spell, so what it announces is the ask's
    // place among everything the page is waiting on.
    list: openAsks,
    go: (ask) => goToAsk(ask, openAsks()),
  },
  {
    key: "l",
    word: "links",
    does: "Go to the nth link",
    list: pageLinks,
    // Focus, not a follow: g says go, and what a focused link then answers is the
    // platform's Enter, which the link scope names on the line. A press that navigated
    // would be a door with no landing to look at first.
    go: (link) => {
      scrollToElement(link);
      link.focus({ preventScroll: true });
    },
  },
  {
    key: "d",
    word: "disclosures",
    does: "Go to the nth disclosure and open it",
    list: pageDisclosures,
    // Opening is the arrival and not a press that follows it. Every arrival here reveals
    // the collapsed containers on its way — this is the one whose target is the container,
    // so the reveal that was travel for the others is the whole motion for this one, and a
    // reader who wanted the section open has it open having asked once. The scroll takes
    // the box rather than the summary, since a section taller than the window starts at its
    // start where a centred summary would put half the screen above it. Standing on the
    // summary afterwards leaves the platform's own press to close it again, which the
    // disclosure scope names on the line.
    go: (summary) => {
      scrollToElement(summary.parentElement);
      summary.focus({ preventScroll: true });
    },
  },
];
// A list's addressable members, and the range its label names. Capped where it is read
// rather than where each list is written, so an entry states what it holds and this states
// what the keyboard can reach.
const addressed = (entry) => entry.list().slice(0, ADDRESS_CAP);
const range = (n) => (n > 1 ? `1–${n}` : "1");
// How an address is spelled, in one place and off the row that binds the key (GOTO): a
// member with a standing surface of its own says the whole motion there — a reply box's
// placeholder reads "Reply · g c 2" — and the armed chip is built the same way. Written
// out at each of them, `g` was a letter three sites had agreed on and none could correct.
const addressLabel = (entry, n) => `${labelOf(GOTO)} ${entry.key} ${n}`;

// Whether the chord is up, and the list a digit addresses once a letter has named one.
// The armed window is a mode the whole keyboard is in, and a digit pressed inside it
// belongs to the chord wherever focus sits. A widget's own digit keys used to have to ask
// this before consuming one; they no longer do, and lf-options no longer imports it — the
// chord's scope claims everything, so the dispatcher never reaches an inner scope while the
// window stands, and the mode enforces itself where it was a rule each widget had to keep.
//
// `aimedList` and not `aimed`, which this file already spends on the aim chord's element
// (refreshAim, aimTarget, aimBox): two concepts under one word, in one file, shadowing each
// other inside the functions that hold both.
let chordArmed = false;
let aimedList = null;
// Arming, aiming and disarming are one call, because they are one window: naming a list
// re-opens it rather than starting a second, and every way down — Escape, a stray key,
// focus entering a box — takes the aim with it.
//
// It stands until one of those, where it stood for a second and a half. A timeout is how a
// keyboard resolves an ambiguous prefix, and there is none here: `g` is a prefix and
// nothing else, any key the chord does not bind disarms it and then runs with its ordinary
// meaning, so nothing is ever swallowed by a window left open. What the clock did instead
// was charge the reader for reading the menu the press had just painted — and a letter
// arriving a moment late is not a no-op but the page's own key, so a slow reader pressing
// `l` got the leaves board rather than the links.
function setChord(on, list = null) {
  // Armed over a control that has claimed Escape, one press would have two owners — the
  // control's rung and the chord's cancel — so the chord refuses to arm there at all.
  if (on && !chordArmed && claimsEsc(focused())) return;
  chordArmed = on;
  aimedList = on ? list : null;
  // A list the reader cannot see is a list wearing no addresses: the panel holds the
  // comments and draws nothing while closed, so naming that list opens it, and the chips
  // land on boxes that have a geometry to be placed from. The open belongs here rather
  // than in the arrival, where it left the letter painting nothing at all.
  if (list?.reveal) list.reveal();
  // The chips are the eye's copy; the window itself is spoken, or the mode change is
  // silent to exactly the reader who can't see them. Off the rows either way, since the
  // rows are what the window answers now — the letters at the first stage, the named
  // list's digits at the second — and a sentence written here for the second would have
  // been the row's own words, restated where nothing could correct them.
  if (on) announce(`Go to — ${saying(GO.rows)}`);
  paintHere();
}

// The chips: one per addressable member, drawn in the chrome's layer (addressBoard) and
// placed from the member's own visible box, so a chip cannot claim room the page has
// already refused — a thread scrolled out of the panel's list, a card half out of a board.
// Painted only once a letter has named a list: before that there is no digit to promise,
// and nine chips over a page nobody has aimed at yet are nine promises the next press
// won't keep.
//
// The layer is the chrome's rather than the page's own markup for the reason every mark is
// (see "Paint; don't wrap"): the addressable things include links set mid-sentence, and a
// span written into a paragraph to carry a number is a span the passage walk then has to
// know about.
//
// Every chip is built detached and the board takes them in one write, which is the rule
// the legend states for this same layer: a chip in the tree is a DOM write, and the next
// member's rect read after one is a layout forced per member — nine of them on every
// scroll frame an armed window stands through.
function paintAddresses() {
  const chips = [];
  if (aimedList) {
    const clips = new Map();
    // The banner stands over the page rather than in it, so shownRect says nothing about
    // it — that reading is what the page's own boxes clip, and the bar clips none of them.
    // The chip is the one thing that has to care, being drawn above the bar: placed on a
    // corner the bar has taken, it is a digit floating over the status line, addressing
    // nothing the reader can see there. So it rides the covered edge, and a member with
    // nothing left below that edge wears no chip at all.
    const covered = banner.getBoundingClientRect().bottom;
    for (const [i, member] of addressed(aimedList).entries()) {
      const r = startsAt(aimedList.spot?.(member) ?? member, clips);
      if (!r || r.bottom <= covered) continue; // nothing to see, nothing to address
      const chip = el("span", "lf-address", String(i + 1));
      if (r.top < covered) chip.classList.add("lf-in");
      chip.style.left = `${r.left}px`;
      chip.style.top = `${Math.max(r.top, covered)}px`;
      chips.push(chip);
    }
  }
  addressBoard.replaceChildren(...chips);
}
// A page that moves under an armed window moves the boxes the chips were placed from, so
// the chips follow it rather than standing where the page used to be. Capture, because the
// panel's list and a board's own overflow scroll in boxes of their own and a scroll event
// does not bubble.
//
// Only while a list is aimed at, which is why this is a listener of its own rather than a
// line in the page's own repaint door (pageShifted): what the line says about the chord
// holds at every scroll position, no list's membership moving with the page, so the door
// that repaints on every scroll of every page would be repainting for nobody. Aimed, the
// paint is the whole of paintHere — the ring and the line are cheap beside the chips, and
// one door is what stops the chips having a repaint set of their own to keep in step.
addEventListener("scroll", () => aimedList && paintHere(), {
  capture: true,
  passive: true,
});
addEventListener("resize", () => aimedList && paintHere());

// ---------- what the page's keys are live over ----------
const hasThreads = () => openThreads().length > 0;
// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own; nor a resolved thread, which has no reply
// box for Enter to reach and no Resolve for r to press.
const focusedThread = () => {
  const active = document.activeElement;
  return active?.classList?.contains("lf-thread") ? active : null;
};
// What c would comment on, read off the anchor the 💬 carries — the same one commentKey
// acts on, so the word and the button on screen cannot name different things. An element
// anchor answers in its own word (a figure, a card), the way the panel names one.
const commentTarget = () =>
  !fabAnchor
    ? "page"
    : fabAnchor.quote
      ? "selection"
      : itemWord(elementById(fabAnchor.section)) || "item";

// Pages are authored documents where typing can start at any moment, so a scope whose keys
// are bare letters stands down wherever a letter is a keystroke. That is the whole of the
// question, and asking a wider one cost the page its keyboard: every `<input>` counted,
// so a reader standing on a screenshot's before/after radio — which consumes no letter the
// platform ever gave it — lost c, d/u, a and the rest, with nothing on screen saying why.
// A select is in, its letters jumping its options; a radio, a checkbox, a slider, a colour
// or file button are out. The platform's set of text-entry types, stated whole: a denylist
// named the two controls to hand and left a slider swallowing the Escape rung the same way
// the version chooser had. A bare or unknown type resolves to "text", so the default lands
// on the typed side.
const TYPED_TYPES = new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);
const takesLetters = (node) =>
  Boolean(node) &&
  (node.tagName === "TEXTAREA" ||
    node.tagName === "SELECT" ||
    node.isContentEditable ||
    (node.tagName === "INPUT" && TYPED_TYPES.has(node.type)));

// Letting go of what the reader is standing on. One act at both ends of the ladder, and
// one line of code, because standing on an ask out on the page and standing on a banner
// button are the same state — the reader holding something — reached from either side of
// the chrome. What the two rungs do not share is the word, and neither word is the other's:
// leaving the chrome names where the reader lands, since that is the whole of what the
// rung is for, and letting go of an ask names the act, since they were on the page all
// along.
//
// Focus rather than blur, because the two differ in what Space does next: `html` is
// `overflow: hidden` here so the document scrolls in `body`, and the browser scrolls
// whichever box it last saw the reader put themselves in. A blur names none —
// activeElement reads as body either way — and Space goes on doing nothing until the next
// click in the page.
//
// Which asks that body be somewhere a reader can be put, and it is not one by default.
// Chrome makes a scroll container focusable so the keyboard can scroll it, and that was
// the whole of what made this call work: on a page long enough to scroll, focus landed on
// body; on a page that fits the window, `body.focus()` moved nothing and the reader stayed
// on the control the line had just promised to take them off — measured both ways on one
// page, by shrinking its content until it fit. So the rung failed exactly where its own
// reason for existing is strongest, a short page having no scroll to hand back and every
// bit as much of a Space that presses whatever the reader was left standing on.
document.body.tabIndex = -1;
const letGo = () => document.body.focus({ preventScroll: true });
// The Escape ladder, one definition for every scope that reaches past the focused control,
// so the thread's, the list's and the page's cannot disagree. It unwinds from where the
// reader is standing, not from what happens to be open.
//
// So the first rung is theirs: out on the page, the innermost thing they are in is the ask
// they are standing on, and a panel behind them is a layer they are not in. Nothing said
// this before — a reader the walk had brought to an ask could press Escape all day and the
// ring stayed on it, the one place in the runtime a key put the reader somewhere with no
// key to take them out again.
//
// Inside the chrome it is the layers first, in the order the reader is in them: the leaves
// board goes before the comment panel — it was opened for a glance, where the panel is the
// work itself — unless focus stands inside the panel, since a reader backing out of its
// general box is standing on its list, and their next Escape taking a board off the far
// side of the screen took the key away from the work it was unwinding.
//
// Then the last rung leaves the chrome, because closing the panel does not put the reader
// back on the page: it lands them on the control that closes it, deliberately (setPanel
// says why), and the closing keypress rings a button a pointer-borne reader never chose.
// Their next Space is then that button rather than the page's scroll. CLAUDE.md's "The
// reader has to be standing somewhere" holds the rest.
function rung() {
  const active = document.activeElement;
  const holding = Boolean(active) && active !== document.body;
  if (holding && !inChrome(active))
    return { says: "let go", does: "Let go of what you are standing on", out: letGo };
  // Whichever board holds the edge, named by the rung so the reader is told what the
  // press will take rather than being told "close the board" over two of them.
  if (edgeUp && !panel.contains(active))
    return {
      says: `close ${edgeUp}`,
      does: `Close the ${edgeUp} board`,
      out: () => showEdge(null),
    };
  if (panelOpen)
    return {
      says: "close comments",
      does: "Close the comment panel",
      out: () => setPanel(false),
    };
  if (holding)
    return { says: "back to the page", does: "Back out onto the page", out: letGo };
  return null;
}
// The page's own Escape, said and run off one object: each rung states the act, the word
// the line paints over it and the sentence the reference lists. A row rather than a rung,
// so the reference names it beside every other key and cannot list a stale half of the
// ladder.
//
// The sentence is the rung's for the reason `c`'s is the anchor's: the reader can see
// which branch they are in, so a word covering all of them tells them nothing. "Back out
// one layer" was true while every rung took a layer of chrome off the page, and stopped
// being true the day the first rung became letting go of an ask, which is no layer at
// all — the line saying "let go" while the reference said "layer" about the same press.
const BACK_OUT = {
  keys: ["Escape"],
  does: () => rung()?.does,
  line: () => rung()?.says,
  when: () => Boolean(rung()),
  run: () => rung().out(),
};

// ---------- what a scope takes ----------
// A scope shadows what stands behind it two ways, and they are one rule: a row of its own
// that names the key, and a claim on keys it has no row for. The second is the platform's
// share — where the reader stands, the browser already answers these and the register has
// nothing to run and nothing to say, so an outer row that named one would be promising a
// press it will not get. Everything not claimed stacks: a scope's rows are reached
// wherever no nearer scope has taken the binding.
//
// This was a blanket (`only: true`), and the blanket is what put a working keyboard out of
// a reader's reach. A text box does claim every key that types a character, so the blanket
// was right about the case it was written for and wrong about the class: the box also took
// the Escape it has no use for, which one branch inside its own row then hand-rescued for
// the controls that type nothing. One key rescued and every other one left swallowed is the
// shape of a menu being extended. Named as a claim instead, the rescue is deleted rather than
// widened: a select's typeahead takes the letters and leaves the page's Escape standing,
// and a radio, which types nothing, claims nothing and keeps the whole keyboard.
const EVERYTHING = () => true;
// A press that puts a character in the box: one character, and Shift is the only modifier
// that still types one — Shift+a is an A, so the page's answer-all must not fire behind it.
// Mod and Alt compose shortcuts a box has no use for, which is how the send key reaches its
// own row.
const PRINTABLE = (binding) => {
  const { key, mods } = parsed(binding);
  return [...key].length === 1 && mods.every((m) => m === "Shift");
};
// What a mode standing over the page takes: the page's keys, and every scope between, minus
// the one key that says what this mode's own keys are. The reference is the exemption for the
// same reason the line draws its chip last whatever the room — a reader who has just opened
// something unfamiliar is exactly the reader who needs it, and a mode that swallowed it would
// leave the line naming a walk and no way to ask about anything else.
//
// A `function`, so the row it reads can be the one the page's own table declares: the modes
// are built beside the controls they belong to, further up than that table, and a claim is
// only ever called at a press. A blanket suits a mode that cannot outlive a keystroke — the
// chord disarms on any key and runs it again, so `?` still reaches the page behind it — and
// the versions menu is the other kind, standing until the reader closes it.
function allButTheReference(binding) {
  return !bindings(REFERENCE).includes(binding);
}

// ---------- the scopes ----------
// Above everything: the chord is armed, or the reference is up. Both claim everything — the
// page stands down under them — and each declares what it keeps, which is how the
// reference's own key goes on working while every other one is suspended.

// The chord: one scope, a row per addressable list, and the window's own way out. The row
// holds the whole motion — its letter names the list, and the digits it then binds are the
// addresses into it. That is `v`'s shape, a chooser whose second key belongs to the scope
// the first one stood up, and the reason it is one row rather than two is that a digits row
// of its own could not name which list it meant.
//
// A row's `when` carries both questions here, where a scope usually carries one of them: a
// list the page hasn't got is a capability, and which list is aimed at is whether the press
// moves now. They can share the answer because a mode is not somewhere the reader stands
// near — see showHelp, which reads a mode's rows by their own liveness for exactly that
// reason. Written as a scope per list instead, each stating its own capability, the two
// were named apart at the price of three scopes under one title, and the reference then
// gathered them in the order it walks the stack — backwards, so it named the lists in the
// opposite order to the line that had just offered them.
const GO = {
  title: "With g armed",
  when: () => ADDRESSES.some((entry) => entry.list().length > 0),
  chord: () => (aimedList ? `${labelOf(GOTO)} ${aimedList.key}` : labelOf(GOTO)),
  at: () => chordArmed,
  claims: EVERYTHING,
  rows: [
    ...ADDRESSES.map((entry) => ({
      keys: () =>
        aimedList === entry
          ? addressed(entry).map((_, i) => String(i + 1))
          : [entry.key],
      // The range the list actually holds, so the label cannot offer an address no member
      // wears; the letter drops off it once it has been pressed, the armed chip having
      // taken it (`g c`).
      label: () =>
        aimedList === entry
          ? range(addressed(entry).length)
          : `${entry.key} ${range(addressed(entry).length)}`,
      does: entry.does,
      line: entry.word,
      when: () => entry.list().length > 0 && (!aimedList || aimedList === entry),
      run: (binding) => {
        if (aimedList !== entry) return setChord(true, entry);
        const member = addressed(entry)[+binding - 1];
        setChord(false); // before the travel, so the arrival's own scrolling paints nothing
        entry.go(member);
      },
    })),
    {
      keys: ["Escape"],
      does: "Cancel the chord",
      line: "cancel",
      run: () => setChord(false),
    },
  ],
};
const HELP = {
  title: "In this reference",
  at: () => helpOpen,
  claims: EVERYTHING,
  rows: [
    { keys: ["?"], does: "Close this reference", line: "close", run: toggleHelp },
    {
      keys: ["Escape"],
      does: "Close this reference",
      line: "close help",
      run: () => showHelp(false),
    },
  ],
};

// Below the element scopes: the page's own modes, then the page. The composer's rung is
// its own scope rather than the box's, because the box may not have focus — the reader
// clicked away and the composer still stands, holding their draft.
const COMPOSER = {
  title: "In the composer",
  at: () => composerOpen,
  rows: [
    {
      keys: ["Escape"],
      does: "Close the composer, keeping the draft",
      line: "close — draft kept",
      run: () => {
        hideComposer();
        showFab(null);
      },
    },
  ],
};
// The box a reply or a comment is typed into, which is the panel's; a page's own control
// is somewhere the reader is standing, not something they are writing in. Declared above
// the scope rather than below it, because a row naming a predicate directly reads the
// binding as the table is built — the deferring wrapper the branch here used to need was
// the only thing hiding that.
const inTheBox = () => panel.contains(document.activeElement);
const focusedThreadOf = () => document.activeElement?.closest?.(".lf-thread");
// A box words are typed into takes the keys that put a character in it, and only those:
// the page's bare letters are keystrokes here, while Escape and Enter are the box's to
// declare or to pass on. What it declares is the way back out — to the thread a reply
// belongs to, so Esc then Enter round-trips, or to the list, so j/k walk on from where the
// backing-out started. Drafts are kept at every rung.
//
// A control the reader is standing on rather than writing in keeps that rung without this
// scope carrying a second branch for it. That branch is what this replaced: the swallow
// took the page's Escape from a select out on the page, so the row reimplemented the
// panels' rung inside its own `when` and `run` and said the other scope's word on the line.
// The keys nothing here reimplemented — c, the walks, the versions, the reference — were
// swallowed and stayed swallowed, which is the whole argument for claiming rather than
// swallowing.
const TYPING = {
  title: "In a text box",
  at: () => takesLetters(focused()),
  claims: PRINTABLE,
  rows: [
    {
      keys: ["Escape"],
      does: "Leave the box, keeping what is typed",
      line: () => (focusedThreadOf() ? "back to thread" : "back to list"),
      when: inTheBox,
      run: () => {
        const thread = focusedThreadOf();
        document.activeElement.blur();
        (thread ?? threadsBox).focus();
      },
    },
  ],
};

// A focused thread: the reply and the resolve are this scope's, not the page's. They said
// "On a focused thread" in their own sentences and were live over the whole page, so a
// reader who had focused nothing was offered a press that no-opped — d/u's bug from the
// other side. The compose row is what tells an open thread from a resolved one, which has
// neither a box for Enter to reach nor a Resolve for r to press.
const THREAD = {
  title: "On a focused thread",
  when: hasThreads,
  at: () => Boolean(focusedThread()),
  rows: [
    {
      keys: ["Enter"],
      does: "Write a reply",
      line: "reply",
      when: () => Boolean(focusedThread()?.querySelector(":scope > .lf-compose")),
      run: () => focusedThread().querySelector("textarea")?.focus(),
    },
    {
      keys: ["r"],
      does: "Resolve it",
      line: "resolve",
      // Through the thread's own button, so keyboard and mouse are one behaviour — the
      // focus landing included — and a resolved thread offers no button to find, which is
      // the row's own liveness rather than a silent no-op inside the press.
      when: () => Boolean(focusedThread()?.querySelector(":scope > .lf-compose")),
      run: () =>
        focusedThread()
          .querySelector(":scope > .lf-thread-actions > .lf-resolve")
          ?.click(),
    },
  ],
};

// The platform's own controls in the page, and the press each already answers. The control
// scope below cannot cover them: it works a span `offer` made pressable, where these arrive
// with their keys already bound, and which keys differ — Enter follows an <a> while Space
// scrolls the page out from under it, and both open a <summary>. So neither row binds a
// `run`, the press being the browser's; nothing here promises more than the browser already
// does, and what a row adds is the promise being on screen. `g` puts the reader on both of
// these by key, and until a scope existed the line went quiet at exactly the moment they
// arrived, with the press that finishes the motion unnamed.
//
// A table and not a scope apiece, for the reason the addresses are one: two scopes differing
// only in a selector and a word are two things to edit the day either the chrome rule or the
// shape of a capability changes, and the third platform control would make it three. The
// page's controls and not every one, which is the reading the addresses take as well: the
// chrome's own links are the leaves board's and its resolved comments are the panel's, and
// both of those declare what they answer themselves. Asked of the document at large, "On a
// link" was had by every page — a machine with one neighbour has a board full of links — so
// the reference named it wherever the reader went, on pages holding none to stand on.
const NATIVE = [
  {
    title: "On a link",
    sel: "a[href]",
    press: ["Enter"],
    does: "Follow it",
    line: "follow",
  },
  {
    title: "On a disclosure",
    sel: "details > summary",
    press: PRESS,
    does: "Open or close it",
    // Read where it is painted rather than named once for both branches, the way a diff's
    // own file rows read theirs: what this press does is whichever way the disclosure is
    // standing, and a word fixed at declaration could only ever say one of them.
    line: () => (focused().parentElement.open ? "close" : "open"),
  },
].map(({ title, sel, press, does, line }) => ({
  title,
  at: () => {
    const el = focused();
    return Boolean(el?.matches?.(sel)) && !inChrome(el);
  },
  when: () => pageParts(sel).length > 0,
  rows: [{ keys: press, does, line }],
}));

// Every press the runtime builds out of a span, in one declaration. `offer` writes
// role="button" onto an element the platform gives no keys, so these two are the UA's
// contract restored — and the survey's largest hole was that nine classes of control
// across core and five widgets answered Space while one of them said so. Outermost of the
// control scopes, so a widget whose press means something more (a grip grabs, a mark
// toggles) names it in its own words and the walk's dedupe keeps this row from saying it
// again.
const CONTROL_SELECTOR = "[data-lf-offer][tabindex]";
const CONTROL = {
  title: "On a control",
  at: () => Boolean(focused()?.matches?.(CONTROL_SELECTOR)),
  // The page has to have built one, or the reference names a place the reader can't
  // stand. The query is the reference's cost and not the line's: `at` is asked first and
  // answers false wherever this could be in doubt, so a paint never reaches it.
  when: () => Boolean(document.querySelector(CONTROL_SELECTOR)),
  rows: [
    {
      keys: PRESS,
      does: "Work the focused control",
      line: "press it",
      // Space would take the page out from under the press, which is why the row consumes
      // it; the dispatcher does that for every row that runs.
      run: () => focused().click(),
    },
  ],
};

// Design mode: a page mode the reader stands in for a batch of remarks about the layer.
// Its Escape is the innermost rung while it stands — a composer opened in it closes
// first (COMPOSER is nearer), then the mode, then the panels — and the press it is made
// of is not a key at all, so that row binds nothing and says nothing on the line, the
// way the ⌥ aim's row does.
const DESIGN = {
  title: "In design mode",
  at: () => designOn,
  rows: [
    {
      keys: [],
      label: "click",
      does: "Comment on what the click lands on — a widget, a control, the chrome; prose still selects",
    },
    {
      // Both keys, on one row: i is the toggle and Escape the mode's own rung, and two
      // chips reading "leave design" said one thing twice on the line.
      keys: ["Escape", "i"],
      does: "Leave design mode",
      line: "leave design",
      run: () => setDesign(false),
    },
  ],
};

// The page itself. Table order is the line's priority order — a total order every row has
// already, rather than a field one can forget — so a row's place here decides what falls
// off the end when the window is narrow, and reordering for readability moves the line.
// v names the chooser, the control wearing the version number, and the menu it opens
// takes the letter again for the newest version — one motion whose second half is a key of
// the scope the first half stood up, so it costs the table no row and holds whether or not
// this page is behind. Named, because the chip that jumps straight to the newest version
// spells that motion in its tooltip.
const CHOOSER = {
  keys: ["v"],
  does: "The versions, and what each one changed",
  line: "versions",
  when: () => versions.length > 0,
  run: () => versionBtn.onclick(),
};
// Named for the same kind of reason: a mode standing over the page suspends the page's keys
// and keeps this one (`allButTheReference`), and the claim reads the binding off the row
// rather than spelling "?" beside it — a fact about a binding written where the binding
// cannot correct it is the register's own oldest bug. Its place in the table is nominal, the
// line drawing this chip last whatever the room (renderLine).
const REFERENCE = {
  keys: ["?"],
  does: "This key reference",
  line: "keys",
  run: toggleHelp,
};
// The way in to the chord, named for the reason the two rows above it are: the armed chip
// and every address a member speaks are built from this row's own key (addressLabel), so
// the letter the reader presses and the letter the page prints cannot be two decisions.
//
// The key alone on the line: what it opens is a table, and a label naming one of its lists
// would be the chord's old shape wearing a letter — `g 1–9` said "threads" without saying
// it, and the day a second list arrived there was no honest range to print. The scope the
// press stands up names them all, one chip each.
const GOTO = {
  keys: ["g"],
  does: "Go by address — the next key names one of the page's lists",
  line: "go to",
  // The scope this press stands up, read rather than restated: a key that armed a window
  // with nothing in it would be the one promise the chord cannot keep.
  when: GO.when,
  run: () => setChord(true),
};
const PAGE = {
  rows: [
    {
      keys: ["c"],
      // One key, three destinations, and the surfaces name the one in front of the reader:
      // a live selection, the item a click raised the 💬 on, or the page itself when
      // nothing is pending. "Comment" covered all three and so promised none of them.
      does: () => `Comment on the ${commentTarget()}`,
      line: () => `comment on the ${commentTarget()}`,
      // A selection made before the anchor pass has run can't be quoted yet, and
      // commenting on the page instead is not what the reader asked for — so the press
      // waits, and the row's own liveness is where that is said rather than a refusal
      // inside run that no surface can see.
      when: () => anchoringReady || !pageSelection(),
      run: commentKey,
    },
    {
      keys: ["j", "k"],
      does: "Next / previous open thread",
      line: "threads",
      when: hasThreads,
      repeat: true,
      run: (binding) => stepThread(binding === "j" ? 1 : -1),
    },
    {
      // A borrowed pair, like the walks either side of it: j/k is vim's list, d/u is
      // less's half page, and n/p is next and previous wherever a keyboard walks a list
      // of things. The walk held `a` alone and then `a`/`p`, and
      // both were the same mistake in different sizes — a letter naming what is walked
      // rather than which way, so the second half had nowhere to come from and ended up
      // a pair only its author knew. Naming the direction is also what leaves the noun's
      // shifted letter to the answer that acts on all of them at once (A, below).
      keys: ["n", "p"],
      does: "Next / previous thing this page is waiting on you for",
      line: "asks",
      when: () => openAsks().length > 0,
      run: (binding) => stepAsk(binding === "n" ? 1 : -1),
    },
    {
      // `a` for the asks — the letter the walk gave up when it moved to naming directions
      // (n/p above), and the noun every surface names this board by. What it opens is the
      // list those keys walk, which until now the reader could only reach by walking it:
      // there was no way to see what was waiting without visiting each one in turn.
      keys: ["a"],
      does: () =>
        `${openEdge("asks") ? "Hide" : "Show"} what this page is waiting on you for`,
      line: () => `${openEdge("asks") ? "hide" : "show"} asks`,
      also: asksBtn, // the banner count opens the same board, which then names this key
      when: asksOffered,
      run: () => {
        showEdge(openEdge("asks") ? null : "asks");
        // Opening lands on the first row, so the board's own keys are the next press
        // rather than a Tab-hunt across the banner — the move `l` makes into the leaves.
        // Closing hands focus back, which showEdge owns.
        if (openEdge("asks")) askRows()[0]?.focus();
      },
    },
    {
      keys: ["d", "u"],
      does: "Half a page down / up",
      line: "half a page",
      repeat: true,
      run: (binding) => stepPage(binding === "d" ? 0.5 : -0.5),
    },
    {
      // `l` for the leaves, the word every surface names this board by. It was `o`,
      // for the "Other leaves" the button said before the count was one off the list
      // it promised — so the key went on spelling a word nothing on screen said, and
      // a mnemonic nobody can reconstruct is a key nobody reaches for twice.
      keys: ["l"],
      does: () => `${openEdge("leaves") ? "Hide" : "Show"} the machine's leaves`,
      line: () => `${openEdge("leaves") ? "hide" : "show"} leaves`,
      also: othersBtn,
      when: boardOffered,
      run: () => {
        showEdge(openEdge("leaves") ? null : "leaves");
        // Opening lands on the first neighbour, so the board's own keys are the next press
        // rather than a Tab-hunt across the banner — the move c makes into the comment
        // panel's box. Closing hands focus back, which showEdge owns. The key is dead
        // with nothing to show, so an open always has a row to land on.
        if (openEdge("leaves")) othersLinks()[0].focus();
      },
    },
    {
      // The same list n/p walk, answered at large: every blanket answer the page offers,
      // given through the banner's own presses, so a decision taken by key is a decision
      // taken by the control and the log records each one separately. Its words are the
      // registry's rather than a sentence written here — "accept" is one widget's verb,
      // and a key that said it in core would be the sentence the banner's count used to
      // be. `a` names the asks it answers and stands for nothing on its own: an
      // unshifted letter that ends the matter for every one of them is a press too
      // cheap for what it does. The walk is spelled in directions (n/p), so the noun was
      // free for the board above, which is what it now opens.
      keys: ["Shift+a"],
      does: () =>
        standingAnswers()
          .map(({ label, n }) => `${label} all ${n}`)
          .join(", ") + " waiting on you",
      line: "answer all",
      when: () => standingAnswers().length > 0,
      run: () => {
        for (const { btn } of standingAnswers()) btn.click();
      },
    },
    {
      // The last thing the reader did to this page, put back. Its own key rather
      // than the platform's ⌘Z, which belongs to the box a reader is typing in and
      // is taken by the browser everywhere else: this is a page-level press like
      // every other letter here, and the typing scope keeps it off a composer's
      // words by claiming its letters. The word is "undo" and never the verb it is
      // about to state — `move` is one widget's word, and a line that said it would
      // be naming a member where the mechanism is what holds.
      keys: ["z"],
      does: "Take back the last change you made here",
      line: "undo",
      // Dead while the page holds a gesture no log read accounts for, this one's
      // own send included: the walk would name the gesture *before* the one they
      // just made and take that back instead. The line drops the chip for as long
      // as that is true rather than promising a press that would undo the wrong thing.
      when: () => !unrecordedGesture() && Boolean(undoable()),
      run: undoLast,
    },
    // Above the page's furniture, because it is the way out of wherever the reader is
    // standing and they are standing somewhere far more often than a panel is open: it
    // ranks with the presses that act on where they are, not with the versions and the
    // modes. Below it, the line drops chips a window at a time, and this is the one that
    // says how to undo the press that put them there.
    BACK_OUT,
    // And the chord below it, having sat among the walks and pushed it off the end of a
    // 1280px line — the reader standing on an ask, which is the one place the way out was
    // written for. What it costs to yield is small and what it buys is not: `g` opens a
    // door to three lists the walks above already reach one at a time, so a narrow window
    // hides a second way to somewhere; the press it was crowding out is the only way back
    // from where a press had just put the reader.
    GOTO,
    CHOOSER,
    {
      // The way in; the mode's own scope takes the letter back out (DESIGN), nearer
      // than this row, so while it stands this one is shadowed off the line.
      keys: ["i"],
      does: "Design mode: comment on the layer — a widget, a control, the chrome — rather than the page",
      line: "design mode",
      run: () => setDesign(true),
    },
    REFERENCE,
    // Reference: a real key the browser owns, and one gesture that is not a key at all.
    // Neither says a word for the line, so neither is ever promised as the next press —
    // one rule where the three exemptions this replaced were three.
    {
      keys: ["F7"],
      does: "Caret browsing (the browser's): select text by keyboard, then c",
    },
    AIM,
  ],
};

// The stack, innermost first, and the whole of what the runtime says about the order. The
// element scopes splice in where ELEMENTS stands — between the two modes that suspend the page
// and the page's own, because a widget's control shadows the page and nothing shadows an armed
// chord or the reference — and every other reading is taken from here: the dispatcher and the
// line walk it as it stands, the reference walks it backwards.
//
// Three lists said this, and the third was the reference's own, in its own order, holding the
// same eight scopes by hand. A mode left out of that one was a mode the reference never named
// — which is not a hypothetical, being the failure it had already made when core's modes were
// not declared the way a widget's are. A list that must be edited in step with another is the
// same bug waiting on the next mode.
const ELEMENTS = Symbol("the scopes of the focused element");
const SCOPES = [
  GO,
  HELP,
  ELEMENTS,
  VERSIONS,
  COMPOSER,
  TYPING,
  THREAD,
  ...NATIVE,
  CONTROL,
  DESIGN,
  PAGE,
];
const CORE = SCOPES.filter((scope) => scope !== ELEMENTS);
// Core's scopes are checked at module load by the rule every widget's are checked by at
// upgrade, so a row here that presses with nothing to say for itself takes down the layer on
// the first page rather than going quiet on every one.
for (const scope of CORE) checked(scope.rows, scope.title ?? "the page's own keys");
// A control the keyboard also reaches names its key, and names it off the row. Three
// tooltips spelled theirs in prose — "(a)", "(o)", "(v v)" — which is the field the key
// line's word used to be, a fact about a binding written somewhere the binding cannot
// correct. `also` is where a row says which control it duplicates; the chip's is the one
// motion no single row makes, so it is composed of the two rows that make it.
for (const scope of CORE)
  for (const row of scope.rows) if (row.also) row.also.title += ` (${labelOf(row)})`;
latestChip.title += ` (${labelOf(CHOOSER)} ${labelOf(NEWEST)})`;

// The two questions a scope answers, named apart because the surfaces ask them apart: the
// reference lists a scope the page *has* and filters its rows by liveness only where the reader
// is standing in it, while the dispatcher and the line want both at once. Spelled `!x || x()`
// in three places before, which is a rule written three times and named nowhere.
const pageHas = (scope) => !scope.when || scope.when();
const readerIn = (scope) => !scope.at || scope.at();
// Where the reader is first, and what the page has second: both are pure and the and is
// the same either way round, but `at` is a class check and a `when` may be the whole event
// log folded — so the walk asks the cheap question of every scope and the dear one only of
// the scopes it is already standing in. That is the rule the dispatcher's row loop already
// keeps and the control scope's own comment already claims ("`at` is asked first and answers
// false wherever this could be in doubt, so a paint never reaches it"), and the scope walk
// was the one place it was not true. The chord is what made it bite: its `when` reaches the
// asks fold and then every link on the page, once per keydown, from the first keystroke of
// the first comment.
const standing = (scope) => readerIn(scope) && pageHas(scope);
// Every scope the reader is standing in, innermost first. The whole list: what a nearer
// scope takes out of reach is the walk's own business, and both walkers say it the same
// way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
// the list here instead was the same statement made where only one of the two shadowings
// could be seen.
function stack() {
  return SCOPES.flatMap((scope) =>
    scope === ELEMENTS ? scopesFor(focused()) : scope,
  ).filter(standing);
}
// The claims of every scope nearer the reader than this one, accumulated as either walk
// steps outward. A scope's own claim is pushed after its rows, because what it takes from
// the page it does not take from itself.
const shadow = () => {
  const claims = [];
  return {
    takes: (binding) => claims.some((c) => c(binding)),
    past: (scope) => {
      if (scope.claims) claims.push(scope.claims);
    },
  };
};
// Every scope the page has, gathered by title, for the reference. Not the stack: the
// reference answers "what could I do here", so it names a card grip's keys whether or not
// a grip has focus. What it does not name is a key that would refuse the press, which is
// the rows' own liveness.
//
// The runtime's own modes come through the same door as a widget's, and the reference was
// blind to them while they did not: the sharpest case was the overlay never saying how to
// close the overlay, and a quiet page naming no Escape at all. So a section is its title
// wherever the title comes from — the box a reply is typed into declares its send key from
// wireInput and its way out from the typing mode, and they are one heading.
//
// The stack backwards, so a reader learning the keyboard starts from the page in front of them
// and reads inward, and the widgets' sections land where their scopes stand in it rather than
// wherever a second list happened to put them.
function declaredStack() {
  const sections = new Map();
  const named = (section) =>
    scopesFor(focused()).some((s) => s.title === section.title);
  for (const scope of SCOPES.toReversed()) {
    if (scope !== ELEMENTS) {
      merge(sections, { ...scope, rows: bySentence(scope.rows) });
      continue;
    }
    // Where the reader is, for a widget's section, is whether the focused element declares it
    // — the one thing core's own scopes state for themselves and an element scope cannot,
    // since it is gathered here by title and the elements wearing that title are many.
    for (const section of declaredScopes.values())
      merge(sections, { ...section, at: () => named(section) });
  }
  // The way out reads last, after what the scope is for. A section gathers its rows from
  // wherever they were declared, and a mode contributing only its Escape would otherwise
  // put the exit above the walk it exits from.
  const exit = (row) => (bindings(row).includes("Escape") ? 1 : 0);
  return [...sections.values()].map((s) => ({
    ...s,
    rows: [...s.rows.values()].sort((a, b) => exit(a) - exit(b)),
  }));
}

// ---------- the dispatcher ----------
// One listener. Scoping is still the DOM's — an element scope holds while focus is inside
// it — but the walk is the stack's rather than the bubble's, so which scope wins is a
// statement here instead of an ordering between nine listeners. `isComposing` is the one
// guard that stays an event's rather than a scope's: an IME's own Escape is not the
// runtime's to take.
document.addEventListener("keydown", (ev) => {
  if (ev.isComposing) return;
  if (run(ev)) return;
  // Any other key disarms the chord and keeps its ordinary meaning, so a mistyped g costs
  // nothing: g j is a thread step and g g re-arms. A letter naming no list disarms the same
  // way, and so does a digit past the end of the list a letter named. Spelled as walking
  // again rather than as a rule, so the meaning a key keeps is the meaning the register
  // gives it.
  if (chordArmed) {
    setChord(false);
    run(ev);
  }
});
function run(ev) {
  const nearer = shadow();
  for (const scope of stack()) {
    for (const row of scope.rows) {
      // The key first, then the claim, then the liveness: a `when` may be the whole event
      // log folded (`a` asks what the page is still waiting on), and asking it of every row
      // the press is not for makes the cost of a keystroke the size of the table rather
      // than the size of the match. A row that matches and is dead still falls through to
      // the scope behind it, which is what `continue` says either way round.
      if (!row.run) continue;
      const binding = bindings(row).find((b) => answers(b, ev));
      if (!binding || nearer.takes(binding) || !live(row)) continue;
      // A held key repeats keydown where a real button fires once, so a row says whether
      // it repeats: a held `]` was a page navigation per repeat and a held pick a `choose`
      // per repeat, where a walk wants the repeat and is the reason the flag exists. The
      // repeat is still consumed — Space is a page scroll if it isn't, so holding it on a
      // control would send the page out from under the press the first one made.
      ev.preventDefault();
      if (ev.repeat && !row.repeat) return true;
      row.run(binding);
      return true;
    }
    nearer.past(scope);
  }
  return false;
}

// A focus move is the one change in where the reader is standing that no state writer
// sees, so it asks for the paint itself — the ring and the line both, which is why one
// call answers for it. Focus entering a box, or a control that claims Escape, also disarms
// the chord — a digit typed in a box is text, and a chip left blooming would promise a
// cancel the control would consume.
document.addEventListener("focusin", () => {
  // The same question `setChord` asks before arming, so it takes the same answer: two
  // readings of where the reader is standing would refuse to arm somewhere they then
  // failed to disarm.
  const active = focused();
  if (chordArmed && (takesLetters(active) || claimsEsc(active))) setChord(false);
  paintHere();
});
document.addEventListener("focusout", () => paintHere());
// A disclosure opening or closing changes what the next press does, and no writer in this
// file reports it: the word on a summary's row is read off `open`, and the reader standing
// there has moved nothing else. Left unpainted, the line said "close" for the three seconds
// until a poll happened past — a key line stale about the press under the reader's finger,
// where every gate reads it as eventually right. The event does not bubble, so this
// captures; and it is the document's rather than each <details>'s, because the disclosures
// on a page are whatever its author wrote and whatever its widgets built, which is not a
// list this file can hold. lf-diff had exactly that listener on each file it renders, which
// is one widget's answer to a question the runtime is the one that asks.
document.addEventListener("toggle", () => paintHere(), true);

// ---------- the key line ----------
// What the next press does, walked outward from where the reader stands and cut where the
// room runs out. The cut is measured rather than counted, for the reason `reserve` measures
// the words a control may say: a stated number of chips is a fact about one font at one
// window size, and it stops being true silently. What the room cannot hold is one press
// away, because `?` is drawn whatever happens — it is what the line truncates *to*.
//
// The rows the line shows, innermost scope first: the ones carrying a word for it. A row
// is skipped where any of its bindings has been named already, so an inner scope's own
// word for a press wins and the generic one behind it stays quiet — the case that names
// this is `g c` aimed over an option's pick mark, where the chord's "1–3 comments" and the
// mark's "1–5 toggle the nth" would otherwise stand side by side, two promises for one
// press.
function lineRows(scopes) {
  const named = new Set();
  const nearer = shadow();
  const rows = [];
  for (const scope of scopes) {
    for (const row of scope.rows) {
      // Shadowing before liveness, for the reason the dispatcher matches the key first:
      // under the reference every page row is claimed away, and asking each one what the
      // page is waiting on to then say nothing about it is the table's cost per paint. A
      // dead row names nothing, so it shadows nothing either.
      if (!row.line) continue;
      const bound = bindings(row);
      if (bound.some((k) => named.has(k) || nearer.takes(k))) continue;
      if (!live(row)) continue;
      for (const k of bound) named.add(k);
      rows.push(row);
    }
    nearer.past(scope);
  }
  return rows;
}
function renderLine() {
  // One walk, read twice: `at` and `when` are the page's own state and a second walk would
  // ask every one of them again for the same frame.
  const scopes = stack();
  const rows = lineRows(scopes);
  // `?` rides last whatever its place in the table, being what the line truncates *to*:
  // whatever the room could not hold is one press away, and the press that reaches it has
  // to survive the cut that hid them.
  const ref = rows.findIndex((row) => bindings(row).includes("?"));
  const ordered =
    ref === -1 ? rows : [...rows.slice(0, ref), ...rows.slice(ref + 1), rows[ref]];
  // Read where it is painted, like every other cell: the chord's chip says which stage the
  // reader is at (`g`, then `g c`), and a string fixed at declaration could only say one.
  const chord = word(scopes.find((s) => s.chord)?.chord);
  keylineEl.textContent = "";
  const chip = (key, said, armed) => {
    const span = el("span", "lf-key");
    const kbd = document.createElement("kbd");
    if (armed) kbd.className = "armed";
    kbd.textContent = key;
    span.append(kbd);
    if (said) span.append(el("span", "", said));
    keylineEl.append(span);
    return span;
  };
  const armed = chord ? chip(chord, "", true) : null;
  const drawn = ordered.map((row) => chip(labelOf(row), word(row.line)));
  // One layout, then positions: the line paints on every focus move, and a page whose board
  // carries thirty grips would force thirty layouts if the fit were measured a chip at a
  // time. Where each chip already sits answers the question, so nothing has to be summed —
  // and summing is what broke it first. `offsetWidth` rounds to whole pixels while the
  // layout is fractional, so adding eight chips up overshot a room they exactly filled and
  // dropped the last of them; a rect is the same number the layout used. `?` is measured
  // in as well, being kept whatever happens, so the cut leaves it room rather than putting
  // it back afterwards to overflow on its own.
  //
  // What goes, goes from the end, which is the outside of the stack: a narrow window costs
  // the reader the page's own keys and keeps the scope they are standing in. The line still
  // carries overflow: hidden underneath this, the backstop for a window too narrow to hold
  // even the chips that are kept — that clip was the whole mechanism before, and a clipped
  // chip reads as a bug where a dropped one reads as a legend.
  const style = getComputedStyle(keylineEl);
  const gap = parseFloat(style.columnGap) || 0;
  const edge = keylineEl.getBoundingClientRect().right - parseFloat(style.paddingRight);
  const rects = drawn.map((span) => span.getBoundingClientRect());
  const pinned = ref === -1 ? 0 : 1; // the ? chip, kept whatever the room
  const held = pinned ? gap + rects.at(-1).width : 0;
  for (let i = 0; i < drawn.length - pinned; i++) {
    if (rects[i].right + held <= edge) continue;
    for (const span of drawn.slice(i, drawn.length - pinned)) span.remove();
    break;
  }
}
paintHere();
// The room is the window's, so the window changing is a scope change like any other. It
// was the one edge no writer reported: a reader who narrowed their window kept the wide
// selection until they next moved focus, and the CSS clip did the cutting instead.
addEventListener("resize", paintHere);

// c goes where commenting happens: a live selection gets the composer (what the floating
// button does), an element click's pending 💬 gets that, and otherwise the general box,
// the panel opening to hold it. Never the panel's collapse: c doubled as the toggle once,
// so with the panel standing open the one key that promised "comment" answered "close",
// and no shortcut reached the box. Backing out is Escape's, which already closes the panel
// rung by rung.
function commentKey() {
  updateFab(); // the selection may be newer than the mouseup that last placed the button
  if (fabAnchor) return fab.onclick();
  setPanel(true);
  generalInput.focus();
}

// j/k walk the open threads: panel focus and the page highlight move as a pair — they are
// two views of the same thread. Clamped at the ends, not wrapped; never empty, because the
// keys are live only while open threads exist, and hasThreads counts what renderThreads
// wrote here in the same synchronous pass.
function stepThread(dir) {
  if (!panelOpen) setPanel(true);
  const threads = openThreads();
  const at = threads.indexOf(document.activeElement?.closest?.(".lf-thread"));
  const next =
    threads[
      at === -1
        ? dir > 0
          ? 0
          : threads.length - 1
        : Math.max(0, Math.min(threads.length - 1, at + dir))
    ];
  next.focus({ preventScroll: true });
  next.scrollIntoView({ behavior: SCROLL, block: "nearest" });
  scrollToThread(next.dataset.id);
}

// d and u step the reader half a page down and up — less's pair, and half a page rather
// than a whole one so the lines they were reading are still on screen to read on from.
// The browser's own keys are left to the browser (Space, Home/End, PageUp/Down all reach
// it untouched, and a test pins that); these are the runtime's.
//
// They move the region the reader's own scrolling moves, which under a covering sheet is
// its thread list rather than the page behind it — the rule syncLayout already states for
// the wheel, and a key is no different. Scrolling a page nobody can see reads to the user
// as the key doing nothing, and then the document is somewhere else when the sheet closes.
//
// The step moves at the pace of the browser's own paging keys. Native paging is a quick
// glide — PageDown covers a page here in ~140ms, and Space and the arrows ride the same
// animator — but that animator is the compositor's and JS cannot ask for it, while
// scrollTo's smooth takes three times as long over the same distance and has no dial,
// which is what read as gradual when the step rode it. So the runtime drives the step
// itself: PAGE_MS of easing out, each write `instant` rather than `auto` since a page is
// free to set `scroll-behavior: smooth` on the box it scrolls (jumpBy says the same) and
// a glide built from smooth writes would never land. A press mid-flight retargets from
// the goal, so two quick presses move exactly a page; the goal is clamped, so pressing on
// at the foot banks no debt for u to press back through; and the step stands down the
// moment the box moves under another hand — a wheel, a centering — because the reader's
// own gesture outranks a key's. Under reduced motion the step is a jump, the answer the
// rest of the runtime's motion already gives (SCROLL).
//
// The page the step halves is the one the reader can see. The document's box lends its
// top edge to the fixed banner, and scroll-padding-top — declared on that scroller, read
// exactly so by scrollToElement — is where the box already says how much of itself stands
// covered; the thread list declares none and subtracts nothing.
const PAGE_MS = 140;
let glide = null; // {box, goal, wrote, raf}
// The glide's claim on the box: it holds only while the box is where the glide last
// wrote it. The tick asks before every write, and a press asks the same question before
// trusting the goal — the reader can take the box between frames, and a press landing
// in that gap otherwise measures from a goal the box has already left.
const holding = (box) =>
  glide?.box === box && Math.abs(box.scrollTop - glide.wrote) <= 1;
function stepPage(fraction) {
  const box = panelCovers() ? threadsBox : pageScroller;
  const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const from = holding(box) ? glide.goal : box.scrollTop;
  const goal = Math.max(
    0,
    Math.min(
      box.scrollHeight - box.clientHeight,
      from + fraction * (box.clientHeight - clear),
    ),
  );
  if (REDUCED) {
    box.scrollTo({ top: goal, behavior: "instant" });
    return;
  }
  cancelAnimationFrame(glide?.raf);
  const start = box.scrollTop;
  const t0 = performance.now();
  const tick = (now) => {
    if (!holding(box)) {
      glide = null; // the box moved under another hand; theirs wins
      return;
    }
    // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
    // the press that scheduled the tick, and an unfloored t walks the ease out past the
    // start — to a write the box clamps, which the next tick then read as another hand.
    const t = Math.max(0, Math.min(1, (now - t0) / PAGE_MS));
    box.scrollTo({
      top: goal - (goal - start) * (1 - t) ** 3,
      behavior: "instant",
    });
    // Where the write left the box, not what it asked for: the box clamps at its ends
    // and snaps to pixels, and the claim the next tick tests is about the box.
    glide.wrote = box.scrollTop;
    if (t < 1) glide.raf = requestAnimationFrame(tick);
    else glide = null;
  };
  glide = { box, goal, wrote: start, raf: requestAnimationFrame(tick) };
}

// ---------- the reference ----------
// Every scope the page has, live rows only, so nothing on screen is a key that does
// nothing. It renders at open and can go stale while it stands, and the two directions
// cost differently, both acceptably: a row going dead under it cannot be pressed, since
// the overlay is `only` and the page stands down beneath it, and a key going live under it
// is merely unlisted until the next open, one press away.
let helpOpen = false;
// Where the reference was opened from, so closing it hands the reader back. Any dialog that
// takes focus owes that; what makes it structural here is that a scope is *where focus is*,
// so the overlay explaining a walk was also the way out of it — open the reference from a
// version row or a held card and the row's keys, which it had just listed, reached nothing
// afterwards. A mode over the page keeps this one key (`allButTheReference`), and a kept key
// that costs the reader their place is not much of an exemption.
let helpFrom = null;
function showHelp(open) {
  if (open && !helpOpen) helpFrom = focused();
  helpOpen = open;
  if (open) {
    helpEl.textContent = "";
    helpEl.append(el("div", "lf-help-title", "Keyboard reference"));
    const table = (rows) => {
      const t = document.createElement("table");
      for (const row of rows) {
        const tr = document.createElement("tr");
        const kbd = document.createElement("kbd");
        kbd.textContent = labelOf(row);
        const keyCell = document.createElement("td");
        keyCell.append(kbd);
        tr.append(keyCell, el("td", "", word(row.does)));
        t.append(tr);
      }
      return t;
    };
    for (const scope of declaredStack()) {
      if (!pageHas(scope)) continue;
      // A scope the reader is standing in is filtered by each row's own liveness, because
      // they can see which state they are in and a row that would refuse the press must
      // not be on screen. A scope they are merely near is listed whole: a row's `when`
      // asks whether the press moves *here*, and here is not where they are, so a grip's
      // "arrows move" belongs in the reference though no card is held and `r` belongs in
      // it though no thread is focused. Filtering both by the same predicate is what took
      // the thread's own keys out of the reference altogether.
      //
      // A mode is the exception, and it is one because there is no standing near it: the
      // reader is in it or it is not there, so its rows answer about here whichever way the
      // reference was opened. The chord is what needs this said — its rows are the lists
      // the page has, and `?` reaches the reference only from a page nobody has armed, so
      // listed whole it would name `l` on a page holding no link at all.
      const inIt = readerIn(scope) || scope.claims === EVERYTHING;
      const rows = scope.rows.filter((row) => row.does && (!inIt || live(row)));
      if (!rows.length) continue;
      if (scope.title) helpEl.append(el("h3", "", scope.title));
      helpEl.append(table(rows));
    }
  }
  helpEl.classList.toggle("open", open);
  if (open) helpEl.focus({ preventScroll: true });
  // Only from inside the overlay: a mousedown somewhere else closes it (standDown), and the
  // press's own focus is the browser's default action, still to come — a restore made from
  // out here would be putting focus back for the click to take again.
  else if (helpEl.contains(focused()) && helpFrom?.isConnected)
    helpFrom.focus({ preventScroll: true });
  paintHere();
}
function toggleHelp() {
  showHelp(!helpOpen);
}

// ---------- the ask, collected ----------
// An ask is a standing request to the reader: a question with no pick on it, a change
// nobody has decided, a piece of work the page says is waiting on them. Which widgets
// can be one is the registry's answer (x-awaits) and nothing out here names a tag —
// the banner's count, the n/p walk, and the "?" overlay's row are three readings of this
// one list, so what the banner counts and what the key steps to cannot disagree. The
// count used to be a query for `lf-suggestion:not([data-lf-state])`, which was
// perfect for suggestions and silently blind to every other thing a page asks.
//
// Both halves of "unanswered" were already written down. Asking is the entry's own
// condition over the element's attributes: a group takes picks only with `choose` and
// stops asking once it is `settled`, a task waits only at `review` or `blocked`. And
// answered is the state x-state already declares — where a verb records itself as an
// attribute the page carries the answer, so a version that honors a pick reads as
// answered with no log at all (the shipped examples arrive that way) and a pick the
// reader cleared reads as open again. Every other verb answers through its own
// surviving fold entry, and the dispatch below is on the attribute kind rather than on
// having a record at all, because the two cases that aren't attributes come to the same
// thing: accept and reject record nothing, honoring retiring the whole wrapper, and a
// draft's edit records into the body, which no attribute read could reach either.
const askEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
// Every declared attribute holding one of the values that ask — a flag's two values
// being its presence and its absence, since it carries none of its own.
function answeredAsk(el, fold) {
  const specs = Object.entries(registry[el.tagName.toLowerCase()]["x-state"] ?? {});
  // The fold holds one entry per unit whatever the verb, so a recordless verb is
  // answered only by an entry that is actually its own — a `choose` surviving in
  // the slot says nothing about `answer`, and a cleared pick must ask again.
  return specs.some(([verb, spec]) =>
    spec.record?.kind === "attribute"
      ? domFacet(el, spec.record) !== ""
      : fold.get(el.id)?.e.action === verb,
  );
}
const askTags = () => tagsDeclaring((entry) => entry["x-awaits"]);
// In document order, because that is the order the page asks them in and the order
// the reader walks — the chrome container sits after the page's blocks, so a thread's
// question queues behind the page's own. Quoted material asks nothing (an exhibited
// decision is a mention). A widget in a thread asks like one on the page: a question
// is a request to the reader wherever it stands, and the panel's count is a different
// fact — threads open, not answers owed.
function openAsks() {
  // Before the first replay, the DOM carries authored initial state while the log may
  // already answer it. This list drives both pixels and actions, so an empty list is the
  // only honest answer until the presentation boundary says replay is complete.
  if (!pagePresented()) return [];
  const tags = askTags();
  if (!tags.length) return [];
  const fold = stateFold(VNUM);
  // A question in a thread is the thread's, so a thread the log has settled asks
  // nothing more — the same reading paintAnchors makes when it takes a resolved
  // thread's mark off the page. Settlement comes from the log and placement from the
  // DOM, and the node keeps its id while it folds out of the open list, so the count
  // drops in the frame the resolve lands, whoever posted it. Without this, a question
  // the agent asked and then withdrew by resolving would stand in the banner's count
  // for the life of the page, and n would step the reader into a shut disclosure.
  const settled = new Set(
    buildThreads()
      .filter((t) => t.resolved)
      .map((t) => t.root.id),
  );
  return [...document.querySelectorAll(tags.join(","))].filter((el) => {
    // settledAway: an ask inside a slot the log retired left the page with it —
    // a group in a rejected suggestion's lf-new counted on, and the walk
    // stepped the reader to a hidden element.
    if (quoted(el) || settledAway(el) || !matchesWhen(el, askEntry(el).when))
      return false;
    const thread = closestAcross(el, ".lf-thread, .lf-going");
    if (thread && settled.has(thread.dataset.id)) return false;
    return !(inChrome(el) ? answeredThreadAsk(el, fold) : answeredAsk(el, fold));
  });
}
// A thread ask has no version to answer it and no restated to retract it, so every
// action on it stands and answered needs no floors. Only a widget with an action
// channel asks in a thread at all — nothing there could ever answer one without —
// and `x-awaits.until` (consulted only here, where no record can close a set) holds
// a matching ask open until the reader has posted the verb it names.
function answeredThreadAsk(el, fold) {
  const entry = registry[el.tagName.toLowerCase()];
  if (!Object.keys(entry["x-state"] ?? {}).length) return true;
  const until = entry["x-awaits"].until;
  if (until && matchesWhen(el, until.when))
    return events.some(
      (e) => e.kind === "action" && e.widget === el.id && e.action === until.verb,
    );
  return answeredAsk(el, fold);
}

// One blanket answer per verb a widget declares one for (x-awaits.all), each deciding
// its asks one at a time so the log records what was consented to rather than one
// blanket yes — accepting the rest after rejecting one stays honest. The widget
// exposes a method named for the verb; the label is built from the same word.
//
// Built when the registry lands rather than written out above, so the second widget to
// declare one gets its control by declaring it. Each takes its place in the row rather
// than a box of its own: a control with no siblings is a control the press sweep walks
// past, and one that only ever appears at upgrade spends the spacer's slack, not the
// room of anything to its right.
const bulkButtons = new Map();
function buildBulkAnswers() {
  for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
    const verb = registry[tag]["x-awaits"].all;
    if (bulkButtons.has(verb)) continue;
    const label = verb[0].toUpperCase() + verb.slice(1);
    const btn = el("button", "lf-btn lf-answer-all", "");
    btn.title = `${label} every one still waiting on you`;
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        for (const ask of openAsks())
          if (askEntry(ask).all === verb) await ask[verb]?.();
      } finally {
        btn.disabled = false;
      }
    };
    showNews(btn, false);
    bulkButtons.set(verb, { btn, label });
    banner.insertBefore(btn, versionBtn);
    // In the row now, so it holds the widest it reaches below a thousand — the same
    // words syncAsks writes, measured in the face it will render in (see reserve).
    reserve(btn, [`✓ ${label} all (999)`]);
  }
}

// Each blanket answer with the asks it would take, from the list above. The banner
// writes its controls from this and the A key reads the same call, so the count on the
// row, the count the "?" reference promises, and the presses the key makes are one
// reading rather than three — and neither surface names a verb, since which verbs there
// are is the registry's answer.
function blanketAnswers(asks) {
  return [...bulkButtons].map(([verb, { btn, label }]) => ({
    btn,
    label,
    n: asks.filter((ask) => askEntry(ask).all === verb).length,
  }));
}
// The ones with something to answer right now. Declared rather than assigned, like
// openAsks above it: the key table is written further up the file, so a const would put
// this in its own dead zone for anything asked of that table before the module ends.
function standingAnswers() {
  return blanketAnswers(openAsks()).filter((a) => a.n);
}

// The banner's reading of that one list. Refreshed from every signal that can change
// it: a widget saying it has just taken an answer (lf-answered, which is also when the
// page's own words change), and every poll, which is where the fold moves and where a
// send that failed has its optimism taken back.
function syncAsks() {
  const asks = openAsks();
  // While the board stands its button stands too, whatever the count just did — the
  // press that opened it has to be able to close it.
  showNews(asksBtn, asksOffered());
  asksBtn.textContent = `Asks (${asks.length})`;
  // Only while the board is up: the count above is what a closed board says, and these
  // rows are what an open one says. A closed board reconciling a list on every poll is
  // work for a reader who cannot see it, and rows in a document nothing can press.
  if (openEdge("asks")) renderAsks(asks);
  for (const { btn, label, n } of blanketAnswers(asks)) {
    showNews(btn, Boolean(n));
    btn.textContent = `✓ ${label} all (${n})`;
  }
  // The n/p and A rows stand on this list, so the surfaces reading them are repainted
  // where it changes — the rule showFab and showEdge already keep for the words
  // they write.
  paintHere();
}
// An answer also changes what text the page has — a retired slot leaves it, a pick
// mark starts saying "your pick" — so the marks are repainted from the same signal,
// and a comment on text the user just removed says so at once rather than at the
// next poll.
document.addEventListener("lf-answered", () => {
  syncAsks();
  paintAnchors();
});
document.addEventListener("lf-actions", syncAsks);
// One row per open ask, reconciled on every signal that moves the list, the way the
// leaves board reconciles its own — rows kept in place rather than rebuilt, so a
// repaint doesn't swap a row out from under a pressed pointer or drop focus inside it.
//
// Keyed by the ask's id and not by the element: a new version replaces every node on the
// page, and the row for a question that survived the republish is the same row. That is
// also what a press resolves through — the element this row stood for may be gone, and
// the ask with that id is the one the reader means.
//
// A row says what kind of thing is asking and then the ask's own opening words, which is
// itemSays — the same reading the comment panel labels an anchor with, so a row and a
// comment on that ask say the same thing. Nothing here asks which widget it is: the kind
// is the element's own word and the words are the element's own text, so the twelfth
// widget gets a row that reads properly on the day it declares x-awaits.
const askRowsById = new Map();
function renderAsks(asks) {
  let anchor = null;
  if (!openEdge("asks")) {
    for (const [, row] of askRowsById) row.remove();
    askRowsById.clear();
    return;
  }
  for (const ask of asks) {
    let row = askRowsById.get(ask.id);
    if (!row) {
      row = el("button", "lf-asks-row");
      row.type = "button";
      // The attribute that already means "this chrome belongs to that ask" (askPlace),
      // so focus landing on a row is the reader standing in the ask it names, and the
      // ring, the walk's own measuring point and the mark all follow with nothing added.
      row.setAttribute(ASK_AT, ask.id);
      row.append(el("span", "lf-asks-kind"), el("span", "lf-asks-says"));
      row.onclick = () => {
        const to = openAsks().find((a) => a.id === ask.id);
        if (to) goToAsk(to, openAsks());
      };
      askRowsById.set(ask.id, row);
    }
    const [kind, says] = row.querySelectorAll(".lf-asks-kind, .lf-asks-says");
    const word = itemWord(ask);
    const said = itemSays(ask) || ask.id;
    // Written only on change: an unchanged poll must not feed the mutation stream a
    // screen reader rebuilds its buffer on.
    if (kind.textContent !== word) kind.textContent = word;
    if (says.textContent !== said) says.textContent = said;
    const account = `${word} · ${said}`;
    if (row.title !== account) row.title = account;
    const place = anchor ? anchor.nextElementSibling : asksPanel.firstElementChild;
    if (place !== row) asksPanel.insertBefore(row, place);
    anchor = row;
  }
  const live = new Set(asks.map((a) => a.id));
  for (const [id, row] of askRowsById)
    if (!live.has(id)) {
      // An answered ask takes its row with it, and may take the focus with it too — a
      // reader who answered from somewhere else while standing on this row. Hand focus
      // to whatever now stands in its place rather than letting it fall to the body,
      // which is nowhere and takes the ring with it.
      const held = row.contains(document.activeElement);
      const next = row.nextElementSibling ?? row.previousElementSibling;
      row.remove();
      askRowsById.delete(id);
      if (held) (next ?? asksBtn).focus();
    }
}

// The walk over what the page is waiting on the reader for. It wraps at both ends,
// because asks are a worklist rather than a document to read through: answering one takes
// it out of the list, so forward is the direction that has somewhere to go, and a walk
// that clamped there would strand them at the end of it.
//
// A press this control belongs to: one inside the ask, or one hoisted out of it and
// pointing back (a suggestion's row is the column's child, so that it can hang in the
// page margin). Landing on it rather than on the ask puts the reader on the press that
// answers it, and Tab walks the rest of that ask's own controls from there.
const ASK_CONTROL = "[data-lf-offer][tabindex]";
// Which ask such a control decides, where the widget hoisted it out of the element (the
// attribute lf-suggestion writes on the row it hangs in the margin).
const ASK_ROW = "data-lf-for";
// Chrome that stands *at* an ask without deciding it: the asks board's rows. Separate
// from ASK_ROW above, because the two say different things about the same element and
// one of them has a consumer that must not confuse them — stepAsk looks through ASK_ROW
// for the control to put the reader on, and a row that merely points at the ask is not
// that control. What they share is this: focus on either means the reader is standing at
// that ask, which is the one question askPlace asks.
const ASK_AT = "data-lf-at";
// The tab stop this walk lends an ask that holds nothing to work: such an ask has no box
// in the tab order and the runtime writes it one — which is paint on the author's element,
// and PAGE_PAINT_ATTRIBUTES is the whole of what the runtime may leave standing there (a
// `tabindex` in it would blind the replay signature to an authored one). So the lend lasts
// exactly as long as the ring it goes with: the walk hands the stop over as it moves, and
// markHere takes it back when the reader leaves.
//
// One function for both ends of it, because written as statements at each end the walk's
// half only ever wrote — it took the last lend's reference with it and left the stop
// standing. Two control-less asks in a row is all it took, and the walk in the shipped
// examples goes through two: stepping off a task left it wearing a tab stop that nothing
// afterwards was ever going to remove.
let askLent = null;
function lend(ask) {
  if (askLent === ask) return;
  askLent?.removeAttribute("tabindex");
  askLent = ask;
  if (ask) ask.tabIndex = -1;
}
// Where the walk last left off. Not the same question as where the reader is standing,
// though one answer used to serve both: the ring said where they were and the walk read
// its own last landing off it. The Asks button is the walk's own control and focuses
// itself on the way to running a step, so a reader pressing it is standing in the banner
// and the ring is rightly gone from the page — leaving the walk with nothing to step from
// but whatever happens to be on screen, which would send every second press on that
// button back up the page.
let landed = null;
// A place in the document, stated as the ask it belongs to wherever it belongs to one: a
// control hoisted out of its ask and pointing back at it stands for that ask and not for
// the block it was hung beside, or stepping back from a suggestion's own ✓ Accept would
// land on the suggestion the reader is already standing on.
function askPlace(node) {
  const el = node.nodeType === 1 ? node : node.parentElement;
  const row = el?.closest(`[${ASK_ROW}], [${ASK_AT}]`);
  const at = row?.getAttribute(ASK_ROW) ?? row?.getAttribute(ASK_AT);
  return (at && elementById(at)) ?? node;
}
// The open ask the reader is standing in: the one holding the focus, or the one a control
// hoisted into the margin decides. The innermost of them, an ask being able to hold
// another (a question inside a suggestion's lf-new) — openAsks answers in document order,
// so the last container in the list is the nearest one.
//
// document.activeElement rather than focused(), for the reason askPosition gives: a
// control staged in a shadow tree retargets to its host, and the host is the place in the
// document this wants.
function standingIn() {
  const held = document.activeElement;
  if (!held || held === document.body) return null;
  const place = askPlace(held);
  return openAsks().findLast((ask) => ask === place || ask.contains(place)) ?? null;
}
// The ring that says so, painted from the focus rather than written where the reader was
// put. The walk used to write it, and it then said where the walk had left them rather
// than where they were: click away, work in the panel, come back tomorrow, and an ask
// nobody was standing in went on wearing "you are here". Every other way into an ask —
// Tab, a click on one of its controls — left the ring somewhere else entirely, so the
// same place was marked or not by how the reader had reached it.
//
// Keyed on focus and not on :focus-visible, which is a claim about the last input rather
// than about where the reader is: the Asks button's own press lands the focus by script
// after a click, and the ask it brought the reader to would wear nothing at all.
//
// The ask wears it, and so does every box it shows through (shownParts): the ask is
// what carries the id captureView writes down and the place askStep measures from,
// while an outline needs a box to hang on. Every widget in the vocabulary draws one
// box now — the wrapper that declined to took a form instead, in its own stylesheet,
// after the ring went out over its pieces and read as two boxes touching rather than
// as the one ask the reader is standing in — so on shipped pages the parts are the
// ask itself, and the fallback answers the wrapper any page can still style boxless
// in a line, the same way the thread's mark does (paintAnchors).
//
// The board's row for the ask is a second surface showing this one fact, so it is
// painted from this one reading rather than from a mark the board keeps for itself —
// and the ring is the chrome's as much as the page's (the [data-lf-ask] rule in the
// stylesheet is written against the attribute, not against the page), so wearing the
// attribute is the whole of what the row needs.
function markHere() {
  const here = standingIn();
  const row = here && asksPanel.querySelector(`[${ASK_AT}="${here.id}"]`);
  const wearing = new Set(
    here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
  );
  // A walk that runs past the foot of an open board leaves its mark off screen, which is
  // the board saying nothing exactly while the reader is using it. `nearest` so a row
  // already in view moves nothing.
  if (row && openEdge("asks")) row.scrollIntoView({ block: "nearest" });
  for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
    if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
  if (askLent !== here) lend(null);
  for (const marked of wearing) marked.setAttribute(PAGE_PAINT_ATTRIBUTE.ask, "1");
}
const readingBlock = () => blocksOnScreen().next().value?.[0] ?? null;
// Where the walk measures from: where the reader is standing, rather than where the walk
// last put them. It carried an id of its own, so every walk the reader had not made with
// this key started at the top of the page — select a paragraph and press `n` and you were
// taken back past everything you had read, and so was anyone scrolled halfway down
// pressing it for the first time. d/u measure from the scroll position and j/k from the
// focused thread; this measured from its own memory, which is the one place the reader
// isn't.
//
// Read in the order of how directly each says where they are: what they have focused,
// what they have selected, where this walk last left off (`landed`), and what they are
// reading. Every one of them can be absent, and then the first ask is the only answer
// there is.
//
// document.activeElement rather than focused(): a control staged in a shadow tree
// retargets to its host, which is exactly what this question wants — a place in the
// document to measure the asks against, not the control the register would dispatch to.
function askPosition() {
  const held = document.activeElement;
  // The banner stands over the page rather than in it, and its controls are addresses
  // the reader holds from wherever they are. The Asks button focuses itself on the way
  // to running this, so measuring from it would send every press on it back to the top.
  if (held && held !== document.body && !banner.contains(held)) return askPlace(held);
  const sel = getSelection();
  // A caret counts here, where the composer's reading of the selection (pageSelection)
  // wants words to quote: a click that placed one is the reader saying where they are.
  if (sel?.focusNode && !inChrome(sel.focusNode)) return askPlace(sel.focusNode);
  // A landing whose element a later version dropped is no place at all, and
  // compareDocumentPosition against a detached node answers about no document.
  return (landed?.isConnected ? landed : null) ?? readingBlock();
}
// The ask `dir` steps to from there. Document position rather than an index into the
// list, because the reader's place is a place and not a row: an ask holding it is the one
// they are standing on, so it is what they step off rather than what they step to.
function askStep(asks, dir) {
  const here = askPosition();
  if (!here) return dir > 0 ? asks[0] : asks.at(-1);
  const side =
    dir > 0 ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING;
  const reach = asks.filter((ask) => {
    const rel = here.compareDocumentPosition(ask);
    return !(rel & Node.DOCUMENT_POSITION_CONTAINS) && rel & side;
  });
  return dir > 0 ? (reach[0] ?? asks[0]) : (reach.at(-1) ?? asks.at(-1));
}
// Where the reader stands when they are put on an ask: the control that works it —
// one inside the ask, or one the widget hoisted into the margin and pointed back at
// it — or the ask itself, lent a tab stop where it holds nothing to work. Named
// because two presses put a reader on an ask and one of them is not a walk: a widget
// rebuilt under the reader (rebuild) has to hand back the place they were standing,
// and a second answer to "where is that" would drift from this one the first time the
// control rule changed.
function standOn(el) {
  const control =
    el.querySelector(ASK_CONTROL) ??
    document.querySelector(`[${ASK_ROW}="${el.id}"] ${ASK_CONTROL}`);
  if (!control) lend(el);
  (control ?? el).focus({ preventScroll: true });
}

// Standing on one ask: what n and p do once they have decided which, what a press on a
// board row does having been told outright, and where `g a` lands a digit. One function
// because it is one act — a second would be a second answer to "how do I put the reader on
// an ask", and the two would drift the first time either the reveal or the focus rule
// changed.
//
// The list comes with the ask, because the announcement names a place in it and the caller
// is the one that knows which list it walked: the walk's own, the board's, or the whole of
// what the page is waiting on where an address reached past the nine it can spell.
function goToAsk(next, asks) {
  // A thread's ask lives in the panel, which has no geometry while closed — the
  // same reason reveal() opens a settled group before the scroll.
  if (inChrome(next) && !panelOpen) setPanel(true);
  reveal(next); // a settled group or an inactive tab has no geometry until it opens
  landed = next;
  // The ring follows: the focus move is what paints it, so the walk says where to stand
  // and markHere says where the reader is standing, rather than both saying the second.
  standOn(next);
  // Each ask centres in the region it stands in. The banner clearance
  // scrollToElement answers for is the document scroller's alone, and a thread's
  // ask is in the panel's own list, which has none — so that one is the platform's
  // to centre and only a page ask takes the shared travel.
  if (inChrome(next)) next.scrollIntoView({ behavior: SCROLL, block: "center" });
  else scrollToElement(next);
  announce(`${asks.indexOf(next) + 1} of ${asks.length} waiting on you`);
}
function stepAsk(dir) {
  const asks = openAsks();
  if (!asks.length) return; // never: the key and the control are live only with asks
  goToAsk(askStep(asks, dir), asks);
}

// ---------- version diff ----------
// "Changes since vN": blocks (paragraphs, list items, widget items) whose text
// isn't present in the base version get a tinted marker, so re-reading a
// revision is cheap. Block-level and additions-only — deleted text has no home
// to mark — and a widget that renders its own body is opaque to it. The base is
// any version older than the one being read, offered by its own row in the
// chooser's menu, where the note saying what changed in words sits beside the
// press that marks it on the page.
//
// Which blocks and which widgets is the registry's answer both times, so a widget added
// to the vocabulary diffs on the strength of its entry: a widget item whose content
// model is prose is a block of the page's prose the same way a paragraph is.
const diffBlockSel = () =>
  [
    TEXT_BLOCK,
    "aside",
    ...tagsDeclaring((e) => e["x-parent"] && (e["x-content"] ?? "prose") === "prose"),
    // A verbatim body reaches the reader as its own words, so the widget is a block
    // of the page's prose the way a paragraph is. The leaf-blocks-only rule below
    // keeps the two sides symmetric: unupgraded (the base document) the authored
    // <pre> inside is the leaf and keys the same collapsed text the upgraded
    // widget's standing body keys live — so a rewritten or new draft marks, where
    // it used to be the one block of prose the diff was blind to.
    ...tagsDeclaring((e) => e["x-verbatim"]),
  ].join(",");
// Opaque: a widget whose upgrade renders its data body, so the text on screen is the
// module's and can't compare; and one whose slots a decision retires, which holds two
// versions of one passage and is already its own mark. Plus svg, drawn by either.
const diffOpaqueSel = () =>
  [
    ...tagsDeclaring(
      (e) => e["x-upgrade"] && !e["x-verbatim"] && e["x-content"] === "data",
    ),
    // flatMap, so the set holds holder tags rather than the arrays naming them: a set
    // of arrays never dedupes, two array objects never being equal.
    ...new Set(
      tagsDeclaring((e) => e["x-retired-when"]).flatMap(
        (tag) => registry[tag]["x-parent"],
      ),
    ),
    "svg",
  ].join(",");
// What is being compared, and whether the comparison is standing. Every rendering of
// the pair — the chooser's word and paint, each row's press, the rail down the span —
// is written by paintDiff and read back by nothing.
let diffBase = null;
let diffOn = false;
const diffMarked = [];
// The comparison request that owns the page. Every request takes the next number and every
// stop takes one too, so a base whose document lands after the reader has moved on is
// dropped rather than painted over the base they are standing on now. Reachable because the
// walk asks per row: it is one fetch per press, and the presses come faster than the network.
let diffRequest = 0;
// A block's key is its *authored* text (`wrote`), which is why that reading exists: it
// drops even the labels anchoring reads as the page's own words, because the base
// version is parsed unupgraded and holds none of them.
function diffBlocks(root) {
  const pairs = [];
  const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
  for (const b of root.querySelectorAll(blocks)) {
    if (inChrome(b) || b.closest(opaque)) continue;
    if (b.querySelector(blocks)) continue; // leaf blocks only, or nesting double-marks
    let key = wrote(b);
    // An x-says value is the page's words at the element's edge (renderSaid), so it
    // belongs to what this block says: folded into the key at its declared edge, a
    // version that moves a metric's number or an event's time marks though no prose
    // changed. Symmetric for free — the base parses unupgraded, where the same
    // attribute would have painted the same words through the pseudo-element.
    for (const [attr, edge] of Object.entries(
      registry[b.localName]?.["x-says"] ?? {},
    )) {
      const said = b.getAttribute(attr);
      if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
    }
    if (key) pairs.push([b, key]);
  }
  // Opaque widgets key by identity, not body: an upgrade rewrote the live body,
  // so text can't compare — but a widget the base didn't have still marks.
  for (const w of root.querySelectorAll(opaque)) {
    // parentElement, not w itself: an svg a widget rendered stays its widget's.
    if (inChrome(w) || w.parentElement?.closest(opaque)) continue;
    pairs.push([w, ` ${w.tagName}#${w.id}`]);
  }
  return pairs;
}
// The base version's own document, which is the whole of what a comparison waits for. Split
// from the marking below so that everything touching the live page happens in one synchronous
// stretch after the single await: the walk through the menu asks for a comparison per row, and
// a marking pass that could interleave with the next row's would leave two bases' marks
// standing under a chooser naming one of them.
async function baseDocument(baseVersion) {
  const baseName = versionUrl(baseVersion);
  const res = await fetch(baseName);
  if (!res.ok) throw new Error(`couldn't load ${baseName}`);
  return new DOMParser().parseFromString(await res.text(), "text/html");
}
function applyDiff(doc, baseVersion) {
  // Multiset membership rather than an alignment: an unchanged block that
  // merely moved stays unmarked; a changed or new one has no base twin.
  const base = new Map();
  for (const [, key] of diffBlocks(doc)) base.set(key, (base.get(key) ?? 0) + 1);
  for (const [b, key] of diffBlocks(document.body)) {
    const left = base.get(key) ?? 0;
    if (left > 0) base.set(key, left - 1);
    else {
      b.classList.add("lf-ins-block");
      diffMarked.push(b);
    }
  }
  // The state half: block keys catch words, and a pure state change — a card
  // in a different column, a pick on a different option — has no text of its
  // own. Compare declared facets instead: the base version's state (its markup
  // plus both folds as of it — a report standing at the base painted there
  // just as an action did, so what the reader saw includes it) against the
  // live DOM, which already wears the current folds. Body facets are words and
  // the block keys above own them.
  const baseFold = stateFold(baseVersion);
  const baseReports = reportFold(baseVersion);
  for (const { tag, spec } of stateSpecs()) {
    if (!spec.record || spec.record.kind === "body") continue;
    for (const widget of document.body.querySelectorAll(tag)) {
      if (inChrome(widget) || quoted(widget)) continue;
      const units =
        spec.unit === "widget" || !spec.unit
          ? widget.id
            ? [widget]
            : []
          : [...widget.querySelectorAll(`${spec.record.within} > [id]`)];
      for (const el of units) {
        const baseEl = doc.getElementById(el.id);
        if (!baseEl) continue; // new to this version: the content half marks it
        // The later writer wins between the channels, as replay's seq order has
        // it; a fold entry whose detail lacks this record's field wrote some
        // other facet of the unit and says nothing about this one.
        const writers = [baseFold.get(el.id), baseReports.get(el.id)]
          .filter((c) => c && spec.record.value in c.e.detail)
          .sort((a, b) => a.e.seq - b.e.seq);
        const before = writers.length
          ? foldedFacet(writers.at(-1).e, spec.record)
          : domFacet(baseEl, spec.record);
        const now = domFacet(el, spec.record);
        if (before === now) continue;
        // The element the change reads on: the option now picked, or the moved
        // card itself.
        const target =
          (spec.record.kind === "attribute" && now && elementById(now)) || el;
        if (!target.classList.contains("lf-ins-block")) {
          target.classList.add("lf-ins-block");
          diffMarked.push(target);
        }
      }
    }
  }
  // Container widgets surface marks their panels hide (lf-tabs badges each tab).
  document.dispatchEvent(new CustomEvent("lf-diff"));
  return diffMarked.length;
}
// Whether a version can be compared with the one being read: anything published
// before it, which is which rows the menu builds a press onto.
const comparable = (version) => VNUM !== null && version < VNUM;
// Every rendering of the pair above, written in one place: the chooser's word, its
// paint and what it says it will do, the checked state of each row's Δ, and the rail
// down the rows the comparison spans. Called by the setter, by a menu rebuild — the
// other thing that can leave a rendering behind the state — and once at load, so what
// the chooser says it will do is written here from the start rather than standing as a
// second copy of these sentences up where the control is built.
function paintDiff() {
  versionBtn.textContent = versionLabel(diffOn);
  versionBtn.classList.toggle("on", diffOn);
  // Rewritten on every diff change, so the key it names is taken from the row each time
  // rather than typed into one of the two branches and forgotten in the other.
  versionBtn.title = diffOn
    ? `Showing what changed since v${diffBase} — pick a version, or press its Δ again to stop`
    : `Versions: read one, or mark what changed since it (${labelOf(CHOOSER)})`;
  for (const row of versionMenu.querySelectorAll(".lf-version-row")) {
    const version = +row.dataset.lfVersion;
    row.classList.toggle(
      "lf-compared",
      diffOn && version >= diffBase && version <= VNUM,
    );
  }
  for (const press of versionMenu.querySelectorAll(".lf-version-diff"))
    press.setAttribute(
      "aria-checked",
      String(diffOn && +press.dataset.lfVersion === diffBase),
    );
}
paintDiff();
// Whether the comparison is standing and what against — the only thing that decides
// it, the marks and the paint being renderings rather than a second copy.
function setDiff(on, base) {
  diffOn = on;
  if (on) diffBase = base;
  if (!on) {
    diffRequest++; // a stop outranks a comparison still on its way
    for (const b of diffMarked) b.classList.remove("lf-ins-block");
    diffMarked.length = 0;
    document.dispatchEvent(new CustomEvent("lf-diff"));
  }
  paintDiff();
}
// The one way a comparison starts, from a row's press or from the walk through the menu.
// It states a base rather than toggling one — the toggle is a press's own reading of it,
// and the walk has none to spend, standing on a row being what makes it the base however
// many times the reader arrives there.
async function showComparison(base) {
  const mine = ++diffRequest;
  let doc;
  try {
    doc = await baseDocument(base);
  } catch {
    showToast(`Couldn't load v${base}`);
    return;
  }
  if (mine !== diffRequest) return;
  if (diffOn) setDiff(false); // the old base's marks, before the new base's land
  const n = applyDiff(doc, base);
  setDiff(true, base);
  showToast(
    n
      ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}`
      : `No text changes since v${base}`,
  );
}
// A press names one base, so pressing the standing one again is the way off it: a Δ is a
// toggle where it is lit and a switch of base where it isn't. The keyboard's way off is the
// walk itself — down to the version being read, which is comparable with nothing and so
// stops rather than re-bases.
const pressComparison = (base) =>
  diffOn && base === diffBase ? setDiff(false) : showComparison(base);

// ---------- banner ----------
// "Claude is working" is a claim in status.json, and nothing revises a claim once the
// session behind it walks away — so a page nobody is watching reads exactly like a page
// whose user has said nothing yet. The banner asks whether anyone is attending, and
// only two things answer yes: Claude is credibly busy, or a `leaf wait` is live.
// Everything else is absence, where the reason and the remedy are all that vary.
//
// One of those absences is not a fault, and reading it as one was the bug. A page served
// across sessions — a command hub, a dashboard left open for a fortnight — is unheld for
// most of its life, and a night of it is Tuesday. So the banner separates "somebody is
// behind this page and isn't keeping up", which is worth an amber dot and a nudge, from
// "nobody is behind it", which is the standing page at rest: grey, and the plain fact
// that it picks up again when a session does.
//
// Every one of those answers is about a session that exists or existed, and a page can be
// served with none — the whole of leaf.page is, each example a working page on a static
// host where the log is the reader's own browser and no agent will ever read it. The
// banner had no way to say that, so the page said the nearest thing it could and claimed
// to be listening: green dot, "awaits", over a page waiting for nobody. Whoever answers
// the poll declares it instead (`unattended`), and it is judged ahead of the rest because
// it is not a state the evidence below could reach — there is no claim to weigh, no pid
// to look for, and nothing coming that would change the answer.
const HANDOFF_GRACE_MS = 2 * 60 * 1000;
const WORKING_GRACE_MS = 15 * 60 * 1000;
// How long a claim of work may go unrefreshed before the page stops taking its word for
// it. Exported, because the banner is not the only thing that judges one: a page running
// a fleet says the same sentence per row, and a second threshold spelled in a widget
// would be a second answer to "how long is too long" — free to disagree with the banner
// directly above it about the very same silence. The caller supplies the rope where its
// claim has a shorter one; the constant is the default because that is the case there is
// only one of.
export const quietSince = (ts, grace = WORKING_GRACE_MS) =>
  Boolean(ts) && Date.now() - new Date(ts).getTime() > grace;
// Which claim each kind reads out, and so whose detail it may speak. A `working`
// claim gone quiet under a live watcher is judged `listening` too, and that detail
// names what the agent was doing rather than what it wants back — the wrong half of
// the loop to read out after "awaits". The question sits here rather than at each
// seat, for the reason `kind` does: two seats answering it separately is two answers
// to what the page may say it is waiting for. A kind absent here is a judgment
// against the claim — nobody is behind the page, or the page is closed — and the
// claim's words about the work are not the news there.
const DETAIL_FROM = { working: "working", listening: "waiting" };
// The claim-against-proof judgment, one function for every surface that shows a
// status: the banner's sentence about this page and a panel row about a neighbour
// read the same fields the server gathers in one place (`presence`), so the two can
// never disagree about what "working" means. `kind` is the judged state and `detail`
// the claim's own words where that state licenses them; the caller words it for its
// seat.
function presented(state) {
  const { status, listening, session_alive, unattended } = state;
  // How long the claim has gone unrefreshed. The rope is short for the status
  // `leaf wait` writes as it prints a batch, because the agent writes its own
  // `leaf status` after acknowledgement — that mark outliving minutes is a dropped
  // pickup, not a long turn.
  const quiet = quietSince(
    status.ts,
    status.handoff ? HANDOFF_GRACE_MS : WORKING_GRACE_MS,
  );
  // Nothing is behind the claim. The claimant pid settles it where there is one: gone
  // is gone, whatever the claim says and whether a stray `leaf wait` still holds
  // a lease for a session that can no longer read it. Where nothing claimed the
  // page — a server started outside an agent host — there is no pid to look for, so a
  // live watcher or a claim still inside its grace is the whole of the evidence, and
  // once both are spent the page is unheld too.
  const unheld =
    session_alive === false || (session_alive === null && !listening && quiet);
  const kind = unattended
    ? "unattended"
    : status.state === "idle"
      ? "closed"
      : unheld
        ? "unheld"
        : status.state === "working" && !quiet
          ? "working"
          : listening
            ? "listening"
            : "away";
  return {
    kind,
    quiet,
    detail: status.state === DETAIL_FROM[kind] ? status.detail : "",
  };
}
// The judgment's third seat. A reader keeps a leaf in a tab for days and looks at
// six of them; the tab strip is the whole of what the browser shows about a page nobody
// has open, so the state that decides whether to go there belongs in it. Same judgment
// (presented), same writer as the dot and the line, and the tone is taken off the dot
// itself rather than mapped from kind to token again — one answer to what a tone looks
// like, so a project overriding --ok overrides the tab with it and the two cannot come
// apart. It is a read of the theme, not of the rendering: what colour this tone paints
// as is a question nothing else can answer, where what state the page is in is already
// in hand.
//
// The mark is the vendored icon.svg — the page's own asset like the theme, so a project
// can put its own there — and all the runtime does to it is paint the one element it
// declares. Refused rather than defaulted, as the theme's shadow block is: a mark with
// no lf-tone leaves a tab that never changes, which is a status readout that silently
// isn't one.
const tabLink = Object.assign(document.createElement("link"), {
  rel: "icon",
  type: "image/svg+xml",
  href: "/icon.svg",
});
document.head.append(tabLink);
let iconMark = null;
const iconUrls = new Map();
// The mark with one colour written over it, or — for "" — the mark as authored. A style
// element appended last outranks the file's own rules, the dark-scheme block included,
// since a media query carries no specificity of its own. So this knows nothing about the
// icon beyond the class it promises, and a project's own mark is painted on the same
// terms.
function iconUrl(color) {
  let url = iconUrls.get(color);
  if (url === undefined) {
    const svg = iconMark.cloneNode(true);
    if (color) {
      const style = svg.ownerDocument.createElementNS(
        "http://www.w3.org/2000/svg",
        "style",
      );
      style.textContent = `.lf-tone { fill: ${color} }`;
      svg.append(style);
    }
    url =
      "data:image/svg+xml," +
      encodeURIComponent(new XMLSerializer().serializeToString(svg));
    iconUrls.set(color, url);
  }
  return url;
}
async function loadIcon() {
  const response = await fetch("/icon.svg");
  if (!response.ok)
    throw new Error(`leaf: the tab icon failed to load (${response.status})`);
  const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  // Two failures, and the same symptom: no element to paint. A parse error is reported
  // as a document rather than thrown, so a mark that isn't SVG at all reaches the class
  // check and fails it — sending whoever overrode the file to look for a class that is
  // sitting right there in it.
  const broken = doc.querySelector("parsererror");
  if (broken)
    throw new Error(
      // Collapsed, because the browser's report is laid out as a page and reads as
      // several lines of it; what matters is the line and column it names.
      `leaf: icon.svg is not SVG — ${broken.textContent.replace(/\s+/g, " ").trim()}`,
    );
  if (!doc.querySelector(".lf-tone"))
    throw new Error(
      "leaf: icon.svg carries no lf-tone element, which is where the page's " +
        "status is painted",
    );
  iconMark = doc.documentElement;
  // Left where `version export` can find it: a file has no session behind it, so a copy
  // wears the mark saying nothing rather than the tone it was exported under.
  tabLink.dataset.lfRest = iconUrl("");
  paintTab();
}
// A declaration, and called from two places, because the fetch above can land after the
// first poll has already judged the page.
function paintTab() {
  if (!iconMark) return;
  const url = iconUrl(getComputedStyle(dot).backgroundColor);
  // Written only on change: an unchanged poll must not hand the browser its icon again
  // every two seconds.
  if (tabLink.getAttribute("href") !== url) tabLink.setAttribute("href", url);
}
// One writer for the dot, the line and the tab, offline included: null is the poll saying
// it couldn't reach the server, not a second function's own rendering. The line is one of
// the two things on the row that give up width when it runs out (see the theme), so what
// a narrow window clips is a hover away, the way the version chooser's label is — worth
// more now that the line carries the ask and not only the state. Written every time
// rather than only when the box clips, because whether it does is a fact about the
// rendering and nothing here reads that back.
const showStatus = (tone, ...parts) => {
  dot.className = "lf-dot" + (tone ? " " + tone : "");
  statusText.textContent = "";
  statusText.append(...parts);
  statusText.title = statusText.textContent;
  paintTab();
};
function renderStatus(state) {
  if (state instanceof Error) {
    showStatus("offline", "Page couldn't apply current state — reload");
    return;
  }
  if (state === null) {
    showStatus("offline", "Server offline — comments won't send");
    return;
  }
  const { status, pending } = state;
  const { kind, quiet, detail } = presented(state);
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = pending
    ? `${pending} update${pending === 1 ? "" : "s"} waiting.`
    : "Your comments are saved.";
  let text = "",
    showAge = false;
  if (kind === "closed") text = "Leaf closed";
  else if (kind === "unattended")
    // No agent named and no pickup promised, which is the whole difference from
    // `unheld` below: there is nobody to name and nothing coming. What the reader can
    // still do is everything — the page works, it just works alone — so the line says
    // where their gestures go rather than that they are saved for someone.
    text = "Nobody is behind this page. What you do here stays in this browser.";
  else if (kind === "unheld")
    // No agent is named, because which one picks the page up next is not a fact this
    // page holds — only that the log is there for whichever does.
    text = `No session holds this page. ${saved} It picks up again when a session does.`;
  else if (kind === "working") {
    showAge = Boolean(status.ts);
    text = `${agentName()} is working${detail ? " — " + detail : ""}`;
  } else if (kind === "listening") {
    // Attendance is half the news; the other half is what the page wants back. The
    // Asks count beside it says how many things are unanswered and nothing about what
    // any of them is, so the claim's detail says that here in the agent's own words,
    // the way a `working` claim's says what it is doing. With nothing declared it is
    // the standing instruction, which is what a page asking nothing wanted anyway.
    //
    // "awaits" while the judged kind stays `listening`: they name different things.
    // The kind and the server field behind it are the evidence — a watcher live on the
    // other end — and the words are the stance it supports, which is the registry's
    // own word for a standing request to the reader (x-awaits). Wording is the seat's,
    // per `presented`, so a row in the leaves panel leads with the bare word and
    // carries the same ask behind it.
    text = `${agentName()} awaits — ${detail || "select text to comment"}`;
  } else {
    // Somebody is behind the page and isn't attending: say which and what to do. A
    // long silence means Claude lost the thread; a recent check-in means it is
    // mid-turn and the next one collects.
    const [why, how] = quiet
      ? [
          `${agentName()} last checked in ${ago(status.ts)}.`,
          "Nudge it in the terminal.",
        ]
      : [`${agentName()} isn't watching right now.`, "It picks them up next turn."];
    text = `${why} ${saved} ${how}`;
  }
  const line = [text];
  if (showAge)
    line.push(
      " ",
      Object.assign(el("span", "lf-age"), { textContent: `(${ago(status.ts)})` }),
    );
  showStatus(TONE[kind], ...line);
}

// Navigate to a version with the pin semantics every chooser shares: an older
// version pins the view, the newest unpins it.
const goVersion = (version) => {
  const path = versionUrl(version);
  location.href = version === latestVersion ? path : `${path}?pin`;
};
function renderVersions(state) {
  versions = state.versions;
  const notes = {};
  for (const e of events) if (e.kind === "note") notes[e.version] = e.text;
  const key = JSON.stringify([state.versions, notes]);
  const current = state.versions.includes(VNUM) ? VNUM : null;
  // Rebuilt rather than reconciled: this runs only when the versions or their notes
  // actually changed, which on a page's whole life is a handful of times, and the
  // menu is only ever read while it is open — where a rebuild would take the focused
  // row out from under a walk. So an open menu defers the rebuild, and the key is
  // what the built list holds rather than what the last poll saw: consuming it here
  // and skipping the build inside would mark the change handled and leave that
  // version out of the menu until some later one happened along. A version arriving
  // under an open menu is the new-version chip's news; the list catches up on the
  // next poll after it closes.
  if (key !== lastVersionsKey && !versionMenuOpen) {
    lastVersionsKey = key;
    versionMenu.textContent = "";
    for (const version of state.versions) {
      const isLatest = version === state.versions.at(-1);
      const row = el("button", "lf-version-row");
      row.setAttribute("role", "menuitem");
      row.dataset.lfVersion = version;
      // The version and its note are two kinds of word — which one this is, and
      // what it was — so they are two elements rather than one string. That is
      // what lets the note wrap to as many lines as it needs, which is the whole
      // reason the notes are here rather than on a control 190px wide.
      row.append(
        el("span", "lf-version-num", `v${version}${isLatest ? " (latest)" : ""}`),
      );
      if (notes[version]) row.append(el("span", "lf-version-note", notes[version]));
      if (version === current) row.setAttribute("aria-current", "true");
      row.onclick = () => {
        showVersionMenu(false);
        goVersion(version);
      };
      versionMenu.append(row);
      // The comparison this row offers, in the menu's second column beside the note
      // that says the same thing in words. A grid sibling rather than a child, a
      // button inside a button being no markup at all, and named in full: the glyph
      // is the eye's shorthand and says nothing aloud.
      if (comparable(version)) {
        const press = el("button", "lf-version-diff", "Δ");
        press.setAttribute("role", "menuitemcheckbox");
        press.dataset.lfVersion = version;
        press.setAttribute("aria-label", `Mark what changed since v${version}`);
        press.title = `Mark what changed since v${version}`;
        // The pointer's own door, and it closes the menu: the marks are on the page this
        // hangs over, and a pointer has no walk to be standing in the middle of. The
        // keyboard's is the walk itself, which leaves the list up.
        press.onclick = () => {
          showVersionMenu(false);
          pressComparison(version);
        };
        versionMenu.append(press);
      }
    }
    paintDiff(); // a fresh list, and a standing comparison to show on it
  }
  latestVersion = state.versions.at(-1) ?? null;
  const behind = latestVersion !== null && VNUM !== null && latestVersion !== VNUM;
  // Follow the newest version unless pinned or the user is mid-composition:
  // drafts survive navigation, but an open composer or a live selection
  // doesn't. While deferred, the chip shows instead.
  if (behind && !PINNED && !midComposition()) {
    location.replace(versionUrl(latestVersion));
    return;
  }
  showNews(latestChip, behind);
  if (behind) latestChip.textContent = `New version available → open v${latestVersion}`;
}
// A gesture of the reader's that the page has not accounted for in a log read, asked of
// the layer's own signals rather than of any widget by name: a drag wears .lf-dragging
// (the module sets it), every unresolved browser event is in the outbox, and an undo
// in flight is its own — it is tracked separately because the walk itself cannot be
// offered again while its event is being answered.
// Two questions want the answer,
// which is why it has a name of its own: navigating away would destroy such a gesture,
// and the undo walk reads the log to find the last thing the reader did, so it cannot
// answer while the page is holding one. Its own press included — a second `z` landing
// inside the first one's trip would read the log from before it and withdraw the same
// gesture again, which the door refuses and the reader hears as a page that couldn't
// reach its server.
const unrecordedGesture = () =>
  undoing || outbox.length > 0 || Boolean(document.querySelector(".lf-dragging"));
// The user is mid-something navigation would destroy: the above, and the words they
// have typed — a composition surface is a focused textarea, any holding words, or a
// widget-built one (data-lf-offer) even empty, because deleting everything is still an
// edit.
const midComposition = () =>
  composerOpen ||
  Boolean(fabAnchor) ||
  unrecordedGesture() ||
  (document.activeElement?.tagName === "TEXTAREA" &&
    (document.activeElement.value !== "" ||
      document.activeElement.hasAttribute("data-lf-offer")));
// Through the chooser's own travel, so the chip opens the version it names. `/` reached
// the same place by asking the server which version is newest — a second route to what
// goVersion states, and one that could land the reader on a version the chip had not
// offered, since the answer is re-derived at the press rather than at the render.
latestChip.onclick = () => goVersion(latestVersion);

// ---------- polling ----------
// Rendering version V shows V plus every action recorded up to it, replayed in
// seq order: a reload keeps the user's drag, a second tab follows along
// live, and a decision made on v10 still stands on v25. Widgets opt in by
// exposing applyAction(action, detail) — an absolute placement, so replaying
// the sender's own action is a no-op. The first poll runs after upgrades
// settle, so the methods exist, and the pass runs at the end of a poll, so the
// panel's own widgets do too.
//
// Absolute is what makes replay converge, and the order is the rest of what it
// owes: an action applied after the gesture that superseded it states the widget
// from its older place in that order, and the reader's next gesture computes from
// what it painted and sends a decision they never made. Applying each action once
// says nothing about *when* — an action recorded before a click can still be applied
// after it. Two facts keep the order between them. A widget whose own action has not
// been answered is left alone (`outbox`): the page's copy of the widget is
// ahead of every log it can read, so nothing in one can be shown to sit after it.
// That hold ends when the POST's state (or a periodic poll) contains the minted action —
// from there the log being append-only carries it, since an answer the page has already
// read past is stale whole and dropped (receiveState).
//
// Reports ride the same pass with the precedence reversed. A report is a
// worker's provisional news (`leaf report`, x-report in the registry): it
// paints onto the versions published before it and stops at the version whose
// note answers it by id (`reports`, the mirror of `restated`) — where an
// action outranks every later version until a retraction. The two channels
// never share a record today, so their order within one poll is unobservable;
// each keeps seq order within itself.
//
// The log outranks the markup, and that is the whole rule: authored state is the
// initial condition, never a later correction, so nothing a version does or
// omits can un-make a decision by itself. The repo's own CLAUDE.md carries why,
// and what it cost to learn. Replay used to stop at the handoff cursor, on the
// premise that a version written after the agent saw an action encoded it — a
// premise nothing checked, and acknowledgement is not assent. Only a version can say
// what the agent did with an action, and saying it is `version check`'s business now
// (restatement_errors), not something inferred here from silence.
const appliedActions = new Set();
// What an action rests on: the widget that sent it, and the parts of that widget
// its detail names — a `move` rests on its card as much as on the board. Either
// can be taken back, which is what lets a rewritten card drop its own moves while
// the rest of the board stays where the user put it. Containment is the test,
// not "the page has an element by that id", so a literal detail value can't
// collide with an unrelated element that happens to be called the same thing.
function restsOn(e, widget) {
  // flat(), because a detail field may name several elements at once (a group's
  // set of picks) and each of them is something the action rests on.
  const parts = Object.values(e.detail)
    .flat()
    .map((v) => (typeof v === "string" ? elementById(v) : null))
    .filter((el) => el && widget && containsAcross(widget, el))
    .map((el) => el.id);
  return [e.widget, ...parts];
}
// Which of those a later version took back. One spelling of the rule, because three
// readings ask it — replay, the fold, and the thread list — and a decision standing in
// one of them and retracted in another is the drift `restated` exists to prevent. The
// ids rather than a boolean, since replay says so on the page (data-lf-restated) and
// the other two only count them.
//
// A widget the page no longer holds answers for itself alone, which is what a version
// honoring a decision leaves behind: the wrapper is retired, so there is nothing to ask
// about containment and nothing that should read as a retraction — retirement is the
// decision being carried out, not taken back. That is also the answer interact.py gives
// without trying, reading a version file where the same element is simply absent.
function retractedIds(e, floors, widget) {
  return restsOn(e, widget).filter((id) => (floors.get(id) ?? 0) > e.version);
}
// Retractions: a version that rewrote the words or state under a decision says
// so with `restated`, and publishing records it on the note that released it.
// Reading it from the log rather than from the markup is what makes it last —
// the version *after* the rewrite declares nothing, and its silence would
// otherwise hand the user's retracted state straight back.
// The two note fields are the reviewer and agent channels' readings of one durable
// relation: a version answers ids, and its answer lasts without being repeated.
// Memoized on the log's identity and the field/window query: `events` has one writer,
// which replaces the array wholesale (poll), so a cached answer cannot be stale and
// every consumer shares the same filter-and-max fold.
const noteFloorsMemo = new WeakMap();
function noteFloors(field, upto) {
  let byQuery = noteFloorsMemo.get(events);
  if (!byQuery) noteFloorsMemo.set(events, (byQuery = new Map()));
  const query = `${field}:${upto}`;
  if (byQuery.has(query)) return byQuery.get(query);
  const floors = new Map();
  for (const e of events)
    if (e.kind === "note" && e.version <= upto)
      for (const id of e[field] || [])
        floors.set(id, Math.max(floors.get(id) ?? 0, e.version));
  byQuery.set(query, floors);
  return floors;
}
const retractionFloors = (upto) => noteFloors("restated", upto);
// A report's end: the ids the notes in the window answered, absorbed or
// overruled — the agent channel's mirror of retractionFloors, read from the
// log for the same reason (the version after the answer declares nothing, and
// its silence must not hand the report back).
const answeredReports = (upto) => noteFloors("reports", upto);
// An id-bearing element's state as markup can say it: tag, attributes, and
// place among its id-bearing kin. Text is deliberately absent — words are the
// static gate's subject (restatement_errors); this is the rest, the state no
// version file can speak. What the runtime itself paints onto page elements —
// exactly PAGE_PAINT_ATTRIBUTES — is absent too: no version can assert those,
// and looking away from them keeps a reading taken from the live DOM equal to
// one taken from the file without hiding a widget's own data-lf state. Diffed around each replay batch to
// record what replay wrote, and imported by version check --render to read the version
// files with the same eyes, so the two readings cannot drift.
export function shallowSigs(root) {
  const sigs = new Map();
  for (const el of [root, ...root.querySelectorAll("[id]")]) {
    if (!el.id) continue;
    const attrs = [...el.attributes]
      .filter((a) => !PAGE_PAINT_ATTRIBUTES.has(a.name))
      .map((a) => `${a.name}=${a.value}`)
      .sort()
      .join(" ");
    const kin = [...(el.parentElement?.children ?? [])].filter((c) => c.id);
    sigs.set(
      el.id,
      `${el.tagName} [${attrs}] in=${el.parentElement?.id ?? ""}#${kin.indexOf(el)}`,
    );
  }
  return sigs;
}
// The settlement mark is the layer's paint of a logged decision, never a module
// obligation: x-retired-when and x-parent already state which verbs settle a holder,
// so the writer with the registry and the log both in hand is this replay. It used to
// be each holder module's duty, documented in the scaffold and enforced nowhere — the
// suggestion remembered, and the first module that forgot would have silently split
// the page's reading from the file's, with `leaf comment` refusing quotes as the only
// symptom. A module is still free to say the mark sooner as its own gesture's paint
// (lf-suggestion does, choreographing its fold around it); this write is then the
// no-op that makes the guarantee unconditional. Written only where an action retires
// behind the version and retraction gates — applied, thrown, or with no applyAction
// to call — so a pinned older page and a restated decision stay unmarked. The mark
// follows the fold both ways: the file's standing state is the last surviving action
// per unit, so a widget-unit verb that doesn't settle displaces the decision there,
// and the mark goes with it — left standing, the page would silence slots the log had
// handed back. Returns whether it wrote, for the one caller that would otherwise
// report nothing written.
function markSettled(el, action) {
  const outcomes = settlementSlots()[el.localName];
  if (!outcomes) return false;
  if (outcomes[action]) {
    el.setAttribute("data-lf-state", action);
    renderRetired(el);
    return true;
  }
  const unit = registry[el.localName]?.["x-state"]?.[action]?.unit ?? "widget";
  if (unit === "widget" && el.hasAttribute("data-lf-state")) {
    el.removeAttribute("data-lf-state");
    renderRetired(el);
    return true;
  }
  return false;
}
// One act for the three ways an action ends behind the gates — applied, thrown, or
// with no applyAction to call: retired for this load, with the settlement mark
// brought up to date in the same stroke, so a new terminal path cannot retire
// without marking.
function retire(el, e) {
  appliedActions.add(e.seq);
  return e.kind === "action" && markSettled(el, e.action);
}
function applyActions() {
  // Never mutate the page under a live gesture — a replayed foreign action could
  // move the nodes a drag preview is holding. Retry next poll.
  if (document.querySelector(".lf-dragging")) return;
  const floors = retractionFloors(VNUM);
  const withdrawn = takenBack();
  const answered = answeredReports(VNUM);
  const deferredWidgets = new Set();
  let applied = false;
  const started = [];
  // Withdrawals this load has not answered for yet. A gesture the page is showing and
  // the log no longer holds leaves the two disagreeing, and putting that right is the
  // whole of what an undo does on screen — done here rather than at the press, so the
  // tab that pressed and the tab that merely heard arrive at one page by one route.
  //
  // Only a withdrawal that arrives after the log has been rendered has anything to put
  // right: one already in the log at load skipped the gesture it names, so the page was
  // built without it. Asking instead whether *replay* applied that gesture is the
  // question one tab always answers wrongly — the tab that made it painted it itself
  // and replay never touched it (outbox), so the tab that pressed `z` would
  // be the one tab the press did nothing in.
  for (const e of events) {
    if (e.kind !== "undo" || appliedActions.has(e.seq)) continue;
    const target = logRendered && eventById(e.undoes);
    const put = target && target.kind === "action" && restoreFor(target);
    if (!put) {
      appliedActions.add(e.seq); // nothing to put right, now or ever
      continue;
    }
    // The holds the loop below keeps, kept here too, because this is replay. A widget
    // the page has painted ahead of the log has its events reconsidered once the
    // outbox answers its own gesture, and one that asks for time gets the next state —
    // an `lf-draft` with an editor standing answers false rather
    // than let the log pull words out from under the reader. So the withdrawal is marked
    // answered only once it has been, or it is spent on a widget that never took it
    // and that tab holds the withdrawn words for the rest of its life, with the
    // pending mark cleared because the fold agrees the gesture is gone.
    if (actionPending(target.widget) || deferredWidgets.has(target.widget)) continue;
    if (put.state) {
      if (put.el.applyAction(put.state.action, put.state.detail) === false) {
        deferredWidgets.add(target.widget);
        continue;
      }
      // The restored action is the unit's standing state again, so the settlement
      // mark follows it here exactly as it follows an applied one (retire): a prior
      // settlement a recorded verb had displaced comes back marked, or the page would
      // show words its own reading had retired. After the apply rather than beside
      // it, because a widget that asked for time has not taken the restore yet and
      // must not be marked as having settled on it.
      markSettled(put.el, put.state.action);
    } else rebuild(put.el);
    appliedActions.add(e.seq);
    // Counted as replay having moved the page, because it has: a restore puts words
    // back that a decision had taken off it, and the marks belong on them again. The
    // rebuild is the sharp case — its nodes are new, so a mark painted over the old
    // ones is a range on a subtree the document no longer has, and a comment on the
    // sentence the reader just took back came back unmarked and read as detached.
    applied = true;
  }
  // Actions first, then reports, each pass bracketed by its own snapshot so what
  // replay wrote is attributed to the channel that wrote it: version check
  // --render reads the reviewer channel's record (replayWrote) as "state the log
  // replays over", and a report's write there would lay a worker's news at the
  // user's door. The loop inside a pass is synchronous, so between a pass's two
  // readings nothing but its applyAction calls — no gesture, no widget rendering
  // itself — can touch the page, and the diff of the ends is exactly what that
  // channel wrote.
  for (const [kind, wroteAttr] of [
    ["action", PAGE_PAINT_ATTRIBUTE.replayWrote],
    ["report", PAGE_PAINT_ATTRIBUTE.reportWrote],
  ]) {
    const before = events.some((e) => e.kind === kind && !appliedActions.has(e.seq))
      ? shallowSigs(document.body)
      : null;
    const priorMotion = before && new Set(document.getAnimations());
    let wrote = false;
    for (const e of events) {
      // Held rather than decided, both of them: a widget the page has painted ahead
      // of the log (`outbox`, see above) has its events reconsidered when its answer
      // reads the gesture back, and a widget that asked for time gets the next state —
      // so nothing here is retired on a page state that was temporary.
      if (
        e.kind !== kind ||
        appliedActions.has(e.seq) ||
        deferredWidgets.has(e.widget) ||
        actionPending(e.widget)
      )
        continue;
      const el = elementById(e.widget);
      // Every terminal action is decided here and never looked at again. This pass runs
      // after the panel has rendered the log, so a widget that isn't here is one no
      // version can carry — an honored suggestion, whose wrapper the version replaced.
      if (!el) {
        appliedActions.add(e.seq);
        continue;
      }
      // Withdrawn: the reader took this gesture back, so the log no longer holds it and
      // replay does not put it on the page. Ahead of the chrome branch below rather
      // than inside it, because the fold drops a withdrawn action wherever it stands
      // and a reading of the log that replayed one the fold had dropped would be the
      // two disagreeing about what the page says. What this load may have painted
      // before the withdrawal arrived is the pass above's to put right.
      if (e.kind === "action" && withdrawn.has(e.id)) {
        appliedActions.add(e.seq);
        continue;
      }
      if (e.kind === "report") {
        // A report paints the versions published before it and ends at the one
        // whose note answered it: a pinned older version predates the news, and
        // an answered report's state is the document's to speak. No retraction
        // floors here — a report is not a decision `restated` can take back.
        if (e.version > VNUM || answered.has(e.id)) {
          appliedActions.add(e.seq);
          continue;
        }
      } else if (!inChrome(el)) {
        // A pinned older version is a historical view, so it shows what the user
        // had done by then and not what they did later. A widget inside the comment
        // layer (.lf-chrome — a reply's inline question) has no version at all: its markup
        // is frozen in the log, and no version can rewrite or retract it.
        if (e.version > VNUM) {
          appliedActions.add(e.seq);
          continue;
        }
        const gone = retractedIds(e, floors, el);
        if (gone.length) {
          // Say so on the page: a decision undone looks exactly like one never
          // made, and the user is owed the difference.
          for (const id of gone) {
            const target = elementById(id);
            if (target) target.setAttribute(PAGE_PAINT_ATTRIBUTE.restated, "1");
          }
          appliedActions.add(e.seq);
          continue;
        }
      }
      // Present but never upgraded is a different fact from absent: the module
      // failed, its own fail-soft box says so, and retiring the decision here
      // would silently drop what the user recorded. The events wait while the
      // upgrade pass may still deliver the module; once it has finished, no
      // import retries this load, and holding them forever stalls the
      // caught-up stamp the export and render gates wait on. Retiring is this
      // load's memory alone (appliedActions), so a later load with the module
      // healthy replays them. It stands behind the version and retraction gates
      // above — they read the log alone, never the method — so the settlement
      // mark can land here too: the mark is the layer's, and a holder whose
      // module supplies no applyAction at all still owes the page nothing.
      if (!el.applyAction) {
        if (document.body.dataset.lfUpgraded === "1" && retire(el, e)) wrote = true;
        continue;
      }
      // A widget may briefly own live local input. `false` asks replay to leave this
      // action and later actions for the same widget in order for the next poll.
      // A throw is contained to the event that threw: unretired, it re-throws on
      // every poll, and everything after it in this pass — paintPending, the
      // caught-up stamp the render gate awaits — never runs again. The console
      // error makes it a finding of that gate, the same bargain the import path
      // strikes with failSoft.
      let outcome;
      try {
        outcome = el.applyAction(e.action, e.detail);
      } catch (error) {
        reportPageError(
          `<${el.tagName.toLowerCase()}> applyAction(${e.action}) threw: ${error?.message ?? error}`,
        );
        failSoft(el, error);
        retire(el, e);
        wrote = true;
        continue;
      }
      if (outcome === false) {
        deferredWidgets.add(e.widget);
        continue;
      }
      retire(el, e);
      wrote = true;
    }
    if (!wrote) continue;
    applied = true;
    const now = shallowSigs(document.body);
    // What the pass wrote — the ids whose shallow state its calls changed —
    // recorded on the body, where version check --render reads it. A no-op says the
    // markup already held the state; only a page widget can contradict its
    // version, so a reply's widget (.lf-chrome, no version) goes unrecorded.
    const changed = [...new Set([...before.keys(), ...now.keys()])].filter(
      (id) => before.get(id) !== now.get(id) && !inChrome(elementById(id)),
    );
    if (changed.length) {
      const prior = document.body.getAttribute(wroteAttr)?.split(" ") ?? [];
      document.body.setAttribute(
        wroteAttr,
        [...new Set([...prior, ...changed])].join(" "),
      );
    }
    started.push(...document.getAnimations().filter((a) => !priorMotion.has(a)));
  }
  if (applied) {
    // A replay moves the page's text — a card to another column, a suggestion to its
    // settled slot — so the marks are repainted where they now belong. Said here rather
    // than left to the caller's order: a pass held off by a live drag lands on a poll
    // that has nothing else to re-render.
    paintAnchors();
    // A FLIP a widget starts in applyAction keeps the moved element's hit box over
    // its old home until the motion lands, so the pass above asked what is under the
    // pointer mid-flight. The batch's own animations are the fact to consume — never
    // the document's, whose chrome runs one that has no end — and when the last of
    // them lands, ask again.
    Promise.allSettled(started.map((a) => a.finished)).then(() => pageShifted());
  }
  // Beside paintPending, and outside the `applied` gate above, because the two facts
  // this speaks arrive by different doors: a status a report moved is a widget the pass
  // applied, and a retraction is painted by the pass that *declines* to apply one, which
  // never marks itself as having written. Free to run every poll because the writer is
  // idempotent — it re-reads nothing to whoever is listening unless the word or its seat
  // has actually moved.
  renderQuiet(document.body);
  paintPending();
  // Every action and report in the log is now decided (applied, skipped, or
  // retired), and the stamp says so — it is what version check --render awaits
  // before reading the replay's record, so the gate never reads a page mid-replay.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.applied, String(appliedActions.size));
  logRendered = true;
}

// ---------- decided, awaiting the honoring version ----------
// The registry's x-state names each verb's fold unit and record form, so one
// pass renders "the user decided this and no version has carried it yet"
// for every widget alike — choose had its mark, edit its tint, move nothing,
// and the asymmetry was each widget remembering (or not) on its own. The
// authored facets are captured once per page load, after upgrades and before
// the first replay: the markup's initial condition, which replay then
// overwrites in the DOM.
const authoredFacets = new Map(); // unit id -> the facet this version arrived showing

// Both channels: a report's record form is a facet exactly as an action's is,
// so the authored-facet capture and the diff's state half serve the two alike.
// Named members rather than a tuple, because this list grew one: `verb` arrived for
// the authored capture, and every consumer destructuring by position bound the verb
// where it wanted the spec. Nothing threw — the diff's state half simply read
// `undefined` for every record and marked nothing, which is the silence the render
// gate caught and no reader would have.
function stateSpecs() {
  const specs = [];
  for (const [tag, entry] of widgetEntries())
    for (const channel of ["x-state", "x-report"])
      for (const [verb, spec] of Object.entries(entry[channel] ?? {}))
        specs.push({ tag, channel, verb, spec });
  return specs;
}

// What the page shows for one unit's declared record form, asked of the live
// DOM or of the diff's parsed base document alike. An attribute record is the
// set of elements wearing it — a group taking several picks marks several — so
// both readings collapse to the sorted ids, and comparing them stays a !==.
//
// The id-bearing ones only, because an id is how a member of that set is named
// everywhere else: in the action detail the fold reads back (foldedFacet sorts
// the ids the log carries) and in interact.py's reading of the same page, which
// can see none but those. One marked element without an id contributed an empty
// string that sorted to the front of the join, so a set the two sides agreed on
// came out with a leading space on this one.
function domFacet(el, record) {
  if (record.kind === "attribute")
    return [...el.querySelectorAll(`[${record.attr}]`)]
      .map((o) => o.id)
      .filter(Boolean)
      .sort()
      .join(" ");
  if (record.kind === "value") return el.getAttribute(record.attr);
  if (record.kind === "position") return el.closest(record.within)?.id ?? null;
  return quoteFrom(textNodesUnder(el)); // "body": the words, read the way a quote is
}

// The state the folded action left, from the detail field the record declares,
// collapsed the way the DOM reading collapses — its words where it is words,
// its sorted ids where it is a set.
function foldedFacet(e, record) {
  const value = e.detail[record.value];
  if (record.kind === "body")
    return [
      ...String(value ?? "")
        .replace(COLLAPSE, " ")
        .trim(),
    ].join("");
  if (record.kind === "attribute") return [...value].sort().join(" ");
  return value ?? null;
}

// The same capture read the other way: the detail that *states* each unit's
// authored placement, keyed by the verb that would state it. The facet above is
// what a comparison needs, and it is deliberately lossy — a position collapses to
// its column, a body to its collapsed words — because the log's own detail is
// compared collapsed. Taking a gesture back needs a statement rather than a
// comparison, and the two are different questions about one record: a card put
// back on the right list in the wrong place is the facet's answer, correct and
// useless.
const authoredDetails = new Map(); // "<verb> <unit id>" -> the detail stating it
const authoredKey = (verb, unit) => `${verb} ${unit}`;

// And the markup itself, for the widgets whose state cannot be stated at all: one whose
// x-state declares a verb with no record — a settlement, where "undecided" is a value no
// verb carries. Kept only for those, because a clone is the whole subtree and every
// other widget can be told its state in a sentence.
//
// Taken beside the passage fences and for the same reason, which is that both are
// readings of what the *version* wrote: the moment after the registry lands and before
// the modules import is the only one at which the page holds the author's markup and
// nothing else. A clone taken a moment later is a clone of the upgraded page — the
// injected controls, the marks, and `once`'s own stamp with them — so putting it back
// would put back a widget that had already been upgraded and would never upgrade again.
const authoredMarkup = new Map(); // widget id -> the markup this version wrote
// By tag rather than by verb, because a family declaring two record-less verbs — a
// suggestion's accept and its reject — would otherwise clone every one of its
// instances once per verb and keep the last.
function rememberAuthoredMarkup() {
  const settlements = new Set(
    stateSpecs()
      .filter(({ channel, spec }) => channel === "x-state" && !spec.record)
      .map(({ tag }) => tag),
  );
  for (const tag of settlements)
    for (const widget of document.querySelectorAll(tag))
      if (widget.id) authoredMarkup.set(widget.id, widget.cloneNode(true));
}

// Whether this load has rendered the log onto the page yet, which is the whole of what
// separates the log a page is built from and the news that arrives afterwards.
let logRendered = false;

function captureAuthoredFacets() {
  for (const { tag, channel, verb, spec } of stateSpecs()) {
    if (!spec.record) continue;
    for (const widget of document.querySelectorAll(tag)) {
      if (spec.unit === "widget" || !spec.unit) {
        if (widget.id) rememberAuthored(widget, widget.id, channel, verb, spec);
      } else
        // Per-part units, at the record form's own key: a position facet is
        // carried by the container's direct children (a column's cards), and
        // an id'd element nested inside one — a draft in a card — is not a
        // unit, just a passenger whose `closest()` would echo its carrier's.
        for (const part of widget.querySelectorAll(`${spec.record.within} > [id]`))
          rememberAuthored(part, part.id, channel, verb, spec);
    }
  }
}

// The facet for both channels, because both fold and both are compared against the
// markup (paintPending reads the report fold too). The detail for the reviewer's
// channel alone: it exists to state a gesture back, and a report is not the reader's
// to take back — captured for both, a report verb sharing a name with a state verb
// would take that key from under it.
function rememberAuthored(el, unit, channel, verb, spec) {
  authoredFacets.set(unit, domFacet(el, spec.record));
  if (channel !== "x-state") return;
  const detail = authoredDetail(el, unit, spec);
  if (detail) authoredDetails.set(authoredKey(verb, unit), detail);
}

// Built from the record form alone, so no widget is named here and a twelfth one is
// covered the day it declares. Null where this version's markup states no placement
// at all — an unset scalar, a part standing outside the container its record names —
// and a unit with no authored statement simply has no first gesture to take back.
function authoredDetail(el, unit, spec) {
  const record = spec.record;
  const detail = spec.unit && spec.unit !== "widget" ? { [spec.unit]: unit } : {};
  if (record.kind === "attribute")
    detail[record.value] = [...el.querySelectorAll(`[${record.attr}]`)]
      .map((o) => o.id)
      .filter(Boolean)
      .sort();
  else if (record.kind === "value") {
    const value = el.getAttribute(record.attr);
    if (value === null) return null;
    detail[record.value] = value;
  } else if (record.kind === "body")
    // Uncollapsed, where domFacet collapses: what is being reproduced is the
    // words, and a draft's paragraphs are the whole of the difference. The same
    // walk either way, so the two readings cannot disagree about *which* words
    // are the page's — only about the whitespace between them.
    detail[record.value] = textNodesUnder(el)
      .map((seg) => seg.node.data.slice(seg.start, seg.end))
      .join("");
  else {
    const within = el.closest(record.within);
    if (!within?.id) return null;
    detail[record.value] = within.id;
    // Among the container's id'd children, which is the same list the capture
    // above walks — and the same one a board counts, a column admitting nothing
    // but cards.
    detail[record.order] = [...within.children].filter((c) => c.id).indexOf(el);
  }
  return detail;
}

// The user's standing state as of `upto`: the last surviving action per
// declared unit. Every applyAction is absolute, which is what makes this a
// fold — one linear scan, no replay simulation. Surviving means not under a
// retraction floor keyed on what the action rests on — the same containment
// set replay skips by, so the two can't disagree about what a `restated` took
// back.
// The two folds' shared walk, which is everything about them that is the same:
// the events of one kind inside the window whose widget is still on the page
// and whose tag still declares the verb, each with the unit it folds to. What
// differs is only what each channel counts as ended — a retraction floor for
// the reviewer's, a note's answer for the agent's — so that is the caller's
// `live` predicate and nothing else is duplicated. interact.py's `declared_events`
// owns the same seam on the file side.
// Which element one event states, per the verb's declared fold unit: the widget itself
// where the verb is absolute across the group, and the element its detail names where
// it is absolute per part. One sentence, because two copies of it are two readings of
// the registry free to disagree about what an event is about.
const unitOf = (e, spec) =>
  spec.unit === "widget" || !spec.unit ? e.widget : e.detail[spec.unit];

function* foldable(kind, channel, upto, live) {
  for (const e of events) {
    if (e.kind !== kind || e.version > upto) continue;
    const el = elementById(e.widget);
    // The element, not its module: the fold reads the registry's declaration,
    // so a decided widget whose module failed to load still folds — asking for
    // applyAction here silently dropped its decision from every derived view.
    if (!el || inChrome(el)) continue;
    const spec = registry[el.tagName.toLowerCase()]?.[channel]?.[e.action];
    if (!spec || !live(e, el)) continue;
    const unit = unitOf(e, spec);
    if (typeof unit === "string") yield [unit, { e, spec }];
  }
}

// Two ways an action stops standing, and the fold owes both the same answer: a version
// that rewrote what it rested on (`restated`), and the reader taking it back (`undo`).
// Neither leaves a mark on the action itself — the log is append-only — so both are
// read from what came after it.
function stateFold(upto) {
  const floors = retractionFloors(upto);
  const withdrawn = takenBack();
  return new Map(
    foldable(
      "action",
      "x-state",
      upto,
      (e, el) => !withdrawn.has(e.id) && !retractedIds(e, floors, el).length,
    ),
  );
}

// What stands for one unit with one event left out of the reckoning — the fold, minus
// that event. Every applyAction is absolute, so the last surviving action on a unit
// *is* that unit's state, and there is no replay to simulate. Verbs that record are
// the whole of what it considers, because a verb recording nothing says nothing about
// the unit's markup — a settlement standing between two states is not one of them.
//
// The exclusion is the event's id and not a bound on its seq, because what a page owes
// after a withdrawal is the unit's state *now*, and the two are the same answer only
// while the withdrawn action is still the unit's last word. It need not be: a reader
// presses `z` on the move their tab knows about while another tab has moved the same
// card past it, and nothing at the door can refuse that — recency is not a property an
// event has. Answering with what stood before it *then* paints over the move that
// still stands, in every tab that hears it, and a tab that took that move from replay
// has it marked applied and never lays it down again. By id, the same press replays
// the standing action instead, which is a no-op, as an absolute value always is.
function standingFor(unit, without) {
  const floors = retractionFloors(VNUM);
  const withdrawn = takenBack();
  let found = null;
  for (const [at, entry] of foldable(
    "action",
    "x-state",
    VNUM,
    (e, el) =>
      e.id !== without && !withdrawn.has(e.id) && !retractedIds(e, floors, el).length,
  ))
    if (at === unit && entry.spec.record) found = entry;
  return found;
}

// The agent channel's fold: the last standing report per declared unit as of
// `upto`. Standing means inside the window and not answered by a note there —
// no retraction floors, because a report is not a decision `restated` can take
// back; a note naming it is the one way it ends.
function reportFold(upto) {
  const answered = answeredReports(upto);
  return new Map(foldable("report", "x-report", upto, (e) => !answered.has(e.id)));
}

// What this page's folds hold, handed out so the one premise underneath them can
// be tested from outside: every applyAction is absolute, and neither fold is a
// fold if one isn't. `version check --render` applies each of these a second
// time and asks what moved (RELATIVE_REPLAYS, in interact.py) — the page has
// already replayed them, so a widget stating the whole value has nothing to do
// and one stepping from what it reads moves again.
//
// Both channels, because both fold the same way: a report states an absolute
// value exactly as an action does. The widget rather than the unit, because
// applyAction is the widget's method and the detail is what names the part.
//
// In the log's own order, which is the whole of what makes re-applying them a
// no-op. An absolute applyAction states its unit whole and says nothing about
// any other, so where two units share an ordered container the page is the
// *sequence's* result rather than any one action's: two cards dragged to the
// head of one column leave it holding the second above the first, and replaying
// the first alone lifts it back over the second. Neither implementation moved;
// the reading did. A fold is keyed by unit and a Map keeps each key where it
// first appeared, so the surviving events have to be put back in `seq` order
// rather than taken as the fold hands them over.
//
// The widget and the facet are both read at the call rather than held, because
// an application earlier in the batch is free to have replaced the element a
// later one names. A unit the current version dropped has no facet at all —
// its widget survived it.
export const standingState = () =>
  [...stateFold(VNUM), ...reportFold(VNUM)]
    .sort(([, a], [, b]) => a.e.seq - b.e.seq)
    .map(([unit, { e, spec }]) => ({
      get widget() {
        return elementById(e.widget);
      },
      unit,
      action: e.action,
      detail: e.detail,
      facet: () => {
        const el = spec.record && elementById(unit);
        return el ? domFacet(el, spec.record) : null;
      },
    }));

// ---------- taking a gesture back ----------
// Undo withdraws; it never deletes. The log is append-only and the page is a fold over
// it, so `z` posts one event naming the gesture it takes back, and every fold and the
// thread reading drop that gesture. The page is then the version plus what still
// stands — the same sentence a reload has always read, and the same one `restated`
// already writes from the author's side. Nothing states a counter-gesture into the
// log: a card put back where it came from would read as a decision to move it there,
// and "undecided" is not a value any verb can carry, so a page whose reader takes back
// an accept could never have been stated at all.
//
// What the reader *sees* is derived from that rather than restated, and by the
// cheapest faithful means. Where the log still leaves the unit a state that can be
// stated — a prior action's detail, or the placement this version's markup arrived
// showing — the widget is told it, so the card travels back under the reader's eye and
// keeps its focus. Where the verb records nothing, there is no such state, so the
// widget is rebuilt from the version's own markup and whatever survives is replayed
// onto it. Both routes are chosen by a declaration and neither knows a widget's name.
const takenBack = () => new Set(events.filter((e) => e.undoes).map((e) => e.undoes));
const eventById = (id) => events.find((e) => e.id === id);

// How this action would be taken off the page, or null where it cannot be: the widget
// has gone, its tag no longer declares the verb, or no module is there to answer for
// it. `state` is what to tell the widget; its absence means the rebuild, which is the
// answer for a verb that records nothing — a settlement rather than a state.
// Which version the gesture was made against is not asked here, and that is the whole
// of the difference between offering an undo and hearing one. Offering is the walk's
// (undoable): a later version is free to have been written around the decision, so on
// v2 the authored placement of a card moved on v1 is *where the move put it*, and the
// press would be live and paint nothing. Hearing has no such choice — a tab pinned to
// v1 can still gesture, and its undo reaches a tab reading v2, which applied that
// action and must now take it off. What this load's markup says is the right answer
// there either way: a version written around the decision states the same placement,
// so the restore is a no-op, and one that had not catches up.
function restoreFor(e) {
  const el = elementById(e.widget);
  if (!el || inChrome(el) || !el.applyAction) return null;
  const spec = registry[el.tagName.toLowerCase()]?.["x-state"]?.[e.action];
  if (!spec) return null;
  // Every id'd instance of a record-less tag outside the chrome was cloned before the
  // modules imported, and the three refusals above cover the rest, so the clone is
  // there. A widget minted after that capture would throw in `rebuild` rather than
  // reporting itself as a gesture that cannot be taken back.
  if (!spec.record) return { el };
  const unit = unitOf(e, spec);
  const stands = standingFor(unit, e.id);
  if (stands)
    return { el, state: { action: stands.e.action, detail: stands.e.detail } };
  const detail = authoredDetails.get(authoredKey(e.action, unit));
  return detail ? { el, state: { action: e.action, detail } } : null;
}

// The newest gesture of the reader's own that still stands and can still be taken off
// the page. Newest-first over the whole log rather than a stack this tab keeps,
// because a stack is a second store: it would die on the reload a new version
// performs, and a second tab would hold a different one. The reader's own — an agent's
// `leaf resolve` is not theirs to undo — and never an undo itself, which is what makes
// repeated presses a walk backwards instead of a toggle.
function undoable() {
  const withdrawn = takenBack();
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.author !== "user" || e.kind === "undo" || withdrawn.has(e.id)) continue;
    if (e.kind === "resolve" || e.kind === "unresolve") return e;
    // On the version it was made against: a later version may have been written
    // around the decision, and a press that paints nothing is not one to offer. What
    // *hearing* such an undo owes is restoreFor's, and is not the same answer.
    if (e.kind === "action" && e.version === VNUM && restoreFor(e)) return e;
  }
  return null;
}

// Said in the kinds this file owns, never in the verb the action carries: `move` and
// `edit` read as nouns in that sentence and `choose` does not, and which of the two a
// widget's word is is not core's to know. It is the same rule that keeps "accept" out
// of the answer-all row's words, met here in its smallest form.
const UNDO_WORDS = {
  resolve: "Reopened the thread",
  unresolve: "Resolved the thread again",
  action: "Took back your last change",
};

// This press's own record of being in flight, read by unrecordedGesture with the
// layer's other two.
let undoing = false;

// The press posts and nothing else. What the page does about it is applyActions',
// where it is done once for every tab off the log rather than here for this one off
// the gesture — the second tab has to arrive at the same page, and a route only this
// tab took would be a second answer to converge with. The round trip is the cost, and
// it is the one gesture that can afford it: a drag has to follow the pointer, where a
// keypress has nothing on screen waiting on the frame.
async function undoLast() {
  const e = undoable();
  if (!e) return;
  undoing = true;
  paintKeys();
  try {
    if (await post({ kind: "undo", undoes: e.id }))
      toast(`${UNDO_WORDS[e.kind]} — sent to ${agentName()}`);
  } finally {
    undoing = false;
    paintKeys();
  }
}

// The widget put back as the version wrote it, for the withdrawal no state can state.
// A rebuild rather than an un-apply, because there is no un-apply to call: applyAction
// states a value, and the value here is "whatever the markup says", which only the
// markup holds. The clone is this version's, taken before replay first touched the
// page, so what goes back is exactly what a reload would render before the log is read
// — and the log is then read onto it, the same pass that reads it onto a fresh load.
function rebuild(el) {
  const id = el.id;
  // Whether the reader is standing in what is about to be replaced — inside it, or on
  // a control the widget hoisted out of it — because they have to be handed the place
  // back afterwards. The other route never asks: a widget told its state keeps its own
  // focus, and it was only the rebuild that dropped a reader onto <body> without a
  // word, which is the silence the ladder's own rung exists to avoid.
  const here = focused();
  const standing =
    Boolean(here) &&
    (containsAcross(el, here) || Boolean(here.closest?.(`[${ASK_ROW}="${id}"]`)));
  // Chrome the widget hoisted out of itself goes with it, and the widget is what takes
  // it: a control hung in the page margin is outside the subtree being replaced, so
  // only its owner knows to take it away, and disconnectedCallback is where the
  // platform already asks. Sweeping `[data-lf-for]` here as well would be a second
  // writer for one fact — and one that a widget hoisting chrome under some other
  // marker would silently escape anyway. What holds it is the render gate, where a row
  // left behind shows as two rows on one change.
  const fresh = authoredMarkup.get(id).cloneNode(true);
  // Before the insertion, as the load writes it before the modules import: a widget
  // that declares a width model asks for it on its first render, and connectedCallback
  // is that render.
  markWide(fresh);
  el.replaceWith(fresh); // defined already, so connectedCallback runs on insertion
  // The rest of what the upgrade gives every subtree beyond its module's own work. Not
  // awaited as the upgrade awaits it: nothing is holding a first paint here, and a
  // widget with async work of its own settles it the way it always does.
  dress(fresh);
  reachScrollers(fresh);
  // The fences the passage reading walks are node identities, and these are new nodes
  // holding the same markup — so the index is taken again rather than left naming a
  // subtree the page no longer has.
  rememberPassageParts();
  // Everything this load applied *inside* that widget went with the node, so the
  // surviving log has to land on the new subtree. Its own events and any nested
  // widget's alike: a change may propose markup that holds one — which is how the
  // family says a widget-state change, there being no separate patch shape — and
  // a pick the reader made inside it is theirs, not part of what they took back.
  const inside = new Set(
    [fresh, ...fresh.querySelectorAll("[id]")].map((node) => node.id).filter(Boolean),
  );
  for (const e of events) if (inside.has(e.widget)) appliedActions.delete(e.seq);
  if (standing) standOn(fresh);
}

// data-lf-pending: this element's decided state differs from what the version's
// markup arrived showing — the record is behind the log. It clears when a
// version carries the decision (the two agree again) or a retraction hands the
// state back to the author. A decided suggestion has no record form to agree
// with (honoring retires the wrapper), so it stays marked while the wrapper
// stands.
function paintPending() {
  for (const attr of [PAGE_PAINT_ATTRIBUTE.pending, PAGE_PAINT_ATTRIBUTE.reported])
    for (const el of pageQueryAll(`[${attr}]`)) el.removeAttribute(attr);
  for (const [unit, { e, spec }] of stateFold(VNUM)) {
    const el = elementById(unit);
    if (!el) continue;
    const behind = spec.record
      ? foldedFacet(e, spec.record) !== authoredFacets.get(unit)
      : true;
    if (behind) el.setAttribute(PAGE_PAINT_ATTRIBUTE.pending, "1");
  }
  // The mirror mark, kept apart so a worker's news never wears the user's
  // color: data-lf-reported says this element's state is a standing report the
  // version's markup has not absorbed — provisional until a version answers it,
  // where data-lf-pending says the reader decided and the record lags.
  for (const [unit, { e, spec }] of reportFold(VNUM)) {
    const el = elementById(unit);
    if (!el) continue;
    if (foldedFacet(e, spec.record) !== authoredFacets.get(unit))
      el.setAttribute(PAGE_PAINT_ATTRIBUTE.reported, "1");
  }
}
async function poll() {
  let res;
  try {
    res = await fetch("/api/state");
  } catch {
    // Network absence is a completed answer: there is no log to replay, so the offline
    // authored page is honest. A successful but malformed response is different — let
    // JSON or processing errors escape so the caller retains the recovery boundary.
    res = null;
  }
  const responseGeneration = res?.ok && res.headers.get("Leaf-Layer");
  if (responseGeneration && !sameLayer(responseGeneration)) return;
  // A refusal is not state: the server answers a missing key with error-shaped JSON at
  // 403. A live server refusing the key and a dead one both leave the page unreachable
  // from here, and the terminal link is the recourse for both.
  const state = res?.ok ? await res.json() : null;
  if (!state) {
    if (statePhase === "waiting") statePhase = "offline";
    renderStatus(null);
    if (panelOpen) renderPanel();
    // The sequence consumers still hear the tick. A poll that brought nothing changes
    // no history, so they re-render what they already held — but anything of theirs
    // that reads a clock rather than the log has to keep moving, and a dead server is
    // exactly when it matters: the banner says the server is gone while a roster row
    // froze its "last heard 4m ago" at the moment the answers stopped, which is the
    // authored freshness this widget layer exists to replace, produced by the layer
    // itself. Replay is deliberately not run — there is nothing new to apply.
    document.dispatchEvent(new Event("lf-actions"));
    return;
  }
  return receiveState(state);
}
async function receiveState(state) {
  // Every state this page reads passes here — the poll's, and the one an accepted
  // event response carries — so the generation is checked once for both rather than
  // at each door it arrives through.
  if (!sameLayer(state.layer)) return;
  const nextEvents = state.events;
  const eventSeq = nextEvents.at(-1)?.seq ?? 0;
  // post() and the timer can poll together. The log is append-only, so a response
  // behind one already rendered is unambiguously stale; accepting it would move
  // every event-derived view backwards until the next poll.
  if (eventSeq < lastEventSeq) return;
  // Messages render from Markdown; have the renderer in hand before the panel
  // builds a body, so msgNode stays synchronous.
  if (
    nextEvents.some(
      (e) => e.kind === "comment" || e.kind === "reply" || e.kind === "append",
    )
  )
    await loadMarked();
  events = nextEvents;
  statePhase = "ready";
  settleAcceptedDrafts();
  agent = state.agent || "Claude";
  // Before the panel renders: the streaming caret keys on the same judgment the
  // banner shows, so a growing message and the dot beside it cannot disagree —
  // and a flip repaints the open messages itself, because status can move with
  // no event behind it and the reconcile below only runs when events arrive.
  const wasWorking = agentWorking;
  agentWorking = presented(state).kind === "working";
  if (agentWorking !== wasWorking) paintStreaming();
  renderStatus(state);
  renderVersions(state);
  renderOthers(state);
  if (eventSeq > lastEventSeq) {
    lastEventSeq = eventSeq;
    renderPanel();
    // Sign-off is a fact in the log, not a click this tab happens to remember, so a
    // reload (or the other tab) shows it too.
    paintApproval();
    const agentReplies = events.filter(
      (e) => e.author === "claude" && e.kind === "reply",
    );
    if (agentMsgCount >= 0 && agentReplies.length > agentMsgCount && !panelOpen)
      showToast(`${agentReplies.at(-1).agent || "Agent"} replied — open Comments`, () =>
        setPanel(true),
      );
    agentMsgCount = agentReplies.length;
  }
  // Last, because the panel has just rendered the log: a widget carried by a reply is
  // on the page by now, so an action naming one that isn't names a widget no version
  // holds, and applyActions can retire it instead of looking for it forever.
  applyActions();
  // Sequence consumers render after replay, so their history and the widget's
  // standing body describe the same poll. This also fires when the event list did
  // not grow: applyAction may have deferred while a user was typing, then become
  // applicable on the next poll after they close the editor.
  document.dispatchEvent(new Event("lf-actions"));
}
// ---------- restore ----------
// The general box and reply textareas repopulate as they render; a saved composer draft
// resurfaces visibly near the top so it isn't stranded in storage after a reload.
generalInput.value = loadDraft("general") ?? "";
if (readerStore.get(PANEL_KEY) === "1") setPanel(true);
// Remembered board intent is staged here, after every declaration exists. Its strip is
// part of the arrival geometry, but its state-dependent rows stay hidden until the first
// replay presents the page and restoreEdge paints them. An already-presented document
// (an exported or pre-presented DOM) can restore immediately through the same function.
edgeUp = readerStore.get(EDGE_KEY) || null;
if (edgeUp) document.body.dataset.lfEdge = edgeUp;
if (pagePresented()) restoreEdge();
if (tabStore.get(DESIGN_KEY) === "1") setDesign(true, { spoken: false });
// Every way this page can come up that is not a first visit — the restores above, each
// named by the fact its store holds. The browser gate arrives once in each, because
// every other reading it takes is of a first visit: a fresh context holds nothing, so
// the panel is shut, no board stands and the mode is off. That made the restores the one
// road onto the page with no gate on it, and a board left standing came up as a
// ReferenceError rather than a page — on every load, for the only readers who had asked
// for it. Declared here rather than listed in the gate, because a list over there stops
// at the surfaces it was taught; this one is read on the day a surface starts
// remembering something. One stored fact each rather than the combinations of them: what
// a finding has to name is the restore that broke, and the geometry the combinations
// would add is measured on the first visit already.
export const ARRANGEMENTS = [
  { name: "the comment panel open", ...readerStore.where(PANEL_KEY), value: "1" },
  ...[...edges.keys()].map((board) => ({
    name: `the ${board} board standing`,
    ...readerStore.where(EDGE_KEY),
    value: board,
  })),
  { name: "design mode on", ...tabStore.where(DESIGN_KEY), value: "1" },
];
// Where the reader stands, which is the half of an arrival the browser cannot answer on
// a page that moves its own scrolling: `html` is `overflow: hidden` so the document
// scrolls in `body`, and the browser scrolls whichever box it last saw the reader put
// themselves in — on a fresh load, none of them, so Space, PageDown and the arrows did
// nothing at all until the reader happened to click somewhere in the page. Literally the
// move the Escape ladder makes of letting go, since an arrival and a reader who has just
// put something down are standing in the same place; `letGo` carries the reasons, the
// focus rather than a blur among them, and CLAUDE.md's "The reader has to be standing
// somewhere" holds the rest.
//
// Here rather than in the start block below, which runs asynchronous upgrades with the
// chrome clickable throughout: a reader who took a control in that window would have it
// taken back off them. Main is withheld from paint, but body is the visible scroll box and
// can name itself to Chrome now.
letGo();
// Where an arrival lands — version switch, reload, back, a URL naming an element (the
// panel and a remembered board's strip are restored just above, so the column is already
// reflowed; the board's pixels wait for replay). The browser answers
// this twice, and both answers are taken before the page is done becoming itself:
// upgrades change its height afterwards (tabs collapse, diagrams render, diff files
// fold), so a restored offset points into a document that no longer exists and a
// fragment jump lands at an element a tab has since closed over. Hence manual
// restoration, and hence the fragment travelling the same road — that was the half of
// this takeover left to the platform, which cannot see the page the upgrade makes.
//
// The ranking is the browser's own, restated once the geometry has settled. A fresh
// navigation is someone arriving at a named place, so the fragment outranks the saved
// position: that position is wherever this tab last left this page, and a URL naming an
// element is not a request to resume it. A reload or a back is someone returning, where
// the fragment is left over from a reference followed earlier and their own position is
// the answer. An id this version hasn't got falls through to that position, the same way
// a reference naming one paints detached rather than dead-ending.
history.scrollRestoration = "manual";
const ARRIVING = performance.getEntriesByType("navigation")[0]?.type === "navigate";
// Parsed inside its own guard, which is a different question from whether the store
// answered: tabStore hands back null for a store that refused, and what a page wrote
// there is only JSON while every version of this runtime agrees about the shape. A
// landmark that no longer parses costs the reader their scroll position; throwing here
// would cost them the page, at module top level, with nothing else having run.
const savedView = (() => {
  try {
    return JSON.parse(tabStore.get(VIEW_KEY) || "null");
  } catch {
    return null;
  }
})();
addEventListener("pagehide", () => {
  if (!anchoringReady) return;
  tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
});
function landArrival() {
  const aimed =
    ARRIVING && resolveAnchor({ section: fragmentId(location.hash) })?.element;
  if (aimed) scrollToElement(aimed, "instant");
  else if (savedView) restoreView(savedView);
}
const savedComposer = pendingComposer();

// ---------- start ----------
const PRESENTATION_WAIT_ANIMATION = "lf-presentation-wait";
const cssMilliseconds = (name) => {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (value.endsWith("ms")) return Number(value.slice(0, -2));
  if (value.endsWith("s")) return Number(value.slice(0, -1)) * 1000;
  return Number(value);
};

// One positive fact for the one presentation boundary. Success has applied the log;
// an unavailable first poll has painted the offline status and deliberately hands the
// authored page back. A caught startup failure cannot make that promise, so it leaves
// the fixed recovery surface in place rather than exposing decisions it never read. A
// fast answer releases before the delayed waiting surface can paint. Once that surface
// has started, its CSS animation is the clock and the CSS dwell is the budget: the message
// stays long enough to read instead of becoming the flash it was meant to prevent.
async function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  const wait = document
    .getAnimations()
    .find((animation) => animation.animationName === PRESENTATION_WAIT_ANIMATION);
  const current = Number(wait?.currentTime);
  const delay = Number(wait?.effect.getTiming().delay);
  if (wait && Number.isFinite(current) && current >= delay) {
    const shownAt = (wait.startTime ?? document.timeline.currentTime - current) + delay;
    const releaseAt = shownAt + cssMilliseconds("--lf-presentation-dwell");
    // Timers are a wake-up hint, not the presentation clock: a browser may service one
    // a few milliseconds before its requested deadline. Re-read the CSS timeline after
    // every wake so the recovery message never loses the end of its promised dwell.
    while (document.timeline.currentTime < releaseAt) {
      await new Promise((resolve) =>
        setTimeout(resolve, releaseAt - document.timeline.currentTime),
      );
    }
  }
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.presented, "1");
  // Repaint state-dependent chrome in this same task. The presentation attribute opens
  // the gate, replay is already complete, and no frame can expose the authored count or
  // an empty persisted board between those facts.
  restoreEdge();
  showNews(othersBtn, boardOffered());
  syncAsks();
  paintApproval();
  promoteDeferredModals();
}

// Upgrades flush before the anchor pass and the view restore, so quotes and reading
// positions are re-found in the enhanced DOM, not the pre-upgrade one. An async function,
// never a top-level await: widget modules import this module's helpers, and awaiting their
// import at top level would deadlock the cycle (their evaluation waits on this module's
// async evaluation completing).
async function startPage() {
  await Promise.all([
    upgradeWidgets(),
    // Alongside rather than after, and caught rather than fatal: the tab icon is not
    // what the page is for, so a layer missing it says so in the console and leaves the
    // rest working — the same bargain a widget module that fails to import makes. It is
    // still awaited here, because `version export` copies the page at the stamp below
    // and a mark that arrived after it would leave the copy's tab to chance.
    loadIcon().catch((err) => console.error(err)),
  ]);
  // The box the page ends up with is not the one it started in, because a module may
  // change it while upgrading: a page with a change to decide gives up a rail of the
  // controls' own width, and lf-suggestion states that from the first row it builds,
  // which is long after the layout first ran. Every reader of the box is therefore
  // re-run here rather than left holding the pre-upgrade one — the room a wide widget
  // spends was the one that noticed, standing a diagram out over the rail on the first
  // shipped page to carry both.
  //
  // The observer watches that box now, so the standing answer is not this line's. What
  // is this line's is the timing: an observation is answered at the next rendering
  // update, which is a frame past the stamp below, and the stamp is where `version check
  // --render` and an exported copy read the page. So the observer keeps the room true for
  // the page's life and this makes it true at the moment the page is called finished,
  // which is what test_the_room_is_measured_after_a_late_rail holds it to. The strip is
  // stated first, being padding on the box the room comes off.
  stateStrip();
  syncLayout();
  // Before the first poll's replay: the authored facets are the markup's
  // initial condition, and replay is about to overwrite them in the DOM.
  captureAuthoredFacets();
  buildBulkAnswers();
  syncAsks();
  anchoringReady = true;
  paintAnchors(); // an early general post may already have loaded anchored threads
  updateFab(); // an early selection is now read from the fully upgraded page
  paintHere(); // c is live again, whether or not that selection raised the button
  landArrival();
  if (savedView && savedView.v < VNUM) showToast(`Updated to v${VNUM}`);
  if (savedComposer)
    openComposer(
      savedComposer.anchor,
      savedComposer.text,
      (innerWidth - 320) / 2,
      64,
      Boolean(savedComposer.suggest),
      savedComposer.about ?? null,
    );
  // Start replay before stamping the document, preserving the two readiness facts, but
  // present neither half on its own. The first completed read — state or offline — is the
  // presentation boundary; only after it settles does the ordinary polling cadence begin,
  // so a held first request cannot be overtaken by a second answer and leave presentation
  // waiting on the wrong call.
  let presentationAttempt;
  const ensurePresentation = () => {
    if (!presentationAttempt)
      presentationAttempt = presentPage().finally(() => {
        presentationAttempt = null;
      });
    return presentationAttempt;
  };
  const pollAndPresent = async () => {
    try {
      await poll();
      if (!document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented))
        await ensurePresentation();
    } catch (error) {
      reportPageError(`poll failed: ${error?.message ?? error}`);
      renderStatus(error);
    }
  };
  pollAndPresent().finally(() => setInterval(pollAndPresent, POLL_MS));
  // Every widget has upgraded and every async one has settled, so the geometry and
  // the drawn SVG are final. `version export` copies the page at this moment and has no
  // other way to know it arrived: a load event fires before the modules run, and
  // networkidle only says a bundle finished downloading, not that it finished
  // drawing. The stamp says the document is done becoming itself.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. The fixed recovery surface stays in front:
  // this failure happened before the log was read, so the authored decisions underneath
  // are not an honest page to release.
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
