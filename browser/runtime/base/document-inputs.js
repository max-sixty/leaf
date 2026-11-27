/* Document-local input vocabulary and intent clock, shared by early delivery and
   portable widgets. This source is both inlined before prepaint and imported by
   modules. One per-document slot keeps the first clock and its listeners when the
   module graph arrives; a plain host starts it with its first portable import. */
(() => {
  const key = Symbol.for("leaf.inputs");
  if (Reflect.has(window, key)) return;
  // Inputs belong to this document from its first script, even while the module
  // graph is still loading. Delayed arrival work must not take focus or scroll
  // back from someone already using the authored page. dom/focus.js exposes this
  // same counter and subscription after startup; no later listener starts over.
  let inputs = 0;
  // The inputs among them that take the user away from the entry they are on rather
  // than acting in it (`away`): a step Back or Forward, which moves them to another
  // entry, and leaving the window, as for another application, after which they come
  // back to the same place. Either supersedes a gesture under way (dom/user-intent.js), but
  // a return to an entry's record yields only to the user's acts within the entry
  // (records/history.js). A search with find-in-page leaves the window too, so a return still
  // under way can move the page from the match the search reached; the user leaving
  // for another application while a slow reload arrives is the commoner case, and
  // counting it would lose their place for good.
  let away = 0;
  // The user's inputs, `away` aside, as they last stepped Back or Forward, or none
  // before any step (`entered`). The arrival counts their acts within the entry it
  // arrives at from there (records/history.js, `beginArrival`), so what they did at the entry
  // they left doesn't keep them from the record of the one they reached, though the
  // step came before Leaf handled steps. The count itself only grows, so a return an
  // act of theirs superseded stays superseded.
  let entered = 0;
  // While a reload Leaf asked for hands a place back, a key the bootstrap holds acts
  // only once the hold replays it, so until then it is no input, and the hand-back it
  // waits for is not superseded by it; nor is the input a held word makes in a field
  // as the hold types it in. The hold hears of the other inputs the clock
  // counts (`counted`): an act within the entry, and a step Back or Forward the
  // browser says the user took, which leaves the entry the held keys were typed at
  // (`step`). It hears of no step the page's script takes, nor of leaving the window,
  // after which the keys still land where the user then stands (bootstrap.js,
  // `holdEarlyKeys`).
  /** @type {Parameters<DocumentInputs["holdKeys"]>[0]} */
  let hold = null;
  /** @type {Set<(event: Event) => void>} */
  const inputReaders = new Set();
  // The controls the user has changed in this document (`edited`), whose state a
  // reload's arrival leaves as they left it (features/version.js, `installArrival`): a field or
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
  // The state a reload carries for a control and puts back (records/carry.js; prepaint.js,
  // `handingOn`), each where the control holds it: whether a disclosure is open; the
  // tick of a checkbox or radio; the values of the options chosen in a select, several
  // where it takes `multiple`; and the words in a text box or in an input other than a
  // file input, whose value only the browser sets.
  /** @param {Element} node @returns {node is HTMLInputElement} */
  const holdsTick = (node) =>
    node instanceof HTMLInputElement &&
    (node.type === "checkbox" || node.type === "radio");
  /** @param {Element} node @returns {node is HTMLElement & {value: string}} */
  const holdsValue = (node) =>
    node instanceof HTMLElement &&
    (node.matches(textBox) ||
      (node instanceof HTMLInputElement && node.type !== "file" && !holdsTick(node)));
  /** @type {DocumentInputs["controlState"]} */
  const controlState = (node) => {
    if (node instanceof HTMLDetailsElement) return { open: node.open };
    if (node instanceof HTMLSelectElement)
      return { chosen: [...node.selectedOptions].map((option) => option.value) };
    if (holdsTick(node)) return { checked: node.checked };
    if (holdsValue(node)) return { value: node.value };
    return null;
  };
  // A select takes back the chosen options it still has. Where it has none of them, as
  // after a revision that took the chosen option away, it keeps what it shows.
  /** @type {DocumentInputs["putControlState"]} */
  const putControlState = (node, state) => {
    if (node instanceof HTMLDetailsElement && "open" in state) node.open = state.open;
    else if (node instanceof HTMLSelectElement && "chosen" in state) {
      const chosen = new Set(state.chosen);
      const options = [...node.options];
      if (chosen.size && !options.some((option) => chosen.has(option.value))) return;
      for (const option of options) option.selected = chosen.has(option.value);
    } else if (holdsTick(node) && "checked" in state) node.checked = state.checked;
    else if (holdsValue(node) && "value" in state) node.value = state.value;
  };
  /** @type {DocumentInputs} */
  const state = {
    textField,
    textBox,
    typesText,
    takesLetters,
    controlState,
    putControlState,
    get count() {
      return inputs;
    },
    get away() {
      return away;
    },
    get entered() {
      return entered;
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
    if (hold?.holds(event)) return;
    inputs++;
    if (event.type === "blur") away++;
    else hold?.counted(false);
    for (const read of inputReaders) read(event);
  };
  for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"])
    window.addEventListener(type, input, { capture: true, passive: true });
  for (const type of ["input", "click"])
    window.addEventListener(type, change, { capture: true, passive: true });
  // Going Back or Forward is the user's word too, though the browser's own buttons send
  // the page no input. Where the Navigation API runs, the step counts as it begins,
  // before Leaf's own handler for it (records/history.js) retains its intent; elsewhere Leaf has
  // no such handler, and the `popstate` that follows the step counts. An opaque frame,
  // as a live sample is, has the API with no entries and fires only `popstate`. Every
  // step moves the clock and the arrival's baseline (`entered`), but only one the
  // browser says the user took (`userInitiated`), rather than the page's script, lets
  // held keys go; any other leaves them to run where the user then stands. `popstate`
  // can't say who took a step, so it lets nothing go, and nor does Firefox, which
  // reports no step as the user's, the browser's own Back included (Gecko bug
  // 1903552): there a held run outlives the user's step and its keys run at the entry
  // the step reached.
  /** @param {boolean} user */
  const step = (user) => {
    inputs++;
    away++;
    entered = inputs - away;
    if (user) hold?.counted(true);
  };
  if (window.navigation?.currentEntry)
    window.navigation.addEventListener("navigate", (event) => {
      if (event.navigationType === "traverse") step(event.userInitiated);
    });
  else window.addEventListener("popstate", () => step(false));

  Reflect.set(window, key, state);
})();
