(() => {
  // browser/runtime/icon-paths.js
  var SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';
  var ICONS = {
    activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
    add: '<path d="M8 3v10M3 8h10"/>',
    change: '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
    check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
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

  // packages/motion/initial/lf-motion.js
  document.documentElement.lfInitial.register(
    "lf-motion",
    (host, { offer, offerAction, tabStore, authoredBody }) => {
      const saved = JSON.parse(
        tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}'
      );
      const controls = offer("div", "lf-motion-controls");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", host.getAttribute("aria-label"));
      const play = offerAction("symbol", "lf-motion-play");
      const symbol = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      symbol.setAttribute("viewBox", "0 0 16 16");
      symbol.setAttribute("aria-hidden", "true");
      symbol.setAttribute("focusable", "false");
      play.append(symbol);
      let lastLabel;
      let lastPlaying;
      const paintPlay = (label, playing) => {
        if (label !== lastLabel) {
          play.setAttribute("aria-label", label);
          play.title = label;
          lastLabel = label;
        }
        if (playing !== lastPlaying) {
          symbol.innerHTML = playing ? ICONS.pause : ICONS.play;
          lastPlaying = playing;
        }
      };
      paintPlay("Play", false);
      const time = offer("input", "lf-motion-time", null, "range");
      time.name = "time";
      time.min = "0";
      time.max = host.getAttribute("duration");
      time.step = "1";
      time.value = String(Math.min(Number(time.max), saved.time));
      time.setAttribute("aria-label", "Time");
      const clock = offer(
        "span",
        "lf-motion-clock",
        `${Math.round(Number(time.value))} ms`
      );
      const speedLabel = offer("label", "lf-motion-speed", "Speed");
      const speed = offer("select", "", null);
      speed.name = "speed";
      for (const rate of [1, 0.5, 0.25]) {
        const option = document.createElement("option");
        option.value = String(rate);
        option.textContent = `${rate}\xD7`;
        speed.append(option);
      }
      speed.value = String(saved.rate);
      speedLabel.append(speed);
      controls.append(play, time, clock, speedLabel);
      const body = document.createElement("div");
      body.className = "lf-motion-body";
      host.append(controls, authoredBody(body));
      return { controls, play, paintPlay, time, clock, speed };
    }
  );
})();
