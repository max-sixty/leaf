# Explain an interface with a live sample

A page that explains how a Leaf widget, verb, or event flow behaves lets the user
produce the behavior and watch what it writes. A live `lf-sample` gives them a
disposable page with its own event log (`skills/leaf/references/page-authoring.md`,
"Live samples").

```html
<p>Pick <em>Now</em> and then <em>Later</em>: each pick sends a
<code>choose</code>. Press <kbd>z</kbd> to undo
the second pick and watch the feed record it.</p>
<lf-sample id="try-sample" label="release question">
  <template id="try-page" data-sample>
    <lf-ask id="ship-ask">
      <h2>When should this ship?</h2>
      <lf-options id="ship" choose>
        <lf-option id="ship-now"><strong>Now</strong> Today, behind the flag.</lf-option>
        <lf-option id="ship-later"><strong>Later</strong> Next week.</lf-option>
      </lf-options>
    </lf-ask>
    <lf-activity id="sample-feed"></lf-activity>
  </template>
</lf-sample>
```

The template holds only the demonstrated page: the interface, authored as a real page
would author it, and an `lf-activity` feed of the sample's own log, so each gesture
shows the event it writes. Nothing in it mentions the sample or how to operate it. The
parent's prose directly above the sample lists the gestures to try, in an order that
exercises each verb the page explains, undo included.

Before handing the page over, drive the sample from the parent page using only what
the prose tells the user: a probe that knows more shows the sample works, not that a
user can work it. Then read each line the feed prints for those gestures, since a
badly worded line misleads the user about the log the page explains.
