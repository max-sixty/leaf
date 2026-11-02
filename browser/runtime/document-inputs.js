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
  /** @type {Set<(event: Event) => void>} */
  const inputReaders = new Set();
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
    inputs++;
    for (const read of inputReaders) read(event);
  };
  for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"])
    window.addEventListener(type, input, { capture: true, passive: true });

  Reflect.set(window, key, state);
})();
