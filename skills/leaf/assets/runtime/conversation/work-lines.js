/* Live work claims rendered at their thread or widget-owned seats. */
export function createWorkLines(dependencies) {
  const {
    agentName,
    ago,
    claimState,
    droppedAt,
    el,
    elementById,
    inChrome,
    matchesWhen,
    pageQueryAll,
    quietSince,
    registry,
    runtime,
    threads,
    threadsBox,
    updateSequence,
  } = dependencies;

  // One writer for every local work line. Which box it stands in is the subject's — a
  // thread's complete or inline seat, a widget's declared conversation, or a prose
  // widget itself — while the sentence, silence word, and clock are identical. Lines are
  // kept across polls so an unchanged claim is not announced again every two seconds.
  function paintWorkLine(host, update, before, wanted) {
    if (!host) return;
    const { kind, id } = update.target;
    let line = [...host.children].find(
      (child) =>
        child.matches(".lf-work-line") &&
        child.dataset.subjectKind === kind &&
        child.dataset.subjectId === id,
    );
    if (!line) {
      line = el("div", "lf-work-line lf-ui");
      line.dataset.lfGen = "1";
      line.dataset.subjectKind = kind;
      line.dataset.subjectId = id;
      line.append(el("span"), el("time"));
    }
    const next = before ?? null;
    if (line.parentElement !== host || line.nextSibling !== next)
      host.insertBefore(line, next);
    wanted.add(line);
    const what = line.firstElementChild;
    const when = line.lastElementChild;
    // Written only on change, like the message clocks beside it: an unchanged poll must
    // not hand the reader's screen reader the same sentence every two seconds.
    const said = `${update.agent || agentName()} is on this — ${update.text}`;
    if (what.textContent !== said) what.textContent = said;
    // A claim of work nobody has renewed, said in a word. The banner cannot answer for
    // this seat: every `leaf status … --on` write refreshes the page's own line, so one
    // delegate still reporting keeps the banner green while another's claim ages here —
    // the fleet's dead-row failure one level down, and the reason the roster says this
    // in words rather than leaving it to a tint. Both of the banner's own questions,
    // asked here by the same two predicates: gone unrenewed too long, or left behind by
    // a turn that ended. A local line is written by the command that writes the claim, so a
    // seat answering either question differently would have the page arguing with
    // itself about one silence. `ago` is still rendered whole beside the word rather
    // than reworded to absorb it. The cell is added and removed rather than hidden,
    // because a hidden one still reads out in the thread's text.
    let cold = line.querySelector(":scope > .lf-work-quiet");
    const turnClosed =
      update.session && update.session === claimState().claimingSession
        ? claimState().agentTurnClosed
        : null;
    if (quietSince(update.ts) || droppedAt(update.ts, turnClosed)) {
      if (!cold) line.insertBefore(el("span", "lf-work-quiet", "quiet"), when);
    } else cold?.remove();
    const age = ago(update.ts);
    if (when.textContent !== age) when.textContent = age;
  }

  function widgetWorkSeat(owner) {
    const work = registry[owner.localName]?.["x-work"];
    if (!work || !matchesWhen(owner, work.when)) return null;
    if (work.seat === "content") return { host: owner, before: null };
    const conversation = registry[owner.localName]["x-conversation"];
    if (!matchesWhen(owner, conversation.when)) return null;
    const host = [...owner.children].find(
      (child) =>
        child.matches(".lf-conversation[data-lf-conversation]") &&
        child.dataset.lfConversation === owner.id,
    );
    if (!host) return null;
    const before = [...host.children].find((child) => !child.matches(".lf-work-line"));
    return { host, before: before ?? null };
  }

  // Every local seat for every typed subject. The merged x-work declaration decided at
  // the CLI boundary whether a widget could safely carry one and tells this reading which
  // of the two general seats to use. Core still knows no content-widget tag name. A claim
  // created on a later version cannot leak backward into a pinned historical page.
  function paintWorkLines() {
    const wanted = new Set();
    const claims = claimState().claimsHeld
      ? updateSequence().filter(
          (update) => update.source === "claim" && update.disposition === "effective",
        )
      : [];
    for (const update of claims) {
      const { kind, id } = update.target;
      if (kind === "thread") {
        const thread = threads().find((candidate) => candidate.root.id === id);
        if (!thread || thread.resolved) continue;
        const complete = threadsBox.querySelector(`.lf-thread[data-id="${id}"]`);
        paintWorkLine(
          complete,
          update,
          complete?.querySelector(":scope > .lf-compose"),
          wanted,
        );
        for (const inline of document.querySelectorAll(
          `.lf-conversation-thread[data-thread="${id}"]`,
        ))
          paintWorkLine(
            inline,
            update,
            inline.querySelector(":scope > .lf-say"),
            wanted,
          );
        continue;
      }
      if (kind !== "widget" || update.revision > runtime.currentRevision) continue;
      const owner = elementById(id);
      if (!owner || inChrome(owner)) continue;
      const seat = widgetWorkSeat(owner);
      if (seat) paintWorkLine(seat.host, update, seat.before, wanted);
    }
    for (const line of pageQueryAll(".lf-work-line"))
      if (!wanted.has(line)) line.remove();
  }

  return { paintWorkLines };
}
