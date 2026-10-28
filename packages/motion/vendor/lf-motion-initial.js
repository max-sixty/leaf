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

  // packages/motion/initial/lf-motion.js
  document.documentElement.lfInitial.register(
    "lf-motion",
    (host, { offerElement, offerActionElement, tabStore, authoredBody }) => {
      const saved = JSON.parse(
        tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}'
      );
      const body = document.createElement("div");
      body.className = "lf-motion-body";
      authoredBody(body);
      const drawing = {};
      const offered = (key, cls) => (node) => {
        if (node) drawing[key] = offerElement(node, cls);
      };
      const controlsRef = offered("controls", "lf-motion-controls");
      const playRef = (node) => {
        if (node) drawing.play = offerActionElement(node, "symbol", "lf-motion-play");
      };
      const timeRef = offered("time", "lf-motion-time");
      const clockRef = offered("clock", "lf-motion-clock");
      const speedLabelRef = offered("speedLabel", "lf-motion-speed");
      const speedRef = offered("speed", "");
      const template = ({
        time = Math.min(Number(host.getAttribute("duration")), saved.time),
        rate = saved.rate,
        label = "Play",
        playing = false
      } = {}) => html`
      <div
        ${ref(controlsRef)}
        role="group"
        aria-label=${host.getAttribute("aria-label")}
      >
        <button ${ref(playRef)} aria-label=${label} title=${label}>
          <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            ${unsafeSVG(ICONS[actionIcon(playing ? "pause" : "play")])}
          </svg>
        </button>
        <input
          ${ref(timeRef)}
          type="range"
          name="time"
          min="0"
          max=${host.getAttribute("duration")}
          step="1"
          aria-label="Time"
          aria-valuetext=${`${Math.round(time)} milliseconds`}
          .value=${live(String(time))}
        />
        <span ${ref(clockRef)}>${Math.round(time)} ms</span>
        <label ${ref(speedLabelRef)}
          >Speed<select ${ref(speedRef)} name="speed">
            ${[1, 0.5, 0.25].map(
        (value) => html`<option value=${value} .selected=${live(rate === value)}>
                  ${value}×
                </option>`
      )}
          </select></label
        >
      </div>
      ${body}
    `;
      return Object.assign(drawing, { render: template });
    }
  );
})();
