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

/** A thrown value in one line, for a failure the page shows: its message, or its name
 * where it has no message, with the members of an `AggregateError` listed after it. */
export function describeFailure(reason: unknown): string {
  return readException(() => {
    const fields = exceptionFields(reason);
    const message = fields.message || fields.name || "Error";
    return reason instanceof AggregateError && reason.errors.length
      ? `${message}: ${reason.errors.map(describeFailure).join("; ")}`
      : message;
  }, UNREADABLE);
}

/** A thrown value's `{name, message, stack}` as plain data, which a message port
 * carries where it would refuse the value itself. */
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

/** A thrown value as an `Error`: itself where it is one, else an object that is one
 * and carries the value's record, with no stack the value didn't have. */
export function exceptionError(reason: unknown): Error {
  return readException(
    () =>
      reason instanceof Error
        ? reason
        : Object.assign(Object.create(Error.prototype), exceptionRecord(reason)),
    Object.assign(Object.create(Error.prototype), { message: UNREADABLE }),
  );
}

/** A thrown value's whole evidence, for a log or a report: its name and message, its
 * stack, each member of an `AggregateError` and each cause behind it, under a first
 * line of `context` and its one-line description where `context` is given. */
export function exceptionText(reason: unknown, context: string = ""): string {
  return readException(
    () => {
      const fields = exceptionFields(reason);
      const message = fields.message;
      const text = !fields.hasMessage
        ? message
        : `${fields.name || "Error"}: ${message}`;
      const stack = fields.stack;
      let evidence = !stack
        ? text
        : stack.includes(text)
          ? stack
          : `${text}
${stack}`;
      if (reason instanceof AggregateError)
        evidence += reason.errors
          .map(
            (error) => `
${exceptionText(error)}`,
          )
          .join("");
      if (fields.cause !== undefined)
        evidence += `
Caused by: ${exceptionText(fields.cause)}`;
      if (!context) return evidence;
      const summary = reason instanceof Error ? describeFailure(reason) : message;
      return `${context}: ${summary}${
        !fields.hasMessage
          ? ""
          : `
${evidence}`
      }`;
    },
    context ? `${context}: ${UNREADABLE}` : UNREADABLE,
  );
}
