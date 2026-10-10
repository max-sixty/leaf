/* The isolated child's explicit interface to its containing page. Values cross the
 * port; documents, DOM nodes, functions and browser owners remain in this realm. */
const child = document.documentElement.lfSample;
const commands = new Map();
const observers = new Map();
export function onSampleNotice(type, callback) {
  if (!observers.has(type)) observers.set(type, new Set());
  observers.get(type).add(callback);
  return () => observers.get(type).delete(callback);
}
export function registerSampleCommand(name, callback) {
  commands.set(name, callback);
  return () => commands.delete(name);
}
export function sampleNotice(type, detail = {}) {
  child?.send({ type, detail });
}
if (child)
  child.receive(async ({ id, method, type, detail }) => {
    if (type) {
      for (const callback of observers.get(type) ?? []) callback(detail);
      return;
    }
    try {
      if (!commands.has(method)) throw new Error(`Unknown sample command: ${method}`);
      const result = await commands.get(method)(detail);
      child.send({ id, result });
    } catch (error) {
      child.send({ id, error: { name: error.name, message: error.message } });
    }
  });

if (child) {
  let presented = false;
  let height = null;
  const measure = () => {
    if (!document.body) return;
    const next = Math.ceil(document.body.getBoundingClientRect().height);
    if (next !== height) {
      height = next;
      sampleNotice("height", { height });
    }
  };
  const inspect = () => {
    const error = document.documentElement.dataset.lfStartupError;
    if (error) sampleNotice("error", { message: error });
    if (presented || !document.body?.hasAttribute("data-lf-presented")) return;
    presented = true;
    child.present();
    measure();
    if (!child.settings.passive && !child.settings.window) {
      const observer = new window.ResizeObserver(measure);
      observer.observe(document.body);
    }
    sampleNotice("ready", {
      height,
      block: document.documentElement.hasAttribute("data-lf-sample-block"),
    });
  };
  const observer = new MutationObserver(inspect);
  observer.observe(document, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["data-lf-presented", "data-lf-startup-error"],
  });
  inspect();
}
