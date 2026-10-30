/* Native long-frame evidence shared by probes and latency benchmarks. This records
 * the browser's >=50 ms frames, not every task or all CPU time. Script attribution
 * names an entry point, not necessarily the function responsible for its cost.
 * Keep this in developer tooling: no instrumentation ships with a Leaf page. */
const __leafMainThreadProbe = (() => {
  const supported =
    PerformanceObserver.supportedEntryTypes.includes("long-animation-frame");
  let frames = [];
  function record(entries) {
    for (const frame of entries) {
      const end = frame.startTime + frame.duration;
      frames.push({
        start: performance.timeOrigin + frame.startTime,
        end: performance.timeOrigin + end,
        blocking: frame.blockingDuration,
        // Rendering after scripts; forced style/layout is part of each script.
        render: frame.styleAndLayoutStart ? end - frame.styleAndLayoutStart : 0,
        scripts: frame.scripts.map((script) => ({
          start: performance.timeOrigin + script.startTime,
          ms: script.duration,
          forced: script.forcedStyleAndLayoutDuration,
          owner: `${script.sourceURL.split("/").pop() || "(page)"} ${
            script.sourceFunctionName || script.invoker
          }`,
        })),
      });
    }
  }
  const observer = new PerformanceObserver((list) => record(list.getEntries()));
  if (supported) observer.observe({ type: "long-animation-frame" });
  return {
    reset() {
      observer.takeRecords();
      frames = [];
    },
    reading() {
      record(observer.takeRecords());
      return { supported, frames };
    },
  };
})();
Object.defineProperty(window, "__leafMainThread", { value: __leafMainThreadProbe });
