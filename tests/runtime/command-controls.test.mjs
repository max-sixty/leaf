/* A native command control retains one activation across attachment and DOM lifetimes. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  commandScope,
  keys,
  paintKeys,
  reflectFirstScopes,
  reflectKeys,
} from "../../skills/leaf/assets/runtime/keyboard/scopes.js";

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
  assert.equal(control.disabled, true);
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
  assert.equal(control.disabled, true);
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
    [...contributionEntries()].find((offered) => offered.target === owner),
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
  source.setAttribute("aria-disabled", "true");
  refused();
  source.removeAttribute("aria-disabled");
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
  const { commandEntries, bindings, live } =
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
  assert.equal(control.disabled, true);
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
  assert.equal(control.disabled, true);
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
