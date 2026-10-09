# Named widget interfaces (#16)

Deferred for future review at Max's request. This is a proposal, with no
implementation started. Keep the current reference contract until a second
implementing package can demonstrate that its replacement simplifies both the
author's declaration and Leaf's implementation.

## Current contract

A worker points at a goal with `on="parser-tests"`. Leaf finds that element,
then checks that its tag has `role: "goal"` in `$work.widgets`. An exclusive document-local reference uses the same mechanism. The test vocabulary
retains this independent contract; Atlas now uses a native overview section:

```text
lf-atlas-worker.x-refers = {
  "on": {
    "via": "$work.widgets",
    "where": {"role": "goal"}
  }
}
lf-test-plan.x-refers = {
  "readings": {
    "via": "$work.widgets",
    "where": {"role": "readings"},
    "owns": true
  }
}
```

These excerpts identify separate registry entries; the names before `=`
locate each declaration. The exclusive-reference example belongs to the test
vocabulary, while Atlas owns the worker reference. Validation and work projection read the same canonical
role table. There is no duplicate role table to remove.

## Proposed contract

Name the required interface directly:

```text
lf-atlas-worker.x-refers = {
  "on": {"interface": "command/goal"}
}
lf-test-plan.x-refers = {
  "readings": {
    "interface": "command/readings",
    "owns": true
  }
}
```

Implementing tags would declare membership in the corresponding interface.
The syntax for that declaration is unresolved. Membership must replace the
existing role fact, with projection deriving its roles from the same canonical
declaration. Adding membership beside `$work.widgets` would create two
sources of truth.

The referenced elements and authored attributes stay the same. `owns: true`
still requires a readings element to have exactly one owning command in its
document. Generic references remain available.

## Why defer it

Named interfaces could remove dotted-path resolution and predicate matching
from typed reference validation. The demonstrated use is small: two typed
reference declarations in one implementing package, both testing role equality.
Changing their spelling alone establishes no implementation saving; the role
table also carries state and projection metadata that still need an owner.

Revisit this with a second package implementing the same interfaces. Compare
complete declarations, validation, and projection; remove the old typed
reference interpreter and role-membership path in the candidate. Preserve
document-local references, exactly-one-owner validation, and package extensibility.
If the candidate needs more metadata machinery or hardcoded command roles in
core, retain the current contract. Keep external data, authored state, and
visual parts under their existing authorities.

## Owning sources

- [Command Hub registry](../examples/command-hub.page/registry.json):
  `$work.widgets` and `lf-atlas-worker.x-refers.on`; the work test fixture
  owns the exclusive-reference contrast.
- [Registry contract](../skills/leaf/scripts/leaf/registry/contract.py):
  `registry_path` and `reference_relation_error`.
- [Instance validation](../skills/leaf/scripts/leaf/validation/instances.py):
  target matching, reference checks, and ownership checks.
- [Public work projection](../skills/leaf/assets/runtime/work.js):
  role lookup and state metadata consumers.

This note preserves proposal #16 from the interface review page. It records
the future experiment, not approval for a production cutover.
