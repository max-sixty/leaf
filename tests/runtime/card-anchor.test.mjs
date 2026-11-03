import assert from "node:assert/strict";
import test from "node:test";
import { CardAnchor } from "/runtime/thread/card-anchor.js";
import { threadChange } from "/runtime/thread/held-news.js";
import { inputCount, onUserInput } from "/runtime/focus.js";

const beside = { side: "right", adopted: false, fresh: false };

// The browser owns these measurements; this suite exercises the conversation's
// choice of what to preserve, independently of Floating UI and browser layout.
function card(t) {
  const surface = document.createElement("aside");
  surface.innerHTML = `<div class="lf-thread-transcript" style="height:100px">
    <button>Show progress</button>
  </div><div class="lf-thread-reply"><leaf-text tabindex="0"></leaf-text></div>`;
  document.body.append(surface);
  const transcript = surface.querySelector(".lf-thread-transcript");
  const control = surface.querySelector("button");
  const field = surface.querySelector("leaf-text");
  field.value = "";
  let controlOffset = 20;
  surface.getBoundingClientRect = () => new DOMRect(400, 200, 320, 200);
  control.getBoundingClientRect = () => new DOMRect(410, 200 + controlOffset, 80, 24);
  const anchor = new CardAnchor(surface);
  const stop = onUserInput((event) => {
    anchor.pressed(event, inputCount());
  });
  t.after(() => {
    stop();
    surface.remove();
  });
  const place = (seat = beside) => {
    const prepared = anchor.prepare(seat);
    prepared.commit();
    return prepared.edge;
  };
  return {
    anchor,
    field,
    place,
    grow(height, offset = controlOffset) {
      transcript.style.height = `${height}px`;
      controlOffset = offset;
    },
    press() {
      control.dispatchEvent(new window.PointerEvent("pointerdown", { bubbles: true }));
    },
    scroll() {
      control.dispatchEvent(new window.WheelEvent("wheel", { bubbles: true }));
    },
  };
}

test("Send owns its result and receipt, then arriving words resume ordinary reading", (t) => {
  const { anchor, place } = card(t);
  // The shared news reading distinguishes own optimistic words, receipt, and more
  // words in an already displayed stream without inventing a second content diff.
  const reading = (messages) => ({
    messages,
    summaries: [],
    source: { msgs: messages },
  });
  const streamed = (text) => ({
    id: "stream",
    key: "stream",
    author: "agent",
    provisional: true,
    body: text,
  });
  const own = { id: "pending", key: "sent turn", author: "user", body: "My reply" };
  const before = reading([streamed("Opening words")]);
  const sent = reading([own, streamed("Opening words and held news")]);
  const accepted = reading([
    { ...own, id: "durable" },
    streamed("Opening words and held news"),
  ]);
  const growing = reading([
    { ...own, id: "durable" },
    streamed("Opening words and held news, now continuing"),
  ]);
  assert.equal(place(), "top");
  anchor.sending("sent turn");
  // A local repaint before optimistic presentation cannot consume the operation.
  anchor.presented();
  assert.equal(place(), "foot");
  anchor.presented(threadChange(before, sent)?.joined);
  // Send also owns held news revealed together with its optimistic words.
  assert.equal(place(), "foot");
  anchor.presented(threadChange(sent, accepted)?.joined);
  window.dispatchEvent(new window.WheelEvent("wheel"));
  assert.equal(place(), "foot");
  const arrived = threadChange(accepted, growing)?.joined;
  assert.equal(anchor.newsMoves(arrived), false);
  // Prediction is read-only until those words actually show.
  assert.equal(place(), "foot");
  anchor.presented(arrived);
  assert.equal(place(), "top");

  anchor.sending("second send");
  anchor.presented(new Set(["second send"]));
  assert.equal(place(), "foot");
  anchor.writing();
  anchor.presented();
  assert.equal(place(), "top");
});

test("native and restored writing reclaim the reply without comparing draft history", (t) => {
  const { anchor, field, place } = card(t);
  place();
  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  assert.equal(place(), "foot");
  field.value = "Words restored after refusal";
  assert.equal(place(), "top");
  assert.equal(anchor.newsMoves(new Set(["answer"])), true);
  field.value = "";
  anchor.presented(new Set(["sent turn"]));
  assert.equal(place(), "top");
});

test("a box written in after Send stays written in once its words are erased", (t) => {
  const { anchor, field, place } = card(t);
  field.focus();
  place();
  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  // The empty box Send left the caret in lets the answer show.
  assert.equal(anchor.newsMoves(new Set(["answer"])), false);
  // The user types there and erases the words: still writing, so news waits.
  anchor.writing();
  field.value = "A";
  field.value = "";
  assert.equal(anchor.newsMoves(new Set(["answer"])), true);
});

test("above its subject a card keeps its foot, read or written in", (t) => {
  const { anchor, field, place } = card(t);
  const above = { ...beside, side: "top" };
  assert.equal(place(above), "foot");
  // A draft grows up over the transcript, leaving the subject below in view.
  field.focus();
  anchor.writing();
  field.value = "A draft";
  assert.equal(place(above), "foot");
  // Beside its subject the same draft keeps the top.
  assert.equal(place(beside), "top");
});

test("coming back into the box Send left is writing again", (t) => {
  const { anchor, field, place } = card(t);
  field.focus();
  place();
  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  assert.equal(anchor.newsMoves(new Set(["answer"])), false);
  anchor.leftReply();
  assert.equal(anchor.newsMoves(new Set(["answer"])), true);
});

test("beside its subject a card rises as it grows, unless a press or a send holds it", (t) => {
  const { anchor, field, press, grow } = card(t);
  // Read or written in, it rises from the top it holds; under its subject it only
  // grows down.
  assert.equal(anchor.prepare(beside).rises, true);
  assert.equal(anchor.prepare({ ...beside, side: "bottom" }).rises, false);
  field.value = "A draft";
  assert.equal(anchor.prepare(beside).rises, true);
  field.value = "";
  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  assert.equal(anchor.prepare(beside).rises, false);
  // An answer arriving releases the send's foot, and the card rises to show it.
  anchor.presented(new Set(["answer"]));
  assert.equal(anchor.prepare(beside).rises, true);
  press();
  grow(160, 80);
  assert.equal(anchor.prepare(beside).rises, false);
});

test("a news query before Send masks its words cannot release the sent place", (t) => {
  const { anchor, field, place } = card(t);
  field.value = "A reply being sent";
  place();
  anchor.sending("sent turn");
  assert.equal(anchor.newsMoves(new Set(["answer"])), true);
  field.value = "";
  anchor.presented(new Set(["sent turn"]));
  assert.equal(place(), "foot");
});

test("a press retains its changed control through fits but not later input or news", (t) => {
  const { anchor, place, press, grow, scroll } = card(t);
  place();
  press();
  grow(160, 80);
  assert.equal(place(), "foot");
  assert.equal(place(), "foot");
  // An unrelated append is not still the disclosure press's mutation.
  grow(180);
  assert.equal(place(), "top");

  // A change still awaiting placement is already visible when the user presses.
  // Their action can return to the last landed height while moving the control.
  grow(240);
  press();
  grow(180, 120);
  assert.equal(place(), "foot");

  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  assert.equal(place(), "foot");
  press();
  grow(220);
  // This disclosure grew below the control: keep its top, overriding Send's foot.
  assert.equal(place(), "top");
  scroll();
  // The press ends even without another extent change. Send has a separate lifetime.
  assert.equal(place(), "foot");
  grow(260);
  // Scrolling inside the card is not a press that owns the next layout change.
  assert.equal(place(), "foot");
});

test("adoption overrides a conversation hold and a fresh seat releases it", (t) => {
  const { anchor, place } = card(t);
  place();
  anchor.sending("sent turn");
  anchor.presented(new Set(["sent turn"]));
  assert.equal(place({ ...beside, adopted: true }), "top");
  assert.equal(place({ ...beside, side: "top", adopted: true }), "foot");
  assert.equal(anchor.newsMoves(new Set(["answer"])), true);
  assert.equal(place({ ...beside, fresh: true }), "top");
  assert.equal(anchor.newsMoves(), false);
  anchor.sending("sent turn");
  anchor.forget();
  assert.equal(place(), "top");
});

test("a superseded preparation cannot consume a press's layout change", (t) => {
  const { anchor, place, press, grow } = card(t);
  place();
  press();
  grow(160, 80);
  assert.equal(anchor.prepare(beside).edge, "foot");
  // A second fit reads the same still-uncommitted change.
  assert.equal(place(), "foot");
  assert.equal(place(), "foot");

  press();
  grow(200, 120);
  const prepared = anchor.prepare(beside);
  press();
  prepared.commit();
  grow(240, 160);
  // A press captured during fitting owns its next change, not the earlier press.
  assert.equal(place(), "foot");
});
