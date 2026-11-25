// @ts-check
/* The page's first presentation, as a promise for work a widget or a page's script
   starts only once the user has the page, such as drawing what the window doesn't show
   yet. A Leaf page stamps `body[data-lf-presented]` as it first presents
   (module-authoring.md, "Startup and presentation"), and the promise resolves once the
   stamp stands, at once where the page already has. Work started then that can
   still move boxes says so with a `pending-task` event (pending-task.js), which holds
   the page's readiness until it is in; said before presentation, it would hold the
   presentation instead. In a document Leaf didn't compose, it never resolves.

   ```js
   presented().then(() => this.dispatchEvent(new PendingTaskEvent(this.drawRest())));
   ``` */
/** @returns {Promise<void>} */
export const presented = () => {
  const stamped = () => document.body?.hasAttribute("data-lf-presented");
  if (stamped()) return Promise.resolve();
  return new Promise((resolve) => {
    const watch = new MutationObserver(() => {
      if (!stamped()) return;
      watch.disconnect();
      resolve();
    });
    watch.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-lf-presented"],
      subtree: true,
    });
  });
};
