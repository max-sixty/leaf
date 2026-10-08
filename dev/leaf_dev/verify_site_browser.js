/*
 * Browser-side observations for `leaf-dev verify-site`, installed before each navigation.
 * Shared startup evidence is installed separately. Reply readings use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the website-specific Playwright boundary exposed to the Python orchestrator.
 *
 * A reply shows the user one of three ways, in the Threads panel or on a card at its
 * passage, and the page records each as it happens, whatever the journey is doing,
 * counting only what is in view by the same measure for all three: the reply's own
 * message; a thread's row, open or folded, dating its latest message activity at or
 * after the reply, since a folded thread draws no messages; or a news notice, on a
 * thread holding the reply back so as not to move what the user reads, changing once
 * the page's applied state holds the reply. Each compares like clocks: the row's date
 * with the reply's, both the server's, and the notice's change with the reply's
 * arrival, both the page's.
 */
(() => {
  const startedKey = "leaf-visible-reply-started";
  const shownKey = "leaf-reply-shown";
  let activationCount = 0;
  let watch = null;
  function serverScript() {
    const script = document.querySelector("script[data-lf-server]");
    if (!script) throw new Error("Leaf server script is missing");
    return script;
  }

  // `messages`: when each message id came into view; `rows`: when each thread's row in
  // view first dated its latest activity at each instant; `notices`: each change of
  // what a thread's notice in view says, its going included; `applied`: when the
  // page's applied state first held each event.
  function shown() {
    return {
      messages: {},
      rows: {},
      notices: {},
      applied: {},
      ...JSON.parse(sessionStorage.getItem(shownKey) ?? "{}"),
    };
  }

  function stopWatch() {
    watch?.mutations.disconnect();
    watch?.intersections.disconnect();
    watch?.unsubscribe?.();
    watch = null;
  }

  function startWatch() {
    if (sessionStorage.getItem(startedKey) === null || watch) return;
    const inView = new WeakSet();
    const observed = new WeakSet();
    const record = () => {
      const found = shown();
      const now = Date.now();
      const seen = (node) => inView.has(node) && node.checkVisibility();
      for (const message of document.querySelectorAll(".lf-msg.agent[data-mid]")) {
        const id = message.dataset.mid;
        if (
          found.messages[id] === undefined &&
          seen(message) &&
          message.querySelector(".lf-msg-text")?.textContent.trim()
        )
          found.messages[id] = now;
      }
      for (const row of document.querySelectorAll(
        ".lf-thread[data-id] > .lf-thread-summary",
      )) {
        const thread = row.parentElement.dataset.id;
        const latest = row
          .querySelector(".lf-thread-recency")
          ?.getAttribute("datetime");
        found.rows[thread] ??= {};
        if (latest && found.rows[thread][latest] === undefined && seen(row))
          found.rows[thread][latest] = now;
      }
      for (const node of document.querySelectorAll(".lf-thread[data-id]")) {
        const thread = node.dataset.id;
        const notice = node.querySelector(".lf-thread-news");
        const said = notice && seen(notice) ? notice.textContent.trim() : null;
        const notices = found.notices[thread] ?? [];
        if ((notices.at(-1)?.[0] ?? null) !== said)
          found.notices[thread] = [...notices, [said, now]];
      }
      sessionStorage.setItem(shownKey, JSON.stringify(found));
    };
    const intersections = new IntersectionObserver((entries) => {
      for (const { isIntersecting, target } of entries)
        if (isIntersecting) inView.add(target);
        else inView.delete(target);
      record();
    });
    const observe = () => {
      for (const node of document.querySelectorAll(
        ".lf-msg.agent[data-mid], .lf-thread[data-id] > .lf-thread-summary, .lf-thread-news",
      ))
        if (!observed.has(node)) {
          observed.add(node);
          intersections.observe(node);
        }
      record();
      watchApplied();
    };
    const mutations = new MutationObserver(observe);
    watch = { mutations, intersections };
    mutations.observe(document, { attributes: true, childList: true, subtree: true });
    observe();
  }

  // The page's applied state is the runtime's own reading, which a reply joins when
  // the page has it, whether or not it draws it.
  function watchApplied() {
    if (!watch || watch.applied || !document.querySelector("script[data-lf-server]"))
      return;
    watch.applied = runtimeModule("semantic-state").then((semantic) => {
      const apply = (reading) => {
        const found = shown();
        const now = Date.now();
        for (const event of reading.authoritative?.events ?? [])
          found.applied[event.id] ??= now;
        sessionStorage.setItem(shownKey, JSON.stringify(found));
      };
      apply(semantic.readApplication());
      if (watch) watch.unsubscribe = semantic.watchSemantic(apply);
    });
  }

  // When the page first showed the user reply `id`, admitted at `ts` in `thread`, and
  // by which sign: its `message`, its thread's `row`, or its thread's `notice`.
  function replyShown({ thread, id, ts }) {
    const found = shown();
    const signs = [["message", found.messages[id]]];
    for (const [latest, at] of Object.entries(found.rows[thread] ?? {}))
      if (Date.parse(latest) >= Date.parse(ts)) signs.push(["row", at]);
    const applied = found.applied[id];
    if (applied !== undefined)
      for (const [said, at] of found.notices[thread] ?? [])
        if (said !== null && at >= applied) signs.push(["notice", at]);
    const [by, at] = signs
      .filter(([, at]) => at !== undefined)
      .sort((a, b) => a[1] - b[1])[0] ?? [null, null];
    return by === null ? null : { at, by };
  }

  async function runtimeModule(name) {
    const script = serverScript();
    const moduleUrl = new URL(
      `runtime/${name}.js`,
      new URL(script.dataset.lfEntry, location.origin),
    );
    return import(moduleUrl.href);
  }

  const api = {
    identity() {
      const script = serverScript();
      return {
        layer: script.dataset.lfLayer,
        release: script.dataset.lfRelease,
      };
    },
    async scopedMedia() {
      const script = serverScript();
      const media = await runtimeModule("media");
      return {
        path: media.scopedMediaUrl("/media/0123456789abcdef.png"),
        root: script.dataset.lfPageRoot,
      };
    },
    observeCrossTabActivation() {
      activationCount = 0;
      document.addEventListener("lf-session-active", () => activationCount++);
    },
    async activateSession() {
      const client = await runtimeModule("layer-client");
      client.admitResponse(
        new Response(null, { headers: { "Leaf-Session": "active" } }),
      );
    },
    crossTabActivated() {
      return activationCount === 1;
    },
    startVisibleReplyClock() {
      const started = Date.now();
      sessionStorage.setItem(startedKey, String(started));
      sessionStorage.removeItem(shownKey);
      stopWatch();
      startWatch();
      return started;
    },
    replyShownAt: replyShown,
    // What the page shows about a reply the container holds and the panel never drew:
    // the reading it last applied, its traffic, and each message's identity.
    visibleReplyDebug() {
      return {
        panel: document.querySelector(".lf-thread-panel")?.checkVisibility() ?? null,
        visibility: document.visibilityState,
        presented: document.body.hasAttribute("data-lf-presented"),
        reading: document.body.dataset.lfReading ?? null,
        traffic: document.documentElement.dataset.lfTraffic ?? null,
        revision: document.querySelector('meta[name="lf-revision"]')?.content ?? null,
        status: document.querySelector(".lf-status-text")?.textContent?.trim() || null,
        // What each thread shows of itself, and what the page recorded of it.
        threads: [...document.querySelectorAll(".lf-thread[data-id]")].map((node) => ({
          id: node.dataset.id,
          inPanel: Boolean(node.closest(".lf-threads")),
          open: node.hasAttribute("open"),
          visible: node.checkVisibility(),
          latest:
            node
              .querySelector(":scope > .lf-thread-summary .lf-thread-recency")
              ?.getAttribute("datetime") ?? null,
          news: node.querySelector(".lf-thread-news")?.textContent.trim() ?? null,
        })),
        shown: shown(),
        messages: [...document.querySelectorAll(".lf-msg")].map((node) => ({
          classes: [...node.classList],
          mid: node.dataset.mid ?? null,
          attempt: node.dataset.attempt ?? null,
          busy: node.hasAttribute("aria-busy"),
          hasText: Boolean(node.querySelector(".lf-msg-text")?.textContent.trim()),
          visible: node.checkVisibility(),
        })),
      };
    },
    revisionAtLeast(want) {
      return (
        Number(document.querySelector('meta[name="lf-revision"]')?.content) >= want
      );
    },
    revision() {
      return document.querySelector('meta[name="lf-revision"]')?.content ?? null;
    },
    status() {
      return document.querySelector(".lf-status-text")?.textContent?.trim() || null;
    },
  };

  Object.defineProperty(window, "__leafVerifier", {
    value: Object.freeze(api),
  });
  startWatch();
})();
