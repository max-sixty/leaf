(() => {
  // browser/runtime/motion-icon-paths.js
  var PLAY = '<path d="m5 3 7 5-7 5z"/>';
  var PAUSE = '<path d="M5 3v10M11 3v10"/>';

  // packages/motion/initial/lf-motion.js
  document.documentElement.lfInitial.register(
    "lf-motion",
    (host, { offer, tabStore, authoredBody }) => {
      const saved = JSON.parse(
        tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}'
      );
      const controls = offer("div", "lf-motion-controls");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", host.getAttribute("aria-label"));
      const play = offer("button", "lf-btn lf-motion-play");
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
          symbol.innerHTML = playing ? PAUSE : PLAY;
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
