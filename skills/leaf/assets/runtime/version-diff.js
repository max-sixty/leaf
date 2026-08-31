import { runtime } from "./context.js";
import { registry, stateSpecs, tagsDeclaring } from "./registry.js";
import { versionUrl } from "./storage.js";

export function createVersionDiff({
  chooserLabel,
  domFacet,
  elementById,
  inChrome,
  quoted,
  projectionFromView,
  sameLayer,
  showToast,
  stateCoordinate,
  textBlockSelector,
  versionBtn,
  versionLabel,
  versionMenu,
  wrote,
}) {
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
      textBlockSelector(),
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
      // External data is absent from both authored documents. Its seat is opaque, and
      // the authored binding and immutable selector below are the comparison key.
      ...tagsDeclaring((e) => e["x-upgrade"] && e["x-data"]),
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
      const entry = registry[w.localName] ?? {};
      // A data selection is authored semantics even though the generated children
      // of an upgraded widget are opaque to comparison.
      const bindingAttrs = new Set();
      for (const input of Object.values(entry["x-data"] ?? {})) {
        bindingAttrs.add(input.source);
        if (input.snapshot) bindingAttrs.add(input.snapshot);
      }
      const binding = [...bindingAttrs]
        .sort()
        .map((attr) => [attr, w.getAttribute(attr)]);
      pairs.push([w, ` ${w.tagName}#${w.id}${JSON.stringify(binding)}`]);
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
  async function baseReading(baseRevision, throughSeq) {
    const params = new URLSearchParams({
      revision: String(baseRevision),
      through_seq: String(throughSeq),
    });
    const res = await fetch(`/api/view?${params}`);
    if (!res.ok) throw new Error(`couldn't project revision r${baseRevision}`);
    const generation = res.headers.get("Leaf-Layer");
    if (generation && !sameLayer(generation)) return null;
    const answer = await res.json();
    if (!answer.browser) throw new Error(`revision r${baseRevision} has no projection`);
    return answer.browser;
  }
  function applyDiff(doc, baseVersion, baseReading) {
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
    const baseRevision = runtime.versions.find(
      (candidate) => candidate.version === baseVersion,
    )?.revision;
    if (baseRevision == null)
      throw new Error(`version v${baseVersion} has no revision`);
    const baseView = baseReading?.views?.[String(baseRevision)];
    if (!baseView) throw new Error(`revision r${baseRevision} has no projection`);
    const baseProjection = projectionFromView(baseView, baseReading.conversation);
    for (const { tag, spec } of stateSpecs()) {
      if (!spec.record || spec.record.kind === "body") continue;
      for (const widget of document.body.querySelectorAll(tag)) {
        if (inChrome(widget) || quoted(widget)) continue;
        const units =
          spec.unit === "widget"
            ? widget.id
              ? [widget]
              : []
            : [...widget.querySelectorAll(`${spec.record.within} > [id]`)];
        for (const el of units) {
          const baseEl = doc.getElementById(el.id);
          if (!baseEl) continue; // new to this version: the content half marks it
          // A reader's action outranks provisional agent news on the same fact;
          // otherwise the standing writer is the report. The facet coordinate
          // means an unrelated fact on this unit never enters the choice.
          const coordinate = stateCoordinate(widget.id, el.id, spec);
          const writer = baseProjection.desired.get(coordinate);
          const before = writer ? writer.value : domFacet(baseEl, spec.record);
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
    return diffMarked.length;
  }
  // Whether a stamped version can be compared with the revision being read: any stamp
  // on an earlier revision, which is which rows the menu builds a press onto.
  const comparable = (version) => {
    const base = runtime.versions.find((candidate) => candidate.version === version);
    return (
      runtime.currentRevision !== null &&
      base !== undefined &&
      base.revision < runtime.currentRevision
    );
  };
  // Every rendering of the pair above, written in one place: the chooser's word, its
  // paint and what it says it will do, the checked state of each row's Δ, and the rail
  // down the rows the comparison spans. Called by the setter, by a menu rebuild — the
  // other thing that can leave a rendering behind the state — and once at load, so what
  // the chooser says it will do is written here from the start rather than standing as a
  // second copy of these sentences up where the control is built.
  function paintDiff() {
    versionBtn.textContent = versionLabel(diffOn);
    versionBtn.classList.toggle("on", diffOn);
    const currentLabel = runtime.currentLabel ?? "Draft";
    // Rewritten on every diff change, so the key it names is taken from the row each time
    // rather than typed into one of the two branches and forgotten in the other. The
    // closed face is deliberately compact, so its hover and accessible name keep the
    // full draft-after-version context that the open menu also spells out.
    versionBtn.dataset.lfKeyTitle = diffOn
      ? `${currentLabel}: showing what changed since v${diffBase} — pick a version, or press its Δ again to stop`
      : `${currentLabel}: versions; read one, or mark what changed since it`;
    versionBtn.setAttribute(
      "aria-label",
      diffOn
        ? `${currentLabel}: comparing with v${diffBase}; open versions`
        : `${currentLabel}: open versions`,
    );
    const shortcut = chooserLabel();
    versionBtn.title =
      versionBtn.dataset.lfKeyTitle + (shortcut ? ` (${shortcut})` : "");
    for (const row of versionMenu.querySelectorAll(".lf-version-row")) {
      const revision = +row.dataset.lfRevision;
      const baseRevision = runtime.versions.find(
        (candidate) => candidate.version === diffBase,
      )?.revision;
      row.classList.toggle(
        "lf-compared",
        diffOn &&
          baseRevision !== undefined &&
          revision >= baseRevision &&
          revision <= runtime.currentRevision,
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
    }
    paintDiff();
    // Consumers read the settled comparison projection: on/off and its marks move
    // together, rather than announcing an applied DOM diff before it is standing.
    document.dispatchEvent(new CustomEvent("lf-comparison"));
  }
  // The one way a comparison starts, from a row's press or from the walk through the menu.
  // It states a base rather than toggling one — the toggle is a press's own reading of it,
  // and the walk has none to spend, standing on a row being what makes it the base however
  // many times the reader arrives there.
  async function showComparison(base) {
    const mine = ++diffRequest;
    const baseRevision = runtime.versions.find(
      (candidate) => candidate.version === base,
    )?.revision;
    if (baseRevision == null) {
      showToast(`Couldn't load v${base}`);
      return;
    }
    const documentRequest = baseDocument(base);
    let doc;
    let reading;
    try {
      while (mine === diffRequest) {
        const throughSeq = runtime.view?.basis?.through_seq;
        if (!Number.isInteger(throughSeq))
          throw new Error("the current reading has no log sequence");
        [doc, reading] = await Promise.all([
          documentRequest,
          baseReading(baseRevision, throughSeq),
        ]);
        if (reading === null || mine !== diffRequest) return;
        if (runtime.view?.basis?.through_seq === throughSeq) break;
      }
    } catch {
      showToast(`Couldn't load v${base}`);
      return;
    }
    if (mine !== diffRequest) return;
    if (diffOn) setDiff(false); // the old base's marks, before the new base's land
    const n = applyDiff(doc, base, reading);
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

  const comparisonBase = () => (diffOn ? diffBase : null);
  const comparisonChanges = () => (diffOn ? [...diffMarked] : []);
  return {
    comparable,
    comparisonBase,
    comparisonChanges,
    paintDiff,
    pressComparison,
    setDiff,
    showComparison,
  };
}
