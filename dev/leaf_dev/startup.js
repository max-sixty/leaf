/* Development-only startup and layout evidence, installed before navigation by
 * probe and verify-site. The startup reading ends at presentation; the same shift
 * recorder continues through a probe's journey. Native shifts are observations,
 * never pass/fail budgets. Their
 * sources are affected nodes (at most five), not proof of the initiating code.
 * Attribution is serialized when observed; a removed native source is null.
 */
(() => {
  const startup = {};
  const shifts = [];
  let completedAt = Infinity;
  /** @type {Promise<void> | null} */
  let presentationPaint = null;
  function sourceName(node) {
    if (!node) return null;
    const text = node.nodeType === Node.TEXT_NODE;
    let element = text ? node.parentElement : node;
    const parts = [];
    while (element instanceof Element) {
      const parent = element.parentNode;
      if (!parent) {
        parts.unshift(element.id ? `#${CSS.escape(element.id)}` : element.localName);
        break;
      }
      const siblings = [...parent.children].filter(
        (sibling) => sibling.localName === element.localName,
      );
      parts.unshift(
        element.id
          ? `#${CSS.escape(element.id)}`
          : `${element.localName}:nth-of-type(${siblings.indexOf(element) + 1})`,
      );
      if (parent instanceof ShadowRoot) {
        parts.unshift("::shadow");
        element = parent.host;
      } else element = element.parentElement;
    }
    return parts.join(" > ") + (text ? "::text" : "");
  }
  const rect = ({ x, y, width, height }) => ({ x, y, width, height });
  function recordShifts(entries) {
    for (const entry of entries) {
      shifts.push({
        startTime: entry.startTime,
        value: entry.value,
        hadRecentInput: entry.hadRecentInput,
        sources: entry.sources.map((source) => ({
          node: sourceName(source.node),
          previousRect: rect(source.previousRect),
          currentRect: rect(source.currentRect),
        })),
      });
    }
  }
  const shiftObserver = new PerformanceObserver((list) =>
    recordShifts(list.getEntries()),
  );
  // Firefox and WebKit have no layout-shift entries, and warn on asking for them.
  const shiftsSupported =
    PerformanceObserver.supportedEntryTypes.includes("layout-shift");
  if (shiftsSupported) shiftObserver.observe({ type: "layout-shift", buffered: true });
  // Resource Timing's document buffer is bounded. Observe every completed response
  // instead, and drain records already queued when a startup milestone is captured.
  const resourceEntries = [];
  const resourceObserver = new window.PerformanceObserver((list) => {
    resourceEntries.push(...list.getEntries());
  });
  resourceObserver.observe({ type: "resource", buffered: true });
  function observedResources() {
    resourceEntries.push(...resourceObserver.takeRecords());
    return resourceEntries;
  }

  function resourceSnapshot() {
    const resources = observedResources();
    const code = resources.filter((entry) => {
      const url = new URL(entry.name);
      return (
        url.origin === location.origin &&
        (url.pathname.endsWith(".js") ||
          url.pathname.endsWith(".css") ||
          url.pathname.endsWith("registry.json"))
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
      if (body.hasAttribute(attribute) && !startup[name]) {
        startup[name] = resourceSnapshot();
        if (name === "presented")
          presentationPaint = new Promise((resolve) => {
            requestAnimationFrame(() =>
              requestAnimationFrame((at) => {
                completedAt = at;
                recordShifts(shiftObserver.takeRecords());
                resolve();
              }),
            );
          });
      }
    }
  }

  Object.defineProperty(window, "__leafStartup", {
    value: Object.freeze({
      milestones: () => Object.keys(startup),
      resourceNames: () => observedResources().map((entry) => entry.name),
      layoutShifts() {
        recordShifts(shiftObserver.takeRecords());
        return { supported: shiftsSupported, entries: shifts };
      },
      async reading() {
        await presentationPaint;
        recordShifts(shiftObserver.takeRecords());
        const navigation = /** @type {PerformanceNavigationTiming[]} */ (
          performance.getEntriesByType("navigation")
        )[0];
        return {
          first_byte: navigation.responseStart,
          document: navigation.responseEnd,
          paint: Object.fromEntries(
            performance
              .getEntriesByType("paint")
              .map((entry) => [entry.name, entry.startTime]),
          ),
          ...startup,
          shifts: shifts
            .filter((entry) => entry.startTime <= completedAt)
            .map((entry) => ({
              ...entry,
              phase:
                !startup.upgraded || entry.startTime < startup.upgraded.at
                  ? "before-upgrade"
                  : !startup.presented || entry.startTime < startup.presented.at
                    ? "before-presentation"
                    : "presentation",
            })),
        };
      },
    }),
  });
  new MutationObserver(recordStartup).observe(document, {
    attributes: true,
    attributeFilter: ["data-lf-upgraded", "data-lf-presented"],
    childList: true,
    subtree: true,
  });
  recordStartup();
})();
