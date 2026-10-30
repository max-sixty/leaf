/*
 * Browser-side observations for `leaf-dev verify-site`, installed before each navigation.
 * Shared startup evidence is installed separately. Reply readings use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the website-specific Playwright boundary exposed to the Python orchestrator.
 *
 * A reply shows the user one of two ways, in the floating panel's view of its thread
 * or on its card at its passage, and the page records each as it happens, whatever
 * the journey is doing, counting only what is in view by the same measure for both:
 * the reply's own message, or a news notice, on a thread holding the reply back so as
 * not to move what the user reads, changing once the page's applied state holds the
 * reply. The notice's change and the reply's arrival are both on the page's clock.
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

  // `messages`: when each message id came into view; `notices`: each change of what a
  // thread's notice in view says, its going included; `applied`: when the page's
  // applied state first held each event.
  function shown() {
    return {
      messages: {},
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

  // The watch keeps its reading in memory and writes it only when it changes. Each
  // mutation batch adopts the nodes it adds and rereads only the nodes in view.
  function startWatch() {
    if (sessionStorage.getItem(startedKey) === null || watch) return;
    const found = shown();
    let dirty = false;
    const inView = new Set();
    const observed = new WeakSet();
    // A message names its event by `data-mid` or `data-event`, as the reader drawing
    // it does (thread/messages.js).
    const message = ".lf-msg.agent:is([data-mid], [data-event])";
    const selector = `${message}, .lf-thread-news`;
    const note = (table, key, now) => {
      if (table[key] !== undefined) return;
      table[key] = now;
      dirty = true;
    };
    const save = () => {
      if (!dirty) return;
      sessionStorage.setItem(shownKey, JSON.stringify(found));
      dirty = false;
    };
    const record = () => {
      const now = Date.now();
      const said = {};
      for (const node of inView) {
        if (!node.isConnected) {
          inView.delete(node);
          continue;
        }
        if (!node.checkVisibility()) continue;
        if (node.matches(message)) {
          if (node.querySelector(".lf-msg-text")?.textContent.trim())
            note(found.messages, node.dataset.mid ?? node.dataset.event, now);
        } else {
          const thread = drawnThread(node);
          if (thread) said[thread] = node.textContent.trim();
        }
      }
      for (const thread of new Set([
        ...Object.keys(found.notices),
        ...Object.keys(said),
      ])) {
        const notices = found.notices[thread] ?? [];
        const saying = said[thread] ?? null;
        if ((notices.at(-1)?.[0] ?? null) === saying) continue;
        found.notices[thread] = [...notices, [saying, now]];
        dirty = true;
      }
      save();
    };
    const intersections = new IntersectionObserver((entries) => {
      for (const { isIntersecting, target } of entries)
        if (isIntersecting) inView.add(target);
        else inView.delete(target);
      record();
    });
    const adopt = (root) => {
      if (!(root instanceof Element)) return;
      const nodes = root.matches(selector) ? [root] : [];
      for (const node of [...nodes, ...root.querySelectorAll(selector)])
        if (!observed.has(node)) {
          observed.add(node);
          intersections.observe(node);
        }
    };
    const mutations = new MutationObserver((changes) => {
      for (const change of changes)
        if (change.type === "attributes") adopt(change.target);
        else for (const node of change.addedNodes) adopt(node);
      record();
      watchApplied();
    });
    // The page's applied state is the runtime's own reading, which a reply joins when
    // the page has it, whether or not it draws it.
    const apply = (reading) => {
      const now = Date.now();
      for (const event of reading.authoritative?.events ?? [])
        note(found.applied, event.id, now);
      save();
    };
    const watchApplied = () => {
      if (!watch || watch.applied || !document.querySelector("script[data-lf-server]"))
        return;
      watch.applied = runtimeModule("check-api").then((checks) => {
        apply(checks.readApplication());
        if (watch) watch.unsubscribe = checks.watchSemantic(apply);
      });
    };
    watch = { mutations, intersections };
    mutations.observe(document, { attributes: true, childList: true, subtree: true });
    adopt(document.documentElement);
    record();
    watchApplied();
  }

  // The thread a node is drawn in: a card's, or the one the panel's view stands for.
  const drawnThread = (node) => {
    const thread = node.closest(
      ".lf-thread[data-id], [data-lf-thread-view][data-thread]",
    );
    return thread?.dataset.id ?? thread?.dataset.thread ?? null;
  };

  // When the page first showed the user reply `id` in `thread`, and by which sign: its
  // `message` or its thread's `notice`. A notice shows the reply before its message
  // comes into view, so the reading also says when the message itself did
  // (`message`, null while it has not).
  function replyShown({ thread, id }) {
    const found = shown();
    const signs = [["message", found.messages[id]]];
    const applied = found.applied[id];
    if (applied !== undefined)
      for (const [said, at] of found.notices[thread] ?? [])
        if (said !== null && at >= applied) signs.push(["notice", at]);
    const [by, at] = signs
      .filter(([, at]) => at !== undefined)
      .sort((a, b) => a[1] - b[1])[0] ?? [null, null];
    return by === null ? null : { at, by, message: found.messages[id] ?? null };
  }

  // The page's status as the floating panel's leaf names it in every paint, whichever
  // of the field's placeholder, a passing notice or a thread's turn the row shows.
  function status() {
    return document.querySelector(".lf-fp-leaf")?.getAttribute("aria-label") || null;
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
    async activateSession(activation) {
      const client = await runtimeModule("layer-client");
      const response = await fetch(activation, {
        headers: client.layerHeaders(),
        signal: window.AbortSignal.timeout(30_000),
      });
      if (!response.ok || response.headers.get("Leaf-Session") !== "active")
        throw new Error(`Session activation returned HTTP ${response.status}`);
      if (!client.admitResponse(response))
        throw new Error("Session activation belongs to another delivery");
      return response.json();
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
    // What the page shows about a reply the container holds and the page never drew:
    // the reading it last applied, its traffic, and each message's identity.
    visibleReplyDebug() {
      return {
        // The view open in the floating panel: threads, a thread, or none.
        view: document.querySelector(".lf-floating-panel")?.dataset.open ?? null,
        visibility: document.visibilityState,
        presented: document.body.hasAttribute("data-lf-presented"),
        reading: document.body.dataset.lfReading ?? null,
        traffic: document.documentElement.dataset.lfTraffic ?? null,
        revision: document.querySelector('meta[name="lf-revision"]')?.content ?? null,
        status: status(),
        // What each drawn thread shows of itself: a card, or the panel's view.
        threads: [
          ...document.querySelectorAll(
            ".lf-thread[data-id], [data-lf-thread-view][data-thread]",
          ),
        ].map((node) => ({
          id: drawnThread(node),
          inPanel: node.matches("[data-lf-thread-view]"),
          visible: node.checkVisibility(),
          news: node.querySelector(".lf-thread-news")?.textContent.trim() ?? null,
        })),
        shown: shown(),
        messages: [...document.querySelectorAll(".lf-msg")].map((node) => ({
          classes: [...node.classList],
          mid: node.dataset.mid ?? node.dataset.event ?? null,
          attempt: node.dataset.attempt ?? null,
          busy: node.hasAttribute("aria-busy"),
          hasText: Boolean(node.querySelector(".lf-msg-text")?.textContent.trim()),
          visible: node.checkVisibility(),
        })),
      };
    },
    revisionAtLeast(want) {
      return (
        Number(document.querySelector('meta[name="lf-revision"]')?.content) >= want &&
        document
          .querySelector("script[data-lf-entry]")
          ?.lfReadiness?.(null, "presented") === null
      );
    },
    revision() {
      return document.querySelector('meta[name="lf-revision"]')?.content ?? null;
    },
    status,
  };

  Object.defineProperty(window, "__leafVerifier", {
    value: Object.freeze(api),
  });
  startWatch();
})();
