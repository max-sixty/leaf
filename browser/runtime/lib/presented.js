// @ts-check
/* The page's first presentation, as a promise for work a widget or a page's script
   starts only once the user has the page, such as drawing what the window doesn't show
   yet. A Leaf page stamps `body[data-lf-presented]` and dispatches `lf-presentation` on
   `document` as it first presents (module-authoring.md, "Startup and presentation"), so
   the promise resolves at once where the page already has. Work started then that can
   still move boxes says so with a `pending-task` event (pending-task.js), which holds
   the page's readiness until it is in; said before presentation, it would hold the
   presentation instead. In a document Leaf didn't compose, it never resolves.

   ```js
   presented().then(() => this.dispatchEvent(new PendingTaskEvent(this.drawRest())));
   ``` */
/** @returns {Promise<void>} */
export const presented = () =>
  document.body?.hasAttribute("data-lf-presented")
    ? Promise.resolve()
    : new Promise((resolve) =>
        document.addEventListener("lf-presentation", () => resolve(), { once: true }),
      );
