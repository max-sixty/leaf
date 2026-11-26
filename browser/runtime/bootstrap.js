// The server places this script before any loadable page resource.
// It must run even when the entry module or one of its dependencies cannot load.
(() => {
  // The one rename this script makes of the entry the user is on: to `url`, keeping the
  // entry's own state, the record of where the user was on it, which a reload returns
  // them to (records/history.js) and `replaceState` alone drops. A sandboxed sample's document
  // keeps no entries.
  /** @param {URL} url */
  const rename = (url) => {
    const state = window.navigation.currentEntry?.getState();
    history.replaceState(history.state, "", url);
    if (state !== undefined) window.navigation.updateCurrentEntry({ state });
  };
  const arrived = new URL(location.href);
  // `_leaf-recovered` is the mark recovery puts on the one document it asks for, so a
  // document that comes back on the same dead release, or fails to load again from the
  // same server, can tell that asking again is not going to produce a different one.
  // `t` is the host key a handover link carries; the server has already answered it
  // with the cookie every later request rides on, so what stays in the address bar is
  // a link the user can copy, share, or screen without handing out every page on the
  // machine. All three leave before the user sees them.
  const recovered = arrived.searchParams.has("_leaf-recovered");
  const marks = ["_leaf-revision", "_leaf-recovered", "t"];
  if (marks.some((mark) => arrived.searchParams.has(mark))) {
    for (const mark of marks) arrived.searchParams.delete(mark);
    rename(arrived);
  }
  const script = (() => {
    const entry = document.currentScript;
    if (!(entry instanceof HTMLScriptElement))
      throw new Error("The Leaf bootstrap needs its HTML script entry");
    return entry;
  })();
  const root = document.documentElement;
  // runtime/base/ids.js's randomId, which this classic script cannot import: a sample
  // child served by `leaf --host` over plain HTTP has no crypto.randomUUID, nor does a
  // site build served that way.
  const randomId = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
  // A framed document places focus only while it holds input (dom/focus.js,
  // `canPlaceFocus`). Aim cancels native mousedown focus and places its editor after
  // layout, so a trusted input enters the browsing context before those handlers run.
  if (window !== window.top) {
    const nativeWindowFocus = window.focus;
    const enterFrame = /** @param {Event} event */ (event) => {
      if (event.isTrusted && !document.hasFocus()) nativeWindowFocus.call(window);
    };
    for (const type of ["pointerdown", "keydown"])
      window.addEventListener(type, enterFrame, true);
  }
  // The sample URL grants this document its own server operations. An opaque
  // origin keeps it out of its parent's DOM and storage; native network APIs keep
  // their ordinary browser behavior. Only presentation values use the private port.
  if (root.hasAttribute("data-lf-sample")) {
    if (window.lfSampleBridge) {
      root.lfSample = window.lfSampleBridge;
      root.lfSample.install();
    } else {
      /** @type {{port: MessagePort, settings: import("./base/sample-protocol.js").SampleSettings} | null} */
      let connection = null;
      /** @type {PromiseWithResolvers<void>} */
      const { promise: ready, resolve: readyResolve } = Promise.withResolvers();
      /** @type {import("./base/sample-protocol.js").ChildMessage[]} */
      const queued = [];
      /** @type {Set<(message: import("./base/sample-protocol.js").ParentMessage) => void>} */
      const listeners = new Set();
      /** @param {import("./base/sample-protocol.js").ChildMessage} value */
      const send = (value) =>
        connection ? connection.port.postMessage(value) : queued.push(value);
      /** @type {LeafSampleBridge} */
      const bridge = {
        ready,
        get settings() {
          if (!connection) throw new Error("The sample private port is not connected");
          return connection.settings;
        },
        send,
        install() {
          const root = document.documentElement;
          window.lfRootState.setRuntimeRootAttribute(
            root,
            "data-lf-sample-block",
            bridge.settings.window ? null : "",
          );
          dress(worn);
        },
        receive: (callback) => listeners.add(callback),
        present() {
          window.lfRootState.setRuntimeRootAttribute(
            document.documentElement,
            "inert",
            null,
          );
        },
      };
      root.lfSample = bridge;
      window.lfSampleBridge = bridge;
      /** @type {LeafDress} */
      let worn = { attributes: {}, properties: {} };
      /** @param {LeafDress} [next] */
      const dress = (next = { attributes: {}, properties: {} }) => {
        const root = document.documentElement;
        window.lfRootState.wear(root, next);
        worn = next;
      };
      const sample = new URL(`${script.dataset.lfPageRoot}/`, location.origin).pathname;
      const nonce = randomId();
      /** @param {MessageEvent<import("./base/sample-protocol.js").SampleOffer | undefined>} event */
      const connect = (event) => {
        const port = event.ports[0];
        if (
          event.source !== window.parent ||
          event.data?.sample !== sample ||
          event.data.nonce !== nonce ||
          !port
        )
          return;
        window.removeEventListener("message", connect);
        const settings = event.data.settings;
        connection = { port, settings };
        // The bootstrap element owns diagnostic readings before the entry starts.
        script.lfDocumentPort = port;
        port.onmessage =
          /** @param {MessageEvent<import("./base/sample-protocol.js").ParentMessage>} event */ ({
            data,
          }) => {
            if (data.type === "dress") dress(data.detail);
            else for (const callback of listeners) callback(data);
          };
        port.postMessage({ type: "connected", nonce });
        bridge.install();
        dress(settings.dress);
        window.lfRootState.setRuntimeRootAttribute(
          root,
          "data-lf-sample-connecting",
          null,
        );
        readyResolve();
        for (const value of queued.splice(0)) port.postMessage(value);
      };
      // What the document wears, its dress and whether it stands as a block, comes in
      // the containing page's answer, which can land frames after the document could
      // first paint. Until it does the document paints nothing (base.css), so no frame
      // shows a playground's candidate undressed. Opened as a window of its own, it
      // has no containing page to answer and paints at once.
      if (window.parent !== window)
        window.lfRootState.setRuntimeRootAttribute(
          root,
          "data-lf-sample-connecting",
          "",
        );
      window.addEventListener("message", connect);
      window.parent.postMessage({ type: "leaf-sample-connect", sample, nonce }, "*");
      // A frame's own navigation never keeps its document in the page cache, so a
      // persisted pagehide is the containing page's, which takes this document and
      // its port along and brings both back together (host/sample.js keeps the host then).
      window.addEventListener("pagehide", (event) => {
        if (!event.persisted) send({ type: "departed" });
      });
    }
    const sampleBridge = root.lfSample;
    window.addEventListener("lf-startup-failed", () =>
      window.lfDocumentLifetime.whenActive("sample error", () =>
        sampleBridge.send({
          type: "error",
          detail: root.lfStartupException ?? {
            message:
              document.documentElement.dataset.lfStartupError ||
              "Sample could not start",
          },
        }),
      ),
    );
  }
  // A served page draws the live chrome, the floating panel, over the page from the first
  // paint (`html[data-lf-live]`). An export runs the runtime without it (prepaint.js).
  root.toggleAttribute("data-lf-live", true);
  const incarnation = script.dataset.lfServer;
  const layer = script.dataset.lfLayer;
  const release = script.dataset.lfRelease;
  let recovering = false;
  // What the profile says about a startup fault. A page that would not start is the one
  // reading nobody here can reproduce, so the record has to name the thing that did not
  // load. A fault the page recovers from is worth the name too, so the outcome that
  // eventually wins carries it rather than a separate record standing for it.
  /** @type {(reason: string) => void} */
  let recordStartupFault = () => {};
  let stopHoldingKeys = () => {};
  // The words the held keys show, or null while none do (`holdEarlyKeys`).
  /** @type {() => HeldWords | null} */
  let shownKeys = () => null;

  // The floating panel's row stands from the first paint, so the panel never arrives
  // after the page: the panel's own first drawing, which delivery carries inert in a
  // template (runtime/panel-row.html, build/panel-row.mjs), stood after `body` as soon
  // as `body` is parsed, where the runtime's chrome root will stand (base.css), at the
  // size the reader left the panel (`lfChrome.rest`, prepaint.js). The chrome's sheet is
  // adopted with it so it paints styled: the instance the runtime adopts, which an
  // adoption puts after every sheet the page holds, as the runtime's does (leaf.js). It
  // says what the panel says before it has a reading, the status's words beside a leaf
  // with no count, since nothing the server reads is known yet, and the keys held below
  // in place of the status.
  //
  // Until the panel mounts, a press on the leaf lands on the row and does nothing. What
  // it does turns on the panel's state, which only the runtime reads, so a press held
  // until then would act on a panel the user never saw take it; a key means the same
  // wherever it lands, which is why keys are held. The press still never
  // reaches the page beneath the row, and ends a run of held keys as any press does.
  // Those controls take no focus (`inert`), so Tab passes them by.
  //
  // The field is a textarea (`.lf-fp-served-field`), so a press there puts the caret
  // in it and what the user types is words, which the browser keeps, with the caret,
  // selection, input methods and a phone's keyboard, and which the hold leaves to it,
  // as it leaves any field's (`takesLetters`). The words the field says stand under
  // the textarea while it is empty. Return makes a line, since nothing can send yet.
  // While the user is in the field, the row stands as the panel's does while the user
  // writes, as far as the row draws it: the field's ring
  // (`data-lf-control-focus-visible`, dom/focus.js).
  // Rejected: dropping the keys typed there, which loses every word typed before the
  // runtime loads; drawing them in the field's words as typed, which needs a caret,
  // endings, wrapping and a phone's keyboard of its own; a `contenteditable`, which
  // Firefox types into but deletes nothing from when it stands after `body`, as the
  // chrome does (notes/browser-support.md); and holding
  // Return to send once the panel stands, which hides the words typed after it until
  // then or needs a display of its own, for a key the user presses again a moment on.
  //
  // The panel takes the row over as it mounts, in the task that draws the panel's first
  // frame, whose leaf, field and marks stand where the row's stood (floating-panel.css,
  // `data-lf-served`), and offers its field (`lf-held-keys-seat`), which takes the
  // textarea's words and caret (panel/floating-panel.js, `write`) as the row goes. An input
  // method composing in the textarea finishes there first, since words taken
  // mid-composition the method writes again as it ends. Where no panel is coming,
  // because the document reports it cannot start or the runtime gives it up, the row
  // goes as the hold on keys ends (`stopHoldingKeys`), and its sheet with it, which
  // nothing then draws with, unless its field holds words: they stay where the user
  // wrote them until recovery reloads the page.
  /** @type {{say(words: HeldWords | null): void, end(): void} | null} */
  let row = null;
  let rowEnded = false;
  // No panel is coming to take the row over.
  const endRow = () => {
    rowEnded = true;
    row?.end();
    row = null;
  };
  function standRow() {
    const template = document.querySelector(
      "template[data-lf-runtime][data-lf-panel-row]",
    );
    if (!(template instanceof HTMLTemplateElement)) return;
    const stand = () => {
      if (rowEnded) return;
      const chrome = document.createElement("div");
      chrome.className = "lf-chrome";
      chrome.setAttribute("data-lf-runtime", "");
      chrome.append(template.content.cloneNode(true));
      const panel = chrome.firstElementChild;
      const fieldWords = panel?.querySelector(".lf-fp-words");
      const words = fieldWords?.querySelector(".lf-compose-placeholder-words");
      const box = panel?.querySelector(".lf-fp-served-field");
      const panelRow = panel?.querySelector(".lf-fp-row");
      const peek = panel?.querySelector(".lf-fp-peek");
      if (
        !(panel instanceof HTMLElement && fieldWords instanceof HTMLElement) ||
        !(box instanceof HTMLTextAreaElement) ||
        !words ||
        !panelRow ||
        !peek
      )
        throw new Error("The panel's served row has no field, field words or peek");
      panel.dataset.lfRest = window.lfChrome.rest;
      panel.toggleAttribute("data-lf-served", true);
      // Only the controls are inert, since an inert subtree is hidden from assistive
      // technology too: the field's words and the folded leaf's peek are each a status,
      // so held keys are heard where they are seen.
      for (const control of panel.querySelectorAll("button, input"))
        control.toggleAttribute("inert", true);
      for (const seat of [words, peek]) seat.setAttribute("role", "status");
      const status = [...words.childNodes];
      box.addEventListener("input", () => {
        const typed = box.value !== "";
        if (fieldWords.hidden !== typed) fieldWords.hidden = typed;
      });
      let composing = false;
      for (const type of ["compositionstart", "compositionend"])
        box.addEventListener(type, () => (composing = type === "compositionstart"));
      for (const type of ["focus", "blur"])
        box.addEventListener(type, () =>
          panelRow.toggleAttribute("data-lf-control-focus-visible", type === "focus"),
        );
      const sheet = window.lfSheets().chrome;
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
      document.body.after(chrome);
      let offered = false;
      let gone = false;
      /** @param {boolean} taken whether the panel took the row over */
      const go = (taken) => {
        if (gone) return;
        gone = true;
        chrome.remove();
        document.removeEventListener("lf-held-keys-seat", takeOver);
        // A panel that took the row over adopted the sheet as its own (leaf.js).
        if (!taken)
          document.adoptedStyleSheets = document.adoptedStyleSheets.filter(
            (adopted) => adopted !== sheet,
          );
      };
      /** @param {DocumentEventMap["lf-held-keys-seat"]} event */
      const takeOver = ({ detail }) => {
        offered = true;
        const hand = () => {
          if (composing)
            return box.addEventListener("compositionend", hand, { once: true });
          detail.write(box);
          go(true);
        };
        hand();
      };
      document.addEventListener("lf-held-keys-seat", takeOver, { once: true });
      // The panel's size stands while the row does, so one seat says the keys.
      const folded = panel.dataset.lfRest === "mark";
      row = {
        // The keys as the panel says them, each as its badge beside Leaf's words: in
        // the field, or in the folded leaf's peek, as the panel's `heldParts` draws
        // them. None gives the field back its status.
        say(said) {
          const parts = said?.map((part) => {
            const node = document.createElement(
              typeof part === "string" ? "span" : "kbd",
            );
            if (typeof part === "string") node.setAttribute("data-lf-voice", "leaf");
            else node.className = "lf-key-badge lf-held-key";
            node.textContent = typeof part === "string" ? part : part.key;
            return node;
          });
          if (!folded) return words.replaceChildren(...(parts ?? status));
          peek.replaceChildren(...(parts ?? []));
          peek.toggleAttribute("data-lf-shown", Boolean(parts));
        },
        end() {
          if (!offered && !box.value) go(false);
        },
      };
      const held = shownKeys();
      if (held) row.say(held);
    };
    if (document.body) return stand();
    const parsing = new MutationObserver(() => {
      if (!document.body) return;
      parsing.disconnect();
      stand();
    });
    parsing.observe(root, { childList: true });
  }

  // A page key pressed before upgrade would reach a runtime that has not loaded.
  // Upgrade hands the queue to the dispatcher, whose command readiness may retain
  // keys that need private history. What is held is a run of printed keys: one
  // pressed on the page starts it, and every printed key after it
  // joins. Any other key ends the run, and so does a pointer press, which puts the user
  // somewhere the keys were not aimed at: what was held is dropped and the new press
  // keeps its own meaning. Words typed through Leaf's reload are no run: they go into
  // their box as they are typed (`typeBack`). A chord never starts a run, and a
  // modifier alone is half a press, which neither starts nor ends one. After a beat
  // the held keys are shown, so a press visibly landed; a runtime that takes the run
  // within the beat shows nothing.
  //
  // They are shown where the page says what it is doing, the floating panel's field,
  // in place of the status: before the panel mounts, in the row the document served
  // (`standRow`, below), and once the panel offers its field as their seat
  // (`lf-held-keys-seat`, panel/floating-panel.js), there. The user chose the panel's look
  // and field over a notice of the keys' own, a second interface that often stood
  // beside the panel.
  //
  // The hold ends when the runtime takes it, when the document reports it cannot start
  // (`recover`, and the runtime's own `letHeldKeysGo` where it gives the document up),
  // or when the user lets go as above, and never on a clock. The words say the keys
  // run when the page is ready, and a healthy page can take any time to get there on
  // a loaded machine or a slow network. Rejected: ending the hold ten seconds in,
  // on the reading that a page not upgraded by then had faulted, which drops the keys
  // of a page that upgrades later than that on a loaded machine. A page that hangs with no
  // report keeps showing that it is still loading, which is then the truth.
  const { takesLetters, holdKeys } = /** @type {DocumentInputs} */ (
    Reflect.get(window, Symbol.for("leaf.inputs"))
  );
  // Where the tab keeps the run of held keys (`holdEarlyKeys`), and the words typed
  // through Leaf's reload for a draft (`typeBack`). The event of the same name tells
  // the runtime that words wait there.
  const HELD_KEYS = "lf-held-keys";
  const HELD_WORDS = "lf-held-words";
  const HALF_PRESSES = new Set([
    "Shift",
    "Control",
    "Alt",
    "AltGraph",
    "Meta",
    "CapsLock",
  ]);
  function holdEarlyKeys() {
    let taken = false;
    // The place a reload Leaf asked for hands this document (prepaint.js,
    // `placesUser`); a handoff of values alone hands back none. While the place comes
    // back a held key is no input (`holdKeys`, below). Where the user was writing in a
    // box (`typing`), a user typing through the reload means their keys as words for
    // that box (`typeBack`): a Space is a word space rather than a scroll of the page,
    // whatever the single-key preference. Once an input of theirs ends the hand-back
    // (`counted`), their keys are the page's again.
    const { handoff, tabStore, placesUser, handedFocus } = window.lfStorage;
    let moved = false;
    const typingBack = () => placesUser() && handoff?.typing === true && !moved;
    // The box the reload hands back: a draft's editor, named by its draft's context
    // (features/version.js, `captureHandoff`), or a field of the page's own (prepaint.js,
    // `handedFocus`) that holds a caret, which typing into it needs. A date, time or
    // number field holds none, so a key typed for it waits in the run, and the field
    // takes it as it takes any key once the reload puts the user back (`queue`).
    const draft = handoff?.draftEditing?.context ?? null;
    const field = draft || !handedFocus?.caret ? null : handedFocus;
    /** @param {string} key */
    const read = (key) => {
      try {
        return JSON.parse(tabStore.get(key) || "null");
      } catch {
        return null;
      }
    };
    // The words the tab keeps for their drafts until the runtime types them in
    // (`typeBack`), in the order they were typed.
    /** @returns {{context: string, words: string}[]} */
    const keptWords = () => {
      const kept = read(HELD_WORDS);
      return Array.isArray(kept) ? kept : [];
    };
    // The run is kept in the tab as it changes, as each key is held, pressed or let go
    // (`save`), so a document that goes leaves the keys it held and never pressed. A
    // reload Leaf asks for of the same address hands a place back, and its document's
    // run starts with those keys, even where the document before it had put its own
    // place back and was pressing them as it went; any other load starts a run of its
    // own.
    const stored = read(HELD_KEYS);
    /** @type {KeyboardEvent[]} */
    const held =
      placesUser() && Array.isArray(stored)
        ? stored.map((init) => new KeyboardEvent("keydown", init))
        : [];
    const save = () =>
      tabStore.set(
        HELD_KEYS,
        held.length
          ? JSON.stringify(
              held.map(
                ({ key, code, location, shiftKey, ctrlKey, altKey, metaKey }) => ({
                  key,
                  code,
                  location,
                  shiftKey,
                  ctrlKey,
                  altKey,
                  metaKey,
                }),
              ),
            )
          : null,
      );
    save();
    /** @type {((event: KeyboardEvent) => boolean) | null} */
    let ready = null;
    /** @type {(() => boolean) | null} */
    let keep = null;
    let beat = 0;
    // The words shown, as text, or "" while none are.
    let shown = "";
    /** @type {((words: HeldWords | null) => void) | null} */
    let seat = null;
    // What the held keys say, wherever they show: each key as its badge, then Leaf's
    // words. The keys lead, so a narrow field that cuts the line short keeps them. Words
    // typed for a draft are in it already, which is what Leaf says of them, until the
    // user moves on.
    /** @param {string[]} keys @param {string} saying @returns {HeldWords} */
    const said = (keys, saying) =>
      keys.length
        ? [
            ...keys.flatMap((key, at) => [
              ...(at ? [" "] : []),
              { key: key === " " ? "Space" : key },
            ]),
            saying,
          ]
        : [];
    /** @returns {HeldWords} */
    const words = () => {
      const kept = said(moved ? [] : [...typed], " kept in the draft");
      const waiting = said(
        held.map(({ key }) => key),
        held.length === 1
          ? " runs when the page is ready"
          : " run when the page is ready",
      );
      return [...kept, ...(kept.length && waiting.length ? [" · "] : []), ...waiting];
    };
    // Words already shown are not shown again: the panel's field repaints for each, and
    // each of its paints asks the keyboard owner to take the keys again
    // (controller.js, `watchCommandAvailability`), which pauses on the same key.
    const show = () => {
      beat = 0;
      const said = words();
      const text = JSON.stringify(said);
      if (text === shown) return;
      shown = text;
      if (seat) seat(said);
      else row?.say(said);
    };
    const hide = () => {
      clearTimeout(beat);
      beat = 0;
      if (!shown) return;
      shown = "";
      if (seat) seat(null);
      else row?.say(null);
    };
    const letGo = () => {
      held.length = 0;
      save();
      hide();
    };
    // A key the user types through Leaf's reload is a word for the box it hands back
    // as soon as it is typed, so nothing that ends the hold can drop it: a scroll, a
    // press elsewhere, a step away or a page that can't start ends the return of the
    // user's place, not their wish for the words. A field of the page's own takes it
    // at once (`typeIntoField`). A draft's takes it through the tab, which keeps it
    // until the runtime types it in, at once where the runtime has loaded and else as
    // a document of the page next loads (records/drafts.js, `takeHeldWords`), so the box comes
    // back holding it. Until the hand-back ends the hold shows the draft's words as it
    // shows held keys (`typed`), and then asks the runtime whether they are on screen.
    let typed = "";
    /** @param {string} key */
    const typeBack = (key) => {
      if (!draft) return typeIntoField(key);
      typed += key;
      tabStore.set(
        HELD_WORDS,
        JSON.stringify([...keptWords(), { context: draft, words: key }]),
      );
      document.dispatchEvent(new Event(HELD_WORDS));
      if (shown) show();
      else beat ||= setTimeout(show, 150);
    };
    // A field of the page's own takes the words in the value and caret the reload
    // carries for it, which the arrival puts back (records/carry.js, `restoreCarry`), and in the
    // field itself, which may already hold that value; the page hears them there as the
    // field's input, which is the user's typing replayed rather than a new input of
    // theirs (`echo`, `holdKeys`). Neither leaves the document.
    /** @type {InputEvent | null} */
    let echo = null;
    /** @param {string} key */
    const typeIntoField = (key) => {
      if (!field) return;
      const element = document.getElementById(field.id);
      const control =
        element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement
          ? element
          : null;
      const value = field.value ?? control?.defaultValue ?? "";
      const [start, end] = /** @type {[number, number]} */ (field.caret);
      const at = start + key.length;
      field.value = value.slice(0, start) + key + value.slice(end);
      field.caret = [at, at];
      if (!control) return;
      control.value = field.value;
      control.setSelectionRange(at, at);
      echo = new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: key,
      });
      control.dispatchEvent(echo);
      echo = null;
    };
    /** @param {KeyboardEvent} event */
    const queue = (event) => {
      if (event.repeat) return;
      held.push(event);
      save();
      if (taken) return;
      if (shown) show();
      else beat ||= setTimeout(show, 150);
    };
    // Whether the hold takes `event`, which then goes into the box the reload hands back
    // (`typeBack`) or waits in the run until it is replayed (`queue`). Where a place is
    // handed back, the input clock asks this first and leaves such a key uncounted
    // (base/document-inputs.js, `holdKeys`).
    /** @param {KeyboardEvent} event */
    const holds = (event) => {
      if (!window.lfKeyboard.quick && !typingBack()) return false;
      if (event.isComposing || HALF_PRESSES.has(event.key)) return false;
      // Shift chooses which character prints; Ctrl, Alt and Meta make a chord instead.
      const printed =
        event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
      // The run is open, so a printed key follows the keys before it wherever it was
      // typed: a held `c` may yet open the box the rest is text for. Any other key
      // ends the run and keeps its own meaning: Enter, Backspace, Tab, an arrow or a
      // chord acts natively where focus stands, which a replay through the keyboard
      // owner cannot reproduce, and must not act ahead of keys pressed before it.
      if (held.length || taken) return printed;
      // Only a printed page key starts a run. One typed into a field is the field's,
      // and Space on its own scrolls, except where the user typing through Leaf's
      // reload means it as a word space (`typingBack`). The prepaint's `takesLetters`
      // is also the runtime's rule, so a checkbox or radio, which takes no letters,
      // holds the key as the presented page would act on it. `leaf-text` is the
      // runtime's text field; its closed root makes the host the event's origin.
      const origin = event.composedPath()[0];
      const typing = origin instanceof Element && takesLetters(origin);
      if (typing || !printed || (event.key === " " && !typingBack())) return false;
      // Once the document upgrades, the dispatcher supplies readiness from
      // command declarations. Useful page keys pass immediately; only a key
      // whose input is still loading starts another ordered run.
      return !ready?.(event);
    };
    /** @param {KeyboardEvent} event */
    const hold = (event) => {
      if (!window.lfKeyboard.quick && !typingBack()) return letGo();
      if (holds(event)) {
        if (typingBack() && (draft || field)) typeBack(event.key);
        else queue(event);
        event.preventDefault();
        event.stopImmediatePropagation();
      } else if (
        (held.length || taken) &&
        !event.isComposing &&
        !HALF_PRESSES.has(event.key)
      )
        letGo();
    };
    const pointed = () => letGo();
    // The controller takes a run, but the hold stands until its owner has pressed the
    // last key in it: a printed key pressed meanwhile joins the same run rather than
    // running ahead of the keys pressed before it. Each key leaves the run as the
    // controller presses it (`pressed`), and a release lets go of any it leaves. Words
    // already shown stand until the run is pressed or pauses on a key that must still
    // wait, which they then name.
    /** @param {DocumentEventMap["lf-held-keys"]} event */
    const take = (event) => {
      ready = event.detail.ready;
      keep = event.detail.keep;
      // The hand-back is over, and the runtime says the draft is kept where its words
      // aren't on screen in their box, as after a step to another entry (records/drafts.js,
      // `takeHeldWords`).
      if (typed) document.dispatchEvent(new CustomEvent(HELD_WORDS, { detail: draft }));
      typed = "";
      if (!held.length) {
        hide();
        if (!keep?.()) stopHoldingKeys();
        return;
      }
      taken = true;
      clearTimeout(beat);
      beat = 0;
      event.detail.keys = held;
      event.detail.pressed = () => {
        held.shift();
        save();
      };
      event.detail.pause = () => {
        taken = false;
        if (!keep?.()) return stopHoldingKeys();
        if (held.length) show();
      };
      event.detail.release = () => {
        taken = false;
        letGo();
        if (!keep?.()) stopHoldingKeys();
      };
    };
    /** @param {DocumentEventMap["lf-held-keys-seat"]} event */
    const seated = (event) => {
      seat = event.detail.show;
      if (shown) seat(words());
    };
    shownKeys = () => (shown ? words() : null);
    stopHoldingKeys = () => {
      holdKeys(null);
      window.removeEventListener("keydown", hold, true);
      window.removeEventListener("pointerdown", pointed, true);
      document.removeEventListener("lf-held-keys", take);
      document.removeEventListener("lf-held-keys-seat", seated);
      typed = "";
      letGo();
      endRow();
    };
    // Where Leaf's reload hands a place back, a key the hold keeps is no input until it
    // replays, so it doesn't stop the hand-back it waits for, and neither is a bare
    // modifier, which acts on nothing, as the Shift before a capital the hold keeps.
    // Any other input the document's clock counts, a scroll or a step Back or Forward as
    // much as a press, ends that hand-back, so the keys held for the place it would put
    // back go at once (`counted`, `letGo`), and a document that goes then leaves none of
    // them as keys.
    // The run's own presses, once the place is back, are the clock's inputs too, and
    // let go of nothing (`taken`). Elsewhere a held key still counts, so a key typed
    // while the page starts still stops arrival work, such as reopening a comment box,
    // as it always did. Whatever the load, the run belongs to the entry its keys were
    // typed at: a step Back or Forward lets it go, the keys the runtime has yet to
    // press included, only where the browser says the user took it; otherwise the keys
    // stay and run where the user then stands (base/document-inputs.js, `step`). Whether
    // the place is handed back is asked of the entry the user stands at as each input
    // comes (prepaint.js, `placesUser`).
    holdKeys({
      holds: (event) =>
        event === echo ||
        (event instanceof KeyboardEvent &&
          placesUser() &&
          (HALF_PRESSES.has(event.key) || holds(event))),
      counted: (stepped) => {
        if (!stepped && (taken || !placesUser())) return;
        moved = true;
        letGo();
      },
    });
    window.addEventListener("keydown", hold, true);
    window.addEventListener("pointerdown", pointed, true);
    // The keyboard owner takes the held keys as the document upgrades and runs them through
    // its own handler (runtime/panel/page-keys/controller.js).
    document.addEventListener("lf-held-keys", take);
    document.addEventListener("lf-held-keys-seat", seated);
    if (held.length) beat = setTimeout(show, 150);
  }

  // A small public-site profile separates browser upgrade from the first state
  // response and authoritative presentation. Failed module graphs report too.
  function observePublicStartup() {
    if (!release) return;
    let sent = false;
    /** @type {number | null} */
    let upgradedMs = null;
    /** @type {number | null} */
    let firstStateResponseMs = null;
    /** @type {number | null} */
    let presentedMs = null;
    /** @type {string | null} */
    let fault = null;
    /** @param {number | undefined} value */
    const rounded = (value) =>
      value !== undefined && Number.isFinite(value) && value >= 0
        ? Math.round(value)
        : null;
    const pageRoot = new URL(`${script.dataset.lfPageRoot}/`, location.origin);
    const stateUrl = new URL("api/state", pageRoot);
    /** @param {readonly PerformanceEntry[]} entries */
    const readStateResponses = (entries) => {
      for (const entry of entries) {
        if (!(entry instanceof PerformanceResourceTiming)) continue;
        const url = new URL(entry.name);
        if (
          url.origin !== stateUrl.origin ||
          url.pathname !== stateUrl.pathname ||
          entry.responseStart <= 0 ||
          entry.responseEnd <= 0
        )
          continue;
        const ended = Math.round(entry.responseEnd);
        firstStateResponseMs =
          firstStateResponseMs === null ? ended : Math.min(firstStateResponseMs, ended);
      }
    };
    // Observe completions as they arrive: the global resource timeline can fill
    // before state answers, and reading it only at presentation would lose this fact.
    const resources = new PerformanceObserver((list) => {
      readStateResponses(list.getEntries());
    });
    resources.observe({ type: "resource", buffered: true });
    const readMilestones = () => {
      if (upgradedMs === null && document.body?.hasAttribute("data-lf-upgraded"))
        upgradedMs = rounded(performance.now());
      if (presentedMs === null && document.body?.hasAttribute("data-lf-presented"))
        presentedMs = rounded(performance.now());
    };
    /** @param {"presented" | "failed" | "abandoned" | "timeout"} outcome */
    const report = (outcome) => {
      if (sent) return;
      sent = true;
      readMilestones();
      observer.disconnect();
      readStateResponses(resources.takeRecords());
      resources.disconnect();
      const navigation = performance
        .getEntriesByType("navigation")
        .find((entry) => entry instanceof PerformanceNavigationTiming);
      const paint = performance
        .getEntriesByName("first-contentful-paint", "paint")
        .at(0);
      void fetch(new URL("api/performance", pageRoot), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        keepalive: true,
        body: JSON.stringify({
          loadId: randomId(),
          release,
          layer,
          outcome,
          ...(fault && { reason: String(fault).slice(0, 300) }),
          navigationType: navigation?.type ?? "unknown",
          serverMs: rounded(
            navigation?.serverTiming?.find((entry) => entry.name === "leaf")?.duration,
          ),
          firstByteMs: rounded(navigation?.responseStart),
          firstContentfulPaintMs: rounded(paint?.startTime),
          upgradedMs,
          firstStateResponseMs,
          presentedMs,
        }),
      }).catch(() => {});
    };
    const observer = new MutationObserver(() => {
      readMilestones();
      if (presentedMs === null) return;
      observer.disconnect();
      const afterLoad = () => setTimeout(() => report("presented"));
      if (document.readyState === "complete") afterLoad();
      else window.addEventListener("load", afterLoad, { once: true });
    });
    observer.observe(document, {
      attributes: true,
      attributeFilter: ["data-lf-upgraded", "data-lf-presented"],
      childList: true,
      subtree: true,
    });
    // The prepaint's `lf-startup-failed` listener runs before this one, since the
    // prepaint runs first, so a declared failure has already named its fault by the
    // time `failed` is reported here.
    window.addEventListener("lf-startup-failed", () => report("failed"), {
      once: true,
    });
    window.addEventListener("pagehide", () => report("abandoned"), { once: true });
    setTimeout(() => {
      readMilestones();
      // A usable interface may still be waiting on a healthy state read. Its
      // eventual answer or departure closes the authoritative profile.
      if (upgradedMs === null) report("timeout");
    }, 15000);
    recordStartupFault = (reason) => {
      fault ??= reason;
    };
  }

  // A page is incomplete where something it needs did not arrive (prepaint.js, which
  // takes `data-lf-interactive` off the root for each such fault, the first or a
  // later one): it lacks that however far it gets, so the notice stands until a load
  // brings it. The load may have failed on its way from a server that is still
  // there, as when the machine's network changes under the request, and the browser
  // keeps a failed module for the document's life, so once that server answers the
  // page asks it for the document once more, marked. One that comes back incomplete
  // from it waits for a server that can start the page to replace this one. A page
  // that only met an uncaught error in code that did load waits for that server
  // alone: the same server would serve the same bytes, so if the page upgrades it has
  // started with everything it is going to get. A fault that is the page's own
  // (`page`) is answered by no server: the page holds what its author wrote, so the
  // notice says the page has a problem and waits for nothing.
  /** @param {string} reason @param {boolean} page */
  function recover(reason, page) {
    recordStartupFault(reason);
    stopHoldingKeys();
    if (recovering) return;
    recovering = true;
    // The notice says the page has not started, and a page that has upgraded whole has
    // started, before the fault reached this or after, so a user who is using the page
    // would otherwise be reading that Leaf could not start, over a request a second
    // that no answer ends. A page that is incomplete has not started however far it
    // got, as one whose theme did not arrive, or whose runtime declared it failed once
    // it had upgraded and so shows its readable fallback (prepaint.js); it asks.
    const whole = () =>
      Boolean(document.body?.hasAttribute("data-lf-upgraded")) &&
      root.hasAttribute("data-lf-interactive");
    let started = !page && whole();
    const status = document.createElement("p");
    status.className = "lf-chrome";
    status.setAttribute("data-lf-runtime", "");
    status.setAttribute("role", "status");
    status.textContent = page
      ? "Leaf couldn't start: this page has a problem its author needs to fix."
      : "Leaf couldn't start. Waiting for Leaf to update.";
    const show = () => {
      if (!started) document.body.prepend(status);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });
    if (page || started) return;
    const upgrade = new MutationObserver(() => {
      if (!whole()) return;
      upgrade.disconnect();
      started = true;
      status.remove();
    });
    upgrade.observe(document, {
      attributes: true,
      attributeFilter: ["data-lf-upgraded"],
      subtree: true,
    });

    // A round carries what it learned to the end rather than acting where it learned
    // it. The round in flight when the page upgrades resolves after it, and the user
    // is then using a page this would otherwise navigate out from under them, so the
    // one place that acts is the one place that has to ask whether the page started.
    // The one document recovery asks for is this address marked, reloaded as a
    // revision's handoff reloads (features/version.js), past a cache that answered the address
    // the user typed.
    const ask = () => {
      const next = new URL(location.href);
      next.searchParams.set("_leaf-recovered", "");
      rename(next);
      location.reload();
    };
    const check = async () => {
      if (started) return;
      let restart = null;
      try {
        const probe = script.getAttribute("data-lf-probe");
        if (probe === null)
          throw new Error("Startup recovery requires its delivery probe");
        const response = await fetch(probe, { cache: "no-store" });
        // The release this document names is gone, so nothing this document can load
        // will come back and only a newer one can start the page. A marked document
        // that arrives still naming the dead release says something between here and
        // the source is serving a copy of it; asking again lands on that same copy as
        // fast as the network allows, so the page waits on the probe at the cadence
        // every other unstarted page waits at.
        if (response.status === 404 && release && !recovered) restart = ask;
        const current = response.headers.get("Leaf-Server");
        const generation = response.headers.get("Leaf-Layer");
        const currentRelease = response.headers.get("Leaf-Release");
        if (
          (current && current !== incarnation) ||
          (generation && generation !== layer) ||
          (release && currentRelease && currentRelease !== release)
        ) {
          restart ??= () => location.reload();
        } else if (
          response.ok &&
          !recovered &&
          !root.hasAttribute("data-lf-interactive")
        ) {
          restart ??= ask;
        }
      } catch {
        // The stopped server has not been replaced yet.
      }
      if (started) return;
      if (restart) restart();
      else setTimeout(check, 1000);
    };
    void check();
  }

  // The prepaint names each startup fault and marks the page for it (prepaint.js).
  window.addEventListener("lf-startup-fault", (event) =>
    recover(event.detail.reason, event.detail.page),
  );
  // A sample opened as a window of its own has no containing page to connect it, so its
  // runtime never starts (leaf.js waits on `lfSample.ready`): no panel takes a row over
  // there, and nothing takes what is held.
  if (!(root.hasAttribute("data-lf-sample") && window.parent === window)) {
    standRow();
    holdEarlyKeys();
  }
  try {
    observePublicStartup();
  } catch {
    // Optional website diagnostics must never take startup supervision down with them.
  }
})();
