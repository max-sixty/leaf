// @ts-check
/* Drawing an element has under way, as the Web Components Community Group's draft
   protocol for a component's asynchronous work spells it: a `pending-task` event,
   bubbling and composed, whose `complete` promise settles once the drawing is in, or the
   element shows why it could not draw. A host that waits for its components' drawing
   hears it, as a Leaf page holds its presentation on it (module-widgets.md,
   "Drawing"); a page that waits for nothing ignores it.

   ```js
   this.dispatchEvent(new PendingTaskEvent(this.draw()));
   ``` */
export const PENDING_TASK = "pending-task";
export class PendingTaskEvent extends Event {
  /** @param {PromiseLike<unknown>} complete */
  constructor(complete) {
    super(PENDING_TASK, { bubbles: true, composed: true });
    this.complete = complete;
  }
}
