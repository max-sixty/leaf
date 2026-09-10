# Visual targeting

Use `lf-targeting` when a reader needs to identify exact parts of real page markup while
proposing changes. Put it inside `lf-ask` and put the real operable artifact in its one
`lf-target-preview`; the reader selects from the rendered result rather than a replica.

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
same meaningful class when the reader may change them together. Selection offers the
clicked element and at most three ancestors. The reader can retain and rename several
targets, choose instance or class scope, preview supported box-model changes, remove one
change or revert the draft, and add prose for a named target before submitting once.

The submitted `targets` preserve an authored id when available and always include a
structural path plus short visible context. Each style or prose `change` carries its
target key separately. Process that key as the reference; names make the draft readable,
but consumers must not infer identity from prose. A submitted action is the durable
record; unsubmitted selection and preview changes stay local to the reader.
