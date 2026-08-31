let publishedProjectData;
export { publishedProjectData as projectData };

export function createDataProjection({ paintAnchors, setChildren }) {
  // Runtime-supplied data is a third kind of page word: it is neither prose the author
  // put in the version nor apparatus the runtime asks the reader to operate. It belongs
  // in `says` because the reader can point at it, and not in `wrote` because no version
  // contains it. `projectData` states both facts on each rendered datum: data-lf-gen keeps
  // it out of the authored reading, while data-lf-projection + data-lf-datum give it a
  // logical identity that survives a renderer replacing its nodes.
  //
  // The source is the authored seat's id and the key is local to that seat. Keeping the
  // pair in the DOM, rather than in a map beside it, preserves the document + log as the
  // whole state model: records remain the caller's input, and this function owns only their
  // current rendering. A module supplies fresh records on every call. `render` receives the
  // prior node for the same key so an ordinary update can preserve focus and selection, but
  // returning a replacement is valid—the anchor follows the key, not node identity.
  //
  // One projection owns all children of its root. Keys are required strings rather than
  // coerced values: `1` and `"1"` becoming the same DOM attribute would silently merge two
  // facts. The helper reconciles order without reinserting nodes already in place, then
  // schedules the one shared anchor pass after the caller's synchronous projection work.
  let dataPaintQueued = false;
  function projectionChanged() {
    if (dataPaintQueued) return;
    dataPaintQueued = true;
    queueMicrotask(() => {
      dataPaintQueued = false;
      paintAnchors();
    });
  }

  function projectData(root, records, keyOf, render) {
    if (!(root instanceof Element))
      throw new TypeError("projectData root must be an element");
    if (!root.id)
      throw new TypeError("projectData root needs an id to name its projection");
    if (!records?.[Symbol.iterator])
      throw new TypeError("projectData records must be iterable");
    if (typeof keyOf !== "function" || typeof render !== "function")
      throw new TypeError("projectData needs key and render functions");

    const prior = new Map();
    for (const child of root.children) {
      if (
        child.dataset.lfProjection !== root.id ||
        !child.hasAttribute("data-lf-datum")
      )
        continue;
      const key = child.dataset.lfDatum;
      if (prior.has(key))
        throw new Error(`projectData(${root.id}) already renders duplicate key ${key}`);
      prior.set(key, child);
    }

    const keys = new Set();
    const nodes = new Set();
    const wanted = [];
    let index = 0;
    for (const record of records) {
      const key = keyOf(record, index);
      if (typeof key !== "string" || !key)
        throw new TypeError(
          `projectData(${root.id}) key ${index} must be a non-empty string`,
        );
      if (keys.has(key))
        throw new Error(`projectData(${root.id}) received duplicate key ${key}`);
      keys.add(key);
      const node = render(record, prior.get(key) ?? null, index);
      if (!(node instanceof Element))
        throw new TypeError(
          `projectData(${root.id}) render(${key}) returned no element`,
        );
      if (node === root || nodes.has(node))
        throw new Error(
          `projectData(${root.id}) render reused the node for key ${key}`,
        );
      nodes.add(node);
      node.dataset.lfGen = "1";
      node.dataset.lfProjection = root.id;
      node.dataset.lfDatum = key;
      wanted.push(node);
      index++;
    }

    // A projection's children are its rendering. Remove source whitespace or an old
    // non-element rendering first, then use the runtime's stable-child reconciler so a
    // node already in the right place is not detached and reinserted.
    for (const child of [...root.childNodes])
      if (child.nodeType !== Node.ELEMENT_NODE) child.remove();
    setChildren(root, wanted);
    projectionChanged();
    return wanted;
  }

  publishedProjectData = projectData;
}
