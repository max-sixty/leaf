/**
 * One session's between-turn watch. Host adapters own process creation and wakes;
 * this owner keeps termination, replacement and completion in the same order.
 *
 * A Stop watch survives another Stop. Every Interrupt replaces the old watch,
 * including an Interrupt watch, so the new ending reads fresh receipt evidence.
 * Replacement invalidates completion immediately, but retains the old process
 * until `done` proves it has exited and released its lease. Concurrent endings
 * collapse to the latest request. Shutdown invalidates queued starts and wakes.
 * `live` checks watch ownership after yielding; `open` tracks the session lifetime
 * for a host that has already confirmed input and still owes its delivery.
 */

type Watch = { stop: () => unknown; done: Promise<string> }
type Ending = { interrupted: boolean }

export class WatchOwner {
  private current: Watch | undefined
  private desired: Ending | undefined
  private pending: Promise<void> = Promise.resolve()
  private closed = false
  private generation = 0

  get open(): boolean {
    return !this.closed
  }

  ensure(
    interrupted: boolean,
    start: () => Watch,
    wake: (output: string, live: () => boolean) => unknown,
  ): Promise<void> {
    if (this.closed || (!interrupted && this.desired?.interrupted === false)) return this.pending
    const ending = { interrupted }
    this.desired = ending
    const generation = ++this.generation
    return this.enqueue(async () => {
      if (this.desired !== ending) return
      await this.stopCurrent()
      if (this.closed || this.desired !== ending) return
      const current = start()
      this.current = current
      const live = () => !this.closed && this.generation === generation
      void current.done.then(output => {
        if (!live()) return
        this.current = undefined
        this.desired = undefined
        return wake(output, live)
      })
    }).catch(error => {
      if (this.desired === ending) this.desired = undefined
      throw error
    })
  }

  close(): Promise<void> {
    this.closed = true
    this.desired = undefined
    ++this.generation
    return this.enqueue(() => this.stopCurrent())
  }

  private enqueue(operation: () => Promise<void>): Promise<void> {
    const next = this.pending.then(operation)
    // A failed host operation is reported to its caller, without poisoning later
    // shutdown or replacement requests.
    this.pending = next.catch(() => undefined)
    return next
  }

  private async stopCurrent(): Promise<void> {
    const current = this.current
    if (!current) return
    try {
      await current.stop()
    } finally {
      // Cancelling a host's output iterator can finish before its child exits.
      await current.done
      this.current = undefined
    }
  }
}
