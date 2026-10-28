(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // browser/runtime/icon-paths.js
  var SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';
  var ICONS = {
    activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
    add: '<path d="M8 3v10M3 8h10"/>',
    change: '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
    check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
    // A task app's ticked circle, for the to-do the user ends: a bare check is Resolve's,
    // and a to-do on a thread stands under its thread's Resolve.
    checked: '<circle cx="8" cy="8" r="5.5"/><path d="m5.6 8.15 1.7 1.7 3.1-3.3"/>',
    comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
    // The common copy glyph: the front sheet at the bottom right. Mirrored, with the front
    // sheet at the bottom left, two squares read as a window's Restore button.
    copy: '<rect x="6" y="6" width="7" height="7" rx="1.25"/><path d="M10 6V4.25C10 3.56 9.44 3 8.75 3h-4.5C3.56 3 3 3.56 3 4.25v4.5C3 9.44 3.56 10 4.25 10H6"/>',
    cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
    dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
    down: '<path d="m4 6.25 4 4 4-4"/>',
    edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
    expand: '<path d="M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75"/>',
    collapse: '<path d="M13 3 9.25 6.75M9.25 3.25v3.5h3.5M3 13l3.75-3.75M3.25 9.25h3.5v3.5"/>',
    fit: '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
    fold: '<path d="M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5"/>',
    more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
    // What waits on the user, an inbox's tray: the On me mark. The question mark stays
    // with an obligation and with help (`?`).
    inbox: '<path d="M2.75 9.25h2.9l1 1.6h2.7l1-1.6h2.9M2.75 9.25 4.4 4h7.2l1.65 5.25v2.75H2.75z"/>',
    link: '<path d="M6.67 8.67a3.33 3.33 0 0 0 5.03.36l2-2a3.33 3.33 0 0 0-4.71-4.71l-1.15 1.14M9.33 7.33a3.33 3.33 0 0 0-5.03-.36l-2 2a3.33 3.33 0 0 0 4.71 4.71l1.14-1.14"/>',
    // A map's locate mark, for the way from a thread to where its words stand.
    locate: '<circle cx="8" cy="8" r="4"/><path d="M8 1.75v2.5M8 11.75v2.5M1.75 8h2.5M11.75 8h2.5"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/>',
    microphone: '<rect x="6" y="2" width="4" height="7" rx="2"/><path d="M4 7.5v.75a4 4 0 0 0 8 0V7.5M8 12.25V14M6 14h4"/><path class="lf-mic-slash" d="M2.5 2.5l11 11"/>',
    next: '<path d="m6 3.5 4.5 4.5L6 12.5"/>',
    pause: '<path d="M5 3v10M11 3v10"/>',
    play: '<path d="m5 3 7 5-7 5z"/>',
    previous: '<path d="m10 3.5-4.5 4.5 4.5 4.5"/>',
    // How a list is arranged: its lines, shortening, the choosers' symbol.
    arrange: '<path d="M3 4.5h10M3 8h7M3 11.5h4"/>',
    all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
    pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
    question: '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
    reaction: '<circle cx="6.5" cy="8.25" r="4.25"/><circle cx="5" cy="7.25" r=".55" fill="currentColor" stroke="none"/><circle cx="8" cy="7.25" r=".55" fill="currentColor" stroke="none"/><path d="M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4"/>',
    retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
    save: '<path d="M3 4.25A1.25 1.25 0 0 1 4.25 3h6.5L13 5.25v6.5A1.25 1.25 0 0 1 11.75 13h-7.5A1.25 1.25 0 0 1 3 11.75zM5.5 3v2.5h4V3"/>',
    search: '<circle cx="7" cy="7" r="3.75"/><path d="m10 10 3 3"/>',
    send: SEND,
    sent: SEND,
    start: '<path d="M3.5 3v10M12.5 3.5 6 8l6.5 4.5z"/>',
    subtract: '<path d="M3 8h10"/>',
    unfold: '<path d="M3 8h10M5.5 5.25 8 2.75l2.5 2.5M5.5 10.75 8 13.25l2.5-2.5"/>',
    undo: '<path d="M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1"/>',
    up: '<path d="m4 9.75 4-4 4 4"/>',
    waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>'
  };
  var SVG = "http://www.w3.org/2000/svg";
  var iconMarkup = (icon) => {
    const markup = ICONS[icon];
    if (!markup) throw new TypeError(`Unknown Leaf icon: ${icon}`);
    return markup;
  };
  function iconElement(icon, className = "lf-margin-entry-icon") {
    const svg2 = document.createElementNS(SVG, "svg");
    svg2.setAttribute("viewBox", "0 0 16 16");
    svg2.setAttribute("focusable", "false");
    svg2.setAttribute("aria-hidden", "true");
    svg2.setAttribute("class", className);
    svg2.dataset.lfIcon = icon;
    svg2.innerHTML = iconMarkup(icon);
    return svg2;
  }
  var ACTIONS = {
    accept: { name: "Accept", icon: "check" },
    add: { name: "Add", icon: "add" },
    arrange: { name: "Arrange", icon: "arrange" },
    cancel: { name: "Cancel", icon: "cross" },
    close: { name: "Close", icon: "cross" },
    collapse: { name: "Collapse", icon: "collapse" },
    comment: { name: "Comment", icon: "comment" },
    copy: { name: "Copy", icon: "copy" },
    "copy-link": { name: "Copy link", icon: "link" },
    dictate: { name: "Dictate", icon: "microphone" },
    discard: { name: "Discard", icon: "cross" },
    done: { name: "Done", icon: "checked" },
    edit: { name: "Edit", icon: "edit" },
    expand: { name: "Expand", icon: "expand" },
    find: { name: "Find", icon: "search" },
    "collapse-all": { name: "Collapse all", icon: "fold" },
    "expand-all": { name: "Expand all", icon: "unfold" },
    fit: { name: "Fit", icon: "fit" },
    minimize: { name: "Minimize", icon: "subtract" },
    more: { name: "More options", icon: "more" },
    next: { name: "Next", icon: "next" },
    // A find bar's steps run up and down its matches, as a browser's do.
    "next-match": { name: "Next match", icon: "down" },
    "on-me": { name: "On me", icon: "inbox" },
    pause: { name: "Pause", icon: "pause" },
    play: { name: "Play", icon: "play" },
    previous: { name: "Previous", icon: "previous" },
    "previous-match": { name: "Previous match", icon: "up" },
    react: { name: "Add reaction", icon: "reaction" },
    remove: { name: "Remove", icon: "cross" },
    reject: { name: "Reject", icon: "cross" },
    reopen: { name: "Reopen", icon: "check" },
    reset: { name: "Reset", icon: "retry" },
    resolve: { name: "Resolve", icon: "check" },
    retry: { name: "Retry", icon: "retry" },
    save: { name: "Save", icon: "save" },
    send: { name: "Send", icon: "send" },
    show: { name: "Show", icon: "locate" },
    start: { name: "Start", icon: "start" },
    suggest: { name: "Suggest", icon: "edit" },
    undo: { name: "Undo", icon: "undo" },
    "zoom-in": { name: "Zoom in", icon: "add" },
    "zoom-out": { name: "Zoom out", icon: "subtract" }
  };
  var actionIcon = (action) => {
    const named = ACTIONS[action];
    if (!named) throw new TypeError(`Unknown Leaf action: ${action}`);
    return named.icon;
  };
  var actionName = (action) => {
    actionIcon(action);
    return ACTIONS[action].name;
  };
  var SYMBOLIC = /* @__PURE__ */ new Set(["symbol", "mark"]);
  function actionFace(role, label, action) {
    if (!SYMBOLIC.has(role)) {
      if (action !== void 0)
        throw new TypeError(`A ${role} says its label and shows no action's symbol`);
      return label;
    }
    if (action === void 0) throw new TypeError(`A ${role} names the action it shows`);
    const name = actionName(action);
    return label ?? name;
  }
  function showAction(control, action, className = "lf-action-icon") {
    const icon = actionIcon(action);
    const drawn = control.querySelector(":scope > svg[data-lf-icon]");
    if (drawn?.getAttribute("data-lf-icon") === icon) return;
    const symbol = iconElement(icon, className);
    if (drawn) drawn.replaceWith(symbol);
    else control.prepend(symbol);
  }
  var drawAction = (node, role, action) => showAction(node, action, role === "mark" ? "lf-mark-icon" : "lf-action-icon");
  function actionOffers(base) {
    const titled = (title) => title === void 0 ? void 0 : { title };
    return {
      /**
       * @param {LeafActionRole} role @param {string} [className] @param {string} [label]
       * @param {{title?: string, action?: string}} [options]
       */
      offerAction(role, className, label, { title, action } = {}) {
        const node = base.offerAction(
          role,
          className,
          actionFace(role, label, action),
          titled(title)
        );
        if (SYMBOLIC.has(role)) drawAction(node, role, action);
        return node;
      },
      /**
       * @template {Element} T
       * @param {T} node @param {LeafActionRole} role @param {string} [className]
       * @param {string} [label] @param {{title?: string, action?: string}} [options]
       */
      offerActionElement(node, role, className, label, { title, action } = {}) {
        base.offerActionElement(
          node,
          role,
          className,
          actionFace(role, label, action),
          titled(title)
        );
        if (SYMBOLIC.has(role)) drawAction(node, role, action);
        return node;
      }
    };
  }

  // packages/playground/initial/lf-playground.js
  var own = (root, tag) => [...root.querySelectorAll(`:scope > ${tag}`)];
  var belongsTo = (host, member) => member.parentElement.closest("lf-playground, [data-lf-exhibit]") === host;
  var ownControls = (host, preview) => [
    ...own(host, "lf-playground-control"),
    ...[...preview?.querySelectorAll("lf-playground-control") ?? []].filter(
      (control) => belongsTo(host, control)
    )
  ];
  function createPlayground(host, tools) {
    const { tabStore, offerElement, generatedElement } = tools;
    const { offerActionElement } = actionOffers(tools);
    const presets = own(host, "lf-playground-preset");
    const outputs = own(host, "lf-playground-output");
    const previews = own(host, "lf-playground-preview");
    const controls = ownControls(host, previews[0]);
    if (!controls.length || outputs.length !== 1 || previews.length !== 1)
      throw new Error("playground needs controls, one preview and one output");
    const output = outputs[0], preview = previews[0];
    const controlByName = /* @__PURE__ */ new Map();
    const choicesByName = /* @__PURE__ */ new Map();
    for (const control of controls) {
      const name = control.getAttribute("name"), kind = control.getAttribute("kind");
      const choices = own(control, "lf-playground-choice");
      if (kind === "choice" !== Boolean(choices.length))
        throw new Error(`control ${name} needs choices only for kind choice`);
      choicesByName.set(name, choices);
      controlByName.set(name, control);
    }
    const parse = (control, raw) => {
      const name = control.getAttribute("name"), kind = control.getAttribute("kind");
      if (kind === "range") {
        const value = Number(raw), min = Number(control.getAttribute("min"));
        const max = Number(control.getAttribute("max")), step = Number(control.getAttribute("step") ?? "1");
        if (!Number.isFinite(value) || min >= max || value < min || value > max)
          throw new Error(`control ${name} has a value outside its range`);
        if (Math.abs((value - min) / step - Math.round((value - min) / step)) > 1e-9)
          throw new Error(`control ${name} has a value off its step`);
        return value;
      }
      if (kind === "toggle") {
        if (!["true", "false"].includes(raw))
          throw new Error(`toggle control ${name} needs true or false`);
        return raw === "true";
      }
      if (typeof raw !== "string") throw new Error(`control ${name} needs text`);
      if (kind === "choice" && !choicesByName.get(name).some((choice) => choice.getAttribute("value") === raw))
        throw new Error(`control ${name} has no choice ${raw}`);
      if (kind === "color") {
        if (!/^#[0-9a-f]{6}$/i.test(raw))
          throw new Error(`color control ${name} needs #rrggbb`);
        return raw.toLowerCase();
      }
      return raw;
    };
    const typed = (control, value) => {
      const name = control.getAttribute("name"), kind = control.getAttribute("kind");
      const type = kind === "range" ? "number" : kind === "toggle" ? "boolean" : "string";
      if (typeof value !== type) throw new Error(`control ${name} needs a ${type}`);
      return parse(control, String(value));
    };
    const defaults = Object.freeze(
      Object.fromEntries(
        controls.map((control) => [
          control.getAttribute("name"),
          parse(control, control.getAttribute("value"))
        ])
      )
    );
    const key = `lf-playground:${host.id}`;
    let storedCandidate = null;
    try {
      const stored = tabStore.get(key);
      if (stored !== null) {
        storedCandidate = JSON.parse(stored);
        if (!storedCandidate || typeof storedCandidate !== "object" || Array.isArray(storedCandidate))
          throw new Error("invalid stored configuration");
      }
    } catch {
      storedCandidate = null;
      tabStore.set(key, null);
    }
    let values;
    try {
      values = Object.freeze(
        Object.fromEntries(
          controls.map((control) => {
            const name = control.getAttribute("name");
            const value = Object.hasOwn(storedCandidate ?? {}, name) ? storedCandidate[name] : defaults[name];
            return [name, typed(control, value)];
          })
        )
      );
    } catch {
      storedCandidate = null;
      tabStore.set(key, null);
      values = defaults;
    }
    const interactive = !host.closest("[data-lf-exhibit]");
    const authored = [...host.childNodes];
    const railed = controls.filter((control) => control.parentElement === host);
    const candidates = /* @__PURE__ */ new Set();
    const bodies = /* @__PURE__ */ new Map();
    for (const [name, choices] of choicesByName) {
      if (choices.some(
        (choice) => [...choice.childNodes].some(
          (child) => child.nodeType === Node.ELEMENT_NODE || child.nodeType === Node.TEXT_NODE && child.data.trim()
        )
      ))
        candidates.add(controlByName.get(name));
      for (const choice of choices) bodies.set(choice, [...choice.childNodes]);
    }
    host.classList.toggle("lf-playground-quoted", !interactive);
    for (const control of controls) {
      if (candidates.has(control)) control.classList.add("lf-playground-candidates");
      if (interactive)
        control.classList.add(`lf-playground-${control.getAttribute("kind")}`);
    }
    if (!interactive) {
      const bare = new Set(controls.filter((control) => !candidates.has(control)));
      const holdsOnlyBare = (box) => [...box.childNodes].every(
        (child) => child.nodeType === Node.TEXT_NODE ? !child.data.trim() : child.nodeType === Node.COMMENT_NODE || bare.has(child)
      );
      for (const control of bare)
        for (let box = control.parentElement; box !== preview && box !== host && !bare.has(box) && holdsOnlyBare(box); box = box.parentElement)
          bare.add(box);
      for (const hidden of [...bare, ...presets]) hidden.hidden = true;
    }
    const presetSettings = new Map(
      presets.map((preset) => {
        const settings = own(preset, "lf-playground-setting");
        if (!settings.length)
          throw new Error(`preset ${preset.getAttribute("label")} is empty`);
        return [
          preset,
          Object.freeze(
            Object.fromEntries(
              settings.map((setting) => {
                const name = setting.getAttribute("for");
                return [
                  name,
                  parse(controlByName.get(name), setting.getAttribute("value"))
                ];
              })
            )
          )
        ];
      })
    );
    const formatted = (control, value) => `${value}${control.getAttribute("unit") ?? ""}`;
    const slots = [...output.querySelectorAll("lf-playground-value")].filter(
      (slot) => belongsTo(host, slot)
    );
    for (const slot of slots) generatedElement(slot, { says: true });
    const presetWords = new Map(
      presets.map((preset) => [preset, [...preset.childNodes]])
    );
    for (const root of [...controls, ...bodies.keys(), ...presets, ...slots])
      root.replaceChildren();
    host.replaceChildren();
    const offered = (apply) => ref((element) => {
      if (element) apply(element);
    });
    const inputOffer = offered((element) => offerElement(element, "lf-playground-input"));
    const radioOffer = offered((element) => offerElement(element, ""));
    const action = (role, cls, label, options) => offered((element) => offerActionElement(element, role, cls, label, options));
    const resetOffer = action("symbol", "lf-playground-reset", void 0, {
      action: "reset"
    });
    const revealOffer = action("symbol", "lf-playground-reveal", "Show instruction", {
      action: "more"
    });
    const submitOffer = action("commit", "lf-playground-submit");
    const presetOffer = action("word", "lf-playground-preset");
    const nativeInputs = (control) => [
      ...control.querySelectorAll(
        ":scope > input, :scope > select, :scope > .choice > input, :scope > .lf-playground-choices > lf-playground-choice > .choice > input"
      )
    ];
    const split = () => host.querySelector(":scope > .lf-playground-split");
    const actions = () => split()?.querySelector(
      ":scope > .lf-playground-rail > .lf-playground-instruction-region > .lf-playground-actions"
    );
    const instructionId = `${host.id}-instruction`;
    const submitLabel = host.getAttribute("submit-label") ?? "Use these settings";
    const offline = Boolean(document.querySelector("script[data-lf-offline]"));
    const presetBar = () => !presets.length ? nothing : railed.length ? html`<header
            class="lf-playground-presets"
            role="group"
            aria-label="Starting points"
          >
            ${presets}
          </header>` : html`<div
            class="lf-playground-presets"
            role="group"
            aria-label="Starting points"
          >
            ${presets}
          </div>`;
    const controlsPane = () => html` <div
      class="lf-playground-controls-region"
      data-lf-reading-role="pane"
      data-lf-generated
      role="region"
      aria-label="Controls"
    >
      ${presetBar()}${railed.length ? html`<div class="lf-playground-controls" role="group" aria-label="Controls">
              ${railed}
            </div>` : nothing}
    </div>`;
    const view = {
      controls,
      controlByName,
      presets,
      presetSettings,
      defaults,
      values,
      storedCandidate,
      output,
      preview,
      parse,
      typed,
      copy: null,
      get submit() {
        return actions()?.querySelector(":scope > .lf-playground-submit") ?? null;
      },
      get reset() {
        return actions()?.querySelector(":scope > .lf-playground-reset") ?? null;
      },
      get reveal() {
        return actions()?.querySelector(":scope > .lf-playground-reveal") ?? null;
      },
      get instruction() {
        return actions()?.querySelector(":scope > .lf-playground-instruction") ?? null;
      },
      get presetButtons() {
        return new Map(
          presets.map((preset) => [preset, preset.querySelector(":scope > button")])
        );
      },
      get regions() {
        return [
          [
            "controls",
            ":scope > .lf-playground-controls-region, :scope > .lf-playground-rail > .lf-playground-controls-region",
            railed.length ? ".lf-playground-controls" : ".lf-playground-presets"
          ],
          [
            "instruction",
            ":scope > .lf-playground-rail > .lf-playground-instruction-region",
            ".lf-playground-actions"
          ],
          ["rail", ":scope > .lf-playground-rail", null],
          [
            "preview",
            ":scope > .lf-playground-preview-region",
            ".lf-playground-preview-body"
          ]
        ].flatMap(([name, selector, body]) => {
          const region = split()?.querySelector(selector);
          return region ? [{ name, host: region, body: body ? region.querySelector(body) : region }] : [];
        });
      },
      isInput(control, target) {
        return nativeInputs(control).includes(target);
      },
      readInput(control) {
        const inputs = nativeInputs(control), input = inputs[0];
        return input.type === "radio" ? inputs.find((radio) => radio.checked)?.value : control.getAttribute("kind") === "toggle" ? input.checked : input.value;
      },
      reflection(next) {
        const attributes = {}, properties = {};
        for (const [name, value] of Object.entries(next)) {
          const control = controlByName.get(name);
          if (!control) continue;
          attributes[`data-playground-${name}`] = String(value);
          const content = formatted(control, value);
          properties[`--playground-${name}`] = control.getAttribute("kind") === "text" ? JSON.stringify(content) : content;
        }
        return { attributes, properties };
      },
      render({ values: next = values, instruction = null, chosen = () => false } = {}) {
        if (instruction === null) {
          for (const slot of slots)
            render(
              html`${formatted(
                controlByName.get(slot.getAttribute("for")),
                next[slot.getAttribute("for")]
              )}`,
              slot
            );
        } else {
          if (!output.hasAttribute("data-lf-gen")) {
            output.replaceChildren();
            generatedElement(output, { says: true });
          }
          render(html`${instruction}`, output);
        }
        for (const control of controls) {
          const name = control.getAttribute("name"), kind = control.getAttribute("kind"), label = control.getAttribute("label");
          const choices = choicesByName.get(name);
          const select = kind === "choice" && control.getAttribute("appearance") === "select";
          if (!select)
            for (const choice of choices)
              render(
                html`
                ${interactive ? html`<label class="choice" data-lf-gen="1"
                        ><input
                          ${radioOffer}
                          type="radio"
                          name=${`${host.id}-${name}`}
                          value=${choice.getAttribute("value")}
                          .checked=${next[name] === choice.getAttribute("value")}
                        /><span class="lf-playground-choice-label" data-lf-gen="1"
                          >${choice.getAttribute("label")}</span
                        ></label
                      >` : html`<p class="lf-playground-choice-heading" data-lf-gen="1">
                        ${choice.getAttribute("label")}
                      </p>`}
                ${candidates.has(control) ? html`<div class="lf-playground-choice-preview">
                        ${bodies.get(choice)}
                      </div>` : nothing}
              `,
                choice
              );
          if (!interactive) {
            render(html`${choices}`, control);
            continue;
          }
          const field = html`<input
          type=${kind === "toggle" ? "checkbox" : kind}
          ${inputOffer}
          id=${`${host.id}-${name}-input`}
          name=${`${host.id}-${name}`}
          aria-label=${label}
          role=${kind === "toggle" ? "switch" : nothing}
          min=${control.getAttribute("min") ?? nothing}
          max=${control.getAttribute("max") ?? nothing}
          step=${control.getAttribute("step") ?? nothing}
          placeholder=${control.getAttribute("placeholder") ?? nothing}
          .checked=${kind === "toggle" ? next[name] : false}
          .value=${kind === "toggle" ? "on" : next[name]}
        />`;
          render(
            html`<span class="lf-playground-control-label" data-lf-gen="1">${label}</span>
            ${select ? html`<select
                    ${inputOffer}
                    name=${`${host.id}-${name}`}
                    aria-label=${label}
                    .value=${next[name]}
                  >
                    ${choices.map(
              (choice) => html`<option
                          value=${choice.getAttribute("value")}
                          .selected=${next[name] === choice.getAttribute("value")}
                        >
                          ${choice.getAttribute("label")}
                        </option>`
            )}
                  </select>` : kind === "choice" ? html`<div
                      class="lf-playground-input lf-playground-choices"
                      role="radiogroup"
                      aria-label=${label}
                    >
                      ${choices}
                    </div>` : kind === "toggle" ? html`<label class="choice" data-lf-gen="1">${field}</label>` : field}
            ${kind === "range" ? html`<output class="lf-playground-reading"
                    >${formatted(control, next[name])}</output
                  >` : nothing} `,
            control
          );
        }
        if (!interactive) return html`${authored}`;
        for (const preset of presets)
          render(
            html`${presetWords.get(preset)}<button
              ${presetOffer}
              aria-pressed=${Object.entries(presetSettings.get(preset)).every(
              ([name, value]) => Object.is(next[name], value)
            )}
            >
              ${preset.getAttribute("label")}
            </button>`,
            preset
          );
        return html`<div class="lf-playground-split">
        ${!railed.length && presets.length ? controlsPane() : nothing}
        <div
          class="lf-playground-preview-region"
          data-lf-reading-role="pane"
          data-lf-generated
          role="region"
          aria-label="Preview"
        >
          <div class="lf-playground-preview-body">${preview}</div>
        </div>
        <div class="lf-playground-rail" data-lf-track>
          ${railed.length ? controlsPane() : nothing}
          <div
            class="lf-playground-instruction-region"
            data-lf-reading-role="pane"
            data-lf-generated
            role="region"
            aria-label="Instruction to agent"
          >
            <footer class="lf-playground-actions">
              <button ${resetOffer}></button>
              <button
                ${revealOffer}
                popovertarget=${instructionId}
                aria-controls=${instructionId}
                aria-expanded="false"
              ></button>
              <button ${submitOffer} data-room=${`${submitLabel}
Undo choice`}>
                <span data-lf-gen="1">${chosen() ? "Undo choice" : submitLabel}</span>
              </button>
              <div
                class="lf-playground-instruction"
                id=${instructionId}
                popover="auto"
                role="dialog"
                aria-labelledby=${`${instructionId}-title`}
              >
                <div class="lf-playground-instruction-head">
                  <p
                    class="lf-playground-instruction-title lf-label"
                    id=${`${instructionId}-title`}
                    data-lf-gen="1"
                  >
                    Instruction to agent
                  </p>
                  ${view.copy ?? nothing}
                </div>
                <div class="lf-playground-instruction-body">${output}</div>
              </div>
              ${offline ? html`<span class="lf-playground-unavailable" data-lf-gen="1"
                      >Submission unavailable: no agent or server is available.</span
                    >` : nothing}
            </footer>
          </div>
        </div>
      </div>`;
      }
    };
    const initialReflection = view.reflection(values);
    for (const [name, value] of Object.entries(initialReflection.properties))
      host.style.setProperty(name, value);
    for (const [name, value] of Object.entries(initialReflection.attributes))
      host.setAttribute(name, value);
    host.classList.add("lf-rendered");
    return view;
  }
  document.documentElement.lfInitial.register("lf-playground", createPlayground);
})();
