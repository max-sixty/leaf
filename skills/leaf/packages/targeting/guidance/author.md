Use `lf-targeting` when a user needs to identify exact parts of real page markup while
proposing changes. Put it inside `lf-ask` and put the real operable artifact in its one
`lf-target-preview`; the user selects from the rendered result rather than a replica.

```html
<lf-ask id="landing-changes-ask">
  <h2>Which exact changes should be made?</h2>
  <lf-targeting id="landing-changes">
    <lf-target-preview id="landing-preview">
      <section id="hero" class="landing-card">
        <h3 class="section-title">Build the next release</h3>
      </section>
      <section class="landing-card">
        <h3 class="section-title">Inspect the evidence</h3>
      </section>
    </lf-target-preview>
  </lf-targeting>
</lf-ask>
```

Give an element an id when it has its own durable identity. Give repeated elements the
same meaningful class when the user may change them together. Selection offers the
chosen element and its complete authored ancestor chain.

Each submitted target's `reference` identifies it: the element's authored id, or, for
an element without one, a structural path from its nearest id-bearing ancestor or
the preview. Its `scope` says whether a change applies to that element alone or to
every preview element carrying its `className`. Its name, label, and visible text
describe it but never identify it. Each style or prose `change` carries its target's
`key` in `target`; resolve that key to the target's reference. A submitted action is
the durable record; unsubmitted selection and preview changes stay local to the user.
