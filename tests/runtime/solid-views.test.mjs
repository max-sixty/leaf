/* A Solid view tracks the fields it draws while preserving native editing state. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  createView,
  html,
  For,
  createSignal,
  createMemo,
  createEffect,
  createRoot,
  flush,
  afterRender,
  renderCommit,
  watchReaction,
  onCleanup,
} from "/vendor/browser-runtime.js";

test("native effects commit retained view bindings before post-render work", async () => {
  const host = document.createElement("section");
  document.body.append(host);
  const view = createView(
    host,
    (read) => html`<label>${() => read().label}<input /></label>`,
    { label: "Before" },
  );
  const editor = host.querySelector("input");
  editor.value = "retained draft";
  editor.focus();
  editor.setSelectionRange(3, 8);
  const [label, setLabel] = createSignal("Before");
  const readings = [];
  let commit;
  const stop = createRoot((dispose) => {
    createEffect(label, (label) => {
      commit = renderCommit(() => {
        view.update({ label });
        afterRender(() => {
          readings.push(host.textContent);
        });
      });
    });
    return dispose;
  });
  try {
    flush();
    await commit.ready;
    flush(() => setLabel("After"));
    assert.deepEqual(readings, ["Before", "After"]);
    await commit.ready;
    assert.equal(host.querySelector("input"), editor);
    assert.equal(editor.value, "retained draft");
    assert.equal(document.activeElement, editor);
    assert.deepEqual([editor.selectionStart, editor.selectionEnd], [3, 8]);
  } finally {
    stop();
    view.dispose();
    host.remove();
  }
});

test("a deferred binding failure rejects its commit and leaves unrelated views live", async (t) => {
  const reports = [];
  const reporter = globalThis.reportError;
  globalThis.reportError = (error) => reports.push(error);
  t.after(() => {
    globalThis.reportError = reporter;
  });
  const host = document.createElement("section");
  const other = document.createElement("section");
  const view = createView(
    host,
    (read) =>
      html`<output
        >${() => {
          if (read().label === "broken") throw new Error("Cannot draw this commit");
          return read().label;
        }}</output
      >`,
    { label: "Ready" },
  );
  const independent = createView(
    other,
    (read) => html`<output>${() => read().label}</output>`,
    { label: "Ready" },
  );
  try {
    const broken = renderCommit(() => {
      view.update({ label: "broken" });
    });
    const healthy = renderCommit(() => {
      independent.update({ label: "Still live" });
    });
    await assert.rejects(broken.committed, /Cannot draw this commit/);
    await assert.rejects(broken.ready, /Cannot draw this commit/);
    await healthy.ready;
    assert.equal(other.textContent, "Still live");
    await renderCommit(() => {
      view.update({ label: "Recovered" });
    }).ready;
    assert.equal(host.textContent, "Recovered");
    assert.deepEqual(
      reports,
      [],
      "an owned error is delivered only through its commit",
    );
  } finally {
    view.dispose();
    independent.dispose();
  }
});

for (const cancelled of [false, true]) {
  test(`a local binding failure reports and recovers${cancelled ? " after a cancelled publication" : ""}`, async (t) => {
    const reports = [];
    const reporter = globalThis.reportError;
    globalThis.reportError = (error) => reports.push(error);
    t.after(() => {
      globalThis.reportError = reporter;
    });
    const failure = new Error("Local binding failed");
    const [broken, setBroken] = createSignal(false, { ownedWrite: true });
    const host = document.createElement("section");
    const other = document.createElement("section");
    const view = createView(
      host,
      () =>
        html`<output
          >${() => {
            if (broken()) throw failure;
            return "Local view healthy";
          }}</output
        >`,
      {},
    );
    const independent = createView(
      other,
      (read) => html`<output>${() => read().label}</output>`,
      { label: "Ready" },
    );
    try {
      if (cancelled) {
        let current = true;
        const publication = renderCommit(() => view.update({}), {
          current: () => current,
        });
        current = false;
        await publication.ready;
      }
      // A reentrant native flush can stand inside a different owner's render frame.
      // Only this view's outstanding publication receipt can own its failure.
      await renderCommit(() => {
        flush(() => setBroken(true));
        independent.update({ label: "Still live" });
      }).ready;
      assert.match(
        host.querySelector(".lf-error")?.textContent,
        /Local binding failed/,
      );
      assert.deepEqual(reports, [failure], "the original error is reported once");
      assert.equal(other.textContent, "Still live");
      flush(() => setBroken(false));
      assert.equal(host.textContent, "Local view healthy");
      assert.equal(host.querySelector(".lf-error"), null);
      independent.update({ label: "Still updating" });
      assert.equal(other.textContent, "Still updating");
      assert.deepEqual(reports, [failure]);
    } finally {
      view.dispose();
      independent.dispose();
    }
  });
}

for (const stage of ["update", "initial mount"]) {
  test(`a cancelled ${stage} reports a binding failure its owner did not consume`, async (t) => {
    const reports = [];
    const reporter = globalThis.reportError;
    globalThis.reportError = (error) => reports.push(error);
    t.after(() => {
      globalThis.reportError = reporter;
    });
    const failure = new Error(`Cancelled ${stage} failed`);
    const host = document.createElement("section");
    const component = (read) =>
      html`<output
        >${() => {
          if (read().broken) throw failure;
          return "Recovered";
        }}</output
      >`;
    let view =
      stage === "update" ? createView(host, component, { broken: false }) : null;
    let current = true;
    const publication = renderCommit(
      () => {
        if (view) view.update({ broken: true });
        else view = createView(host, component, { broken: true });
      },
      { current: () => current },
    );
    current = false;
    try {
      await publication.ready;
      assert.deepEqual(reports, [failure]);
      assert.match(host.querySelector(".lf-error")?.textContent, /failed/);
      view.update({ broken: false });
      assert.equal(host.textContent, "Recovered");
      assert.deepEqual(reports, [failure]);
    } finally {
      view?.dispose();
    }
  });
}

test("overlapping view publications leave binding failure with the latest commit", async () => {
  const host = document.createElement("section");
  const component = (read) =>
    html`<output
      >${() => {
        if (read().label === "broken") throw new Error("Latest view failed");
        return read().label;
      }}</output
    >`;
  const view = createView(host, component, { label: "Ready" });
  try {
    const earlier = renderCommit(() => {
      view.update({ label: "Earlier" });
    });
    const latest = renderCommit(() => {
      view.update({ label: "broken" });
    });
    await earlier.ready;
    await assert.rejects(latest.committed, /Latest view failed/);
    await assert.rejects(latest.ready, /Latest view failed/);
    await renderCommit(() => {
      view.update({ label: "Recovered" });
    }).ready;
    assert.equal(host.textContent, "Recovered");
  } finally {
    view.dispose();
  }

  let recovering;
  const failedMount = renderCommit(() => {
    recovering = createView(host, component, { label: "broken" });
  });
  const recoveredMount = renderCommit(() => {
    recovering.update({ label: "Newer" });
  });
  try {
    await Promise.all([failedMount.ready, recoveredMount.ready]);
    assert.equal(host.textContent, "Newer");
  } finally {
    recovering.dispose();
  }
});

test("a failed view releases its work, leaves other views live and can recover", () => {
  const host = document.createElement("section");
  const other = document.createElement("section");
  const independent = createView(
    other,
    (read) => html`<output>${() => read().label}</output>`,
    { label: "Ready" },
  );
  let cleanups = 0;
  const component = (read) => {
    onCleanup(() => cleanups++);
    return html`<output
      >${() => {
        if (read().label === "broken") throw new Error("Cannot draw this value");
        return read().label;
      }}</output
    >`;
  };
  try {
    assert.throws(
      () => createView(host, component, { label: "broken" }),
      /Cannot draw this value/,
    );
    assert.equal(cleanups, 1, "a failed initial mount releases its work");
    independent.update({ label: "Still working" });
    assert.equal(other.textContent, "Still working");

    const view = createView(host, component, { label: "Ready" });
    try {
      assert.throws(() => view.update({ label: "broken" }), /Cannot draw this value/);
      assert.equal(cleanups, 2, "a failed update releases its work");
      independent.update({ label: "Still live" });
      assert.equal(other.textContent, "Still live");
      view.update({ label: "Recovered" });
      assert.equal(host.textContent, "Recovered");
    } finally {
      view.dispose();
    }
    assert.equal(cleanups, 3, "the recovered view has its own lifetime");
  } finally {
    independent.dispose();
  }
});

test("an imperative draw follows completed reads without waking on a lazy first pull", () => {
  for (const memoized of [false, true]) {
    const [value, setValue] = createSignal(0);
    const memo = createMemo(() => value() * 2, { lazy: true });
    let wakes = 0;
    const stop = watchReaction(
      () => {
        assert.equal(memoized ? memo() : value(), 0);
        flush(() => setValue(1));
      },
      () => {
        wakes++;
      },
    );
    flush();
    assert.equal(wakes, 1, "the completed read was changed by its own draw");
    stop();
    flush(() => setValue(2));
    assert.equal(wakes, 1, "a disposed draw no longer follows its inputs");
    const stopLazy = watchReaction(
      () => {
        assert.equal(memo(), 4);
      },
      () => {
        wakes++;
      },
    );
    flush();
    assert.equal(wakes, 1, "the first pull returns fresh data and owes no second draw");
    stopLazy();
  }
});

test("a retained native view outlives the imperative draw that first mounts it", () => {
  const host = document.createElement("section");
  const [value, setValue] = createSignal(0);
  let view;
  const stop = watchReaction(
    () => {
      value();
      view = createView(host, (read) => html`<output>${() => read().value}</output>`, {
        value: "first",
      });
    },
    () => {},
  );
  flush(() => setValue(1));
  view.update({ value: "second" });
  assert.equal(host.textContent, "second");
  stop();
  view.dispose();
});

test("updating one field leaves an independent binding and native editor alone", () => {
  const host = document.createElement("section");
  document.body.append(host);
  let labelReads = 0;
  const view = createView(
    host,
    (props) =>
      html` <label
          >${() => {
            labelReads++;
            return props().label;
          }}<input
        /></label>
        <output>${() => props().count}</output>`,
    { label: "Notes", count: 0 },
  );
  const input = host.querySelector("input");
  input.value = "An unfinished sentence";
  input.focus();
  input.setSelectionRange(3, 13);
  view.update({ label: "Notes", count: 1 });
  assert.equal(host.querySelector("output").textContent, "1");
  assert.equal(labelReads, 1);
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "An unfinished sentence");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [3, 13]);
  view.dispose();
  host.remove();
});

test("reordering keyed records preserves each row's kind and native editor", () => {
  const host = document.createElement("section");
  document.body.append(host);
  const row = { key: "command", kind: "entry", entry: { label: "Run" } };
  const heading = { key: "heading", kind: "heading", title: "Commands" };
  const view = createView(
    host,
    (read) =>
      For({
        get each() {
          return read().items;
        },
        keyed: (item) => item.key,
        children: (item) =>
          item().kind === "entry"
            ? html`<label>${() => item().entry.label}<input /></label>`
            : html`<h2>${() => item().title}</h2>`,
      }),
    { items: [row, heading] },
  );
  const input = host.querySelector("input");
  input.value = "Unfinished";
  input.focus();
  input.setSelectionRange(2, 6);
  view.update({
    items: [
      { ...heading, title: "Available" },
      { ...row, entry: { label: "Execute" } },
    ],
  });
  assert.equal(host.firstElementChild.tagName, "H2");
  assert.equal(host.firstElementChild.textContent, "Available");
  assert.equal(host.querySelector("label").textContent, "Execute");
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "Unfinished");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [2, 6]);
  view.dispose();
  host.remove();
});
