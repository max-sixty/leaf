// One helper wires every durable text surface: the general box, each per-thread reply,
// and the compact anchored composer. They persist a draft on each keystroke, send on the
// binding their caller supplies, and can't be double-sent by an impatient second click.
// Growing with their content is the stylesheet's job (field-sizing), not this file's.
// wire() returns a sync() the caller runs after setting .value programmatically, so the
// send button and any containing chrome agree with what's in the box.
export function createInput({ focused, keys, showToast, spell }) {
  // The send binding, and the register's spelling of it: the placeholder, the button's
  // tooltip and the row a box declares all read one string, where the constant they used to
  // share sat beside a listener that bound the chord independently.
  const SEND = "Mod+Enter";
  // Focus-derived hints join the runtime's one standing paint. Only the input losing the
  // standing and the one gaining it can change for that reason.
  const inputPaints = new WeakMap();
  let paintedInput = null;
  const paintInputs = () => {
    const held = focused();
    const input = held && inputPaints.has(held) ? held : null;
    if (paintedInput && paintedInput !== input) inputPaints.get(paintedInput)?.();
    if (input) inputPaints.get(input)?.();
    paintedInput = input;
  };
  // `sends` is the word the box's own send row says — "send", "suggest", "comment" — since
  // a composer in suggestion mode and a thread's reply are the same binding doing different
  // things, and the row is where the surfaces read that from.
  function wireInput(
    ta,
    {
      hint,
      address,
      save,
      send,
      sendBtn,
      sends,
      altBtn = null,
      altSend = null,
      busy = () => false,
      sendKey = SEND,
      layout = () => {},
    },
  ) {
    // The hint goes in the placeholder, where it's visible exactly while the box is
    // empty and can't be found any other way; the button's tooltip spells the send key
    // out. The send shortcut is focus-scoped, so only the focused box may claim it.
    // Unfocused, the placeholder may carry a contextual key where the composer has one.
    // Both hint and address may be functions because their labels can change while the
    // box stands.
    const label = () => (typeof hint === "function" ? hint() : hint);
    const sendKeys = spell(sendKey);
    const paint = () => {
      // Read the shared logical focus so this hint agrees with the key line and rings.
      const standing = focused() === ta;
      const suffix = standing ? sendKeys : address?.();
      const placeholder = suffix ? `${label()} · ${suffix}` : label();
      if (ta.placeholder !== placeholder) ta.placeholder = placeholder;
    };
    inputPaints.set(ta, paint);
    const repaint = () => {
      if (focused() === ta) paintInputs();
      else paint();
    };
    sendBtn.title = `Send (${sendKeys})`;
    if (altBtn) altBtn.title = altBtn.textContent;
    let sending = false;
    // Keep a disabled send reachable so the reader can discover why it will not send;
    // submit() is the behavioral guard and aria-disabled exposes the same state.
    const sync = () => {
      repaint();
      const disabled = String(sending || busy() || !ta.value.trim());
      sendBtn.setAttribute("aria-disabled", disabled);
      altBtn?.setAttribute("aria-disabled", disabled);
      layout();
    };
    // A runtime-built box is normally wired before it can receive focus. Preserve the
    // bookkeeping too if a caller wires one that is already standing.
    repaint();
    const submit = async (sender) => {
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
        await sender(text, raw);
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
      {
        id: "text.send",
        keys: [sendKey],
        does: "Send what you have typed",
        line: sends,
        run: () => sendBtn.click(),
      },
    ]);
    sendBtn.addEventListener("click", () => submit(send));
    altBtn?.addEventListener("click", () => submit(altSend));
    return sync;
  }

  return { paint: paintInputs, wire: wireInput };
}
