/*
 * Browser-side observations for `leaf-dev verify-site`, installed before each navigation.
 * Shared startup evidence is installed separately. Visible-reply timestamps use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the website-specific Playwright boundary exposed to the Python orchestrator.
 */
(() => {
  const visibleReplyStartedKey = "leaf-visible-reply-started";
  const visibleReplyAtKey = "leaf-visible-reply-at";
  const workVisibleAtKey = "leaf-work-visible-at";
  // The receipts a user's message wears once the agent is on it, which its status
  // claim or a streamed reply sets (`runtime/thread/workflow.js`).
  const atWork = new Set(["Working", "Replying"]);
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

  function workVisible() {
    return JSON.parse(sessionStorage.getItem(workVisibleAtKey) ?? "{}");
  }

  // When each thread first shows the agent on it: a message of the thread reading
  // Working or Replying, or the agent's words in it, streamed or final.
  function recordWorkVisible() {
    const found = workVisible();
    let changed = false;
    for (const thread of document.querySelectorAll(".lf-threads > .lf-thread[data-id]")) {
      const id = thread.dataset.id;
      if (found[id]) continue;
      const working = [...thread.querySelectorAll(".lf-msg-sending")].some(
        (receipt) => atWork.has(receipt.textContent.trim()) && receipt.checkVisibility(),
      );
      const answering = [...thread.querySelectorAll(".lf-msg.agent")].some(
        (message) =>
          message.querySelector(".lf-msg-text")?.textContent.trim() &&
          message.checkVisibility(),
      );
      if (working || answering) {
        found[id] = Date.now();
        changed = true;
      }
    }
    if (changed) sessionStorage.setItem(workVisibleAtKey, JSON.stringify(found));
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
      recordWorkVisible();
      for (const message of document.querySelectorAll(
        ".lf-threads .lf-msg.agent[data-mid]",
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
      sessionStorage.removeItem(workVisibleAtKey);
      stopVisibleReplyWatch();
      watchVisibleAgentReply();
      return started;
    },
    visibleReplyRecorded(id) {
      return visibleReplies()[id] !== undefined;
    },
    visibleReplyAt(id) {
      return visibleReplies()[id] ?? null;
    },
    workVisibleAt(thread) {
      return workVisible()[thread] ?? null;
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
