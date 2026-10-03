/*
 * Browser-side observations for `leaf-dev verify-site`, installed before each navigation.
 * Shared startup evidence is installed separately. Visible-reply timestamps use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the website-specific Playwright boundary exposed to the Python orchestrator.
 */
(() => {
  const visibleReplyStartedKey = "leaf-visible-reply-started";
  const visibleReplyAtKey = "leaf-visible-reply-at";
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

  function watchVisibleAgentReply() {
    const started = sessionStorage.getItem(visibleReplyStartedKey);
    if (
      started === null ||
      sessionStorage.getItem(visibleReplyAtKey) !== null ||
      visibleReplyObservers
    )
      return;

    const seen = new WeakSet();
    const intersections = new IntersectionObserver((entries) => {
      const visible = entries.find(
        ({ isIntersecting, target }) =>
          isIntersecting &&
          target.querySelector(".lf-msg-text")?.textContent.trim() &&
          target.checkVisibility(),
      );
      if (!visible || sessionStorage.getItem(visibleReplyAtKey) !== null) return;
      sessionStorage.setItem(visibleReplyAtKey, String(Date.now()));
      stopVisibleReplyWatch();
    });
    const observe = () => {
      for (const message of document.querySelectorAll(".lf-msg.agent")) {
        if (
          !seen.has(message) &&
          message.querySelector(".lf-msg-text")?.textContent.trim()
        ) {
          seen.add(message);
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
      watchVisibleAgentReply();
      return started;
    },
    visibleReplyRecorded() {
      return sessionStorage.getItem(visibleReplyAtKey) !== null;
    },
    visibleReplyAt() {
      const visible = sessionStorage.getItem(visibleReplyAtKey);
      return visible === null ? null : Number(visible);
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
