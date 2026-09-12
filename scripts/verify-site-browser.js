/*
 * Browser-side observations for verify_site.py, installed before each navigation.
 * Startup readings belong to one document. Visible-reply timestamps use sessionStorage
 * because the agent journey may navigate before Python reads them. __leafVerifier is
 * the one Playwright boundary exposed to the Python orchestrator.
 */
(() => {
  const visibleReplyStartedKey = "leaf-visible-reply-started";
  const visibleReplyAtKey = "leaf-visible-reply-at";
  const startup = {};
  let activationCount = 0;
  let visibleReplyObservers = null;

  function serverScript() {
    const script = document.querySelector("script[data-lf-server]");
    if (!script) throw new Error("Leaf server script is missing");
    return script;
  }

  function resourceSnapshot() {
    const resources = performance.getEntriesByType("resource");
    const code = resources.filter((entry) => {
      const url = new URL(entry.name);
      return (
        url.origin === location.origin &&
        (url.pathname.endsWith(".js") ||
          url.pathname.endsWith(".css") ||
          url.pathname.endsWith("/registry.json"))
      );
    });
    const javascript = code.filter((entry) =>
      new URL(entry.name).pathname.endsWith(".js"),
    );
    const state = resources.filter((entry) =>
      new URL(entry.name).pathname.endsWith("/api/state"),
    );
    const bytes = (entries) =>
      entries.reduce((total, entry) => total + entry.encodedBodySize, 0);
    const lastResponse = (entries) =>
      entries.length ? Math.max(...entries.map((entry) => entry.responseEnd)) : null;
    return {
      at: performance.now(),
      code_loaded: lastResponse(code),
      js_loaded: lastResponse(javascript),
      state_loaded: lastResponse(state),
      requests: resources.length,
      bytes: bytes(resources),
      code_requests: code.length,
      code_bytes: bytes(code),
      js_requests: javascript.length,
      js_bytes: bytes(javascript),
    };
  }

  function recordStartup() {
    const body = document.body;
    if (!body) return;
    for (const [name, attribute] of [
      ["upgraded", "data-lf-upgraded"],
      ["presented", "data-lf-presented"],
    ]) {
      if (body.hasAttribute(attribute) && !startup[name])
        startup[name] = resourceSnapshot();
    }
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
      for (const message of document.querySelectorAll(".lf-msg.claude")) {
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
    startupMilestones() {
      return Object.keys(startup);
    },
    startupReading() {
      const navigation = performance.getEntriesByType("navigation")[0];
      return {
        first_byte: navigation.responseStart,
        document: navigation.responseEnd,
        paint: Object.fromEntries(
          performance
            .getEntriesByType("paint")
            .map((entry) => [entry.name, entry.startTime]),
        ),
        ...startup,
      };
    },
    identity() {
      const script = serverScript();
      return {
        layer: script.dataset.lfLayer,
        release: script.dataset.lfRelease,
      };
    },
    resourceNames() {
      return performance.getEntriesByType("resource").map((entry) => entry.name);
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
      client.observeSession(
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
    visibleReplyDebug() {
      return {
        panel: document.querySelector(".lf-thread-panel")?.checkVisibility(),
        messages: [...document.querySelectorAll(".lf-msg")].map((node) => ({
          author: [...node.classList],
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
  new MutationObserver(recordStartup).observe(document, {
    attributes: true,
    attributeFilter: ["data-lf-upgraded", "data-lf-presented"],
    childList: true,
    subtree: true,
  });
  recordStartup();
  watchVisibleAgentReply();
})();
