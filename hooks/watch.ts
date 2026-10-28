/**
 * Pi's between-turn watch. The extension owns process creation and wakes;
 * this owner keeps termination, replacement and completion in the same order.
 *
 * A Stop watch survives another Stop. Every Interrupt replaces the old watch,
 * including an Interrupt watch, so the new ending reads fresh receipt evidence.
 * Replacement invalidates completion immediately, but retains the old process
 * until `done` proves it has exited and released its lease. Concurrent endings
 * collapse to the latest request. Shutdown invalidates queued starts and wakes.
 */

type Watch = { stop: () => void; done: Promise<string> };
type Ending = { interrupted: boolean };

export class WatchOwner {
  private current: Watch | undefined;
  private desired: Ending | undefined;
  private pending: Promise<void> = Promise.resolve();
  private closed = false;

  ensure(
    interrupted: boolean,
    start: () => Watch,
    wake: (output: string) => void,
  ): Promise<void> {
    if (this.closed || (!interrupted && this.desired?.interrupted === false))
      return this.pending;
    const ending = { interrupted };
    this.desired = ending;
    return this.enqueue(async () => {
      if (this.desired !== ending) return;
      await this.stopCurrent();
      if (this.closed || this.desired !== ending) return;
      const current = start();
      this.current = current;
      void current.done.then((output) => {
        if (this.desired !== ending) return;
        this.current = undefined;
        this.desired = undefined;
        return wake(output);
      });
    });
  }

  close(): Promise<void> {
    this.closed = true;
    this.desired = undefined;
    return this.enqueue(() => this.stopCurrent());
  }

  private enqueue(operation: () => Promise<void>): Promise<void> {
    return (this.pending = this.pending.then(operation));
  }

  private async stopCurrent(): Promise<void> {
    const current = this.current;
    if (!current) return;
    current.stop();
    await current.done;
    this.current = undefined;
  }
}
