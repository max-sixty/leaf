import assert from "node:assert/strict";
import test from "node:test";
import {
  createEffect,
  createRenderEffect,
  createRoot,
  createSignal,
  flush,
} from "@solidjs/signals";
import { afterRender, renderCommit, writeView } from "./rendering.ts";

test("post-commit measurements see every preceding native DOM write", async () => {
  const [requested, request] = createSignal("before");
  const [props, publish] = createSignal("before", { ownedWrite: true });
  let dom = "";
  let commit;
  const readings = [];
  const stop = createRoot((dispose) => {
    createRenderEffect(props, (value) => {
      dom = value;
    });
    createEffect(requested, (value) => {
      commit = renderCommit(() => {
        writeView(
          () => {
            publish(value);
          },
          () => {},
        );
        afterRender(() => {
          readings.push(dom);
          if (value === "after") {
            writeView(
              () => {
                publish("measured");
              },
              () => {},
            );
            afterRender(() => {
              assert.equal(dom, "measured");
              writeView(
                () => {
                  publish("nested");
                },
                () => {},
              );
            });
          }
        });
        afterRender(() => {
          readings.push(dom);
        });
      });
    });
    return dispose;
  });
  try {
    flush();
    await commit.ready;
    readings.length = 0;
    flush(() => request("after"));
    assert.deepEqual(readings, ["after", "nested"]);
    await commit.ready;
  } finally {
    stop();
  }
});

test("committed DOM does not wait for an asynchronous preparation", async () => {
  const preparation = Promise.withResolvers();
  const afterPreparation = Promise.withResolvers();
  const measurements = [];
  const commit = renderCommit(() => {
    afterRender(() => {
      measurements.push("visible");
      return afterPreparation.promise;
    });
    return preparation.promise;
  });
  await commit.committed;
  assert.deepEqual(measurements, ["visible"]);
  let ready = false;
  void commit.ready.then(() => {
    ready = true;
  });
  preparation.resolve("prepared");
  await Promise.resolve();
  assert.equal(ready, false);
  afterPreparation.resolve();
  assert.equal(await commit.ready, "prepared");
});

test("a failed measurement rejects its owner while an unrelated commit completes", async () => {
  const failure = new Error("Cannot measure this view");
  const jobs = [];
  const broken = renderCommit(
    () => {
      afterRender(() => {
        throw failure;
      });
      afterRender(() => {
        assert.fail("a failed owner's later work must not run");
      });
    },
    {
      bind(callback) {
        jobs.push("enqueue");
        return () => {
          try {
            return callback();
          } finally {
            jobs.push("finish");
          }
        };
      },
    },
  );
  const healthy = renderCommit(() => "healthy");
  await assert.rejects(broken.committed, failure);
  await assert.rejects(broken.ready, failure);
  assert.equal(await healthy.ready, "healthy");
  assert.equal(await renderCommit(() => "later").ready, "later");
  assert.deepEqual(jobs, ["enqueue", "enqueue", "finish", "finish"]);
});

test("a parent measurement waits for a nested commit's post-commit writes", async () => {
  const [props, publish] = createSignal("before", { ownedWrite: true });
  let dom = "";
  const stop = createRoot((dispose) => {
    createRenderEffect(props, (value) => {
      dom = value;
    });
    return dispose;
  });
  try {
    const readings = [];
    let stretches = 0;
    const commit = renderCommit(
      () => {
        renderCommit(() => {
          writeView(
            () => {
              publish("child");
            },
            () => {},
          );
          afterRender(() => {
            writeView(
              () => {
                publish("child measured");
              },
              () => {},
            );
          });
        });
        afterRender(() => {
          readings.push(dom);
        });
      },
      {
        run(callback) {
          stretches++;
          return callback();
        },
      },
    );
    await commit.ready;
    assert.deepEqual(readings, ["child measured"]);
    assert.equal(stretches, 4, "nested work inherits the owner's tracked stretches");
  } finally {
    stop();
  }
});

test("each measurement retains its registration context and tracked stretch", async () => {
  let context = "input";
  const readings = [];
  const stretches = [];
  const commit = renderCommit(
    () => {
      afterRender(() => {
        readings.push(context);
      });
      context = "passive";
      afterRender(() => {
        readings.push(context);
      });
    },
    {
      bind(callback) {
        const captured = context;
        return () => {
          const previous = context;
          context = captured;
          try {
            return callback();
          } finally {
            context = previous;
          }
        };
      },
      run(callback) {
        stretches.push("start");
        try {
          return callback();
        } finally {
          stretches.push("end");
        }
      },
    },
  );
  context = "unrelated";
  await commit.ready;
  assert.deepEqual(readings, ["input", "passive"]);
  assert.deepEqual(stretches, ["start", "end", "start", "end", "start", "end"]);
  assert.equal(context, "unrelated");
});

for (const cancellation of ["superseded", "disconnected"]) {
  test(`a ${cancellation} owner retires queued work and retains started failures`, async () => {
    let connected = true;
    let generation = 1;
    const claimed = generation;
    const preparation = Promise.withResolvers();
    const failure = new Error("Started preparation failed");
    const jobs = [];
    let stretches = 0;
    const commit = renderCommit(
      () => {
        writeView(
          () => {},
          () => assert.fail("an obsolete owner's binding check must not run"),
        );
        afterRender(() => assert.fail("an obsolete owner must not act on its DOM"));
        renderCommit(() => {
          afterRender(() => assert.fail("nested work inherits its owner's lifetime"));
        });
        return preparation.promise;
      },
      {
        current: () => connected && claimed === generation,
        bind(callback) {
          jobs.push("enqueue");
          return () => {
            try {
              jobs.push("run");
              return callback();
            } finally {
              jobs.push("finish");
            }
          };
        },
        run(callback) {
          stretches++;
          return callback();
        },
      },
    );
    if (cancellation === "superseded") generation++;
    else connected = false;
    await commit.committed;
    assert.deepEqual(jobs, ["enqueue", "enqueue", "run", "finish", "run", "finish"]);
    assert.equal(stretches, 4, "cancelled bound callbacks still enter their run hook");
    let ready = false;
    void commit.ready.then(
      () => {
        ready = true;
      },
      () => {
        ready = true;
      },
    );
    await Promise.resolve();
    assert.equal(ready, false, "cancellation cannot acknowledge a pending preparation");
    preparation.reject(failure);
    await assert.rejects(commit.ready, failure);
  });
}

test("an already obsolete commit skips its write and resolves without a result", async () => {
  const commit = renderCommit(() => assert.fail("an obsolete write must not start"), {
    current: () => false,
  });
  await commit.committed;
  assert.equal(await commit.ready, undefined);
});

test("a root commit keeps its lifetime separate from the caller flushing it", async () => {
  const preparation = Promise.withResolvers();
  let current = true;
  let callerStretches = 0;
  let callerBindings = 0;
  let independent;
  const readings = [];
  const caller = renderCommit(
    () => {
      independent = renderCommit(
        () => {
          afterRender(() => {
            readings.push("independent measured");
          });
          return preparation.promise;
        },
        { root: true },
      );
      current = false;
      return "caller finished";
    },
    {
      current: () => current,
      run(callback) {
        callerStretches++;
        return callback();
      },
      bind(callback) {
        callerBindings++;
        return callback;
      },
    },
  );
  try {
    await Promise.all([caller.committed, independent.committed]);
    assert.deepEqual(readings, ["independent measured"]);
    assert.equal(callerStretches, 1);
    assert.equal(callerBindings, 0);
    let result;
    void caller.ready.then((value) => {
      result = value;
    });
    await new Promise(setImmediate);
    assert.equal(
      result,
      "caller finished",
      "independent async work cannot hold the caller",
    );
    preparation.resolve("independent finished");
    assert.equal(await independent.ready, "independent finished");
  } finally {
    preparation.resolve();
  }
});
