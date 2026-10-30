/** Exception summaries, diagnostic traces, and records crossing sample ports.
 * Each public reader protects its complete operation: a thrown value can itself
 * throw while read, converted to text, or inspected through native operations.
 * Error events keep native Error identity and never invent a failure stack.
 */
const UNREADABLE = "Could not read the error";

function readException<T>(read: () => T, unreadable: T): T {
  try {
    return read();
  } catch {
    return unreadable;
  }
}

function exceptionFields(reason: unknown) {
  if (reason === null || (typeof reason !== "object" && typeof reason !== "function"))
    return {
      name: undefined,
      message: String(reason),
      stack: undefined,
      cause: undefined,
      hasMessage: false,
    };
  const name = "name" in reason ? reason.name : undefined;
  const message = "message" in reason ? reason.message : undefined;
  const stack = "stack" in reason ? reason.stack : undefined;
  const cause = "cause" in reason ? reason.cause : undefined;
  return {
    name: typeof name === "string" ? name : undefined,
    message: typeof message === "string" ? message : String(reason),
    stack: typeof stack === "string" ? stack : undefined,
    cause,
    hasMessage: typeof message === "string",
  };
}

export function describeFailure(reason: unknown): string {
  return readException(() => {
    const fields = exceptionFields(reason);
    const message = fields.message || fields.name || "Error";
    return reason instanceof AggregateError && reason.errors.length
      ? `${message}: ${reason.errors.map(describeFailure).join("; ")}`
      : message;
  }, UNREADABLE);
}

export function exceptionRecord(reason: unknown) {
  return readException(
    () => {
      const fields = exceptionFields(reason);
      return {
        name: fields.name ?? "Error",
        message: fields.message,
        stack: fields.stack,
      };
    },
    { name: "Error", message: UNREADABLE, stack: undefined },
  );
}

export function exceptionError(reason: unknown): Error {
  return readException<Error>(
    () =>
      reason instanceof Error
        ? reason
        : Object.assign(Object.create(Error.prototype), exceptionRecord(reason)),
    Object.assign(Object.create(Error.prototype), { message: UNREADABLE }),
  );
}

export function exceptionText(reason: unknown, context = ""): string {
  return readException(
    () => {
      const fields = exceptionFields(reason);
      const message = fields.message;
      const text = !fields.hasMessage
        ? message
        : `${fields.name || "Error"}: ${message}`;
      const stack = fields.stack;
      let evidence = !stack ? text : stack.includes(text) ? stack : `${text}\n${stack}`;
      if (reason instanceof AggregateError)
        evidence += reason.errors.map((error) => `\n${exceptionText(error)}`).join("");
      if (fields.cause !== undefined)
        evidence += `\nCaused by: ${exceptionText(fields.cause)}`;
      if (!context) return evidence;
      const summary = reason instanceof Error ? describeFailure(reason) : message;
      return `${context}: ${summary}${!fields.hasMessage ? "" : `\n${evidence}`}`;
    },
    context ? `${context}: ${UNREADABLE}` : UNREADABLE,
  );
}
