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
  // count (`counted`), and whether it was a step Back or Forward, which moves the user
  // to another entry rather than acting within the one the hand-back returns them to
  // (bootstrap.js, `holdEarlyKeys`).
  /** @type {Parameters<DocumentInputs["holdKeys"]>[0]} */
  let hold = null;
  /** @type {Set<(event: Event) => void>} */
  const inputReaders = new Set();
  // The controls the user has changed in this document: a field they typed into or a
  // box they ticked, as its trusted `input` says; a group of radios they chose among,
  // the radios of one `name` in one form, or in one tree where they have none; and a
  // disclosure whose summary they pressed, or took Enter or Space on. A page's own
  // script that sets a value or opens a disclosure makes no such input, so state a
  // reload carries yields to the user's newer change alone (carry.js, `restoreCarry`).
  /** @type {WeakSet<Element>} */
  const changed = new WeakSet();
  /** @type {WeakMap<Node, Set<string>>} */
  const chosenAmong = new WeakMap();
  /** @param {HTMLInputElement} radio */
  const radioScope = (radio) => radio.form ?? radio.getRootNode();
  /** @param {Event} event */
  const noteChange = (event) => {
    if (!event.isTrusted) return;
    if (event.type === "input") {
      const [origin] = event.composedPath();
      if (!(origin instanceof Element)) return;
      changed.add(origin);
      if (
        origin instanceof HTMLInputElement &&
        origin.type === "radio" &&
        origin.name
      ) {
        const scope = radioScope(origin);
        const names = chosenAmong.get(scope) ?? new Set();
        chosenAmong.set(scope, names.add(origin.name));
      }
      return;
    }
    const presses =
      event.type === "pointerdown" ||
      (event instanceof KeyboardEvent && (event.key === "Enter" || event.key === " "));
    if (!presses) return;
    const summary = event
      .composedPath()
      .find((node) => node instanceof HTMLElement && node.localName === "summary");
    const details = summary instanceof HTMLElement ? summary.parentElement : null;
    if (details instanceof HTMLDetailsElement) changed.add(details);
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
      return (
        node instanceof HTMLInputElement &&
        node.type === "radio" &&
        Boolean(node.name) &&
        Boolean(chosenAmong.get(radioScope(node))?.has(node.name))
      );
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
    noteChange(event);
    inputs++;
    hold?.counted(false);
    for (const read of inputReaders) read(event);
  };
  for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"])
    window.addEventListener(type, input, { capture: true, passive: true });
  // Going Back or Forward is the user's word too, though the browser's own buttons send
  // the page no input. Where the Navigation API runs, the step counts as it begins,
  // before Leaf's own handler for it (history.js) retains its intent; elsewhere Leaf has
  // no such handler, and the `popstate` that follows the step counts. An opaque frame,
  // as a live sample is, has the API with no entries and fires only `popstate`.
  const step = () => {
    inputs++;
    steps++;
    hold?.counted(true);
  };
  if (window.navigation?.currentEntry)
    window.navigation.addEventListener("navigate", (event) => {
      if (event.navigationType === "traverse") step();
    });
  else window.addEventListener("popstate", step);

  Reflect.set(window, key, state);
})();
