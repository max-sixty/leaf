/*
 * Where words stand on their lines, for `leaf-dev stills` (`baseline_changes`).
 *
 * Words set in different faces and centred in boxes of their own stand on different
 * baselines, the larger lower, and a reader beside them sees the line step. Such boxes
 * are the items of flex rows and of grids of more than one column, subgrids included,
 * and boxes placed out of flow, as a notice anchored beside a head is. So in the
 * document and its open shadow trees, this reads each such box that holds one line of
 * words, by its first words a screen reader alone doesn't read, outside SVG; an item
 * that is itself a row stands by its own items. Boxes whose words share a line, each
 * one's words reaching the middle of the other's, and stand within eight ems of each
 * other, read as one run. The eye doesn't hold a pane of many lines, or a word across
 * the row, to its neighbour's baseline: in the stills catalogue, words read together,
 * as a name and its time or a legend and the radio choice after it, stood three ems
 * apart or less, and words at a row's two ends, as the floating panel's field and its
 * count, thirty or more. Words in two rows share a line only where one row stands in
 * the other, as a head's time row in the head, so two cards side by side are two lines;
 * and words in a box fixed over the page, or in the top layer, share no line with words
 * outside it, which it may cover. For each
 * run whose words stand at least `threshold` CSS px apart it returns each box's words,
 * face, baseline against the run's first, and whether they sit on a fill, border or
 * shadow of their own, as a pill's do, whose box the eye reads rather than their
 * baseline.
 *
 * A run of words' box stands a fixed ascent above its baseline, scaled as the page
 * scales the words. That ascent is read from a zero-size inline-block on the baseline
 * of a sample of the same words in the same face, set outside the page in a shadow
 * root of its own, so the page's rules don't restyle the sample and the words measured
 * are never touched: wrapping them would expose them to the page's rules and drop a
 * selection in them. Each run says which of the runs alike in their row and words it
 * is (`nth`).
 */
(threshold) => {
  const roots = [document];
  for (let i = 0; i < roots.length; i++)
    for (const el of roots[i].querySelectorAll("*"))
      if (el.shadowRoot) roots.push(el.shadowRoot);
  const shown = (el) =>
    el.checkVisibility({ visibilityProperty: true, opacityProperty: true });
  const up = (e) => e.parentElement ?? e.getRootNode().host;
  // Words a screen reader alone reads stand under a clip; words placed out of their
  // item's flow stand on a line of their own.
  const drawn = (node, item) => {
    for (let e = node.parentElement; e && e !== item.parentNode; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.clipPath !== "none" || s.clip !== "auto") return false;
      if (e !== item && /absolute|fixed/.test(s.position)) return false;
    }
    return true;
  };
  // Two runs of words share a line when one's middle stands within the other.
  const reaches = (a, b) => {
    const middle = (a.top + a.bottom) / 2;
    return middle > b.top && middle < b.bottom;
  };
  // Where a run of words shows across the line: its fragments on the line of `box`,
  // cut to each box between it and `item` that clips what overflows it, as a name cut
  // with an ellipsis is.
  const across = (node, item, box) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    let left = Infinity;
    let right = -Infinity;
    for (const rect of range.getClientRects())
      if (rect.width && (reaches(rect, box) || reaches(box, rect))) {
        left = Math.min(left, rect.left);
        right = Math.max(right, rect.right);
      }
    for (let e = node.parentElement; e && e !== item.parentNode; e = e.parentElement)
      if (getComputedStyle(e).overflowX !== "visible") {
        const clip = e.getBoundingClientRect();
        left = Math.max(left, clip.left);
        right = Math.min(right, clip.right);
      }
    return { left, right };
  };
  const wordsOf = (node, item) => {
    if (!node.data.trim()) return null;
    const parent = node.parentElement;
    if (!parent || parent.closest("svg") || !shown(parent) || !drawn(node, item))
      return null;
    const range = document.createRange();
    range.selectNodeContents(node);
    const box = range.getClientRects()[0];
    return box?.width ? { node, box } : null;
  };
  // An item that holds one line of words: its first words, and where the words on that
  // line start and end, which a box stretched across the row, or a field wider than its
  // words, does not say.
  const lineOf = (item) => {
    const walker = document.createTreeWalker(item, NodeFilter.SHOW_TEXT);
    let words = null;
    for (let node = walker.currentNode; node && !words; node = walker.nextNode())
      if (node.nodeType === Node.TEXT_NODE) words = wordsOf(node, item);
    if (!words) return null;
    const whole = document.createRange();
    whole.selectNodeContents(item);
    const area =
      item === words.node
        ? whole.getBoundingClientRect()
        : item.getBoundingClientRect();
    if (area.height >= 2 * words.box.height) return null;
    const edge = across(words.node, item, words.box);
    for (let node = walker.currentNode; node; node = walker.nextNode()) {
      if (node.nodeType !== Node.TEXT_NODE || !node.data.trim()) continue;
      if (!shown(node.parentElement) || !drawn(node, item)) continue;
      const more = across(node, item, words.box);
      edge.left = Math.min(edge.left, more.left);
      edge.right = Math.max(edge.right, more.right);
    }
    return { ...words, edge };
  };
  const boxed = (item, node) => {
    for (let e = node.parentElement; e && item.contains(e); e = e.parentElement) {
      const s = getComputedStyle(e);
      const border = ["Top", "Right", "Bottom", "Left"].some(
        (side) =>
          parseFloat(s[`border${side}Width`]) > 0 && s[`border${side}Style`] !== "none",
      );
      if (s.backgroundColor !== "rgba(0, 0, 0, 0)" || border || s.boxShadow !== "none")
        return true;
    }
    return false;
  };
  // The box that stays put over the page around an element, or the document.
  const layer = (el) => {
    for (let e = el; e; e = up(e))
      if (
        getComputedStyle(e).position === "fixed" ||
        e.matches(":modal, :popover-open")
      )
        return e;
    return document;
  };
  const label = (el) => {
    const parts = [];
    for (let e = el; e && parts.length < 4; e = up(e))
      parts.unshift(
        e.localName +
          (e.id
            ? `#${e.id}`
            : [...e.classList]
                .slice(0, 2)
                .map((c) => `.${c}`)
                .join("")),
      );
    return parts.join(" > ");
  };
  const common = (a, b) => {
    const above = new Set();
    for (let e = a; e; e = up(e)) above.add(e);
    for (let e = b; e; e = up(e)) if (above.has(e)) return e;
    return null;
  };
  // A grid of one column, or of one column and empty ones, stacks its items, as a flex
  // column does; a subgrid lays its items in its parent's columns.
  const columns = (el, style) =>
    style.gridTemplateColumns.startsWith("subgrid")
      ? columns(up(el), getComputedStyle(up(el)))
      : (style.gridTemplateColumns.match(/[\d.]+px/g) ?? []).filter(
          (width) => parseFloat(width) > 0,
        ).length;
  const isRow = (el, style) =>
    /grid/.test(style.display)
      ? columns(el, style) > 1
      : /flex/.test(style.display) && style.flexDirection.startsWith("row");
  // Each item a flex row or grid places, and each box placed out of flow, which can
  // stand beside another's words, by its first words. An item that is itself a row
  // stands by its own items.
  const items = new Map();
  for (const root of roots)
    for (const box of root.querySelectorAll("*")) {
      const style = getComputedStyle(box);
      const row = isRow(box, style);
      const placed = /absolute|fixed/.test(style.position) && !row ? [box] : [];
      for (const item of [...placed, ...(row ? box.childNodes : [])]) {
        if (item.nodeType === Node.ELEMENT_NODE) {
          if (isRow(item, getComputedStyle(item))) continue;
        } else if (item.nodeType !== Node.TEXT_NODE) continue;
        const words = lineOf(item);
        if (!words || items.has(words.node)) continue;
        if (words.box.bottom < 0 || words.box.top > innerHeight) continue;
        const owner = item.nodeType === Node.ELEMENT_NODE ? item : item.parentElement;
        const face = getComputedStyle(words.node.parentElement);
        items.set(words.node, {
          ...words,
          owner,
          row: item === box ? null : box,
          layer: layer(owner),
          face,
          size: parseFloat(face.fontSize),
          text: words.node.data.trim().slice(0, 24),
          boxed: item.nodeType === Node.ELEMENT_NODE && boxed(item, words.node),
        });
      }
    }
  // Words in two rows share a line only where one row stands inside the other, as a
  // head's time row inside the head; two cards side by side are two lines. Words in a
  // box placed out of flow, such as a notice anchored beside a head, join the line they
  // stand beside.
  const within = (outer, inner) => {
    for (let e = inner; e; e = up(e)) if (e === outer) return true;
    return false;
  };
  const placedAround = (el) => {
    for (let e = el; e; e = up(e))
      if (getComputedStyle(e).position === "absolute") return e;
    return null;
  };
  const beside = (a, b) => {
    const placed = placedAround(a);
    return placed !== null && !within(placed, b);
  };
  const related = (a, b) =>
    !a || !b || within(a, b) || within(b, a) || beside(a, b) || beside(b, a);
  const shared = [];
  for (const it of [...items.values()].sort((a, b) => a.box.top - b.box.top)) {
    const line = shared.find(
      ([seed]) =>
        seed.layer === it.layer &&
        (reaches(it.box, seed.box) || reaches(seed.box, it.box)),
    );
    if (line) line.push(it);
    else shared.push([it]);
  }
  const lines = [];
  for (const line of shared) {
    line.sort((a, b) => a.edge.left - b.edge.left);
    let run = [line[0]];
    for (const it of [...line.slice(1), null]) {
      const last = run.at(-1);
      const gap = it && it.edge.left - last.edge.right;
      if (
        it &&
        gap > -1 &&
        gap <= 8 * Math.max(it.size, last.size) &&
        related(it.row, last.row)
      ) {
        run.push(it);
        continue;
      }
      if (run.length > 1) {
        const row = label(run.map((r) => r.owner).reduce(common));
        // Which of the runs alike in their row and words this is, counted over every
        // run, split or not, so a report can tell two rows that read alike apart.
        const alike = JSON.stringify([row, ...run.map((r) => r.text)]);
        const nth = lines.filter((line) => line.alike === alike).length;
        lines.push({ row, alike, nth, items: run });
      }
      run = [it];
    }
  }
  // Each run's ascent and box height, from a sample of the same words in the same face
  // outside the page, read as the run is, in a shadow root of its own so the page's
  // rules don't restyle it. A glyph another font supplies, such as an emoji, can change
  // the box, so the sample holds the run's own words. The samples go in together and
  // are read together, so the page lays out once more.
  const host = document.createElement("div");
  host.style.cssText = "all:initial;position:fixed;left:-10000px;top:0";
  const sampled = host.attachShadow({ mode: "open" });
  const samples = new Map();
  const sampleOf = (it) => {
    const { face } = it;
    const key = JSON.stringify([
      face.fontStyle,
      face.fontVariantCaps,
      face.fontWeight,
      face.fontStretch,
      face.fontSize,
      face.fontFamily,
      it.node.data,
    ]);
    if (!samples.has(key)) {
      const sample = document.createElement("div");
      sample.style.cssText = "white-space:nowrap;line-height:normal";
      Object.assign(sample.style, {
        fontStyle: face.fontStyle,
        fontVariantCaps: face.fontVariantCaps,
        fontWeight: face.fontWeight,
        fontStretch: face.fontStretch,
        fontSize: face.fontSize,
        fontFamily: face.fontFamily,
      });
      const words = document.createTextNode(it.node.data.trim());
      const mark = document.createElement("span");
      mark.style.cssText =
        "display:inline-block;width:0;height:0;vertical-align:baseline";
      sample.append(mark, words);
      sampled.append(sample);
      samples.set(key, { words, mark });
    }
    return samples.get(key);
  };
  const runs = lines.map((line) => line.items.map(sampleOf));
  document.documentElement.append(host);
  // A run's box stands its ascent above its baseline, scaled as its page scales it.
  const measured = lines.map((line, l) =>
    line.items.map((it, i) => {
      const { words, mark } = runs[l][i];
      const range = document.createRange();
      range.selectNodeContents(words);
      const box = range.getClientRects()[0];
      const ascent = mark.getBoundingClientRect().top - box.top;
      return it.box.top + ascent * (it.box.height / box.height);
    }),
  );
  host.remove();
  return lines.flatMap(({ row, nth, items: run }, l) => {
    const ys = measured[l];
    const spread = Math.max(...ys) - Math.min(...ys);
    if (spread < threshold) return [];
    return [
      {
        row,
        nth,
        spread: +spread.toFixed(2),
        items: run.map((it, i) => ({
          text: it.text,
          face: [
            it.face.fontStyle,
            it.face.fontWeight,
            `${it.face.fontSize}/${it.face.lineHeight}`,
          ]
            .filter((part) => part !== "normal")
            .join(" "),
          boxed: it.boxed,
          offset: +(ys[i] - ys[0]).toFixed(2),
        })),
      },
    ];
  });
};
