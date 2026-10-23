(() => {
  // packages/motion/initial/lf-motion.js
  document.documentElement.lfInitial.register(
    "lf-motion",
    (host, { offer, tabStore }) => {
      const saved = JSON.parse(
        tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}'
      );
      const controls = offer("div", "lf-motion-controls");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", host.getAttribute("aria-label"));
      const play = offer("button", "lf-btn lf-motion-play");
      const room = offer("span", "");
      room.dataset.lfRoom = "Play\nPause\nShow end";
      const playLabel = offer("span", "", "Play");
      room.append(playLabel);
      play.append(room);
      const replay = offer("button", "lf-btn lf-motion-replay", "Replay");
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
      controls.append(replay, play, time, clock, speedLabel);
      const body = document.createElement("div");
      body.className = "lf-motion-body";
      body.append(...host.childNodes);
      host.append(controls, body);
      return { controls, replay, play, playLabel, time, clock, speed };
    }
  );
})();
