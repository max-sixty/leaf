/** An authored sample command always sends its failure back over the private port. */
import assert from "node:assert/strict";
import test from "node:test";
import { runInNewContext } from "node:vm";

let receive;
const sent = [];
document.documentElement.lfSample = {
  receive(callback) {
    receive = callback;
  },
  send(value) {
    sent.push(structuredClone(value));
  },
  settings: {},
  present() {},
};
const { registerSampleCommand } = await import("../../browser/runtime/sample-child.js");
const { describeFailure, exceptionError, exceptionText } =
  await import("../../browser/runtime/exception.js");

const ordinary = new Error("ordinary failure");
ordinary.name = "OrdinaryFailure";
const remote = runInNewContext('new Error("remote failure")');
const revoked = Proxy.revocable({}, {});
revoked.revoke();
const unreadable = {
  name: "Error",
  message: "Could not read the error",
  stack: undefined,
};
const cases = [
  [
    "ordinary",
    ordinary,
    { name: ordinary.name, message: ordinary.message, stack: ordinary.stack },
  ],
  [
    "remote",
    remote,
    { name: remote.name, message: remote.message, stack: remote.stack },
  ],
  ["null", null, { name: "Error", message: "null", stack: undefined }],
  ["null prototype", Object.create(null), unreadable],
  [
    "throwing getter",
    Object.defineProperty({}, "message", {
      get() {
        throw new Error("unreadable getter");
      },
    }),
    unreadable,
  ],
  ["revoked proxy", revoked.proxy, unreadable],
  [
    "uncloneable fields",
    { name() {}, message: 42, stack: Symbol("stack") },
    { name: "Error", message: "[object Object]", stack: undefined },
  ],
];

for (const [label, reason, error] of cases) {
  test(`a sample command answers a ${label} failure`, async () => {
    registerSampleCommand(label, () => {
      throw reason;
    });
    await receive({ id: label, method: label });
    assert.deepEqual(
      sent.find((message) => message.id === label),
      { id: label, error },
    );
  });
}

test("failure rendering keeps native Error identity and completes on unreadable values", () => {
  assert.equal(exceptionError(ordinary), ordinary);
  for (const reason of [Object.create(null), revoked.proxy]) {
    assert.equal(describeFailure(reason), unreadable.message);
    assert.equal(
      exceptionText(reason, "Command failed"),
      `Command failed: ${unreadable.message}`,
    );
    const error = exceptionError(reason);
    assert.ok(error instanceof Error);
    assert.equal(error.message, unreadable.message);
    assert.equal(error.stack, undefined);
  }
});

test("failure summaries retain a useful name when the message is empty", () => {
  assert.equal(describeFailure(new Error()), "Error");
  assert.equal(describeFailure(new DOMException("", "SecurityError")), "SecurityError");
  assert.equal(describeFailure(new Error("ordinary failure")), "ordinary failure");
});
