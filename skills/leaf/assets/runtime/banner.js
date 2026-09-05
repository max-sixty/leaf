import { clocked } from "./presence.js";

export function createBanner({
  agentName,
  ago,
  announce,
  dot,
  el,
  presented,
  statusText,
  notice,
}) {
  // ---------- banner ----------
  const TONE = {
    working: "working",
    listening: "listening",
    stalled: "away",
    away: "away",
    unheld: "",
    unattended: "",
    closed: "",
  };
  const toneFor = (kind) => TONE[kind];
  // The judgment's third seat. A reader keeps a leaf in a tab for days and looks at
  // six of them; the tab strip is the whole of what the browser shows about a page nobody
  // has open, so the state that decides whether to go there belongs in it. Same judgment
  // (presented), same writer as the dot and the line, and the tone is taken off the dot
  // itself rather than mapped from kind to token again — one answer to what a tone looks
  // like, so a project overriding --ok overrides the tab with it and the two cannot come
  // apart. It is a read of the theme, not of the rendering: what colour this tone paints
  // as is a question nothing else can answer, where what state the page is in is already
  // in hand.
  //
  // The mark is the vendored icon.svg — the page's own asset like the theme, so a project
  // can put its own there — and all the runtime does to it is paint the one element it
  // declares. Refused rather than defaulted, as the theme's shadow block is: a mark with
  // no lf-tone leaves a tab that never changes, which is a status readout that silently
  // isn't one.
  const tabLink = Object.assign(document.createElement("link"), {
    rel: "icon",
    type: "image/svg+xml",
    href: "/icon.svg",
  });
  document.head.append(tabLink);
  let iconMark = null;
  const iconUrls = new Map();
  // The mark with one colour written over it, or — for "" — the mark as authored. A style
  // element appended last outranks the file's own rules, the dark-scheme block included,
  // since a media query carries no specificity of its own. So this knows nothing about the
  // icon beyond the class it promises, and a project's own mark is painted on the same
  // terms.
  function iconUrl(color) {
    let url = iconUrls.get(color);
    if (url === undefined) {
      const svg = iconMark.cloneNode(true);
      if (color) {
        const style = svg.ownerDocument.createElementNS(
          "http://www.w3.org/2000/svg",
          "style",
        );
        style.textContent = `.lf-tone { fill: ${color} }`;
        svg.append(style);
      }
      url =
        "data:image/svg+xml," +
        encodeURIComponent(new XMLSerializer().serializeToString(svg));
      iconUrls.set(color, url);
    }
    return url;
  }
  async function loadIcon() {
    const response = await fetch("/icon.svg");
    if (!response.ok)
      throw new Error(`leaf: the tab icon failed to load (${response.status})`);
    const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
    // Two failures, and the same symptom: no element to paint. A parse error is reported
    // as a document rather than thrown, so a mark that isn't SVG at all reaches the class
    // check and fails it — sending whoever overrode the file to look for a class that is
    // sitting right there in it.
    const broken = doc.querySelector("parsererror");
    if (broken)
      throw new Error(
        // Collapsed, because the browser's report is laid out as a page and reads as
        // several lines of it; what matters is the line and column it names.
        `leaf: icon.svg is not SVG — ${broken.textContent.replace(/\s+/g, " ").trim()}`,
      );
    if (!doc.querySelector(".lf-tone"))
      throw new Error(
        "leaf: icon.svg carries no lf-tone element, which is where the page's " +
          "status is painted",
      );
    iconMark = doc.documentElement;
    // Left where `version export` can find it: a file has no session behind it, so a copy
    // wears the mark saying nothing rather than the tone it was exported under.
    tabLink.dataset.lfRest = iconUrl("");
    paintTab();
  }
  // A declaration, and called from two places, because the fetch above can land after the
  // first poll has already judged the page.
  function paintTab() {
    if (!iconMark) return;
    const url = iconUrl(getComputedStyle(dot).backgroundColor);
    // Written only on change: an unchanged poll must not hand the browser its icon again
    // every two seconds.
    if (tabLink.getAttribute("href") !== url) tabLink.setAttribute("href", url);
  }
  // One writer for the dot, the line, the tab and the live region, offline included: null
  // is the poll saying it couldn't reach the server, not a second function's own
  // rendering. The line wins the row's width now and wraps to two, so what a narrow
  // window still clips is a hover away, the way the version chooser's label is. Written
  // every time rather than only when the box clips, because whether it does is a fact
  // about the rendering and nothing here reads that back.
  //
  // The live region is the fourth seat and the one that must not be written every time.
  // This line is rewritten on every poll — an age moving, a count turning over, a detail
  // rephrased — and a region repeating all of that is a page talking over the reader it
  // is talking to. What is worth interrupting for is the kind changing: work starting, a
  // turn ending, the server going and coming back. What it says then is the banner's own
  // sentence, so what is heard and what is on the row are one line rather than two
  // accounts of it. The first reading is the page arriving rather than a change in it,
  // and arriving is the document's own announcement.
  let saidKind;
  const showStatus = (kind, tone, ...parts) => {
    dot.className = "lf-dot" + (tone ? " " + tone : "");
    statusText.textContent = "";
    statusText.append(...parts);
    statusText.title = statusText.textContent;
    paintTab();
    const changed = saidKind !== undefined && saidKind !== kind;
    saidKind = kind;
    if (changed) announce(statusText.textContent);
  };
  // A reload the page has decided on its own: a layer that has moved under it, or a
  // version it could not show. The reader is looking at a page that is about to go, and a
  // tab reloading with nothing said is the page appearing to lose their place for no
  // reason. One line, in the seat the rest of the banner's news arrives in, said out loud
  // as well — a reload is exactly the moment a reader not watching the banner needs
  // telling, and there is no kind here to have changed.
  function sayLine(text) {
    showStatus(saidKind, "", text);
    announce(text);
  }
  let previewButton = null;
  let previewDiagnostics = "";
  function renderPreview(state) {
    const preview = state.preview;
    if (!preview) return;
    const commit = preview.commit
      ? `@${preview.commit}${preview.dirty ? "+" : ""}`
      : "";
    const kind = preview.interaction === "automation" ? "Automation" : "Preview";
    const label = `${kind} · ${preview.checkout}${commit}`;
    const safeUrl = new URL(location.href);
    safeUrl.searchParams.delete("t");
    previewDiagnostics = [
      "Leaf preview",
      `example: ${preview.example}`,
      `checkout: ${preview.checkout}`,
      `interaction: ${preview.interaction}`,
      ...(preview.commit ? [`commit: ${preview.commit}`] : []),
      ...(preview.dirty !== undefined ? [`dirty: ${preview.dirty}`] : []),
      `started: ${preview.started}`,
      `layer generation: ${state.layer.generation}`,
      ...(state.layer.fingerprint
        ? [`layer fingerprint: ${state.layer.fingerprint}`]
        : []),
      ...(state.active ? [`revision: ${state.active.revision}`] : []),
      `event sequence: ${state.events.at(-1)?.seq ?? 0}`,
      `url: ${safeUrl}`,
    ].join("\n");
    if (!previewButton) {
      previewButton = el("button", "lf-btn lf-preview", label);
      previewButton.type = "button";
      previewButton.setAttribute("aria-label", "Copy preview diagnostics");
      previewButton.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(previewDiagnostics);
          notice("Copied preview diagnostics");
        } catch (_error) {
          notice("Couldn't copy preview diagnostics");
        }
      });
      statusText.before(previewButton);
    }
    previewButton.textContent = label;
    previewButton.title = `${preview.example} · started ${preview.started} · copy diagnostics`;
  }
  function renderStatus(state) {
    if (state instanceof Error) {
      showStatus("broken", "offline", "Page couldn't apply current state — reload");
      return;
    }
    if (state === null) {
      showStatus(
        "unreachable",
        "offline",
        "Server offline — reconnecting. Keep this page open so pending changes can send.",
      );
      return;
    }
    renderPreview(state);
    const { status, pending } = state;
    const { kind, quiet, dropped, detail } = presented(state);
    // What the user's words do meanwhile. The log takes them with nobody on the other
    // end; the only thing attendance changes is when they are read.
    const saved = pending
      ? `${pending} update${pending === 1 ? "" : "s"} waiting.`
      : "Your comments are saved.";
    // Dated by whichever fact ended the belief. A dropped claim is dated by the ending
    // and not by its own last word, because "last checked in just now" under an amber
    // dot is the line arguing with the dot beside it.
    const dated = dropped
      ? `${agentName()} left this when its turn ended ${ago(state.turn_closed)}`
      : `${agentName()} last checked in ${ago(status.ts)}`;
    let text = "",
      showAge = false;
    if (kind === "closed") text = "Leaf closed";
    else if (kind === "unattended")
      // No agent named and no pickup promised, which is the whole difference from
      // `unheld` below: there is nobody to name and nothing coming. What the reader can
      // still do is everything — the page works, it just works alone — so the line says
      // where their gestures go rather than that they are saved for someone.
      text = "Nobody is behind this page. What you do here stays in this browser.";
    else if (kind === "unheld")
      // No agent is named, because which one picks the page up next is not a fact this
      // page holds — only that the log is there for whichever does.
      text = `No session holds this page. ${saved} It picks up again when a session does.`;
    else if (kind === "working") {
      showAge = Boolean(status.ts);
      text = `${agentName()} is working${detail ? " — " + detail : ""}`;
    } else if (kind === "listening") {
      // Attendance is half the news; the other half is what the page wants back. The
      // Decisions count beside it says how many things are unanswered and nothing about what
      // any of them is, so the claim's detail says that here in the agent's own words,
      // the way a `working` claim's says what it is doing. With nothing declared it is
      // the standing instruction, which is what a page asking nothing wanted anyway.
      //
      // "awaits" while the judged kind stays `listening`: they name different things.
      // The kind and the server field behind it are the evidence — a watcher live on the
      // other end — and the words are the stance it supports, which is the registry's
      // own word for a standing decision for the reader (x-awaits). Wording is the seat's,
      // per `presented`, so a row in the leaves panel leads with the bare word and
      // carries the same decision behind it.
      text = `${agentName()} awaits — ${detail || "select text to comment"}`;
    } else if (kind === "stalled") {
      // The claim stands, dated, with no remedy attached: a watcher is live, so the
      // reader's next word reaches the agent without anyone touching a terminal. What
      // they are owed is the age, which is the one thing they cannot see for themselves
      // and the whole of what separates a delegate mid-answer from a dropped thread. It
      // is spoken in the same words the branch below uses for the same silence, rather
      // than in the muted parenthesis a live `working` claim wears: there the age is a
      // footnote to news, and here it is the news.
      text = `${dated}${detail ? ": " + detail : ""}. ${saved}`;
    } else {
      // Somebody is behind the page and isn't attending: say which and what to do. A
      // long silence means Claude lost the thread; a recent check-in means it is
      // mid-turn and the next one collects.
      const [why, how] = quiet
        ? [`${dated}.`, "Nudge it in the terminal."]
        : [`${agentName()} isn't watching right now.`, "It picks them up next turn."];
      text = `${why} ${saved} ${how}`;
    }
    const line = [text];
    if (showAge)
      line.push(
        " ",
        Object.assign(el("span", "lf-age"), { textContent: `(${ago(status.ts)})` }),
      );
    showStatus(kind, TONE[kind], ...line);
  }

  return {
    loadIcon,
    renderStatus: clocked(document.body, renderStatus),
    sayLine,
    toneFor,
  };
}
