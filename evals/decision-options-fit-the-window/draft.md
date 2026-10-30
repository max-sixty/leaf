The user commented on a long thread they were reading in a margin card:
"particularly in times like this, it would be useful to have a way of opening the
thread in the expanded floating panel; so we can see it all; can we think about
how to do that?"

You investigated and prototyped. Your notes:

- Today a margin card is 444px wide. A thread reaches the floating panel's thread
  view only by closing the card, pressing the Threads mark and then the thread's
  row: three presses. That view opens 540px wide. The panel also has a 760px
  width, More room to write, for long drafts.
- Measured on this thread in a 1640x1010 window: the margin card shows 864 of
  1245px of it (69%), the panel's thread view 778 of 1007px (77%), and the panel
  at 760px all 839px.
- The routes, from today's behavior to the largest change:
  - today, "Keep Threads as the only way in": three presses, 540px.
  - panel, "Add Open in panel to the card": an expand icon in the card's head,
    beside Resolve and Close. One press closes the card and opens the thread in
    the panel's view at today's 540px.
  - reading, "Open in panel at reading size": the same icon, and the view opens
    760px wide and may rise to 24px from the window's top. The whole thread fits.
    You recommend it.
- The captures below come from a prototype. Its implementation is not included in
  this workspace.
- Captures, each a 1640x1010 window with the thread open beside the column:
  - evals/decision-options-fit-the-window/captures/start-card.png: today's margin
    card, where every route starts.
  - evals/decision-options-fit-the-window/captures/card-with-button.png: the card
    with the Open in panel icon in its head, at about x 1180 to 1640, y 10 to 80.
  - evals/decision-options-fit-the-window/captures/today-panel.png: after Threads,
    then the thread's row: the panel's view at 540px.
  - evals/decision-options-fit-the-window/captures/panel-panel.png: after Open in
    panel at today's size.
  - evals/decision-options-fit-the-window/captures/reading-panel.png: after Open
    in panel at reading size, the whole thread.
- Once a route is chosen, you'll build it from the prototype into the runtime with
  a keyboard route, carry a reply being written into the panel, and show the user
  a before/after still and the journey in Firefox.

You have written this first draft of the page. Its images name the capture files;
register them with `leaf page media` and use the URLs it prints. Finish the page for
handoff and save it.

```html
<!doctype html>
<html lang="en">
  <head>
    <title>Open a long thread in the panel?</title>
    <meta
      name="description"
      content="Three ways a long thread read in a narrow margin card could move into Leaf's floating panel, measured at a 1640×1010 window, with a live prototype of each."
    />
    <style>
      #route-choice {
        --playground-choice-columns: minmax(0, 1fr);
      }
      .route-frames {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--sp-3);
        margin: 0;
      }
      .route-frames figure {
        margin: 0;
      }
      .route-frames figcaption {
        color: var(--ink-2);
        font-size: var(--t-6, 0.85em);
        margin-top: var(--sp-1);
      }
      .route-frames img {
        display: block;
        width: 100%;
        border: 1px solid var(--border-2);
        border-radius: var(--r-m, 6px);
      }
      @media (max-width: 720px) {
        .route-frames {
          grid-template-columns: minmax(0, 1fr);
        }
      }
    </style>
  </head>
  <body>
    <main class="layout-column">
      <header id="top">
        <h1>Open a long thread in the panel?</h1>
        <p class="lede">
          The panel already reads a whole thread at full width: a thread opened from
          Threads stands in its view, and a card's thread can go there in one press. At
          reading size, the thread from your screenshot fits with no scrolling.
        </p>
      </header>

      <section id="which-surface">
        <h2>Which "expanded panel" this means</h2>
        <p>
          I took the expanded floating panel to be the panel with a thread's view open
          over its row, the view Threads opens and <em>Show on page</em> leaves
          (<code>floating-panel.js</code>, "Opened"). The panel also has an
          <code>data-expanded</code> state, <em>More room to write</em>, which widens it
          to 760&#8239;px for a long draft. Candidate C borrows that width for reading.
        </p>
        <table id="room-table">
          <thead>
            <tr>
              <th scope="col">Where the thread stands</th>
              <th scope="col">Width</th>
              <th scope="col">Thread shown at once</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Margin card (today)</th>
              <td>444&#8239;px</td>
              <td>864 of 1245&#8239;px, 69%</td>
            </tr>
            <tr>
              <th scope="row">Panel's thread view (today, via Threads)</th>
              <td>540&#8239;px</td>
              <td>778 of 1007&#8239;px, 77%</td>
            </tr>
            <tr>
              <th scope="row">Panel at reading size (prototype)</th>
              <td>760&#8239;px</td>
              <td>839 of 839&#8239;px, all of it</td>
            </tr>
          </tbody>
        </table>
        <p>
          These figures come from the thread in your screenshot, its three longest
          messages, in a 1640×1010 window. That size reproduces your card's position
          beside the column. Chromium and Firefox measure the same to the pixel.
        </p>
      </section>

      <lf-ask id="route-ask">
        <h2>How should a card hand its thread to the panel?</h2>
        <p>
          Each candidate starts from the card a <kbd>t</kbd> walk opens. B and C add
          <em>Open in panel</em> to the card's head, beside Resolve and Close. The card
          closes, so one thread stands open, and the view takes focus. The way back is
          the view's existing <em>Show on page</em>.
        </p>
        <lf-playground
          id="route-playground"
          data-width="available"
          submit-label="Build this route"
        >
          <lf-playground-preview>
            <lf-playground-control
              id="route-choice"
              name="format"
              label="Route into the panel"
              kind="choice"
              value="b"
            >
              <lf-playground-choice
                value="baseline"
                label="A. Keep Threads as the only way in"
              >
                <p>
                  <small class="tag">no change</small> Close the card, press the Threads
                  mark, then the thread's row: three presses. The view opens at
                  540&#8239;px.
                </p>
                <div class="route-frames">
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/start-card.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/start-card.png"
                        alt="Today's margin card, 444 px wide at the window's right edge, its transcript scrolling, with Resolve and Close in its head."
                    /></a>
                    <figcaption>The card a walk opens.</figcaption>
                  </figure>
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/today-panel.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/today-panel.png"
                        alt="The same thread in the panel's thread view, 540 px wide, centred over the page, still scrolling."
                    /></a>
                    <figcaption>After Threads, then the row.</figcaption>
                  </figure>
                </div>
              </lf-playground-choice>
              <lf-playground-choice value="a" label="B. Add Open in panel to the card">
                <p>
                  <small class="tag">one press</small>
                  <small class="tag">today's size</small> The view opens where Threads
                  would open it, 540&#8239;px wide, still scrolling about a quarter of
                  this thread.
                </p>
                <div class="route-frames">
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/card-with-button.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/card-with-button.png"
                        alt="The margin card with an expand icon added before Resolve and Close."
                    /></a>
                    <figcaption>Open in panel, the expand icon.</figcaption>
                  </figure>
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/panel-panel.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/panel-panel.png"
                        alt="The thread in the panel's view at 540 px, the card gone."
                    /></a>
                    <figcaption>After the press.</figcaption>
                  </figure>
                </div>
              </lf-playground-choice>
              <lf-playground-choice
                value="b"
                label="C. Add Open in panel, opening at reading size"
              >
                <p>
                  <small class="tag">one press</small>
                  <small class="tag">recommended</small> The view opens at More room to
                  write's 760&#8239;px, and may rise to 24&#8239;px from the window's
                  top rather than 160&#8239;px. This thread fits whole. The panel goes
                  back to its usual size when the view closes.
                </p>
                <div class="route-frames">
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/card-with-button.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/card-with-button.png"
                        alt="The margin card with an expand icon added before Resolve and Close."
                    /></a>
                    <figcaption>Open in panel, as in B.</figcaption>
                  </figure>
                  <figure>
                    <a
                      href="evals/decision-options-fit-the-window/captures/reading-panel.png"
                      ><img
                        src="evals/decision-options-fit-the-window/captures/reading-panel.png"
                        alt="The thread in the panel at 760 px wide and nearly the window's height, every message visible with no scrolling."
                    /></a>
                    <figcaption>After the press: the whole thread.</figcaption>
                  </figure>
                </div>
              </lf-playground-choice>
            </lf-playground-control>
            <p id="sample-note">
              Try the selected candidate below: press the comment marker beside "Land
              lf-diff's rows", or <kbd>t</kbd> inside the window, then the expand icon
              in the card's head. The window is smaller than yours, so it scrolls
              sooner.
            </p>
            <lf-sample id="route-sample" label="long thread" window>
              <template
                id="route-sample-page"
                data-sample
                data-sample-events="route-sample-history"
              >
                <header id="sample-top">
                  <h1>Issue triage</h1>
                  <p class="lede">
                    A fixture holding one long thread beside a decision.
                  </p>
                </header>
                <section id="sample-intro">
                  <h2>Where things stand</h2>
                  <p>
                    Three of the open issues wait on a decision. The first is about
                    whether a diff's rows should be drawn before the page first shows,
                    which trades a slightly later first paint for no shift once
                    highlighting arrives.
                  </p>
                  <p>
                    The others are smaller. A shortcut to expand everything waiting, and
                    a URL that opens a specific thread, which the overseer needs before
                    it can link to one.
                  </p>
                </section>
                <section id="sample-proto-diff-ask">
                  <h2>Land lf-diff's rows before first paint? (#3174)</h2>
                  <p>
                    Demo: an lf-diff with an inline patch draws its file headers,
                    separators and plain-text rows before the page first shows, at their
                    final height, with no data-height. Pierre then colours the lines in
                    place. Branch proto/3174-diff-first-paint: 10 files, +850 / −445,
                    mostly in packages/diff, 40 commits behind main.
                  </p>
                  <p>
                    Measured against main, the gain is smaller than the issue suggested.
                    Main doesn't first-paint an empty box. It shows the raw patch in a
                    plain pre at about the right height, then shifts 10 px when Pierre's
                    drawing replaces it, and a correct data-height removes even that.
                    These are medians over several runs on a slow device.
                  </p>
                  <p>
                    The prototype buys the coloured diff about 150 ms sooner and removes
                    that 10 px. In return every inline-diff page gets 84 KB more
                    render-blocking document and 15 ms more main-thread work before
                    first contentful paint.
                  </p>
                  <p>
                    A third option styles the fallback pre to the drawn diff's height in
                    CSS and retires the height advice for inline diffs. It needs no
                    script and no second drawing path, and it's a hypothesis until
                    measured the same way.
                  </p>
                  <p>
                    Recommendation: don't land the prototype. Try the CSS fallback
                    height, measure it the same way, and land it if it removes the
                    shift.
                  </p>
                </section>
                <section id="sample-later">
                  <h2>Later</h2>
                  <p>
                    The overseer should wait for a URL that opens a specific thread, its
                    main gap. The value slice lands after #3929 merges, moving all five
                    widgets at once.
                  </p>
                  <p>Nothing else here waits on you.</p>
                </section>
              </template>
            </lf-sample>
          </lf-playground-preview>
          <lf-playground-output>
            Build route <lf-playground-value for="format"></lf-playground-value> from
            the thread-expanded-panel prototype into the runtime properly: the card's
            Open in panel press with a keyboard route, the reply being written carried
            along as Show on page carries it, and the panel's header comment updated.
            Show me a before/after still and the journey in Firefox.
          </lf-playground-output>
        </lf-playground>
      </lf-ask>

      <section id="considered">
        <h2>What each candidate leaves open</h2>
        <ul>
          <li id="open-draft">
            <strong>A reply being written in the card.</strong> The prototype drops it
            from view when the card closes, though the draft is kept. Building B or C
            would carry it into the panel's field, the reverse of what Show on page
            already does (<code>releaseReplies</code>).
          </li>
          <li id="open-back">
            <strong>The view's back link reads "‹ Threads".</strong> A thread's view
            always stands over Threads, wherever it was opened from. I'd leave that,
            since Show on page is the way back to the card.
          </li>
          <li id="open-threads-route">
            <strong>Whether Threads opens a thread at reading size too.</strong> C gives
            reading size only to a thread the card handed over, so opening a thread from
            Threads moves nothing at the panel's foot. Making every thread's view
            760&#8239;px is one rule fewer, but the foot's controls would shift sideways
            as the view opens.
          </li>
          <li id="open-in-place">
            <strong>Not built: the card growing in place.</strong> At your window the
            room beside the column is about 440&#8239;px, so a wider card covers the
            passage it discusses, much as the panel does. It would also give the card a
            second large reading mode beside the panel's.
          </li>
        </ul>
      </section>
    </main>
    <script id="route-sample-history" type="application/json">
      [
        {
          "kind": "comment",
          "author": "user",
          "text": "the tradeoff here is basically being faster & more responsive, vs avoiding any shift after paint?\n\nand the latter option also means the code gets more complicated?",
          "id": "tradeoff-question",
          "anchor": {
            "section": "sample-proto-diff-ask"
          }
        },
        {
          "kind": "reply",
          "author": "agent",
          "text": "Mostly yes on complexity. Speed against shift is closer than that, though, because there are three states, not two:\n\n- **Main, no `data-height`:** the earliest first paint, then an empty diff box until the diff module loads Pierre, and then the content below jumps.\n- **Main, correct `data-height`:** the same first paint and no jump, but the box stays empty until Pierre loads. A diff wraps, so its height depends on width, and one number is right at only one width. The agent also has to keep the number current after every edit.\n- **Prototype:** the diff's text is in the first paint itself, at its final height at every width, so it shows sooner than on main and never jumps. The cost is a ~50 KB inline script (14 KB gzipped) parsed before first paint, so first paint itself may come slightly later. I haven't measured that delay, so I've started a base-against-prototype startup comparison and will put the numbers on [the decision](#proto-diff-ask).\n\nOn complexity: yes. Leaf gains a second drawing path that has to match Pierre's metrics exactly (+850 / −445). It also had to cancel three page-level CSS rules, and the row assembly is written twice until it's unified. In exchange, inline diffs drop `data-height`, the advice that asks for it, and one known-finding exemption. So it's more Leaf code for less author work.\n",
          "parent": "tradeoff-question",
          "responds": "tradeoff-question",
          "agent": "Claude"
        },
        {
          "kind": "reply",
          "author": "agent",
          "text": "The measurement is on [the decision](#proto-diff-ask), and it changed my advice. Main's start is better than either of us assumed. It already shows the raw patch at first paint, at about the right height, and shifts only 10 px when the drawn diff replaces it.\n\nSo the prototype buys the coloured diff about 150 ms sooner (420 ms at 4× throttle) and removes that 10 px. In return every inline-diff page gets 84 KB more render-blocking document and 15 ms more main-thread work before first contentful paint (74 ms at 4×). The page also shows the server's state 30 ms later (200 ms at 4×).\n\nI now recommend a new option: style the fallback `<pre>` to the drawn diff's height in CSS and retire the height advice for inline diffs. That needs no script and no second drawing path. It's a hypothesis until measured the same way.\n",
          "parent": "tradeoff-question",
          "responds": "tradeoff-question",
          "agent": "Claude"
        }
      ]
    </script>
  </body>
</html>
```
