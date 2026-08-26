/* lf-shot: a before/after pair of screenshots of one view, shown one at a time in one
 * frame.
 *
 * The comparison is a flip, not a wipe. A wipe puts the two states either side of a
 * divider, so it reads a change only where the change happens to cross the divider;
 * anything wholly on one side is a thing the eye has to carry across the seam and hold
 * in memory. Swapping one registered frame for the other leaves the change as the only
 * thing on screen that moves — the blink comparator's trick, and how it found a planet.
 *
 * That works because the eye holds still, so what the flip costs to work is the whole of
 * what it is worth. The switch was a radio each under the frame: two targets 83px apart
 * and 20px tall, together a fiftieth of the image's area, so every alternation spent a
 * look away from the change, an aim, and a re-aim for the second click — and a
 * comparison is many alternations. The frame is the target now. A transparent label
 * over the image drives one checkbox, so the pointer rests on the change and clicks
 * without aiming, and the two states swap under it.
 *
 * Everything that needs is native: the state is a checkbox, the swap a `:has(:checked)`
 * rule in the theme. No handler runs after the upgrade, so a serialized copy of this
 * page — DOM kept, script tags dropped — still flips, and a printed one stacks both
 * frames instead. A dragged slider would have survived neither.
 *
 * Two kinds of word, and they are marked differently on purpose. Each frame's caption
 * names which state it holds, which is the widget's own word and the only thing telling
 * the two frames apart once paper has both of them on the page: data-lf-gen alone, so
 * the version diff looks away and the user can still select it. The switch under the
 * frame is a thing to press, so it goes through `offer` with the rest of the chrome.
 * What the page has to say about the change itself is neither — it is prose, written
 * around the element, where a comment can reach it like any other sentence. */
import { once, offer, failSoft, keys, paintKeys, settle } from "/runtime/widget-api.js";

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const alt = this.getAttribute("alt");
      const shots = [];

      for (const state of ["before", "after"]) {
        const frame = document.createElement("div");
        frame.className = "lf-shotframe";
        frame.dataset.lfGen = "1";
        frame.dataset.lfState = state;

        const img = document.createElement("img");
        img.src = this.getAttribute(state);
        img.alt = `${state}: ${alt}`;
        shots.push(img);
        const caption = document.createElement("span");
        caption.className = "lf-shotcap";
        caption.dataset.lfGen = "1";
        caption.textContent = state;
        frame.append(img, caption);
        this.append(frame);
      }

      // The target: transparent, the frame's own size, and driving the checkbox below by
      // `for`. It carries the offer marker like any other control a widget hangs, so
      // paper drops it and a float steps around it where one would otherwise stand on
      // the image; the copy keeps it, the checkbox's state being the browser's.
      const flip = offer("label", "lf-shotflip");
      flip.htmlFor = `lf-shot-${this.id}-flip`;

      // The switch sits under the frame and not on it. It is not what the reader works
      // during a comparison — the image is — so it is the keyboard's handle and the word
      // that says the image is live, and a chip in the frame's corner buys neither of
      // those at the price of covering the change it is there to show. Put there first,
      // it landed on the very pill the pair existed to show.
      const row = offer("div", "lf-shotpick");
      const label = offer("label", "");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.id = flip.htmlFor;
      // `.lf-ui` because it carries an id: which item a comment is on is asked as
      // `[id]:not(.lf-ui)` of the element itself, so an injected id without the class
      // answers that question with itself.
      box.className = "lf-ui";
      box.ariaLabel = `${alt}: show the after state`;
      // The word for the bigger target is this label's own, not a note beside it. A
      // pointer cursor is the only other thing saying the image is live, and it says so
      // to whoever has already hovered — while an offer standing outside a control, with
      // words and nothing to work, is what a copy has no way to honour
      // (`test_an_exported_example_stands_on_its_own` refuses one). Inside, the press the
      // words name is the label over the frame, and paper drops both together.
      label.append(box, " flip — or click the image");
      row.append(label);

      // Space is the platform's here, the control being a checkbox, so the row binds no
      // `run`: binding one would toggle a box the browser has already toggled. It carries
      // a word all the same, which is the whole of what it is for — a press the reader
      // can make and no surface names is this register's own inversion, and the runtime's
      // control scope cannot reach it, matching a tab stop of its own making where this
      // control brought its own. Enter is left out because a checkbox answers it only as a
      // form's submit, and there is no form on a leaf page.
      keys(box, "On a screenshot", [
        {
          keys: [" "],
          does: () => `Show the ${box.checked ? "before" : "after"} frame`,
          line: () => `show ${box.checked ? "before" : "after"}`,
        },
      ]);
      // A toggle is no focus move, so nothing else would repaint the word it just changed.
      box.addEventListener("change", paintKeys);

      this.append(flip, row);
      settle(this.register(shots));
    }

    // Both frames render at the frame's width, so a pair shot at two different
    // viewports is scaled by two different factors and every line in it lands
    // somewhere new. The flip then says the whole page changed, which is the one
    // failure this widget cannot afford: it is silent, it is convincing, and the
    // reader has no way to tell it from the truth. Heights may differ freely —
    // content reflowing taller is a real thing to see, and it stays registered.
    async register(shots) {
      await Promise.all(shots.map((img) => img.decode().catch(() => {})));
      const [before, after] = shots.map((img) => img.naturalWidth);
      if (before && after && before !== after)
        failSoft(
          this,
          new Error(
            `before is ${before}px wide and after is ${after}px — a pair has to be shot ` +
              `at one viewport, or the flip moves everything`,
          ),
        );
    }
  },
);
