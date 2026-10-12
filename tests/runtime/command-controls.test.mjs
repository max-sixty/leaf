/* A native command control retains one activation across attachment and DOM lifetimes. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  commandScope,
  commandsOn,
  commandsWithin,
  projectCommandScope,
  keys,
  paintKeys,
  reflectFirstScopes,
  reflectKeys,
} from "../../skills/leaf/assets/runtime/keyboard/scopes.js";
import { setQuickShortcuts } from "../../skills/leaf/assets/runtime/keyboard/bindings.js";

test("quick shortcuts withdraw character routes while native commands and modified keys remain", () => {
  const owner = document.createElement("section");
  const character = document.createElement("button");
  const modified = document.createElement("button");
  owner.append(character, modified);
  document.body.append(owner);
  let runs = 0;
  keys(
    character,
    commandScope("Character action", [
      {
        id: "preference.character",
        title: "Run character action",
        keys: ["a", "Shift+a", "1", "?"],
        control: character,
        run: () => runs++,
      },
    ]),
  );
  keys(
    modified,
    commandScope("Modified action", [
      {
        id: "preference.modified",
        title: "Run modified action",
        keys: ["Mod+a", "Alt+a", "Shift+ArrowLeft", "Enter", " "],
        control: modified,
        run: () => runs++,
      },
    ]),
  );
  try {
    reflectFirstScopes();
    assert.equal(character.getAttribute("aria-keyshortcuts"), "a Shift+a 1 ?");
    setQuickShortcuts(false);
    paintKeys();
    reflectKeys();
    assert.equal(character.getAttribute("aria-keyshortcuts"), null);
    assert.equal(character.disabled, false);
    assert.equal(
      modified.getAttribute("aria-keyshortcuts"),
      "Meta+a Control+a Alt+a Shift+ArrowLeft Enter Space",
    );
    character.click();
    modified.click();
    assert.equal(runs, 2);
    setQuickShortcuts(true);
    paintKeys();
    reflectKeys();
    assert.equal(character.getAttribute("aria-keyshortcuts"), "a Shift+a 1 ?");
  } finally {
    setQuickShortcuts(true);
    owner.remove();
  }
});

test("a command owns its native button across availability, replacement and reconnection", () => {
  const owner = document.createElement("section");
  let control = document.createElement("button");
  owner.append(control);
  document.body.append(owner);
  let available = true;
  let count = 0;
  const scope = commandScope("Probe commands", [
    {
      id: "probe.apply",
      title: "Apply",
      keys: ["x"],
      control: () => control,
      when: () => available,
      run: () => count++,
    },
  ]);
  keys(owner, scope);
  reflectFirstScopes();
  control.click();
  assert.equal(count, 1);
  available = false;
  paintKeys();
  reflectKeys();
  assert.equal(control.getAttribute("aria-disabled"), "true");
  assert.equal(control.disabled, false);
  control.click();
  assert.equal(count, 1);
  available = true;
  paintKeys();
  reflectKeys();
  assert.equal(control.disabled, false);
  const previous = control;
  control = document.createElement("button");
  previous.replaceWith(control);
  paintKeys();
  reflectKeys();
  previous.click();
  control.click();
  assert.equal(count, 2);
  owner.remove();
  control.click();
  assert.equal(count, 2);
  document.body.append(owner);
  keys(owner, scope);
  reflectFirstScopes();
  control.click();
  assert.equal(count, 3);
  available = false;
  paintKeys();
  reflectKeys();
  assert.equal(control.getAttribute("aria-disabled"), "true");
  assert.equal(control.disabled, false);
  keys(owner, "Replacement", [
    { id: "probe.other", title: "Other", keys: ["x"], run: () => (count += 10) },
  ]);
  reflectFirstScopes();
  assert.equal(control.disabled, false);
  assert.equal(control.getAttribute("aria-keyshortcuts"), null);
  control.click();
  assert.equal(count, 3);
  owner.remove();
});

// A new thread card's Resolve, focused and pressed by a key in the same task, did
// nothing until a paint had wired it.
test("a button declared on itself activates before its declaration is painted", () => {
  const control = document.createElement("button");
  document.body.append(control);
  let count = 0;
  keys(control, "Probe commands", [
    { id: "probe.press", title: "Press", keys: ["Enter"], control, run: () => count++ },
  ]);
  control.click();
  assert.equal(count, 1);
  control.remove();
});

// A projected entry retains native origin/surface/input without a second callback.
test("a contribution invokes its declared command and derives refusal from it", async () => {
  const { registerContribution } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const { contributionEntry } =
    await import("../../skills/leaf/assets/runtime/contribution-controls.js");
  const target = document.createElement("section");
  document.body.append(target);
  let available = true;
  const received = [];
  const scope = commandScope("Projected action", [
    {
      id: "probe.projected",
      title: "Apply",
      keys: ["x"],
      when: () => available,
      run: (_binding, context) =>
        received.push([context.origin, context.surface, context.input]),
    },
  ]);
  const cached = contributionEntry({
    key: "apply",
    icon: "check",
    label: "Apply",
    scope,
    activation: "probe.projected",
  });
  const registration = registerContribution({
    key: "projected-command-probe",
    target,
    read: () => ({ entries: [cached] }),
  });
  const control = document.createElement("button");
  target.append(control);
  assert.equal(
    registration.activate("apply", {
      origin: control,
      surface: "map",
      input: "pointer",
    }),
    true,
  );
  assert.deepEqual(received, [[control, "map", "pointer"]]);
  available = false;
  paintKeys();
  reflectKeys();
  assert.equal(registration.entry("apply").disabled, true);
  assert.equal(
    registration.activate("apply", {
      origin: control,
      surface: "margin",
      input: "keyboard",
    }),
    false,
  );
  assert.equal(received.length, 1);
  available = true;
  paintKeys();
  reflectKeys();
  assert.equal(registration.entry("apply").disabled, false);
  registration.unregister();
  assert.equal(registration.activate("apply"), false);
  target.remove();
});

test("a control lookup during contribution normalization waits for the complete reading", async () => {
  const { registerContribution, watchContributions } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const { contributionEntry } =
    await import("../../skills/leaf/assets/runtime/contribution-controls.js");
  const target = document.createElement("section");
  document.body.append(target);
  let registration;
  let reading = false;
  let state = "idle";
  const seen = [];
  const scope = commandScope("Reading transaction", [
    {
      id: "probe.reading",
      title: "Apply",
      control: () => registration?.control("apply"),
      run: () => {},
    },
  ]);
  const stop = watchContributions(({ immediate }) => {
    seen.push({ reading, state: registration.entry("apply").state, immediate });
  });
  try {
    registration = registerContribution({
      key: "reading-transaction-probe",
      target,
      read: () => {
        reading = true;
        try {
          return {
            state,
            entries: [
              contributionEntry({
                key: "apply",
                icon: "check",
                label: "Apply",
                state,
                scope,
                activation: "probe.reading",
              }),
            ],
          };
        } finally {
          reading = false;
        }
      },
    });
    state = "engaged";
    registration.update({ immediate: true });
    assert.deepEqual(seen, [{ reading: false, state: "engaged", immediate: true }]);
  } finally {
    stop();
    registration?.unregister();
    target.remove();
  }
});

test("a shared button selects its live state and context-only routes retain their argument", () => {
  const owner = document.createElement("section");
  const button = document.createElement("button");
  owner.append(button);
  document.body.append(owner);
  let open = false;
  const result = [];
  keys(owner, "Changing control", [
    {
      id: "probe.open",
      title: "Open",
      keys: ["x"],
      control: button,
      when: () => !open,
      run: () => {
        result.push("open");
        open = true;
        paintKeys();
      },
    },
    {
      id: "probe.close",
      title: "Close",
      keys: ["x"],
      control: button,
      when: () => open,
      run: () => {
        result.push("close");
        open = false;
        paintKeys();
      },
    },
  ]);
  reflectFirstScopes();
  button.click();
  reflectKeys();
  button.click();
  assert.deepEqual(result, ["open", "close"]);
  const second = document.createElement("button");
  owner.append(second);
  keys(owner, "Context-only routes", [
    {
      id: "probe.route",
      title: "Route",
      keys: [],
      routes: [
        { id: "probe.first", title: "First", contextKeys: ["1"], control: button },
        { id: "probe.second", title: "Second", contextKeys: ["2"], control: second },
      ],
      run: (binding) => result.push(binding),
    },
  ]);
  reflectFirstScopes();
  button.click();
  second.click();
  assert.deepEqual(result, ["open", "close", "1", "2"]);
  owner.remove();
});

// Getter controls are claimed at reflection, so their previous attributes must not
// leave a projected command one reading behind its native source.
test("a getter button and its contribution agree on their first and replacement readings", async () => {
  const { live } =
    await import("../../skills/leaf/assets/runtime/keyboard/bindings.js");
  const { registerContribution } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const { contributionEntry } =
    await import("../../skills/leaf/assets/runtime/contribution-controls.js");
  const owner = document.createElement("section");
  let source = document.createElement("button");
  source.disabled = true;
  owner.append(source);
  document.body.append(owner);
  let runs = 0;
  const row = {
    id: "probe.getter-reading",
    title: "Apply",
    control: () => source,
    run: () => runs++,
  };
  const scope = commandScope("Getter source", [row]);
  keys(owner, scope);
  const registration = registerContribution({
    key: "getter-reading-probe",
    target: owner,
    read: () => ({
      entries: [
        contributionEntry({
          key: "apply",
          icon: "check",
          label: "Apply",
          activation: row.id,
          scope,
        }),
      ],
    }),
  });
  try {
    const available = () => {
      assert.equal(live(row), true);
      assert.equal(source.disabled, false);
      assert.equal(registration.entry("apply").disabled, false);
      assert.equal(registration.activate("apply"), true);
    };
    reflectFirstScopes();
    available();
    const previous = source;
    source = document.createElement("button");
    source.disabled = true;
    source.setAttribute("aria-disabled", "true");
    previous.replaceWith(source);
    paintKeys();
    reflectKeys();
    available();
    assert.equal(runs, 2);
  } finally {
    registration.unregister();
    owner.remove();
  }
});

test("source constraints and derived disabled output share one availability reading", async () => {
  const { live } =
    await import("../../skills/leaf/assets/runtime/keyboard/bindings.js");
  const { registerContribution, contributionEntries } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const { contributionEntry, presentContributionHost, trackContributionControl } =
    await import("../../skills/leaf/assets/runtime/contribution-controls.js");
  const owner = document.createElement("section");
  const fieldset = document.createElement("fieldset");
  const legend = document.createElement("legend");
  const source = document.createElement("button");
  fieldset.append(legend, source);
  owner.append(fieldset);
  document.body.append(owner);
  let available = true;
  let runs = 0;
  const row = {
    id: "probe.constraints",
    title: "Apply",
    keys: ["x"],
    control: source,
    when: () => available,
    run: () => runs++,
  };
  const scope = commandScope("Source constraints", [row]);
  keys(owner, scope);
  reflectFirstScopes();
  const cached = contributionEntry({
    key: "apply",
    icon: "check",
    label: "Apply",
    activation: row.id,
    scope,
  });
  const registration = registerContribution({
    key: "constraints-probe",
    target: owner,
    read: () => ({ entries: [cached] }),
  });
  const projection = document.createElement("button");
  owner.append(projection);
  trackContributionControl(
    [...contributionEntries()].find((offered) => offered.target() === owner),
    "map",
    "apply",
    projection,
  );
  const refresh = () => {
    paintKeys();
    reflectKeys();
    presentContributionHost(projection, registration.entry("apply"));
  };
  const refused = () => {
    refresh();
    assert.equal(live(row), false);
    assert.equal(registration.entry("apply").disabled, true);
    assert.equal(projection.getAttribute("aria-disabled"), "true");
    assert.equal(registration.activate("apply"), false);
  };
  // Owned attributes are presentation, not a second source of command availability.
  source.setAttribute("aria-disabled", "true");
  refresh();
  assert.equal(live(row), true);
  assert.equal(source.getAttribute("aria-disabled"), null);
  const input = document.createElement("input");
  owner.append(input);
  row.control = input;
  input.setAttribute("aria-disabled", "true");
  refused();
  input.removeAttribute("aria-disabled");
  row.control = source;
  available = false;
  refused();
  available = true;
  refresh();
  assert.equal(source.disabled, false);
  assert.equal(registration.entry("apply").disabled, false);
  assert.equal(registration.activate("apply"), true);
  fieldset.disabled = true;
  refused();
  legend.append(source);
  refresh();
  assert.equal(live(row), true);
  assert.equal(registration.entry("apply").disabled, false);
  assert.equal(registration.activate("apply"), true);
  assert.equal(runs, 2);
  // A declaration may return its generated projected host. Its own stale ARIA paint
  // must not become a new authority that prevents its false-to-true transition.
  row.control = projection;
  available = false;
  refused();
  available = true;
  refresh();
  assert.equal(live(row), true);
  assert.equal(registration.entry("apply").disabled, false);
  assert.equal(projection.getAttribute("aria-disabled"), "false");
  registration.unregister();
  projection.setAttribute("aria-disabled", "true");
  assert.equal(live(row), false);
  assert.equal(registration.activate("apply"), false);
  owner.remove();
});

test("each contribution publication validates its current activation capability", async () => {
  const { registerContribution } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const target = document.createElement("section");
  document.body.append(target);
  let action = false;
  const registration = registerContribution({
    key: "changing-action-probe",
    target,
    read: () => ({
      entries: [
        {
          key: "changing",
          label: "Changing",
          icon: "check",
          behavior: action ? "action" : "status",
        },
      ],
    }),
  });
  action = true;
  assert.throws(
    () => registration.update(),
    /unscoped contribution action needs an activate function/,
  );
  assert.equal(registration.entry("changing").behavior, "status");
  registration.unregister();
  target.remove();
});

test("context aliases project the selected source route's availability", async () => {
  const { commandEntries, commandPresentations, bindings, live } =
    await import("../../skills/leaf/assets/runtime/keyboard/bindings.js");
  const { scopesAt } =
    await import("../../skills/leaf/assets/runtime/keyboard/scopes.js");
  const owner = document.createElement("section");
  const one = document.createElement("button");
  const two = document.createElement("button");
  owner.append(one, two);
  document.body.append(owner);
  let first = false;
  keys(owner, "Route aliases", [
    {
      id: "probe.aliases",
      title: "Act",
      keys: ["ArrowLeft", "ArrowRight"],
      routes: [
        {
          id: "probe.alias-one",
          title: "First",
          binding: "ArrowLeft",
          contextKeys: ["1"],
          control: one,
          when: () => first,
        },
        {
          id: "probe.alias-two",
          title: "Second",
          binding: "ArrowRight",
          contextKeys: ["2"],
          control: two,
          when: () => !first,
        },
      ],
      run: () => {},
    },
  ]);
  reflectFirstScopes();
  const contextual = scopesAt(owner).find((scope) => scope.contextual).rows[0];
  assert.deepEqual(bindings(contextual), ["1", "2"]);
  assert.equal(live(contextual), true);
  assert.deepEqual(
    commandEntries(contextual).map(({ id }) => id),
    ["probe.alias-two"],
  );
  assert.deepEqual(commandEntries(contextual, ["1"]), []);
  assert.deepEqual(
    commandPresentations(contextual, bindings(contextual), {
      includeUnavailable: true,
    }).map(({ id }) => id),
    ["probe.alias-one", "probe.alias-two"],
  );
  first = true;
  paintKeys();
  reflectKeys();
  assert.deepEqual(
    commandEntries(contextual).map(({ id }) => id),
    ["probe.alias-one"],
  );
  assert.deepEqual(commandEntries(contextual, ["2"]), []);
  owner.remove();
});

test("the command reference retains unavailable command identities", async () => {
  const { commandPresentations } =
    await import("../../skills/leaf/assets/runtime/keyboard/bindings.js");
  const row = { id: "probe.leave", keys: ["Tab"], when: () => false, run: () => {} };
  assert.deepEqual(commandPresentations(row), []);
  assert.deepEqual(
    commandPresentations(row, ["Tab"], { includeUnavailable: true }).map(
      ({ id }) => id,
    ),
    ["probe.leave"],
  );
});

test("page command scopes share native activation and hand removed controls back", async () => {
  const { pageScope } =
    await import("../../skills/leaf/assets/runtime/keyboard/register.js");
  const control = document.createElement("button");
  document.body.append(control);
  let available = true;
  let runs = 0;
  const remove = pageScope("versions", {
    rows: [
      {
        id: "probe.page",
        title: "Apply page action",
        keys: ["x"],
        control,
        when: () => available,
        run: () => runs++,
      },
    ],
  });
  reflectFirstScopes();
  control.click();
  assert.equal(runs, 1);
  available = false;
  paintKeys();
  reflectKeys();
  assert.equal(control.getAttribute("aria-disabled"), "true");
  assert.equal(control.disabled, false);
  remove();
  reflectKeys();
  assert.equal(control.disabled, false);
  control.click();
  assert.equal(runs, 1);
  control.remove();
});

test("a projected scope withdrawal preserves a native control's pending handback", async () => {
  const { projectCommandScope } =
    await import("../../skills/leaf/assets/runtime/keyboard/scopes.js");
  const owner = document.createElement("section");
  const control = document.createElement("button");
  owner.append(control);
  document.body.append(owner);
  keys(owner, "Temporary action", [
    {
      id: "probe.temporary",
      title: "Temporary",
      keys: ["x"],
      control,
      when: () => false,
      run: () => {},
    },
  ]);
  reflectFirstScopes();
  assert.equal(control.getAttribute("aria-disabled"), "true");
  assert.equal(control.disabled, false);
  const projection = commandScope("Projected keys", [
    { id: "probe.projected-only", title: "Project", keys: ["y"], run: () => {} },
  ]);
  projectCommandScope(control, "probe", projection);
  keys(owner, "Empty", []);
  projectCommandScope(control, "probe", null);
  reflectKeys();
  assert.equal(control.disabled, false);
  owner.remove();
});

test("a disappearing projected command refuses instead of becoming a generic action", async () => {
  const { registerContribution } =
    await import("../../skills/leaf/assets/runtime/contributions.js");
  const owner = document.createElement("section");
  document.body.append(owner);
  let routeId = "probe.current";
  let runs = 0;
  const row = {
    id: "probe.changing",
    title: "Changing",
    keys: ["x"],
    routes: () => [{ id: routeId, title: "Current", binding: "x" }],
    run: () => runs++,
  };
  const scope = commandScope("Changing projection", [row]);
  const registration = registerContribution({
    key: "changing-projected-command",
    target: owner,
    read: () => ({
      entries: [
        {
          key: "apply",
          icon: "check",
          label: "Apply",
          scope,
          activation: "probe.current",
        },
      ],
    }),
  });
  assert.equal(registration.activate("apply"), true);
  routeId = "probe.other";
  paintKeys();
  reflectKeys();
  assert.equal(registration.entry("apply").disabled, true);
  assert.equal(registration.activate("apply"), false);
  routeId = "probe.current";
  paintKeys();
  reflectKeys();
  assert.equal(registration.entry("apply").disabled, false);
  assert.equal(registration.activate("apply"), true);
  const run = row.run;
  delete row.run;
  paintKeys();
  reflectKeys();
  assert.equal(registration.entry("apply").disabled, true);
  assert.equal(registration.activate("apply"), false);
  row.run = run;
  paintKeys();
  reflectKeys();
  assert.equal(registration.activate("apply"), true);
  assert.equal(runs, 3);
  registration.unregister();
  owner.remove();
});

// Filling an in-flow face would resize the click target holding it before activation, so
// every lent face, a button's child included, keeps an out-of-flow seat.
test("a lent hint inside a button keeps its out-of-flow seat after withdrawal", async () => {
  const { createCommandHints } =
    await import("../../skills/leaf/assets/runtime/keyboard/command-hints.js");
  const { registerCoveringAuxiliarySurface } =
    await import("../../skills/leaf/assets/runtime/keyboard/register.js");
  registerCoveringAuxiliarySurface(() => null);
  const owner = document.createElement("section");
  const control = document.createElement("button");
  const badge = document.createElement("kbd");
  control.append(badge);
  owner.append(control);
  document.body.append(owner);
  keys(owner, "Hint ownership", [
    {
      id: "probe.hint-seat",
      title: "Apply",
      keys: ["x"],
      control,
      bindingBadge: badge,
      run: () => {},
    },
  ]);
  reflectFirstScopes();
  control.focus();
  const hints = createCommandHints({ presentedControl: () => null });
  try {
    hints.paint();
    assert.equal(badge.classList.contains("lf-binding-seat"), true);
    hints.destroy();
    assert.equal(badge.classList.contains("lf-binding-seat"), true);
    assert.equal(control.contains(badge), true);
  } finally {
    owner.remove();
  }
});

test("a scope's attachment and re-render run its latest callbacks and read only its own element", async () => {
  const { html, render } = await import("/vendor/browser-runtime.js");
  const other = document.createElement("button");
  document.body.append(other);
  keys(other, "Elsewhere", [{ id: "probe.elsewhere", keys: ["x"], title: "x" }]);
  const root = document.createElement("section");
  document.body.append(root);
  const invoked = [];
  const paint = (reading, available = true) =>
    render(
      html`<button
        ${commandsOn("Template", [
          {
            id: "probe.template",
            keys: ["y"],
            title: "act",
            when: () => available,
            run: () => invoked.push(reading),
          },
        ])}
      ></button>`,
      root,
    );
  paint("first");
  reflectFirstScopes();
  reflectKeys();
  const element = root.querySelector("button");
  assert.equal(element.getAttribute("aria-keyshortcuts"), "y");

  const read = other.getAttribute;
  let otherReads = 0;
  other.getAttribute = (...args) => (otherReads++, read.apply(other, args));
  paint("second", false);
  reflectFirstScopes();
  reflectKeys();
  assert.equal(otherReads, 0, "a re-render reads no other scoped element");
  assert.equal(element.getAttribute("aria-keyshortcuts"), null);
  paint("third");
  reflectFirstScopes();
  reflectKeys();
  assert.equal(element.getAttribute("aria-keyshortcuts"), "y");
  commandsWithin(root)[0].row.run();
  assert.deepEqual(invoked, ["third"]);

  const added = document.createElement("button");
  root.append(added);
  keys(added, "Added", [{ id: "probe.added", keys: ["z"], title: "z" }]);
  reflectFirstScopes();
  reflectKeys();
  assert.equal(otherReads, 0, "an imperative attachment reads no other scoped element");
  assert.equal(added.getAttribute("aria-keyshortcuts"), "z");
  root.remove();
  other.remove();
});

test("a template scope refused on re-render withdraws its shortcuts, and its aliases follow each reading", async () => {
  const { html, render } = await import("/vendor/browser-runtime.js");
  const { scopesAt } =
    await import("../../skills/leaf/assets/runtime/keyboard/scopes.js");
  const root = document.createElement("section");
  document.body.append(root);
  const paint = (title, second) =>
    render(
      html`<button
        ${commandsOn(title, [
          {
            id: "probe.first",
            keys: ["y"],
            contextKeys: ["Enter"],
            title: "a",
            run() {},
          },
          { id: "probe.second", keys: ["y"], title: "b", when: () => second, run() {} },
        ])}
      ></button>`,
      root,
    );
  paint("First", false);
  reflectFirstScopes();
  reflectKeys();
  const element = root.querySelector("button");
  assert.equal(element.getAttribute("aria-keyshortcuts"), "y Enter");
  paint("Second", false);
  reflectFirstScopes();
  assert.deepEqual(
    scopesAt(element).map(({ title }) => title),
    ["Second", "Second"],
  );

  paint("Second", true);
  assert.throws(() => reflectFirstScopes(), /y/);
  reflectKeys();
  assert.equal(commandsWithin(root).length, 0);
  assert.equal(element.getAttribute("aria-keyshortcuts"), null);
  root.remove();
});

test("template scopes follow current rows and retire without removing projected commands", async () => {
  const { html, nothing, render } = await import("/vendor/browser-runtime.js");
  const root = document.createElement("section");
  document.body.append(root);
  const invoked = [];
  const rows = (id, key, available = true) => [
    {
      id,
      title: id,
      keys: [key],
      when: () => available,
      run: () => invoked.push(id),
    },
  ];
  const paint = (title, declaration, options, active = true) =>
    render(
      html`<span ${active ? commandsOn(title, declaration, options) : nothing}></span>`,
      root,
    );
  const part = paint("First scope", rows("probe.first", "x"));
  const element = root.querySelector("span");
  reflectFirstScopes();
  assert.equal(element.getAttribute("aria-keyshortcuts"), "x");
  commandsWithin(root)[0].row.run();

  paint("Second scope", rows("probe.second", "y"), { when: () => false });
  reflectFirstScopes();
  assert.equal(commandsWithin(root).length, 0);
  assert.equal(element.getAttribute("aria-keyshortcuts"), null);
  paint("Second scope", rows("probe.second", "y"));
  reflectFirstScopes();
  const [current] = commandsWithin(root);
  assert.equal(current.scope.title, "Second scope");
  assert.equal(current.row.id, "probe.second");
  current.row.run();
  assert.deepEqual(invoked, ["probe.first", "probe.second"]);
  assert.equal(root.querySelector("span"), element);
  assert.equal(element.getAttribute("aria-keyshortcuts"), "y");
  paint("Second scope", rows("probe.second", "y", false));
  reflectFirstScopes();
  assert.equal(commandsWithin(root).length, 0);
  assert.equal(element.getAttribute("aria-keyshortcuts"), null);
  paint("Second scope", rows("probe.second", "y"));
  reflectFirstScopes();
  const writes = new MutationObserver(() => {});
  writes.observe(element, { attributes: true });
  paint("Second scope", rows("probe.second", "y"));
  reflectFirstScopes();
  assert.deepEqual(writes.takeRecords(), [], "an unchanged scope writes no attributes");
  writes.disconnect();

  const projected = commandScope("Projected", rows("probe.projected", "z"));
  projectCommandScope(element, "test", projected);
  paint("Unused", [], undefined, false);
  assert.deepEqual(
    commandsWithin(root).map(({ row }) => row.id),
    ["probe.projected"],
  );
  assert.equal(element.getAttribute("aria-keyshortcuts"), "z");

  paint(commandScope("Returned", rows("probe.returned", "x")));
  part.setConnected(false);
  assert.deepEqual(
    commandsWithin(root).map(({ row }) => row.id),
    ["probe.projected"],
  );
  paint("While detached", rows("probe.detached", "y"));
  assert.deepEqual(
    commandsWithin(root).map(({ row }) => row.id),
    ["probe.projected"],
  );
  part.setConnected(true);
  assert.deepEqual(
    commandsWithin(root).map(({ row }) => row.id),
    ["probe.detached", "probe.projected"],
  );
  render(nothing, root);
  assert.equal(commandsWithin(root).length, 0);
  root.remove();
});
