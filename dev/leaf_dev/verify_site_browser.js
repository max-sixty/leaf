/*
 * Browser-side observations for `leaf-dev verify-site`, installed before each navigation.
 * Shared startup evidence is installed separately. Visible-reply timestamps use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the website-specific Playwright boundary exposed to the Python orchestrator.
 *
 * A reply shows the user one of three ways, in the Threads panel or on a card at its
 * passage, and the page records each as it happens, whatever the journey is doing:
 * the reply's own message coming into view in an open thread; a thread's row in the panel, open or folded, dating its latest message
 * activity at or after the reply, since a folded thread draws no messages; or a news
 * notice on a thread holding the reply back, so as not to move what the user reads,
 * changing what it says after the reply was admitted. Only the last compares the
 * page's clock with the server's.
 */
(() => {
  const visibleReplyStartedKey = "leaf-visible-reply-started";
  const visibleReplyAtKey = "leaf-visible-reply-at";
  const threadActivityAtKey = "leaf-thread-activity-at";
  let activationCount = 0;
  let visibleReplyObservers = null;
  function serverScript() {
    const script = document.querySelector("script[data-lf-server]");
    if (!script) throw new Error("Leaf server script is missing");
    return script;
  }

  function stopVisibleReplyWatch() {
    visibleReplyObservers?.mutations.disconnect();
    visibleReplyObservers?.intersections.disconnect();
    visibleReplyObservers = null;
  }

  function visibleReplies() {
    return JSON.parse(sessionStorage.getItem(visibleReplyAtKey) ?? "{}");
  }

  function threadActivity() {
    return JSON.parse(sessionStorage.getItem(threadActivityAtKey) ?? "{}");
  }

  // When each thread's row first dated its latest message activity at each instant.
  function recordThreadActivity() {
    const found = threadActivity();
    let changed = false;
    for (const recency of document.querySelectorAll(
      ".lf-thread[data-id] > .lf-thread-summary .lf-thread-recency[datetime]",
    )) {
      const thread = recency.closest(".lf-thread").dataset.id;
      const latest = recency.getAttribute("datetime");
      if (found[thread]?.[latest] !== undefined || !recency.checkVisibility()) continue;
      found[thread] = { ...found[thread], [latest]: Date.now() };
      changed = true;
    }
    // A thread's notice is recorded each time what it says changes, its going
    // included, at the page's own time.
    for (const node of document.querySelectorAll(".lf-thread[data-id]")) {
      const thread = node.dataset.id;
      const notice = node.querySelector(".lf-thread-news");
      const said = notice?.checkVisibility() ? notice.textContent.trim() : null;
      const notices = found[thread]?.news ?? [];
      if ((notices.at(-1)?.[0] ?? null) === said) continue;
      found[thread] = { ...found[thread], news: [...notices, [said, Date.now()]] };
      changed = true;
    }
    if (changed) sessionStorage.setItem(threadActivityAtKey, JSON.stringify(found));
  }

  function watchVisibleAgentReply() {
    const started = sessionStorage.getItem(visibleReplyStartedKey);
    if (started === null || visibleReplyObservers) return;

    // A streamed draft and its durable answer reuse the same message node. Observing
    // that node once would keep the stream's id even after its data-mid changes.
    const seen = new WeakMap();
    const intersections = new IntersectionObserver((entries) => {
      const replies = visibleReplies();
      for (const { isIntersecting, target } of entries) {
        const id = target.dataset.mid;
        if (
          !isIntersecting ||
          !id ||
          replies[id] ||
          !target.querySelector(".lf-msg-text")?.textContent.trim() ||
          !target.checkVisibility()
        )
          continue;
        replies[id] = Date.now();
        intersections.unobserve(target);
      }
      sessionStorage.setItem(visibleReplyAtKey, JSON.stringify(replies));
    });
    const observe = () => {
      recordThreadActivity();
      for (const message of document.querySelectorAll(
        ".lf-thread .lf-msg.agent[data-mid]",
      )) {
        if (
          seen.get(message) !== message.dataset.mid &&
          message.querySelector(".lf-msg-text")?.textContent.trim()
        ) {
          if (seen.has(message)) intersections.unobserve(message);
          seen.set(message, message.dataset.mid);
          intersections.observe(message);
        }
      }
    };
    const mutations = new MutationObserver(observe);
    visibleReplyObservers = { mutations, intersections };
    mutations.observe(document, {
      attributes: true,
      childList: true,
      subtree: true,
    });
    observe();
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
      sessionStorage.setItem(visibleReplyStartedKey, String(started));
      sessionStorage.removeItem(visibleReplyAtKey);
      sessionStorage.removeItem(threadActivityAtKey);
      stopVisibleReplyWatch();
      watchVisibleAgentReply();
      return started;
    },
    visibleReplyRecorded(id) {
      return visibleReplies()[id] !== undefined;
    },
    // When the user was first shown reply `id`, admitted at `ts`, in `thread`.
    replyShownAt({ thread, id, ts }) {
      const shown = [visibleReplies()[id]];
      const { news = [], ...activity } = threadActivity()[thread] ?? {};
      for (const [latest, at] of Object.entries(activity))
        if (Date.parse(latest) >= Date.parse(ts)) shown.push(at);
      for (const [said, at] of news)
        if (said !== null && at >= Date.parse(ts)) shown.push(at);
      const times = shown.filter((at) => at !== undefined);
      return times.length ? Math.min(...times) : null;
    },
    visibleReplyAt(id) {
      return visibleReplies()[id] ?? null;
    },
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
        activity: threadActivity(),
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
  watchVisibleAgentReply();
})();
