/* Document-local input vocabulary and intent clock, shared by early delivery and
   portable widgets. This source is both inlined before prepaint and imported by
   modules. One per-document slot keeps the first clock and its listeners when the
   module graph arrives; a plain host starts it with its first portable import. */
(() => {
  const key = Symbol.for("leaf.inputs");
  if (Reflect.has(window, key)) return;
  // Inputs belong to this document from its first script, even while the module
  // graph is still loading. Delayed arrival work must not take focus or scroll
  // back from someone already using the authored page. focus.js exposes this
  // same counter and subscription after startup; no later listener starts over.
  let inputs = 0;
  // The steps Back or Forward among them, which move the user to another entry rather
  // than within the one they are on (history.js).
  let steps = 0;
  // While a reload Leaf asked for hands a place back, a key the bootstrap holds acts
  // only once the hold replays it, so until then it is no input, and the hand-back it
  // waits for is not superseded by it. The hold hears of every input the clock does
  // count, a step Back or Forward included (`counted`), each of which ends the
  // hand-back the held keys were typed for (bootstrap.js, `holdEarlyKeys`).
  /** @type {Parameters<DocumentInputs["holdKeys"]>[0]} */
  let hold = null;
  /** @type {Set<(event: Event) => void>} */
  const inputReaders = new Set();
  // The controls the user has changed in this document (`edited`), whose state a
  // reload's arrival leaves as they left it (version.js, `installArrival`): a field or
  // box a trusted `input` came from, and a disclosure whose summary took a trusted
  // `click`, which the browser fires for a press, a tap or a key that activates it, and
  // for no right-click or cancelled press. A control in an exclusive group counts as
  // changed where the user changed any member, since HTML keeps the group to one
  // choice and restoring one member would undo theirs: radios of one name in one form,
  // or in one tree where they have none, and disclosures of one name in one tree. A
  // page's own script makes no trusted input, so a value it writes reads as its own,
  // even one written in answer to the user, as a script that takes their paste and
  // writes it itself does, and so does a disclosure find-in-page opens. Two more
  // readings stand by what they cost: a click on a control inside a summary marks its
  // disclosure, and its group, though nothing toggled, which needs such a control and a
  // press during a start; and a form's native Reset is no change, so the arrival puts
  // back words in the fields the user didn't touch, where they see them come back.
  /** @type {WeakSet<Element>} */
  const changed = new WeakSet();
  /** @type {WeakMap<Node, Set<string>>} */
  const changedGroups = new WeakMap();
  // The exclusive group `node` stands in, as its scope and its kind and name.
  /** @param {Element} node @returns {[Node, string] | null} */
  const groupOf = (node) => {
    if (node instanceof HTMLInputElement && node.type === "radio" && node.name)
      return [node.form ?? node.getRootNode(), `radio ${node.name}`];
    const name = node instanceof HTMLDetailsElement && node.getAttribute("name");
    return name ? [node.getRootNode(), `details ${name}`] : null;
  };
  /** @param {Element} node */
  const noteChange = (node) => {
    changed.add(node);
    const group = groupOf(node);
    if (!group) return;
    const [scope, name] = group;
    changedGroups.set(scope, (changedGroups.get(scope) ?? new Set()).add(name));
  };
  /** @param {Event} event */
  const change = (event) => {
    if (!(event instanceof Event) || !event.isTrusted) return;
    const path = event.composedPath();
    if (event.type === "input") {
      if (path[0] instanceof Element) noteChange(path[0]);
      return;
    }
    const summary = path.find(
      (node) => node instanceof HTMLElement && node.localName === "summary",
    );
    const details = summary instanceof HTMLElement ? summary.parentElement : null;
    if (details instanceof HTMLDetailsElement) noteChange(details);
  };
  // Early key holding and the runtime ask the same question of a key's origin.
  // Selects and custom options keep typeahead without being text editors.
  const textField = "leaf-text";
  const textBox = `textarea, ${textField}`;
  const typedTypes = new Set([
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
  /** @type {DocumentInputs["typesText"]} */
  const typesText = (node) =>
    node instanceof Element &&
    (node.matches(textBox) ||
      (node instanceof HTMLElement && node.isContentEditable) ||
      (node instanceof HTMLInputElement && typedTypes.has(node.type)));
  /** @type {DocumentInputs["takesLetters"]} */
  const takesLetters = (node) =>
    typesText(node) ||
    (node instanceof Element &&
      (node.localName === "select" || node.getAttribute("role") === "option"));
  /** @type {DocumentInputs} */
  const state = {
    textField,
    textBox,
    typesText,
    takesLetters,
    get count() {
      return inputs;
    },
    get steps() {
      return steps;
    },
    holdKeys(next) {
      hold = next;
    },
    edited(node) {
      if (changed.has(node)) return true;
      const group = groupOf(node);
      return Boolean(group && changedGroups.get(group[0])?.has(group[1]));
    },
    observe(read) {
      inputReaders.add(read);
      return () => inputReaders.delete(read);
    },
  };
  /** @param {Event} event */
  const input = (event) => {
    // Firefox can send an inaccessible foreign wheel object to an arriving
    // sandboxed window. It is not this realm's Event and reaches no document.
    // Reject it before reading fields or handing it to the input subscribers.
    if (!(event instanceof Event)) return;
    // Entering a child frame blurs this Window while its document still holds
    // input through that child. Only leaving the document supersedes its gesture.
    if (event.type === "blur" && (event.target !== window || document.hasFocus()))
      return;
    if (event instanceof KeyboardEvent && hold?.holds(event)) return;
    inputs++;
    hold?.counted();
    for (const read of inputReaders) read(event);
  };
  for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"])
    window.addEventListener(type, input, { capture: true, passive: true });
  for (const type of ["input", "click"])
    window.addEventListener(type, change, { capture: true, passive: true });
  // Going Back or Forward is the user's word too, though the browser's own buttons send
  // the page no input. Where the Navigation API runs, the step counts as it begins,
  // before Leaf's own handler for it (history.js) retains its intent; elsewhere Leaf has
  // no such handler, and the `popstate` that follows the step counts. An opaque frame,
  // as a live sample is, has the API with no entries and fires only `popstate`.
  const step = () => {
    inputs++;
    steps++;
    hold?.counted();
  };
  if (window.navigation?.currentEntry)
    window.navigation.addEventListener("navigate", (event) => {
      if (event.navigationType === "traverse") step();
    });
  else window.addEventListener("popstate", step);

  Reflect.set(window, key, state);
})();
