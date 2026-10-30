// @ts-check
/** Exception summaries, diagnostic traces, and records crossing sample ports.
 * Each public reader protects its complete operation: a thrown value can itself
 * throw while read, converted to text, or inspected through native operations.
 * Error events keep native Error identity and never invent a failure stack.
 */
const UNREADABLE = "Could not read the error";

/** @template T @param {() => T} read @param {T} unreadable @returns {T} */
function readException(read, unreadable) {
  try {
    return read();
  } catch {
    return unreadable;
  }
}

/** @param {unknown} reason */
function exceptionFields(reason) {
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

/** @param {unknown} reason @returns {string} */
export function describeFailure(reason) {
  return readException(() => {
    const fields = exceptionFields(reason);
    const message = fields.message || fields.name || "Error";
    return reason instanceof AggregateError && reason.errors.length
      ? `${message}: ${reason.errors.map(describeFailure).join("; ")}`
      : message;
  }, UNREADABLE);
}

/** @param {unknown} reason */
export function exceptionRecord(reason) {
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

/** @param {unknown} reason @returns {Error} */
export function exceptionError(reason) {
  return readException(
    () =>
      reason instanceof Error
        ? reason
        : Object.assign(Object.create(Error.prototype), exceptionRecord(reason)),
    Object.assign(Object.create(Error.prototype), { message: UNREADABLE }),
  );
}

/** @param {unknown} reason @param {string} [context] @returns {string} */
export function exceptionText(reason, context = "") {
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
