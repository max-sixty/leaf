# Explain an interface with a live specimen

When a page explains how a Leaf widget, verb, or event flow behaves, let the reader
produce the behavior and watch what it writes, rather than describing it. A live
`lf-specimen` gives the reader a disposable page with its own event log;
`skills/leaf/references/page-authoring.md`, "Live specimens", covers its markup and
host behavior.

```html
<p>Press <strong>Enter specimen</strong>, then pick <em>Now</em> and then
<em>Later</em>: each pick sends a <code>choose</code>. Press <kbd>z</kbd> to undo
the second pick and watch the feed record it.</p>
<lf-specimen id="try-specimen" label="release question">
  <template id="try-page" data-specimen>
    <lf-ask id="ship-ask">
      <h2>When should this ship?</h2>
      <lf-options id="ship" choose>
        <lf-option id="ship-now"><strong>Now</strong> Today, behind the flag.</lf-option>
        <lf-option id="ship-later"><strong>Later</strong> Next week.</lf-option>
      </lf-options>
    </lf-ask>
    <lf-activity id="specimen-feed"></lf-activity>
  </template>
</lf-specimen>
```

The template holds only the demonstrated page: the interface under explanation,
authored as a real page would author it, and an `lf-activity` feed of the specimen's
own log, so each gesture shows the event it writes as it lands. Without the feed,
the reader sees the widget change but not the log the page is about. Nothing in the
template refers to the specimen or tells the reader how to operate it.

The walkthrough goes in the parent's prose directly above the specimen. It lists
the gestures to try, in an order that exercises each verb the page explains, undo
included. An idle specimen ignores clicks until the reader presses **Enter
specimen**, so the prose names that button first.

Before handing the page over, drive the specimen from the parent page with only
what the prose tells the reader. A probe that already knows the host's controls
shows that the specimen works, but not that a reader can get it to work. Then read
every line the feed prints for the walkthrough's gestures; a verb the feed words
badly misleads the reader about the log the page explains.
