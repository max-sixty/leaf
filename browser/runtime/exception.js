/* @noformat Generated TypeScript; edit the .ts owner. */
const UNREADABLE = "Could not read the error";
function readException(read, unreadable) {
  try {
    return read();
  } catch {
    return unreadable;
  }
}
function exceptionFields(reason) {
  if (reason === null || typeof reason !== "object" && typeof reason !== "function")
    return {
      name: void 0,
      message: String(reason),
      stack: void 0,
      cause: void 0,
      hasMessage: false
    };
  const name = "name" in reason ? reason.name : void 0;
  const message = "message" in reason ? reason.message : void 0;
  const stack = "stack" in reason ? reason.stack : void 0;
  const cause = "cause" in reason ? reason.cause : void 0;
  return {
    name: typeof name === "string" ? name : void 0,
    message: typeof message === "string" ? message : String(reason),
    stack: typeof stack === "string" ? stack : void 0,
    cause,
    hasMessage: typeof message === "string"
  };
}
function describeFailure(reason) {
  return readException(() => {
    const fields = exceptionFields(reason);
    const message = fields.message || fields.name || "Error";
    return reason instanceof AggregateError && reason.errors.length ? `${message}: ${reason.errors.map(describeFailure).join("; ")}` : message;
  }, UNREADABLE);
}
function exceptionRecord(reason) {
  return readException(
    () => {
      const fields = exceptionFields(reason);
      return {
        name: fields.name ?? "Error",
        message: fields.message,
        stack: fields.stack
      };
    },
    { name: "Error", message: UNREADABLE, stack: void 0 }
  );
}
function exceptionError(reason) {
  return readException(
    () => reason instanceof Error ? reason : Object.assign(Object.create(Error.prototype), exceptionRecord(reason)),
    Object.assign(Object.create(Error.prototype), { message: UNREADABLE })
  );
}
function exceptionText(reason, context = "") {
  return readException(
    () => {
      const fields = exceptionFields(reason);
      const message = fields.message;
      const text = !fields.hasMessage ? message : `${fields.name || "Error"}: ${message}`;
      const stack = fields.stack;
      let evidence = !stack ? text : stack.includes(text) ? stack : `${text}
${stack}`;
      if (reason instanceof AggregateError)
        evidence += reason.errors.map((error) => `
${exceptionText(error)}`).join("");
      if (fields.cause !== void 0)
        evidence += `
Caused by: ${exceptionText(fields.cause)}`;
      if (!context) return evidence;
      const summary = reason instanceof Error ? describeFailure(reason) : message;
      return `${context}: ${summary}${!fields.hasMessage ? "" : `
${evidence}`}`;
    },
    context ? `${context}: ${UNREADABLE}` : UNREADABLE
  );
}
export {
  describeFailure,
  exceptionError,
  exceptionRecord,
  exceptionText
};
